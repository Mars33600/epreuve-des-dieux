"""Deux middlewares : le filtre du mode teaser et les en-têtes de sécurité (ARCHITECTURE §7.2 et §9).

Ce sont des middlewares ASGI « purs » : ils voient passer chaque requête avant toute route, statiques
et 404 compris. Une route ajoutée plus tard est donc filtrée d'office, sans qu'on y pense.

- `FiltreMode` : en mode teaser, seuls `/`, `/sante` et `/static/…` répondent (websockets compris). Le reste reçoit
  une redirection 303 vers `/`, sauf les chemins `/api/…`, qui reçoivent un 404 (un appel de
  script n'a que faire d'une redirection vers une page).
- `EntetesSecurite` : pose la CSP et les autres en-têtes sur toutes les réponses qui le traversent.
  Les erreurs 500 passent par un autre chemin (le gestionnaire d'erreurs de `app.py`), qui pose
  les mêmes en-têtes lui-même.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from starlette.datastructures import MutableHeaders
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
}


def chemin_permis(chemin: str) -> bool:
    """Le chemin répond-il à tout le monde, même pendant le teaser ?

    Un chemin à segments « . », « .. » ou vides (`/static/../admin`, `/static//x`) n'est jamais permis :
    un navigateur ne les envoie pas, et le routeur ne les normalise pas, donc une route à paramètre
    du lot B pourrait y répondre en passant pour un fichier statique.
    """
    segments = chemin.split("/")[1:]
    if any(s in (".", "..") for s in segments) or "" in segments[:-1]:
        return False
    return chemin in CHEMINS_TOUJOURS_PERMIS or chemin.startswith(PREFIXES_TOUJOURS_PERMIS)


class FiltreMode:
    """En mode teaser, ne laisse passer que les chemins toujours permis."""

    def __init__(self, app: ASGIApp, reglage: ReglageMode, ouvert_le: datetime,
                 horloge: Callable[[], datetime]) -> None:
        self.app, self.reglage, self.ouvert_le, self.horloge = app, reglage, ouvert_le, horloge

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Les websockets aussi : une route `@app.websocket` du lot B ne doit pas échapper au teaser.
        if scope["type"] not in ("http", "websocket") or chemin_permis(scope["path"]):
            await self.app(scope, receive, send)
            return
        mode = mode_effectif(self.reglage, self.ouvert_le, self.horloge())
        # Au lot A, personne n'est connecté. Le lot B lit la session ici.
        if voit_site_complet(mode, est_admin=False):
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
