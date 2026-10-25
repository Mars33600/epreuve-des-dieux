"""Client HTTP minimal pour api.dofusdb.fr (lecture seule, sans clé).

Utilisé uniquement par l'outil d'import, jamais pendant le fonctionnement du bot :
DofusDB est un projet communautaire sans garantie de disponibilité.
"""

from __future__ import annotations

import httpx

URL_DOFUSDB = "https://api.dofusdb.fr"
USER_AGENT = "epreuve-des-dieux/0.1 (import d'etage, une fois par etage)"  # en ASCII : exigé par HTTP


class ClientDofusDB:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # `transport` permet aux tests de remplacer le réseau par des réponses enregistrées.
        self._http = httpx.AsyncClient(
            base_url=URL_DOFUSDB, headers={"User-Agent": USER_AGENT}, timeout=20, transport=transport
        )

    async def __aenter__(self) -> ClientDofusDB:
        return self

    async def __aexit__(self, *exc) -> None:
        await self._http.aclose()

    async def _get(self, chemin: str) -> dict:
        reponse = await self._http.get(chemin)
        reponse.raise_for_status()
        return reponse.json()

    async def donjon(self, id_: int) -> dict:
        """`name.fr`, `optimalPlayerLevel` et surtout `achievements` (les succès du donjon)."""
        return await self._get(f"/dungeons/{id_}")

    async def succes(self, id_: int) -> dict:
        return await self._get(f"/achievements/{id_}")

    async def categorie_quetes(self, id_: int) -> dict:
        """`name.fr` et `questIds` : toutes les quêtes d'une zone."""
        return await self._get(f"/quest-categories/{id_}")
