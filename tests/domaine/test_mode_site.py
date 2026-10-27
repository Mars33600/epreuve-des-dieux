"""mode_effectif() et voit_site_complet() : la bascule du teaser vers le site complet."""

import itertools
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

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


@pytest.mark.parametrize(("mode", "est_admin"), list(itertools.product(["teaser", "ouvert"], [False, True])))
def test_voit_site_complet_les_4_combinaisons(mode, est_admin):
    # Plus de testeur au lot B : aucun joueur avant l'ouverture, seuls les admins voient le site.
    assert voit_site_complet(mode, est_admin) is (mode == "ouvert" or est_admin)


def test_chemins_permis_du_lot_b():
    assert CHEMINS_TOUJOURS_PERMIS == {"/", "/sante", "/connexion", "/auth/discord/retour", "/deconnexion"}
    assert "/inscription" not in CHEMINS_TOUJOURS_PERMIS
    assert PREFIXES_TOUJOURS_PERMIS == ("/static/",)


# --- Cas adverses ---------------------------------------------------------------------------------------


class FuseauSansDecalage(tzinfo):
    """Un tzinfo présent mais qui ne connaît pas son décalage : la date reste « naïve » pour Python."""

    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


@pytest.mark.parametrize("reglage", ["auto", "teaser", "ouvert"])
def test_fuseau_sans_decalage_refuse(reglage):
    bancale = datetime(2026, 11, 13, 17, 0, tzinfo=FuseauSansDecalage())
    with pytest.raises(ValueError, match="ouvert_le"):
        mode_effectif(reglage, bancale, OUVERTURE)
    with pytest.raises(ValueError, match="maintenant"):
        mode_effectif(reglage, OUVERTURE, bancale)


def test_ouverture_ecrite_avec_le_fuseau_nomme_de_paris():
    # Avec ZoneInfo, le 13/11 tombe en heure d'hiver : 17:00 à Paris = 16:00 UTC, pas 15:00.
    ouverture = datetime(2026, 11, 13, 17, 0, tzinfo=ZoneInfo("Europe/Paris"))
    assert ouverture == OUVERTURE
    assert mode_effectif("auto", ouverture, datetime(2026, 11, 13, 15, 59, 59, 999999, tzinfo=UTC)) == "teaser"
    assert mode_effectif("auto", ouverture, datetime(2026, 11, 13, 16, 0, tzinfo=UTC)) == "ouvert"


@pytest.mark.parametrize("decalage_h", [-12, -5, 0, 5.5, 14])
def test_meme_instant_quel_que_soit_le_fuseau_de_l_horloge(decalage_h):
    fuseau = timezone(timedelta(hours=decalage_h))
    assert mode_effectif("auto", OUVERTURE, (OUVERTURE - SECONDE).astimezone(fuseau)) == "teaser"
    assert mode_effectif("auto", OUVERTURE, OUVERTURE.astimezone(fuseau)) == "ouvert"

