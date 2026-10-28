"""Le barème : 4 catégories, 1 point chacune, par grimpeur et par étage (SPEC §5).

Pourquoi aucun nombre à virgule : `0.75 * 24` peut donner 18.000000000000004, et l'arrondi au-dessus
donnerait alors 19 au lieu de 18. On calcule le palier avec `fractions.Fraction`, qui est exacte :
m peut valoir 2 ou 5/2 sans erreur d'arrondi, et `math.ceil` d'une fraction est exact.
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


def categories_grimpeur(contenu: ContenuEtage, coches: Coches) -> dict[Categorie, EtatCategorie]:
    """donjons : faits/total sur les cases classiques visibles (une par donjon visible qui en a une) ;
    full_succes : sur toutes les cases visibles ; principales, secondaires : sur les quêtes visibles."""
    classiques = [c.id for c in contenu.cases if c.est_classique]
    toutes = [c.id for c in contenu.cases]
    principales = [q.id for q in contenu.quetes if q.nature == "principale"]
    secondaires = [q.id for q in contenu.quetes if q.nature == "secondaire"]

    def etat(categorie: Categorie, ids: list[int], cochees: frozenset[int]) -> EtatCategorie:
        return EtatCategorie(categorie, sum(1 for i in ids if i in cochees), len(ids))

    return {
        "donjons": etat("donjons", classiques, coches.cases),
        "full_succes": etat("full_succes", toutes, coches.cases),
        "principales": etat("principales", principales, coches.quetes),
        "secondaires": etat("secondaires", secondaires, coches.quetes),
    }


def _a_le_point(etat: EtatCategorie, regles: Regles) -> bool:
    return etat.acquise or (etat.vide and regles.categorie_vide == "offerte")


def points_grimpeur(contenu: ContenuEtage, coches: Coches, regles: Regles) -> int:
    """0 à 4, catégories indépendantes. Si regles.categorie_vide == "offerte", une catégorie vide rapporte 1."""
    return sum(1 for e in categories_grimpeur(contenu, coches).values() if _a_le_point(e, regles))


def categories_comptees(contenu: ContenuEtage, regles: Regles) -> int:
    """K : nombre de catégories non vides (« ignoree ») ou toujours 4 (« offerte »)."""
    if regles.categorie_vide == "offerte":
        return len(CATEGORIES)
    return sum(1 for e in categories_grimpeur(contenu, Coches(0)).values() if not e.vide)


def palier(nb_actifs: int, nb_categories: int, regles: Regles, palier_manuel: int | None = None) -> int:
    """palier_manuel s'il n'est pas None ; sinon ceil(regles.points_par_joueur × nb_actifs × nb_categories / 4),
    en Fraction (exact). ValueError si une entrée est négative ou si nb_categories > 4."""
    if nb_actifs < 0 or nb_categories < 0 or (palier_manuel is not None and palier_manuel < 0):
        raise ValueError("palier : entrée négative")
    if nb_categories > len(CATEGORIES):
        raise ValueError(f"palier : {nb_categories} catégories, 4 au plus")
    if palier_manuel is not None:
        return palier_manuel
    return math.ceil(Fraction(regles.points_par_joueur) * nb_actifs * nb_categories / len(CATEGORIES))


@dataclass(frozen=True)
class EtatJauge:
    score: int
    palier: int
    palier_manuel: bool
    actifs: int
    en_pause: int
    nb_categories: int  # K, pour écrire la formule du palier à côté de la jauge
    points_par_categorie: dict[Categorie, int]

    @property
    def pleine(self) -> bool:
        return self.actifs > 0 and self.palier > 0 and self.score >= self.palier

    @property
    def maximum(self) -> int:
        """« Maximum possible » (DA) : K points par actif."""
        return self.nb_categories * self.actifs

    @property
    def manquants(self) -> int:
        return max(0, self.palier - self.score)


def calculer_jauge(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur],
                   coches: Mapping[int, Coches], regles: Regles) -> EtatJauge:
    """Seuls les grimpeurs actifs comptent. Sans entrée dans `coches` : 0 point. Pas de bonus au lot B (lot C).
    Palier : contenu.etage.palier_manuel s'il est réglé, sinon la formule."""
    grimpeurs = list(grimpeurs)
    actifs = [g for g in grimpeurs if g.statut == "actif"]
    par_categorie: dict[Categorie, int] = dict.fromkeys(CATEGORIES, 0)
    for g in actifs:
        for cat, etat in categories_grimpeur(contenu, coches.get(g.id, Coches(g.id))).items():
            if _a_le_point(etat, regles):
                par_categorie[cat] += 1
    k = categories_comptees(contenu, regles)
    manuel = contenu.etage.palier_manuel
    return EtatJauge(
        score=sum(par_categorie.values()),
        palier=palier(len(actifs), k, regles, manuel),
        palier_manuel=manuel is not None,
        actifs=len(actifs),
        en_pause=sum(1 for g in grimpeurs if g.statut == "pause"),
        nb_categories=k,
        points_par_categorie=par_categorie,
    )


def detail_par_grimpeur(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
                        regles: Regles) -> list[tuple[Grimpeur, dict[Categorie, EtatCategorie], int]]:
    """Pour la vérification avant ouverture (EX-83) : chaque grimpeur, ses catégories, ses points."""
    resultat = []
    for g in grimpeurs:
        c = coches.get(g.id, Coches(g.id))
        resultat.append((g, categories_grimpeur(contenu, c), points_grimpeur(contenu, c, regles)))
    return resultat


def cascade_coche(contenu: ContenuEtage, ref: ElementRef, cochee: bool, regles: Regles) -> tuple[ElementRef, ...]:
    """Les éléments à changer en plus de `ref` (T-16) : cocher un succès non classique → la case classique du
    donjon ; décocher la case classique → les autres cases du donjon. Vide si regles.succes_coche_vaincu est faux."""
    if not regles.succes_coche_vaincu or ref.type != "case":
        return ()
    case = next((c for c in contenu.cases if c.id == ref.id), None)
    if case is None:
        return ()
    du_donjon = contenu.cases_du_donjon(case.donjon_id)
    if cochee and not case.est_classique:
        return tuple(ElementRef("case", c.id) for c in du_donjon if c.est_classique)
    if not cochee and case.est_classique:
        return tuple(ElementRef("case", c.id) for c in du_donjon if c.id != case.id)
    return ()
