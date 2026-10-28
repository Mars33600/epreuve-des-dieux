"""Petits textes du domaine : listes, dates en heure de Paris, pseudos."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
         "novembre", "décembre")
PSEUDO_MIN, PSEUDO_MAX = 2, 30


def liste_francaise(mots: list[str]) -> str:
    """["A", "B", "C"] -> « A, B et C »."""
    if len(mots) <= 1:
        return "".join(mots)
    return ", ".join(mots[:-1]) + " et " + mots[-1]


def date_paris(d: datetime) -> str:
    """« vendredi 13 novembre à 17 h », ou « … à 17 h 30 ». ValueError pour une date sans fuseau."""
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError(f"date sans fuseau : {d.isoformat()}")
    p = d.astimezone(PARIS)
    heure = f"{p.hour} h" + (f" {p.minute:02d}" if p.minute else "")
    return f"{_JOURS[p.weekday()]} {p.day} {_MOIS[p.month - 1]} à {heure}"


def valider_pseudo(pseudo: str) -> str:
    """Le pseudo nettoyé (espaces de bord retirés, espaces internes réduits à un seul).

    ValueError s'il fait moins de 2 ou plus de 30 caractères, ou s'il contient un caractère invisible.
    """
    nettoye = " ".join(pseudo.split())
    if not nettoye.isprintable():
        raise ValueError("le pseudo contient un caractère invisible")
    if not PSEUDO_MIN <= len(nettoye) <= PSEUDO_MAX:
        raise ValueError(f"le pseudo doit faire entre {PSEUDO_MIN} et {PSEUDO_MAX} caractères")
    return nettoye
