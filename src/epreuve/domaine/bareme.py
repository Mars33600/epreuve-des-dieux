"""STUB B2 — remplacé par la version de B1 à l'intégration (interfaces figées de LOTS.md, lot B).

Catégories, points, palier et jauge. Calcul exact avec Fraction (pas de flottants).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from epreuve.domaine.modeles import (
    CATEGORIES,
    Categorie,
    Coches,
    ContenuEtage,
    ElementRef,
    Grimpeur,
    Regles,
)


@dataclass(frozen=True)
class EtatCategorie:
    categorie: Categorie
    faits: int
    total: int

    @property
    def acquise(self) -> bool:
        return self.total > 0 and self.faits == self.total

    @property
    def vide(self) -> bool:
        return self.total == 0


def _cases_classiques(contenu: ContenuEtage) -> list[int]:
    return [c.id for c in contenu.cases if c.est_classique]


def categories_grimpeur(contenu: ContenuEtage, coches: Coches) -> dict[Categorie, EtatCategorie]:
    classiques = _cases_classiques(contenu)
    toutes = [c.id for c in contenu.cases]
    princ = [q.id for q in contenu.quetes if q.nature == "principale"]
    second = [q.id for q in contenu.quetes if q.nature == "secondaire"]
    return {
        "donjons": EtatCategorie("donjons", sum(i in coches.cases for i in classiques), len(classiques)),
        "full_succes": EtatCategorie("full_succes", sum(i in coches.cases for i in toutes), len(toutes)),
        "principales": EtatCategorie("principales", sum(i in coches.quetes for i in princ), len(princ)),
        "secondaires": EtatCategorie("secondaires", sum(i in coches.quetes for i in second), len(second)),
    }


def _point(etat: EtatCategorie, regles: Regles) -> bool:
    return etat.acquise or (etat.vide and regles.categorie_vide == "offerte")


def points_grimpeur(contenu: ContenuEtage, coches: Coches, regles: Regles) -> int:
    return sum(_point(e, regles) for e in categories_grimpeur(contenu, coches).values())


def categories_comptees(contenu: ContenuEtage, regles: Regles) -> int:
    if regles.categorie_vide == "offerte":
        return 4
    vide = Coches(0)
    return sum(not e.vide for e in categories_grimpeur(contenu, vide).values())


def palier(nb_actifs: int, nb_categories: int, regles: Regles, palier_manuel: int | None = None) -> int:
    if palier_manuel is not None:
        return palier_manuel
    if nb_actifs < 0 or nb_categories < 0 or nb_categories > 4:
        raise ValueError("entrées du palier invalides")
    return math.ceil(Fraction(regles.points_par_joueur) * nb_actifs * nb_categories / 4)


@dataclass(frozen=True)
class EtatJauge:
    score: int
    palier: int
    palier_manuel: bool
    actifs: int
    en_pause: int
    nb_categories: int
    points_par_categorie: dict[Categorie, int]

    @property
    def pleine(self) -> bool:
        return self.actifs > 0 and self.palier > 0 and self.score >= self.palier

    @property
    def maximum(self) -> int:
        return self.nb_categories * self.actifs

    @property
    def manquants(self) -> int:
        return max(0, self.palier - self.score)


def calculer_jauge(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur],
                   coches: Mapping[int, Coches], regles: Regles) -> EtatJauge:
    gs = list(grimpeurs)
    actifs = [g for g in gs if g.statut == "actif"]
    par_cat: dict[Categorie, int] = dict.fromkeys(CATEGORIES, 0)
    for g in actifs:
        for cat, etat in categories_grimpeur(contenu, coches.get(g.id, Coches(g.id))).items():
            par_cat[cat] += _point(etat, regles)
    k = categories_comptees(contenu, regles)
    manuel = contenu.etage.palier_manuel
    return EtatJauge(score=sum(par_cat.values()), palier=palier(len(actifs), k, regles, manuel),
                     palier_manuel=manuel is not None, actifs=len(actifs),
                     en_pause=sum(g.statut == "pause" for g in gs), nb_categories=k, points_par_categorie=par_cat)


def detail_par_grimpeur(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
                        regles: Regles) -> list[tuple[Grimpeur, dict[Categorie, EtatCategorie], int]]:
    sortie = []
    for g in grimpeurs:
        c = coches.get(g.id, Coches(g.id))
        sortie.append((g, categories_grimpeur(contenu, c), points_grimpeur(contenu, c, regles)))
    return sortie


def cascade_coche(contenu: ContenuEtage, ref: ElementRef, cochee: bool, regles: Regles) -> tuple[ElementRef, ...]:
    if not regles.succes_coche_vaincu or ref.type != "case":
        return ()
    case = next((c for c in contenu.cases if c.id == ref.id), None)
    if case is None:
        return ()
    autres = contenu.cases_du_donjon(case.donjon_id)
    if cochee and not case.est_classique:
        return tuple(ElementRef("case", c.id) for c in autres if c.est_classique)
    if not cochee and case.est_classique:
        return tuple(ElementRef("case", c.id) for c in autres if not c.est_classique)
    return ()
