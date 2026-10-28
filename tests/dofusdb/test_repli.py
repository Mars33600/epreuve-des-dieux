"""Client DofusDB et repli des succès d'un donjon, sur les réponses enregistrées (tests/donnees/dofusdb/)."""

import json

import httpx
import pytest

from epreuve.dofusdb.client import USER_AGENT, ClientDofusDB
from epreuve.dofusdb.repli import ClientEnCache, succes_du_donjon
from tests.conftest import DONNEES, transport_dofusdb


async def test_succes_du_donjon_90_depuis_dofusdb_puis_cache(tmp_path):
    appels = []
    async with ClientDofusDB(transport=transport_dofusdb(appels), intervalle=0) as c:
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

    async with ClientDofusDB(transport=httpx.MockTransport(repondre), intervalle=0) as c:
        assert (await c.quete(275))["path"] == "/quests/275"
        assert (await c.objet(7043))["path"] == "/items/7043"
        assert [o["id"] for o in await c.objets_par_type(23)] == [0, 1, 2]
    assert DONNEES.exists() and len(vus) == 4


# --- Repli de nature, sur les réponses réelles mises en cache (donnees/dofusdb/) --------------------------

from pathlib import Path  # noqa: E402

from epreuve.dofusdb.repli import alleger, guides_repli, id_du_donjon, quetes_du_succes  # noqa: E402

CACHE_REEL = Path(__file__).resolve().parents[2] / "donnees" / "dofusdb"


async def test_fermeture_de_l_emeraude_donne_15_quetes():
    g = await guides_repli(ClientEnCache(None, CACHE_REEL), {"Dofus Émeraude", "Dofus Argenté", "Dofus Kaliptus"})
    assert {d: len(q) for d, q in g.items()} == {"Dofus Émeraude": 15, "Dofus Argenté": 74, "Dofus Kaliptus": 0}
    assert "Balade en forêt" in g["Dofus Émeraude"].values()


def ecrire(dossier, nom, donnees):
    (dossier / f"{nom}.json").write_text(json.dumps(donnees), encoding="utf-8")


async def test_succes_oa_recursifs_et_cycles(tmp_path):
    ecrire(tmp_path, "achievement-1", {"id": 1, "objectives": [{"criterion": "Qf=10&OA=2"}, {"criterion": None}]})
    ecrire(tmp_path, "achievement-2", {"id": 2, "objectives": [{"criterion": "OA=1|Qf=11"}]})
    assert await quetes_du_succes(ClientEnCache(None, tmp_path), 1, set()) == {10, 11}


async def test_id_du_donjon_par_recherche(tmp_path):
    vus = []

    def repondre(req):
        vus.append(dict(req.url.params))
        n = req.url.params["name.fr"]
        return httpx.Response(200, json={"data": [{"id": 34, "name": {"fr": n}, "mapIds": [1]}] if n == "Maison"
                                         else []})

    async with ClientDofusDB(transport=httpx.MockTransport(repondre), intervalle=0) as c:
        cache = ClientEnCache(c, tmp_path)
        assert await id_du_donjon(cache, "Maison") == 34
        assert await id_du_donjon(cache, "Absent du jeu") is None
        assert await id_du_donjon(cache, "Maison") == 34  # relu dans le cache
    assert len(vus) == 2 and (tmp_path / "dungeon-recherche-maison.json").exists()


def test_alleger():
    brut = {"id": 1, "name": {"fr": "A"}, "objectives": [{"id": 2, "criterion": "Qf=1", "readableCriterion": [1] * 9}],
            "img": "x", "categoryId": 3}
    assert alleger("achievement", brut) == {"id": 1, "name": {"fr": "A"}, "categoryId": 3,
                                             "objectives": [{"id": 2, "order": None, "criterion": "Qf=1"}]}
    assert alleger("autre", brut) is brut and alleger("quest", [{"id": 1, "x": 2}]) == [{"id": 1}]


async def test_client_pacing_une_requete_par_seconde(monkeypatch):
    attentes = []

    async def dormir(s):
        attentes.append(s)

    import epreuve.dofusdb.client as module
    monkeypatch.setattr(module.asyncio, "sleep", dormir)
    async with ClientDofusDB(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))) as c:
        await c.quete(1)
        await c.quete(2)
    assert len(attentes) == 1 and 0 < attentes[0] <= 1
