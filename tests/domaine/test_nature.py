"""Principal ou secondaire (SPEC §6.3) : critères DofusDB, fermeture, classement."""

import pytest

from epreuve.domaine.nature import Classement, classer, fermeture, quetes_obligatoires


@pytest.mark.parametrize(("critere", "attendu"), [
    ("Qf=1462&PL>39", {1462}),
    ("(Qf=272|Qf=273|Qf=274)", set()),  # la quête 275 : une seule des trois suffit
    ("(Qf=272|Qf=273|Qf=274)&Qf=10", {10}),
    ("Qf=1&(Qf=2&(Qf=3&PL>10))", {1, 2, 3}),
    ("((Qf=1|Qf=2)&Qf=3)&Qf=4", {3, 4}),
    ("Qf=1|Qf=2", set()),
    ("", set()),
    ("PL>20&Qo=5&Qf=6", {6}),
    ("Qf=7&(Qf=8", {7, 8}),  # parenthèse non fermée : tolérée
])
def test_quetes_obligatoires(critere, attendu):
    assert quetes_obligatoires(critere) == attendu


def test_quetes_obligatoires_none():
    assert quetes_obligatoires(None) == frozenset()  # type: ignore[arg-type]


def test_fermeture_avec_cycle_et_diamant():
    prerequis = {1: [2, 3], 2: [4], 3: [4], 4: [1], 5: [6]}
    assert fermeture([1], prerequis) == {1, 2, 3, 4}
    assert fermeture([], prerequis) == frozenset()
    assert fermeture([9], prerequis) == {9}


def test_classer_priorites():
    guides_duffus = {"Émeraude": {1, 2}, "Argenté": {2, 3}, "Ocre": {7}}
    guides_repli = {"Émeraude": {4}, "Cacao": {5, 6}, "Kaliptus": {8}}
    retenus = {"Émeraude", "Argenté", "Cacao"}
    r = classer(range(1, 10), guides_duffus, guides_repli, retenus, {3: "secondaire", 9: "principale"})
    assert r[1] == Classement("principale", "duffus", ("Émeraude",))
    assert r[2] == Classement("principale", "duffus", ("Argenté", "Émeraude"))  # alphabétique, accents ignorés
    assert r[3] == Classement("secondaire", "admin", ())  # l'admin prime sur Duffus
    assert r[4] == Classement("secondaire", "duffus", ())  # repli ignoré : l'Émeraude a un guide Duffus
    assert r[5] == Classement("principale", "dofusdb", ("Cacao",))
    assert r[7] == Classement("secondaire", "duffus", ())  # Ocre non retenu
    assert r[8] == Classement("secondaire", "duffus", ())  # Kaliptus non retenu
    assert r[9] == Classement("principale", "admin", ())


def test_classer_admin_principale_garde_les_dofus():
    r = classer([1], {"Émeraude": {1}}, {}, {"Émeraude"}, {1: "principale"})
    assert r[1] == Classement("principale", "admin", ("Émeraude",))
