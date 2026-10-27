"""Où en est chacun : les compteurs « 7/12 », « qui ne l'a pas fait ? » et l'avancement (SPEC §4.6).

Seuls les grimpeurs ACTIFS comptent : un compteur et sa liste « qui ne l'a pas fait ? » sont donc toujours
cohérents (compteur + pas faits = nombre d'actifs).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from epreuve.domaine.bareme import categories_grimpeur, points_grimpeur
from epreuve.domaine.modeles import Categorie, Coches, ContenuEtage, ElementRef, Grimpeur, Regles


def _actifs(grimpeurs: Iterable[Grimpeur]) -> list[Grimpeur]:
    return [g for g in grimpeurs if g.statut == "actif"]


def _coches(coches: Mapping[int, Coches], g: Grimpeur) -> Coches:
    return coches.get(g.id, Coches(g.id))


def _par_pseudo(grimpeurs: Iterable[Grimpeur]) -> list[Grimpeur]:
    return sorted(grimpeurs, key=lambda g: (g.pseudo.casefold(), g.id))


def compteurs(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur],
              coches: Mapping[int, Coches]) -> dict[ElementRef, int]:
    """Pour chaque élément visible : le nombre d'ACTIFS qui l'ont coché."""
    actifs = [_coches(coches, g) for g in _actifs(grimpeurs)]
    return {ref: sum(1 for c in actifs if c.contient(ref)) for ref in contenu.elements()}


def qui(element: ElementRef, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
        fait: bool) -> list[Grimpeur]:
    """Les actifs qui ont (fait=True) ou n'ont pas (fait=False) coché l'élément, triés par pseudo."""
    return _par_pseudo(g for g in _actifs(grimpeurs) if _coches(coches, g).contient(element) == fait)


def qui_categorie(contenu: ContenuEtage, categorie: Categorie, grimpeurs: Iterable[Grimpeur],
                  coches: Mapping[int, Coches], fait: bool) -> list[Grimpeur]:
    """« fait » = a le point de la catégorie ; actifs seulement, triés par pseudo."""
    return _par_pseudo(g for g in _actifs(grimpeurs)
                       if categories_grimpeur(contenu, _coches(coches, g))[categorie].acquise == fait)


def avancement(contenu: ContenuEtage, coches: Coches) -> tuple[int, int]:
    """(éléments visibles cochés, total des éléments visibles)."""
    elements = contenu.elements()
    return sum(1 for e in elements if coches.contient(e)), len(elements)


def moins_avance(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
                 regles: Regles) -> Grimpeur | None:
    """Parmi les actifs : le moins de points, puis le moins de cochés, puis le pseudo. None sans actif."""

    def cle(g: Grimpeur) -> tuple[int, int, str, int]:
        c = _coches(coches, g)
        return points_grimpeur(contenu, c, regles), avancement(contenu, c)[0], g.pseudo.casefold(), g.id

    return min(_actifs(grimpeurs), key=cle, default=None)
