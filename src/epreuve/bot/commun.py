"""Outils partagés par les commandes : contexte d'exécution, réponse, recherche tolérante.

Chaque commande est écrite en deux couches :
- une fonction « métier » `async def …(ctx, …) -> Reponse`, testable sans Discord ;
- une fine couche Discord (dans les classes `Groupe…`) qui vérifie l'accès, construit le
  contexte, appelle la fonction métier et envoie la réponse.
"""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import discord

from epreuve.bot.acces import REPONSE_REFUS, est_admin
from epreuve.db.depot import Depot

journal_bot = logging.getLogger("epreuve.bot")

LIMITE_DISCORD = 2000  # nombre de caractères maximal d'un message Discord


@dataclass(frozen=True)
class Contexte:
    depot: Depot
    acteur_id: int  # l'id Discord de l'admin qui agit (écrit au journal)
    maintenant: datetime
    guild_id: int  # notre serveur : sert à refuser les preuves venues d'ailleurs
    fuseau: ZoneInfo


@dataclass(frozen=True)
class Reponse:
    texte: str
    ephemere: bool = True  # par défaut, seul l'admin qui a tapé la commande la voit


def normaliser(texte: str) -> str:
    """Sans accents ni majuscules : « Pépin » → « pepin ». Sert à l'autocomplétion."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold().strip()


def suggestions(saisie: str, options: Iterable[tuple[str, str]], limite: int = 25) -> list[tuple[str, str]]:
    """Filtre des couples (affiché, valeur) : d'abord ceux qui COMMENCENT par la saisie, puis ceux
    qui la CONTIENNENT. Discord n'accepte que 25 propositions au plus."""
    s = normaliser(saisie)
    debut, dedans = [], []
    for nom, valeur in options:
        n = normaliser(nom)
        if n.startswith(s):
            debut.append((nom, valeur))
        elif s in n:
            dedans.append((nom, valeur))
    return (debut + dedans)[:limite]


def tronquer(texte: str) -> str:
    if len(texte) <= LIMITE_DISCORD:
        return texte
    return texte[: LIMITE_DISCORD - 20] + "\n… (liste tronquée)"


def date_lisible(d: datetime, fuseau: ZoneInfo) -> str:
    """« 31/10 à 09:12 », en heure de Paris."""
    return d.astimezone(fuseau).strftime("%d/%m à %H:%M")


# --- Couche Discord -----------------------------------------------------------------------------


def contexte_de(interaction: discord.Interaction, depot: Depot, guild_id: int, fuseau: str) -> Contexte:
    return Contexte(depot, interaction.user.id, datetime.now(UTC), guild_id, ZoneInfo(fuseau))


async def autoriser(interaction: discord.Interaction, admin_role_id: int) -> bool:
    """À appeler en tête de chaque commande admin. Répond « Réservé aux admins » si besoin."""
    if est_admin(interaction.user, admin_role_id):
        return True
    journal_bot.warning("refus d'accès : %s a tenté /%s", interaction.user.id,
                        getattr(interaction.command, "qualified_name", "?"))
    await interaction.response.send_message(REPONSE_REFUS, ephemeral=True)
    return False


async def envoyer(interaction: discord.Interaction, reponse: Reponse, **extra) -> None:
    journal_bot.info("/%s par %s : %s", getattr(interaction.command, "qualified_name", "?"),
                     interaction.user.id, reponse.texte.splitlines()[0][:120])
    await interaction.response.send_message(tronquer(reponse.texte), ephemeral=reponse.ephemere, **extra)
