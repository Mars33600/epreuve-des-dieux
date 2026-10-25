"""Fabrique de données de test : l'étage 0 selon les réponses de Shadoaze.

Contenus : 1 = succès 33 « Kardorim vaincu », 2 à 5 = les 4 autres succès du donjon,
6 = le lot « Toutes les quêtes d'Incarnam ». Paliers : 1 → {1}, 2 → {1..5}, 3 → {6}.
"""

from datetime import UTC, datetime, timedelta
from itertools import count
from zoneinfo import ZoneInfo

from epreuve.domaine.modeles import Contenu, Etage, Grimpeur, Palier, Validation

PARIS = ZoneInfo("Europe/Paris")
OUVERTURE = datetime(2026, 10, 30, 17, 0, tzinfo=PARIS).astimezone(UTC)
PLANCHER = datetime(2026, 11, 13, 17, 0, tzinfo=PARIS).astimezone(UTC)
AVANT = OUVERTURE - timedelta(days=2)  # inscription avant l'ouverture : compté
PENDANT = OUVERTURE + timedelta(days=3)  # un moment quelconque pendant l'étage

ETAGE0 = Etage(
    id=1, numero=0, nom="Le Seuil", level_cap=20, seuil_pourcent=75, statut="ouvert",
    ouvert_le=OUVERTURE, date_plancher_suivant=PLANCHER, zone_quetes="Incarnam",
    donjons_affiches=("Kardorim",),
)  # fmt: skip

CONTENUS = (
    Contenu(1, 1, "succes", "Crypte de Kardorim", "Kardorim vaincu"),
    Contenu(2, 1, "succes", "Kardorim (Duo)", "Kardorim (Duo)"),
    Contenu(3, 1, "succes", "Kardorim (Zombie)", "Kardorim (Zombie)"),
    Contenu(4, 1, "succes", "Kardorim (Premier)", "Kardorim (Premier)"),
    Contenu(5, 1, "succes", "Kardorim (Spécial)", "Kardorim (Spécial)"),
    Contenu(6, 1, "lot_quetes", "Toutes les quêtes d'Incarnam (24)", "Toutes les quêtes d'Incarnam"),
)
FULL_SUCCES = (1, 2, 3, 4, 5)
CHALLENGES = (2, 3, 4, 5)

PALIERS = (
    Palier(1, 1, 1, "Kardorim vaincu", frozenset({1})),
    Palier(2, 1, 2, "Kardorim full succès", frozenset(FULL_SUCCES)),
    Palier(3, 1, 3, "Toutes les quêtes d'Incarnam", frozenset({6})),
)


def grimpeur(id: int, statut: str = "actif", classe: str = "Iop", niveau: int | None = 20,
             difficulte: str = "easy", pseudo: str | None = None, retard: bool = False) -> Grimpeur:
    """Par défaut compté (inscrit et inclus avant l'ouverture). `retard=True` : retardataire."""
    inscrit = PENDANT if retard else AVANT
    return Grimpeur(id, pseudo or f"G{id}", classe, difficulte, statut, niveau, inscrit,
                    None if retard else inscrit)


_ids = count(1)


def validation(grimpeur_id: int, contenu_id: int, niveau: int | None = 20, statut: str = "acceptee",
               forcee: bool = False, realisee_le: datetime = PENDANT, source: str = "manuelle") -> Validation:
    return Validation(next(_ids), grimpeur_id, contenu_id, niveau, statut, forcee, source, realisee_le)


def faits(grimpeur_id: int, contenus=(1, 2, 3, 4, 5, 6), **kw) -> list[Validation]:
    """Les validations d'un grimpeur sur plusieurs contenus d'un coup (le lot 6 est déclaré)."""
    return [validation(grimpeur_id, c, **({"niveau": None, "source": "declaration"} if c == 6 else {}) | kw)
            for c in contenus]
