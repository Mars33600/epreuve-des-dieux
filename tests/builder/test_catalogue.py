"""Catalogue du builder : chargement des données aspirées, recherche par emplacement comme la fenêtre de Duffus."""

import json

import pytest

from epreuve.builder.aspirer import reduire_objet, reduire_panoplie
from epreuve.builder.catalogue import Catalogue, catalogue_par_defaut, normaliser
from epreuve.builder.effets import EFFET_CARAC, ORDRE_CARACS, valeur_effet


@pytest.mark.parametrize(("de", "a", "attendu"), [
    (16, 20, 20), (20, 0, 20), (0, 5, 5), (0, 0, 0), (-20, 0, -20), (-20, -10, -10), (0, -5, -5), (-5, 10, 10),
    (-10, 5, -10),
])  # fmt: skip
def test_valeur_effet_comme_duffus(de, a, attendu):
    assert valeur_effet(de, a) == attendu


def test_table_des_effets():
    assert set(EFFET_CARAC.values()) == set(ORDRE_CARACS)
    assert EFFET_CARAC[157] == "Force" and EFFET_CARAC[246] == "Re Eau" and EFFET_CARAC[2990] == "Invocations"


def test_normaliser():
    assert normaliser("  Cœur d'Égée ") == "coeur d'egee"


def test_reduire_objet_et_panoplie():
    o = reduire_objet({"id": 7, "name": "Choipo", "level": 30, "typeid": 16, "iconid": 1, "itemsetid": -1,
                       "criterions": "", "simpleeffects_json": [
                           {"effectId": 157, "from": -20, "to": 0}, {"effectId": 983, "from": 0, "to": 0}]})
    assert o == {"id": 7, "nom": "Choipo", "niveau": 30, "type": 16, "icone": 1, "panoplie": None,
                 "conditions": None, "effets": [[157, -20, 0]]}
    p = reduire_panoplie({"id": 1, "name": "P", "items_json": "[1, 2]",
                          "simple_effectsbycount_json": json.dumps({"2": [{"effectId": 118, "from": 5, "to": 0}],
                                                                    "1": []})})
    assert p == {"id": 1, "nom": "P", "objets": [1, 2], "bonus": {"1": [], "2": [[118, 5, 0]]}}


def test_donnees_aspirees_chargees():
    cat = catalogue_par_defaut()
    assert len(cat.objets) > 3000 and len(cat.panoplies) > 400
    coiffe = cat.objet(2411)
    assert coiffe.nom == "Coiffe du Bouftou" and coiffe.panoplie == 1
    assert coiffe.caracs() == {"Force": 20, "Intelligence": 20}


def test_recherche_par_emplacement():
    cat = catalogue_par_defaut()
    total, page = cat.rechercher("coiffe", texte="bouftou", niveau_max=50)
    assert total >= 1 and all(o.type == 16 and o.niveau <= 50 for o in page)
    assert [o.id for o in page][:1] == [2411] or 2411 in [o.id for o in page]
    total_anneaux, anneaux = cat.rechercher("anneau1", niveau_min=190, niveau_max=200, limite=500)
    assert total_anneaux == len(anneaux) and all(o.type == 9 and 190 <= o.niveau <= 200 for o in anneaux)
    niveaux = [(o.niveau, o.id) for o in anneaux]
    assert niveaux == sorted(niveaux, reverse=True)  # niveau puis id décroissants


def test_recherche_par_caracteristique_et_type():
    cat = catalogue_par_defaut()
    _, page = cat.rechercher("arme", caracs=["PA", "Force"], limite=1000)
    assert page and all(o.caracs().get("PA", 0) > 0 and o.caracs().get("Force", 0) > 0 for o in page)
    _, marteaux = cat.rechercher("arme", types=[7], limite=1000)
    assert marteaux and {o.type for o in marteaux} == {7}
    _, rien = cat.rechercher("coiffe", types=[7])  # un type hors de la famille de l'emplacement
    assert rien == []


def test_recherche_dofus_trophees_apres_dofus():
    cat = catalogue_par_defaut()
    _, page = cat.rechercher("dofus3", limite=5000)
    rangs = [{23: 0, 151: 1, 217: 2}[o.type] for o in page]
    assert rangs == sorted(rangs)


def test_exclus_et_texte_court():
    cat = Catalogue.depuis_json(
        [{"id": 6894, "nom": "Exclu", "niveau": 1, "type": 16, "effets": []},
         {"id": 1, "nom": "Abc", "niveau": 1, "type": 16, "effets": []}], [])
    assert [o.id for o in cat.rechercher("coiffe")[1]] == [1]
    assert cat.rechercher("coiffe", texte="z")[0] == 1  # moins de 2 caractères : pas de filtre
    assert cat.rechercher("coiffe", texte="zz")[0] == 0
