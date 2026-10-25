"""Qui entre dans la jauge : les grimpeurs comptés et les retardataires (SPEC §5.4, Shadoaze §8 bis c, d, e).

- Un grimpeur inscrit avant l'ouverture de l'étage en cours est compté (`inclus_le` renseigné).
- Un grimpeur inscrit après, ou qui revient de pause, est retardataire : il n'entre ni dans le
  maximum ni dans les points (« il n'est intégré à l'algorithme que s'il rattrape »).
- Il devient compté quand son niveau connu atteint le NIVEAU PLANCHER : le plus petit niveau connu
  parmi les grimpeurs comptés (le moins avancé du groupe). Un admin peut aussi l'inclure à la main.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from epreuve.domaine.modeles import Etage, Grimpeur


def est_compte(g: Grimpeur) -> bool:
    """Actif et inclus : il entre dans le maximum et dans les points."""
    return g.statut == "actif" and g.inclus_le is not None


def est_retardataire(g: Grimpeur) -> bool:
    """Actif mais pas (ou plus) inclus : hors de la jauge tant qu'il n'a pas rattrapé."""
    return g.statut == "actif" and g.inclus_le is None


def niveau_plancher(grimpeurs: Iterable[Grimpeur], etage: Etage) -> int:
    """Le niveau à rattraper : le plus petit niveau connu parmi les comptés, sinon le cap de l'étage."""
    niveaux = [g.niveau_connu for g in grimpeurs if est_compte(g) and g.niveau_connu is not None]
    return min(niveaux) if niveaux else etage.level_cap


def doit_etre_inclus(g: Grimpeur, plancher: int) -> bool:
    """Vrai si un retardataire a rattrapé le grimpeur compté le moins avancé."""
    return est_retardataire(g) and g.niveau_connu is not None and g.niveau_connu >= plancher


def inclus_des_l_inscription(inscrit_le: datetime, etage_ouvert: Etage | None) -> bool:
    """À l'inscription : compté si aucun étage n'est ouvert, ou si l'étage n'a pas encore ouvert."""
    if etage_ouvert is None or etage_ouvert.ouvert_le is None:
        return True
    return inscrit_le < etage_ouvert.ouvert_le
