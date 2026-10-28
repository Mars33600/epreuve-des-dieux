"""Le site : assemblage de l'application (ARCHITECTURE §9).

    GET /        le teaser (mode teaser, sauf admin connecté) ; sinon l'accueil (visiteur) ou la tour
    GET /sante   {"statut": "ok", "base": "absente"|"ok"|"erreur", "mode": "teaser"|"ouvert"}
    auth.py      /connexion, /auth/discord/retour, /deconnexion
    pages.py     /etages/{n}, /etages/{n}/quetes/{id}, /grimpeurs, /grimpeurs/{id}, /inscription
    api.py       POST /api/coches, GET /api/etages/{n}/manque
    admin.py     /admin/…

Pendant le teaser, tout le reste reçoit une redirection 303 vers `/` (ou un 404 pour `/api/…`), sauf
pour un admin connecté : c'est le rôle de `securite.py`, qui pose aussi les en-têtes de sécurité.

Le site ne sait pas d'où viennent les données : il reçoit une « source » qui a l'interface du dépôt.
En production c'est le dépôt Postgres ; en démonstration et dans les tests, `demo.DepotDemo`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from epreuve.config import Config
from epreuve.discord.oauth import ClientOAuth
from epreuve.domaine.mode_site import mode_effectif
from epreuve.domaine.modeles import Regles
from epreuve.web import admin, api, auth, pages
from epreuve.web.auth import Refus, admin_pour_le_filtre, visiteur
from epreuve.web.rendu import creer_gabarits, rendre
from epreuve.web.securite import ENTETES_SECURITE, EntetesSecurite, FiltreMode

journal = logging.getLogger("epreuve.web")
ICI = Path(__file__).parent
MESSAGE_INDISPONIBLE = "Le site est momentanément indisponible. Réessaie dans une minute."
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")


class SourceEtat(Protocol):
    # Le site lit tout par cette source (l'interface du dépôt, figée dans LOTS). `ping` sert à /sante.
    async def ping(self) -> bool: ...


def maintenant_utc() -> datetime:
    return datetime.now(UTC)


def jour_en_clair(d: datetime) -> str:
    """« vendredi 13 novembre 2026 » (« 1er » pour le premier du mois)."""
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{JOURS[d.weekday()]} {jour} {MOIS[d.month - 1]} {d.year}"


def creer_app(config: Config, horloge: Callable[[], datetime] = maintenant_utc,
              source: SourceEtat | None = None, *, oauth: ClientOAuth | None = None,
              regles: Regles | None = None) -> FastAPI:
    """Fabrique l'application. `horloge`, `source` et `oauth` sont injectables : les tests simulent la date,
    la base et Discord."""
    app = FastAPI(title="L'Épreuve des Dieux", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config, app.state.horloge, app.state.depot = config, horloge, source
    app.state.oauth, app.state.regles = oauth, regles or Regles()
    app.state.gabarits = gabarits = creer_gabarits()
    app.mount("/static", StaticFiles(directory=ICI / "static"), name="static")
    # Ordre : le dernier ajouté enveloppe les autres. Les en-têtes s'ajoutent donc aussi aux 303 et 404 du filtre.
    app.add_middleware(FiltreMode, reglage=config.site_mode, ouvert_le=config.site_ouvert_le, horloge=horloge,
                       est_admin=admin_pour_le_filtre)
    app.add_middleware(EntetesSecurite)
    ouverture = config.site_ouvert_le.astimezone(ZoneInfo(config.fuseau))  # pour la date écrite en clair

    def mode():
        return mode_effectif(config.site_mode, config.site_ouvert_le, horloge())

    def est_api(request: Request) -> bool:
        return request.url.path == "/api" or request.url.path.startswith("/api/")

    @app.exception_handler(Refus)
    async def _refus(request: Request, exc: Refus):
        if est_api(request):
            return JSONResponse({"ok": False, "message": exc.message}, status_code=exc.statut)
        if exc.vers is not None:
            return RedirectResponse(exc.vers, status_code=303)
        return await rendre(request, "erreur.html", {"message": exc.message, "statut": exc.statut}, exc.statut)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        message = "Introuvable." if exc.status_code == 404 else "Requête refusée."
        if est_api(request) or exc.status_code == 405:
            return JSONResponse({"ok": False, "message": message}, status_code=exc.status_code)
        return await rendre(request, "erreur.html", {"message": message, "statut": exc.status_code},
                            exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _invalide(request: Request, _exc: RequestValidationError):
        if est_api(request):
            return JSONResponse({"ok": False, "message": "Requête invalide."}, status_code=422)
        return await rendre(request, "erreur.html", {"message": "Requête invalide.", "statut": 422}, 422)

    @app.exception_handler(Exception)
    async def _erreur(_request: Request, exc: Exception) -> JSONResponse:
        # Jamais de trace de pile vers le visiteur : elle part dans les journaux du serveur.
        # Cette réponse ne traverse pas EntetesSecurite : on pose les en-têtes ici.
        journal.error("erreur non prévue : %r", exc)
        return JSONResponse({"erreur": MESSAGE_INDISPONIBLE}, status_code=500, headers=ENTETES_SECURITE)

    # HEAD aussi : les outils d'analyse des en-têtes et certaines sondes n'envoient que HEAD.
    @app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    async def page(request: Request):
        v = await visiteur(request)
        if mode() == "teaser" and not v.est_admin:
            return gabarits.TemplateResponse(request, "teaser.html", {
                "site_ouvert_le": config.site_ouvert_le, "teaser_lien_entrer": config.teaser_lien_entrer,
                "ouvert": False, "ouverture": ouverture, "jour_ouverture": jour_en_clair(ouverture),
            }, headers={"Cache-Control": "no-store"})  # fmt: skip
        if not v.connecte:
            return await rendre(request, "accueil.html")
        await auth.exiger_grimpeur(request)
        return await pages.tour(request, v)

    @app.api_route("/sante", methods=["GET", "HEAD"])
    async def sante():
        if source is None:
            base = "absente"
        else:
            try:
                base = "ok" if await source.ping() else "erreur"
            except Exception:  # noqa: BLE001 — toute erreur veut dire « base injoignable »
                base = "erreur"
        # Le teaser ne dépend pas de la base : toujours 200. Le site ouvert, lui, en a besoin.
        statut = 503 if mode() == "ouvert" and base != "ok" and source is not None else 200
        return JSONResponse({"statut": "ok" if statut == 200 else "erreur", "base": base, "mode": mode()},
                            status_code=statut, headers={"Cache-Control": "no-store"})

    app.include_router(auth.routeur)
    app.include_router(pages.routeur)
    app.include_router(api.routeur)
    app.include_router(admin.routeur)
    return app
