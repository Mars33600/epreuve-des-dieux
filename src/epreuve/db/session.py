"""Création du moteur de base de données (asynchrone, avec un petit pool de connexions)."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def creer_moteur(database_url: str) -> AsyncEngine:
    """Un moteur pour tout le programme.

    - `pool_pre_ping` : avant de réutiliser une connexion du pool, on vérifie qu'elle vit encore
      (utile si Supabase a coupé une connexion inactive) ;
    - pool petit : un seul programme, peu de requêtes simultanées, et l'offre gratuite de
      Supabase limite le nombre de connexions.
    """
    return create_async_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=2)
