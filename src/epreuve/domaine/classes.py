"""Les 19 classes de Dofus 3 et la répartition des grimpeurs entre elles.

La liste est recopiée une fois depuis `GET /breeds` de DofusDB, dans l'ordre du jeu.
Une nouvelle classe ajoutée au jeu demande une mise à jour ici : c'est voulu, la classe
d'un grimpeur est contrôlée contre cette liste (ici et dans la base).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # import réservé au typage, pour éviter un import circulaire avec modeles.py
    from collections.abc import Iterable

    from epreuve.domaine.modeles import Grimpeur

CLASSES: tuple[str, ...] = (
    "Féca", "Osamodas", "Enutrof", "Sram", "Xélor", "Ecaflip", "Eniripsa",
    "Iop", "Crâ", "Sadida", "Sacrieur", "Pandawa", "Roublard", "Zobal", "Steamer", "Eliotrope",
    "Huppermage", "Ouginak", "Forgelance",
)  # fmt: skip


@dataclass(frozen=True)
class RepartitionClasse:
    classe: str
    actifs: int
    en_pause: int


def repartition_classes(grimpeurs: Iterable[Grimpeur]) -> tuple[RepartitionClasse, ...]:
    """Pour chacune des 19 classes, dans l'ordre du jeu : combien d'actifs, combien en pause.

    Les classes à zéro sont gardées (c'est elles qui intéressent un nouveau venu).
    Les exclus sont ignorés.
    """
    actifs = dict.fromkeys(CLASSES, 0)
    en_pause = dict.fromkeys(CLASSES, 0)
    for g in grimpeurs:
        if g.statut == "actif":
            actifs[g.classe] += 1
        elif g.statut == "pause":
            en_pause[g.classe] += 1
    return tuple(RepartitionClasse(c, actifs[c], en_pause[c]) for c in CLASSES)
