"""Le Builder (lot E3) : pages et API, sur connexion seulement.

    GET  /builder                         mes builds et ceux de la guilde, et « Nouveau build »
    GET  /builder/nouveau                 l'éditeur, sur un build vierge
    GET  /api/builder/objets              la fenêtre de choix d'un emplacement (filtres de Duffus)
    POST /api/builder/calcul              totaux, panoplies, conditions, base, parchemins, dérivés (sans effet de bord)
    GET  /builder/{id}                    un build : éditeur pour l'auteur, lecture seule s'il est partagé
    POST /api/builder/builds              enregistrer un nouveau build (grimpeur, jeton CSRF)
    PUT|DELETE /api/builder/builds/{id}   le modifier ou le supprimer (auteur seul, jeton CSRF)
    POST /api/builder/builds/{id}/dupliquer   copie d'un build à soi ou partagé, privée, au nom du grimpeur
    GET  /builder/comparer?a=…&b=…        deux builds côte à côte, écart par caractéristique
    GET  /static/builder/<fichier>        la feuille et le script de l'éditeur

Le module se branche sur l'application par `brancher(app, source)` : un routeur et l'état dont il a besoin.
Il ne dépend que de deux lectures du dépôt commun (`session`, `grimpeur_par_discord`) pour savoir qui visite ;
le cookie est celui du lot B (`__Host-session`, empreinte SHA-256 en base).
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ValidationError

from epreuve.builder.arme import BUFFS_PUISSANCE, MODES, calculer_arme
from epreuve.builder.calcul import Build, calculer, nettoyer, puissance_par_element
from epreuve.builder.catalogue import Catalogue, catalogue_par_defaut
from epreuve.builder.depot import BuildEnregistre, Contenu, DepotBuilds
from epreuve.builder.effets import (
    CARACS_PRINCIPALES,
    EMPLACEMENTS,
    GROUPES,
    NOMS_EMPLACEMENTS,
    NOMS_TYPES,
    ORDRE_CARACS,
    TYPES_DOFUS,
    TYPES_FAMILIERS,
)
from epreuve.domaine.classes import CLASSES

ICI = Path(__file__).parent
COOKIE_SESSION = "__Host-session"
STATIQUES = {"builder.js": "text/javascript", "builder.css": "text/css"}
MESSAGE_CONNEXION = "Connecte-toi avec Discord pour utiliser le builder."
PAGE_MAX = 60

routeur = APIRouter()
gabarits = Jinja2Templates(directory=ICI / "templates")


@dataclass(frozen=True)
class Visiteur:
    discord_id: int
    est_admin: bool
    csrf: str
    grimpeur_id: int | None = None
    pseudo: str | None = None


Identifier = Callable[[Request], Awaitable[Visiteur | None]]


@dataclass
class ServicesBuilder:
    identifier: Identifier
    catalogue: Callable[[], Catalogue] = catalogue_par_defaut
    builds: DepotBuilds | None = None  # None sans base : on compose, sans enregistrer
    horloge: Callable[[], datetime] = lambda: datetime.now(UTC)


def identifier_par_session(depot: Any, horloge: Callable[[], datetime] = lambda: datetime.now(UTC)) -> Identifier:
    """Le visiteur d'après le cookie de session du lot B. Un grimpeur exclu n'entre pas ; un admin sans fiche, si."""

    async def identifier(request: Request) -> Visiteur | None:
        jeton = request.cookies.get(COOKIE_SESSION)
        if not jeton or depot is None:
            return None
        session = await depot.session(hashlib.sha256(jeton.encode()).digest(), horloge())
        if session is None:
            return None
        g = await depot.grimpeur_par_discord(session.discord_user_id)
        if g is not None and g.statut == "exclu":
            g = None
            if not session.est_admin:
                return None
        return Visiteur(session.discord_user_id, session.est_admin, session.csrf,
                        g.id if g else None, g.pseudo if g else None)

    return identifier


def brancher(app: FastAPI, source: Any = None, services: ServicesBuilder | None = None) -> None:
    """Ajoute le builder à l'application : son routeur et ses services (`app.state.builder`)."""
    if services is None:
        moteur = getattr(source, "_moteur", None)  # le dépôt commun porte le moteur de la base
        services = ServicesBuilder(identifier_par_session(source), builds=DepotBuilds(moteur) if moteur else None)
    app.state.builder = services
    # Les routes sont ajoutées une à une (et non par `include_router`, qui les enveloppe) : chacune reste visible
    # telle quelle dans `app.routes`, où le test du teaser vérifie que toutes sont fermées avant l'ouverture.
    app.router.routes.extend(routeur.routes)


def _services(request: Request) -> ServicesBuilder:
    return request.app.state.builder


async def _visiteur(request: Request) -> Visiteur | None:
    return await _services(request).identifier(request)


def _erreur(statut: int, message: str) -> JSONResponse:
    return JSONResponse({"ok": False, "message": message}, status_code=statut, headers={"Cache-Control": "no-store"})


def _contexte_editeur() -> dict:
    """Les listes fixes dont la page a besoin (emplacements, types, caractéristiques, classes)."""
    familles = {
        "arme": [[t, NOMS_TYPES[t]] for t in EMPLACEMENTS["arme"]],
        "familier": [[t, nom] for nom, t in TYPES_FAMILIERS.items()],
        "dofus": [[t, nom] for nom, t in TYPES_DOFUS.items()],
    }
    return {"emplacements": [[e, NOMS_EMPLACEMENTS[e]] for e in EMPLACEMENTS], "familles": familles,
            "caracs": list(ORDRE_CARACS), "classes": list(CLASSES), "principales": list(CARACS_PRINCIPALES),
            "groupes": [[nom, list(c)] for nom, c in GROUPES]}


# --- Pages ----------------------------------------------------------------------------------------------------


@routeur.get("/builder", response_class=HTMLResponse)
async def page_liste(request: Request) -> Response:
    v = await _visiteur(request)
    if v is None:
        return RedirectResponse("/", status_code=303)
    builds = _services(request).builds
    mes, guilde = [], []
    if builds is not None:
        mes = await builds.de_grimpeur(v.grimpeur_id) if v.grimpeur_id else []
        guilde = await builds.partages(sauf_grimpeur=v.grimpeur_id)
    return gabarits.TemplateResponse(request, "builder/liste.html", {
        "v": v, "mes": mes, "guilde": guilde, "avec_base": builds is not None})  # fmt: skip


@routeur.get("/builder/nouveau", response_class=HTMLResponse)
async def page_nouveau(request: Request) -> Response:
    v = await _visiteur(request)
    if v is None:
        return RedirectResponse("/", status_code=303)
    return gabarits.TemplateResponse(request, "builder/editeur.html", {
        "v": v, "config": {**_contexte_editeur(), "build": None, "modifiable": True,
                           "enregistrable": _enregistrable(request, v)},
    })  # fmt: skip


def _enregistrable(request: Request, v: Visiteur) -> bool:
    return _services(request).builds is not None and v.grimpeur_id is not None


def _build_json(b: BuildEnregistre) -> dict:
    c = b.contenu
    return {"id": b.id, "auteur": b.auteur, "nom": c.nom, "classe": c.classe, "niveau": c.niveau, "objets": c.objets,
            "caracs_base": c.caracs_base, "caracs_parcho": c.caracs_parcho, "note": c.note, "partage": c.partage}


@routeur.get("/builder/{build_id:int}", response_class=HTMLResponse)
async def page_build(request: Request, build_id: int) -> Response:
    v = await _visiteur(request)
    if v is None:
        return RedirectResponse("/", status_code=303)
    b = await _lisible(request, v, build_id)
    if b is None:
        return gabarits.TemplateResponse(request, "builder/liste.html", {
            "v": v, "mes": [], "guilde": [], "avec_base": False, "introuvable": True}, status_code=404)  # fmt: skip
    a_moi = b.grimpeur_id == v.grimpeur_id
    return gabarits.TemplateResponse(request, "builder/editeur.html", {
        "v": v, "config": {**_contexte_editeur(), "build": _build_json(b), "modifiable": a_moi,
                           "enregistrable": a_moi, "duplicable": _enregistrable(request, v)},
    })  # fmt: skip


async def _lisible(request: Request, v: Visiteur, build_id: int) -> BuildEnregistre | None:
    """Le build s'il est à ce visiteur ou partagé dans la guilde, sinon None."""
    builds = _services(request).builds
    b = await builds.lire(build_id) if builds is not None else None
    if b is None or not (b.grimpeur_id == v.grimpeur_id or b.contenu.partage):
        return None
    return b


@routeur.get("/builder/comparer", response_class=HTMLResponse)
async def page_comparer(request: Request, a: int | None = None, b: int | None = None) -> Response:
    v = await _visiteur(request)
    if v is None:
        return RedirectResponse("/", status_code=303)
    s = _services(request)
    choix: list[BuildEnregistre] = []
    if s.builds is not None:
        choix = (await s.builds.de_grimpeur(v.grimpeur_id) if v.grimpeur_id else []) + \
            await s.builds.partages(sauf_grimpeur=v.grimpeur_id)
    builds = [await _lisible(request, v, x) if x is not None else None for x in (a, b)]
    colonnes = []
    for x in builds:
        if x is None:
            colonnes.append(None)
            continue
        c = x.contenu
        r = calculer(Build(c.niveau, c.objets, c.caracs_base, c.caracs_parcho), s.catalogue())
        colonnes.append({"build": x, "r": r})
    lignes = []
    if all(colonnes):
        va, vb = (col["r"].affichage for col in colonnes)
        for groupe, caracs in GROUPES:
            rangs = [(c, va.get(c, 0), vb.get(c, 0)) for c in caracs if va.get(c, 0) or vb.get(c, 0)]
            if rangs:
                lignes.append((groupe, rangs))
    return gabarits.TemplateResponse(request, "builder/comparer.html", {
        "v": v, "choix": choix, "a": a, "b": b, "colonnes": colonnes, "lignes": lignes,
        "introuvable": any(x is not None and c is None for x, c in zip((a, b), colonnes, strict=True))})  # fmt: skip


@routeur.get("/static/builder/{fichier}")
async def statique(fichier: str) -> Response:
    if fichier not in STATIQUES:  # liste fermée : aucun chemin construit à partir de la requête
        return Response(status_code=404)
    return FileResponse(ICI / "static" / "builder" / fichier, media_type=STATIQUES[fichier],
                        headers={"Cache-Control": "no-cache"})


# --- API ------------------------------------------------------------------------------------------------------


@routeur.get("/api/builder/objets")
async def api_objets(request: Request, emplacement: str, q: str = "", niveau_min: int | None = None,
                     niveau_max: int | None = None, type_: list[int] = Query(default=[], alias="type"),  # noqa: B008
                     carac: list[str] = Query(default=[]), decalage: int = 0) -> Response:  # noqa: B008
    if await _visiteur(request) is None:
        return _erreur(401, MESSAGE_CONNEXION)
    if emplacement not in EMPLACEMENTS:
        return _erreur(422, "Emplacement inconnu.")
    if any(c not in ORDRE_CARACS for c in carac) or decalage < 0 or len(q) > 100:
        return _erreur(422, "Filtre invalide.")
    total, page = _services(request).catalogue().rechercher(
        emplacement, texte=q, niveau_min=niveau_min, niveau_max=niveau_max, types=type_ or None, caracs=carac,
        limite=PAGE_MAX, decalage=decalage)  # fmt: skip
    return JSONResponse({"total": total, "objets": [o.resume() for o in page]})


class CorpsBuild(BaseModel):
    """Le build tel que l'envoie la page. Les bornes fines (niveau, parchemins) sont celles de `calcul.nettoyer`."""

    niveau: int = Field(200, ge=-10_000, le=10_000)
    objets: dict[str, int | None] = Field(default_factory=dict, max_length=32)
    caracs_base: dict[str, int] = Field(default_factory=dict, max_length=12)
    caracs_parcho: dict[str, int] = Field(default_factory=dict, max_length=12)
    mode_arme: str = "melee"
    buff_arme: str = ""

    def build(self) -> Build:
        bornes = lambda d: {k: max(-10_000, min(10_000, v)) for k, v in d.items()}  # noqa: E731
        return Build(self.niveau, dict(self.objets), bornes(self.caracs_base), bornes(self.caracs_parcho))


def resultat_json(build: Build, catalogue: Catalogue, mode_arme: str = "melee", buff_arme: str = "") -> dict:
    r = calculer(build, catalogue)
    arme = catalogue.objet(build.objets.get("arme"))
    calcul_arme = None
    if arme is not None and arme.arme is not None and mode_arme in MODES and buff_arme in BUFFS_PUISSANCE:
        calcul_arme = calculer_arme(arme.arme, r.totaux, mode_arme, buff_arme)
    objets = {e: o.resume() for e, oid in build.objets.items() if e in EMPLACEMENTS and (o := catalogue.objet(oid))}
    return {"objets": objets, "totaux": r.totaux, "affichage": r.affichage, "alertes": r.alertes,
            "panoplies": [{"id": p.id, "nom": p.nom, "nb": p.nb, "max": p.max_nb, "caracs": [list(c) for c in p.caracs]}
                          for p in r.panoplies],
            "points": {"total": r.points_total, "depenses": r.points_depenses,
                       "restants": r.points_total - r.points_depenses},
            "puissance": puissance_par_element(r.totaux), "detail": r.detail, "arme": calcul_arme}


async def _lire_corps(request: Request, modele: type[BaseModel]) -> BaseModel | None:
    try:
        return modele.model_validate(await request.json())
    except (ValueError, ValidationError):
        return None


@routeur.post("/api/builder/calcul")
async def api_calcul(request: Request) -> Response:
    if await _visiteur(request) is None:
        return _erreur(401, MESSAGE_CONNEXION)
    corps = await _lire_corps(request, CorpsBuild)
    if corps is None:
        return _erreur(422, "Build illisible.")
    if corps.mode_arme not in MODES or corps.buff_arme not in BUFFS_PUISSANCE:
        return _erreur(422, "Réglage d'arme inconnu.")
    resultat = resultat_json(corps.build(), _services(request).catalogue(), corps.mode_arme, corps.buff_arme)
    return JSONResponse({"ok": True, **resultat})


# --- Enregistrement -------------------------------------------------------------------------------------------


class CorpsEnregistre(CorpsBuild):
    nom: str = Field(min_length=1, max_length=80)
    classe: str
    note: str = Field("", max_length=2000)
    partage: bool = False

    def contenu(self) -> Contenu | None:
        if self.classe not in CLASSES or not self.nom.strip():
            return None
        b = nettoyer(self.build())
        return Contenu(self.nom.strip(), self.classe, b.niveau, {k: v for k, v in b.objets.items() if v is not None},
                       b.caracs_base, b.caracs_parcho, self.note, self.partage)


def _origine_permise(request: Request) -> bool:
    origine = request.headers.get("origin")
    return origine is None or origine == f"{request.url.scheme}://{request.url.netloc}"


async def _ecrivain(request: Request) -> tuple[Visiteur | None, JSONResponse | None]:
    """Le grimpeur qui écrit, ou la réponse d'erreur : 401 sans session, 403 CSRF ou Origin, 409 sans fiche."""
    v = await _visiteur(request)
    if v is None:
        return None, _erreur(401, MESSAGE_CONNEXION)
    jeton = request.headers.get("x-csrf-token", "")
    if not v.csrf or not hmac.compare_digest(jeton, v.csrf) or not _origine_permise(request):
        return None, _erreur(403, "Requête refusée. Recharge la page.")
    if v.grimpeur_id is None or _services(request).builds is None:
        return None, _erreur(409, "Il faut une fiche de grimpeur pour enregistrer un build.")
    return v, None


async def _contenu(request: Request) -> Contenu | None:
    corps = await _lire_corps(request, CorpsEnregistre)
    return corps.contenu() if corps is not None else None


@routeur.post("/api/builder/builds")
async def api_creer(request: Request) -> Response:
    v, refus = await _ecrivain(request)
    if refus:
        return refus
    contenu = await _contenu(request)
    if contenu is None:
        return _erreur(422, "Build invalide : nom (1 à 80 caractères), classe et niveau sont demandés.")
    s = _services(request)
    return JSONResponse({"ok": True, "id": await s.builds.creer(v.grimpeur_id, contenu, s.horloge())},
                        status_code=201)


@routeur.put("/api/builder/builds/{build_id:int}")
async def api_modifier(request: Request, build_id: int) -> Response:
    v, refus = await _ecrivain(request)
    if refus:
        return refus
    contenu = await _contenu(request)
    if contenu is None:
        return _erreur(422, "Build invalide : nom (1 à 80 caractères), classe et niveau sont demandés.")
    s = _services(request)
    if not await s.builds.modifier(build_id, v.grimpeur_id, contenu, s.horloge()):
        return _erreur(404, "Build introuvable.")
    return JSONResponse({"ok": True, "id": build_id})


@routeur.delete("/api/builder/builds/{build_id:int}")
async def api_supprimer(request: Request, build_id: int) -> Response:
    v, refus = await _ecrivain(request)
    if refus:
        return refus
    if not await _services(request).builds.supprimer(build_id, v.grimpeur_id):
        return _erreur(404, "Build introuvable.")
    return JSONResponse({"ok": True})


@routeur.post("/api/builder/builds/{build_id:int}/dupliquer")
async def api_dupliquer(request: Request, build_id: int) -> Response:
    """Comme « Dupliquer » chez Duffus : « Copie de <nom> », au nom du visiteur ; la copie est privée."""
    v, refus = await _ecrivain(request)
    if refus:
        return refus
    source = await _lisible(request, v, build_id)
    if source is None:
        return _erreur(404, "Build introuvable.")
    c = source.contenu
    copie = Contenu(f"Copie de {c.nom}"[:80], c.classe, c.niveau, c.objets, c.caracs_base, c.caracs_parcho, c.note,
                    partage=False)
    s = _services(request)
    return JSONResponse({"ok": True, "id": await s.builds.creer(v.grimpeur_id, copie, s.horloge())},
                        status_code=201)
