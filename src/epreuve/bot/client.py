"""Création du bot : verrou de serveur, enregistrement et synchronisation des commandes.

Le bot fonctionne sans aucun intent privilégié au jalon bêta : seul `GUILDS` est demandé.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from epreuve.bot.cmd_etage import GroupeEtage
from epreuve.bot.cmd_grimpeur import GroupeGrimpeur
from epreuve.bot.cmd_joueur import CommandesJoueur
from epreuve.bot.cmd_validation import CommandesValidation
from epreuve.db.depot import Depot

journal = logging.getLogger("epreuve.bot")


class ArbreVerrouille(app_commands.CommandTree):
    """L'arbre des commandes, qui ignore toute interaction venue d'un autre serveur."""

    def __init__(self, client: discord.Client, guild_id: int) -> None:
        super().__init__(client)
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.guild_id == self.guild_id


class BotEpreuve(discord.Client):
    def __init__(self, depot: Depot, guild_id: int, admin_role_id: int, fuseau: str) -> None:
        super().__init__(intents=discord.Intents(guilds=True))
        self.guild_id = guild_id
        self.tree = ArbreVerrouille(self, guild_id)
        notre_serveur = discord.Object(id=guild_id)
        args = (depot, guild_id, admin_role_id, fuseau)
        self.tree.add_command(GroupeGrimpeur(*args), guild=notre_serveur)
        self.tree.add_command(GroupeEtage(*args), guild=notre_serveur)
        for commande in [*CommandesValidation(*args).commandes(), *CommandesJoueur(*args).commandes()]:
            self.tree.add_command(commande, guild=notre_serveur)

    @property
    def connecte(self) -> bool:
        """Pour /sante : la passerelle Discord est-elle connectée ?"""
        return self.is_ready() and not self.is_closed()

    async def setup_hook(self) -> None:
        # Synchronisation sur NOTRE serveur seulement : instantanée (la synchro globale prend ~1 h).
        await self.tree.sync(guild=discord.Object(id=self.guild_id))

    async def on_ready(self) -> None:
        journal.info("connecté en tant que %s", self.user)
        for serveur in list(self.guilds):
            await self._quitter_si_etranger(serveur)

    async def on_guild_join(self, serveur: discord.Guild) -> None:
        await self._quitter_si_etranger(serveur)

    async def _quitter_si_etranger(self, serveur: discord.Guild) -> None:
        if serveur.id != self.guild_id:
            journal.warning("serveur inconnu %s : le bot le quitte", serveur.id)
            await serveur.leave()
