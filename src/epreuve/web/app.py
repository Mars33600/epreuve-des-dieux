"""Le site, version lot A : le teaser, une sonde de santé, les fichiers statiques.

    GET /        le teaser (mode teaser) ; en mode ouvert, provisoirement, le teaser dans son état
                 « Les portes sont ouvertes » (le lot B y met l'accueil et la tour)
    GET /sante   {"statut": "ok", "base": "absente"|"ok"|"erreur", "mode": "teaser"|"ouvert"}
    /static/teaser/, /static/fonts/   la feuille, le script et les polices du teaser

Tout le reste reçoit une redirection 303 vers `/` (ou un 404 pour `/api/…`) pendant le teaser :
c'est le rôle de `securite.py`, qui pose aussi les en-têtes de sécurité sur chaque réponse.

Le site ne sait pas d'où vient l'état de la base : il reçoit une « source » qui sait `ping()`.
En production c'est le dépôt (Postgres) ; sans `DATABASE_URL`, il n'y en a pas, et le teaser
tourne quand même.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from epreuve.config import Config
from epreuve.domaine.mode_site import mode_effectif
from epreuve.web.securite import ENTETES_SECURITE, EntetesSecurite, FiltreMode

journal = logging.getLogger("epreuve.web")
ICI = Path(__file__).parent
MESSAGE_INDISPONIBLE = "Le site est momentanément indisponible. Réessaie dans une minute."
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")


class SourceEtat(Protocol):
    # Au lot A, on ne demande à la base que d'être joignable. Le lot B ajoute les lectures.
    async def ping(self) -> bool: ...


def maintenant_utc() -> datetime:
    return datetime.now(UTC)


def jour_en_clair(d: datetime) -> str:
    """« vendredi 13 novembre 2026 » (« 1er » pour le premier du mois)."""
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{JOURS[d.weekday()]} {jour} {MOIS[d.month - 1]} {d.year}"


def creer_app(config: Config, horloge: Callable[[], datetime] = maintenant_utc,
              source: SourceEtat | None = None) -> FastAPI:
    """Fabrique l'application. `horloge` est injectable : les tests simulent la date."""
    app = FastAPI(title="L'Épreuve des Dieux", docs_url=None, redoc_url=None, openapi_url=None)
    # Seuls les statiques du teaser sont servis : l'ancienne page (app.js, style.css) attend le lot B.
    for dossier in ("teaser", "fonts"):
        app.mount(f"/static/{dossier}", StaticFiles(directory=ICI / "static" / dossier), name=dossier)
    # Ordre : le dernier ajouté enveloppe les autres. Les en-têtes s'ajoutent donc aussi aux 303 et 404 du filtre.
    app.add_middleware(FiltreMode, reglage=config.site_mode, ouvert_le=config.site_ouvert_le, horloge=horloge)
    app.add_middleware(EntetesSecurite)
    gabarits = Jinja2Templates(directory=ICI / "templates")
    ouverture = config.site_ouvert_le.astimezone(ZoneInfo(config.fuseau))  # pour la date écrite en clair

    def mode():
        return mode_effectif(config.site_mode, config.site_ouvert_le, horloge())

    @app.exception_handler(Exception)
    async def _erreur(_request: Request, exc: Exception) -> JSONResponse:
        # Jamais de trace de pile vers le visiteur : elle part dans les journaux du serveur.
        # Cette réponse ne traverse pas EntetesSecurite : on pose les en-têtes ici.
        journal.error("erreur non prévue : %r", exc)
        return JSONResponse({"erreur": MESSAGE_INDISPONIBLE}, status_code=500, headers=ENTETES_SECURITE)

    @app.get("/", response_class=HTMLResponse)
    async def page(request: Request):
        return gabarits.TemplateResponse(request, "teaser.html", {
            "site_ouvert_le": config.site_ouvert_le, "teaser_lien_entrer": config.teaser_lien_entrer,
            "ouvert": mode() == "ouvert", "ouverture": ouverture, "jour_ouverture": jour_en_clair(ouverture),
        })  # fmt: skip

    @app.get("/sante")
    async def sante():
        # Toujours 200 au lot A : le teaser ne dépend pas de la base. Au lot B, 503 si elle est injoignable.
        if source is None:
            base = "absente"
        else:
            try:
                base = "ok" if await source.ping() else "erreur"
            except Exception:  # noqa: BLE001 — toute erreur veut dire « base injoignable »
                base = "erreur"
        return JSONResponse({"statut": "ok", "base": base, "mode": mode()}, headers={"Cache-Control": "no-store"})

    return app
