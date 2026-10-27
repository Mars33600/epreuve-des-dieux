"""Qui voit quoi : le brouillard sur les étages scellés (SPEC §4.3, EX-111).

Les gabarits ne reçoivent que le résultat de `etages_visibles` : un étage scellé n'y entre jamais pour
un non-admin, si bien qu'aucune page ne peut en laisser fuir le nom ou le contenu par mégarde.
"""

from __future__ import annotations

from collections.abc import Iterable

from epreuve.domaine.modeles import Etage

NB_SCELLES_DECORATIFS = 6  # constante d'affichage, jamais calculée (ne révèle pas le nombre d'étages)


def etages_visibles(etages: Iterable[Etage], est_admin: bool) -> list[Etage]:
    """Ouverts et terminés (admin : tous), triés par numéro."""
    return sorted((e for e in etages if est_admin or e.statut != "scelle"), key=lambda e: e.numero)


def etage_cochable(etage: Etage) -> bool:
    return etage.statut in ("ouvert", "termine")


def peut_modifier_coches(acteur_grimpeur_id: int | None, est_admin: bool, cible_grimpeur_id: int) -> bool:
    """Un grimpeur ne coche que pour lui-même ; un admin, pour n'importe qui (avec un motif, côté dépôt)."""
    return est_admin or (acteur_grimpeur_id is not None and acteur_grimpeur_id == cible_grimpeur_id)
