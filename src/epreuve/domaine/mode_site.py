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
# Lot B : la connexion est permise pour que les admins puissent entrer pendant le teaser. Un joueur
# connecté revoit le teaser. « /inscription » n'est pas dans cette liste : elle ne s'ouvre que pendant la
# fenêtre des fiches (`fiches_ouvertes`, décision du 07/11), et le filtre la traite à part.
CHEMINS_TOUJOURS_PERMIS: frozenset[str] = frozenset({"/", "/sante", "/connexion", "/auth/discord/retour",
                                                     "/deconnexion"})
# Fichiers statiques du site, permis par chemin exact : la feuille et le script commun, sans aucune donnée
# d'étage. Sans eux, les pages servies à un visiteur (erreur de connexion, etc.) s'afficheraient sans style.
# Les icônes du site sont en ligne dans les gabarits : aucun fichier d'icône à permettre.
CHEMINS_STATIQUES_SITE_PERMIS: frozenset[str] = frozenset({"/static/style.css", "/static/commun.css", "/static/app.js"})
# Seuls les dossiers du teaser : une route à paramètre en tête (`/{x}/…`) ne doit jamais passer pour
# un fichier statique. Jamais de préfixe large « /static/ ».
PREFIXES_TOUJOURS_PERMIS: tuple[str, ...] = ("/static/teaser/", "/static/fonts/")
# La seule page du site servie à un joueur pendant la fenêtre des fiches, avant l'ouverture.
CHEMIN_FICHE = "/inscription"


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


def voit_site_complet(mode: ModeEffectif, est_admin: bool) -> bool:
    """Vrai en mode ouvert, ou pour un admin (qui voit le site derrière le teaser).

    Aucun joueur avant l'ouverture : le statut de « testeur » du lot A a disparu au lot B.
    """
    return mode == "ouvert" or est_admin


def fiches_ouvertes(ouvertes_le: datetime, fermees_le: datetime, maintenant: datetime) -> bool:
    """Un joueur peut-il créer sa fiche ? Vrai de `ouvertes_le` (compris) à `fermees_le` (exclu).

    La pré-inscription (11/11 17 h → 13/11 17 h) donne le nombre de grimpeurs actifs dès l'ouverture,
    donc le vrai palier de l'étage 0 ; passé `fermees_le`, plus personne ne s'ajoute (seul un admin le peut).
    Lève ValueError si une date n'a pas de fuseau.
    """
    for nom, d in (("ouvertes_le", ouvertes_le), ("fermees_le", fermees_le), ("maintenant", maintenant)):
        if d.tzinfo is None or d.utcoffset() is None:
            raise ValueError(f"{nom} doit porter un fuseau horaire : {d.isoformat()}")
    return ouvertes_le <= maintenant < fermees_le
