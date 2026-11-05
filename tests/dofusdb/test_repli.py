"""Client DofusDB et repli des succès d'un donjon, sur les réponses enregistrées (tests/donnees/dofusdb/)."""

import json

import httpx
import pytest

from epreuve.dofusdb.client import USER_AGENT, ClientDofusDB
from epreuve.dofusdb.repli import ClientEnCache, formater_regle, id_du_defi, regle_du_defi, succes_du_donjon
from epreuve.domaine.modeles import MARQUE_ALEATOIRE
from tests.conftest import DONNEES, transport_dofusdb


async def test_succes_du_donjon_90_depuis_dofusdb_puis_cache(tmp_path):
    appels = []
    async with ClientDofusDB(transport=transport_dofusdb(appels), intervalle=0) as c:
        cases = await succes_du_donjon(ClientEnCache(c, tmp_path), 90)
    assert [n for _, n, _, _ in cases] == ["Crypte de Kardorim", "Kardorim (Duo)", "Kardorim (Zombie)",
                                           "Kardorim (Premier)", "Kardorim (Spécial)"]
    assert [e for *_, e in cases] == [True, False, False, False, False]
    assert cases[0][0] == "dofusdb:33" and "[challenge" not in cases[1][2]
    assert cases[1][2] == "Finir le donjon à deux personnages au plus."
    assert cases[3][2].endswith("d'un combat à l'autre.")
    assert len(appels) == 10 and (tmp_path / "dungeon-90.json").exists()
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

from epreuve.dofusdb.repli import (  # noqa: E402
    alleger,
    guides_repli,
    id_du_donjon,
    normaliser_nom,
    quetes_du_succes,
)

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
    index = [{"id": 3, "name": {"fr": "Bibliothèque du Maître Corbac"}},
             {"id": 149, "name": {"fr": "Expédition - Bibliothèque du Maître Corbac"}},
             {"id": 7, "name": {"fr": "Jumeau"}}, {"id": 8, "name": {"fr": "Jumeau"}}]

    def repondre(req):
        vus.append(dict(req.url.params))
        if "name.fr" not in req.url.params:  # l'index, par pages de 2
            skip = int(req.url.params["$skip"])
            return httpx.Response(200, json={"total": len(index), "data": index[skip:skip + 2]})
        n = req.url.params["name.fr"]
        return httpx.Response(200, json={"data": [{"id": 34, "name": {"fr": n}, "mapIds": [1]}] if n == "Maison"
                                         else []})

    async with ClientDofusDB(transport=httpx.MockTransport(repondre), intervalle=0) as c:
        cache = ClientEnCache(c, tmp_path)
        assert await id_du_donjon(cache, "Maison") == 34
        assert await id_du_donjon(cache, "Absent du jeu") is None
        assert await id_du_donjon(cache, "Maison") == 34  # relu dans le cache
        # La recherche exacte échoue (« Maitre » chez Duffus) : l'index, comparé sans accents, retrouve le donjon,
        # et lui seul (pas l'« Expédition » homonyme).
        assert await id_du_donjon(cache, "Bibliothèque du Maitre Corbac") == 3
        assert await id_du_donjon(cache, "jumeau") is None  # deux donjons répondent : on ne choisit pas
    # 2 recherches exactes, 2 pages d'index (lues une fois, puis cache), 2 recherches exactes encore.
    assert len(vus) == 6 and (tmp_path / "dungeon-recherche-maison.json").exists()
    assert (tmp_path / "dungeon-index.json").exists()


def test_normaliser_nom():
    assert normaliser_nom("Bibliothèque du Maitre Corbac") == normaliser_nom("Bibliothèque du  Maître Corbac")
    assert normaliser_nom("Défi du Chalœil") == "defi du chaloeil"
    assert normaliser_nom("Chafer Rōnin (Duo)") == "chafer ronin duo"


async def test_donjon_a_deux_boss_garde_celui_de_duffus():
    """Tanière Givrefoux (58) : DofusDB range sous ce donjon les succès du Tengu ET de la Fuji Givrefoux
    Nourricière (anciennes « Cavernes Givrefoux » et « Cavernes Nourricières »), deux classiques, 10 cases."""
    cache = ClientEnCache(None, CACHE_REEL)
    tous = await succes_du_donjon(cache, 58)
    assert len(tous) == 10 and sum(1 for *_, cl in tous if cl) == 1  # l'ancien bug : deux jeux fusionnés
    tengu = await succes_du_donjon(cache, 58, "Tengu Givrefoux")
    assert [i for i, *_ in tengu] == ["dofusdb:31", "dofusdb:538", "dofusdb:748", "dofusdb:749", "dofusdb:6218"]
    assert [cl for *_, cl in tengu] == [True, False, False, False, False]
    assert len(await succes_du_donjon(cache, 58, "Boss inconnu")) == 10  # aucun ne le cite : rien n'est retiré
    # Un donjon à une seule classique ne filtre jamais, même si le boss Duffus s'écrit autrement.
    assert len(await succes_du_donjon(cache, 47, "Chafer Ronin")) == 5


async def test_succes_liste_deux_fois_une_seule_case(tmp_path):
    (tmp_path / "dungeon-1.json").write_text(json.dumps({"achievements": [1, 1]}))
    (tmp_path / "achievement-1.json").write_text(json.dumps(
        {"id": 1, "categoryId": 11, "name": {"fr": "S1"}, "description": {"fr": "Vaincre X."}}))
    assert len(await succes_du_donjon(ClientEnCache(None, tmp_path), 1)) == 1


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


def test_formater_regle_duo_sans_le_parametre_de_tours():
    duo = "Vaincre tous les monstres avec 2 personnages maximum et en moins de {1} tours."
    assert formater_regle(duo) == "Finir le donjon à deux personnages au plus."


def test_formater_regle_fixe_reste_telle_quelle():
    regle = "Les ennemis ne doivent pas recevoir de soin."
    assert formater_regle(regle + "\n") == regle


def test_formater_regle_aleatoire_explique_et_ne_nomme_aucun_monstre():
    texte = formater_regle("{0} doit être achevé en premier.")
    regle, marque, explication = texte.partition(MARQUE_ALEATOIRE)
    assert regle == "Le monstre désigné par le jeu doit être achevé en premier." and marque
    assert "{" not in texte and "changer d'un combat à l'autre" in explication


async def test_regle_du_defi_lue_chez_dofusdb_et_introuvable_sans_cache(tmp_path):
    texte = "Les combattants alliés doivent utiliser exactement un point de mouvement par tour de jeu."
    (tmp_path / "challenge-115.json").write_text(json.dumps({"id": 115, "description": {"fr": texte}}))
    c = ClientEnCache(None, tmp_path)
    assert (await regle_du_defi(c, 115)).startswith("Les combattants alliés")
    assert await regle_du_defi(c, 999) is None
    assert id_du_defi("Vaincre X en validant le challenge [challenge,115].") == 115 and id_du_defi("Vaincre X.") is None
