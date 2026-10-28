"""QA, tests adverses du module de règles (src/epreuve/domaine/).

Chaque attendu vient de docs/SPEC.md §5 / §7 / §8 bis et de docs/REPONSES-SHADOAZE.md, pas du code.
Pas de base, pas de réseau.
"""

# ruff: noqa: E402, I001
import pytest

# Ce module importe domaine/inclusion.py, déjà supprimé sur la branche wip (retardataires automatiques
# retirés) : il ne se chargeait plus. Ses idées de tests adverses seront reprises au lot B (docs/LOTS.md, inventaire).
pytest.skip("domaine v3 (inclusion.py supprimé), tests réécrits au lot B", allow_module_level=True)

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from epreuve.domaine.controles import (
    MOTIF_AVANT_OUVERTURE,
    MOTIF_DEJA_VALIDE,
    MOTIF_EXCLU,
    MOTIF_PAUSE,
    controler_validation,
    validation_compte,
)
from epreuve.domaine.inclusion import (
    doit_etre_inclus,
    est_compte,
    est_retardataire,
    inclus_des_l_inscription,
    niveau_plancher,
)
from epreuve.domaine.jauges import calculer_etat_etage, marques_grimpeur, points_grimpeur
from epreuve.domaine.seuil import seuil
from tests.fabrique import CHALLENGES, CONTENUS, ETAGE0, FULL_SUCCES, PALIERS, PENDANT, faits, grimpeur, validation

PARIS = ZoneInfo("Europe/Paris")
RACINE = Path(__file__).resolve().parents[2]


def etat(grimpeurs, validations, maintenant=PENDANT, etage=ETAGE0):
    return calculer_etat_etage(etage, PALIERS, grimpeurs, validations, maintenant)


def pts(g, validations):
    return points_grimpeur(g, PALIERS, validations, ETAGE0)


# --- Grimpeur qui dépasse sa difficulté (§8 bis a) ----------------------------------------------


def test_aventurier_full_succes_et_quetes_rapporte_3_le_maximum_ne_bouge_pas():
    av = grimpeur(1, difficulte="easy")
    e = etat([av], faits(1))
    assert pts(av, faits(1)) == 3
    assert e.jauge.maximum == 1 and e.jauge.seuil == 1
    assert e.jauge.points == 3 and e.jauge.pleine  # points > maximum : pas de plafond, pas de plantage


def test_eclaireur_qui_fait_les_quetes_apres_le_full_succes_rapporte_3():
    ecl = grimpeur(1, difficulte="med")
    assert pts(ecl, faits(1)) == 3
    assert etat([ecl], faits(1)).jauge.maximum == 2


def test_points_au_dela_du_maximum_ne_comptent_pas_pour_un_autre_etat():
    # 1 Aventurier au-dessus + 1 Collectionneur à 0 : 3 points sur 4, seuil 3 → pleine.
    gs = [grimpeur(1, difficulte="easy"), grimpeur(2, difficulte="hard")]
    e = etat(gs, faits(1))
    assert (e.jauge.points, e.jauge.maximum, e.jauge.seuil, e.jauge.pleine) == (3, 4, 3, True)


# --- Paliers stricts (§8 bis b) -------------------------------------------------------------------


@pytest.mark.parametrize(("contenus", "attendu"), [
    ((6,), 0),                       # quêtes seules
    ((1, 6), 1),                     # donjon + quêtes, sans full succès
    ((1, 2, 3, 4, 6), 1),            # 4 succès sur 5 + quêtes
    ((*CHALLENGES, 6), 0),           # full succès SANS le succès 33 (donjon non enregistré) + quêtes
    (CHALLENGES, 0),                 # challenges sans le succès de base
    (FULL_SUCCES, 2),
    ((*FULL_SUCCES, 6), 3),
])  # fmt: skip
def test_paliers_stricts(contenus, attendu):
    assert pts(grimpeur(1, difficulte="hard"), faits(1, contenus)) == attendu


def test_full_succes_sans_donjon_enregistre_marques():
    m = marques_grimpeur(grimpeur(1), PALIERS, faits(1, CHALLENGES), ETAGE0)
    assert m == {1: False, 2: False, 3: False}


def test_quete_annulee_redescend_de_3_a_2():
    vs = faits(1, FULL_SUCCES) + [validation(1, 6, niveau=None, source="declaration", statut="annulee")]
    assert pts(grimpeur(1), vs) == 2


def test_validation_d_un_autre_grimpeur_ne_compte_pas():
    assert pts(grimpeur(1), faits(2)) == 0


def test_validation_refusee_puis_acceptee_compte():
    vs = [validation(1, 1, statut="refusee"), validation(1, 1)]
    assert pts(grimpeur(1), vs) == 1


# --- Retardataires (§5.4, §8 bis c, d, e) --------------------------------------------------------


def test_plancher_est_le_moins_avance_des_comptes():
    gs = [
        grimpeur(1, niveau=18),
        grimpeur(2, niveau=12),
        grimpeur(3, niveau=None),
        grimpeur(4, niveau=5, statut="pause"),
        grimpeur(5, niveau=3, retard=True),
    ]
    assert niveau_plancher(gs, ETAGE0) == 12  # ni la pause, ni le retardataire, ni l'inconnu


def test_plancher_sans_aucun_niveau_connu_est_le_cap():
    assert niveau_plancher([grimpeur(1, niveau=None), grimpeur(2, niveau=None)], ETAGE0) == 20
    assert niveau_plancher([], ETAGE0) == 20


def test_retardataire_sans_niveau_connu_reste_retardataire():
    r = grimpeur(9, niveau=None, retard=True)
    assert not doit_etre_inclus(r, 1)


def test_retardataire_a_egalite_avec_le_plancher_est_inclus():
    r = grimpeur(9, niveau=12, retard=True)
    assert doit_etre_inclus(r, 12) and not doit_etre_inclus(r, 13)


def test_retardataire_hors_maximum_et_hors_points():
    comptes = [grimpeur(1, difficulte="hard"), grimpeur(2, difficulte="med")]
    r = grimpeur(9, difficulte="hard", retard=True)
    e = etat([*comptes, r], faits(9))
    assert (e.jauge.maximum, e.jauge.points, e.n_retardataires, e.n_comptes) == (5, 0, 1, 2)
    assert e.grimpeurs_par_palier == (0, 0, 0)


def test_inclusion_forcee_fait_monter_le_maximum_et_compte_ses_points():
    comptes = [grimpeur(i, difficulte="easy") for i in range(1, 5)]  # M = 4, S = 3
    r = grimpeur(9, difficulte="hard", niveau=3, retard=True)
    avant = etat([*comptes, r], faits(9) + faits(1, (1,)) + faits(2, (1,)) + faits(3, (1,)))
    assert (avant.jauge.points, avant.jauge.maximum, avant.jauge.seuil, avant.jauge.pleine) == (3, 4, 3, True)
    inclus = replace(r, inclus_le=PENDANT, inclusion_forcee=True)
    apres = etat([*comptes, inclus], faits(9) + faits(1, (1,)) + faits(2, (1,)) + faits(3, (1,)))
    # Le maximum monte de 3, le seuil de 3 à 6, ses 3 points comptent : 6/7, seuil 6 → toujours pleine.
    assert (apres.jauge.points, apres.jauge.maximum, apres.jauge.seuil) == (6, 7, 6)


def test_inclusion_d_un_retardataire_a_zero_point_vide_une_jauge_pleine():
    """§7 « Jauge pleine, puis plus pleine » : le site affiche l'état réel."""
    comptes = [grimpeur(i, difficulte="easy") for i in range(1, 5)]
    vs = faits(1, (1,)) + faits(2, (1,)) + faits(3, (1,))
    r = replace(grimpeur(9, difficulte="hard", retard=True), inclus_le=PENDANT)
    e = etat([*comptes, r], vs)
    assert (e.jauge.points, e.jauge.maximum, e.jauge.seuil, e.jauge.pleine) == (3, 7, 6, False)


def test_inclusion_forcee_d_un_niveau_bas_fait_baisser_le_plancher():
    gs = [grimpeur(1, niveau=18), replace(grimpeur(9, niveau=4, retard=True), inclus_le=PENDANT, inclusion_forcee=True)]
    assert niveau_plancher(gs, ETAGE0) == 4


def test_retour_de_pause_n_est_pas_compte_ni_retardataire_tant_qu_il_est_en_pause():
    g = grimpeur(1, statut="pause")
    assert not est_compte(g) and not est_retardataire(g) and not doit_etre_inclus(g, 1)
    revenu = replace(g, statut="actif", inclus_le=None)  # ce que fait la reprise (§8 bis e)
    assert est_retardataire(revenu)


def test_exclu_n_est_jamais_inclus():
    g = grimpeur(1, statut="exclu", niveau=200, retard=True)
    assert not doit_etre_inclus(g, 1)
    assert etat([g], faits(1)).jauge.maximum == 0


def test_inscription_a_la_seconde_de_l_ouverture():
    ouv = ETAGE0.ouvert_le
    assert inclus_des_l_inscription(ouv - timedelta(seconds=1), ETAGE0)
    assert not inclus_des_l_inscription(ouv, ETAGE0)  # « avant » l'ouverture : strict


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Écart à arbitrer : si tous les comptés ont dépassé le cap (tolérance Q9 / « bloquer au 21 »), "
        "le plancher passe au-dessus du cap ; un retardataire qui respecte le cap ne peut alors jamais "
        "être inclus automatiquement. Attendu : plancher plafonné au level_cap."
    ),
)
def test_plancher_jamais_au_dessus_du_cap():
    gs = [grimpeur(1, niveau=21), grimpeur(2, niveau=22)]
    r = grimpeur(9, niveau=20, retard=True)
    assert doit_etre_inclus(r, niveau_plancher(gs, ETAGE0))


# --- N = 0, changement de difficulté, seuil ------------------------------------------------------


def test_n_zero():
    e = etat([], [])
    assert (e.jauge.points, e.jauge.maximum, e.jauge.seuil, e.jauge.pleine, e.deblocable) == (0, 0, 0, False, False)
    assert e.jauge.manquants == 0


def test_n_zero_avec_seulement_pause_retardataire_exclu_et_leurs_points():
    gs = [grimpeur(1, statut="pause"), grimpeur(2, retard=True), grimpeur(3, statut="exclu")]
    vs = faits(1) + faits(2) + faits(3)
    e = etat(gs, vs, maintenant=ETAGE0.date_plancher_suivant + timedelta(days=1))
    assert (e.jauge.points, e.jauge.maximum, e.jauge.pleine, e.deblocable) == (0, 0, False, False)
    assert (e.n_comptes, e.n_pause, e.n_retardataires) == (0, 1, 1)


def test_changement_de_difficulte_recalcule_maximum_et_seuil_pas_les_points():
    gs = [grimpeur(i, difficulte=d) for i, d in enumerate(["hard"] * 4 + ["med"] * 4 + ["easy"] * 4, 1)]
    vs = faits(5, FULL_SUCCES)
    avant = etat(gs, vs)
    gs[4] = replace(gs[4], difficulte="hard")  # un Éclaireur devient Collectionneur
    apres = etat(gs, vs)
    assert (avant.jauge.maximum, avant.jauge.seuil) == (24, 18)
    assert (apres.jauge.maximum, apres.jauge.seuil) == (25, 19)
    assert avant.jauge.points == apres.jauge.points == 2
    assert apres.comptes_par_difficulte == {"easy": 4, "med": 3, "hard": 5}


def test_seuil_100_pourcent():
    e100 = replace(ETAGE0, seuil_pourcent=100)
    gs = [grimpeur(1, difficulte="med"), grimpeur(2, difficulte="easy")]
    assert not etat(gs, faits(1, FULL_SUCCES), etage=e100).jauge.pleine  # 2/3
    assert etat(gs, faits(1, FULL_SUCCES) + faits(2, (1,)), etage=e100).jauge.pleine  # 3/3
    # Un Aventurier qui en fait plus compense un Éclaireur à 0 : 3/3 quand même.
    assert etat(gs, faits(2, (*FULL_SUCCES, 6)), etage=e100).jauge.pleine


def test_seuil_1_pourcent_un_point_suffit():
    e1 = replace(ETAGE0, seuil_pourcent=1)
    gs = [grimpeur(i, difficulte="hard") for i in range(1, 13)]  # M = 36, S = ⌈0,36⌉ = 1
    assert etat(gs, faits(1, (1,)), etage=e1).jauge.seuil == 1
    assert etat(gs, faits(1, (1,)), etage=e1).jauge.pleine


@pytest.mark.parametrize("p", [0, -5, 101])
def test_seuil_0_ou_hors_bornes_refuse(p):
    with pytest.raises(ValueError):
        seuil(24, p)
    with pytest.raises(ValueError):
        etat([grimpeur(1)], [], etage=replace(ETAGE0, seuil_pourcent=p))


@pytest.mark.parametrize(
    ("m", "p", "s"),
    [(1, 75, 1), (3, 75, 3), (4, 75, 3), (19, 75, 15), (25, 75, 19), (50, 14, 7), (100, 33, 33), (7, 100, 7)],
)
def test_seuil_valeurs(m, p, s):
    assert seuil(m, p) == s


# --- Dates, heure de Paris, changement d'heure ---------------------------------------------------


def paris(*a):
    return datetime(*a, tzinfo=PARIS)


def test_dates_de_l_etage_0_dans_le_yaml_sont_a_l_heure_d_hiver_de_paris():
    """Le 25/10/2026 on repasse à l'heure d'hiver : 30/10 17:00 Paris = 16:00 UTC (et non 15:00)."""
    cfg = yaml.safe_load((RACINE / "config/etages/etage-0.yaml").read_text(encoding="utf-8"))
    assert cfg["ouvert_le"].astimezone(UTC) == datetime(2026, 10, 30, 16, 0, tzinfo=UTC)
    assert cfg["ouvert_le"] == paris(2026, 10, 30, 17, 0)
    assert cfg["date_plancher_suivant"] == paris(2026, 11, 13, 17, 0)


def test_deblocable_a_la_minute_pres_heure_de_paris():
    gs = [grimpeur(1)]
    vs = faits(1, (1,))
    assert not etat(gs, vs, maintenant=paris(2026, 11, 13, 16, 59)).deblocable
    assert not etat(gs, vs, maintenant=paris(2026, 11, 13, 16, 59, 59, 999999)).deblocable
    assert etat(gs, vs, maintenant=paris(2026, 11, 13, 17, 0)).deblocable
    # 17:00 en heure d'été (+02:00) = 16:00 en hiver : pas encore.
    assert not etat(gs, vs, maintenant=datetime(2026, 11, 13, 15, 0, tzinfo=UTC)).deblocable
    # Comparaison indépendante du fuseau de « maintenant ».
    assert etat(gs, vs, maintenant=datetime(2026, 11, 13, 16, 0, tzinfo=UTC)).deblocable


def test_validation_avant_l_ouverture_a_la_seconde_pres():
    g = grimpeur(1)
    c = CONTENUS[0]
    juste_avant = paris(2026, 10, 30, 16, 59, 59)
    pile = paris(2026, 10, 30, 17, 0)
    assert MOTIF_AVANT_OUVERTURE in controler_validation(g, c, 20, juste_avant, ETAGE0, False).bloquants
    assert controler_validation(g, c, 20, pile, ETAGE0, False).ok
    assert not validation_compte(validation(1, 1, realisee_le=juste_avant), ETAGE0)
    assert validation_compte(validation(1, 1, realisee_le=pile), ETAGE0)


def test_validation_la_nuit_du_changement_d_heure_avant_ouverture():
    # 25/10/2026 02:30 existe deux fois à Paris ; dans les deux cas, c'est avant l'ouverture.
    for fold in (0, 1):
        d = datetime(2026, 10, 25, 2, 30, tzinfo=PARIS, fold=fold)
        assert MOTIF_AVANT_OUVERTURE in controler_validation(grimpeur(1), CONTENUS[0], 20, d, ETAGE0, False).bloquants


def test_etage_ouvert_sans_date_d_ouverture():
    e = replace(ETAGE0, ouvert_le=None)
    assert MOTIF_AVANT_OUVERTURE in controler_validation(grimpeur(1), CONTENUS[0], 20, PENDANT, e, False).bloquants
    assert etat([grimpeur(1)], faits(1), etage=e).jauge.points == 0


def test_sans_date_plancher_deblocable_des_que_pleine():
    e = replace(ETAGE0, date_plancher_suivant=None)
    assert etat([grimpeur(1)], faits(1, (1,)), etage=e).deblocable


# --- Cap dépassé (Q3, Q9) -------------------------------------------------------------------------


@pytest.mark.parametrize(("niveau", "bloque", "avertit"), [
    (1, False, False), (15, False, False), (20, False, False), (21, False, True), (200, False, True),
    (0, True, False), (-1, True, False), (201, True, False), (999, True, False),
])  # fmt: skip
def test_controle_du_niveau(niveau, bloque, avertit):
    c = controler_validation(grimpeur(1), CONTENUS[0], niveau, PENDANT, ETAGE0, False)
    assert (not c.ok) == bloque
    assert bool(c.avertissements) == avertit


def test_cap_depasse_non_force_ne_compte_pas_force_compte():
    assert pts(grimpeur(1), [validation(1, 1, niveau=21)]) == 0
    assert pts(grimpeur(1), [validation(1, 1, niveau=21, forcee=True)]) == 1


def test_un_seul_succes_au_dessus_du_cap_bloque_le_palier_2():
    vs = faits(1, (1, 2, 3, 4)) + [validation(1, 5, niveau=22)]
    assert pts(grimpeur(1), vs) == 1


def test_declaration_de_quetes_sans_niveau_pas_de_cap():
    c = controler_validation(grimpeur(1), CONTENUS[5], None, PENDANT, ETAGE0, False)
    assert c.ok and not c.avertissements


def test_tous_les_motifs_ensemble():
    autre_etage = replace(CONTENUS[0], etage_id=99)
    c = controler_validation(
        grimpeur(1, statut="exclu"),
        autre_etage,
        999,
        ETAGE0.ouvert_le - timedelta(1),
        replace(ETAGE0, statut="scelle"),
        True,
    )
    assert len(c.bloquants) == 6 and MOTIF_EXCLU in c.bloquants and MOTIF_DEJA_VALIDE in c.bloquants
    assert MOTIF_PAUSE not in c.bloquants
