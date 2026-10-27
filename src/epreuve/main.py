"""Point d'entrée de production : le site seul, servi par uvicorn.

    python -m epreuve.main

Plus de bot connecté en permanence (ARCHITECTURE §2) : un seul programme, une seule tâche.
Au lot A, la base est facultative : sans `DATABASE_URL`, le teaser tourne et `/sante` répond
« base absente ». Si le serveur s'arrête sur une erreur, Fly.io relance la machine.
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from epreuve.config import Config
from epreuve.web.app import creer_app


async def lancer(config: Config) -> None:
    moteur = None
    source = None
    if config.database_url is not None:
        # Importés ici seulement : sans base, le teaser n'a pas besoin de SQLAlchemy.
        from epreuve.db.depot import Depot
        from epreuve.db.session import creer_moteur

        moteur = creer_moteur(config.database_url.get_secret_value())
        source = Depot(moteur)
    app = creer_app(config, source=source)
    serveur = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=config.site_port,  # noqa: S104
                                            log_level=config.journal_niveau.lower(), proxy_headers=True))
    try:
        await serveur.serve()
    finally:
        if moteur is not None:
            await moteur.dispose()


def main() -> None:  # pragma: no cover — lance un vrai serveur
    config = Config()  # lit l'environnement ; s'arrête avec un message clair si une variable est mal formée
    logging.basicConfig(level=config.journal_niveau,
                        format="%(asctime)s %(levelname)s %(name)s : %(message)s")
    logging.getLogger("epreuve").info("démarrage, configuration : %s", config)  # secrets masqués
    asyncio.run(lancer(config))


if __name__ == "__main__":  # pragma: no cover
    main()
