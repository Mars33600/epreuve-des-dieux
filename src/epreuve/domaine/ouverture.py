"""STUB B2 — remplacé par la version de B1 à l'intégration (interfaces figées de LOTS.md, lot B)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from epreuve.domaine.bareme import EtatJauge
from epreuve.domaine.modeles import Categorie, Etage
from epreuve.domaine.textes import date_paris


@dataclass(frozen=True)
class Decision:
    ok: bool
    raisons: tuple[str, ...]


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
    raisons: list[str] = []
    if en_cours.statut != "ouvert":
        raisons.append("l'étage en cours n'est pas ouvert")
    if prochain is None:
        raisons.append("aucun étage préparé")
    if jauge.actifs == 0:
        raisons.append("aucun grimpeur actif")
    elif not jauge.pleine:
        raisons.append(f"jauge : il manque {jauge.manquants} points")
    if en_cours.date_plancher_suivant is not None and maintenant < en_cours.date_plancher_suivant:
        raisons.append(f"pas avant le {date_paris(en_cours.date_plancher_suivant)}")
    return Decision(not raisons, tuple(raisons))


def bilan_etage(jauge: EtatJauge, maintenant: datetime, force: bool, motif: str | None) -> Bilan:
    if force and not (motif or "").strip():
        raise ValueError("un motif est obligatoire pour forcer l'ouverture")
    return Bilan(maintenant, jauge.actifs, jauge.palier, jauge.score, dict(jauge.points_par_categorie), force, motif)
