"""Garde-fous de mise en page trouvés à la recette : ils ne se voient qu'au navigateur, on les fige dans le CSS."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src/epreuve/web/static"


def regle(css: str, selecteur: str) -> str:
    m = re.search(rf"(?m)^{re.escape(selecteur)}\{{([^}}]*)\}}", css)
    assert m, f"règle « {selecteur} » introuvable"
    return m.group(1)


def test_le_corps_n_est_pas_un_conteneur_de_defilement_et_couvre_l_ecran():
    # `html{overflow-x:clip}` coupe la propagation : un `overflow-x:hidden` sur body en faisait un conteneur de
    # défilement à la hauteur du contenu, qui rognait le menu déroulant et les suggestions sur les pages courtes
    # (le prologue plein écran, une erreur…).
    corps = regle((STATIC / "style.css").read_text(), "body")
    assert "overflow-x:hidden" not in corps and "overflow:hidden" not in corps
    assert "min-height:100vh" in corps
