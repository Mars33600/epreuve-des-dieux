"""Peut-on ouvrir l'étage suivant ? Et le bilan figé de l'étage qui se termine (SPEC §5.2, §5.5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from epreuve.domaine.bareme import EtatJauge
from epreuve.domaine.modeles import Categorie, Etage
from epreuve.domaine.textes import date_paris


@dataclass(frozen=True)
class Decision:
    ok: bool
    raisons: tuple[str, ...]  # lisibles, en français ; un admin peut forcer malgré elles


@dataclass(frozen=True)
class Bilan:
    fige_le: datetime
    actifs: int
    palier: int
    score: int
    points_par_categorie: dict[Categorie, int]
    force: bool
    motif: str | None


def peut_ouvrir(jauge: EtatJauge, en_cours: Etage, prochain: Etage | None, maintenant: datetime) -> Decision:
    """Ouvrable ⇔ l'étage en cours est ouvert, un étage scellé suit, la jauge est pleine et la date plancher
    est passée (à l'instant exact, c'est permis). Toutes les raisons de refus sont données, pas seulement la
    première."""
    raisons: list[str] = []
    if en_cours.statut != "ouvert":
        raisons.append("l'étage en cours n'est pas ouvert")
    if prochain is None or prochain.statut != "scelle":
        raisons.append("aucun étage préparé")
    if jauge.actifs == 0:
        raisons.append("aucun grimpeur actif")
    elif jauge.palier == 0:
        raisons.append("jauge : palier nul (étage sans catégorie), régler un palier manuel")
    elif not jauge.pleine:
        n = jauge.manquants
        raisons.append(f"jauge : il manque {n} point{'s' if n > 1 else ''}")
    plancher = en_cours.date_plancher_suivant
    if plancher is not None and maintenant < plancher:
        raisons.append(f"pas avant le {date_paris(plancher)}")
    return Decision(not raisons, tuple(raisons))


def bilan_etage(jauge: EtatJauge, maintenant: datetime, force: bool, motif: str | None) -> Bilan:
    """Le bilan figé à l'ouverture de l'étage suivant. ValueError si force et motif vide."""
    motif = (motif or "").strip() or None
    if force and motif is None:
        raise ValueError("une ouverture forcée exige un motif")
    return Bilan(maintenant, jauge.actifs, jauge.palier, jauge.score, dict(jauge.points_par_categorie), force, motif)
