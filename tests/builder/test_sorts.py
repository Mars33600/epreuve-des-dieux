"""Calculateur de sorts, chiffré à la main d'après le code de Duffus (`Rt`), sur les niveaux de « Pression » (Iop)."""

from epreuve.builder.sorts import calculer_sort, grade_pour, jet_sort

PRESSION = {"id": 13106, "nom": "Pression", "icone": 11830, "niveaux": [
    {"grade": 1, "niveau": 1, "cc": 10, "pa": 3, "po_min": 1, "po_max": 4,
     "effets": [[776, 10, 0, 0], [97, 16, 18, 0]], "effets_cc": [[776, 10, 0, 0], [97, 19, 21, 0]]},
    {"grade": 2, "niveau": 66, "cc": 10, "pa": 3, "po_min": 1, "po_max": 4,
     "effets": [[776, 10, 0, 0], [97, 20, 23, 0]], "effets_cc": [[776, 10, 0, 0], [97, 24, 28, 0]]},
    {"grade": 3, "niveau": 132, "cc": 10, "pa": 3, "po_min": 1, "po_max": 4,
     "effets": [[776, 10, 0, 0], [97, 26, 30, 0]], "effets_cc": [[776, 10, 0, 0], [97, 31, 36, 0]]},
]}  # fmt: skip
TOTAUX = {"Force": 200, "Puissance": 50, "Do Terre": 10, "Dommages": 5, "Do Critique": 8, "% Do Sorts": 20,
          "% Do Mélée": 10, "% Critique": 15}


def test_pression_grade_3():
    """k = (50 + 200 + 100) / 100 = 3,5. Normal 26 : ⌊91⌋ + 15 = 106 → ⌊127,2⌋ → ⌊139,7⌋ = 139 ;
    30 : 120 → 144 → 158. Critique (+ 8) 31 : 108 + 23 = 131 → 157 → 172 ; 36 : 149 → 178 → 195."""
    r = calculer_sort(PRESSION, TOTAUX, 200)
    assert (r["grade"], r["pa"], r["po"], r["taux_critique"]) == (3, 3, [1, 4], 25)
    assert r["normal"] == [{"effet": 97, "libelle": "dommages Terre", "soin": False, "jet": [139, 158]}]
    assert r["critique"][0]["jet"] == [172, 195]  # l'effet 776 (érosion) n'est pas une ligne de dégâts
    assert calculer_sort(PRESSION, {**TOTAUX, "% Do Dist": 0}, 200, "distance")["normal"][0]["jet"] == [127, 144]


def test_grade_selon_le_niveau():
    assert grade_pour(PRESSION["niveaux"], 100)["grade"] == 2
    assert grade_pour(PRESSION["niveaux"], 132)["grade"] == 3
    assert calculer_sort(PRESSION, {}, 0) is None
    assert calculer_sort(PRESSION, {}, 1)["normal"][0]["jet"] == [16, 18]


def test_soins_poussee_meilleur_et_pire_element():
    assert jet_sort([108, 10, 20, 0], {"Intelligence": 50, "Soins": 3}) == (18, 33)
    assert jet_sort([5, 2, 0, 0], {"Do Pou": 10}, niveau=200) == (71, 71)  # ⌊(100 + 10 + 32) × 2 / 4⌋
    c = {"Force": 100, "Chance": 300, "Do Eau": 4, "Do Feu": 7}
    assert jet_sort([2822, 10, 0, 0], c) == (44, 44)  # Chance : 4 × 10 + 4
    assert jet_sort([2832, 10, 0, 0], c) == (17, 17)  # pire : Intelligence (0), le premier à égalité : 10 + 7
    assert jet_sort([97, 0, 0, 0], c) is None and jet_sort([776, 10, 0, 0], c) is None
    assert jet_sort([5, 0, 0, 0], c) is None
