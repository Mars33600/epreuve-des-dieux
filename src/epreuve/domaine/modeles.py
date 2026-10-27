"""Les objets du domaine : des dataclasses figées, sans base de données ni Discord.

Tout le reste du projet (bot, site, base) parle avec ces objets. Ils sont figés
(`frozen=True`) : on ne modifie jamais un grimpeur « en place », on en fabrique un
nouveau. Ça évite qu'une fonction de calcul change une donnée par effet de bord.

Tous les `datetime` sont avec fuseau, en UTC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from epreuve.domaine.classes import CLASSES

Difficulte = Literal["easy", "med", "hard"]
Statut = Literal["actif", "pause", "exclu"]
StatutValid = Literal["acceptee", "refusee", "annulee"]
Source = Literal["manuelle", "ia_confirmee", "ia_corrigee", "declaration"]
StatutEtage = Literal["scelle", "ouvert", "termine"]

DIFFICULTES: tuple[str, ...] = ("easy", "med", "hard")
STATUTS: tuple[str, ...] = ("actif", "pause", "exclu")
TYPES_QUETES: tuple[str, ...] = ("quete", "lot_quetes")  # ce qui se déclare avec /quetes

# Ce que voit un humain : le règlement parle d'Aventuriers, d'Éclaireurs et de Collectionneurs.
NOM_DIFFICULTE: dict[str, str] = {"easy": "Aventurier", "med": "Éclaireur", "hard": "Collectionneur"}


@dataclass(frozen=True)
class Etage:
    id: int
    numero: int
    nom: str
    level_cap: int
    seuil_pourcent: int
    statut: StatutEtage
    ouvert_le: datetime | None
    date_plancher_suivant: datetime | None
    zone_quetes: str
    donjons_affiches: tuple[str, ...]
    chapitre_guide: str | None = None  # le chapitre du guide Duffus de cet étage (palier 3)


# Les étages de la tour sont les chapitres du guide Duffus : étage N = chapitre N.
URL_GUIDE_DUFFUS = "https://duffus.fr/guide-complet"


@dataclass(frozen=True)
class Palier:
    """Un palier de points (rang 1, 2 ou 3) et les contenus qu'il AJOUTE.

    Atteindre le palier k, c'est avoir fait tous les contenus des paliers 1 à k.
    """

    id: int
    etage_id: int
    rang: int
    libelle: str
    contenu_ids: frozenset[int]


@dataclass(frozen=True)
class Contenu:
    id: int
    etage_id: int
    type: str  # "succes", "quete", "lot_quetes" ou "autre"
    nom: str
    nom_court: str


@dataclass(frozen=True)
class Grimpeur:
    id: int
    pseudo: str
    classe: str
    difficulte: Difficulte
    statut: Statut
    niveau_connu: int | None  # sert à l'affichage et au contrôle du cap
    inscrit_le: datetime

    def __post_init__(self) -> None:
        # Le domaine refuse une classe inconnue : la base a la même règle (contrainte CHECK).
        if self.classe not in CLASSES:
            raise ValueError(f"classe inconnue : {self.classe!r}")
        if self.difficulte not in DIFFICULTES:
            raise ValueError(f"difficulté inconnue : {self.difficulte!r}")
        if self.statut not in STATUTS:
            raise ValueError(f"statut inconnu : {self.statut!r}")


@dataclass(frozen=True)
class Validation:
    id: int
    grimpeur_id: int
    contenu_id: int
    niveau: int | None  # vide pour une déclaration de quêtes
    statut: StatutValid
    forcee: bool  # acceptée par un admin malgré un dépassement de cap
    source: Source
    realisee_le: datetime


@dataclass(frozen=True)
class EntreeJournal:
    """Une ligne du journal. `details` est un petit dictionnaire libre (stocké en JSON)."""

    id: int
    horodatage: datetime
    type: str
    public: bool
    grimpeur_id: int | None = None
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Instantane:
    """Tout ce qu'il faut pour dessiner le site, lu en une fois.

    Le site ne sait pas d'où viennent les données : de la base en production,
    ou d'un jeu de démonstration en local. C'est ce qui permet de lancer la démo
    sans Postgres ni Discord.
    """

    etages: tuple[Etage, ...]
    paliers: tuple[Palier, ...]  # ceux de l'étage ouvert
    contenus: tuple[Contenu, ...]  # ceux de l'étage ouvert
    grimpeurs: tuple[Grimpeur, ...]
    validations: tuple[Validation, ...]
    journal_public: tuple[EntreeJournal, ...]  # du plus récent au plus ancien

    @property
    def etage_ouvert(self) -> Etage | None:
        return next((e for e in self.etages if e.statut == "ouvert"), None)


def liste_francaise(mots: list[str]) -> str:
    """["A", "B", "C"] -> « A, B et C »."""
    if len(mots) <= 1:
        return "".join(mots)
    return ", ".join(mots[:-1]) + " et " + mots[-1]


def phrase_validation(nb_grimpeurs: int, contenus: list[str], niveaux: list[int | None]) -> str:
    """La fin de phrase d'une entrée du fil, après les pseudos (que le site met en gras).

    - validation : « ont validé « Kardorim (Duo) » (niv. 20). »
    - déclaration (aucun niveau) : « a déclaré avoir terminé « Toutes les quêtes d'Incarnam ». »
    """
    titres = liste_francaise([f"« {c} »" for c in contenus])
    connus = [n for n in niveaux if n is not None]
    if not connus:
        verbe = "a déclaré" if nb_grimpeurs <= 1 else "ont déclaré"
        return f"{verbe} avoir terminé {titres}."
    verbe = "a validé" if nb_grimpeurs <= 1 else "ont validé"
    bas, haut = min(connus), max(connus)
    niv = f"niv. {bas}" if bas == haut else f"niv. {bas} à {haut}"
    return f"{verbe} {titres} ({niv})."
