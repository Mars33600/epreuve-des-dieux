"""Client HTTP minimal pour api.dofusdb.fr (lecture seule, sans clé).

Utilisé uniquement à la construction des étages (complément et repli, ARCHITECTURE §6.7), jamais pendant
la navigation : DofusDB est un projet communautaire sans garantie de disponibilité.
"""

from __future__ import annotations

import httpx

URL_DOFUSDB = "https://api.dofusdb.fr"
USER_AGENT = "EpreuveDesDieux-construction/1.0 (projet de fans ; https://epreuve-des-dieux.fr)"  # ASCII (HTTP)


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
        """Un succès, avec `categoryId` et ses `objectives` (critères `Qf=…`, `OA=…`)."""
        return await self._get(f"/achievements/{id_}")

    async def quete(self, id_: int) -> dict:
        """Une quête : `name.fr`, `startCriterion` (à lire avec `nature.quetes_obligatoires`)."""
        return await self._get(f"/quests/{id_}")

    async def objet(self, id_: int) -> dict:
        """Un objet : `name.fr`, `img`, `questsThatReward`, `achievementsThatReward`."""
        return await self._get(f"/items/{id_}")

    async def objets_par_type(self, type_id: int) -> list[dict]:
        """Tous les objets d'un type (23 : les Dofus), page par page (50 par page chez DofusDB)."""
        objets: list[dict] = []
        while True:
            page = await self._get(f"/items?typeId={type_id}&$limit=50&$skip={len(objets)}")
            objets.extend(page.get("data", []))
            if not page.get("data") or len(objets) >= page.get("total", 0):
                return objets
