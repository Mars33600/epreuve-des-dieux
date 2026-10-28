"""Client DofusDB et repli des succès d'un donjon, sur les réponses enregistrées (tests/donnees/dofusdb/)."""

import json

import httpx
import pytest

from epreuve.dofusdb.client import USER_AGENT, ClientDofusDB
from epreuve.dofusdb.repli import ClientEnCache, succes_du_donjon
from tests.conftest import DONNEES, transport_dofusdb


async def test_succes_du_donjon_90_depuis_dofusdb_puis_cache(tmp_path):
    appels = []
    async with ClientDofusDB(transport=transport_dofusdb(appels)) as c:
        cases = await succes_du_donjon(ClientEnCache(c, tmp_path), 90)
    assert [n for _, n, _, _ in cases] == ["Crypte de Kardorim", "Kardorim (Duo)", "Kardorim (Zombie)",
                                           "Kardorim (Premier)", "Kardorim (Spécial)"]
    assert [e for *_, e in cases] == [True, False, False, False, False]
    assert cases[0][0] == "dofusdb:33" and "[challenge" not in cases[1][2]
    assert len(appels) == 6 and (tmp_path / "dungeon-90.json").exists()
    assert await succes_du_donjon(ClientEnCache(None, tmp_path), 90) == cases  # relu sans réseau


async def test_categorie_compagnons_exclue(tmp_path):
    (tmp_path / "dungeon-1.json").write_text(json.dumps({"achievements": [1, 2]}))
    for i, cat in ((1, 11), (2, 142)):
        (tmp_path / f"achievement-{i}.json").write_text(json.dumps(
            {"id": i, "categoryId": cat, "name": {"fr": f"S{i}"}, "description": {"fr": "Vaincre X."}}))
    assert [n for _, n, _, _ in await succes_du_donjon(ClientEnCache(None, tmp_path), 1)] == ["S1"]


async def test_sans_cache_ni_reseau(tmp_path):
    with pytest.raises(LookupError):
        await ClientEnCache(None, tmp_path).donjon(5)


async def test_nouvelles_methodes_du_client():
    vus = []

    def repondre(req):
        vus.append(str(req.url))
        assert req.headers["User-Agent"] == USER_AGENT
        if req.url.path == "/items" and req.url.params["typeId"] == "23":
            skip = int(req.url.params["$skip"])
            return httpx.Response(200, json={"total": 3, "data": [{"id": i} for i in range(skip, min(skip + 2, 3))]})
        return httpx.Response(200, json={"id": 1, "path": req.url.path})

    async with ClientDofusDB(transport=httpx.MockTransport(repondre)) as c:
        assert (await c.quete(275))["path"] == "/quests/275"
        assert (await c.objet(7043))["path"] == "/items/7043"
        assert [o["id"] for o in await c.objets_par_type(23)] == [0, 1, 2]
    assert DONNEES.exists() and len(vus) == 4
