"""peut_ouvrir() et bilan_etage() (SPEC §5.2, §5.5, critère 27)."""

from datetime import timedelta

import pytest

from epreuve.domaine.bareme import EtatJauge
from epreuve.domaine.ouverture import bilan_etage, peut_ouvrir
from tests.fabrique import PENDANT, PLANCHER, etage

EN_COURS = etage(1, 0, "ouvert")
PROCHAIN = etage(2, 1, "scelle")
PTS = {"donjons": 8, "full_succes": 4, "principales": 6, "secondaires": 6}


def jauge(score=24, palier=24, actifs=12):
    return EtatJauge(score, palier, False, actifs, 0, 4, PTS)


def test_ok_exactement_a_la_date_plancher():
    d = peut_ouvrir(jauge(), EN_COURS, PROCHAIN, PLANCHER)
    assert d.ok and d.raisons == ()


def test_avant_la_date_plancher():
    d = peut_ouvrir(jauge(), EN_COURS, PROCHAIN, PLANCHER - timedelta(seconds=1))
    assert not d.ok and d.raisons == ("pas avant le vendredi 13 novembre à 17 h",)


def test_sans_date_plancher():
    assert peut_ouvrir(jauge(), etage(1, 0, date_plancher_suivant=None), PROCHAIN, PENDANT).ok


@pytest.mark.parametrize(("j", "en_cours", "prochain", "raison"), [
    (jauge(), EN_COURS, None, "aucun étage préparé"),
    (jauge(), EN_COURS, etage(2, 1, "ouvert"), "aucun étage préparé"),
    (jauge(score=21), EN_COURS, PROCHAIN, "jauge : il manque 3 points"),
    (jauge(score=23), EN_COURS, PROCHAIN, "jauge : il manque 1 point"),
    (jauge(0, 0, 0), EN_COURS, PROCHAIN, "aucun grimpeur actif"),
    (jauge(0, 0, 5), EN_COURS, PROCHAIN, "jauge : palier nul (étage sans catégorie), régler un palier manuel"),
    (jauge(), etage(1, 0, "termine"), PROCHAIN, "l'étage en cours n'est pas ouvert"),
])
def test_chaque_raison_de_refus(j, en_cours, prochain, raison):
    d = peut_ouvrir(j, en_cours, prochain, PLANCHER)
    assert not d.ok and d.raisons == (raison,)


def test_plusieurs_raisons_a_la_fois():
    d = peut_ouvrir(jauge(score=0), EN_COURS, None, PENDANT)
    assert len(d.raisons) == 3


def test_bilan_etage():
    b = bilan_etage(jauge(score=26), PENDANT, False, None)
    assert (b.fige_le, b.actifs, b.palier, b.score, b.force, b.motif) == (PENDANT, 12, 24, 26, False, None)
    assert b.points_par_categorie == PTS and b.points_par_categorie is not PTS
    assert bilan_etage(jauge(), PENDANT, True, " Shadoaze l'a demandé ").motif == "Shadoaze l'a demandé"


@pytest.mark.parametrize("motif", [None, "", "   "])
def test_bilan_force_sans_motif_refuse(motif):
    with pytest.raises(ValueError, match="motif"):
        bilan_etage(jauge(), PENDANT, True, motif)
