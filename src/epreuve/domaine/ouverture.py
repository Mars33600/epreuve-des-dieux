"""Peut-on ouvrir l'étage suivant ? Le site l'ouvre-t-il seul ? Et le bilan figé de l'étage qui se termine
(SPEC §5.2, §5.5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from epreuve.domaine.bareme import EtatJauge
from epreuve.domaine.mode_site import ModeEffectif
from epreuve.domaine.modeles import Categorie, Etage, Regles
from epreuve.domaine.textes import date_paris

# L'ouverture automatique n'a pas d'auteur humain : le journal note un acteur vide (`acteur_discord_id` NULL,
# affiché « système » dans le journal admin). Pas 0 ni un faux identifiant : un identifiant Discord inventé
# pourrait un jour coïncider avec un vrai compte, NULL ne le peut pas.
ACTEUR_SYSTEME: int | None = None


@dataclass(frozen=True)
class Decision:
    ok: bool
    raisons: tuple[str, ...]  # lisibles, en français ; un admin peut forcer malgré elles


@dataclass(frozen=True)
class Bilan:
    fige_le: datetime
    actifs: int
    palier: int
    score: int
    points_par_categorie: dict[Categorie, int]
    force: bool
    motif: str | None


def peut_ouvrir(jauge: EtatJauge, en_cours: Etage, prochain: Etage | None, maintenant: datetime) -> Decision:
    """Ouvrable ⇔ l'étage en cours est ouvert, un étage scellé suit, la jauge est pleine et la date plancher
    est passée (à l'instant exact, c'est permis). Toutes les raisons de refus sont données, pas seulement la
    première."""
    raisons: list[str] = []
    if en_cours.statut != "ouvert":
        raisons.append("l'étage en cours n'est pas ouvert")
    if prochain is None or prochain.statut != "scelle":
        raisons.append("aucun étage préparé")
    if jauge.actifs == 0:
        raisons.append("aucun grimpeur actif")
    elif jauge.palier == 0:
        raisons.append("jauge : palier nul (étage sans catégorie), régler un palier manuel")
    elif not jauge.pleine:
        n = jauge.manquants
        raisons.append(f"jauge : il manque {n} point{'s' if n > 1 else ''}")
    plancher = en_cours.date_plancher_suivant
    if plancher is not None and maintenant < plancher:
        raisons.append(f"pas avant le {date_paris(plancher)}")
    return Decision(not raisons, tuple(raisons))


def pleine_depuis(jauge: EtatJauge, avant: datetime | None, maintenant: datetime) -> datetime | None:
    """Depuis quand la jauge est-elle pleine ? `avant` : l'instant noté au regard précédent (None si elle ne
    l'était pas). Toujours pleine → l'instant d'origine est gardé ; pleine à l'instant → `maintenant` ; plus
    pleine → None, et le compte du délai de grâce repartira de zéro à la prochaine coche qui la remplit."""
    if not jauge.pleine:
        return None
    return avant if avant is not None else maintenant


def reste_avant_ouverture(pleine_depuis: datetime | None, maintenant: datetime, regles: Regles) -> float | None:
    """Secondes avant la fin du délai de grâce (`regles.delai_grace_secondes`) ; None si la jauge n'est pas
    pleine, ou si le délai est déjà écoulé. La veille s'en sert pour se réveiller pile à la fin du délai."""
    if pleine_depuis is None:
        return None
    reste = regles.delai_grace_secondes - (maintenant - pleine_depuis).total_seconds()
    return reste if reste > 0 else None


def ouvrir_automatiquement(jauge: EtatJauge, en_cours: Etage, prochain: Etage | None, maintenant: datetime,
                           regles: Regles, mode: ModeEffectif, pendant_teaser: bool = False, *,
                           pleine_depuis: datetime | None) -> bool:
    """Le site ouvre-t-il seul l'étage suivant ? Seulement si la règle est active, le site ouvert (pendant le
    teaser rien ne bouge, sauf `pendant_teaser` pour la recette des admins : les annonces restent coupées),
    `peut_ouvrir` d'accord, et la jauge pleine depuis au moins le délai de grâce : une coche par erreur qui
    remplit la jauge se rattrape en décochant dans la minute, avant que l'étage ne s'ouvre (on ne referme pas
    un étage). Jamais de force : une ouverture qui demanderait un motif reste une décision d'admin."""
    delai_ecoule = pleine_depuis is not None and reste_avant_ouverture(pleine_depuis, maintenant, regles) is None
    return (regles.ouverture_automatique and (mode == "ouvert" or pendant_teaser) and delai_ecoule
            and peut_ouvrir(jauge, en_cours, prochain, maintenant).ok)


def bilan_etage(jauge: EtatJauge, maintenant: datetime, force: bool, motif: str | None) -> Bilan:
    """Le bilan figé à l'ouverture de l'étage suivant. ValueError si force et motif vide."""
    motif = (motif or "").strip() or None
    if force and motif is None:
        raise ValueError("une ouverture forcée exige un motif")
    return Bilan(maintenant, jauge.actifs, jauge.palier, jauge.score, dict(jauge.points_par_categorie), force, motif)
