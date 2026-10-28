"""Le Builder (lot E3) : pages et API, sur connexion seulement.

    GET  /builder                         mes builds et ceux de la guilde, et « Nouveau build »
    GET  /builder/nouveau                 l'éditeur, sur un build vierge
    GET  /api/builder/objets              la fenêtre de choix d'un emplacement (filtres de Duffus)
    GET  /static/builder/<fichier>        la feuille et le script de l'éditeur

Le module se branche sur l'application par `brancher(app, source)` : un routeur et l'état dont il a besoin.
Il ne dépend que de deux lectures du dépôt commun (`session`, `grimpeur_par_discord`) pour savoir qui visite ;
le cookie est celui du lot B (`__Host-session`, empreinte SHA-256 en base).
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from epreuve.builder.catalogue import Catalogue, catalogue_par_defaut
from epreuve.builder.effets import (
    EMPLACEMENTS,
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
    builds: Any = None  # DepotBuilds (incrément 4), None sans base


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
    app.state.builder = services or ServicesBuilder(identifier_par_session(source))
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
            "caracs": list(ORDRE_CARACS), "classes": list(CLASSES)}


# --- Pages ----------------------------------------------------------------------------------------------------


@routeur.get("/builder", response_class=HTMLResponse)
async def page_liste(request: Request) -> Response:
    v = await _visiteur(request)
    if v is None:
        return RedirectResponse("/", status_code=303)
    return gabarits.TemplateResponse(request, "builder/liste.html", {"v": v})


@routeur.get("/builder/nouveau", response_class=HTMLResponse)
async def page_nouveau(request: Request) -> Response:
    v = await _visiteur(request)
    if v is None:
        return RedirectResponse("/", status_code=303)
    return gabarits.TemplateResponse(request, "builder/editeur.html", {
        "v": v, "config": {**_contexte_editeur(), "build": None, "modifiable": True},
    })  # fmt: skip


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
