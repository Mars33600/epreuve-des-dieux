"""Les outils de duffus.fr, sans les tutoriels (E4). Tous réservés aux grimpeurs connectés.

    GET /outils                       la liste des outils
    GET /outils/almanax               l'offrande du jour (?jour=AAAA-MM-JJ) et les 14 jours suivants
    GET /outils/calculateur-drop      taux de drop selon la prospection (calcul dans outils.js)
    GET /outils/xp-metiers            simulateur d'XP de métier (outils.js + /outils/donnees/craft.json)
    GET /outils/craft                 module de craft : liste de recettes, ressources à réunir (idem)
    GET /outils/elevage               croisements d'élevage : montures obtenues (outils.js + montures.json)
    GET /outils/classes[/{id}]        les 19 classes et leurs sorts, niveau par niveau
    GET /outils/donnees/{nom}.json    craft ou montures, lus par outils.js

Ce que Duffus garde pour chaque utilisateur (plans de craft, séances d'XP, montures obtenues) reste ici dans le
navigateur (`localStorage`) : le site ne stocke rien de plus, et n'a jamais lu les données d'un utilisateur de Duffus.
Pas d'équivalent de la carte interactive : ses tuiles sont des images du stockage de Duffus, qu'on ne recopie pas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from epreuve.outils import lecture
from epreuve.web.auth import Refus, exiger_grimpeur
from epreuve.web.rendu import rendre

routeur = APIRouter(prefix="/outils")
PARIS = ZoneInfo("Europe/Paris")
JOURS_SUIVANTS = 14


@dataclass(frozen=True)
class Outil:
    chemin: str
    nom: str
    resume: str


OUTILS = (
    Outil("almanax", "Almanax", "L'offrande du jour, son bonus, et les quatorze jours à venir."),
    Outil("calculateur-drop", "Calculateur de drop", "Ta vraie chance de drop selon la prospection et les bonus."),
    Outil("classes", "Classes et sorts", "Les 19 classes, leurs sorts et leurs caractéristiques par niveau."),
    Outil("elevage", "Croisements d'élevage", "Coche les montures que tu as obtenues, génération par génération."),
    Outil("craft", "Module de craft", "Une liste de recettes, et toutes les ressources à réunir."),
    Outil("xp-metiers", "Simulateur d'XP des métiers", "Combien de crafts pour passer du niveau X au niveau Y."),
)


@routeur.get("")
async def liste(request: Request):
    await exiger_grimpeur(request)
    return await rendre(request, "outils/index.html", {"outils": OUTILS})


@routeur.get("/almanax")
async def almanax(request: Request, jour: str = ""):
    await exiger_grimpeur(request)
    premier, dernier = lecture.bornes_almanax()
    aujourdhui = request.app.state.horloge().astimezone(PARIS).date()
    try:
        choisi = date.fromisoformat(jour) if jour else aujourdhui
    except ValueError:
        raise Refus(404, "Introuvable.") from None
    suivants = [o for i in range(1, JOURS_SUIVANTS + 1) if (o := lecture.offrande(choisi + timedelta(days=i)))]
    return await rendre(request, "outils/almanax.html", {
        "offrande": lecture.offrande(choisi), "choisi": choisi, "aujourdhui": aujourdhui, "suivants": suivants,
        "veille": choisi - timedelta(days=1) if choisi > premier else None,
        "lendemain": choisi + timedelta(days=1) if choisi < dernier else None,
        "premier": premier, "dernier": dernier})


@routeur.get("/calculateur-drop")
async def calculateur_drop(request: Request):
    await exiger_grimpeur(request)
    return await rendre(request, "outils/drop.html")


@routeur.get("/xp-metiers")
async def xp_metiers(request: Request):
    await exiger_grimpeur(request)
    return await rendre(request, "outils/xp_metiers.html")


@routeur.get("/craft")
async def craft(request: Request):
    await exiger_grimpeur(request)
    return await rendre(request, "outils/craft.html")


@routeur.get("/elevage")
async def elevage(request: Request):
    await exiger_grimpeur(request)
    return await rendre(request, "outils/elevage.html")


@routeur.get("/classes")
async def classes(request: Request):
    await exiger_grimpeur(request)
    return await rendre(request, "outils/classes.html", {"classes": lecture.classes(), "classe": None})


@routeur.get("/classes/{classe_id}")
async def classe(request: Request, classe_id: int):
    await exiger_grimpeur(request)
    trouvee = next((c for c in lecture.classes() if c["id"] == classe_id), None)
    if trouvee is None:
        raise Refus(404, "Introuvable.")
    return await rendre(request, "outils/classes.html", {"classes": lecture.classes(), "classe": trouvee})


@routeur.get("/donnees/{nom}.json")
async def donnees(request: Request, nom: str):
    await exiger_grimpeur(request)
    if nom not in lecture.PUBLIQUES:
        raise Refus(404, "Introuvable.")
    return FileResponse(lecture.fichier(nom), media_type="application/json",
                        headers={"Cache-Control": "private, max-age=3600"})
