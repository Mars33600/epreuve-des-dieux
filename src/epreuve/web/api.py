"""L'API JSON consommée par `app.js` (LOTS, lot B, « API JSON » : forme et codes figés).

    POST /api/coches                         cocher ou décocher (soi-même ; un admin pour un autre, avec motif)
    GET  /api/etages/{n}/manque?type=&id=    « qui ne l'a pas fait ? » pour un élément ou une catégorie

Erreurs : `{"ok": false, "message": "…"}` en français. 401 sans session ; 403 CSRF, Origin, cible non
permise, exclu ou gelé interdit de coche ; 404 élément inconnu, masqué ou d'un étage scellé ; 409 pas de
fiche ; 422 corps invalide ou motif manquant. Aucun identifiant Discord dans les réponses.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from epreuve.db.depot import CocheRefusee, Introuvable
from epreuve.domaine.modeles import ElementRef, Etage, Grimpeur
from epreuve.domaine.visibilite import etage_cochable, peut_modifier_coches
from epreuve.web.auth import MESSAGE_SUSPENDU, Refus, exiger_grimpeur, verifier_ecriture
from epreuve.web.pages import etage_visible, resoudre_quoi
from epreuve.web.vues import categories_json, charger_vue_etage, cle, jauge_json

routeur = APIRouter()
INTROUVABLE = "Cet élément n'existe pas ou n'est pas accessible."


def _corps_invalide() -> Refus:
    return Refus(422, "Requête invalide.")


async def lire_corps(request: Request) -> dict:
    try:
        corps = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError) as e:
        raise _corps_invalide() from e
    if not isinstance(corps, dict):
        raise _corps_invalide()
    type_, id_, cochee = corps.get("type"), corps.get("id"), corps.get("cochee")
    gid, motif = corps.get("grimpeur_id"), corps.get("motif")
    if (type_ not in ("case", "quete", "donjon") or type(id_) is not int or type(cochee) is not bool
            or (gid is not None and type(gid) is not int) or (motif is not None and not isinstance(motif, str))):
        raise _corps_invalide()
    if type_ == "donjon" and not cochee:
        raise Refus(422, "« Tout le donjon » ne sert qu'à cocher.")
    return {"type": type_, "id": id_, "cochee": cochee, "grimpeur_id": gid, "motif": (motif or "").strip() or None}


async def etage_de_l_element(depot, type_: str, id_: int) -> Etage:
    """L'étage ouvert ou terminé qui contient l'élément VISIBLE ; sinon 404 (inconnu, masqué ou scellé)."""
    for etage in await depot.etages():
        if not etage_cochable(etage):
            continue
        c = await depot.contenu_etage(etage.id)
        ids = {"case": {x.id for x in c.cases}, "quete": {x.id for x in c.quetes}, "donjon": {x.id for x in c.donjons}}
        if id_ in ids[type_]:
            return etage
    raise Refus(404, INTROUVABLE)


@routeur.post("/api/coches")
async def coches(request: Request):
    v = await verifier_ecriture(request)
    corps = await lire_corps(request)
    autre = corps["grimpeur_id"] is not None and corps["grimpeur_id"] != v.grimpeur_id
    if autre and v.discord_injoignable:
        raise Refus(503, "Discord ne répond pas : réessaie dans une minute.")
    if autre and not v.est_admin:  # avant le contrôle de la fiche : cocher pour un autre est d'abord interdit
        raise Refus(403, "Tu ne peux cocher que ta propre fiche.")
    v = await exiger_grimpeur(request)
    s = request.app.state
    cible: Grimpeur | None
    if corps["grimpeur_id"] is None or corps["grimpeur_id"] == v.grimpeur_id:
        cible = v.grimpeur
        if cible is None:
            raise Refus(409, "Crée d'abord ta fiche pour cocher.")
        if cible.statut == "exclu":
            raise Refus(403, MESSAGE_SUSPENDU)
        motif = None
    else:
        if not peut_modifier_coches(v.grimpeur_id, v.est_admin, corps["grimpeur_id"]):
            raise Refus(403, "Tu ne peux cocher que ta propre fiche.")
        cible = await s.depot.grimpeur(corps["grimpeur_id"])
        if cible is None:
            raise Refus(404, "Grimpeur introuvable.")
        motif = corps["motif"]
        if motif is None:
            raise Refus(422, "Un motif est obligatoire pour modifier la fiche d'un autre grimpeur.")
    etage = await etage_de_l_element(s.depot, corps["type"], corps["id"])
    maintenant, acteur = s.horloge(), v.discord_id
    try:
        if corps["type"] == "donjon":
            avant = await s.depot.coches_etage(etage.id)
            await s.depot.cocher_donjon(cible.id, corps["id"], acteur, maintenant, s.regles, motif)
            contenu = await s.depot.contenu_etage(etage.id)
            deja = avant.get(cible.id)
            changes = tuple(ElementRef("case", c.id) for c in contenu.cases_du_donjon(corps["id"])
                            if deja is None or c.id not in deja.cases)
        else:
            changes = await s.depot.cocher(cible.id, ElementRef(corps["type"], corps["id"]), corps["cochee"], acteur,
                                           maintenant, s.regles, motif)
    except Introuvable as e:
        raise Refus(404, INTROUVABLE) from e
    except CocheRefusee as e:
        raise Refus(403, "Cette fiche ne peut pas être modifiée pour l'instant.") from e
    except ValueError as e:
        raise Refus(422, "Un motif est obligatoire pour modifier la fiche d'un autre grimpeur.") from e
    vue = await charger_vue_etage(s.depot, etage, s.regles)
    return JSONResponse({
        "ok": True, "changement": bool(changes),
        "moi": {"points": vue.points(cible.id), "categories": categories_json(vue.categories(cible.id))},
        "jauge": jauge_json(vue.jauge),
        "compteurs": {cle(r): vue.compteurs.get(cle(r), 0) for r in changes},
    }, headers={"Cache-Control": "no-store"})


@routeur.get("/api/etages/{numero}/manque")
async def manque(request: Request, numero: int, type: str = "", id: str = ""):  # noqa: A002 — noms figés
    v = await exiger_grimpeur(request)
    s = request.app.state
    etage = await etage_visible(request, numero, v)
    if type not in ("case", "quete", "donjon", "categorie") or not id:
        raise Refus(422, "Requête invalide.")
    vue = await charger_vue_etage(s.depot, etage, s.regles)
    trouve = resoudre_quoi(vue, type, id)
    if trouve is None:
        raise Refus(404, INTROUVABLE)
    _, pas_fait, fait = trouve

    def court(g: Grimpeur) -> dict:
        return {"id": g.id, "pseudo": g.pseudo, "classe": g.classe}

    return JSONResponse({"pas_fait": [court(g) for g in pas_fait], "fait": [court(g) for g in fait]},
                        headers={"Cache-Control": "no-store"})
