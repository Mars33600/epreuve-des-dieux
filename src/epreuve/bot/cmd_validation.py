"""/valider et /annuler : la saisie des validations de donjon et de succès par les admins.

Règles de /valider :
- TOUT OU RIEN sur les motifs bloquants (pause, doublon, date…) : s'il y en a un seul, rien n'est
  écrit et la réponse les liste tous ;
- un DÉPASSEMENT DE CAP n'est pas un refus (Shadoaze, Q9) : le bot affiche un avertissement et deux
  boutons, « Accepter malgré le dépassement » et « Annuler la saisie ». Rien n'est écrit avant le clic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

import discord
from discord import app_commands

from epreuve.bot.cmd_etage import charger_etat
from epreuve.bot.cmd_grimpeur import autocompletion_pseudo
from epreuve.bot.commun import (
    Contexte,
    Reponse,
    autoriser,
    contexte_de,
    date_lisible,
    differer,
    envoyer,
    normaliser,
    suggestions,
)
from epreuve.db.depot import DejaValide, Depot, Introuvable, PreuveDiscord
from epreuve.domaine.controles import MOTIF_DEJA_VALIDE, controler_validation
from epreuve.domaine.modeles import TYPES_QUETES, Contenu, Grimpeur, liste_francaise, phrase_validation

NB_MAX_GRIMPEURS = 8
ID_MAX = 2**31 - 1  # le plus grand identifiant possible d'une validation (entier Postgres)
DELAI_CONFIRMATION_S = 600  # les boutons d'avertissement expirent après 10 minutes

# --- Liens de preuve -----------------------------------------------------------------------------

# https://discord.com/channels/<serveur>/<salon>/<message> (aussi ptb., canary. et discordapp.com)
_LIEN = re.compile(r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)/?$")
EPOQUE_DISCORD_MS = 1_420_070_400_000  # 1er janvier 2015 : l'origine des identifiants Discord


def date_du_snowflake(identifiant: int) -> datetime:
    """Un identifiant Discord encode sa date de création : les 42 premiers bits sont des millisecondes
    depuis 2015. Pas besoin de lire le message pour connaître sa date."""
    ms = (identifiant >> 22) + EPOQUE_DISCORD_MS
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def lire_preuve(lien: str, guild_id: int) -> PreuveDiscord | str:
    """Découpe le lien d'un message. Renvoie un motif de refus (str) si le lien ne convient pas."""
    m = _LIEN.match(lien.strip())
    if not m:
        return "lien de preuve invalide (attendu : le lien d'un message Discord, « Copier le lien du message »)"
    serveur, salon, message = (int(x) for x in m.groups())
    if serveur != guild_id:
        return "la preuve vient d'un autre serveur Discord"
    return PreuveDiscord(serveur, salon, message, lien.strip(), date_du_snowflake(message))


def trouver_contenu(saisie: str, contenus: list[Contenu]) -> Contenu | None:
    """Par id (valeur choisie dans l'autocomplétion) ou par nom tapé, sans casse ni accents."""
    if saisie.strip().isdigit():
        par_id = next((c for c in contenus if c.id == int(saisie)), None)
        if par_id:
            return par_id
    cible = normaliser(saisie)
    return next((c for c in contenus if cible in (normaliser(c.nom_court), normaliser(c.nom))), None)


async def motif_doublon(ctx: Contexte, g: Grimpeur, contenu: Contenu) -> str:
    """« déjà validé le 31/10 à 09:12 (n° 12) » : le domaine dit « déjà validé », on ajoute la date."""
    existante = await ctx.depot.validation_acceptee(g.id, contenu.id)
    if existante is None:  # pragma: no cover — course très improbable : annulée entre-temps
        return MOTIF_DEJA_VALIDE
    return f"{MOTIF_DEJA_VALIDE} le {date_lisible(existante.realisee_le, ctx.fuseau)} (n° {existante.id})"


# --- Fonctions métier ----------------------------------------------------------------------------


@dataclass(frozen=True)
class DemandeValidation:
    contenu: str  # l'id choisi dans l'autocomplétion, ou un nom tapé à la main
    couples: list[tuple[str, int]]  # (pseudo, niveau)
    preuve: str | None = None


@dataclass(frozen=True)
class AConfirmer:
    """Réponse de /valider quand il y a un dépassement de cap : l'admin doit trancher."""

    texte: str
    demande: DemandeValidation


async def valider(ctx: Contexte, d: DemandeValidation, accepter_depassement: bool = False) -> Reponse | AConfirmer:
    """Contrôle puis écrit. Avec un dépassement de cap et `accepter_depassement=False`, n'écrit rien
    et renvoie `AConfirmer`. Le bouton « Accepter » rappelle cette fonction avec `True` : tous les
    contrôles sont refaits sur les données du moment, puis les validations sont écrites `forcee`."""
    if not d.couples:
        return Reponse("Rien n'a été enregistré : indique au moins un grimpeur et son niveau.")
    etage = await ctx.depot.etage_ouvert()
    if etage is None:
        return Reponse("Rien n'a été enregistré : aucun étage n'est ouvert.")
    contenus = await ctx.depot.contenus(etage.id)
    contenu = trouver_contenu(d.contenu, [c for c in contenus if c.type not in TYPES_QUETES])
    if contenu is None:
        quete = trouver_contenu(d.contenu, [c for c in contenus if c.type in TYPES_QUETES])
        aide = " Les quêtes se déclarent avec `/quetes`." if quete else ""
        return Reponse(f"Rien n'a été enregistré : contenu « {d.contenu} » inconnu sur l'étage en cours.{aide}")

    bloquants: list[str] = []
    avertissements: list[str] = []
    preuve, realisee_le = None, ctx.maintenant
    if d.preuve:
        lue = lire_preuve(d.preuve, ctx.guild_id)
        if isinstance(lue, str):
            bloquants.append(lue)
        else:
            preuve, realisee_le = lue, lue.poste_le

    couples: list[tuple[Grimpeur, int, bool]] = []
    vus: set[int] = set()
    for pseudo, niveau in d.couples:
        g = await ctx.depot.grimpeur_par_pseudo(pseudo)
        if g is None:
            bloquants.append(f"« {pseudo} » : grimpeur inconnu")
            continue
        if g.id in vus:
            bloquants.append(f"{g.pseudo} : indiqué deux fois")
            continue
        vus.add(g.id)
        deja = await ctx.depot.validation_acceptee(g.id, contenu.id) is not None
        controle = controler_validation(g, contenu, niveau, realisee_le, etage, deja)
        for m in controle.bloquants:
            bloquants.append(f"{g.pseudo} : {await motif_doublon(ctx, g, contenu) if m == MOTIF_DEJA_VALIDE else m}")
        avertissements += [f"{g.pseudo} : {m}" for m in controle.avertissements]
        couples.append((g, niveau, bool(controle.avertissements)))

    if bloquants:
        return Reponse("Rien n'a été enregistré :\n" + "\n".join(f"• {m}" for m in bloquants))
    if avertissements and not accepter_depassement:
        return AConfirmer("⚠️ Dépassement de cap, à trancher :\n" + "\n".join(f"• {m}" for m in avertissements)
                          + "\nRien n'est enregistré tant que tu n'as pas choisi.", d)

    try:
        ids = await ctx.depot.creer_validations(etage, contenu, couples, realisee_le, preuve,
                                               ctx.acteur_id, ctx.maintenant)
    except DejaValide:
        # Un autre admin a validé le même couple pendant qu'on contrôlait : la base a tout bloqué.
        details = [f"• {g.pseudo} : {await motif_doublon(ctx, g, contenu)}"
                   for g, _, _ in couples if await ctx.depot.validation_acceptee(g.id, contenu.id)]
        return Reponse("Rien n'a été enregistré :\n" + "\n".join(details))

    pseudos = liste_francaise([g.pseudo for g, _, _ in couples])
    phrase = phrase_validation(len(couples), [contenu.nom_court], [n for _, n, _ in couples])
    lignes = [f"✅ {pseudos} {phrase}",
              f"Validations n° {', '.join(str(i) for i in ids)} (réalisée le {date_lisible(realisee_le, ctx.fuseau)})."]
    forcees = [g.pseudo for g, _, f in couples if f]
    if forcees:
        lignes.append(f"Acceptée malgré le dépassement de cap pour {liste_francaise(forcees)} (inscrit au journal).")
    etat = await charger_etat(ctx)
    if etat:
        lignes.append(f"Jauge : {etat.jauge.points} points sur {etat.jauge.seuil} requis.")
    return Reponse("\n".join(lignes))


async def annuler(ctx: Contexte, validation_id: int, motif: str) -> Reponse:
    if not 1 <= validation_id <= ID_MAX:
        return Reponse(f"Rien n'a été annulé : numéro de validation invalide ({validation_id}).")
    if not motif.strip():
        return Reponse("Rien n'a été annulé : indique un motif.")
    try:
        v = await ctx.depot.annuler_validation(validation_id, motif, ctx.acteur_id, ctx.maintenant)
    except Introuvable as e:
        return Reponse(f"Rien n'a été annulé : {e}.")
    return Reponse(f"Validation n° {v.id} annulée ({motif}). Elle ne compte plus dans la jauge "
                   "mais reste visible dans `/grimpeur voir`.")


# --- Couche Discord -----------------------------------------------------------------------------

Niveau = app_commands.Range[int, 1, 200]


class ConfirmationDepassement(discord.ui.View):
    """« Accepter malgré le dépassement » / « Annuler la saisie ». Seul l'admin qui a lancé la
    commande peut cliquer ; les boutons expirent après 10 minutes."""

    def __init__(self, outil: CommandesValidation, auteur_id: int, demande: DemandeValidation) -> None:
        super().__init__(timeout=DELAI_CONFIRMATION_S)
        self.outil, self.auteur_id, self.demande = outil, auteur_id, demande

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.auteur_id:
            await interaction.response.send_message("Seul l'admin qui a lancé la saisie peut trancher.",
                                                    ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accepter malgré le dépassement", style=discord.ButtonStyle.danger)
    async def accepter(self, interaction: discord.Interaction, _bouton: discord.ui.Button) -> None:
        if not await autoriser(interaction, self.outil.admin_role_id):
            return
        ctx = contexte_de(interaction, self.outil.depot, self.outil.guild_id, self.outil.fuseau)
        rep = await valider(ctx, self.demande, accepter_depassement=True)
        self.stop()
        await interaction.response.edit_message(content=rep.texte, view=None)

    @discord.ui.button(label="Annuler la saisie", style=discord.ButtonStyle.secondary)
    async def abandonner(self, interaction: discord.Interaction, _bouton: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(content="Saisie annulée, rien n'a été enregistré.", view=None)


class CommandesValidation:
    """Regroupe /valider et /annuler, qui ont besoin du dépôt et de la configuration."""

    def __init__(self, depot: Depot, guild_id: int, admin_role_id: int, fuseau: str) -> None:
        self.depot, self.guild_id, self.admin_role_id, self.fuseau = depot, guild_id, admin_role_id, fuseau

    def commandes(self) -> list[app_commands.Command]:
        return [self._valider(), self._annuler()]

    async def _contenus(self, _interaction: discord.Interaction, saisie: str):
        """Seulement les succès de l'étage ouvert : les quêtes passent par /quetes."""
        etage = await self.depot.etage_ouvert()
        contenus = await self.depot.contenus(etage.id) if etage else []
        options = [(c.nom_court, str(c.id)) for c in contenus if c.type == "succes"]
        return [app_commands.Choice(name=n, value=v) for n, v in suggestions(saisie, options)]

    async def _pseudos(self, _interaction: discord.Interaction, saisie: str):
        return await autocompletion_pseudo(self.depot, saisie)

    def _valider(self) -> app_commands.Command:
        outil = self

        @app_commands.command(name="valider", description="Enregistrer un donjon ou un succès (1 à 8 grimpeurs)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        @app_commands.describe(contenu="Le succès réalisé", preuve="Lien du message du screen")
        async def valider_cmd(
            interaction: discord.Interaction, contenu: str, grimpeur1: str, niveau1: Niveau,
            grimpeur2: str | None = None, niveau2: Niveau | None = None,
            grimpeur3: str | None = None, niveau3: Niveau | None = None,
            grimpeur4: str | None = None, niveau4: Niveau | None = None,
            grimpeur5: str | None = None, niveau5: Niveau | None = None,
            grimpeur6: str | None = None, niveau6: Niveau | None = None,
            grimpeur7: str | None = None, niveau7: Niveau | None = None,
            grimpeur8: str | None = None, niveau8: Niveau | None = None,
            preuve: str | None = None,
        ) -> None:
            if not await autoriser(interaction, outil.admin_role_id):
                return
            paires = [(grimpeur1, niveau1), (grimpeur2, niveau2), (grimpeur3, niveau3), (grimpeur4, niveau4),
                      (grimpeur5, niveau5), (grimpeur6, niveau6), (grimpeur7, niveau7), (grimpeur8, niveau8)]
            couples, oublis = [], []
            for i, (pseudo, niveau) in enumerate(paires, start=1):
                if pseudo and niveau:
                    couples.append((pseudo, niveau))
                elif pseudo or niveau:
                    oublis.append(f"• grimpeur{i} et niveau{i} vont ensemble")
            if oublis:
                await envoyer(interaction, Reponse("Rien n'a été enregistré :\n" + "\n".join(oublis)))
                return
            await differer(interaction)
            ctx = contexte_de(interaction, outil.depot, outil.guild_id, outil.fuseau)
            demande = DemandeValidation(contenu, couples, preuve)
            rep = await valider(ctx, demande)
            if isinstance(rep, AConfirmer):
                vue = ConfirmationDepassement(outil, interaction.user.id, demande)
                await interaction.followup.send(rep.texte, ephemeral=True, view=vue)
                return
            await envoyer(interaction, rep)

        valider_cmd.autocomplete("contenu")(self._contenus)
        for i in range(1, NB_MAX_GRIMPEURS + 1):
            valider_cmd.autocomplete(f"grimpeur{i}")(self._pseudos)
        return valider_cmd

    def _annuler(self) -> app_commands.Command:
        outil = self

        @app_commands.command(name="annuler", description="Annuler une validation ou une déclaration")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        @app_commands.describe(validation="Numéro de la validation", motif="Pourquoi on l'annule")
        async def annuler_cmd(interaction: discord.Interaction, validation: app_commands.Range[int, 1, ID_MAX],
                              motif: str) -> None:
            if not await autoriser(interaction, outil.admin_role_id):
                return
            await differer(interaction)
            ctx = contexte_de(interaction, outil.depot, outil.guild_id, outil.fuseau)
            await envoyer(interaction, await annuler(ctx, validation, motif))

        return annuler_cmd
