"""Repli DofusDB des succès d'un donjon (T-02, ARCHITECTURE §6.7), quand Duffus ne les donne pas.

`GET /dungeons/{id}` → `achievements`, sans la catégorie Compagnons (142). La case classique est le succès
sans défi (sa description ne contient pas `[challenge,`). Le résultat est au même format que les succès
Duffus (`contenu.construire.CasePreparee`), avec `succes_source = "dofusdb"`. Les réponses lues sont mises
en cache dans un dossier (`donnees/dofusdb/`), pour que les reconstructions se fassent sans réseau.
"""

from __future__ import annotations

import json
from pathlib import Path

from epreuve.dofusdb.client import ClientDofusDB

CATEGORIE_COMPAGNONS = 142


class ClientEnCache:
    """Lit d'abord `<cache>/<genre>-<id>.json`, sinon DofusDB, puis enregistre la réponse."""

    def __init__(self, client: ClientDofusDB | None, cache: Path) -> None:
        self._client = client
        self._cache = cache

    async def _lire(self, genre: str, id_: int, appel) -> dict:
        f = self._cache / f"{genre}-{id_}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        if self._client is None:
            raise LookupError(f"{f.name} absent du cache et aucun accès réseau")
        donnees = await appel(id_)
        self._cache.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(donnees, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return donnees

    async def donjon(self, id_: int) -> dict:
        return await self._lire("dungeon", id_, self._client.donjon if self._client else None)

    async def succes(self, id_: int) -> dict:
        return await self._lire("achievement", id_, self._client.succes if self._client else None)


async def succes_du_donjon(client: ClientEnCache, dofusdb_id: int) -> list[tuple[str, str, str, bool]]:
    """(id, nom, condition, est_classique) dans l'ordre : la classique, « (Duo) », puis les autres par id."""
    donjon = await client.donjon(dofusdb_id)
    succes = [await client.succes(i) for i in donjon.get("achievements", [])]
    succes = [s for s in succes if s.get("categoryId") != CATEGORIE_COMPAGNONS]

    def description(s: dict) -> str:
        return (s.get("description") or {}).get("fr", "")

    def cle(s: dict) -> tuple[int, int, int]:
        nom = (s.get("name") or {}).get("fr", "")
        return ("[challenge," in description(s), not nom.endswith("(Duo)"), s["id"])

    succes.sort(key=cle)
    return [(f"dofusdb:{s['id']}", s["name"]["fr"], description(s).split(" en validant")[0].strip() + "."
             if "[challenge," in description(s) else description(s), i == 0 and "[challenge," not in description(s))
            for i, s in enumerate(succes)]
