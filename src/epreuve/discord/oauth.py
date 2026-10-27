"""La connexion avec Discord, en OAuth2 seulement : aucun bot, aucune écriture sur Discord (ARCHITECTURE §8).

Le site ne parle à Discord qu'à travers quatre adresses :
    POST /oauth2/token                          échanger le code reçu au retour contre un jeton d'accès
    GET  /users/@me                             l'identifiant et le nom affiché
    GET  /users/@me/guilds/{serveur}/member     le membre du serveur et ses rôles (404 = pas membre)
    POST /oauth2/token/revoke                   révoquer le jeton à la déconnexion

Portées demandées : « identify » et « guilds.members.read ». Rien d'autre : le site ne lit ni les
messages ni la liste des serveurs, et n'écrit rien. Le transport httpx est injectable : les tests
simulent Discord avec `httpx.MockTransport`, sans aucun appel réseau.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote, urlencode

import httpx
from pydantic import SecretStr

journal = logging.getLogger("epreuve.discord")

API = "https://discord.com/api/v10"
AUTORISATION = "https://discord.com/oauth2/authorize"
PORTEES = "identify guilds.members.read"


class ErreurDiscord(Exception):
    """Discord a répondu autre chose que prévu (jeton refusé, panne, réponse illisible)."""


class PasMembre(ErreurDiscord):
    """La personne n'est pas membre du serveur de l'événement (404 sur /member)."""


@dataclass(frozen=True)
class Identite:
    discord_user_id: int
    nom: str
    roles: frozenset[int]


class ClientOAuth:
    def __init__(self, client_id: str, client_secret: SecretStr, redirect_uri: str, guild_id: int,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.client_id, self._secret = client_id, client_secret
        self.redirect_uri, self.guild_id = redirect_uri, guild_id
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=API, transport=self._transport, timeout=10.0,
                                 headers={"User-Agent": "EpreuveDesDieux (site de suivi, OAuth2)"})

    def url_autorisation(self, state: str) -> str:
        """L'écran d'autorisation de Discord. `prompt=none` : pas de nouvel écran si déjà accepté."""
        return AUTORISATION + "?" + urlencode({
            "response_type": "code", "client_id": self.client_id, "scope": PORTEES,
            "redirect_uri": self.redirect_uri, "state": state, "prompt": "none",
        }, quote_via=quote)  # %20 plutôt que « + » pour l'espace des portées, comme dans la doc de Discord

    async def echanger_code(self, code: str) -> str:
        """Le code reçu au retour → un jeton d'accès (valable 7 jours)."""
        donnees = {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri}
        async with self._client() as c:
            r = await c.post("/oauth2/token", data=donnees, auth=(self.client_id, self._secret.get_secret_value()))
        if r.status_code != 200:
            raise ErreurDiscord(f"échange du code refusé ({r.status_code})")
        jeton = _json(r).get("access_token")
        if not isinstance(jeton, str) or not jeton:
            raise ErreurDiscord("réponse de Discord sans jeton")
        return jeton

    async def identite(self, jeton: str) -> Identite:
        """Qui est-ce, et quels sont ses rôles sur le serveur ? PasMembre s'il n'en est pas membre."""
        entetes = {"Authorization": f"Bearer {jeton}"}
        async with self._client() as c:
            moi = await c.get("/users/@me", headers=entetes)
            if moi.status_code != 200:
                raise ErreurDiscord(f"identité refusée ({moi.status_code})")
            membre = await c.get(f"/users/@me/guilds/{self.guild_id}/member", headers=entetes)
        if membre.status_code == 404:
            raise PasMembre("pas membre du serveur")
        if membre.status_code != 200:
            raise ErreurDiscord(f"membre illisible ({membre.status_code})")
        u, m = _json(moi), _json(membre)
        try:
            uid = int(u["id"])
            roles = frozenset(int(r) for r in m.get("roles", []))
        except (KeyError, TypeError, ValueError) as e:
            raise ErreurDiscord("réponse de Discord illisible") from e
        # Le nom du serveur d'abord (ce que les grimpeurs voient), puis le nom affiché, puis le nom d'utilisateur.
        nom = m.get("nick") or u.get("global_name") or u.get("username") or str(uid)
        return Identite(uid, str(nom), roles)

    async def revoquer(self, jeton: str) -> None:
        """Révoque le jeton chez Discord. Une erreur est journalisée, jamais remontée : la session est déjà close."""
        try:
            async with self._client() as c:
                r = await c.post("/oauth2/token/revoke", data={"token": jeton, "token_type_hint": "access_token"},
                                 auth=(self.client_id, self._secret.get_secret_value()))
            if r.status_code != 200:
                journal.warning("révocation du jeton refusée par Discord (%s)", r.status_code)
        except httpx.HTTPError as e:
            journal.warning("révocation du jeton impossible : %s", type(e).__name__)


def est_admin(identite: Identite, roles_admin: frozenset[int], admins_sup: frozenset[int]) -> bool:
    """Admin ⇔ un rôle d'admin sur le serveur, ou l'identifiant dans la liste de secours."""
    return bool(identite.roles & roles_admin) or identite.discord_user_id in admins_sup


def _json(r: httpx.Response) -> dict:
    try:
        d = r.json()
    except ValueError as e:
        raise ErreurDiscord("réponse de Discord illisible") from e
    if not isinstance(d, dict):
        raise ErreurDiscord("réponse de Discord illisible")
    return d
