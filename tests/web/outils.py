"""Outils des tests du site : l'application sur le faux dépôt (`DepotDemo`) et un faux Discord.

Aucun appel réseau : Discord est simulé par `httpx.MockTransport` (`demo.faux_discord`), qui note chaque
adresse appelée. Le client de test parle en https : les cookies `__Host-` exigent `Secure`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from pydantic import SecretStr

from epreuve.config import Config
from epreuve.discord.oauth import ClientOAuth
from epreuve.domaine.modeles import Regles
from epreuve.web.app import creer_app
from epreuve.web.demo import (
    HORLOGE_DEMO,
    ID_HORS_LISTE,
    ID_MARCEAU,
    ID_NOUVELLE,
    ROLE_ADMIN,
    DepotDemo,
    _id_discord,
    faux_discord,
    membres_demo,
)

SITE = "https://epreuve.test"
AVANT_OUVERTURE = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
ID_BRINDILLE = _id_discord(1)   # grimpeur 1, actif
ID_OMBREVIVE = _id_discord(8)   # grimpeur 8, en pause
ID_FOURBE = _id_discord(13)     # grimpeur 13, exclu
ID_ADMIN_SUP = 300000000000000777  # admin par la liste de secours (sans rôle)
IDS_DISCORD_FABRIQUE = [_id_discord(i) for i in range(1, 14)] + [ID_MARCEAU, ID_NOUVELLE, ID_HORS_LISTE]


@dataclass
class Monde:
    """Une application de test, son dépôt, son horloge réglable et le journal des appels à Discord."""

    depot: DepotDemo
    appels: list[str]
    membres: dict
    maintenant: list[datetime] = field(default_factory=lambda: [HORLOGE_DEMO])
    app: object = None

    def horloge(self) -> datetime:
        return self.maintenant[0]

    def avancer(self, **duree) -> None:
        self.maintenant[0] += timedelta(**duree)

    def client(self) -> TestClient:
        return TestClient(self.app, base_url=SITE, follow_redirects=False)

    def connecter(self, discord_id: int, client: TestClient | None = None) -> TestClient:
        """Le parcours OAuth complet sur le faux Discord ; renvoie le client connecté."""
        c = client or self.client()
        r = c.get("/connexion")
        assert r.status_code == 303, r.text
        state = re.search(r"state=([^&]+)", r.headers["location"]).group(1)
        r = c.get(f"/auth/discord/retour?code=code-{discord_id}&state={state}")
        assert r.status_code == 303, r.text
        return c

    def csrf(self, c: TestClient, chemin: str = "/") -> str:
        html = c.get(chemin).text
        m = re.search(r'<meta name="csrf" content="([^"]*)"', html)
        assert m, html[:500]
        return m.group(1)


def monde(*, mode: str = "ouvert", maintenant: datetime | None = None, regles: Regles | None = None,
          depot: DepotDemo | None = None) -> Monde:
    depot = depot or DepotDemo()
    appels: list[str] = []
    membres = membres_demo(depot)
    membres[ID_ADMIN_SUP] = ("Secours", frozenset())
    m = Monde(depot, appels, membres)
    if maintenant is not None:
        m.maintenant[0] = maintenant
    config = Config(SITE_MODE=mode, SITE_URL=SITE, DISCORD_GUILD_ID=1, DISCORD_ADMIN_ROLE_IDS=str(ROLE_ADMIN),
                    ADMINS_SUPPLEMENTAIRES=str(ID_ADMIN_SUP), DISCORD_CLIENT_SECRET="secret-de-test", _env_file=None)
    oauth = ClientOAuth(config.discord_client_id, SecretStr("secret-de-test"), config.redirect_uri, 1,
                        transport=faux_discord(membres, appels))
    m.app = creer_app(config, horloge=m.horloge, source=depot, oauth=oauth, regles=regles)
    return m


def routes_declarees(app) -> list:
    """Toutes les routes, y compris celles des routeurs inclus (FastAPI les enveloppe à l'inclusion)."""
    sortie = []
    for r in app.routes:
        sortie.extend(r.original_router.routes if hasattr(r, "original_router") else [r])
    return sortie


def cocher(c: TestClient, csrf: str, **corps):
    return c.post("/api/coches", json=corps, headers={"X-CSRF-Token": csrf, "Origin": SITE})
