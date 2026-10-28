"""Repli DofusDB des fiches : priorité stricte à Duffus, rapprochement sûr, seuil de 5 % après le repli."""

from dataclasses import replace

import pytest

from epreuve.contenu import construire as k
from epreuve.contenu.fiche_dofusdb import FicheRepli, fiches_de_repli
from epreuve.db.depot import ContenuFiche

ASPI = k.Aspiration.lire(k.derniere_aspiration())
CONFIG = k.lire_config_etages()
RETENUS = k.lire_dofus_retenus()


def quete_jeu(id_: int, nom: str = "", depart=None) -> dict:
    """Une quête DofusDB allégée (`alleger_quete_fiche`), une étape, deux objectifs."""
    return {"id": id_, "nom": nom, "prerequis": [7], "objets": [[50, 2]], "depart": depart or [],
            "etapes": [{"id": 1, "nom": "Première étape", "description": "Va <voir> le PNJ.", "recompenses": [
                {"itemsReward": [[50, 3]], "emotesReward": [], "titlesReward": []}], "objectifs": [
                {"genre": "QuestObjectiveGoToNpcData", "texte": "Aller voir {npc,1}", "parametres": [1, 0, 0],
                 "position": [-6, -3]},
                {"genre": "QuestObjectiveMultiFightMonsterData", "texte": "Vaincre x5 {monster,2}",
                 "parametres": [2, 5, 0], "position": None}]}]}


class FauxDofusDB:
    """Un client DofusDB qui note chaque quête demandée."""

    def __init__(self, noms_du_jeu: dict[int, str]) -> None:
        self.noms_du_jeu = noms_du_jeu
        self.demandees: list[int] = []

    async def index_quetes(self):
        return [{"id": i, "name": {"fr": n}} for i, n in self.noms_du_jeu.items()]

    async def quetes_completes(self, ids):
        self.demandees += sorted(ids)
        return {i: quete_jeu(i) for i in ids}

    async def noms(self, genre, ids):
        base = {"npcs": "Mériana", "monsters": "Milimulou", "items": "Kama"}[genre]
        return {i: base + str(i) for i in ids}

    async def cartes(self, ids):
        return {i: [1, 2] for i in ids}


def test_etage_1_une_seule_quete_sans_fiche_duffus():
    manquantes = k.entrees_sans_fiche(1, ASPI, CONFIG, RETENUS)
    assert list(manquantes.values()) == ["Quête de classe"]


async def test_une_quete_avec_fiche_duffus_ne_passe_jamais_par_dofusdb():
    manquantes = k.entrees_sans_fiche(1, ASPI, CONFIG, RETENUS)
    avec_fiche = [q.nom for q in k.construire(1, ASPI, CONFIG, RETENUS, forcer=True).quetes if q.fiche]
    assert len(avec_fiche) == 42
    # DofusDB connaît un homonyme pour CHAQUE quête (avec ou sans fiche Duffus) : seule la manquante est lue.
    client = FauxDofusDB({100 + i: n for i, n in enumerate([*avec_fiche, "Quête de classe"])})
    fiches = await k.fiches_repli_etage(1, ASPI, CONFIG, RETENUS, client)
    assert client.demandees == [100 + len(avec_fiche)] and len(fiches) == len(manquantes) == 1
    e = k.construire(1, ASPI, CONFIG, RETENUS, fiches_repli=fiches)
    assert e.nb_fiches == {"duffus": 42, "dofusdb": 1} and e.sans_fiche == []


def test_construire_ne_remplace_jamais_une_fiche_duffus():
    base = k.construire(1, ASPI, CONFIG, RETENUS, forcer=True)
    piege = FicheRepli(ContenuFiche(recompenses=["PIÈGE"]))
    e = k.construire(1, ASPI, CONFIG, RETENUS, fiches_repli={int(q.duffus_id): piege for q in base.quetes})
    sources = {q.nom: q.source_fiche for q in e.quetes}
    assert sources.pop("Quête de classe") == "dofusdb"
    assert set(sources.values()) == {"duffus"}
    assert all("PIÈGE" not in q.fiche.recompenses for q in e.quetes if q.source_fiche == "duffus")


def norm(n: str) -> str:
    return k._normaliser(n)


async def test_rapprochement_exact_normalise_sinon_pas_de_fiche():
    client = FauxDofusDB({1: "La magicienne des marécages", 2: "Jumelle", 3: "Jumelle", 4: "Autre chose"})
    a_completer = {10: "LA MAGICIENNE des marecages !", 11: "Jumelle", 12: "La magicienne", 13: "Inconnue"}
    fiches = await fiches_de_repli(a_completer, client, norm, {})
    assert fiches[10].fiche is not None and client.demandees == [1]
    for i in (11, 12, 13):  # ambigu (2 quêtes), approximatif (préfixe), absent
        assert fiches[i].fiche is None and fiches[i].alerte


async def test_ambigu_cote_duffus_aussi():
    client = FauxDofusDB({1: "Double"})
    fiches = await fiches_de_repli({10: "Double", 11: "Double"}, client, norm, {norm("Double"): [10, 11]})
    assert all(f.fiche is None and "ambigu" in f.alerte for f in fiches.values()) and client.demandees == []


async def test_la_fiche_dofusdb_a_la_forme_duffus_et_ne_remplit_que_le_connu():
    client = FauxDofusDB({1: "Quête A", 7: "Prérequis"})
    f = (await fiches_de_repli({10: "Quête A"}, client, norm, {norm("Prérequis"): [99]}))[10].fiche
    assert isinstance(f, ContenuFiche)
    assert f.etapes[0].titre == "Première étape" and "&lt;voir&gt;" in f.etapes[0].texte_html
    assert f.etapes[0].objectifs == ("Aller voir Mériana1", "Vaincre x5 Milimulou2")
    assert [(m.nom, m.quantite) for m in f.monstres] == [("Milimulou2", 5)]
    assert [(m.nom, m.quantite) for m in f.objets] == [("Kama50", 2)] and f.recompenses == ["3 × Kama50"]
    assert [(p.x, p.y) for p in f.positions] == [(-6, -3)]
    assert [(p.duffus_id, p.nom) for p in f.prerequis] == [("99", "Prérequis")]  # nom exact et unique chez Duffus
    assert f.succes_lie is None



def test_seuil_de_5_pour_cent_apres_le_repli():
    # Étage 1 : 1 quête sur 43 sans fiche Duffus (2,3 %). On retire 3 pages Duffus : 4/43 = 9 % > 5 %.
    noms = [q.nom for q in k.construire(1, ASPI, CONFIG, RETENUS, forcer=True).quetes if q.fiche][:3]
    pages = dict(ASPI.pages)
    for q in ASPI.quetes.values():
        if q["title"].strip() in noms and (s := k.slug_quete(q)):
            pages.pop(s, None)
    aspi = replace(ASPI, pages=pages)
    with pytest.raises(k.ConstructionArretee):
        k.construire(1, aspi, CONFIG, RETENUS)
    repli = {int(q.duffus_id): FicheRepli(ContenuFiche(recompenses=["x"])) for q in
             k.construire(1, aspi, CONFIG, RETENUS, forcer=True).quetes if q.fiche is None}
    e = k.construire(1, aspi, CONFIG, RETENUS, fiches_repli=repli)  # le repli comble : plus de blocage
    assert e.sans_fiche == [] and e.nb_fiches["dofusdb"] == 4
