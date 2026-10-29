"""Serveur de recette : le site en mode démo (données fictives) ou adossé à une base de test remplie.

    uv run python tests/qa/serveur_qa.py demo|base [port]

`base` lit TEST_DATABASE_URL ou DATABASE_URL (jamais `.env`), crée quelques grimpeurs fictifs s'il n'y en a pas,
et connecte par un faux Discord (page « qui es-tu ? »). L'horloge est figée au 15/11/2026, étage 0 ouvert.
"""

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from epreuve.config import Config  # noqa: E402
from epreuve.web.demo import (  # noqa: E402
    HORLOGE_DEMO,
    ID_MARCEAU,
    ID_SHADOAZE,
    ROLE_ADMIN,
    ClientOAuthDemo,
    creer_app_demo,
    faux_discord,
)

PSEUDOS = [("Brindille", "Iop"), ("Karamel", "Crâ"), ("Bouftou-Fou", "Eniripsa"), ("Tournesol", "Sram"),
           ("Éléonore", "Féca")]
BASE_ID = 400000000000000000


async def _preparer(url: str):
    from epreuve.db.depot import Depot
    from epreuve.db.session import creer_moteur

    moteur = creer_moteur(url)
    depot = Depot(moteur)
    maintenant = datetime.now(UTC)
    ids = [BASE_ID + i for i in range(len(PSEUDOS))]
    await depot.ajouter_liste(ids, "actif", ID_MARCEAU, maintenant)
    for i, (pseudo, classe) in zip(ids, PSEUDOS, strict=True):
        if await depot.grimpeur_par_discord(i) is None:
            await depot.creer_grimpeur(i, pseudo.lower(), pseudo, classe, None, maintenant)
    membres = {i: (p, frozenset()) for i, (p, _) in zip(ids, PSEUDOS, strict=True)}
    membres[ID_MARCEAU] = ("Marceau", frozenset({ROLE_ADMIN}))
    membres[ID_SHADOAZE] = ("Shadoaze", frozenset({ROLE_ADMIN}))
    await moteur.dispose()  # le pool est lié à cette boucle : le serveur crée le sien
    return membres


def creer_app_base(url: str):
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    from epreuve.db.depot import Depot
    from epreuve.db.session import creer_moteur
    from epreuve.regles import lire_regles
    from epreuve.web.app import creer_app
    from epreuve.web.rendu import rendre

    membres = asyncio.run(_preparer(url))
    depot = Depot(creer_moteur(url))
    config = Config(SITE_MODE="ouvert", DISCORD_GUILD_ID=1, DISCORD_ADMIN_ROLE_IDS=str(ROLE_ADMIN), _env_file=None)
    oauth = ClientOAuthDemo(config.discord_client_id, SecretStr("demo"), config.redirect_uri, 1,
                            transport=faux_discord(membres))
    app = creer_app(config, horloge=lambda: HORLOGE_DEMO, source=depot, oauth=oauth, regles=lire_regles())

    @app.get("/demo/qui", response_class=HTMLResponse)
    async def qui(request: Request, state: str = ""):
        return await rendre(request, "demo_qui.html", {
            "profils": [(f"/auth/discord/retour?code=code-{i}&state={state}", nom) for i, (nom, _) in membres.items()]})

    return app


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    if mode == "demo":
        app = creer_app_demo("ouvert")
    else:
        url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
        if not url:
            raise SystemExit("TEST_DATABASE_URL ou DATABASE_URL manquant")
        app = creer_app_base(url)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
