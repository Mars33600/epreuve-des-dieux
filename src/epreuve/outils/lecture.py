"""Lecture des données des outils (JSON versionné, voir aspirer.py) : chargées une fois, gardées en mémoire."""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from pathlib import Path

DONNEES = Path(__file__).parent / "donnees"
PUBLIQUES = ("craft", "montures")  # servies telles quelles au navigateur (les outils en JS les lisent)


def fichier(nom: str) -> Path:
    return DONNEES / f"{nom}.json"


@cache
def charger(nom: str):
    return json.loads(fichier(nom).read_text(encoding="utf-8"))


def offrande(jour: date) -> dict | None:
    """L'offrande de l'Almanax d'un jour, ou None hors des dates connues."""
    ligne = charger("almanax").get(jour.isoformat())
    if ligne is None:
        return None
    objet, quantite, type_bonus, bonus, kamas, ratio_xp, niveau = ligne
    return {"jour": jour, "objet": objet, "quantite": quantite, "type_bonus": type_bonus, "bonus": bonus,
            "kamas": kamas, "ratio_xp": ratio_xp, "niveau": niveau}


def bornes_almanax() -> tuple[date, date]:
    jours = sorted(charger("almanax"))
    return date.fromisoformat(jours[0]), date.fromisoformat(jours[-1])


def classes() -> list[dict]:
    return charger("classes")
