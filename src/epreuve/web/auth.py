"""La connexion, la session et les droits (ARCHITECTURE §8).

    GET  /connexion             tire un `state`, le pose en cookie court, renvoie vers Discord
    GET  /auth/discord/retour   vérifie `state`, échange le code, vérifie le membre et ses rôles, ouvre la session
    POST /deconnexion           supprime la session en base et révoque le jeton chez Discord

La session est en base ; le cookie `__Host-session` ne contient qu'un jeton aléatoire de 256 bits, dont
la base ne garde que l'empreinte SHA-256. Les droits d'admin sont revérifiés auprès de Discord au plus
toutes les 10 minutes, au moment d'une action d'admin.

Les « dépendances » (`exiger_grimpeur`, `exiger_admin`, `verifier_ecriture`) sont appelées par les routes :
elles lèvent `Refus`, que `app.py` transforme en redirection, en page d'erreur ou en JSON (`/api/…`).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass, replace
from datetime import timedelta

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.requests import HTTPConnection
from starlette.types import Scope

from epreuve.discord.oauth import ErreurDiscord, PasMembre, est_admin
from epreuve.domaine.mode_site import mode_effectif
from epreuve.domaine.modeles import Grimpeur, Session
from epreuve.web.securite import csrf_valide, origine_permise

journal = logging.getLogger("epreuve.web.auth")

COOKIE_SESSION = "__Host-session"
COOKIE_STATE = "__Host-oauth_state"
DUREE_SESSION = timedelta(days=7)
DUREE_STATE = timedelta(minutes=10)
REVERIFICATION = timedelta(minutes=10)

MESSAGE_NON_MEMBRE = "Ce site est réservé aux grimpeurs de L'Épreuve des Dieux."
MESSAGE_SUSPENDU = "Ta participation est suspendue. Contacte un admin."
MESSAGE_STATE = "La connexion a expiré ou n'a pas été demandée par ce site. Recommence."

routeur = APIRouter()


class Refus(Exception):
    """Une requête refusée : `vers` = redirection (pages), sinon page d'erreur ou JSON `{"ok": false}`."""

    def __init__(self, statut: int, message: str, vers: str | None = None) -> None:
        super().__init__(message)
        self.statut, self.message, self.vers = statut, message, vers


def hacher(jeton: str) -> bytes:
    return hashlib.sha256(jeton.encode()).digest()


@dataclass
class Visiteur:
    session: Session | None = None
    id_hache: bytes | None = None
    grimpeur: Grimpeur | None = None

    @property
    def connecte(self) -> bool:
        return self.session is not None

    @property
    def est_admin(self) -> bool:
        return self.session is not None and self.session.est_admin

    @property
    def csrf(self) -> str:
        return self.session.csrf if self.session else ""

    @property
    def grimpeur_id(self) -> int | None:
        return self.grimpeur.id if self.grimpeur else None

    @property
    def discord_id(self) -> int | None:
        return self.session.discord_user_id if self.session else None


def _services(app):
    return app.state


async def visiteur(request: HTTPConnection) -> Visiteur:
    """Le visiteur de cette requête, lu une seule fois (le filtre du mode teaser et la route le partagent)."""
    deja = getattr(request.state, "visiteur", None)
    if deja is not None:
        return deja
    v = Visiteur()
    jeton = request.cookies.get(COOKIE_SESSION)
    s = _services(request.app)
    if jeton and s.depot is not None:
        id_hache = hacher(jeton)
        session = await s.depot.session(id_hache, s.horloge())
        if session is not None:
            v = Visiteur(session, id_hache, await s.depot.grimpeur_par_discord(session.discord_user_id))
    request.state.visiteur = v
    return v


async def admin_pour_le_filtre(scope: Scope) -> bool:
    """Pour `FiltreMode` : le visiteur est-il un admin connecté ? (lecture seule, sans appel à Discord)"""
    return (await visiteur(HTTPConnection(scope))).est_admin  # HTTPConnection : http comme websocket


def mode(request: Request) -> str:
    s = _services(request.app)
    return mode_effectif(s.config.site_mode, s.config.site_ouvert_le, s.horloge())


async def exiger_connecte(request: Request) -> Visiteur:
    v = await visiteur(request)
    if not v.connecte:
        raise Refus(401, "Connecte-toi avec Discord pour continuer.", vers="/")
    return v


async def exiger_grimpeur(request: Request) -> Visiteur:
    """« Grimpeur » : connecté avec une fiche non exclue, ou admin même sans fiche (ARCHITECTURE §9)."""
    v = await exiger_connecte(request)
    if v.est_admin:
        return v
    if v.grimpeur is None:
        raise Refus(409, "Crée d'abord ta fiche.", vers="/inscription")
    if v.grimpeur.statut == "exclu":
        raise Refus(403, MESSAGE_SUSPENDU)
    return v


async def reverifier_admin(request: Request, v: Visiteur) -> bool:
    """Au plus toutes les 10 minutes, redemande à Discord si l'admin a toujours son rôle."""
    s = _services(request.app)
    maintenant = s.horloge()
    if not v.est_admin or v.session is None or v.id_hache is None:
        return False
    if maintenant - v.session.roles_verifies_le <= REVERIFICATION:
        return True
    if s.oauth is None:
        raise Refus(503, "La vérification des droits auprès de Discord est indisponible.")
    try:
        identite = await s.oauth.identite(v.session.jeton_oauth)
        admin = est_admin(identite, s.config.discord_admin_role_ids, s.config.admins_supplementaires)
    except (PasMembre, ErreurDiscord):
        admin = False  # jeton expiré, rôle ou appartenance retirés : la session redevient non-admin
    except httpx.HTTPError as e:
        raise Refus(503, "Discord ne répond pas : réessaie dans une minute.") from e
    await s.depot.maj_roles_session(v.id_hache, admin, maintenant)
    v.session = replace(v.session, est_admin=admin, roles_verifies_le=maintenant)
    if not admin:
        journal.info("droits d'admin retirés après revérification")
    return admin


async def exiger_admin(request: Request) -> Visiteur:
    v = await exiger_connecte(request)
    if not v.est_admin or not await reverifier_admin(request, v):
        raise Refus(403, "Cette page est réservée aux admins.")
    return v


async def verifier_ecriture(request: Request) -> Visiteur:
    """Tout POST : notre origine, une session, et le jeton CSRF (en-tête X-CSRF-Token ou champ « csrf »)."""
    s = _services(request.app)
    if not origine_permise(request, s.config.site_url):
        raise Refus(403, "Requête refusée : elle ne vient pas de ce site.")
    v = await visiteur(request)
    if not v.connecte:
        raise Refus(401, "Ta session a expiré : reconnecte-toi.", vers="/")
    recu = request.headers.get("x-csrf-token")
    if recu is None and request.headers.get("content-type", "").startswith(
            ("application/x-www-form-urlencoded", "multipart/form-data")):
        recu = (await request.form()).get("csrf")
    if not csrf_valide(v.csrf, recu if isinstance(recu, str) else None):
        raise Refus(403, "Requête refusée : jeton de sécurité invalide. Recharge la page.")
    return v


def _poser_cookie(reponse, nom: str, valeur: str, duree: timedelta) -> None:
    reponse.set_cookie(nom, valeur, max_age=int(duree.total_seconds()), path="/", secure=True, httponly=True,
                       samesite="lax")


@routeur.get("/connexion")
async def connexion(request: Request):
    s = _services(request.app)
    if s.oauth is None:
        raise Refus(503, "La connexion avec Discord n'est pas encore configurée.")
    state = secrets.token_urlsafe(32)
    reponse = RedirectResponse(s.oauth.url_autorisation(state), status_code=303)
    _poser_cookie(reponse, COOKIE_STATE, state, DUREE_STATE)
    return reponse


@routeur.get("/auth/discord/retour")
async def retour(request: Request, code: str = "", state: str = "", error: str = ""):
    s = _services(request.app)
    attendu = request.cookies.get(COOKIE_STATE, "")
    if not state or not attendu or not hmac.compare_digest(state.encode(), attendu.encode()):
        raise Refus(400, MESSAGE_STATE)
    if error or not code:
        raise Refus(400, "Connexion annulée sur Discord.")
    if s.oauth is None:
        raise Refus(503, "La connexion avec Discord n'est pas encore configurée.")
    try:
        jeton_oauth = await s.oauth.echanger_code(code)
    except (ErreurDiscord, httpx.HTTPError) as e:
        raise Refus(502, "Discord n'a pas validé la connexion. Recommence.") from e
    try:
        identite = await s.oauth.identite(jeton_oauth)
    except PasMembre as e:
        await s.oauth.revoquer(jeton_oauth)
        raise Refus(403, MESSAGE_NON_MEMBRE) from e
    except (ErreurDiscord, httpx.HTTPError) as e:
        raise Refus(502, "Discord n'a pas pu confirmer ton identité. Recommence.") from e
    admin = est_admin(identite, s.config.discord_admin_role_ids, s.config.admins_supplementaires)
    maintenant = s.horloge()
    ancien = request.cookies.get(COOKIE_SESSION)
    if ancien:
        await s.depot.supprimer_session(hacher(ancien))
    jeton = secrets.token_urlsafe(32)
    await s.depot.creer_session(hacher(jeton), identite.discord_user_id, identite.nom, admin, jeton_oauth,
                                secrets.token_urlsafe(32), maintenant, DUREE_SESSION)
    grimpeur = await s.depot.grimpeur_par_discord(identite.discord_user_id)
    vers = "/" if grimpeur is not None or mode(request) == "teaser" else "/inscription"
    reponse = RedirectResponse(vers, status_code=303)
    _poser_cookie(reponse, COOKIE_SESSION, jeton, DUREE_SESSION)
    reponse.delete_cookie(COOKIE_STATE, path="/", secure=True, httponly=True, samesite="lax")
    return reponse


@routeur.post("/deconnexion")
async def deconnexion(request: Request):
    s = _services(request.app)
    reponse = RedirectResponse("/", status_code=303)
    reponse.delete_cookie(COOKIE_SESSION, path="/", secure=True, httponly=True, samesite="lax")
    v = await visiteur(request)
    if not v.connecte:
        return reponse
    await verifier_ecriture(request)
    jeton_oauth = await s.depot.supprimer_session(v.id_hache)
    if jeton_oauth and s.oauth is not None:
        await s.oauth.revoquer(jeton_oauth)
    return reponse
