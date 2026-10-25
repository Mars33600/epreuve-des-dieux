"""Les points visés par difficulté et le seuil de la jauge, calculé en entiers.

La jauge d'un étage (SPEC §5.3) : chaque grimpeur compté « vise » 1, 2 ou 3 points selon sa
difficulté. Le maximum est la somme des points visés ; le seuil est un pourcentage de ce maximum,
arrondi au-dessus.

Pourquoi des entiers : en virgule flottante, certaines multiplications ne tombent pas juste.
0,75 × 24 donne bien 18,0 sur nos machines, mais 50 × 0,14 donne 7,000000000000001, et l'arrondi
au-dessus donnerait alors 8 au lieu de 7. Avec (maximum × pourcent + 99) // 100, il n'y a aucune
virgule, donc aucune erreur possible.
"""

from __future__ import annotations

POINTS_VISES: dict[str, int] = {"easy": 1, "med": 2, "hard": 3}


def seuil(maximum: int, pourcent: int) -> int:
    """⌈ maximum × pourcent / 100 ⌉. Exemple de Shadoaze : seuil(24, 75) = 18."""
    if not 1 <= pourcent <= 100:
        raise ValueError(f"pourcentage de seuil invalide : {pourcent} (attendu entre 1 et 100)")
    if maximum <= 0:
        return 0
    return (maximum * pourcent + 99) // 100
