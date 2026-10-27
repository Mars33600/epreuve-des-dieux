"""Le barème : catégories, points, palier, jauge, cascade (SPEC §5, critères 15 et 16)."""

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from epreuve.domaine.bareme import (
    EtatCategorie,
    calculer_jauge,
    categories_comptees,
    categories_grimpeur,
    detail_par_grimpeur,
    palier,
    points_grimpeur,
)
from epreuve.domaine.modeles import ContenuEtage, Regles
from tests.fabrique import (
    CASES_REF,
    CLASSIQUES,
    COCHES_REFERENCE,
    CONTENU_REF,
    DONJONS_REF,
    ETAGE_REF,
    GRIMPEURS_REF,
    PRINCIPALES,
    QUETES_REF,
    SECONDAIRES,
    TOUTES_CASES,
    case,
    coches,
    donjon,
    etage,
    grimpeur,
)

R = Regles()
OFFERTE = Regles(categorie_vide="offerte")


def contenu(donjons=DONJONS_REF, cases=CASES_REF, quetes=QUETES_REF, **kw_etage):
    return ContenuEtage.visible(etage(**kw_etage), donjons, cases, quetes)


# --- Catégories et points ------------------------------------------------------------------------------


def test_etat_categorie():
    assert EtatCategorie("donjons", 3, 3).acquise and not EtatCategorie("donjons", 3, 3).vide
    assert not EtatCategorie("donjons", 2, 3).acquise
    assert EtatCategorie("donjons", 0, 0).vide and not EtatCategorie("donjons", 0, 0).acquise


@pytest.mark.parametrize(("cases", "quetes", "attendu"), [
    (CLASSIQUES, (), {"donjons"}),
    (TOUTES_CASES, (), {"donjons", "full_succes"}),  # full succès ⇒ donjons (la classique fait partie des 5)
    ((), PRINCIPALES, {"principales"}),
    ((), SECONDAIRES, {"secondaires"}),
    ((), PRINCIPALES + SECONDAIRES, {"principales", "secondaires"}),  # indépendance : quêtes sans donjons
    (TOUTES_CASES[1:], (), set()),  # tout sauf une classique
])
def test_chaque_categorie_seule(cases, quetes, attendu):
    etats = categories_grimpeur(CONTENU_REF, coches(1, cases, quetes))
    assert {c for c, e in etats.items() if e.acquise} == attendu
    assert points_grimpeur(CONTENU_REF, coches(1, cases, quetes), R) == len(attendu)


def test_totaux_de_reference():
    etats = categories_grimpeur(CONTENU_REF, coches(1))
    assert {c: e.total for c, e in etats.items()} == {"donjons": 3, "full_succes": 15, "principales": 4,
                                                       "secondaires": 5}


def test_donjon_masque_et_case_masquee_ne_comptent_pas():
    donjons = (donjon(1), donjon(2), donjon(3, masque=True))
    cases = tuple(c if c.id != 2 else case(2, 1, 2, masquee=True) for c in CASES_REF)
    c = contenu(donjons=donjons, cases=cases)
    etats = categories_grimpeur(c, coches(1, (1, 3, 4, 5, 6, 7, 8, 9, 10)))
    assert (etats["donjons"].faits, etats["donjons"].total) == (2, 2)
    assert (etats["full_succes"].faits, etats["full_succes"].total) == (9, 9)
    assert etats["full_succes"].acquise


def test_donjon_sans_case_classique_visible():
    cases = tuple(c if c.id != 1 else case(1, 1, 1, masquee=True) for c in CASES_REF)
    etats = categories_grimpeur(contenu(cases=cases), coches(1, (6, 11)))
    assert (etats["donjons"].faits, etats["donjons"].total) == (2, 2) and etats["donjons"].acquise


def test_categorie_vide_jamais_acquise_sauf_offerte():
    sans_principale = contenu(quetes=tuple(q for q in QUETES_REF if q.nature == "secondaire"))
    c = coches(1, (), SECONDAIRES)
    assert not categories_grimpeur(sans_principale, c)["principales"].acquise
    assert points_grimpeur(sans_principale, c, R) == 1
    assert points_grimpeur(sans_principale, c, OFFERTE) == 2
    assert categories_comptees(sans_principale, R) == 3
    assert categories_comptees(sans_principale, OFFERTE) == 4


# --- Palier ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("n", "k", "attendu"), [
    (12, 4, 24), (12, 3, 18), (11, 3, 17), (0, 4, 0), (12, 0, 0), (12, 1, 6), (11, 1, 6), (5, 2, 5),
])
def test_palier_formule(n, k, attendu):
    assert palier(n, k, R) == attendu


def test_palier_exact_en_fraction():
    assert palier(3, 4, Regles(points_par_joueur=Fraction(5, 2))) == 8  # 7,5 → 8
    assert palier(24, 3, Regles(points_par_joueur=Fraction(1))) == 18  # 0,75 × 24 : pas de 19 parasite


def test_palier_manuel_prime():
    assert palier(12, 4, R, palier_manuel=7) == 7
    assert palier(12, 4, R, palier_manuel=0) == 0


@pytest.mark.parametrize(("n", "k", "manuel"), [(-1, 4, None), (1, -1, None), (1, 5, None), (1, 4, -2)])
def test_palier_entrees_invalides(n, k, manuel):
    with pytest.raises(ValueError):
        palier(n, k, R, manuel)


# --- Jauge ------------------------------------------------------------------------------------------------


def test_jauge_de_reference_calculee_a_la_main():
    """Critère 15 : 10 actifs (11 et 12 en pause), points 4+3+2+1+1+0+0+1+2+3 = 17, palier 2 × 10 = 20."""
    j = calculer_jauge(CONTENU_REF, GRIMPEURS_REF, COCHES_REFERENCE, R)
    assert (j.score, j.palier, j.actifs, j.en_pause, j.nb_categories) == (17, 20, 10, 2, 4)
    assert j.points_par_categorie == {"donjons": 5, "full_succes": 3, "principales": 5, "secondaires": 4}
    assert not j.pleine and j.manquants == 3 and j.maximum == 40 and not j.palier_manuel


def test_jauge_exclus_ignores_et_palier_manuel():
    gs = [*GRIMPEURS_REF, grimpeur(13, "exclu")]
    c = ContenuEtage.visible(etage(palier_manuel=15), DONJONS_REF, CASES_REF, QUETES_REF)
    j = calculer_jauge(c, gs, {**COCHES_REFERENCE, 13: COCHES_REFERENCE[1]}, R)
    assert (j.score, j.palier, j.actifs, j.en_pause) == (17, 15, 10, 2)
    assert j.palier_manuel and j.pleine and j.manquants == 0


def test_jauge_sans_actif_jamais_pleine():
    j = calculer_jauge(CONTENU_REF, [grimpeur(1, "pause")], COCHES_REFERENCE, R)
    assert (j.actifs, j.palier, j.score) == (0, 0, 0) and not j.pleine and j.maximum == 0


def test_palier_zero_jamais_plein():
    vide = ContenuEtage.visible(ETAGE_REF, (), (), ())
    j = calculer_jauge(vide, GRIMPEURS_REF, {}, R)
    assert (j.palier, j.nb_categories) == (0, 0) and not j.pleine


def test_jauge_offerte_compte_la_categorie_vide_pour_chaque_actif():
    sans_principale = contenu(quetes=tuple(q for q in QUETES_REF if q.nature == "secondaire"))
    j = calculer_jauge(sans_principale, [grimpeur(1), grimpeur(2)], {}, OFFERTE)
    assert j.points_par_categorie["principales"] == 2 and j.score == 2 and j.palier == 4


def test_detail_par_grimpeur():
    d = detail_par_grimpeur(CONTENU_REF, GRIMPEURS_REF[:3], COCHES_REFERENCE, R)
    assert [(g.id, pts) for g, _, pts in d] == [(1, 4), (2, 3), (3, 2)]
    assert d[2][1]["full_succes"].acquise


# --- Propriétés -------------------------------------------------------------------------------------------

sous_cases = st.frozensets(st.sampled_from(TOUTES_CASES))
sous_quetes = st.frozensets(st.sampled_from(PRINCIPALES + SECONDAIRES))


@given(sous_cases, sous_quetes, st.sampled_from([R, OFFERTE]))
def test_points_entre_0_et_4(cs, qs, regles):
    assert 0 <= points_grimpeur(CONTENU_REF, coches(1, cs, qs), regles) <= 4


@given(sous_cases, sous_quetes, sous_cases, sous_quetes)
def test_cocher_ne_fait_jamais_baisser_les_points(cs, qs, cs2, qs2):
    avant = points_grimpeur(CONTENU_REF, coches(1, cs, qs), R)
    assert points_grimpeur(CONTENU_REF, coches(1, cs | cs2, qs | qs2), R) >= avant


@given(st.integers(0, 1000))
def test_palier_quatre_categories_vaut_2n(n):
    assert palier(n, 4, R) == 2 * n


@given(st.lists(st.tuples(st.sampled_from(["actif", "pause", "exclu"]), sous_cases, sous_quetes), max_size=8))
def test_jauge_somme_des_points_des_actifs(lignes):
    gs = [grimpeur(i, s) for i, (s, _, _) in enumerate(lignes, 1)]
    cs = {i: coches(i, c, q) for i, (_, c, q) in enumerate(lignes, 1)}
    j = calculer_jauge(CONTENU_REF, gs, cs, R)
    assert j.score == sum(points_grimpeur(CONTENU_REF, cs[g.id], R) for g in gs if g.statut == "actif")
    assert j.score == sum(j.points_par_categorie.values())
