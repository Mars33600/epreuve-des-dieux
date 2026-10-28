"""Les calculs du module E1, purs (ni base ni réseau), repris des pages Archimonstres et Avis de recherche
de Duffus :

- un archimonstre (ou un boss) est **capturé** dès 1 exemplaire, et **complet** quand on en a autant que de
  personnages visés (1 à 8) ; la barre de progression compte les complets ;
- filtres : Tous / Capturés / Manquants, « n exemplaires ou + », recherche sans accents par nom ou zone ;
- tris : A–Z, par étape, par zone (aire → sous-zone ; un archi cité dans deux sous-zones apparaît dans les
  deux) ; pour les boss : par niveau, par étape, A–Z ;
- pierres d'âme à prévoir : chaque archi manquant demande, par personnage, la plus petite pierre qui capture
  jusqu'à son niveau maximum (petite ≤ 50, moyenne ≤ 100, grande ≤ 150, énorme ≤ 190) ;
- avis de recherche : tri par niveau, filtre par milice, « Émeraude » (niveau ≤ 120), capturé ou non,
  et la somme des avitons et alitons encore disponibles.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from epreuve.captures.catalogue import Archimonstre, AvisRecherche, Boss, normaliser

PERSONNAGES_MAX = 8
EXEMPLAIRES_MAX = 999
NIVEAU_EMERAUDE = 120
ZONE_INCONNUE = "Zone inconnue"
PIERRES: tuple[tuple[str, str, int], ...] = (
    ("petite", "Petite", 50), ("moyenne", "Moyenne", 100), ("grande", "Grande", 150), ("enorme", "Énorme", 190),
)  # fmt: skip

Etat = Literal["tous", "captures", "manquants"]
Genre = Literal["archi", "boss"]
TRIS_ARCHIS = ("alpha", "etape", "zone")
TRIS_BOSS = ("niveau", "etape", "alpha")


def borne_personnages(n: object) -> int:
    try:
        v = int(n)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1
    return max(1, min(PERSONNAGES_MAX, v))


def pourcentage(faits: int, total: int) -> int:
    return 0 if total <= 0 else min(100, round(faits / total * 100))


def cran(faits: int, total: int) -> int:
    """Le pourcentage par pas de 5 (classes CSS « p-45 » du site : pas de style en ligne)."""
    return 0 if total <= 0 else min(100, max(0, round(faits / total * 20) * 5))


def _cle_nom(x) -> str:
    return normaliser(x.nom)


# --- Archimonstres et boss -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Progression:
    faits: int
    total: int

    @property
    def pct(self) -> int:
        return pourcentage(self.faits, self.total)

    @property
    def cran(self) -> int:
        return cran(self.faits, self.total)

    @property
    def complet(self) -> bool:
        return self.total > 0 and self.faits >= self.total


def progression(items: Iterable[Archimonstre | Boss], nombres: Mapping[int, int], personnages: int) -> Progression:
    ids = {i.id for i in items}
    return Progression(sum(1 for i in ids if nombres.get(i, 0) >= personnages), len(ids))


def correspond(item: Archimonstre | Boss, recherche: str) -> bool:
    r = normaliser(recherche)
    if not r:
        return True
    return r in normaliser(item.nom) or any(r in normaliser(z.nom) for z in item.zones)


def filtrer(items: Iterable, nombres: Mapping[int, int], *, recherche: str = "", etat: str = "tous",
            minimum: int | None = None) -> list:
    sortie = []
    for i in items:
        n = nombres.get(i.id, 0)
        if not correspond(i, recherche):
            continue
        if (etat == "captures" and n == 0) or (etat == "manquants" and n > 0):
            continue
        if minimum is not None and n < minimum:
            continue
        sortie.append(i)
    return sortie


def trier(items: Iterable, tri: str) -> list:
    items = list(items)
    if tri == "etape":
        return sorted(items, key=lambda i: (i.etape if i.etape is not None else 10**6, _cle_nom(i)))
    if tri == "niveau":
        return sorted(items, key=lambda i: (i.niveau_max if i.niveau_max is not None else 10**6, _cle_nom(i)))
    return sorted(items, key=_cle_nom)


@dataclass
class Groupe:
    """Un volet : une étape, une aire ou une sous-zone, avec son compteur."""

    titre: str
    items: list = field(default_factory=list)
    sous: list[Groupe] = field(default_factory=list)
    faits: int = 0
    total: int = 0

    @property
    def pct(self) -> int:
        return pourcentage(self.faits, self.total)

    @property
    def complet(self) -> bool:
        return self.total > 0 and self.faits >= self.total


def _compter(g: Groupe, ids: set[int], nombres: Mapping[int, int], personnages: int) -> Groupe:
    g.total = len(ids)
    g.faits = sum(1 for i in ids if nombres.get(i, 0) >= personnages)
    return g


def par_etape(items: Sequence, nombres: Mapping[int, int], personnages: int) -> list[Groupe]:
    groupes: dict[int | None, list] = {}
    for i in trier(items, "etape"):
        groupes.setdefault(i.etape, []).append(i)
    sortie = []
    for etape, liste in sorted(groupes.items(), key=lambda kv: kv[0] if kv[0] is not None else 10**6):
        titre = f"Étape {etape}" if etape is not None else "Étape inconnue"
        sortie.append(_compter(Groupe(titre, liste), {i.id for i in liste}, nombres, personnages))
    return sortie


def par_zone(items: Sequence[Archimonstre], nombres: Mapping[int, int], personnages: int) -> list[Groupe]:
    """Aire → sous-zone → archis (A–Z). Les zones inconnues et les aires inconnues vont à la fin."""
    aires: dict[str, dict[str, list]] = {}
    for a in trier(items, "alpha"):
        for z in a.zones or ():
            aires.setdefault(z.aire or ZONE_INCONNUE, {}).setdefault(z.nom, []).append(a)
        if not a.zones:
            aires.setdefault(ZONE_INCONNUE, {}).setdefault(ZONE_INCONNUE, []).append(a)

    def cle(nom: str) -> tuple[int, str]:
        return (1 if nom == ZONE_INCONNUE else 0, normaliser(nom))

    sortie = []
    for aire in sorted(aires, key=cle):
        zones = aires[aire]
        sous = [_compter(Groupe(z, zones[z]), {a.id for a in zones[z]}, nombres, personnages)
                for z in sorted(zones, key=cle)]
        ids = {a.id for z in zones.values() for a in z}
        sortie.append(_compter(Groupe(aire, sous=sous), ids, nombres, personnages))
    return sortie


@dataclass(frozen=True)
class Pierre:
    cle: str
    nom: str
    cap: int
    a_prevoir: int
    total: int


@dataclass(frozen=True)
class Pierres:
    pierres: tuple[Pierre, ...]
    hors_bornes: int  # au-dessus du niveau 190 : il faudrait la Gigantesque

    @property
    def a_prevoir(self) -> int:
        return sum(p.a_prevoir for p in self.pierres)


def pierres_a_prevoir(items: Iterable[Archimonstre | Boss], nombres: Mapping[int, int], personnages: int) -> Pierres:
    a_prevoir = {cle: 0 for cle, _, _ in PIERRES}
    total = {cle: 0 for cle, _, _ in PIERRES}
    hors = 0
    for i in items:
        niveau = i.niveau_max
        if niveau is None:
            continue
        pierre = next((cle for cle, _, cap in PIERRES if niveau <= cap), None)
        if pierre is None:
            hors += 1
            continue
        total[pierre] += personnages
        a_prevoir[pierre] += max(0, personnages - nombres.get(i.id, 0))
    return Pierres(tuple(Pierre(cle, nom, cap, a_prevoir[cle], total[cle]) for cle, nom, cap in PIERRES), hors)


# --- Avis de recherche ------------------------------------------------------------------------------------


def milices(avis: Iterable[AvisRecherche]) -> list[str]:
    return sorted({a.milice for a in avis if a.milice}, key=normaliser)


def filtrer_avis(avis: Iterable[AvisRecherche], captures: set[int], *, recherche: str = "", milice: str = "",
                 etat: str = "tous", emeraude: bool = False) -> list[AvisRecherche]:
    r = normaliser(recherche)
    sortie = []
    for a in avis:
        if milice and a.milice != milice:
            continue
        if r and r not in normaliser(a.nom):
            continue
        if (etat == "captures" and a.id not in captures) or (etat == "manquants" and a.id in captures):
            continue
        if emeraude and a.niveau_tri > NIVEAU_EMERAUDE:
            continue
        sortie.append(a)
    return sorted(sortie, key=lambda a: (a.niveau_tri, normaliser(a.nom)))


def recompenses_disponibles(avis: Iterable[AvisRecherche], captures: set[int]) -> dict[str, int]:
    """Ce qu'il reste à gagner : la somme des récompenses des avis pas encore capturés."""
    reste = {"aviton": 0, "aliton": 0}
    for a in avis:
        if a.id not in captures and a.recompense:
            reste[a.recompense_type] += a.recompense
    return reste


# --- Entraide ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Personne:
    id: int
    pseudo: str
    classe: str | None
    nombre: int = 0


def qui_a(grimpeurs: Iterable, detenteurs: Mapping[int, int]) -> tuple[list[Personne], list[Personne]]:
    """(ceux qui l'ont, avec leur nombre d'exemplaires ; ceux qui ne l'ont pas), exclus écartés, A–Z."""
    ont, pas = [], []
    for g in sorted(grimpeurs, key=lambda g: normaliser(g.pseudo)):
        if g.statut == "exclu":
            continue
        n = detenteurs.get(g.id, 0)
        (ont if n > 0 else pas).append(Personne(g.id, g.pseudo, g.classe, n))
    return ont, pas
