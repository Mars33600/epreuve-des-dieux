"""Module E1 : aspiration (faux Duffus, sans réseau) et dépôt Postgres (migration e1_captures)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from epreuve.captures.aspirer import aspirer, liste_in, reduire_grades
from epreuve.captures.catalogue import construire, lire_dossier
from epreuve.captures.depot import DepotCaptures, ElementInconnu
from epreuve.duffus.client import ClientDuffus

MAINTENANT = datetime(2026, 11, 13, 17, tzinfo=UTC)
TABLES_FAUSSES = {
    "archimonstres": [{"id": 1, "nom": "Blorie", "etape": "25", "zone": "Mine", "image": "/images/archis/2404_B.png"}],
    "boss_ocre": [{"id": 7, "nom": "Bouftou Royal", "etape": 17, "image": None}],
    "wanted2": [{"id": 3, "slug": "fou", "nom": "Fou", "lvl": "Niv. 20", "zone": "Astrub", "milice": "Astrub",
                 "recompense": "120", "recompense_type": "aviton", "chasse": None, "dofus_monster_id": "463",
                 "resume_html": "<b>x</b>", "image_avis": "https://stockage/x.png"}],
    "monster_races": [{"id": 1, "name": "Bouftous"}],
    "subareas": [{"id": 1, "name": "Mine", "areaid": 5}, {"id": 2, "name": "Mine", "areaid": 6},
                 {"id": 9, "name": "Ailleurs", "areaid": 5}],
    "areas": [{"id": 5, "name": "Amakna"}, {"id": 6, "name": "Bonta"}],
}


def faux_duffus(appels: list[str]) -> httpx.MockTransport:
    def repondre(r: httpx.Request) -> httpx.Response:
        table = r.url.path.rsplit("/", 1)[1]
        params = parse_qs(urlparse(str(r.url)).query)
        appels.append(table)
        if table == "monsters":
            if "grades_json" in params["select"][0] and "->" not in params["select"][0]:
                return httpx.Response(200, json=[{"id": 463, "name": "Fou", "gfxid": 206,
                                                  "grades_json": [{"level": 20, "lifePoints": 670, "xp": 1}]}])
            if "name" in params:
                return httpx.Response(200, json=[{"id": 11, "name": "Bouftou Royal", "race": 1, "gfxid": 6, "n0": 12}])
            return httpx.Response(200, json=[{"id": 2404, "name": "Blorie", "race": 2, "gfxid": 162, "n0": 52}])
        if table == "subareas" and "monsters_json" in params["select"][0]:
            assert params["id"] == ['in.("1","2")']  # seulement les noms ambigus cités par les archis
            return httpx.Response(200, json=[{"id": 2, "monsters_json": [{"monsterId": 2404}]}])
        return httpx.Response(200, json=TABLES_FAUSSES[table])

    return httpx.MockTransport(repondre)


async def _dormir(_s):
    return None


async def test_aspirer_ecrit_les_fichiers_et_le_catalogue_se_construit(tmp_path):
    appels: list[str] = []
    async with ClientDuffus("https://duffus.test", "cle", transport=faux_duffus(appels), dormir=_dormir) as c:
        rapport = await aspirer(c, tmp_path, date(2026, 10, 28))
    assert rapport.comptes["archimonstres"] == 1 and rapport.requetes == len(appels) == 10
    assert "image_avis" not in (tmp_path / "2026-10-28" / "wanted2.json").read_text()  # jamais les images
    grades = json.loads((tmp_path / "2026-10-28" / "monstres_avis.json").read_text())[0]["grades_json"]
    assert "xp" not in grades[0] and grades[0]["lifePoints"] == 670
    c = construire(lire_dossier(tmp_path / "2026-10-28"))
    assert c.archis[0].zones[0].aire == "Bonta" and c.boss[0].niveau == 12 and c.avis[0].gfx_id == 206


def test_outils_aspiration():
    assert liste_in(['a"b', "c,d"]) == 'in.("a\\"b","c,d")'
    assert reduire_grades([{"level": 1, "autre": 2}, "x"]) == [{**{k: None for k in reduire_grades([{}])[0]},
                                                                "level": 1}]


# --- Postgres ----------------------------------------------------------------------------------------------


@pytest.fixture
async def captures(depot, moteur, tmp_path):
    async with moteur.begin() as c:
        await c.execute(text("TRUNCATE epreuve.capture_archi, epreuve.capture_boss, epreuve.capture_avis, "
                             "epreuve.archi_personnages, epreuve.archimonstre, epreuve.boss_ocre, "
                             "epreuve.avis_recherche"))
    async with ClientDuffus("https://duffus.test", "cle", transport=faux_duffus([]), dormir=_dormir) as c:
        await aspirer(c, tmp_path, date(2026, 10, 28))
    cap = DepotCaptures(moteur)
    await cap.charger_catalogue(construire(lire_dossier(tmp_path / "2026-10-28")), MAINTENANT)
    return cap


async def _grimpeur(depot, n: int):
    await depot.ajouter_liste([n], "actif", 1, MAINTENANT)
    return await depot.creer_grimpeur(n, f"d{n}", f"Pseudo{n}", None, None, MAINTENANT)


async def test_depot_captures(captures, depot):
    cap = captures
    g = await _grimpeur(depot, 1001)
    assert [a.nom for a in await cap.archimonstres()] == ["Blorie"]
    assert await cap.changer_nombre(g.id, "archi", 1, 1, MAINTENANT) == 1
    assert await cap.changer_nombre(g.id, "archi", 1, 1, MAINTENANT) == 2
    assert await cap.nombres(g.id, "archi") == {1: 2}
    assert await cap.changer_nombre(g.id, "archi", 1, -1, MAINTENANT) == 1
    assert await cap.changer_nombre(g.id, "archi", 1, -1, MAINTENANT) == 0
    assert await cap.changer_nombre(g.id, "archi", 1, -1, MAINTENANT) == 0  # jamais négatif
    assert await cap.nombres(g.id, "archi") == {}
    assert await cap.changer_nombre(g.id, "boss", 7, 1, MAINTENANT) == 1
    assert await cap.detenteurs("boss", 7) == {g.id: 1}
    with pytest.raises(ElementInconnu):
        await cap.changer_nombre(g.id, "archi", 999, 1, MAINTENANT)
    assert await cap.capturer_avis(g.id, 3, True, MAINTENANT) is True
    assert await cap.capturer_avis(g.id, 3, True, MAINTENANT) is False  # idempotent
    assert await cap.avis_captures(g.id) == {3} and await cap.detenteurs("avis", 3) == {g.id: 1}
    assert await cap.capturer_avis(g.id, 3, False, MAINTENANT) is True
    assert await cap.personnages(g.id) == 1
    assert await cap.regler_personnages(g.id, 12) == 8 and await cap.personnages(g.id) == 8


async def test_rechargement_retire_sans_supprimer(captures, depot, moteur):
    cap = captures
    g = await _grimpeur(depot, 1002)
    await cap.changer_nombre(g.id, "archi", 1, 1, MAINTENANT)
    vide = construire({})
    await cap.charger_catalogue(vide, MAINTENANT)  # Duffus n'a plus rien : on masque, la capture reste
    assert await cap.archimonstres() == [] and await cap.nombres(g.id, "archi") == {1: 1}
    with pytest.raises(ElementInconnu):
        await cap.changer_nombre(g.id, "archi", 1, 1, MAINTENANT)
    async with moteur.begin() as c:  # la base refuse de supprimer un élément capturé
        with pytest.raises(IntegrityError):
            await c.execute(text("DELETE FROM epreuve.archimonstre WHERE id = 1"))
