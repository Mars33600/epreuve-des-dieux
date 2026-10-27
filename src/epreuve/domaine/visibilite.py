"""STUB B2 — remplacé par la version de B1 à l'intégration (interfaces figées de LOTS.md, lot B)."""

from __future__ import annotations

from collections.abc import Iterable

from epreuve.domaine.modeles import Etage

NB_SCELLES_DECORATIFS = 6


def etages_visibles(etages: Iterable[Etage], est_admin: bool) -> list[Etage]:
    return sorted((e for e in etages if est_admin or e.statut in ("ouvert", "termine")), key=lambda e: e.numero)


def etage_cochable(etage: Etage) -> bool:
    return etage.statut in ("ouvert", "termine")


def peut_modifier_coches(acteur_grimpeur_id: int | None, est_admin: bool, cible_grimpeur_id: int) -> bool:
    return est_admin or (acteur_grimpeur_id is not None and acteur_grimpeur_id == cible_grimpeur_id)
