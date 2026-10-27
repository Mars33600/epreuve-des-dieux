"""/etage etat : la jauge à points de l'étage en cours, son détail et le verdict.

Au jalon bêta, seule la sous-commande « etat » existe (ouvrir, seuil : jalon lancement).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

from epreuve.bot.commun import Contexte, Reponse, autoriser, contexte_de, differer, envoyer
from epreuve.db.depot import Depot
from epreuve.domaine.jauges import EtatEtage, calculer_etat_etage

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
        "octobre", "novembre", "décembre")  # fmt: skip
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def date_longue(d: datetime, fuseau: ZoneInfo) -> str:
    """« vendredi 13 novembre à 17 h » (sans dépendre de la langue du système)."""
    local = d.astimezone(fuseau)
    heure = f"{local.hour} h" + (f" {local.minute:02d}" if local.minute else "")
    return f"{JOURS[local.weekday()]} {local.day} {MOIS[local.month - 1]} à {heure}"


async def charger_etat(ctx: Contexte) -> EtatEtage | None:
    """L'état de l'étage ouvert, calculé par le domaine. None s'il n'y a pas d'étage ouvert."""
    inst = await ctx.depot.charger_instantane()
    etage = inst.etage_ouvert
    if etage is None:
        return None
    return calculer_etat_etage(etage, inst.paliers, inst.grimpeurs, inst.validations, ctx.maintenant)


def texte_maximum(etat: EtatEtage) -> str:
    """« Maximum 24 = 4 Collectionneurs × 3 + 4 Éclaireurs × 2 + 4 Aventuriers × 1. Seuil 75 % → 18. »"""
    d, j = etat.comptes_par_difficulte, etat.jauge
    return (f"Maximum {j.maximum} = {d['hard']} Collectionneurs × 3 + {d['med']} Éclaireurs × 2 + "
            f"{d['easy']} Aventuriers × 1. Seuil {j.seuil_pourcent} % → {j.seuil}.")


def texte_verdict(etat: EtatEtage, fuseau: ZoneInfo) -> str:
    suivant = etat.etage.numero + 1
    plancher = etat.etage.date_plancher_suivant
    if etat.jauge.maximum == 0:
        return "Aucun grimpeur actif : la jauge ne peut pas se remplir."
    if etat.deblocable:
        phrase = f"Le seuil est atteint : un admin peut ouvrir l'étage {suivant}."
    elif etat.jauge.pleine:
        # Pleine mais pas déblocable : c'est forcément que la date plancher n'est pas passée.
        quand = date_longue(plancher, fuseau)
        phrase = f"Le seuil est atteint. L'étage {suivant} pourra s'ouvrir le {quand}, pas avant."
    else:
        pas_avant = f", et pas avant le {date_longue(plancher, fuseau)}" if plancher else ""
        phrase = f"L'étage {suivant} s'ouvre quand la jauge atteint le seuil{pas_avant}."
    morceaux = [f"{etat.n_comptes} grimpeurs actifs"]
    if etat.n_pause:
        morceaux.append(f"{etat.n_pause} en pause")
    return f"{phrase} {', '.join(morceaux)}."


def texte_etat(etat: EtatEtage, fuseau: ZoneInfo, libelles: list[str]) -> str:
    e, j = etat.etage, etat.jauge
    reste = "seuil atteint" if j.pleine else f"il en manque {j.manquants}"
    lignes = [
        f"**Étage {e.numero} · {e.nom}** — cap {e.level_cap}",
        f"Jauge : **{j.points} points sur {j.seuil} requis** — {reste}",
        texte_maximum(etat),
    ]
    for rang, (libelle, n) in enumerate(zip(libelles, etat.grimpeurs_par_palier, strict=False), start=1):
        lignes.append(f"• Palier {rang} · {libelle} : {n} grimpeur{'s' if n > 1 else ''}")
    lignes.append(texte_verdict(etat, fuseau))
    return "\n".join(lignes)


async def etage_etat(ctx: Contexte, public: bool = False) -> Reponse:
    etat = await charger_etat(ctx)
    if etat is None:
        return Reponse("Aucun étage n'est ouvert pour l'instant.")
    libelles = [p.libelle for p in await ctx.depot.paliers(etat.etage.id)]
    return Reponse(texte_etat(etat, ctx.fuseau, libelles), ephemere=not public)


# --- Couche Discord -----------------------------------------------------------------------------


@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
class GroupeEtage(app_commands.Group):
    def __init__(self, depot: Depot, guild_id: int, admin_role_id: int, fuseau: str) -> None:
        super().__init__(name="etage", description="L'étage en cours")
        self.depot, self.guild_id, self.admin_role_id, self.fuseau = depot, guild_id, admin_role_id, fuseau

    @app_commands.command(name="etat", description="La jauge, son détail et le verdict de l'étage en cours")
    @app_commands.describe(public="Si oui, la réponse est visible de tous dans le salon")
    async def etat(self, interaction: discord.Interaction, public: bool = False) -> None:
        if not await autoriser(interaction, self.admin_role_id):
            return
        await differer(interaction, ephemere=not public)
        ctx = contexte_de(interaction, self.depot, self.guild_id, self.fuseau)
        await envoyer(interaction, await etage_etat(ctx, public))
