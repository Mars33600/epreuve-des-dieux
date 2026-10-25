"""Retardataires : qui entre dans le maximum (SPEC §5.4)."""

from dataclasses import replace
from datetime import timedelta

import pytest

from epreuve.domaine.inclusion import (
    doit_etre_inclus,
    est_compte,
    est_retardataire,
    inclus_des_l_inscription,
    niveau_plancher,
)
from tests.fabrique import ETAGE0, OUVERTURE, grimpeur


def test_inscrit_avant_l_ouverture_compte():
    assert inclus_des_l_inscription(OUVERTURE - timedelta(minutes=1), ETAGE0)
    g = grimpeur(1)
    assert est_compte(g) and not est_retardataire(g)


def test_inscrit_apres_l_ouverture_retardataire():
    assert not inclus_des_l_inscription(OUVERTURE, ETAGE0)
    assert not inclus_des_l_inscription(OUVERTURE + timedelta(days=1), ETAGE0)
    g = grimpeur(1, retard=True)
    assert est_retardataire(g) and not est_compte(g)


def test_sans_etage_ouvert_tout_le_monde_est_compte():
    assert inclus_des_l_inscription(OUVERTURE, None)
    assert inclus_des_l_inscription(OUVERTURE, replace(ETAGE0, ouvert_le=None))


def test_niveau_plancher_le_compte_le_moins_avance():
    groupe = [grimpeur(1, niveau=20), grimpeur(2, niveau=14), grimpeur(3, niveau=None),
              grimpeur(4, niveau=5, retard=True),  # un retardataire ne fixe pas le plancher
              grimpeur(5, niveau=3, statut="pause"), grimpeur(6, niveau=2, statut="exclu")]
    assert niveau_plancher(groupe, ETAGE0) == 14


def test_niveau_plancher_sans_niveau_connu_retombe_sur_le_cap():
    assert niveau_plancher([], ETAGE0) == 20
    assert niveau_plancher([grimpeur(1, niveau=None), grimpeur(2, niveau=5, retard=True)], ETAGE0) == 20


@pytest.mark.parametrize(("niveau", "attendu"), [(14, True), (23, True), (13, False), (None, False)])
def test_doit_etre_inclus_au_niveau_plancher(niveau, attendu):
    assert doit_etre_inclus(grimpeur(1, retard=True, niveau=niveau), 14) is attendu


def test_doit_etre_inclus_faux_si_deja_inclus_ou_en_pause():
    assert not doit_etre_inclus(grimpeur(1, niveau=20), 14)
    pause = grimpeur(1, retard=True, niveau=20, statut="pause")
    assert not doit_etre_inclus(pause, 14)
    assert not est_retardataire(pause) and not est_compte(pause)
