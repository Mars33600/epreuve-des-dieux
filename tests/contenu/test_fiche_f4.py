"""Lot F4 : la fiche détaillée (départ, étapes avec positions et quantités), sur de vraies quêtes Duffus."""

from __future__ import annotations

import json

import pytest

from epreuve.contenu import construire as k
from epreuve.contenu.fiche_dofusdb import construire_fiche
from epreuve.contenu.fiche_duffus import lire_fiche

ASPI = k.Aspiration.lire(k.derniere_aspiration())


def fiche_reelle(slug: str):
    entree = next(e for e in ASPI.quetes.values() if (e.get("url") or "").endswith("/" + slug))
    return lire_fiche(ASPI.pages[slug], entree, {}, {}, ASPI.ressources.get(entree["id"], []),
                      ASPI.infos_rapides.get(slug))


def test_sous_le_regard_des_dieux_depart_et_etapes():
    f = fiche_reelle("sous-le-regard-des-dieux")
    d = f.positions[0]
    assert (d.libelle, d.x, d.y, d.zone) == ("Départ : Ganymède", -3, -3, "Incarnam")
    assert f.pnj_depart == "Ganymède"
    combat = next(e for e in f.etapes if e.titre == "Combat")
    assert [(x_.genre, x_.nom, x_.quantite) for x_ in combat.lignes] == [
        ("monstre", "Chafer Éclaireur Céleste", 1), ("monstre", "Chafer Piquier Céleste", 2)]
    assert f.recompenses == ["197 XP"]


def test_etape_de_deplacement_porte_sa_position_lue_sur_le_bouton():
    # « Balade en forêt » : data-coords est resté à « 0,0 », le bouton affiche [-1,-23] (ce que lit le joueur).
    f = fiche_reelle("balade-en-foret")
    deplacements = [e for e in f.etapes if e.titre == "Déplacement"]
    assert [(p.x, p.y) for p in deplacements[0].lieux] == [(-1, -23)]
    assert all(e.lieux for e in deplacements)
    assert f.positions[0].zone == "Astrub" and f.pnj_depart == "Recrue Mercenaire"


def test_etape_a_apporter_et_fabrication_ont_leurs_quantites():
    f = fiche_reelle("a-la-recherche-des-instants-perdus")
    a_apporter = next(e for e in f.etapes if e.titre == "À apporter")
    assert [(x_.nom, x_.quantite) for x_ in a_apporter.lignes][0] == ("Pomme", 1)
    c = fiche_reelle("a-la-croisee-des-mondes")
    fabrication = next(e for e in c.etapes if e.titre == "Fabrication")
    assert (fabrication.lignes[0].nom, fabrication.lignes[0].quantite) == ("Pandaclier", 1)
    assert ("Bois de Bambou", 20) in [(x_.nom, x_.quantite) for x_ in fabrication.lignes]


def test_toute_fiche_duffus_a_un_depart_ou_un_pnj():
    guide = {(e.get("url") or "").rsplit("/", 1)[-1] for e in ASPI.quetes.values() if e.get("own_page")}
    sans = [slug for slug in ASPI.pages if slug in guide and not fiche_reelle(slug).pnj_depart]
    assert len(sans) <= 5, sans


def test_la_fiche_se_range_et_se_relit_en_json():
    from epreuve.db.depot import ContenuFiche, contenu_fiche_json
    f = fiche_reelle("balade-en-foret")
    brut = json.loads(json.dumps(contenu_fiche_json(f)))
    assert ContenuFiche.model_validate(brut) == f
    ancien = {k_: v for k_, v in brut.items() if k_ != "pnj_depart"}
    ancien["etapes"] = [{"ordre": 1, "titre": "Vieux", "texte_html": "<p>x</p>", "objectifs": ["a"]}]
    assert ContenuFiche.model_validate(ancien).etapes[0].lignes == ()  # une fiche écrite avant F4 reste lisible


def test_dofusdb_memes_champs_et_vides_quand_absents():
    q = {"id": 1, "nom": "Q", "prerequis": [], "objets": [], "depart": [{"mapId": 5, "npcId": 7}],
         "etapes": [{"id": 1, "nom": "E", "description": "", "recompenses": [], "objectifs": [
             {"genre": "QuestObjectiveFightMonsterData", "texte": "Vaincre x4 {monster,2}", "parametres": [2, 4, 0],
              "position": [3, 4]},
             {"genre": "QuestObjectiveBringItemToNpcData", "texte": "Ramener à {npc,7} : x50 {item,9}",
              "parametres": [7, 9, 50], "position": None},
             {"genre": "QuestObjectiveFreeFormData", "texte": "Prendre", "parametres": [1, 0, 0],
              "position": None}]}]}
    noms = {"npcs": {7: "Mériana"}, "monsters": {2: "Milimulou"}, "items": {9: "Kama"}}
    f = construire_fiche(q, noms, {5: None}, lambda i: None)  # carte de départ sans coordonnées
    assert not any(p.libelle.startswith("Départ") for p in f.positions) and f.pnj_depart == "Mériana"
    lg = f.etapes[0].lignes
    assert (lg[0].genre, lg[0].nom, lg[0].quantite, lg[0].x, lg[0].y) == ("monstre", "Milimulou", 4, 3, 4)
    assert (lg[1].genre, lg[1].nom, lg[1].quantite, lg[1].x) == ("objet", "Kama", 50, None)
    assert (lg[2].genre, lg[2].nom, lg[2].quantite) == ("texte", None, None)


@pytest.mark.parametrize("etage", [0, 1])
def test_etages_duffus_depart_pour_chaque_quete(etage):
    cfg = k.lire_config_etages()
    quetes = k.construire(etage, ASPI, cfg, k.lire_dofus_retenus(), forcer=True).quetes
    manque = [q.nom for q in quetes if q.fiche and not (q.fiche.pnj_depart and q.fiche.positions)]
    assert len(manque) <= 2, manque


def test_infos_rapides_comme_duffus():
    f = fiche_reelle("a-la-croisee-des-mondes")
    assert f.infos_rapides == ["Combats solo ×2", "Combat tactique ×1"]
    h = fiche_reelle("a-la-recherche-de-dan-lavy")
    assert h.infos_rapides[0] == "Combat en groupe ×1" and h.infos_rapides[1].startswith("Donjon : Hypogée")
