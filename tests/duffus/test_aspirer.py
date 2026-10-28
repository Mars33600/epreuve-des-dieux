"""L'aspiration avec un faux Duffus : validation, extraits stables, rapport, --a-blanc, filtre des fiches."""

import json
from datetime import date

import httpx
import pytest

from epreuve.duffus import aspirer as a
from epreuve.duffus.__main__ import _charger_env
from epreuve.duffus.client import ClientDuffus, ErreurDuffus
from epreuve.duffus.releve import ecrire_releve, relever, schema_depuis_openapi

RANGES = [
    {"id": 2, "order_index": 2, "range_key": "20-40", "label": "20 - 40", "title": "T2", "is_active": True,
     "dungeon_count": 0, "categories": [{"title": "B", "items": [{"type": "quest", "id": 11}]}], "image_url": "x"},
    {"id": 1, "order_index": 1, "range_key": "1-20", "label": "1 - 20", "title": "T1", "is_active": True,
     "dungeon_count": 1, "categories": [{"title": "A", "items": [{"type": "quest", "id": 10},
                                                                 {"type": "tip", "id": "t", "text": "…"}]}]},
]


def quete(id_, slug):
    return {"id": id_, "title": f"Q{id_}", "url": f"/quete/{slug}", "level": "10", "category": "A", "Order": id_,
            "quest_ornot": True, "own_page": True, "zone": "Incarnam", "pnj": "P", "pos": "[0,0]", "note": None,
            "note2": None, "succes": [], "is_dungeon": None, "dungeon_info": None, "dungeons": None, "farm": 1}


TABLES = {
    "guide_ranges": RANGES,
    "quest_list": [quete(11, "b"), quete(10, "a")],
    "quest_pages": [
        {"id": "u1", "slug": "a", "published": True, "status": "approved", "prereq_quests": "[]", "prereqs": [],
         "meta": {"title": "Q10", "level": "10", "zone": "I", "startNpc": "P", "startCoords": "[0,0]",
                  "image": "/images/x.png"}, "rewards": {"xp": "1 xp"}, "manual_resources": [], "steps": [],
         "content_html": "<p>Étape</p>"},
        {"id": "u2", "slug": "b", "published": True, "status": "approved", "prereq_quests": "[]", "prereqs": [],
         "meta": {}, "rewards": {}, "manual_resources": [], "steps": [], "content_html": ""},
    ],
    "dungeon_pages": [{"id": 1, "slug": "crypte", "published": True, "linked_quests": [],
                       "meta": {"title": "Crypte", "bossName": "K", "bossImage": "https://x/y.png"},
                       "successes": {"challenge1": {"name": "Zombie"}}}],
    "achievements": [{"id": 33, "name": "Crypte", "description": "Vaincre K dans son donjon.", "category_id": 11,
                      "level": 10, "order": 1},
                     {"id": 1, "name": "Autre", "description": "Finir une quête.", "category_id": 2, "level": 1,
                      "order": 1}],
    "dofus_list": [{"id": 1, "nom": "Dofus Argenté", "quest_id": 11, "advised_level": 30, "image_url": "z"}],
}


def faux_duffus(tables=TABLES, appels=None):
    def repondre(req: httpx.Request) -> httpx.Response:
        table = req.url.path.removeprefix("/rest/v1/")
        if appels is not None:
            appels.append((table, dict(req.url.params)))
        if table not in tables:
            return httpx.Response(404)
        lignes = tables[table]
        filtre = req.url.params.get("slug")
        if filtre:
            voulus = filtre.removeprefix("in.(").removesuffix(")").split(",")
            lignes = [r for r in lignes if r["slug"] in voulus]
        if req.url.params.get("limit") == "1":
            lignes = lignes[:1]
        return httpx.Response(200, json=lignes)

    return httpx.MockTransport(repondre)


async def _sans_attente(_):
    return None


def client(transport):
    return ClientDuffus("https://exemple.supabase.co", "k", transport=transport, dormir=_sans_attente)


JOUR = date(2026, 10, 29)


async def test_aspiration_complete_et_colonnes_retenues(tmp_path):
    async with client(faux_duffus()) as c:
        r = await a.aspirer(c, tmp_path, JOUR)
    d = tmp_path / "2026-10-29"
    assert sorted(f.name for f in d.iterdir()) == sorted(f"{n}.json" for n in a.TABLES)
    ranges = json.loads((d / "guide_ranges.json").read_text())
    assert [x["id"] for x in ranges] == [1, 2] and "image_url" not in ranges[0]  # trié, colonnes retenues
    assert "farm" not in json.loads((d / "quest_list.json").read_text())[0]
    assert json.loads((d / "dungeon_pages.json").read_text())[0]["meta"] == {"title": "Crypte", "bossName": "K"}
    assert json.loads((d / "quest_pages.json").read_text())[0]["meta"]["title"] == "Q10"
    assert "image" not in json.loads((d / "quest_pages.json").read_text())[0]["meta"]
    assert [x["id"] for x in json.loads((d / "achievements.json").read_text())] == [33]  # donjons seulement
    assert r.comptes["quest_list"] == 2 and "première aspiration" in r.texte()


async def test_deux_aspirations_identiques_octet_par_octet(tmp_path):
    for jour in (JOUR, date(2026, 10, 30)):
        async with client(faux_duffus()) as c:
            r = await a.aspirer(c, tmp_path, jour)
    for nom in a.TABLES:
        assert (tmp_path / "2026-10-29" / f"{nom}.json").read_bytes() == \
            (tmp_path / "2026-10-30" / f"{nom}.json").read_bytes()
    assert r.precedente == "2026-10-29" and all(d == (0, 0, 0) for d in r.differences.values())
    assert "inchangée" in r.texte()


async def test_rapport_de_differences(tmp_path):
    async with client(faux_duffus()) as c:
        await a.aspirer(c, tmp_path, JOUR)
    autre = {**TABLES, "quest_list": [quete(10, "a") | {"title": "Renommée"}, quete(12, "c")]}
    async with client(faux_duffus(autre)) as c:
        r = await a.aspirer(c, tmp_path, date(2026, 11, 2), tables=("quest_list",))
    assert r.differences["quest_list"] == (1, 1, 1)
    assert "+1 −1 ~1" in r.texte()


async def test_a_blanc_n_ecrit_rien(tmp_path):
    async with client(faux_duffus()) as c:
        r = await a.aspirer(c, tmp_path, JOUR, a_blanc=True)
    assert not any(tmp_path.iterdir()) and "rien n'a été écrit" in r.texte()


async def test_colonne_exigee_absente_arrete_sans_rien_ecrire(tmp_path):
    casse = {**TABLES, "quest_list": [{k: v for k, v in quete(10, "a").items() if k != "url"}]}
    async with client(faux_duffus(casse)) as c:
        with pytest.raises(ErreurDuffus, match=r"`quest_list.url` manquant : le schéma de Duffus a changé"):
            await a.aspirer(c, tmp_path, JOUR)
    assert not any(tmp_path.iterdir())


async def test_colonne_de_mauvais_type(tmp_path):
    casse = {**TABLES, "dofus_list": [{"id": "x", "nom": "D", "quest_id": 1, "advised_level": 1}]}
    async with client(faux_duffus(casse)) as c:
        with pytest.raises(ErreurDuffus, match=r"`dofus_list.id` invalide"):
            await a.aspirer(c, tmp_path, JOUR, tables=("dofus_list",))


async def test_table_inconnue(tmp_path):
    async with client(faux_duffus()) as c:
        with pytest.raises(ErreurDuffus, match="table inconnue"):
            await a.aspirer(c, tmp_path, JOUR, tables=("monsters",))


async def test_fiches_limitees_aux_etages_demandes(tmp_path):
    appels = []
    async with client(faux_duffus(appels=appels)) as c:
        await a.aspirer(c, tmp_path, JOUR, tables=("quest_pages",), etages=(0,))
    assert [x["slug"] for x in json.loads((tmp_path / "2026-10-29" / "quest_pages.json").read_text())] == ["a"]
    assert ("quest_pages", {"select": a._colonnes(a.s.QuestePage), "order": "slug.asc", "slug": "in.(a)"}) in appels
    assert sorted(f.name for f in (tmp_path / "2026-10-29").iterdir()) == ["quest_pages.json"]


async def test_fiches_et_tables_lues_une_seule_fois(tmp_path):
    appels = []
    async with client(faux_duffus(appels=appels)) as c:
        await a.aspirer(c, tmp_path, JOUR, tables=("guide_ranges", "quest_list", "quest_pages"), etages=(0, 1, 9))
    assert [t for t, _ in appels] == ["guide_ranges", "quest_list", "quest_pages"]
    assert len(json.loads((tmp_path / "2026-10-29" / "quest_pages.json").read_text())) == 2


def test_colonnes_avec_majuscule_entre_guillemets():
    assert '"Order"' in a._colonnes(a.s.QuestListe).split(",")


def test_serialiser_vide():
    assert a.serialiser([]) == "[]\n"


# --- Relevé --------------------------------------------------------------------------------------------------


async def test_releve_par_une_ligne(tmp_path):
    async with client(faux_duffus({**TABLES, "quest_pages": []})) as c:
        r = await relever(c, ("guide_ranges", "quest_pages", "monsters"))
    assert r["source"] == "une_ligne"
    assert r["tables"]["guide_ranges"]["categories"] == "array" and r["tables"]["guide_ranges"]["is_active"] == \
        "boolean"
    assert r["tables"]["quest_pages"] == {} and r["tables"]["monsters"] == {}  # vide, absente (404)
    f = ecrire_releve(r, tmp_path, JOUR)
    assert f.name == "schema-2026-10-29.json" and json.loads(f.read_text())["source"] == "une_ligne"


async def test_releve_par_openapi():
    api = {"definitions": {"quest_list": {"properties": {"id": {"type": "integer", "format": "bigint"},
                                                         "title": {"type": "string"}}}}}
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=api))
    async with client(transport) as c:
        r = await relever(c)
    assert r == {"source": "openapi", "tables": schema_depuis_openapi(api)}
    assert r["tables"]["quest_list"] == {"id": "bigint", "title": "string"}


async def test_releve_arrete_sur_refus():
    codes = iter([401, 403])
    async with client(httpx.MockTransport(lambda req: httpx.Response(next(codes)))) as c:
        with pytest.raises(ErreurDuffus):
            await relever(c)


def test_charger_env_ne_lit_que_duffus(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("DISCORD_TOKEN=secret\nDUFFUS_SUPABASE_URL='https://x'\n# commentaire\n", encoding="utf-8")
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("DUFFUS_SUPABASE_URL", raising=False)
    _charger_env(f)
    _charger_env(tmp_path / "absent")
    import os
    assert os.environ["DUFFUS_SUPABASE_URL"] == "https://x" and "DISCORD_TOKEN" not in os.environ
