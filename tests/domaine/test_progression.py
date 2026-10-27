"""Compteurs, « qui ne l'a pas fait ? », avancement, moins avancé (SPEC §4.6, critère 18)."""

from hypothesis import given
from hypothesis import strategies as st

from epreuve.domaine.bareme import categories_grimpeur
from epreuve.domaine.modeles import CATEGORIES, ElementRef, Regles
from epreuve.domaine.progression import avancement, compteurs, moins_avance, qui, qui_categorie
from tests.fabrique import (
    COCHES_REFERENCE,
    CONTENU_REF,
    GRIMPEURS_REF,
    PRINCIPALES,
    SECONDAIRES,
    TOUTES_CASES,
    coches,
    grimpeur,
)

R = Regles()


def test_compteurs_ne_comptent_que_les_actifs():
    c = compteurs(CONTENU_REF, GRIMPEURS_REF, COCHES_REFERENCE)
    assert c[ElementRef("case", 1)] == 6  # 1, 2, 3, 6, 8, 10 (11 est en pause)
    assert c[ElementRef("quete", 9)] == 4  # 1, 2, 5, 9
    assert len(c) == 15 + 9


def test_qui_tri_par_pseudo_sans_casse():
    gs = [grimpeur(1, pseudo="brindille"), grimpeur(2, pseudo="Arbre"), grimpeur(3, pseudo="Cèpe"),
          grimpeur(4, "pause", pseudo="Aaa"), grimpeur(5, "exclu", pseudo="Aab")]
    cs = {1: coches(1, (1,)), 3: coches(3, (1,))}
    assert [g.pseudo for g in qui(ElementRef("case", 1), gs, cs, True)] == ["brindille", "Cèpe"]
    assert [g.pseudo for g in qui(ElementRef("case", 1), gs, cs, False)] == ["Arbre"]


def test_qui_categorie_coherent_avec_categories_grimpeur():
    for cat in CATEGORIES:
        faits = {g.id for g in qui_categorie(CONTENU_REF, cat, GRIMPEURS_REF, COCHES_REFERENCE, True)}
        pas = {g.id for g in qui_categorie(CONTENU_REF, cat, GRIMPEURS_REF, COCHES_REFERENCE, False)}
        assert faits | pas == set(range(1, 11)) and not faits & pas
        for i in faits:
            assert categories_grimpeur(CONTENU_REF, COCHES_REFERENCE[i])[cat].acquise
    assert {g.id for g in qui_categorie(CONTENU_REF, "full_succes", GRIMPEURS_REF, COCHES_REFERENCE, True)} \
        == {1, 3, 10}


def test_avancement():
    assert avancement(CONTENU_REF, COCHES_REFERENCE[1]) == (24, 24)
    assert avancement(CONTENU_REF, coches(7)) == (0, 24)
    assert avancement(CONTENU_REF, coches(7, (1, 999), (1,))) == (2, 24)  # 999 n'est pas visible


def test_moins_avance_ignore_les_geles_et_departage():
    # 6 et 7 ont 0 point ; 7 n'a rien coché, 6 a coché 5 éléments.
    assert moins_avance(CONTENU_REF, GRIMPEURS_REF, COCHES_REFERENCE, R).id == 7
    gs = [grimpeur(1, pseudo="Zed"), grimpeur(2, pseudo="alpha"), grimpeur(3, "pause", pseudo="Aaa")]
    assert moins_avance(CONTENU_REF, gs, {}, R).pseudo == "alpha"  # égalité : le pseudo


def test_moins_avance_sans_actif():
    assert moins_avance(CONTENU_REF, [grimpeur(1, "pause")], {}, R) is None


@given(st.lists(st.tuples(st.sampled_from(["actif", "pause", "exclu"]),
                          st.frozensets(st.sampled_from(TOUTES_CASES)),
                          st.frozensets(st.sampled_from(PRINCIPALES + SECONDAIRES))), max_size=8))
def test_propriete_compteur_plus_pas_faits_egale_actifs(lignes):
    gs = [grimpeur(i, s) for i, (s, _, _) in enumerate(lignes, 1)]
    cs = {i: coches(i, c, q) for i, (_, c, q) in enumerate(lignes, 1)}
    nb_actifs = sum(1 for g in gs if g.statut == "actif")
    for ref, n in compteurs(CONTENU_REF, gs, cs).items():
        assert n + len(qui(ref, gs, cs, False)) == nb_actifs
        assert n == len(qui(ref, gs, cs, True))
