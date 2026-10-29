"""Le texte de l'histoire de Shadoaze, lu une fois depuis `contenu/histoire.md`.

Le fichier garde le texte à part du code : un bloc par paragraphe, séparés par une ligne vide, avec un
préfixe facultatif (« lead:: », « big:: », « quote:: », « final:: ») qui donne son rôle de mise en page.
Les lignes qui commencent par « # » sont des commentaires. Jinja échappe le texte au rendu.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

FICHIER = Path(__file__).parent / "contenu" / "histoire.md"
ROLES = ("lead", "big", "quote", "final")


@lru_cache(maxsize=1)
def paragraphes() -> tuple[tuple[str, str], ...]:
    """(rôle, texte) pour chaque bloc ; le rôle est « p » pour un paragraphe courant."""
    lignes = [ligne for ligne in FICHIER.read_text(encoding="utf-8").splitlines() if not ligne.startswith("#")]
    blocs = [b.strip() for b in "\n".join(lignes).split("\n\n") if b.strip()]
    sortie: list[tuple[str, str]] = []
    for bloc in blocs:
        role, sep, texte = bloc.partition("::")
        if sep and role.strip() in ROLES:
            sortie.append((role.strip(), texte.strip()))
        else:
            sortie.append(("p", bloc))
    return tuple(sortie)
