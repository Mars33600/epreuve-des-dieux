"""seuil() : l'arrondi au-dessus de maximum × pourcent / 100, calculé en entiers."""

import fractions
import math

import pytest

from epreuve.domaine.seuil import POINTS_VISES, seuil


@pytest.mark.parametrize("pourcent", [50, 66, 70, 75, 80, 100])
@pytest.mark.parametrize("maximum", range(0, 91))
def test_seuil_table_complete(maximum, pourcent):
    # Référence : la fraction exacte de la bibliothèque standard, sans flottant.
    assert seuil(maximum, pourcent) == math.ceil(fractions.Fraction(maximum * pourcent, 100))


def test_cas_de_shadoaze():
    # 12 grimpeurs, 4 par difficulté : 4×3 + 4×2 + 4×1 = 24 points, seuil 75 % → 18.
    maximum = 4 * POINTS_VISES["hard"] + 4 * POINTS_VISES["med"] + 4 * POINTS_VISES["easy"]
    assert maximum == 24 and seuil(24, 75) == 18
    assert seuil(25, 75) == 19  # un Éclaireur devenu Collectionneur


def test_maximum_nul():
    assert seuil(0, 75) == 0
    assert seuil(-3, 75) == 0


@pytest.mark.parametrize("pourcent", [0, 101, -5])
def test_pourcentage_hors_bornes_refuse(pourcent):
    with pytest.raises(ValueError):
        seuil(24, pourcent)


def test_regression_flottant():
    # 0,75 × 24 tombe juste en machine, mais pas 50 × 0,14 = 7,000000000000001 → ceil = 8.
    assert math.ceil(50 * (14 / 100)) == 8
    assert seuil(50, 14) == 7
