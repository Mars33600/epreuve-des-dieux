"""Point d'entrée d'Alembic : applique les migrations sur la base de DATABASE_URL.

On utilise le moteur asynchrone (asyncpg), comme le reste du programme. La table de version
d'Alembic vit dans le schéma `epreuve`, qu'on crée d'abord s'il n'existe pas.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _url() -> str:
    # Les tests passent l'adresse par config.attributes ; sinon on lit l'environnement.
    url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL n'est pas défini (voir .env.example)")
    return url


def _migrer(connexion) -> None:
    context.configure(connection=connexion, version_table_schema="epreuve")
    with context.begin_transaction():
        context.run_migrations()


async def _lancer() -> None:
    moteur = create_async_engine(_url())
    async with moteur.begin() as connexion:
        await connexion.execute(text("CREATE SCHEMA IF NOT EXISTS epreuve"))
    async with moteur.connect() as connexion:
        await connexion.run_sync(_migrer)
        await connexion.commit()
    await moteur.dispose()


if context.is_offline_mode():
    raise SystemExit("Le mode hors ligne d'Alembic n'est pas utilisé dans ce projet.")
asyncio.run(_lancer())
