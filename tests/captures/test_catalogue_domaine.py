"""Module E1 : construction du catalogue (sans réseau) et calculs purs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from epreuve.captures import domaine as d
from epreuve.captures.catalogue import (
    Archimonstre,
    AvisRecherche,
    Zone,
    construire,
    derniere_aspiration,
    id_monstre_archi,
    lire_dossier,
    nettoyer_resume,
    normaliser,
    zones_de,
)

RACINE = Path(__file__).resolve().parents[2] / "donnees" / "duffus"


def _brut() -> dict:
    return {
        "archimonstres": [
            {"id": 1, "nom": "Blorie l'Assourdissante", "etape": "25", "zone": "Lac de Cania · Mine",
             "image": "/images/archis/2404_Blorie.png"},
            {"id": 2, "nom": "Sans Image", "etape": "20", "zone": "", "image": None},
        ],
        "monstres_e1": [
            {"id": 2404, "name": "Blorie l'Assourdissante", "race": 78, "gfxid": 162, "n0": 52, "n1": 60},
            {"id": 10, "name": "Bouftou Royal", "race": 900, "gfxid": 5, "n0": 150},  # expédition : écarté
            {"id": 11, "name": "Bouftou Royal", "race": 901, "gfxid": 6, "n0": 12, "n1": 20},
        ],
        "monster_races": [{"id": 900, "name": "Expédition royale"}, {"id": 901, "name": "Bouftous"}],
        "boss_ocre": [{"id": 7, "nom": "Bouftou Royal", "etape": 17}],
        "wanted2": [{"id": 3, "slug": "fou", "nom": "Fou", "lvl": "Niv. > 9", "zone": "Astrub", "milice": "Astrub",
                     "recompense": "120", "recompense_type": "aliton", "chasse": "123", "dofus_monster_id": "463",
                     "resume_html": '<b>Invisible</b><img src="http://x/y.png"><script>alert(1)</script>'
                                    '<a href="https://duffus.fr">lien</a>'}],
        "monstres_avis": [{"id": 463, "name": "Fou", "gfxid": 206, "grades_json": [
            {"level": 20, "lifePoints": 670, "actionPoints": 6, "movementPoints": 8, "reductionAir": 10}]}],
        "subareas": [
            {"id": 1, "name": "Lac de Cania", "areaid": 5, "monstres": []},
            {"id": 2, "name": "Mine", "areaid": 6, "monstres": []},
            {"id": 3, "name": "Mine", "areaid": 7, "monstres": [2404]},
        ],
        "areas": [{"id": 5, "name": "Plaines de Cania"}, {"id": 6, "name": "Amakna"}, {"id": 7, "name": "Bonta"}],
    }


def test_construire_suit_les_regles_de_duffus():
    c = construire(_brut())
    a = c.archis[0]
    assert (a.monstre_id, a.gfx_id, a.niveau_min, a.niveau_max, a.niveaux) == (2404, 162, 52, 60, "Niv. 52 à 60")
    # « Mine » existe dans deux aires : on garde celle dont la sous-zone contient le monstre.
    assert a.zones == (Zone("Lac de Cania", "Plaines de Cania"), Zone("Mine", "Bonta"))
    assert a.icone == "https://api.dofusdb.fr/img/monsters/162.png"
    assert c.boss[0].monstre_id == 11 and c.boss[0].niveau == 12  # l'expédition est écartée
    w = c.avis[0]
    assert (w.niveau, w.recompense, w.recompense_type, w.chasse, w.grades[0].pv) == (20, 120, "aliton", True, 670)
    assert w.resume_html == "<b>Invisible</b>lien"
    assert any("Sans Image" in x for x in c.alertes)


def test_petits_outils():
    assert id_monstre_archi("/images/archis/2404_Blorie.png") == 2404 and id_monstre_archi("x.png") is None
    assert zones_de(" A · B ·") == ["A", "B"] and normaliser(" Écureuil ") == "ecureuil"
    assert "<img" not in nettoyer_resume('<div><img src="a"></div>texte')


def test_aspiration_livree_complete():
    dossier = derniere_aspiration(RACINE)
    assert dossier is not None
    c = construire(lire_dossier(dossier))
    assert (len(c.archis), len(c.boss), len(c.avis)) == (286, 51, 82)
    assert c.alertes == ()
    assert all(a.niveau_max and a.gfx_id and a.zones for a in c.archis)


def _archi(i, nom, etape, zones, niv):
    return Archimonstre(i, nom, etape, tuple(Zone(z, a) for z, a in zones), None, None, niv, niv)


ARCHIS = [_archi(1, "Bwork", 20, [("Mine", "Amakna")], 40), _archi(2, "Écureuil", 21, [("Lac", "Cania")], 120),
          _archi(3, "Arak", 20, [("Mine", "Amakna"), ("Lac", "Cania")], 195)]


def test_filtres_tris_et_groupes():
    nombres = {1: 2, 3: 1}
    assert [a.id for a in d.filtrer(ARCHIS, nombres, recherche="ecur")] == [2]
    assert [a.id for a in d.filtrer(ARCHIS, nombres, recherche="lac")] == [2, 3]
    assert [a.id for a in d.filtrer(ARCHIS, nombres, etat="captures")] == [1, 3]
    assert [a.id for a in d.filtrer(ARCHIS, nombres, etat="manquants")] == [2]
    assert [a.id for a in d.filtrer(ARCHIS, nombres, minimum=2)] == [1]
    assert [a.id for a in d.trier(ARCHIS, "alpha")] == [3, 1, 2]
    etapes = d.par_etape(ARCHIS, nombres, 2)
    assert [(g.titre, g.faits, g.total) for g in etapes] == [("Étape 20", 1, 2), ("Étape 21", 0, 1)]
    aires = d.par_zone(ARCHIS, nombres, 1)
    assert [(g.titre, g.faits, g.total) for g in aires] == [("Amakna", 2, 2), ("Cania", 1, 2)]
    assert aires[0].complet and aires[0].sous[0].titre == "Mine"
    p = d.progression(ARCHIS, nombres, 2)
    assert (p.faits, p.total, p.pct, p.cran) == (1, 3, 33, 35)


def test_pierres_a_prevoir():
    p = d.pierres_a_prevoir(ARCHIS, {1: 1}, 2)
    assert {x.cle: (x.a_prevoir, x.total) for x in p.pierres} == {
        "petite": (1, 2), "moyenne": (0, 0), "grande": (2, 2), "enorme": (0, 0)}
    assert p.hors_bornes == 1 and p.a_prevoir == 3
    assert d.borne_personnages("12") == 8 and d.borne_personnages("x") == 1 and d.borne_personnages(0) == 1


def _avis(i, nom, niveau, milice, recompense, type_="aviton"):
    return AvisRecherche(i, f"s{i}", nom, None, niveau, None, milice, recompense, type_, False, None, None, "", ())


def test_avis_filtres_et_recompenses():
    avis = [_avis(1, "Fou", 20, "Astrub", 120), _avis(2, "Grand", 150, "Bonta/Brak", 300, "aliton"),
            _avis(3, "Été", 5, "Astrub", None)]
    assert [a.id for a in d.filtrer_avis(avis, set())] == [3, 1, 2]
    assert [a.id for a in d.filtrer_avis(avis, set(), emeraude=True)] == [3, 1]
    assert [a.id for a in d.filtrer_avis(avis, {1}, etat="captures")] == [1]
    assert [a.id for a in d.filtrer_avis(avis, {1}, milice="Astrub", etat="manquants")] == [3]
    assert [a.id for a in d.filtrer_avis(avis, set(), recherche="ete")] == [3]
    assert d.milices(avis) == ["Astrub", "Bonta/Brak"]
    assert d.recompenses_disponibles(avis, {1}) == {"aviton": 0, "aliton": 300}


def test_qui_a_ecarte_les_exclus():
    g = [SimpleNamespace(id=1, pseudo="Zed", classe=None, statut="actif"),
         SimpleNamespace(id=2, pseudo="Ana", classe="Iop", statut="pause"),
         SimpleNamespace(id=3, pseudo="Fourbe", classe=None, statut="exclu")]
    ont, pas = d.qui_a(g, {1: 3, 3: 1})
    assert [(p.pseudo, p.nombre) for p in ont] == [("Zed", 3)] and [p.pseudo for p in pas] == ["Ana"]
