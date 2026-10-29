"""La fiche de quête (SPEC §4.4 bis), exigence forte de Marceau : la parité avec la fiche de duffus.fr.

La fiche est recopiée à la construction de l'étage et rangée en base ; le domaine ne fait que la décrire et
cacher ce qui ne doit pas sortir : un prérequis d'un étage scellé n'expose ni son nom ni son id (EX-111).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace
from typing import Literal

from epreuve.domaine.modeles import Nature

SourceFiche = Literal["duffus", "duffus+dofusdb", "dofusdb"]


@dataclass(frozen=True)
class Position:
    libelle: str  # « PNJ Ganymède »
    x: int
    y: int
    zone: str | None = None  # « Incarnam »


@dataclass(frozen=True)
class LigneEtape:
    """Un objectif détaillé d'une étape : ce qu'il faut faire, où, quoi et combien. Tout ce que la source ne
    donne pas reste vide."""

    genre: str  # « monstre », « objet », « pnj » ou « texte »
    texte: str = ""  # la phrase de l'objectif quand la source en donne une
    nom: str | None = None  # le monstre, l'objet ou le PNJ visé
    quantite: int | None = None
    x: int | None = None
    y: int | None = None


@dataclass(frozen=True)
class EtapeFiche:
    ordre: int
    titre: str
    texte_html: str  # déjà nettoyé par contenu.construire.nettoyer_fiche
    objectifs: tuple[str, ...] = ()
    lieux: tuple[Position, ...] = ()  # les positions [x,y] de l'étape, dans l'ordre
    lignes: tuple[LigneEtape, ...] = ()  # les objectifs détaillés (monstres, objets, PNJ avec quantités)


@dataclass(frozen=True)
class Besoin:
    """Un objet nécessaire, ou un monstre à vaincre."""

    nom: str
    quantite: int
    icone_url: str | None = None


@dataclass(frozen=True)
class Prerequis:
    """visible : étage ouvert ou terminé → lien vers sa fiche ; scelle : nom ET id à None (EX-111) ;
    hors_guide : nom seul, sans lien."""

    quete_id: int | None
    nom: str | None
    statut: Literal["visible", "scelle", "hors_guide"]


@dataclass(frozen=True)
class FicheQuete:
    quete_id: int
    etage_numero: int
    nom: str
    niveau: int | None
    bloc: str
    nature: Nature
    dofus: tuple[str, ...]
    jusqu_ou: str | None
    a_lier: str | None
    prerequis: tuple[Prerequis, ...]
    etapes: tuple[EtapeFiche, ...]
    objets: tuple[Besoin, ...]
    monstres: tuple[Besoin, ...]
    positions: tuple[Position, ...]
    succes_lie: str | None
    recompenses: tuple[str, ...]  # « 1 200 XP », « 300 kamas », « Émote … »
    source: SourceFiche
    pnj_depart_connu: str | None = None  # le PNJ de départ quand la source le donne sans position
    infos_rapides: tuple[str, ...] = ()  # « Combats en groupe ×2 », « Donjon : … » (vide pour une fiche DofusDB)

    @property
    def depart(self) -> Position | None:
        """L'emplacement de départ : la première position, quand elle est le départ (« Départ : <PNJ> »)."""
        premiere = self.positions[0] if self.positions else None
        return premiere if premiere and premiere.libelle.startswith("Départ") else None

    @property
    def pnj_depart(self) -> str | None:
        d = self.depart
        if d and d.libelle.startswith("Départ : "):
            return d.libelle[len("Départ : "):]
        return self.pnj_depart_connu

    @property
    def complete(self) -> bool:
        """Vrai si la fiche a un vrai contenu : Duffus, ou DofusDB avec ses étapes (sinon : « Fiche détaillée
        indisponible »)."""
        return self.source != "dofusdb" or bool(self.etapes)


SCELLE = Prerequis(None, None, "scelle")


def masquer_prerequis_scelles(fiche: FicheQuete, etages_visibles: Collection[int],
                              etage_de_quete: Mapping[int, int]) -> FicheQuete:
    """Remplace chaque prérequis d'un étage non visible par Prerequis(None, None, "scelle").

    `etages_visibles` : numéros des étages visibles ; `etage_de_quete` : id de quête → numéro d'étage.
    Un prérequis qui pointe vers une quête d'étage inconnu est traité comme scellé (prudence). Toujours
    appelée avant de rendre une fiche à un non-admin : la page et le fragment n'ont aucun autre chemin.
    """

    def filtre(p: Prerequis) -> Prerequis:
        if p.statut == "scelle":
            return SCELLE
        if p.quete_id is not None and etage_de_quete.get(p.quete_id) not in etages_visibles:
            return SCELLE
        return p

    return replace(fiche, prerequis=tuple(filtre(p) for p in fiche.prerequis))


def extraire_ids_discord(texte: str) -> list[int]:
    """« <@123> <@!456> 789 » → [123, 456, 789] : chaque nombre du texte, dans l'ordre, sans doublon."""
    return list(dict.fromkeys(int(n) for n in re.findall(r"\d+", texte)))
