"""/quetes : le grimpeur déclare lui-même ses quêtes (SPEC §4.2, Shadoaze Q4).

Pas de screen exigé ni de niveau : « on se basera sur la parole des gens ». Le joueur peut joindre
le lien d'un screen. Un admin peut déclarer pour un grimpeur non relié (`pour`) et annuler une
déclaration avec /annuler.
"""

from __future__ import annotations

import discord
from discord import app_commands

from epreuve.bot.acces import REPONSE_REFUS, est_admin
from epreuve.bot.cmd_validation import lire_preuve, trouver_contenu
from epreuve.bot.commun import Contexte, Reponse, contexte_de, envoyer, normaliser, suggestions
from epreuve.db.depot import DejaValide, Depot
from epreuve.domaine.controles import controler_validation
from epreuve.domaine.modeles import TYPES_QUETES, Grimpeur, liste_francaise

TOUTES = "toutes"
REPONSE_NON_RELIE = "Demande à un admin de relier ton compte"


async def _grimpeur_vise(ctx: Contexte, pour: str | None, appelant_admin: bool) -> Grimpeur | Reponse:
    if pour:
        if not appelant_admin:
            return Reponse(f"{REPONSE_REFUS} : l'option `pour`.")
        g = await ctx.depot.grimpeur_par_pseudo(pour)
        return g or Reponse(f"Aucun grimpeur nommé « {pour} ».")
    g = await ctx.depot.grimpeur_par_discord(ctx.acteur_id)
    return g or Reponse(f"{REPONSE_NON_RELIE} à ton pseudo de grimpeur : rien n'a été enregistré.")


async def declarer_quetes(ctx: Contexte, contenu: str, preuve: str | None = None, pour: str | None = None,
                          appelant_admin: bool = False) -> Reponse:
    g = await _grimpeur_vise(ctx, pour, appelant_admin)
    if isinstance(g, Reponse):
        return g
    etage = await ctx.depot.etage_ouvert()
    if etage is None:
        return Reponse("Rien n'a été enregistré : aucun étage n'est ouvert.")
    quetes = [c for c in await ctx.depot.contenus(etage.id) if c.type in TYPES_QUETES]

    if normaliser(contenu) == TOUTES:
        # « toutes » : tout ce qui reste à déclarer (ce qui est déjà déclaré est ignoré, sans erreur).
        choisis = [c for c in quetes if await ctx.depot.validation_acceptee(g.id, c.id) is None]
        if not choisis:
            return Reponse(f"**{g.pseudo}** a déjà déclaré toutes les quêtes de l'étage.")
    else:
        trouve = trouver_contenu(contenu, quetes)
        if trouve is None:
            return Reponse(f"Rien n'a été enregistré : quête « {contenu} » inconnue sur l'étage en cours.")
        choisis = [trouve]

    preuve_lue = None
    if preuve:
        preuve_lue = lire_preuve(preuve, ctx.guild_id)
        if isinstance(preuve_lue, str):
            return Reponse(f"Rien n'a été enregistré : {preuve_lue}.")

    bloquants = []
    for c in choisis:
        deja = await ctx.depot.validation_acceptee(g.id, c.id) is not None
        controle = controler_validation(g, c, None, ctx.maintenant, etage, deja)
        bloquants += [f"{c.nom_court} : {m}" for m in controle.bloquants]
    if bloquants:
        return Reponse("Rien n'a été enregistré :\n" + "\n".join(f"• {m}" for m in bloquants))

    try:
        ids = await ctx.depot.declarer(etage, choisis, g, preuve_lue, ctx.acteur_id, ctx.maintenant)
    except DejaValide:
        return Reponse("Rien n'a été enregistré : déjà déclaré.")
    titres = liste_francaise([f"« {c.nom_court} »" for c in choisis])
    return Reponse(f"✅ **{g.pseudo}** a déclaré avoir terminé {titres} (n° {', '.join(map(str, ids))}). "
                   "Les quêtes rapportent des points une fois le full succès atteint.")


# --- Couche Discord -----------------------------------------------------------------------------


class CommandesJoueur:
    def __init__(self, depot: Depot, guild_id: int, admin_role_id: int, fuseau: str) -> None:
        self.depot, self.guild_id, self.admin_role_id, self.fuseau = depot, guild_id, admin_role_id, fuseau

    def commandes(self) -> list[app_commands.Command]:
        return [self._quetes()]

    async def _quetes_restantes(self, interaction: discord.Interaction, saisie: str):
        """Les quêtes pas encore déclarées par l'appelant (ou par le grimpeur `pour`), plus « toutes »."""
        etage = await self.depot.etage_ouvert()
        if etage is None:
            return []
        pour = getattr(interaction.namespace, "pour", None)
        g = (await self.depot.grimpeur_par_pseudo(pour) if pour
             else await self.depot.grimpeur_par_discord(interaction.user.id))
        options = [(TOUTES, TOUTES)]
        for c in await self.depot.contenus(etage.id):
            if c.type in TYPES_QUETES and (g is None or await self.depot.validation_acceptee(g.id, c.id) is None):
                options.append((c.nom_court, str(c.id)))
        return [app_commands.Choice(name=n, value=v) for n, v in suggestions(saisie, options)]

    def _quetes(self) -> app_commands.Command:
        outil = self

        @app_commands.command(name="quetes", description="Déclarer les quêtes que tu as terminées")
        @app_commands.guild_only()
        @app_commands.describe(contenu="Une quête, ou « toutes »", preuve="Lien d'un screen (facultatif)",
                               pour="Réservé aux admins : déclarer pour ce grimpeur")
        async def quetes_cmd(interaction: discord.Interaction, contenu: str, preuve: str | None = None,
                             pour: str | None = None) -> None:
            ctx = contexte_de(interaction, outil.depot, outil.guild_id, outil.fuseau)
            admin = est_admin(interaction.user, outil.admin_role_id)
            await envoyer(interaction, await declarer_quetes(ctx, contenu, preuve, pour, admin))

        quetes_cmd.autocomplete("contenu")(self._quetes_restantes)
        return quetes_cmd
