"""controler_validation() et validation_compte()."""

from dataclasses import replace
from datetime import timedelta

import pytest

from epreuve.domaine.controles import (
    MOTIF_AVANT_OUVERTURE,
    MOTIF_DEJA_VALIDE,
    MOTIF_ETAGE_FERME,
    MOTIF_EXCLU,
    MOTIF_HORS_ETAGE,
    MOTIF_NIVEAU_MANQUANT,
    MOTIF_NON_INSCRIT,
    MOTIF_PAUSE,
    controler_validation,
    validation_compte,
)
from epreuve.domaine.modeles import Contenu
from tests.fabrique import CONTENUS, ETAGE0, OUVERTURE, PENDANT, grimpeur, validation

KARDORIM, QUETES = CONTENUS[0], CONTENUS[5]


def controle(niveau=20, statut="actif", deja=False, quand=PENDANT, contenu=KARDORIM, etage=ETAGE0):
    return controler_validation(grimpeur(1, statut=statut), contenu, niveau, quand, etage, deja)


@pytest.mark.parametrize("niveau", [1, 15, 19, 20])
def test_niveaux_acceptes_sans_avertissement(niveau):
    c = controle(niveau)
    assert c.ok and c.bloquants == () and c.avertissements == ()


@pytest.mark.parametrize("niveau", [21, 22, 200])
def test_depassement_de_cap_est_un_avertissement(niveau):
    c = controle(niveau)
    assert c.ok and c.bloquants == ()
    assert c.avertissements == (f"niveau {niveau} au-dessus du cap 20",)


@pytest.mark.parametrize("niveau", [0, 201, -5])
def test_niveau_impossible_bloquant(niveau):
    c = controle(niveau)
    assert not c.ok and c.bloquants == (f"niveau {niveau} impossible (entre 1 et 200)",)


def test_niveau_manquant_sur_un_succes_bloquant():
    assert controle(None).bloquants == (MOTIF_NIVEAU_MANQUANT,)


def test_declaration_sans_niveau_sur_un_lot_de_quetes():
    c = controle(None, contenu=QUETES)
    assert c.ok and c.avertissements == ()
    assert controle(None, contenu=Contenu(7, 1, "quete", "Cryptologie", "Cryptologie")).ok


def test_pause_et_exclu_bloquants():
    assert controle(statut="pause").bloquants == (MOTIF_PAUSE,)
    assert controle(statut="exclu").bloquants == (MOTIF_EXCLU,)


def test_doublon_bloquant():
    assert controle(deja=True).bloquants == (MOTIF_DEJA_VALIDE,)


def test_avant_ouverture_bloquant():
    assert controle(quand=OUVERTURE - timedelta(seconds=1)).bloquants == (MOTIF_AVANT_OUVERTURE,)
    assert controle(quand=OUVERTURE).ok  # à l'instant de l'ouverture : accepté
    assert MOTIF_AVANT_OUVERTURE in controle(etage=replace(ETAGE0, ouvert_le=None)).bloquants


def test_etage_pas_ouvert_et_contenu_hors_etage():
    assert controle(etage=replace(ETAGE0, statut="scelle")).bloquants == (MOTIF_ETAGE_FERME,)
    assert controle(contenu=Contenu(99, 2, "succes", "Autre", "Autre")).bloquants == (MOTIF_HORS_ETAGE,)


def test_plusieurs_motifs_a_la_fois():
    c = controle(22, statut="pause", deja=True, quand=OUVERTURE - timedelta(days=1))
    assert not c.ok
    assert c.bloquants == (MOTIF_PAUSE, MOTIF_AVANT_OUVERTURE, MOTIF_DEJA_VALIDE)
    assert c.avertissements == ("niveau 22 au-dessus du cap 20",)


def test_motif_non_inscrit_disponible_pour_l_ia():
    assert MOTIF_NON_INSCRIT == "membre non inscrit"


# --- validation_compte -------------------------------------------------------------------------


def test_validation_au_cap_ou_sous_le_cap_compte():
    assert validation_compte(validation(1, 1, niveau=20), ETAGE0)
    assert validation_compte(validation(1, 1, niveau=15), ETAGE0)


@pytest.mark.parametrize("statut", ["refusee", "annulee"])
def test_validation_non_acceptee_ne_compte_pas(statut):
    assert not validation_compte(validation(1, 1, statut=statut), ETAGE0)


def test_au_dessus_du_cap_seulement_si_forcee():
    assert not validation_compte(validation(1, 1, niveau=21), ETAGE0)
    assert validation_compte(validation(1, 1, niveau=21, forcee=True), ETAGE0)


def test_declaration_sans_niveau_compte():
    assert validation_compte(validation(1, 6, niveau=None, source="declaration"), ETAGE0)


def test_avant_ouverture_ou_etage_sans_date_ne_compte_pas():
    assert not validation_compte(validation(1, 1, realisee_le=OUVERTURE - timedelta(minutes=1)), ETAGE0)
    assert not validation_compte(validation(1, 1), replace(ETAGE0, ouvert_le=None))
