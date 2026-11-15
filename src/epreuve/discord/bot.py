"""Le bot du salon « métiers » (demande de BillyBarkMan, 15/11).

On le mentionne : « @Gardien paysan lvl 15 » liste les grimpeurs qui ont déclaré Paysan au niveau 15 ou plus ;
« @Gardien Billy » donne les métiers de Billy. Il répond par des pseudos, sans mentionner personne
(`AllowedMentions.none()`), et seulement dans un salon dont le nom contient « métier ».

Il tourne dans le même programme que le site (une tâche asyncio de `main.lancer`) et lit la même base : il voit
les fiches et les métiers déclarés sur le tableau de bord. Sans `DISCORD_BOT_TOKEN`, il ne démarre pas.
Discord transmet le texte d'un message qui mentionne le bot même sans l'intention « contenu des messages ».
"""

from __future__ import annotations

import logging
import re

import discord

from epreuve.domaine.metiers import (
    METIERS,
    PAR_CLE,
    artisans,
    interpreter,
    plier,
    texte_aide,
    texte_artisans,
    texte_joueur,
    trouver_joueur,
)

journal = logging.getLogger("epreuve.bot")
MENTION = re.compile(r"<@[!&]?\d+>")


def salon_autorise(nom: str) -> bool:
    return "metier" in plier(nom)


async def repondre(depot, texte: str, site: str) -> str:
    """La réponse du bot au texte d'un message, mentions retirées. Lit les fiches et les métiers dans la base."""
    demande = interpreter(MENTION.sub(" ", texte))
    if demande is None:
        return texte_aide(site)
    grimpeurs = {g.id: g for g in await depot.grimpeurs() if g.statut != "exclu"}
    niveaux = [n for n in await depot.metiers() if n.grimpeur_id in grimpeurs]
    if demande.metier is not None:
        liste = [(grimpeurs[n.grimpeur_id].pseudo, n.niveau)
                 for n in artisans(niveaux, demande.metier.cle, demande.minimum)]
        return texte_artisans(demande.metier, demande.minimum, liste, site)
    gid = trouver_joueur(demande.joueur or "", {i: g.pseudo for i, g in grimpeurs.items()})
    if gid is None:
        return f"Je ne trouve ni métier ni grimpeur « {demande.joueur} ». " + texte_aide(site)
    ordre = {m.cle: i for i, m in enumerate(METIERS)}
    siens = sorted((n for n in niveaux if n.grimpeur_id == gid), key=lambda n: (-n.niveau, ordre[n.metier]))
    return texte_joueur(grimpeurs[gid].pseudo, [(PAR_CLE[n.metier].nom, n.niveau) for n in siens])


class BotMetiers(discord.Client):  # pragma: no cover — la connexion à Discord n'est pas testable hors ligne
    def __init__(self, depot, site: str) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.depot, self.site = depot, site

    async def on_ready(self) -> None:
        journal.info("bot des métiers connecté : %s", self.user)

    def _mentionne(self, message: discord.Message) -> bool:
        if self.user in message.mentions:
            return True
        moi = message.guild.me if message.guild else None
        return moi is not None and any(r in moi.roles for r in message.role_mentions if r.is_bot_managed())

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or self.user is None or not self._mentionne(message):
            return
        if not salon_autorise(getattr(message.channel, "name", "")):
            return
        try:
            texte = await repondre(self.depot, message.content, self.site)
        except Exception:  # noqa: BLE001 — une base indisponible ne doit pas faire tomber le bot
            journal.exception("réponse du bot impossible")
            texte = "Je n'arrive pas à lire les métiers pour l'instant, réessaie dans un moment."
        await message.reply(texte, mention_author=False)
