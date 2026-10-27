"""STUB B2 — remplacé par la version de B1 à l'intégration (interfaces figées de LOTS.md, lot B)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from epreuve.domaine.bareme import categories_grimpeur, points_grimpeur
from epreuve.domaine.modeles import Categorie, Coches, ContenuEtage, ElementRef, Grimpeur, Regles


def _actifs(grimpeurs: Iterable[Grimpeur]) -> list[Grimpeur]:
    return sorted((g for g in grimpeurs if g.statut == "actif"), key=lambda g: g.pseudo.casefold())


def compteurs(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur],
              coches: Mapping[int, Coches]) -> dict[ElementRef, int]:
    actifs = _actifs(grimpeurs)
    return {ref: sum(coches.get(g.id, Coches(g.id)).contient(ref) for g in actifs) for ref in contenu.elements()}


def qui(element: ElementRef, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
        fait: bool) -> list[Grimpeur]:
    return [g for g in _actifs(grimpeurs) if coches.get(g.id, Coches(g.id)).contient(element) == fait]


def qui_categorie(contenu: ContenuEtage, categorie: Categorie, grimpeurs: Iterable[Grimpeur],
                  coches: Mapping[int, Coches], fait: bool) -> list[Grimpeur]:
    return [g for g in _actifs(grimpeurs)
            if categories_grimpeur(contenu, coches.get(g.id, Coches(g.id)))[categorie].acquise == fait]


def avancement(contenu: ContenuEtage, coches: Coches) -> tuple[int, int]:
    refs = contenu.elements()
    return sum(coches.contient(r) for r in refs), len(refs)


def moins_avance(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
                 regles: Regles) -> Grimpeur | None:
    actifs = _actifs(grimpeurs)
    if not actifs:
        return None

    def cle(g: Grimpeur):
        c = coches.get(g.id, Coches(g.id))
        return points_grimpeur(contenu, c, regles), avancement(contenu, c)[0], g.pseudo.casefold()

    return min(actifs, key=cle)
