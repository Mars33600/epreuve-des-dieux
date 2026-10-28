"""Aspiration du lot E2 : pagination par clé, reprise après coupure, réduction, filtre des stuffs."""

import json

import httpx
import pytest

from epreuve.duffus import encyclopedie as e
from epreuve.duffus.client import ClientDuffus, ErreurDuffus
from tests.duffus.test_client import Horloge


def objet(i: int) -> dict:
    return {"id": i, "name": f"Objet {i}", "typeid": 9, "level": i % 200, "iconid": 1000 + i, "itemsetid": -1,
            "possibleeffects_json": [{"effectId": 118, "diceNum": 1, "diceSide": 5, "value": 0, "rid": "x",
                                      "zoneDescr": {"shape": 67}}],
            "dropmonsterids_json": [31, 31], "name_unaccent": "inutile", "resourcesbysubarea_json": [1, 2]}


class FauxDuffus:
    """Un PostgREST minimal : order=id.asc, id=gt.N, limit ; peut tomber en panne après n requêtes."""

    def __init__(self, lignes: dict[str, list[dict]], panne_apres: int | None = None):
        self.lignes, self.panne_apres, self.requetes = lignes, panne_apres, []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requetes.append(req)
        if self.panne_apres is not None and len(self.requetes) > self.panne_apres:
            return httpx.Response(403, json={"message": "refusé"})
        table = req.url.path.removeprefix("/rest/v1/")
        cle = req.url.params["order"].removesuffix(".asc")
        lignes = sorted(self.lignes[table], key=lambda r: r[cle])
        if cle in req.url.params:
            borne = req.url.params[cle].removeprefix("gt.")
            lignes = [r for r in lignes if str(r[cle]) > borne] if isinstance(lignes[0][cle], str) else [
                r for r in lignes if r[cle] > int(borne)]
        return httpx.Response(200, json=lignes[: int(req.url.params["limit"])])


def client(faux):
    h = Horloge()
    return ClientDuffus("https://exemple.supabase.co", "CLE", transport=httpx.MockTransport(faux), horloge=h,
                        dormir=h.dormir)


async def test_pagination_par_cle_et_reduction(tmp_path):
    faux = FauxDuffus({"items": [objet(i) for i in range(1, 26)]})
    async with client(faux) as c:
        n, reprises = await e.aspirer_table(c, e.TABLES["objets"], tmp_path, taille=10)
    assert (n, reprises) == (25, 0)
    assert [r.url.params.get("id") for r in faux.requetes] == [None, "gt.10", "gt.20"]
    assert "name_unaccent" not in faux.requetes[0].url.params["select"]
    lignes = e.lire_jsonl(tmp_path / "objets.jsonl")
    assert [r["id"] for r in lignes] == list(range(1, 26))
    assert lignes[0]["effets"] == [[118, 1, 5, 0]] and lignes[0]["drops"] == [31] and lignes[0]["panoplie"] is None
    assert "resourcesbysubarea_json" not in lignes[0] and not (tmp_path / ".en-cours" / "objets").exists()


async def test_reprise_apres_coupure(tmp_path):
    donnees = {"items": [objet(i) for i in range(1, 26)]}
    coupe = FauxDuffus(donnees, panne_apres=2)
    async with client(coupe) as c:
        with pytest.raises(ErreurDuffus):
            await e.aspirer_table(c, e.TABLES["objets"], tmp_path, taille=10)
    assert len(list((tmp_path / ".en-cours" / "objets").glob("*.jsonl"))) == 2
    assert not (tmp_path / "objets.jsonl").exists()
    reprise = FauxDuffus(donnees)
    async with client(reprise) as c:
        n, reprises = await e.aspirer_table(c, e.TABLES["objets"], tmp_path, taille=10)
    assert (n, reprises) == (25, 2)
    assert [r.url.params.get("id") for r in reprise.requetes] == ["gt.20"]  # une seule page relue
    assert [r["id"] for r in e.lire_jsonl(tmp_path / "objets.jsonl")] == list(range(1, 26))


async def test_table_complete_non_relue_sauf_refaire(tmp_path):
    faux = FauxDuffus({"item_types": [{"id": 2, "name": "Arc", "supertypeid": 2, "categoryid": 0}]})
    async with client(faux) as c:
        r1 = await e.aspirer(c, tmp_path, ("types",))
        r2 = await e.aspirer(c, tmp_path, ("types",))
        r3 = await e.aspirer(c, tmp_path, ("types",), refaire=True)
    assert r1.comptes == {"types": 1} and r2.deja_completes == ["types"] and r3.comptes == {"types": 1}
    assert len(faux.requetes) == 2
    assert "déjà complète" in r2.texte()


async def test_stuffs_du_seul_compte_de_l_auteur_sans_son_identifiant(tmp_path):
    stuff = {"id": "a-1", "name": "Iop Terre", "classe": "Iop", "level": 20, "gender": "M", "user_id": "secret",
             "objets": {"arme": 44, "armeVar": None, "coiffe": None}, "dofus": [972, None], "tags": ["Force"],
             "caracs_base": {}, "caracs_parcho": {}, "updated_at": "2026-09-01T00:00:00+00:00"}
    faux = FauxDuffus({"builder": [stuff]})
    async with client(faux) as c:
        await e.aspirer(c, tmp_path, ("stuffs",))
    params = faux.requetes[0].url.params
    assert params["user_id"] == f"eq.{e.COMPTE_STUFFS}" and params["is_public"] == "eq.true"
    assert "user_id" not in params["select"]
    texte = (tmp_path / "stuffs.jsonl").read_text(encoding="utf-8")
    assert "secret" not in texte and e.COMPTE_STUFFS not in texte
    ligne = json.loads(texte)
    assert ligne["objets"] == {"arme": 44} and ligne["dofus"] == [972]


async def test_colonne_manquante_arrete_tout(tmp_path):
    faux = FauxDuffus({"recipes": [{"resultid": 1, "ingredientids_json": [2]}]})
    async with client(faux) as c:
        with pytest.raises(ErreurDuffus, match="quantities_json"):
            await e.aspirer(c, tmp_path, ("recettes",))
    assert not (tmp_path / "recettes.jsonl").exists()


async def test_table_inconnue(tmp_path):
    async with client(FauxDuffus({})) as c:
        with pytest.raises(ErreurDuffus, match="inconnue"):
            await e.aspirer(c, tmp_path, ("builder_des_joueurs",))


def test_reductions():
    assert e.drops_compacts([{"objectId": 7, "percentDropForGrade1": 1.234, "percentDropForGrade5": 2,
                              "hasCriterions": 1}, {"dropId": 3}]) == [[7, 1.23, 2.0, 1]]
    assert e.grades_compacts([{"grade": 1, "level": 16, "lifePoints": 90, "inutile": 3}])[0]["pv"] == 90


def test_nouvelles_tables_reduites_et_sans_donnees_utilisateur():
    assert {"sorts", "niveaux_sorts", "classes", "pnj", "quetes", "etapes_quetes", "objectifs_quetes",
            "recompenses_quetes"} <= set(e.TABLES)
    # Seule la table `builder` (stuffs de l'auteur) est filtrée ; aucune table de compte ni de progression.
    sources = {t.source for t in e.TABLES.values()}
    assert not sources & {"user_quest", "profiles", "craft_plan", "craft_folders"}
    quete = e.TABLES["quetes"]
    sortie = e.valider(quete, [{"id": 1, "name": "Q", "type": 2, "level_min": 5, "level_max": 6,
                                "is_event": 0, "step_ids_json": [9], "quest_json": {"gros": 1},
                                "start_position_json": [{"mapId": 3, "npcId": 4}]}])[0]
    assert sortie["depart"] == [{"carte": 3, "pnj": 4}] and sortie["etapes"] == [9] and "quest_json" not in sortie
    obj = e.TABLES["objectifs_quetes"]
    assert e.valider(obj, [{"id": 1, "step_id": 2, "type_class": "QuestObjectiveGoToNpcData", "parameter0": 7}]
                     )[0]["classe"] == "GoToNpc"
