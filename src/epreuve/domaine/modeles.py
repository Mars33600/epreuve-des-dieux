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
TypeElement = Literal["case", "quete", "bloc"]


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


# Une règle qui change d'un combat à l'autre (le monstre à viser est choisi par le jeu) est écrite en deux
# temps dans `condition` : la règle, puis ce marqueur, puis l'explication. Pas de colonne en plus.
MARQUE_ALEATOIRE = " Aléatoire : "


@dataclass(frozen=True)
class CaseSucces:
    id: int
    donjon_id: int
    ordre: int
    nom: str
    condition: str
    est_classique: bool
    masquee: bool = False

    @property
    def regle(self) -> str:
        """La règle à afficher, sans l'explication « aléatoire »."""
        return self.condition.partition(MARQUE_ALEATOIRE)[0]

    @property
    def explication_aleatoire(self) -> str | None:
        """Pourquoi la règle change d'un combat à l'autre ; None si la règle est fixe."""
        _, marque, suite = self.condition.partition(MARQUE_ALEATOIRE)
        return suite if marque else None


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
class Bloc:
    """Un bloc du guide Duffus pour une tranche (SPEC v5 §3 et §5) : l'unité que le grimpeur coche.

    `nature` : « principale » si le bloc contient au moins une quête principale, sinon « secondaire »,
    sauf correction d'un admin (`nature_origine == "admin"`, qui prime sur la règle)."""

    id: int
    etage_id: int
    titre: str
    numero: int | None  # rang du bloc dans tout le guide Duffus (« Bloc 7 »), None si inconnu
    ordre: int  # position dans la tranche
    nature: Nature
    nature_origine: Literal["construction", "admin"]
    nb_quetes: int
    nb_principales: int
    duffus_url: str | None = None
    duffus_ancre: str | None = None
    nature_motif: str | None = None
    masque: bool = False

    @property
    def nature_par_defaut(self) -> Nature:
        return "principale" if self.nb_principales > 0 else "secondaire"

    @property
    def titre_complet(self) -> str:
        """« Bloc 7 · Début des quêtes d'alignement » (sans numéro : le titre seul)."""
        return f"Bloc {self.numero} · {self.titre}" if self.numero is not None else self.titre

    @property
    def lien_duffus(self) -> str | None:
        if not self.duffus_url:
            return None
        return f"{self.duffus_url}#{self.duffus_ancre}" if self.duffus_ancre else self.duffus_url


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
    quetes: frozenset[int] = frozenset()  # ancien suivi par quête : ne compte plus au barème (SPEC v5 §4)
    blocs: frozenset[int] = frozenset()

    def contient(self, ref: ElementRef) -> bool:
        return ref.id in {"case": self.cases, "bloc": self.blocs}.get(ref.type, self.quetes)


@dataclass(frozen=True)
class ContenuEtage:
    """Le contenu VISIBLE d'un étage : rien de masqué. Une case d'un donjon masqué est exclue."""

    etage: Etage
    donjons: tuple[Donjon, ...]
    cases: tuple[CaseSucces, ...]
    quetes: tuple[Quete, ...]
    blocs: tuple[Bloc, ...] = ()

    @staticmethod
    def visible(etage: Etage, donjons: Iterable[Donjon], cases: Iterable[CaseSucces],
                quetes: Iterable[Quete], blocs: Iterable[Bloc] = ()) -> ContenuEtage:
        ds = tuple(sorted((d for d in donjons if not d.masque), key=lambda d: (d.ordre, d.id)))
        ids = {d.id for d in ds}
        cs = tuple(sorted((c for c in cases if not c.masquee and c.donjon_id in ids),
                          key=lambda c: (c.donjon_id, c.ordre, c.id)))
        qs = tuple(sorted((q for q in quetes if not q.masquee), key=lambda q: (q.ordre, q.id)))
        bs = tuple(sorted((b for b in blocs if not b.masque), key=lambda b: (b.ordre, b.id)))
        return ContenuEtage(etage, ds, cs, qs, bs)

    def cases_du_donjon(self, donjon_id: int) -> tuple[CaseSucces, ...]:
        """Triées par ordre (la case classique, « Vaincre le boss », vient en premier)."""
        return tuple(c for c in self.cases if c.donjon_id == donjon_id)

    def elements(self) -> tuple[ElementRef, ...]:
        """Ce que les grimpeurs cochent : les cases de donjon et les blocs du guide (plus les quêtes une par une)."""
        return (tuple(ElementRef("case", c.id) for c in self.cases)
                + tuple(ElementRef("bloc", b.id) for b in self.blocs))

    def blocs_de_nature(self, nature: Nature) -> tuple[Bloc, ...]:
        return tuple(b for b in self.blocs if b.nature == nature)
