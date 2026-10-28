"""Deux middlewares et la protection des écritures (ARCHITECTURE §7.2, §8.3 et §9).

Ce sont des middlewares ASGI « purs » : ils voient passer chaque requête avant toute route, statiques
et 404 compris. Une route ajoutée plus tard est donc filtrée d'office, sans qu'on y pense.

- `FiltreMode` : en mode teaser, seuls `/`, `/sante`, `/static/…` et la connexion répondent (websockets
  compris), sauf pour un **admin connecté**, qui voit tout (recette). Le reste reçoit une redirection
  303 vers `/`, sauf les chemins `/api/…`, qui reçoivent un 404. Un joueur connecté revoit donc le teaser.
- `EntetesSecurite` : pose la CSP et les autres en-têtes sur toutes les réponses qui le traversent.
  Les erreurs 500 passent par un autre chemin (le gestionnaire d'erreurs de `app.py`), qui pose
  les mêmes en-têtes lui-même.
- `verifier_ecriture` : chaque POST doit venir de notre origine et porter le jeton CSRF de la session.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from datetime import datetime

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.websockets import WebSocketClose

from epreuve.domaine.mode_site import (
    CHEMINS_TOUJOURS_PERMIS,
    PREFIXES_TOUJOURS_PERMIS,
    ReglageMode,
    mode_effectif,
    voit_site_complet,
)

# Pas de 'unsafe-inline' : ni script ni style en ligne, tout vient de /static/.
CSP = ("default-src 'self'; img-src 'self' https://api.dofusdb.fr data:; font-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
ENTETES_SECURITE: dict[str, str] = {
    "Content-Security-Policy": CSP,
    "X-Robots-Tag": "noindex, nofollow",  # le site n'a rien à faire dans les moteurs de recherche
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    # Le cookie de session est `Secure` : on interdit aussi au navigateur de revenir en http. Pas de
    # includeSubDomains ni de preload, pour ne rien imposer aux autres sous-domaines du domaine.
    "Strict-Transport-Security": "max-age=31536000",
}


def chemin_permis(chemin: str) -> bool:
    """Le chemin répond-il à tout le monde, même pendant le teaser ?

    Un chemin à segments « . », « .. » ou vides (`/static/../admin`, `/static//x`) n'est jamais permis :
    un navigateur ne les envoie pas, et le routeur ne les normalise pas, donc une route à paramètre
    pourrait y répondre en passant pour un fichier statique.
    """
    segments = chemin.split("/")[1:]
    if any(s in (".", "..") for s in segments) or "" in segments[:-1]:
        return False
    return chemin in CHEMINS_TOUJOURS_PERMIS or chemin.startswith(PREFIXES_TOUJOURS_PERMIS)


async def _personne(_scope: Scope) -> bool:
    return False


class FiltreMode:
    """En mode teaser, ne laisse passer que les chemins toujours permis, sauf pour un admin connecté.

    `est_admin(scope)` lit la session du visiteur (cookie) : le site complet n'est servi qu'aux admins.
    """

    def __init__(self, app: ASGIApp, reglage: ReglageMode, ouvert_le: datetime,
                 horloge: Callable[[], datetime],
                 est_admin: Callable[[Scope], Awaitable[bool]] = _personne) -> None:
        self.app, self.reglage, self.ouvert_le, self.horloge = app, reglage, ouvert_le, horloge
        self.est_admin = est_admin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Les websockets aussi : une route `@app.websocket` ne doit pas échapper au teaser.
        if scope["type"] not in ("http", "websocket") or chemin_permis(scope["path"]):
            await self.app(scope, receive, send)
            return
        mode = mode_effectif(self.reglage, self.ouvert_le, self.horloge())
        if mode == "ouvert" or voit_site_complet(mode, est_admin=await self.est_admin(scope)):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            reponse = WebSocketClose(code=1008)  # « violation de règle » : la connexion est refusée
        elif scope["path"] == "/api" or scope["path"].startswith("/api/"):
            reponse = JSONResponse({"erreur": "introuvable"}, status_code=404)
        else:
            reponse = RedirectResponse("/", status_code=303)
        await reponse(scope, receive, send)


class EntetesSecurite:
    """Ajoute `ENTETES_SECURITE` à chaque réponse, au moment où ses en-têtes partent."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def envoyer(message: Message) -> None:
            if message["type"] == "http.response.start":
                entetes = MutableHeaders(scope=message)
                for nom, valeur in ENTETES_SECURITE.items():
                    entetes[nom] = valeur
            await send(message)

        await self.app(scope, receive, envoyer)


def origine_permise(request: Request, site_url: str | None) -> bool:
    """Un POST doit venir de chez nous : `Origin` (ou, à défaut, `Referer`) égal à notre origine.

    Sans `SITE_URL`, notre origine est celle de la requête elle-même (développement local).
    Un navigateur envoie toujours `Origin` sur un POST ; son absence totale est acceptée pour les
    outils en ligne de commande, que le jeton CSRF arrête de toute façon.
    """
    attendue = (site_url or f"{request.url.scheme}://{request.url.netloc}").rstrip("/")
    origine = request.headers.get("origin")
    if origine is None:
        referer = request.headers.get("referer")
        if referer is None:
            return True
        return referer == attendue or referer.startswith(attendue + "/")
    return origine == attendue


def csrf_valide(attendu: str | None, recu: str | None) -> bool:
    """Comparaison en temps constant : on ne révèle pas, par la durée, combien de caractères sont justes."""
    return bool(attendu) and bool(recu) and hmac.compare_digest(attendu.encode(), recu.encode())
