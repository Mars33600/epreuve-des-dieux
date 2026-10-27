"""STUB B2 — remplacé par la version de B1 à l'intégration (interfaces figées de LOTS.md, lot B)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")


def liste_francaise(mots: list[str]) -> str:
    if len(mots) <= 1:
        return "".join(mots)
    return ", ".join(mots[:-1]) + " et " + mots[-1]


def date_paris(d: datetime) -> str:
    """« vendredi 13 novembre à 17 h »."""
    p = d.astimezone(PARIS)
    heure = f"{p.hour} h" + (f" {p.minute:02d}" if p.minute else "")
    jour = "1er" if p.day == 1 else str(p.day)
    return f"{JOURS[p.weekday()]} {jour} {MOIS[p.month - 1]} à {heure}"


def valider_pseudo(pseudo: str) -> str:
    nettoye = " ".join(pseudo.split())
    if not 2 <= len(nettoye) <= 30:
        raise ValueError("Le pseudo doit faire entre 2 et 30 caractères.")
    return nettoye
