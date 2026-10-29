"""Le brouillard : un étage scellé ne sort jamais pour un non-admin (EX-111, critère 8)."""

from hypothesis import given
from hypothesis import strategies as st

from epreuve.domaine.visibilite import (
    etage_cochable,
    etages_visibles,
    peut_modifier_coches,
)
from tests.fabrique import etage

ETAGES = [etage(3, 2, "scelle"), etage(1, 0, "termine"), etage(2, 1, "ouvert"), etage(4, 3, "scelle")]


def test_non_admin_ne_voit_que_ouverts_et_termines_tries():
    assert [e.numero for e in etages_visibles(ETAGES, False)] == [0, 1]


def test_admin_voit_tout_trie():
    assert [e.numero for e in etages_visibles(ETAGES, True)] == [0, 1, 2, 3]


@given(st.lists(st.sampled_from(["scelle", "ouvert", "termine"]), max_size=10))
def test_les_scelles_ne_sortent_jamais(statuts):
    etages = [etage(i, i, s) for i, s in enumerate(statuts)]
    assert all(e.statut != "scelle" for e in etages_visibles(etages, False))


def test_etage_cochable():
    assert etage_cochable(etage(statut="ouvert")) and etage_cochable(etage(statut="termine"))
    assert not etage_cochable(etage(statut="scelle"))


def test_peut_modifier_coches():
    assert peut_modifier_coches(3, False, 3)
    assert not peut_modifier_coches(3, False, 4)
    assert not peut_modifier_coches(None, False, 4)
    assert peut_modifier_coches(None, True, 4)  # admin sans fiche
