"""peut_ouvrir(), ouvrir_automatiquement(), le délai de grâce et bilan_etage() (SPEC §5.2, §5.5, critère 27)."""

from datetime import timedelta

import pytest

from epreuve.domaine.bareme import EtatJauge
from epreuve.domaine.modeles import Regles
from epreuve.domaine.ouverture import (
    ACTEUR_SYSTEME,
    bilan_etage,
    ouvrir_automatiquement,
    peut_ouvrir,
    pleine_depuis,
    reste_avant_ouverture,
)
from tests.fabrique import PENDANT, PLANCHER, etage

EN_COURS = etage(1, 0, "ouvert")
PROCHAIN = etage(2, 1, "scelle")
MINUTE = timedelta(seconds=60)
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


@pytest.mark.parametrize(("regles", "mode", "j", "maintenant", "attendu"), [
    (Regles(), "ouvert", jauge(), PLANCHER, True),
    (Regles(ouverture_automatique=False), "ouvert", jauge(), PLANCHER, False),  # réglage coupé : admin seul
    (Regles(), "teaser", jauge(), PLANCHER, False),  # pendant le teaser, rien ne bouge
    (Regles(), "ouvert", jauge(score=23), PLANCHER, False),  # jauge pas pleine
    (Regles(), "ouvert", jauge(), PLANCHER - timedelta(seconds=1), False),  # date plancher pas passée
])
def test_ouverture_automatique(regles, mode, j, maintenant, attendu):
    # La jauge est pleine depuis bien plus que le délai de grâce : seules les autres conditions décident.
    depuis = PLANCHER - timedelta(days=1)
    assert ouvrir_automatiquement(j, EN_COURS, PROCHAIN, maintenant, regles, mode, pleine_depuis=depuis) is attendu


def test_ouverture_automatique_sans_etage_scelle():
    d = PLANCHER - MINUTE
    assert not ouvrir_automatiquement(jauge(), EN_COURS, None, PLANCHER, Regles(), "ouvert", pleine_depuis=d)
    assert ouvrir_automatiquement(jauge(), EN_COURS, PROCHAIN, PLANCHER, Regles(), "teaser", pendant_teaser=True,
                                  pleine_depuis=d)
    assert not ouvrir_automatiquement(jauge(), EN_COURS, PROCHAIN, PLANCHER, Regles(), "teaser", pleine_depuis=d)
    assert not ouvrir_automatiquement(jauge(), EN_COURS, etage(2, 1, "ouvert"), PLANCHER, Regles(), "ouvert",
                                      pleine_depuis=d)


# ---------------------------------------------------------------- le délai de grâce (une coche par erreur)


def test_pleine_depuis_note_garde_et_efface():
    assert pleine_depuis(jauge(), None, PLANCHER) == PLANCHER  # elle vient de se remplir
    assert pleine_depuis(jauge(), PENDANT, PLANCHER) == PENDANT  # toujours pleine : l'instant d'origine reste
    assert pleine_depuis(jauge(score=23), PENDANT, PLANCHER) is None  # décochée : le compte repart de zéro
    assert pleine_depuis(jauge(0, 0, 0), None, PLANCHER) is None


def test_reste_avant_ouverture():
    assert reste_avant_ouverture(None, PLANCHER, Regles()) is None
    assert reste_avant_ouverture(PLANCHER, PLANCHER, Regles()) == 60
    assert reste_avant_ouverture(PLANCHER - timedelta(seconds=45), PLANCHER, Regles()) == 15
    assert reste_avant_ouverture(PLANCHER - MINUTE, PLANCHER, Regles()) is None  # écoulé pile à la minute
    assert reste_avant_ouverture(PLANCHER, PLANCHER, Regles(delai_grace_secondes=0)) is None


@pytest.mark.parametrize(("depuis", "attendu"), [
    (None, False),  # jauge pas pleine au dernier regard
    (PLANCHER, False),  # pleine à l'instant : pas d'ouverture immédiate
    (PLANCHER - timedelta(seconds=59), False),  # une seconde trop tôt
    (PLANCHER - MINUTE, True),  # pleine depuis une minute d'affilée
])
def test_ouverture_automatique_attend_le_delai_de_grace(depuis, attendu):
    assert ouvrir_automatiquement(jauge(), EN_COURS, PROCHAIN, PLANCHER, Regles(), "ouvert",
                                  pleine_depuis=depuis) is attendu


def test_delai_nul_ouvre_des_la_coche():
    regles = Regles(delai_grace_secondes=0)
    assert ouvrir_automatiquement(jauge(), EN_COURS, PROCHAIN, PLANCHER, regles, "ouvert", pleine_depuis=PLANCHER)
    assert not ouvrir_automatiquement(jauge(), EN_COURS, PROCHAIN, PLANCHER, regles, "ouvert", pleine_depuis=None)


def test_acteur_systeme_est_vide():
    # NULL au journal : jamais un identifiant Discord inventé qui pourrait être celui de quelqu'un.
    assert ACTEUR_SYSTEME is None
