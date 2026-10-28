"""Calculateur d'arme, chiffré à la main d'après le code de Duffus (`Ge`, `Qe`)."""

import pytest

from epreuve.builder.arme import Arme, arrondi, calculer_arme, jet
from epreuve.builder.catalogue import catalogue_par_defaut

TOTAUX = {"Force": 100, "Intelligence": 50, "Puissance": 20, "Dommages": 2, "Do Feu": 3, "Do Critique": 4,
          "% Critique": 10, "% Do Armes": 10, "% Do Mélée": 5}


def test_arrondi_comme_math_round():
    assert (arrondi(2.5), arrondi(-2.5), arrondi(2.49), arrondi(-0.5)) == (3, -2, 2, 0)


def test_marteau_du_bouftou():
    """Feu 4 à 8 : (1,7 × 4 + 5) × 1,1 × 1,05 = 13,6 → 14 ; (1,7 × 8 + 5) … = 21,5 → 21.
    Terre 4 à 8 : (2,2 × 4 + 2) … = 12,5 → 12 ; (2,2 × 8 + 2) … = 22,6 → 23.
    Critique (+5 aux jets, + 4 Do Critique) : feu 28 à 36, terre 30 à 40."""
    arme = catalogue_par_defaut().objet(2416).arme
    assert (arme.pa, arme.cc, arme.bonus_cc, arme.lancers) == (4, 30, 5, 1)
    r = calculer_arme(arme, TOTAUX)
    assert [(x["libelle"], x["normal"], x["critique"]) for x in r["lignes"]] == [
        ("dommages Feu", (14, 21), (28, 36)), ("dommages Terre", (12, 23), (30, 40))]
    assert (r["degats"], r["degats_critique"], r["taux_critique"]) == ((26, 44), (58, 76), 40)
    assert (r["par_coup"], r["par_tour"], r["par_pa"]) == (48, 48, 12.0)  # 0,6 × 35 + 0,4 × 67 = 47,8
    distance = calculer_arme(arme, TOTAUX, mode="distance")
    assert distance["lignes"][0]["normal"] == (13, 20)  # sans les 5 % de mêlée


def test_buff_de_puissance_et_caracteristiques_negatives():
    arme = Arme(4, 1, 1, 0, 0, 2, ((97, 10, 0),))
    r = calculer_arme(arme, {"Force": -50, "Puissance": -10}, buff="base")
    assert r["lignes"][0]["normal"] == (39, 39)  # Puissance -10 + 300 = 290, Force ramenée à 0 : × 3,9
    assert r["lignes"][0]["critique"] is None and r["taux_critique"] == 0
    assert (r["par_coup"], r["par_tour"]) == (39, 78)


def test_soins_vol_et_meilleur_element():
    soin = jet((108, 10, 20), {"Intelligence": 50, "Soins": 5}, bonus_soin=300)
    assert soin == (50, 95)  # 4,5 × 10 + 5 ; 4,5 × 20 + 5
    assert jet((2822, 10, 0), {"Force": 10, "Chance": 90, "Do Eau": 7}) == (26, 26)  # Chance : 1,9 × 10 + 7
    arme = Arme(3, 1, 1, 20, 2, 1, ((95, 10, 20), (108, 5, 0)))
    r = calculer_arme(arme, {"Force": 100})
    assert r["vol"] == (10, 20) and r["soins"] == (5, 5) and r["soins_critique"] == (7, 7)
    assert r["degats"] == (20, 40) and r["degats_critique"] == (24, 44)


@pytest.mark.parametrize("effet", [(100, 0, 0), (108, 0, 0)])
def test_ligne_vide(effet):
    assert jet(effet, {}) is None
