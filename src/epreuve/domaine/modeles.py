"""Les objets du domaine : des dataclasses figées, sans base de données ni Discord.

Tout le reste du projet (site, base, construction des étages) parle avec ces objets. Ils sont figés
(`frozen=True`) : on ne modifie jamais un grimpeur « en place », on en fabrique un nouveau. Une fonction
de calcul ne peut donc pas changer une donnée par effet de bord.

Tous les `datetime` portent un fuseau, en UTC. Signatures figées : docs/LOTS.md, lot B.
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
NOM_CATEGORIE: dict[Categorie, str] = {
    "donjons": "Donjons", "full_succes": "Full succès",
    "principales": "Quêtes principales", "secondaires": "Quêtes secondaires",
}  # fmt: skip
Statut = Literal["actif", "pause", "exclu"]
STATUTS: tuple[Statut, ...] = ("actif", "pause", "exclu")
StatutEtage = Literal["scelle", "ouvert", "termine"]
Nature = Literal["principale", "secondaire"]
OrigineNature = Literal["duffus", "dofusdb", "admin"]
TypeElement = Literal["case", "quete"]


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
    palier_manuel: int | None = None
    ambiance_url: str | None = None  # aucun lien vers duffus.fr (EX-70)


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
    masque: bool = False


@dataclass(frozen=True)
class CaseSucces:
    id: int
    donjon_id: int
    ordre: int
    nom: str
    condition: str
    est_classique: bool
    masquee: bool = False


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
    a_une_fiche: bool  # la fiche elle-même se lit à part (FicheQuete)
    masquee: bool = False
    source_fiche: str | None = None  # « duffus », « dofusdb » ou None (revue admin)


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
    prologue_vu: bool = False  # a passé le prologue plein écran de la première connexion

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
    """Jamais transmise à un gabarit : elle porte le jeton OAuth et le jeton CSRF."""

    discord_user_id: int
    nom_discord: str
    est_admin: bool
    roles_verifies_le: datetime
    expire_le: datetime
    jeton_oauth: str = field(repr=False)
    csrf: str = field(repr=False)


@dataclass(frozen=True)
class Regles:
    """Les règles de jeu, lues depuis config/regles.yaml (SPEC §8.1) par `epreuve.regles`.

    Les valeurs par défaut sont les réponses par défaut d'EXIGENCES. Le domaine ne lit jamais de
    fichier : les règles lui sont passées en paramètre.
    """

    points_par_joueur: Fraction = Fraction(2)  # palier = ⌈ m × N × K ÷ 4 ⌉ (EX-09, EX-109)
    categorie_vide: Literal["ignoree", "offerte"] = "ignoree"  # T-11
    succes_coche_vaincu: bool = True  # T-16
    pause_peut_cocher: bool = True  # T-13
    classe_obligatoire: bool = False  # T-20
    afficher_nom_discord: bool = True  # T-20
    liste_officielle_obligatoire: bool = True  # T-19
    verrouiller_modules_par_etage: bool = False  # T-08 (lot E)


@dataclass(frozen=True)
class ElementRef:
    type: TypeElement
    id: int


@dataclass(frozen=True)
class Coches:
    grimpeur_id: int
    cases: frozenset[int] = frozenset()
    quetes: frozenset[int] = frozenset()

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
        ds = tuple(sorted((d for d in donjons if not d.masque), key=lambda d: (d.ordre, d.id)))
        ids = {d.id for d in ds}
        cs = tuple(sorted((c for c in cases if not c.masquee and c.donjon_id in ids),
                          key=lambda c: (c.donjon_id, c.ordre, c.id)))
        qs = tuple(sorted((q for q in quetes if not q.masquee), key=lambda q: (q.ordre, q.id)))
        return ContenuEtage(etage, ds, cs, qs)

    def cases_du_donjon(self, donjon_id: int) -> tuple[CaseSucces, ...]:
        """Triées par ordre (la case classique, « Vaincre le boss », vient en premier)."""
        return tuple(c for c in self.cases if c.donjon_id == donjon_id)

    def elements(self) -> tuple[ElementRef, ...]:
        return (tuple(ElementRef("case", c.id) for c in self.cases)
                + tuple(ElementRef("quete", q.id) for q in self.quetes))
