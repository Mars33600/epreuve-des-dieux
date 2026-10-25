"""Point d'entrée de production : le bot ET le site, dans un seul programme.

    python -m epreuve.main

Une seule boucle asyncio, deux tâches qui attendent le réseau à tour de rôle :
- le serveur web (uvicorn) répond aux visiteurs du site ;
- le bot (discord.py) garde sa connexion à la passerelle Discord.
Si l'une des deux s'arrête sur une erreur, `asyncio.gather` arrête le programme et Fly.io le relance.
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from epreuve.bot.client import BotEpreuve
from epreuve.config import Config
from epreuve.db.depot import Depot
from epreuve.db.session import creer_moteur
from epreuve.web.app import creer_app


async def lancer(config: Config) -> None:
    moteur = creer_moteur(config.database_url.get_secret_value())
    depot = Depot(moteur)
    bot = BotEpreuve(depot, config.discord_guild_id, config.discord_admin_role_id, config.fuseau)
    app = creer_app(depot, discord_connecte=lambda: bot.connecte, fuseau=config.fuseau)
    serveur = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=config.site_port,  # noqa: S104
                                            log_level=config.journal_niveau.lower(), proxy_headers=True))
    try:
        await asyncio.gather(serveur.serve(), bot.start(config.discord_token.get_secret_value()))
    finally:
        await bot.close()
        await moteur.dispose()


def main() -> None:  # pragma: no cover — demande de vrais secrets
    config = Config()  # lit l'environnement ; s'arrête avec un message clair s'il manque une variable
    logging.basicConfig(level=config.journal_niveau,
                        format="%(asctime)s %(levelname)s %(name)s : %(message)s")
    logging.getLogger("epreuve").info("démarrage, configuration : %s", config)  # secrets masqués
    asyncio.run(lancer(config))


if __name__ == "__main__":  # pragma: no cover
    main()
