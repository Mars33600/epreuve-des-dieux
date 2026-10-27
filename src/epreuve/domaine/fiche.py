"""STUB B2 — remplacé par la version de B1 à l'intégration (interfaces figées de LOTS.md, lot B).

La fiche de quête (SPEC §4.4 bis).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace
from typing import Literal

from epreuve.domaine.modeles import Nature

SourceFiche = Literal["duffus", "duffus+dofusdb", "dofusdb"]


@dataclass(frozen=True)
class EtapeFiche:
    ordre: int
    titre: str
    texte_html: str
    objectifs: tuple[str, ...]


@dataclass(frozen=True)
class Position:
    libelle: str
    x: int
    y: int
    zone: str | None


@dataclass(frozen=True)
class Besoin:
    nom: str
    quantite: int
    icone_url: str | None


@dataclass(frozen=True)
class Prerequis:
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
    recompenses: tuple[str, ...]
    source: SourceFiche

    @property
    def complete(self) -> bool:
        return self.source != "dofusdb"


def masquer_prerequis_scelles(fiche: FicheQuete, etages_visibles: Collection[int],
                              etage_de_quete: Mapping[int, int]) -> FicheQuete:
    prerequis = []
    for p in fiche.prerequis:
        etage = etage_de_quete.get(p.quete_id) if p.quete_id is not None else None
        if p.statut == "scelle" or (etage is not None and etage not in etages_visibles):
            prerequis.append(Prerequis(None, None, "scelle"))
        else:
            prerequis.append(p)
    return replace(fiche, prerequis=tuple(prerequis))


def extraire_ids_discord(texte: str) -> list[int]:
    vus: list[int] = []
    for m in re.finditer(r"<@!?(\d{15,21})>|\b(\d{15,21})\b", texte):
        n = int(m.group(1) or m.group(2))
        if n not in vus:
            vus.append(n)
    return vus
