"""STUB B2 — remplacé par la version de B1 à l'intégration (interfaces figées de LOTS.md, lot B).

Les objets du domaine : des dataclasses figées, sans base de données ni Discord.
Toutes les dates portent un fuseau (UTC).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from typing import Literal

from epreuve.domaine.classes import CLASSES

Categorie = Literal["donjons", "full_succes", "principales", "secondaires"]
CATEGORIES: tuple[Categorie, ...] = ("donjons", "full_succes", "principales", "secondaires")
NOM_CATEGORIE: dict[Categorie, str] = {"donjons": "Donjons", "full_succes": "Full succès",
                                       "principales": "Quêtes principales", "secondaires": "Quêtes secondaires"}
Statut = Literal["actif", "pause", "exclu"]
StatutEtage = Literal["scelle", "ouvert", "termine"]
Nature = Literal["principale", "secondaire"]
OrigineNature = Literal["duffus", "dofusdb", "admin"]
TypeElement = Literal["case", "quete"]
STATUTS: tuple[str, ...] = ("actif", "pause", "exclu")


@dataclass(frozen=True)
class Etage:
    id: int
    numero: int
    nom: str
    niveau_min: int
    niveau_max: int
    level_cap: int
    statut: StatutEtage
    ouvert_le: datetime | None
    date_plancher_suivant: datetime | None
    palier_manuel: int | None
    ambiance_url: str | None


@dataclass(frozen=True)
class Donjon:
    id: int
    etage_id: int
    nom: str
    niveau: int | None
    ordre: int
    bloc: str | None
    dofusdb_id: int | None
    origine: Literal["propose", "admin"]
    succes_source: Literal["duffus", "dofusdb"]
    masque: bool


@dataclass(frozen=True)
class CaseSucces:
    id: int
    donjon_id: int
    ordre: int
    nom: str
    condition: str
    est_classique: bool
    masquee: bool


@dataclass(frozen=True)
class Quete:
    id: int
    etage_id: int
    nom: str
    niveau: int | None
    bloc: str
    ordre: int
    nature: Nature
    nature_origine: OrigineNature
    dofus: tuple[str, ...]
    jusqu_ou: str | None
    a_lier: str | None
    a_une_fiche: bool
    masquee: bool


@dataclass(frozen=True)
class Grimpeur:
    id: int
    discord_user_id: int
    nom_discord: str
    pseudo: str
    classe: str | None
    statut: Statut
    niveau_declare: int | None
    inscrit_le: datetime

    def __post_init__(self) -> None:
        if self.classe is not None and self.classe not in CLASSES:
            raise ValueError(f"classe inconnue : {self.classe!r}")
        if self.statut not in STATUTS:
            raise ValueError(f"statut inconnu : {self.statut!r}")


@dataclass(frozen=True)
class EntreeJournal:
    id: int
    horodatage: datetime
    acteur_discord_id: int | None
    type: str
    grimpeur_id: int | None
    etage_id: int | None
    details: Mapping[str, object]
    public: bool


@dataclass(frozen=True)
class Session:
    discord_user_id: int
    nom_discord: str
    est_admin: bool
    roles_verifies_le: datetime
    expire_le: datetime
    jeton_oauth: str
    csrf: str


@dataclass(frozen=True)
class Regles:
    points_par_joueur: Fraction = Fraction(2)
    categorie_vide: Literal["ignoree", "offerte"] = "ignoree"
    succes_coche_vaincu: bool = True
    pause_peut_cocher: bool = True
    classe_obligatoire: bool = False
    afficher_nom_discord: bool = True
    liste_officielle_obligatoire: bool = True
    verrouiller_modules_par_etage: bool = False


@dataclass(frozen=True)
class ElementRef:
    type: TypeElement
    id: int


@dataclass(frozen=True)
class Coches:
    grimpeur_id: int
    cases: frozenset[int] = field(default_factory=frozenset)
    quetes: frozenset[int] = field(default_factory=frozenset)

    def contient(self, ref: ElementRef) -> bool:
        return ref.id in (self.cases if ref.type == "case" else self.quetes)


@dataclass(frozen=True)
class ContenuEtage:
    """Le contenu VISIBLE d'un étage : rien de masqué. Une case d'un donjon masqué est exclue."""

    etage: Etage
    donjons: tuple[Donjon, ...]
    cases: tuple[CaseSucces, ...]
    quetes: tuple[Quete, ...]

    @staticmethod
    def visible(etage: Etage, donjons: Iterable[Donjon], cases: Iterable[CaseSucces],
                quetes: Iterable[Quete]) -> ContenuEtage:
        djs = tuple(sorted((d for d in donjons if not d.masque), key=lambda d: d.ordre))
        ids = {d.id for d in djs}
        cs = tuple(sorted((c for c in cases if not c.masquee and c.donjon_id in ids),
                          key=lambda c: (c.donjon_id, c.ordre)))
        qs = tuple(sorted((q for q in quetes if not q.masquee), key=lambda q: q.ordre))
        return ContenuEtage(etage, djs, cs, qs)

    def cases_du_donjon(self, donjon_id: int) -> tuple[CaseSucces, ...]:
        return tuple(sorted((c for c in self.cases if c.donjon_id == donjon_id), key=lambda c: c.ordre))

    def elements(self) -> tuple[ElementRef, ...]:
        return (tuple(ElementRef("case", c.id) for c in self.cases)
                + tuple(ElementRef("quete", q.id) for q in self.quetes))
