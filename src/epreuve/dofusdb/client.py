"""Client HTTP minimal pour api.dofusdb.fr (lecture seule, sans clé).

Utilisé uniquement à la construction des étages (complément et repli, ARCHITECTURE §6.7), jamais pendant
la navigation : DofusDB est un projet communautaire sans garantie de disponibilité. Même politesse que pour
Duffus : une requête par seconde au plus, et un User-Agent qui nous identifie.
"""

from __future__ import annotations

import asyncio
import time

import httpx

URL_DOFUSDB = "https://api.dofusdb.fr"
USER_AGENT = "EpreuveDesDieux-construction/1.0 (projet de fans ; https://epreuve-des-dieux.fr)"  # ASCII (HTTP)


class ClientDofusDB:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, intervalle: float = 1.0) -> None:
        # `transport` remplace le réseau dans les tests ; `intervalle` = temps minimal entre deux requêtes.
        self._http = httpx.AsyncClient(
            base_url=URL_DOFUSDB, headers={"User-Agent": USER_AGENT}, timeout=20, transport=transport
        )
        self._intervalle = intervalle
        self._derniere = 0.0

    async def __aenter__(self) -> ClientDofusDB:
        return self

    async def __aexit__(self, *exc) -> None:
        await self._http.aclose()

    async def _get(self, chemin: str, params: dict | list | None = None) -> dict:
        attente = self._intervalle - (time.monotonic() - self._derniere)
        if attente > 0:
            await asyncio.sleep(attente)
        self._derniere = time.monotonic()
        reponse = await self._http.get(chemin, params=params)
        reponse.raise_for_status()
        return reponse.json()

    async def donjon(self, id_: int) -> dict:
        """`name.fr`, `optimalPlayerLevel` et surtout `achievements` (les succès du donjon)."""
        return await self._get(f"/dungeons/{id_}")

    async def chercher_donjon(self, nom: str) -> list[dict]:
        """Les donjons dont le nom français est exactement `nom`."""
        return (await self._get("/dungeons", {"name.fr": nom})).get("data", [])

    async def succes(self, id_: int) -> dict:
        """Un succès, avec `categoryId` et ses `objectives` (critères `Qf=…`, `OA=…`)."""
        return await self._get(f"/achievements/{id_}")

    async def defi(self, id_: int) -> dict:
        """Un challenge de donjon (le `[challenge,N]` d'un succès) : `name.fr` et `description.fr`, la règle."""
        return await self._get(f"/challenges/{id_}")

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
            page = await self._get("/items", {"typeId": type_id, "$limit": 50, "$skip": len(objets)})
            objets.extend(page.get("data", []))
            if not page.get("data") or len(objets) >= page.get("total", 0):
                return objets

    async def lot(self, chemin: str, ids: list[int], select: tuple[str, ...] = ()) -> list[dict]:
        """Les éléments de `chemin` (« /npcs/ ») dont l'id est dans `ids`, par paquets de 50 (une requête chacun).
        `select` limite les champs renvoyés. Le `/` final de `chemin` évite une redirection."""
        trouves: list[dict] = []
        for i in range(0, len(ids), 50):
            params: list[tuple[str, str | int]] = [("id[$in][]", x) for x in ids[i : i + 50]] + [("$limit", 50)]
            params += [("$select[]", c) for c in select]
            trouves.extend((await self._get(chemin, params)).get("data", []))
        return trouves

    async def index_quetes(self) -> list[dict]:
        """Toutes les quêtes du jeu, réduites à `id` et `name` (une quarantaine de requêtes)."""
        quetes: list[dict] = []
        while True:
            page = await self._get("/quests/", [("$select[]", "id"), ("$select[]", "name"), ("$limit", 50),
                                                ("$skip", len(quetes)), ("$sort[id]", 1)])
            quetes.extend(page.get("data", []))
            if not page.get("data") or len(quetes) >= page.get("total", 0):
                return quetes
