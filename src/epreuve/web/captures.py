"""Les pages du module E1 (docs/lots/E1.md) : archimonstres (et boss du Dofus Ocre) et avis de recherche.

    GET  /archimonstres                          le suivi : onglet, recherche, filtres, tri, « qui l'a ? »
    POST /archimonstres/personnages              le nombre de personnages visé (1 à 8)
    POST /archimonstres/{archi|boss}/{id}        un exemplaire de plus ou de moins (formulaire, sans JS)
    GET  /avis-de-recherche                      la liste : recherche, milice, Émeraude, capturé ou non
    GET  /avis-de-recherche/{slug}               la fiche d'un avis
    POST /avis-de-recherche/{id}                 capturé ou non (formulaire, sans JS)
    POST /api/archimonstres/{archi|boss}/{id}    {"delta": ±1} → {"ok", "nombre"}           (captures.js)
    POST /api/avis-de-recherche/{id}             {"capture": bool} → {"ok", "capture"}      (captures.js)
    GET  /api/{archimonstres/{genre}|avis-de-recherche}/{id}/qui → {"ont": […], "pas": […]}

Tout exige d'être grimpeur (connecté avec une fiche non exclue, ou admin), comme le reste du site. Écrire
exige en plus une fiche (un admin sans fiche consulte seulement), notre origine et le jeton CSRF. Un grimpeur
en pause garde son suivi : c'est personnel, sans effet sur la jauge. Aucun identifiant Discord n'est rendu.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from epreuve.captures import domaine as d
from epreuve.captures.catalogue import construire, derniere_aspiration, lire_dossier
from epreuve.captures.depot import CapturesMemoire, DepotCaptures, ElementInconnu, SourceCaptures
from epreuve.web.auth import Refus, Visiteur, exiger_grimpeur, verifier_ecriture
from epreuve.web.rendu import rendre

routeur = APIRouter()
DONNEES = Path(__file__).resolve().parents[3] / "donnees" / "duffus"
INTROUVABLE = "Cet élément n'existe pas."
SANS_FICHE = "Crée d'abord ta fiche pour suivre tes captures."
GENRES = ("archi", "boss")
PARAMS_ARCHIS = ("onglet", "q", "etat", "min", "tri")
PARAMS_AVIS = ("q", "milice", "etat", "emeraude")


# --- Source des données -----------------------------------------------------------------------------------


def catalogue_livre():
    """Le catalogue de la dernière aspiration livrée avec le site (donnees/duffus/), vide s'il n'y en a pas."""
    dossier = derniere_aspiration(DONNEES)
    return construire(lire_dossier(dossier) if dossier else {})


async def source(request: Request) -> SourceCaptures:
    """En production, la base du dépôt ; sinon (démonstration, tests), la mémoire. Posée une fois sur l'app.

    Au premier appel en base, si le catalogue est vide, on le charge depuis l'aspiration livrée avec le site :
    le module marche dès la mise en ligne, sans commande à lancer. `python -m epreuve.captures charger` met
    ensuite à jour depuis une aspiration plus récente."""
    s = request.app.state
    cap = getattr(s, "captures", None)
    if cap is not None:
        return cap
    from epreuve.db.depot import Depot

    if isinstance(s.depot, Depot):
        cap = DepotCaptures(s.depot._moteur)  # le moteur du dépôt : une seule réserve de connexions
        if not await cap.archimonstres():
            await cap.charger_catalogue(catalogue_livre(), s.horloge())
    elif s.depot is not None:
        cap = CapturesMemoire(catalogue_livre())
    else:
        raise Refus(503, "Le site est momentanément indisponible. Réessaie dans une minute.")
    s.captures = cap
    return cap


async def _page(request: Request, gabarit: str, contexte: dict):
    """Rendu compressé quand le navigateur l'accepte : 286 cartes pèsent ~310 ko de HTML, ~26 ko en gzip
    (le site n'a pas de compression générale ; on la fait ici pour ne pas toucher à app.py)."""
    reponse = await rendre(request, gabarit, contexte)
    if "gzip" in request.headers.get("accept-encoding", "") and len(reponse.body) > 2048:
        reponse.body = gzip.compress(reponse.body, 6)
        reponse.headers["Content-Encoding"] = "gzip"
        reponse.headers["Content-Length"] = str(len(reponse.body))
        reponse.headers["Vary"] = "Accept-Encoding"
    return reponse


def _grimpeur_id(v: Visiteur) -> int:
    if v.grimpeur is None:
        raise Refus(409, SANS_FICHE)
    return v.grimpeur.id


def _choix(valeur: str | None, permis: tuple[str, ...], defaut: str) -> str:
    return valeur if valeur in permis else defaut


def _entier(valeur: str | None) -> int | None:
    try:
        return int(valeur) if valeur not in (None, "") else None
    except ValueError:
        return None


def _retour(base: str, brut: str | None, permis: tuple[str, ...], ancre: str = "") -> str:
    """La page d'où vient un formulaire, reconstruite à partir des seuls paramètres connus (pas de redirection
    ouverte : le chemin est toujours le nôtre)."""
    params = [(k, v[:100]) for k, v in parse_qsl(brut or "") if k in permis and v]
    return base + (f"?{urlencode(params)}" if params else "") + ancre


async def _qui(request: Request, genre: str, element_id: int) -> tuple[list[d.Personne], list[d.Personne]]:
    cap = await source(request)
    return d.qui_a(await request.app.state.depot.grimpeurs(), await cap.detenteurs(genre, element_id))


def _personnes_json(personnes: list[d.Personne]) -> list[dict]:
    return [{"id": p.id, "pseudo": p.pseudo, "classe": p.classe, "nombre": p.nombre} for p in personnes]


# --- Archimonstres ----------------------------------------------------------------------------------------


@routeur.get("/archimonstres")
async def page_archimonstres(request: Request, onglet: str = "archis", q: str = "", etat: str = "tous",
                             min: str = "", tri: str = "", qui: str = ""):  # noqa: A002 — nom du paramètre d'URL
    v = await exiger_grimpeur(request)
    cap = await source(request)
    genre = "boss" if onglet == "boss" else "archi"
    tris = d.TRIS_BOSS if genre == "boss" else d.TRIS_ARCHIS
    tri = _choix(tri, tris, tris[0])
    etat = _choix(etat, ("tous", "captures", "manquants"), "tous")
    minimum = _entier(min)
    minimum = minimum if minimum is not None and 2 <= minimum <= d.PERSONNAGES_MAX else None
    items = await (cap.boss() if genre == "boss" else cap.archimonstres())
    gid = v.grimpeur_id
    nombres = await cap.nombres(gid, genre) if gid else {}
    persos = await cap.personnages(gid) if gid else 1
    visibles = {i.id for i in d.filtrer(items, nombres, recherche=q, etat=etat, minimum=minimum)}
    if tri == "zone":
        groupes = d.par_zone(items, nombres, persos)
    elif tri == "etape":
        groupes = d.par_etape(items, nombres, persos)
    else:
        groupes = [d.Groupe("", d.trier(items, tri))]
    qui_id = _entier(qui)
    panneau = None
    if qui_id is not None:
        element = next((i for i in items if i.id == qui_id), None)
        if element is not None:
            panneau = (element, *await _qui(request, genre, qui_id))
    params = {"onglet": "boss" if genre == "boss" else "", "q": q, "etat": "" if etat == "tous" else etat,
              "min": str(minimum or ""), "tri": "" if tri == tris[0] else tri}
    libelles = {"alpha": "A–Z", "etape": "Par étape", "zone": "Par zone", "niveau": "Par niveau"}
    liens_tri = [(t, libelles[t], "/archimonstres?" + urlencode([(k, x) for k, x in {**params, "tri": t}.items() if x]))
                 for t in tris]
    return await _page(request, "captures/archimonstres.html", {
        "genre": genre, "items": items, "groupes": groupes, "nombres": nombres, "personnages": persos,
        "visibles": visibles, "progression": d.progression(items, nombres, persos),
        "pierres": d.pierres_a_prevoir(items, nombres, persos), "q": q, "etat": etat, "minimum": minimum,
        "tri": tri, "liens_tri": liens_tri, "panneau": panneau, "peut_suivre": gid is not None,
        "retour": urlencode([(k, x) for k, x in params.items() if x]),
        "PERSONNAGES_MAX": d.PERSONNAGES_MAX, "normaliser": d.normaliser,
    })  # fmt: skip


@routeur.post("/archimonstres/personnages")
async def regler_personnages(request: Request):
    v = await verifier_ecriture(request)
    await exiger_grimpeur(request)
    gid = _grimpeur_id(v)
    form = await request.form()
    await (await source(request)).regler_personnages(gid, d.borne_personnages(form.get("nombre")))
    return RedirectResponse(_retour("/archimonstres", str(form.get("retour") or ""), PARAMS_ARCHIS), status_code=303)


@routeur.post("/archimonstres/{genre}/{element_id}")
async def changer_nombre_form(request: Request, genre: str, element_id: int):
    v = await verifier_ecriture(request)
    await exiger_grimpeur(request)
    gid = _grimpeur_id(v)
    form = await request.form()
    delta = _entier(str(form.get("delta") or ""))
    if genre not in GENRES or delta not in (-1, 1):
        raise Refus(422, "Requête invalide.")
    try:
        await (await source(request)).changer_nombre(gid, genre, element_id, delta, request.app.state.horloge())
    except ElementInconnu as e:
        raise Refus(404, INTROUVABLE) from e
    return RedirectResponse(_retour("/archimonstres", str(form.get("retour") or ""), PARAMS_ARCHIS,
                                    f"#{genre}-{element_id}"), status_code=303)


# --- Avis de recherche ------------------------------------------------------------------------------------


@routeur.get("/avis-de-recherche")
async def page_avis(request: Request, q: str = "", milice: str = "", etat: str = "tous", emeraude: str = "",
                    qui: str = ""):
    v = await exiger_grimpeur(request)
    cap = await source(request)
    avis = await cap.avis()
    gid = v.grimpeur_id
    captures = await cap.avis_captures(gid) if gid else set()
    milices = d.milices(avis)
    milice = milice if milice in milices else ""
    etat = _choix(etat, ("tous", "captures", "manquants"), "tous")
    visibles = {a.id for a in d.filtrer_avis(avis, captures, recherche=q, milice=milice, etat=etat,
                                             emeraude=emeraude == "1")}
    panneau = None
    qui_id = _entier(qui)
    if qui_id is not None:
        element = next((a for a in avis if a.id == qui_id), None)
        if element is not None:
            panneau = (element, *await _qui(request, "avis", qui_id))
    params = {"q": q, "milice": milice, "etat": "" if etat == "tous" else etat,
              "emeraude": "1" if emeraude == "1" else ""}
    return await _page(request, "captures/avis.html", {
        "avis": d.filtrer_avis(avis, set()), "captures": captures, "visibles": visibles, "milices": milices,
        "q": q, "milice": milice, "etat": etat, "emeraude": emeraude == "1", "panneau": panneau,
        "progression": d.Progression(len(captures & {a.id for a in avis}), len(avis)),
        "reste": d.recompenses_disponibles(avis, captures), "peut_suivre": gid is not None,
        "retour": urlencode([(k, x) for k, x in params.items() if x]), "normaliser": d.normaliser,
        "NIVEAU_EMERAUDE": d.NIVEAU_EMERAUDE,
    })  # fmt: skip


@routeur.get("/avis-de-recherche/{slug}")
async def fiche_avis(request: Request, slug: str):
    v = await exiger_grimpeur(request)
    cap = await source(request)
    avis = await cap.avis()
    a = next((x for x in avis if x.slug == slug), None)
    if a is None:
        raise Refus(404, INTROUVABLE)
    captures = await cap.avis_captures(v.grimpeur_id) if v.grimpeur_id else set()
    ont, pas = await _qui(request, "avis", a.id)
    meme_milice = [x for x in d.filtrer_avis(avis, set(), milice=a.milice) if x.id != a.id] if a.milice else []
    return await _page(request, "captures/avis_fiche.html", {
        "a": a, "capture": a.id in captures, "ont": ont, "pas": pas, "meme_milice": meme_milice,
        "captures": captures, "peut_suivre": v.grimpeur_id is not None,
    })  # fmt: skip


@routeur.post("/avis-de-recherche/{avis_id}")
async def capturer_avis_form(request: Request, avis_id: int):
    v = await verifier_ecriture(request)
    await exiger_grimpeur(request)
    gid = _grimpeur_id(v)
    form = await request.form()
    capture = str(form.get("capture") or "")
    if capture not in ("0", "1"):
        raise Refus(422, "Requête invalide.")
    try:
        await (await source(request)).capturer_avis(gid, avis_id, capture == "1", request.app.state.horloge())
    except ElementInconnu as e:
        raise Refus(404, INTROUVABLE) from e
    vers = str(form.get("vers") or "")
    if vers.startswith("/avis-de-recherche/") and vers.count("/") == 2 and all(c.isalnum() or c in "-_/" for c in vers):
        return RedirectResponse(vers, status_code=303)
    return RedirectResponse(_retour("/avis-de-recherche", str(form.get("retour") or ""), PARAMS_AVIS,
                                    f"#avis-{avis_id}"), status_code=303)


# --- API JSON (captures.js) -------------------------------------------------------------------------------


async def _corps(request: Request) -> dict:
    try:
        corps = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError) as e:
        raise Refus(422, "Requête invalide.") from e
    if not isinstance(corps, dict):
        raise Refus(422, "Requête invalide.")
    return corps


@routeur.post("/api/archimonstres/{genre}/{element_id}")
async def api_changer_nombre(request: Request, genre: str, element_id: int):
    v = await verifier_ecriture(request)
    await exiger_grimpeur(request)
    gid = _grimpeur_id(v)
    delta = (await _corps(request)).get("delta")
    if genre not in GENRES or type(delta) is not int or delta not in (-1, 1):
        raise Refus(422, "Requête invalide.")
    try:
        n = await (await source(request)).changer_nombre(gid, genre, element_id, delta, request.app.state.horloge())
    except ElementInconnu as e:
        raise Refus(404, INTROUVABLE) from e
    return JSONResponse({"ok": True, "nombre": n})


@routeur.post("/api/avis-de-recherche/{avis_id}")
async def api_capturer_avis(request: Request, avis_id: int):
    v = await verifier_ecriture(request)
    await exiger_grimpeur(request)
    gid = _grimpeur_id(v)
    capture = (await _corps(request)).get("capture")
    if type(capture) is not bool:
        raise Refus(422, "Requête invalide.")
    try:
        await (await source(request)).capturer_avis(gid, avis_id, capture, request.app.state.horloge())
    except ElementInconnu as e:
        raise Refus(404, INTROUVABLE) from e
    return JSONResponse({"ok": True, "capture": capture})


async def _api_qui(request: Request, genre: str, element_id: int) -> JSONResponse:
    await exiger_grimpeur(request)
    cap = await source(request)
    if genre == "avis":
        ids = {a.id for a in await cap.avis()}
    elif genre in GENRES:
        ids = {i.id for i in await (cap.boss() if genre == "boss" else cap.archimonstres())}
    else:
        raise Refus(404, INTROUVABLE)
    if element_id not in ids:
        raise Refus(404, INTROUVABLE)
    ont, pas = await _qui(request, genre, element_id)
    return JSONResponse({"ont": _personnes_json(ont), "pas": _personnes_json(pas)},
                        headers={"Cache-Control": "no-store"})


@routeur.get("/api/archimonstres/{genre}/{element_id}/qui")
async def api_qui_archi(request: Request, genre: str, element_id: int):
    return await _api_qui(request, genre, element_id)


@routeur.get("/api/avis-de-recherche/{avis_id}/qui")
async def api_qui_avis(request: Request, avis_id: int):
    return await _api_qui(request, "avis", avis_id)
