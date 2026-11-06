"""L'ouverture automatique de l'étage suivant et son annonce Discord (demande de Shadoaze).

Quand la jauge se remplit (une coche, un admin qui gèle un grimpeur ou baisse le palier, un masquage…),
le site ouvre l'étage suivant lui-même, sans attendre un admin. La décision vient du domaine
(`ouverture.ouvrir_automatiquement` : règle active, site ouvert, `peut_ouvrir` d'accord, délai de grâce écoulé) ;
ici, on lit l'état, on écrit, on annonce.

Le délai de grâce (`regles.delai_grace_secondes`, 60 s) : un étage ouvert ne se referme pas, alors une coche par
erreur qui remplit la jauge ne doit pas l'ouvrir aussitôt. Chaque regard note depuis quand la jauge est pleine
(`s.pleine_depuis`, {id de l'étage en cours: instant}) ou efface cette note si elle ne l'est plus ; l'étage
s'ouvre quand la jauge est pleine depuis au moins le délai. La note vit en mémoire : une seule machine sert le
site, et après un redémarrage le compte repart de zéro, ce qui retarde l'ouverture d'une minute au pire. Pas de
table ni de migration pour si peu.

Deux déclencheurs :
- `apres_ecriture`, appelé par chaque route qui peut remplir (ou vider) la jauge, juste après son écriture : il
  note ou efface « pleine depuis », et n'ouvre que si le délai est déjà écoulé (délai 0, ou jauge déjà pleine) ;
- `veiller`, une boucle lancée par `main.py` : elle ouvre à la fin du délai de grâce, et aussi à la date plancher
  si la jauge était pleine AVANT (plus personne ne coche ensuite). Elle regarde chaque minute, et raccourcit son
  attente pour se réveiller pile à la fin du délai : l'étage s'ouvre ~60 s après la coche, pas 119 s.

La même boucle annonce le lancement du site (`annoncer_lancement`), une seule fois : la ligne de journal est
réservée en base AVANT l'envoi (index unique, voir `depot.reserver_annonce_lancement`). Pour partir à 17 h 00
pile, la boucle raccourcit la dernière attente avant `site_ouvert_le` (`delai_avant_regard`).

Concurrence : deux coches simultanées peuvent toutes deux voir la jauge pleine. `depot.ouvrir_etage` verrouille
les étages (FOR UPDATE) et refuse un étage déjà ouvert (EtatInvalide) : la seconde tentative échoue sans rien
écrire, et on l'ignore. Un étage ne s'ouvre donc qu'une fois, et jamais deux étages d'un coup (chaque tentative
vise « l'étage ouvert + 1 » de l'état qu'elle a lu).

L'annonce part après la réponse (tâche de fond de FastAPI, donc après la transaction validée) : un échec de
Discord est journalisé et n'annule jamais l'ouverture.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import BackgroundTasks, Request

from epreuve.db.depot import EtatInvalide, Introuvable
from epreuve.discord.webhook import poster_webhook
from epreuve.domaine.annonce import (
    JOURNAL_LANCEMENT,
    annonce_lancement,
    annonce_ouverture,
    delai_avant_regard,
    doit_annoncer_lancement,
)
from epreuve.domaine.mode_site import mode_effectif
from epreuve.domaine.modeles import Etage
from epreuve.domaine.ouverture import (
    ACTEUR_SYSTEME,
    bilan_etage,
    ouvrir_automatiquement,
    pleine_depuis,
    reste_avant_ouverture,
)
from epreuve.web.vues import charger_vue_etage

journal = logging.getLogger("epreuve.ouverture")
PERIODE = 60.0  # secondes entre deux regards de la boucle : la date plancher est à la minute


async def ouvrir_si_pret(s) -> Etage | None:
    """Ouvre l'étage suivant si le domaine le permet ; renvoie l'étage ouvert, ou None (rien à faire, ou un
    autre vient de l'ouvrir). `s` : l'état de l'application (depot, config, regles, horloge, pleine_depuis).

    La jauge est relue à chaque appel, juste avant `ouvrir_etage` : une décoche arrivée pendant le délai de
    grâce a effacé la note, et l'étage reste fermé."""
    if s.depot is None:
        return None
    etages = await s.depot.etages()
    en_cours = next((e for e in etages if e.statut == "ouvert"), None)
    if en_cours is None:
        s.pleine_depuis = {}
        return None
    prochain = next((e for e in etages if e.numero == en_cours.numero + 1), None)
    vue = await charger_vue_etage(s.depot, en_cours, s.regles)
    maintenant = s.horloge()
    # Pas d'await entre la lecture et l'écriture de la note : deux coches simultanées ne s'entremêlent pas ici.
    # Une seule entrée, celle de l'étage en cours : la note d'un étage terminé ne compte pas pour le suivant.
    depuis = pleine_depuis(vue.jauge, s.pleine_depuis.get(en_cours.id), maintenant)
    s.pleine_depuis = {en_cours.id: depuis} if depuis is not None else {}
    mode = mode_effectif(s.config.site_mode, s.config.site_ouvert_le, maintenant)
    if prochain is None or not ouvrir_automatiquement(vue.jauge, en_cours, prochain, maintenant, s.regles, mode,
                                                       s.config.ouverture_auto_teaser, pleine_depuis=depuis):
        return None
    try:
        ouvert = await s.depot.ouvrir_etage(prochain.numero, bilan_etage(vue.jauge, maintenant, False, None),
                                            ACTEUR_SYSTEME, maintenant)
    except (EtatInvalide, Introuvable):
        return None  # une coche ou un admin simultané l'a ouvert d'abord : rien en double
    s.pleine_depuis = {}
    journal.info("étage %d ouvert automatiquement", ouvert.numero)
    return ouvert


def prochain_regard(s, periode: float) -> float:
    """Secondes avant le prochain regard de la veille : la période, raccourcie pour tomber pile sur le lancement
    du site ou sur la fin du délai de grâce d'une jauge pleine. Une coche qui remplit la jauge pendant que la
    veille dort est vue au regard suivant (moins d'une période plus tard), qui se rendort juste le reste."""
    maintenant = s.horloge()
    attente = delai_avant_regard(maintenant, s.config.site_ouvert_le, periode)
    reste = reste_avant_ouverture(min(s.pleine_depuis.values(), default=None), maintenant, s.regles)
    return reste if reste is not None and reste < attente else attente


async def annoncer(s, etage: Etage) -> bool:
    """Poste l'annonce du Gardien de la Tour ; False sans webhook configuré, pendant le teaser (une ouverture
    de recette par un admin ne doit pas prévenir tout le serveur) ou si Discord échoue."""
    url, cfg = s.config.discord_webhook_annonces, s.config
    if url is None or mode_effectif(cfg.site_mode, cfg.site_ouvert_le, s.horloge()) != "ouvert":
        return False
    return await poster_webhook(url.get_secret_value(), annonce_ouverture(etage, s.config.site_url),
                                transport=getattr(s, "transport_webhook", None))


async def annoncer_lancement(s) -> bool:
    """Poste l'annonce du lancement du site si c'est l'heure ; True seulement si Discord l'a acceptée.

    Sans webhook : rien, pas même la réservation (configuré plus tard dans la fenêtre, il annoncera encore).
    Mode forcé en teaser à l'heure dite : rien non plus, le site n'est pas ouvert. Sinon, on réserve la ligne
    de journal puis on envoie ; un échec de Discord est journalisé et jamais réessayé (la ligne est prise) :
    mieux vaut une annonce manquée qu'un second @everyone."""
    url, cfg = s.config.discord_webhook_annonces, s.config
    if url is None or s.depot is None:
        return False
    maintenant = s.horloge()
    if mode_effectif(cfg.site_mode, cfg.site_ouvert_le, maintenant) != "ouvert":
        return False
    # Hors de la fenêtre, on ne lit même pas la base : c'est le cas de toutes les minutes sauf six heures.
    if not doit_annoncer_lancement(maintenant, cfg.site_ouvert_le, False):
        return False
    deja = bool(await s.depot.journal(1, type_=JOURNAL_LANCEMENT))
    if not doit_annoncer_lancement(maintenant, cfg.site_ouvert_le, deja):
        return False
    if not await s.depot.reserver_annonce_lancement(maintenant):
        return False  # une autre veille l'a réservée entre notre lecture et notre écriture
    envoye = await poster_webhook(url.get_secret_value(), annonce_lancement(cfg.site_url),
                                  transport=getattr(s, "transport_webhook", None))
    if envoye:
        journal.info("lancement du site annoncé sur Discord")
    else:
        journal.warning("annonce du lancement non envoyée : pas de nouvel essai (déjà inscrite au journal)")
    return envoye


async def apres_ecriture(request: Request, taches: BackgroundTasks) -> Etage | None:
    """À appeler après une écriture qui peut remplir la jauge. L'écriture de l'utilisateur est déjà validée :
    une erreur imprévue ici est journalisée et ne change pas sa réponse."""
    s = request.app.state
    try:
        ouvert = await ouvrir_si_pret(s)
    except Exception:  # noqa: BLE001 — l'ouverture auto ne doit jamais faire échouer la coche qui l'a déclenchée
        journal.exception("ouverture automatique impossible")
        return None
    if ouvert is not None:
        taches.add_task(annoncer, s, ouvert)
    return ouvert


async def veiller(s, attendre=asyncio.sleep, periode: float = PERIODE) -> None:
    """La boucle de fond : un regard au démarrage, puis toutes les `periode` secondes (`attendre` injectable),
    sauf une attente raccourcie pour tomber pile sur le lancement ou la fin d'un délai de grâce."""
    while True:
        try:
            await annoncer_lancement(s)
        except Exception:  # noqa: BLE001 — séparé de l'ouverture : une panne de l'un n'empêche pas l'autre
            journal.exception("annonce du lancement impossible")
        try:
            ouvert = await ouvrir_si_pret(s)
            if ouvert is not None:
                await annoncer(s, ouvert)
        except Exception:  # noqa: BLE001 — une base indisponible ne doit pas arrêter la boucle
            journal.exception("ouverture automatique impossible")
        await attendre(prochain_regard(s, periode))
