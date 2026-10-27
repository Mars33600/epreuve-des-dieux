"""points_grimpeur(), marques_grimpeur() et calculer_etat_etage() : la jauge à points."""

from dataclasses import replace
from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from epreuve.domaine.jauges import calculer_etat_etage, marques_grimpeur, points_grimpeur
from epreuve.domaine.modeles import Palier
from tests.fabrique import (
    CHALLENGES,
    ETAGE0,
    FULL_SUCCES,
    PALIERS,
    PARIS,
    PENDANT,
    faits,
    grimpeur,
    validation,
)


def etat(grimpeurs, validations, maintenant=PENDANT, paliers=PALIERS, etage=ETAGE0):
    return calculer_etat_etage(etage, paliers, grimpeurs, validations, maintenant)


def points(validations, g=None):
    return points_grimpeur(g or grimpeur(1), PALIERS, validations, ETAGE0)


def douze():
    """L'exemple de Shadoaze : 4 Collectionneurs, 4 Éclaireurs, 4 Aventuriers."""
    return [grimpeur(i, difficulte=d) for i, d in enumerate(["hard"] * 4 + ["med"] * 4 + ["easy"] * 4, start=1)]


# --- Points d'un grimpeur -------------------------------------------------------------------------


def test_points_selon_les_paliers():
    assert points([]) == 0
    assert points(faits(1, (1,))) == 1
    assert points(faits(1, FULL_SUCCES)) == 2
    assert points(faits(1)) == 3


def test_quatre_challenges_sans_le_succes_33_zero_point():
    assert points(faits(1, CHALLENGES)) == 0
    assert points(faits(1, (*CHALLENGES, 6))) == 0


def test_paliers_stricts_quetes_sans_full_succes():
    assert points(faits(1, (1, 6))) == 1
    m = marques_grimpeur(grimpeur(1), PALIERS, faits(1, (1, 6)), ETAGE0)
    assert m == {1: True, 2: False, 3: True}  # la marque Quêtes s'allume quand même


def test_un_aventurier_peut_rapporter_2_ou_3():
    aventurier = grimpeur(1, difficulte="easy")
    assert points(faits(1, FULL_SUCCES), aventurier) == 2
    assert points(faits(1), aventurier) == 3


def test_annulee_refusee_ne_comptent_pas():
    assert points([validation(1, 1, statut="annulee")]) == 0
    assert points([validation(1, 1, statut="refusee")]) == 0


def test_cap_forcee_ou_non():
    assert points([validation(1, 1, niveau=21)]) == 0
    assert points([validation(1, 1, niveau=21, forcee=True)]) == 1


def test_declaration_sans_niveau_compte():
    assert points(faits(1)) == 3 and faits(1)[-1].niveau is None


def test_avant_ouverture_ne_compte_pas():
    assert points([validation(1, 1, realisee_le=ETAGE0.ouvert_le - timedelta(hours=1))]) == 0


def test_paliers_mal_formes_arretent_la_montee():
    vide = (PALIERS[0], replace(PALIERS[1], contenu_ids=frozenset()), PALIERS[2])
    assert points_grimpeur(grimpeur(1), vide, faits(1), ETAGE0) == 1
    saut = (PALIERS[0], PALIERS[2])  # pas de rang 2
    assert points_grimpeur(grimpeur(1), saut, faits(1), ETAGE0) == 1
    assert marques_grimpeur(grimpeur(1), vide, faits(1), ETAGE0) == {1: True, 2: False, 3: True}


# --- La jauge ------------------------------------------------------------------------------------


def test_exemple_de_shadoaze_4_4_4():
    e = etat(douze(), [])
    assert (e.jauge.maximum, e.jauge.seuil, e.jauge.seuil_pourcent) == (24, 18, 75)
    assert e.comptes_par_difficulte == {"easy": 4, "med": 4, "hard": 4}
    assert e.n_comptes == 12 and e.jauge.points == 0 and not e.jauge.pleine
    assert e.jauge.manquants == 18


def test_changement_de_difficulte_24_vers_25():
    g = douze()
    g[4] = replace(g[4], difficulte="hard")  # un Éclaireur devient Collectionneur
    e = etat(g, [])
    assert (e.jauge.maximum, e.jauge.seuil) == (25, 19)


def test_aventurier_full_succes_ne_change_pas_le_maximum():
    e = etat(douze(), faits(12, FULL_SUCCES))
    assert e.jauge.points == 2 and e.jauge.maximum == 24


def test_pause_hors_du_maximum_et_des_points():
    g = douze()
    g[0] = replace(g[0], statut="pause")
    e = etat(g, faits(1))
    assert e.jauge.maximum == 21 and e.jauge.points == 0 and e.n_pause == 1 and e.n_comptes == 11


def test_inscrit_tardif_en_pause_hors_du_maximum_et_des_points():
    g = [*douze(), grimpeur(13, difficulte="hard", statut="pause")]
    e = etat(g, faits(13) + faits(1, (1,)))
    assert e.jauge.maximum == 24 and e.jauge.points == 1  # ses 3 points ne comptent pas tant qu'il est en pause
    assert e.n_pause == 1 and e.n_comptes == 12
    assert e.grimpeurs_par_palier == (1, 0, 0)
    assert points_grimpeur(g[-1], PALIERS, faits(13), ETAGE0) == 3  # ses points personnels restent visibles
    repris = replace(g[-1], statut="actif")  # un admin le passe actif
    apres = etat([*douze(), repris], faits(13) + faits(1, (1,)))
    assert (apres.jauge.maximum, apres.jauge.points) == (27, 4)


def test_exclu_ne_compte_nulle_part():
    e = etat([grimpeur(1), grimpeur(2, statut="exclu")], faits(2))
    assert e.jauge.maximum == 1 and e.jauge.points == 0 and e.n_comptes == 1


def test_points_au_dela_du_maximum():
    g = [grimpeur(1, difficulte="easy"), grimpeur(2, difficulte="easy")]
    e = etat(g, faits(1) + faits(2))
    assert e.jauge.maximum == 2 and e.jauge.points == 6 and e.jauge.pleine and e.jauge.manquants == 0


def test_maximum_nul():
    for e in (etat([], []), etat([grimpeur(1, statut="pause")], faits(1)), etat([grimpeur(1, statut="exclu")], [])):
        assert e.jauge.maximum == 0 and e.jauge.seuil == 0 and not e.jauge.pleine and not e.deblocable


def test_grimpeurs_par_palier():
    v = faits(1) + faits(2, FULL_SUCCES) + faits(3, (1, 6)) + faits(4, CHALLENGES)
    e = etat([grimpeur(i) for i in range(1, 6)], v)
    assert e.grimpeurs_par_palier == (3, 2, 1)
    assert e.jauge.points == 3 + 2 + 1 + 0 + 0


def _pleine():
    return [grimpeur(1), grimpeur(2)], faits(1) + faits(2)


def test_deblocable_le_13_11_a_17h_heure_de_paris():
    g, v = _pleine()
    avant = etat(g, v, maintenant=datetime(2026, 11, 13, 16, 59, tzinfo=PARIS))
    assert avant.jauge.pleine and not avant.deblocable
    assert etat(g, v, maintenant=datetime(2026, 11, 13, 17, 0, tzinfo=PARIS)).deblocable


def test_deblocable_sans_date_plancher():
    g, v = _pleine()
    assert etat(g, v, etage=replace(ETAGE0, date_plancher_suivant=None)).deblocable


def test_jauge_pas_pleine_pas_deblocable():
    e = etat(douze(), faits(1), maintenant=datetime(2026, 12, 1, tzinfo=PARIS))
    assert not e.jauge.pleine and not e.deblocable


def test_paliers_dans_le_desordre():
    assert etat([grimpeur(1)], faits(1), paliers=tuple(reversed(PALIERS))).jauge.points == 3


# --- Cohérence sur des registres tirés au hasard ---------------------------------------------------

registres = st.lists(
    st.tuples(
        st.sampled_from(["actif", "actif", "pause", "exclu"]),
        st.sampled_from(["easy", "med", "hard"]),
        st.lists(  # (contenu, niveau, statut, forcée)
            st.tuples(st.integers(1, 6), st.sampled_from([None, 15, 20, 21, 23]),
                      st.sampled_from(["acceptee", "acceptee", "annulee", "refusee"]), st.booleans()),
            max_size=8,
        ),
    ),
    max_size=15,
)


@settings(max_examples=200, deadline=None)
@given(registres)
def test_coherence_points_marques_paliers(registre):
    grimpeurs, validations = [], []
    for i, (statut, diff, valids) in enumerate(registre, start=1):
        grimpeurs.append(grimpeur(i, statut=statut, difficulte=diff))
        validations += [validation(i, c, niveau=n, statut=s, forcee=f) for c, n, s, f in valids]

    e = etat(grimpeurs, validations)
    comptes = [g for g in grimpeurs if g.statut == "actif"]
    pts = {g.id: points_grimpeur(g, PALIERS, validations, ETAGE0) for g in comptes}
    assert e.jauge.points == sum(pts.values())  # seuls les actifs comptent
    for g in comptes:
        marques = marques_grimpeur(g, PALIERS, validations, ETAGE0)
        assert all(marques[k] for k in range(1, pts[g.id] + 1))  # points ≥ k ⇒ marques 1..k
    assert e.grimpeurs_par_palier == tuple(sum(p >= k for p in pts.values()) for k in (1, 2, 3))
    assert e.jauge.pleine == (e.jauge.maximum > 0 and e.jauge.points >= e.jauge.seuil)


def test_palier_seul_rang_inconnu():
    seul = (Palier(9, 1, 2, "Rang 2 sans rang 1", frozenset({1})),)
    assert points_grimpeur(grimpeur(1), seul, faits(1), ETAGE0) == 0
