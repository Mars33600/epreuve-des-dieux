"""La jauge à points d'un étage, les points de chaque grimpeur et les marques des cartes.

Règles (SPEC §5, réponses de Shadoaze) :
- trois paliers cumulatifs : 1 = donjons vaincus, 2 = full succès, 3 = full succès + quêtes ;
- points(g) = le plus haut rang k tel que les paliers 1 à k sont tous atteints (paliers STRICTS :
  des quêtes sans full succès ne font pas passer de 1 à 3) ;
- maximum = Σ points visés (1, 2 ou 3 selon la difficulté) des grimpeurs COMPTÉS ;
- points de la jauge = Σ points des grimpeurs COMPTÉS : un retardataire n'entre ni dans le maximum
  ni dans les points tant qu'il n'a pas rattrapé (Shadoaze, §8 bis d) ;
- seuil = 75 % du maximum (arrondi au-dessus) ; pleine ⇔ maximum > 0 et points ≥ seuil ;
- déblocable ⇔ pleine et maintenant ≥ date plancher.

Les marques des cartes, les points et la jauge reposent sur la même fonction interne
`_contenus_faits` : le site ne peut pas se contredire.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from epreuve.domaine.controles import validation_compte
from epreuve.domaine.inclusion import est_compte, est_retardataire
from epreuve.domaine.modeles import DIFFICULTES, Etage, Grimpeur, Palier, Validation
from epreuve.domaine.seuil import POINTS_VISES, seuil


@dataclass(frozen=True)
class EtatJauge:
    points: int
    maximum: int
    seuil: int
    seuil_pourcent: int
    pleine: bool

    @property
    def manquants(self) -> int:
        return max(0, self.seuil - self.points)


@dataclass(frozen=True)
class EtatEtage:
    etage: Etage
    n_comptes: int
    n_pause: int
    n_retardataires: int
    jauge: EtatJauge
    comptes_par_difficulte: dict[str, int]  # pour écrire « 4 × 3 + 4 × 2 + 4 × 1 »
    grimpeurs_par_palier: tuple[int, int, int]  # comptés ayant au moins 1, 2, 3 points
    deblocable: bool


def _contenus_faits(grimpeur_id: int, validations: Iterable[Validation], etage: Etage) -> set[int]:
    """Les contenus pour lesquels ce grimpeur a au moins une validation qui compte."""
    return {v.contenu_id for v in validations if v.grimpeur_id == grimpeur_id and validation_compte(v, etage)}


def _points(paliers: Iterable[Palier], faits: set[int]) -> int:
    """Le plus haut rang k tel que les contenus des paliers 1 à k sont tous faits."""
    points, cumul = 0, set()
    for p in sorted(paliers, key=lambda p: p.rang):
        # Un palier vide, ou un rang qui saute (1 puis 3), arrête la montée.
        if p.rang != points + 1 or not p.contenu_ids:
            break
        cumul |= p.contenu_ids
        if not cumul <= faits:
            break
        points = p.rang
    return points


def points_grimpeur(g: Grimpeur, paliers: Iterable[Palier], validations: Iterable[Validation],
                    etage: Etage) -> int:
    """De 0 à 3 : les points que ce grimpeur rapporte à la jauge (paliers stricts)."""
    return _points(paliers, _contenus_faits(g.id, validations, etage))


def marques_grimpeur(g: Grimpeur, paliers: Iterable[Palier], validations: Iterable[Validation],
                     etage: Etage) -> dict[int, bool]:
    """Pour chaque rang : les contenus PROPRES du palier sont-ils faits ? (non strict)

    La marque Quêtes peut donc s'allumer sans le full succès, alors que les points restent à 1.
    """
    faits = _contenus_faits(g.id, validations, etage)
    return {p.rang: bool(p.contenu_ids) and p.contenu_ids <= faits for p in paliers}


def calculer_etat_etage(
    etage: Etage,
    paliers: Iterable[Palier],
    grimpeurs: Iterable[Grimpeur],
    validations: Iterable[Validation],
    maintenant: datetime,
) -> EtatEtage:
    paliers, grimpeurs, validations = list(paliers), list(grimpeurs), list(validations)
    comptes = [g for g in grimpeurs if est_compte(g)]

    points_par_compte = [points_grimpeur(g, paliers, validations, etage) for g in comptes]
    maximum = sum(POINTS_VISES[g.difficulte] for g in comptes)
    total = sum(points_par_compte)
    s = seuil(maximum, etage.seuil_pourcent)
    pleine = maximum > 0 and total >= s

    plancher = etage.date_plancher_suivant
    return EtatEtage(
        etage=etage,
        n_comptes=len(comptes),
        n_pause=sum(1 for g in grimpeurs if g.statut == "pause"),
        n_retardataires=sum(1 for g in grimpeurs if est_retardataire(g)),
        jauge=EtatJauge(total, maximum, s, etage.seuil_pourcent, pleine),
        comptes_par_difficulte={d: sum(1 for g in comptes if g.difficulte == d) for d in DIFFICULTES},
        grimpeurs_par_palier=(
            sum(1 for p in points_par_compte if p >= 1),
            sum(1 for p in points_par_compte if p >= 2),
            sum(1 for p in points_par_compte if p >= 3),
        ),
        deblocable=pleine and (plancher is None or maintenant >= plancher),
    )
