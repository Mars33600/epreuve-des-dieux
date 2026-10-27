"""mode_effectif() et voit_site_complet() : la bascule du teaser vers le site complet."""

import itertools
from datetime import UTC, datetime, timedelta, timezone

import pytest

from epreuve.domaine.mode_site import (
    CHEMINS_TOUJOURS_PERMIS,
    PREFIXES_TOUJOURS_PERMIS,
    mode_effectif,
    voit_site_complet,
)

PARIS_HIVER = timezone(timedelta(hours=1))
OUVERTURE = datetime(2026, 11, 13, 17, 0, tzinfo=PARIS_HIVER)
SECONDE = timedelta(seconds=1)


@pytest.mark.parametrize(("maintenant", "attendu"), [
    (OUVERTURE - SECONDE, "teaser"),
    (OUVERTURE, "ouvert"),  # à l'instant exact, les portes sont ouvertes
    (OUVERTURE + SECONDE, "ouvert"),
])
def test_auto_autour_de_l_ouverture(maintenant, attendu):
    assert mode_effectif("auto", OUVERTURE, maintenant) == attendu


def test_auto_compare_des_instants_pas_des_heures_murales():
    # 16:00:00 UTC = 17:00 à Paris : c'est l'ouverture, même écrite dans un autre fuseau.
    assert mode_effectif("auto", OUVERTURE, datetime(2026, 11, 13, 15, 59, 59, tzinfo=UTC)) == "teaser"
    assert mode_effectif("auto", OUVERTURE, datetime(2026, 11, 13, 16, 0, tzinfo=UTC)) == "ouvert"


@pytest.mark.parametrize("maintenant", [OUVERTURE - timedelta(days=20), OUVERTURE, OUVERTURE + timedelta(days=60)])
def test_teaser_et_ouvert_forces(maintenant):
    assert mode_effectif("teaser", OUVERTURE, maintenant) == "teaser"  # même après la date
    assert mode_effectif("ouvert", OUVERTURE, maintenant) == "ouvert"  # même avant la date


@pytest.mark.parametrize("reglage", ["auto", "teaser", "ouvert"])
def test_dates_sans_fuseau_refusees(reglage):
    naive = datetime(2026, 11, 13, 17, 0)
    with pytest.raises(ValueError, match="ouvert_le"):
        mode_effectif(reglage, naive, OUVERTURE)
    with pytest.raises(ValueError, match="maintenant"):
        mode_effectif(reglage, OUVERTURE, naive)


@pytest.mark.parametrize(("mode", "est_admin", "est_testeur"),
                         list(itertools.product(["teaser", "ouvert"], [False, True], [False, True])))
def test_voit_site_complet_les_8_combinaisons(mode, est_admin, est_testeur):
    attendu = mode == "ouvert" or est_admin or est_testeur
    assert voit_site_complet(mode, est_admin, est_testeur) is attendu
    # Le seul cas fermé : un visiteur ordinaire pendant le teaser.
    assert attendu is not (mode == "teaser" and not est_admin and not est_testeur)


def test_chemins_permis_du_lot_a():
    assert CHEMINS_TOUJOURS_PERMIS == {"/", "/sante"}
    assert PREFIXES_TOUJOURS_PERMIS == ("/static/",)
