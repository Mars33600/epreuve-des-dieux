"""Le tableau de bord du grimpeur (E4) : sa progression personnelle, comme le tableau de bord de duffus.fr.

    GET /tableau-de-bord                    onglet « Progression » : vue d'ensemble, un bloc par étage, à faire ensuite
    GET /tableau-de-bord?onglet=succes      onglet « Succès de donjon » : les 5 cases de chaque donjon, tous les
                                            étages ouverts ou terminés (?reste=1 : seulement ce qui reste)
    GET /grimpeurs/{id}                     le tableau de bord d'un autre grimpeur (mêmes onglets) : lecture seule,
                                            cochable pour un admin (motif obligatoire) ; le sien → /tableau-de-bord
    GET /grimpeurs/moi                      ancienne adresse de « Ma fiche » → /tableau-de-bord

Retour de recette v4 : « Ma fiche » et le tableau de bord faisaient doublon. Il ne reste qu'une présentation,
qui s'adapte à qui la regarde : soi (cochable, formulaire de profil, blocs à faire ensuite), un autre grimpeur
(cases désactivées, ses blocs du guide en lecture), un admin (le mode édition de l'ancienne fiche : `data-cible`
sur la page, `app.js` envoie `grimpeur_id` et le motif, l'API contrôle et journalise).

L'étage en cours s'affiche au premier niveau ; les étages précédents sont pliés dans « Étages précédents »
(un `<details>` par étage) : la page ne grossit pas d'une carte par semaine. Le lien « N donjons à
compléter » vise l'ancre `#etageN`, que `app.js` déplie à l'arrivée.

Rien de nouveau en base : les chiffres viennent de `charger_vue_etage` (la même source que les pages d'étage)
et les cases sont celles du lot B, cochées par `POST /api/coches` via `app.js` (mêmes attributs `data-ref`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from epreuve.domaine.classes import CLASSES
from epreuve.domaine.modeles import Etage, Grimpeur
from epreuve.domaine.visibilite import etage_cochable
from epreuve.web.auth import Refus, exiger_grimpeur
from epreuve.web.pages import INTROUVABLE, MESSAGES_FICHE, peut_cocher_soi
from epreuve.web.rendu import rendre
from epreuve.web.vues import VueEtage, charger_vue_etage, separer_courant

routeur = APIRouter()
NB_A_FAIRE = 6


@dataclass
class BlocEtage:
    vue: VueEtage
    cochable: bool
    points: int
    faits: int
    total: int
    donjons_restants: int
    blocs_faits: int
    blocs_total: int
    donjons_vaincus: int
    donjons_total: int
    succes_faits: int
    succes_total: int


async def blocs_du_grimpeur(request: Request, g: Grimpeur, cochable: Callable[[Etage], bool]) -> list[BlocEtage]:
    """Un bloc par étage ouvert ou terminé, du plus récent au plus ancien. `cochable` dit, étage par étage, si
    celui qui regarde peut cocher pour `g` (soi selon son statut, un admin toujours, un autre jamais)."""
    s = request.app.state
    grimpeurs = await s.depot.grimpeurs()
    etages = sorted((e for e in await s.depot.etages() if etage_cochable(e)), key=lambda e: -e.numero)
    blocs = []
    for e in etages:
        vue = await charger_vue_etage(s.depot, e, s.regles, grimpeurs)
        faits, total = vue.avancement(g.id)
        coches = vue.coches_de(g.id)
        restants = sum(1 for d in vue.contenu.donjons
                       if any(c.id not in coches.cases for c in vue.contenu.cases_du_donjon(d.id)))
        contenu = vue.contenu
        classiques = [vue.classique(d.id) for d in contenu.donjons]
        blocs.append(BlocEtage(
            vue, cochable(e), vue.points(g.id), faits, total, restants,
            sum(1 for b in contenu.blocs if b.id in coches.blocs), len(contenu.blocs),
            sum(1 for c in classiques if c and c.id in coches.cases), len(contenu.donjons),
            sum(1 for c in contenu.cases if c.id in coches.cases), len(contenu.cases)))
    return blocs


def a_faire(blocs: list[BlocEtage], grimpeur_id: int) -> list[tuple[int, object]]:
    """Les premiers blocs pas encore terminés de l'étage ouvert (sinon du plus récent), les principaux d'abord,
    puis dans l'ordre du guide."""
    ouvert = next((b for b in blocs if b.vue.etage.statut == "ouvert"), blocs[0] if blocs else None)
    if ouvert is None:
        return []
    coches = ouvert.vue.coches_de(grimpeur_id)
    restants = [b for b in sorted(ouvert.vue.contenu.blocs, key=lambda b: (b.nature != "principale", b.ordre))
                if b.id not in coches.blocs]
    return [(ouvert.vue.etage.numero, b) for b in restants[:NB_A_FAIRE]]


def onglet_valide(onglet: str) -> str:
    return "succes" if onglet == "succes" else "progression"


async def rendre_tableau(request: Request, g: Grimpeur, onglet: str, reste: int, cochable: Callable[[Etage], bool],
                         *, soi: bool, edition: bool = False, plus: dict | None = None):
    """Le gabarit commun : `soi` ajoute le profil et les blocs à faire ensuite ; `edition` (admin) pose
    `data-cible` et le champ motif. `base` est l'adresse des onglets, pour qu'ils restent sur la même vue."""
    blocs = await blocs_du_grimpeur(request, g, cochable)
    faits, total = sum(b.faits for b in blocs), sum(b.total for b in blocs)
    courant, precedents = separer_courant(blocs, lambda b: b.vue.etage)
    return await rendre(request, "tableau.html", {
        "onglet": onglet_valide(onglet), "reste": bool(reste), "g": g, "blocs": blocs, "courant": courant,
        "precedents": precedents, "faits": faits, "total": total, "soi": soi, "edition": edition,
        "base": "/tableau-de-bord" if soi else f"/grimpeurs/{g.id}",
        "points": sum(b.points for b in blocs), "points_max": sum(b.vue.points_max for b in blocs),
        "a_faire": a_faire(blocs, g.id) if soi else [], **(plus or {})})


@routeur.get("/tableau-de-bord")
async def tableau_de_bord(request: Request, onglet: str = "progression", reste: int = 0, fait: str = "",
                          erreur: str = ""):
    v = await exiger_grimpeur(request)
    if v.grimpeur is None:  # un admin sans fiche n'a pas de progression
        return await rendre(request, "erreur.html", {"message": "Le tableau de bord est celui d'un grimpeur : "
                                                     "tu n'as pas de fiche.", "statut": 409}, 409)
    regles = request.app.state.regles
    return await rendre_tableau(
        request, v.grimpeur, onglet, reste, lambda e: peut_cocher_soi(v, e, regles), soi=True,
        plus={"classes": CLASSES, "message": "Fiche enregistrée." if fait else "",
              "erreur": MESSAGES_FICHE.get(erreur, "")})


@routeur.get("/grimpeurs/moi")
async def ancienne_fiche_moi():
    """L'ancienne adresse de « Ma fiche » (signets) : déclarée avant `/grimpeurs/{id}`, qui attend un nombre."""
    return RedirectResponse("/tableau-de-bord", status_code=303)


@routeur.get("/grimpeurs/{grimpeur_id}")
async def tableau_d_un_grimpeur(request: Request, grimpeur_id: int, onglet: str = "progression", reste: int = 0):
    """Le tableau de bord d'un autre grimpeur. Mêmes contrôles que l'ancienne fiche : grimpeur connecté (ou admin),
    site ouvert (le teaser est filtré avant, par `securite.FiltreMode`), un exclu est introuvable sauf pour un admin.
    Un admin coche directement (l'ancien `?edition=1` est accepté et ignoré) : le motif obligatoire, exigé par
    `app.js` puis par l'API, empêche une coche par mégarde."""
    v = await exiger_grimpeur(request)
    g = await request.app.state.depot.grimpeur(grimpeur_id)
    if g is None or (g.statut == "exclu" and not v.est_admin):
        raise Refus(404, INTROUVABLE)
    if v.grimpeur_id == g.id:  # son propre tableau : une seule adresse, avec ses onglets
        onglet = onglet_valide(onglet)
        suite = "" if onglet == "progression" else "?onglet=succes" + ("&reste=1" if reste else "")
        return RedirectResponse("/tableau-de-bord" + suite, status_code=303)
    edition = v.est_admin
    return await rendre_tableau(request, g, onglet, reste, lambda e: edition, soi=False, edition=edition)
