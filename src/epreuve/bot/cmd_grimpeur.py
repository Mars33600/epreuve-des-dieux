"""/grimpeur ajouter|modifier|inclure|pause|reprendre|exclure|voir|liste : le registre des grimpeurs.

Toutes ces actions sont écrites au journal avec leur auteur, mais restent hors du fil public.
Celles qui changent le maximum de la jauge (inscription, difficulté, inclusion, pause…) affichent
leur effet : « Maximum 24 → 25, seuil 18 → 19 ».
"""

from __future__ import annotations

import discord
from discord import app_commands

from epreuve.bot.cmd_etage import charger_etat
from epreuve.bot.commun import (
    Contexte,
    Reponse,
    autoriser,
    contexte_de,
    date_lisible,
    envoyer,
    suggestions,
)
from epreuve.db.depot import Depot, ErreurDepot
from epreuve.domaine.classes import CLASSES
from epreuve.domaine.inclusion import est_retardataire
from epreuve.domaine.jauges import EtatEtage
from epreuve.domaine.modeles import DIFFICULTES, NOM_DIFFICULTE, Grimpeur

NOM_STATUT_VALIDATION = {"acceptee": "acceptée", "refusee": "refusée", "annulee": "annulée"}
STATUTS_LISTE = {"actif": "actifs", "pause": "en pause", "exclu": "exclus", "retardataire": "retardataires"}


def nom_statut(g: Grimpeur) -> str:
    if est_retardataire(g):
        return "retardataire (rattrape le groupe)"
    return {"actif": "actif", "pause": "en pause", "exclu": "exclu"}[g.statut]


def pseudo_valide(pseudo: str) -> str | None:
    """Renvoie un motif de refus, ou None si le pseudo convient (2 à 30 caractères)."""
    if not 2 <= len(pseudo) <= 30:
        return "le pseudo doit faire entre 2 et 30 caractères"
    return None


def effet_jauge(avant: EtatEtage | None, apres: EtatEtage | None) -> str:
    """« Maximum 24 → 25, seuil 18 → 19. » (vide si le maximum ne change pas)."""
    if avant is None or apres is None or avant.jauge.maximum == apres.jauge.maximum:
        return ""
    a, b = avant.jauge, apres.jauge
    return f"Maximum {a.maximum} → {b.maximum}, seuil {a.seuil} → {b.seuil}."


async def _trouver(ctx: Contexte, pseudo: str) -> Grimpeur | Reponse:
    g = await ctx.depot.grimpeur_par_pseudo(pseudo)
    return g if g else Reponse(f"Aucun grimpeur nommé « {pseudo} ».")


def _avec_effet(texte: str, avant: EtatEtage | None, apres: EtatEtage | None) -> Reponse:
    effet = effet_jauge(avant, apres)
    return Reponse(f"{texte}\n{effet}" if effet else texte)


# --- Fonctions métier (testables sans Discord) ---------------------------------------------------


async def grimpeur_ajouter(ctx: Contexte, pseudo: str, classe: str, difficulte: str,
                           membre_id: int | None = None) -> Reponse:
    pseudo = pseudo.strip()
    if motif := pseudo_valide(pseudo):
        return Reponse(f"Rien n'a été enregistré : {motif}.")
    if classe not in CLASSES:
        return Reponse(f"Rien n'a été enregistré : classe inconnue « {classe} ».")
    if difficulte not in DIFFICULTES:
        return Reponse(f"Rien n'a été enregistré : difficulté inconnue « {difficulte} ».")
    avant = await charger_etat(ctx)
    try:
        g = await ctx.depot.ajouter_grimpeur(pseudo, classe, difficulte, membre_id, ctx.acteur_id, ctx.maintenant)
    except ErreurDepot as e:
        return Reponse(f"Rien n'a été enregistré : {e}.")
    apres = await charger_etat(ctx)
    texte = f"**{g.pseudo}** est inscrit : {g.classe}, {NOM_DIFFICULTE[g.difficulte]}."
    if est_retardataire(g):
        texte += ("\nL'étage est déjà ouvert : il arrive en **retardataire**. Il n'entre dans la jauge (maximum "
                  "et points) qu'en rattrapant le grimpeur compté le moins avancé, ou avec `/grimpeur inclure`.")
    return _avec_effet(texte, avant, apres)


async def grimpeur_modifier(ctx: Contexte, pseudo: str, nouveau_pseudo: str | None = None,
                            classe: str | None = None, difficulte: str | None = None,
                            niveau: int | None = None, membre_id: int | None = None) -> Reponse:
    g = await _trouver(ctx, pseudo)
    if isinstance(g, Reponse):
        return g
    if nouveau_pseudo is not None:
        nouveau_pseudo = nouveau_pseudo.strip()
        if motif := pseudo_valide(nouveau_pseudo):
            return Reponse(f"Rien n'a été modifié : {motif}.")
    if classe is not None and classe not in CLASSES:
        return Reponse(f"Rien n'a été modifié : classe inconnue « {classe} ».")
    if difficulte is not None and difficulte not in DIFFICULTES:
        return Reponse(f"Rien n'a été modifié : difficulté inconnue « {difficulte} ».")
    if niveau is not None and not 1 <= niveau <= 200:
        return Reponse("Rien n'a été modifié : le niveau doit être entre 1 et 200.")
    avant = await charger_etat(ctx)
    try:
        nouveau, changements = await ctx.depot.modifier_grimpeur(
            g.id, ctx.acteur_id, ctx.maintenant, pseudo=nouveau_pseudo, classe=classe,
            difficulte=difficulte, niveau=niveau, discord_user_id=membre_id,
        )
    except ErreurDepot as e:
        return Reponse(f"Rien n'a été modifié : {e}.")
    if not changements:
        return Reponse(f"Rien à changer pour **{g.pseudo}**.")
    noms = {"pseudo_ig": "pseudo", "classe": "classe", "difficulte": "difficulté",
            "niveau_connu": "niveau", "discord_user_id": "membre Discord"}
    details = []
    for champ, (av, ap) in changements.items():
        if champ == "inclus":
            continue
        if champ == "difficulte":
            av, ap = NOM_DIFFICULTE[av], NOM_DIFFICULTE[ap]
        details.append(f"{noms[champ]} : {av if av is not None else '—'} → {ap}")
    texte = f"**{nouveau.pseudo}** modifié. " + " ; ".join(details) + "."
    if "inclus" in changements:
        texte += "\nIl a rattrapé le groupe : il n'est plus retardataire et entre dans la jauge."
    return _avec_effet(texte, avant, await charger_etat(ctx))


async def grimpeur_inclure(ctx: Contexte, pseudo: str, motif: str | None = None) -> Reponse:
    g = await _trouver(ctx, pseudo)
    if isinstance(g, Reponse):
        return g
    avant = await charger_etat(ctx)
    try:
        await ctx.depot.inclure(g.id, motif, ctx.acteur_id, ctx.maintenant)
    except ErreurDepot as e:
        return Reponse(f"Rien n'a changé : {e}.")
    return _avec_effet(f"**{g.pseudo}** est inclus : il entre dans la jauge (maximum et points).",
                       avant, await charger_etat(ctx))


async def grimpeur_pause(ctx: Contexte, pseudo: str, motif: str | None = None) -> Reponse:
    g = await _trouver(ctx, pseudo)
    if isinstance(g, Reponse):
        return g
    if g.statut == "pause":
        return Reponse(f"**{g.pseudo}** est déjà en pause.")
    if g.statut == "exclu":
        return Reponse(f"**{g.pseudo}** est exclu. Utilise `/grimpeur reprendre` d'abord.")
    avant = await charger_etat(ctx)
    await ctx.depot.changer_statut(g.id, "pause", motif, "pause", ctx.acteur_id, ctx.maintenant)
    texte = f"**{g.pseudo}** est en pause : il sort de la jauge. À sa reprise, il devra rattraper le groupe."
    return _avec_effet(texte, avant, await charger_etat(ctx))


async def grimpeur_reprendre(ctx: Contexte, pseudo: str) -> Reponse:
    g = await _trouver(ctx, pseudo)
    if isinstance(g, Reponse):
        return g
    if g.statut == "actif":
        return Reponse(f"**{g.pseudo}** est déjà actif.")
    avant = await charger_etat(ctx)
    repris = await ctx.depot.changer_statut(g.id, "actif", None, "reprise", ctx.acteur_id, ctx.maintenant)
    if est_retardataire(repris):
        texte = (f"**{g.pseudo}** reprend l'ascension en **retardataire** : il rentre dans la jauge en rattrapant "
                 "le grimpeur compté le moins avancé, ou avec `/grimpeur inclure`.")
    else:
        texte = f"**{g.pseudo}** reprend l'ascension : il est déjà au niveau du groupe et compte tout de suite."
    return _avec_effet(texte, avant, await charger_etat(ctx))


async def grimpeur_exclure(ctx: Contexte, pseudo: str, motif: str) -> Reponse:
    """Appelée APRÈS le bouton de confirmation."""
    g = await _trouver(ctx, pseudo)
    if isinstance(g, Reponse):
        return g
    if g.statut == "exclu":
        return Reponse(f"**{g.pseudo}** est déjà exclu.")
    if not motif.strip():
        return Reponse("Rien n'a été enregistré : l'exclusion demande un motif.")
    avant = await charger_etat(ctx)
    await ctx.depot.changer_statut(g.id, "exclu", motif, "exclusion", ctx.acteur_id, ctx.maintenant)
    return _avec_effet(f"**{g.pseudo}** est exclu ({motif}). Il disparaît du site ; ses validations "
                       "restent au journal. `/grimpeur reprendre` annule l'exclusion.", avant, await charger_etat(ctx))


async def grimpeur_voir(ctx: Contexte, pseudo: str) -> Reponse:
    g = await _trouver(ctx, pseudo)
    if isinstance(g, Reponse):
        return g
    membre = await ctx.depot.discord_du_grimpeur(g.id)
    activite = await ctx.depot.derniere_activite(g.id)
    lignes = [
        f"**{g.pseudo}** (n° {g.id}) — {g.classe}, {NOM_DIFFICULTE[g.difficulte]}, {nom_statut(g)}",
        f"Niveau connu : {g.niveau_connu if g.niveau_connu is not None else 'inconnu'}"
        f" · Discord : {f'<@{membre}>' if membre else 'non relié'}"
        f" · Dernière activité : {date_lisible(activite, ctx.fuseau) if activite else 'aucune'}",
    ]
    validations = await ctx.depot.validations_du_grimpeur(g.id)
    if not validations:
        lignes.append("Aucune validation.")
    for lv in validations:
        v = lv.validation
        quoi = "déclaré" if v.source == "declaration" else f"niv. {v.niveau}"
        extra = " · acceptée malgré le cap" if v.forcee else ""
        extra += f" · motif : {lv.motif}" if lv.motif else ""
        extra += f" · preuve : {lv.preuve}" if lv.preuve else ""
        lignes.append(f"• n° {v.id} {lv.contenu} ({quoi}) le {date_lisible(v.realisee_le, ctx.fuseau)}"
                      f" — {NOM_STATUT_VALIDATION[v.statut]}{extra}")
    return Reponse("\n".join(lignes))


async def grimpeur_liste(ctx: Contexte, statut: str | None = None) -> Reponse:
    grimpeurs = await ctx.depot.grimpeurs(statut)
    if not grimpeurs:
        return Reponse("Aucun grimpeur" + (f" {STATUTS_LISTE[statut]}." if statut else "."))
    activites = await ctx.depot.dernieres_activites()
    titre = f"**{len(grimpeurs)} grimpeurs" + (f" {STATUTS_LISTE[statut]}**" if statut else "**")
    lignes = [titre]
    for g in grimpeurs:
        quand = activites.get(g.id)
        lignes.append(
            f"• {g.pseudo} — {g.classe}, {NOM_DIFFICULTE[g.difficulte]}, {nom_statut(g)}"
            + (f", niv. {g.niveau_connu}" if g.niveau_connu else "")
            + f" · activité : {date_lisible(quand, ctx.fuseau) if quand else 'aucune'}"
        )
    return Reponse("\n".join(lignes))


# --- Couche Discord -----------------------------------------------------------------------------

CHOIX_CLASSES = [app_commands.Choice(name=c, value=c) for c in CLASSES]
CHOIX_DIFFICULTES = [app_commands.Choice(name=NOM_DIFFICULTE[d], value=d) for d in DIFFICULTES]
CHOIX_STATUTS = [app_commands.Choice(name=n, value=s) for s, n in STATUTS_LISTE.items()]


async def autocompletion_pseudo(depot: Depot, saisie: str, seulement_retardataires: bool = False
                                ) -> list[app_commands.Choice[str]]:
    grimpeurs = await depot.grimpeurs("retardataire" if seulement_retardataires else None)
    options = [(g.pseudo, g.pseudo) for g in grimpeurs if g.statut != "exclu"]
    options += [(f"{g.pseudo} (exclu)", g.pseudo) for g in grimpeurs if g.statut == "exclu"]
    return [app_commands.Choice(name=n, value=v) for n, v in suggestions(saisie, options)]


class ConfirmationExclusion(discord.ui.View):
    """Deux boutons sous la réponse éphémère : rien n'est écrit avant « Confirmer »."""

    def __init__(self, groupe: GroupeGrimpeur, pseudo: str, motif: str) -> None:
        super().__init__(timeout=120)
        self.groupe, self.pseudo, self.motif = groupe, pseudo, motif

    @discord.ui.button(label="Confirmer l'exclusion", style=discord.ButtonStyle.danger)
    async def confirmer(self, interaction: discord.Interaction, _bouton: discord.ui.Button) -> None:
        if not await autoriser(interaction, self.groupe.admin_role_id):
            return
        rep = await grimpeur_exclure(self.groupe.ctx(interaction), self.pseudo, self.motif)
        self.stop()
        await interaction.response.edit_message(content=rep.texte, view=None)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def annuler(self, interaction: discord.Interaction, _bouton: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(content="Exclusion abandonnée, rien n'a changé.", view=None)


@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
class GroupeGrimpeur(app_commands.Group):
    def __init__(self, depot: Depot, guild_id: int, admin_role_id: int, fuseau: str) -> None:
        super().__init__(name="grimpeur", description="Le registre des grimpeurs")
        self.depot, self.guild_id, self.admin_role_id, self.fuseau = depot, guild_id, admin_role_id, fuseau

    def ctx(self, interaction: discord.Interaction) -> Contexte:
        return contexte_de(interaction, self.depot, self.guild_id, self.fuseau)

    async def _pseudos(self, _interaction: discord.Interaction, saisie: str):
        return await autocompletion_pseudo(self.depot, saisie)

    async def _retardataires(self, _interaction: discord.Interaction, saisie: str):
        return await autocompletion_pseudo(self.depot, saisie, seulement_retardataires=True)

    @app_commands.command(name="ajouter", description="Inscrire un grimpeur")
    @app_commands.describe(pseudo="Pseudo en jeu (2 à 30 caractères)", membre="Son compte Discord (facultatif)")
    @app_commands.choices(classe=CHOIX_CLASSES, difficulte=CHOIX_DIFFICULTES)
    async def ajouter(self, interaction: discord.Interaction, pseudo: app_commands.Range[str, 2, 30],
                      classe: str, difficulte: str, membre: discord.Member | None = None) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        rep = await grimpeur_ajouter(self.ctx(interaction), pseudo, classe, difficulte, membre.id if membre else None)
        await envoyer(interaction, rep)

    @app_commands.command(name="modifier", description="Modifier un grimpeur")
    @app_commands.choices(classe=CHOIX_CLASSES, difficulte=CHOIX_DIFFICULTES)
    async def modifier(self, interaction: discord.Interaction, pseudo: str,
                       nouveau_pseudo: app_commands.Range[str, 2, 30] | None = None,
                       classe: str | None = None, difficulte: str | None = None,
                       niveau: app_commands.Range[int, 1, 200] | None = None,
                       membre: discord.Member | None = None) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        rep = await grimpeur_modifier(self.ctx(interaction), pseudo, nouveau_pseudo, classe, difficulte,
                                      niveau, membre.id if membre else None)
        await envoyer(interaction, rep)

    @app_commands.command(name="inclure", description="Faire entrer un retardataire dans le maximum")
    async def inclure(self, interaction: discord.Interaction, pseudo: str, motif: str | None = None) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        await envoyer(interaction, await grimpeur_inclure(self.ctx(interaction), pseudo, motif))

    @app_commands.command(name="pause", description="Mettre un grimpeur en pause (il sort de la jauge)")
    async def pause(self, interaction: discord.Interaction, pseudo: str, motif: str | None = None) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        await envoyer(interaction, await grimpeur_pause(self.ctx(interaction), pseudo, motif))

    @app_commands.command(name="reprendre", description="Remettre un grimpeur actif (après pause ou exclusion)")
    async def reprendre(self, interaction: discord.Interaction, pseudo: str) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        await envoyer(interaction, await grimpeur_reprendre(self.ctx(interaction), pseudo))

    @app_commands.command(name="exclure", description="Exclure un grimpeur (demande une confirmation)")
    async def exclure(self, interaction: discord.Interaction, pseudo: str, motif: str) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        g = await self.depot.grimpeur_par_pseudo(pseudo)
        if g is None:
            await envoyer(interaction, Reponse(f"Aucun grimpeur nommé « {pseudo} »."))
            return
        await interaction.response.send_message(
            f"Exclure **{g.pseudo}** ? Motif : {motif}", ephemeral=True,
            view=ConfirmationExclusion(self, g.pseudo, motif),
        )

    @app_commands.command(name="voir", description="La fiche complète d'un grimpeur")
    async def voir(self, interaction: discord.Interaction, pseudo: str) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        await envoyer(interaction, await grimpeur_voir(self.ctx(interaction), pseudo))

    @app_commands.command(name="liste", description="Le registre, filtrable par statut")
    @app_commands.choices(statut=CHOIX_STATUTS)
    async def liste(self, interaction: discord.Interaction, statut: str | None = None) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        await envoyer(interaction, await grimpeur_liste(self.ctx(interaction), statut))

    # La même autocomplétion des pseudos sert à toutes les sous-commandes.
    modifier.autocomplete("pseudo")(_pseudos)
    pause.autocomplete("pseudo")(_pseudos)
    reprendre.autocomplete("pseudo")(_pseudos)
    exclure.autocomplete("pseudo")(_pseudos)
    voir.autocomplete("pseudo")(_pseudos)
    inclure.autocomplete("pseudo")(_retardataires)
