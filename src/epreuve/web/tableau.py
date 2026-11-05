"""Le tableau de bord du grimpeur (E4) : sa progression personnelle, comme le tableau de bord de duffus.fr.

    GET /tableau-de-bord                    onglet « Progression » : vue d'ensemble, un bloc par étage, à faire ensuite
    GET /tableau-de-bord?onglet=succes      onglet « Succès de donjon » : les 5 cases de chaque donjon, tous les
                                            étages ouverts ou terminés (?reste=1 : seulement ce qui reste)

L'étage en cours s'affiche au premier niveau ; les étages précédents sont pliés dans « Étages précédents »
(un `<details>` par étage) : la page ne grossit pas d'une carte par semaine. Le lien « N donjons à
compléter » vise l'ancre `#etageN`, que `app.js` déplie à l'arrivée.

Rien de nouveau en base : les chiffres viennent de `charger_vue_etage` (la même source que les pages d'étage)
et les cases sont celles du lot B, cochées par `POST /api/coches` via `app.js` (mêmes attributs `data-ref`).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Request

from epreuve.domaine.visibilite import etage_cochable
from epreuve.web.auth import exiger_grimpeur
from epreuve.web.pages import peut_cocher_soi
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


async def blocs_du_grimpeur(request: Request, v) -> list[BlocEtage]:
    """Un bloc par étage ouvert ou terminé, du plus récent au plus ancien."""
    s = request.app.state
    g = v.grimpeur
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
            vue, peut_cocher_soi(v, e, s.regles), vue.points(g.id), faits, total, restants,
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


@routeur.get("/tableau-de-bord")
async def tableau_de_bord(request: Request, onglet: str = "progression", reste: int = 0):
    v = await exiger_grimpeur(request)
    onglet = "succes" if onglet == "succes" else "progression"
    if v.grimpeur is None:  # un admin sans fiche n'a pas de progression
        return await rendre(request, "erreur.html", {"message": "Le tableau de bord est celui d'un grimpeur : "
                                                     "tu n'as pas de fiche.", "statut": 409}, 409)
    blocs = await blocs_du_grimpeur(request, v)
    faits, total = sum(b.faits for b in blocs), sum(b.total for b in blocs)
    courant, precedents = separer_courant(blocs, lambda b: b.vue.etage)
    return await rendre(request, "tableau.html", {
        "onglet": onglet, "reste": bool(reste), "g": v.grimpeur, "blocs": blocs, "courant": courant,
        "precedents": precedents, "faits": faits, "total": total,
        "points": sum(b.points for b in blocs), "points_max": sum(b.vue.points_max for b in blocs),
        "a_faire": a_faire(blocs, v.grimpeur.id)})
