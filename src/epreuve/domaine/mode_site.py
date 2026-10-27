"""Le mode du site : le teaser avant l'ouverture, le site complet ensuite (ARCHITECTURE §7).

Le réglage `SITE_MODE` vaut `auto` par défaut : la bascule tombe le vendredi 13/11 à 17 h et ne doit
pas dépendre de la présence de quelqu'un devant son ordinateur. `teaser` et `ouvert` forcent le mode,
pour reprendre la main en une commande (`fly secrets set SITE_MODE=teaser`).

Les dates doivent porter leur fuseau : comparer une date « naïve » à une date en UTC est une erreur
en Python, et deviner le fuseau à sa place décalerait l'ouverture d'une ou deux heures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

ReglageMode = Literal["auto", "teaser", "ouvert"]
ModeEffectif = Literal["teaser", "ouvert"]

# Ce que le middleware laisse passer en mode teaser, pour tout le monde.
CHEMINS_TOUJOURS_PERMIS: frozenset[str] = frozenset({"/", "/sante"})
PREFIXES_TOUJOURS_PERMIS: tuple[str, ...] = ("/static/",)
# Le lot B ajoute : "/connexion", "/auth/discord/retour", "/deconnexion", "/inscription".


def mode_effectif(reglage: ReglageMode, ouvert_le: datetime, maintenant: datetime) -> ModeEffectif:
    """« teaser » si réglage = teaser, ou si réglage = auto et maintenant < ouvert_le ; sinon « ouvert ».

    À l'instant exact de l'ouverture, le site est ouvert. Lève ValueError si une date n'a pas de fuseau.
    """
    for nom, d in (("ouvert_le", ouvert_le), ("maintenant", maintenant)):
        if d.tzinfo is None or d.utcoffset() is None:
            raise ValueError(f"{nom} doit porter un fuseau horaire : {d.isoformat()}")
    if reglage == "teaser" or (reglage == "auto" and maintenant < ouvert_le):
        return "teaser"
    return "ouvert"


def voit_site_complet(mode: ModeEffectif, est_admin: bool, est_testeur: bool) -> bool:
    """Vrai en mode ouvert, ou pour un admin ou un testeur (qui voient le site derrière le teaser)."""
    return mode == "ouvert" or est_admin or est_testeur
