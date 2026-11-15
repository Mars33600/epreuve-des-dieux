"""Le recensement des métiers de la guilde (demande de BillyBarkMan, 15/11).

    GET  /metiers                 qui a quel métier ; `?metier=bijoutier&min=25` : qui peut fabriquer à ce niveau
    POST /grimpeurs/moi/metiers   déclarer ses métiers (depuis le tableau de bord)

Chacun tient ses niveaux à jour lui-même (règle de confiance, comme les coches) ; la page montre la date du dernier
changement, pour repérer un niveau qui date.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from epreuve.domaine.metiers import FAMILLES, METIERS, NIVEAU_MAX, PAR_CLE, artisans, lire_niveaux
from epreuve.web.auth import Refus, exiger_grimpeur, verifier_ecriture
from epreuve.web.rendu import rendre

routeur = APIRouter()


@routeur.get("/metiers")
async def page_metiers(request: Request, metier: str = "", min: str = ""):  # noqa: A002 (« min » : l'adresse lisible)
    await exiger_grimpeur(request)
    depot = request.app.state.depot
    grimpeurs = {g.id: g for g in await depot.grimpeurs() if g.statut != "exclu"}
    niveaux = [n for n in await depot.metiers() if n.grimpeur_id in grimpeurs]
    minimum = int(min) if min.isdigit() and 1 <= int(min) <= NIVEAU_MAX else 1
    choisi = PAR_CLE.get(metier)
    par_metier = {m: artisans(niveaux, m) for m in PAR_CLE}
    total_famille = {f: sum(len(par_metier[m.cle]) for m in METIERS if m.famille == f) for f, _ in FAMILLES}
    return await rendre(request, "metiers.html", {
        "grimpeurs": grimpeurs, "par_metier": par_metier, "total_famille": total_famille,
        "choisi": choisi, "minimum": minimum, "resultat": artisans(niveaux, choisi.cle, minimum) if choisi else None})


@routeur.post("/grimpeurs/moi/metiers")
async def declarer_metiers(request: Request):
    v = await verifier_ecriture(request)
    if v.grimpeur is None or v.grimpeur.statut == "exclu":
        raise Refus(403, "Tu n'as pas de fiche à modifier.")
    form = await request.form()
    try:
        niveaux = lire_niveaux({cle: str(form.get(f"metier_{cle}", "")) for cle in PAR_CLE})
    except ValueError:
        return RedirectResponse("/tableau-de-bord?erreur=metier#mesMetiers", status_code=303)
    s = request.app.state
    await s.depot.regler_metiers(v.grimpeur.id, niveaux, v.discord_id, s.horloge())
    return RedirectResponse("/tableau-de-bord?fait=metiers#mesMetiers", status_code=303)
