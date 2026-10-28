"""Construit les données des outils (E4) à partir des tables de Duffus, en lecture seule et sans aucun
utilisateur : objets, recettes, types d'objet, générations de montures, classes, sorts.

    uv run python -m epreuve.outils aspirer

Le client `duffus/` est poli par construction (1 requête par seconde). Le résultat est écrit en JSON compact
dans `src/epreuve/outils/donnees/` et versionné : le site ne parle jamais à Duffus en marche normale.
"""

from __future__ import annotations

import json
from pathlib import Path

from epreuve.duffus.client import ClientDuffus

DONNEES = Path(__file__).parent / "donnees"
TYPES_MONTURES = {331: "dragodinde", 332: "muldo", 333: "volkorne"}
PAQUET_IDS = 120
METIERS = {2: "Bûcheron", 11: "Forgeron", 13: "Sculpteur", 15: "Cordonnier", 16: "Bijoutier", 24: "Mineur",
           26: "Alchimiste", 27: "Tailleur", 28: "Paysan", 36: "Pêcheur", 41: "Chasseur", 60: "Façonneur",
           65: "Bricoleur", 79: "Éleveur"}


def ecrire(nom: str, donnees: object) -> Path:
    DONNEES.mkdir(parents=True, exist_ok=True)
    f = DONNEES / nom
    f.write_text(json.dumps(donnees, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return f


def ratio_xp(objet: dict, types: dict[int, int]) -> int:
    """Rapport d'XP de craft : celui de l'objet, sinon celui de son type ; -1 (« normal ») vaut 100 ; inconnu, 0."""
    r = objet.get("craftxpratio")
    if r is None or r == -1:
        r = types.get(objet.get("typeid"))
    if r is None:
        return 0
    return 100 if r == -1 else int(r)


async def construire_craft(client: ClientDuffus) -> dict:
    recettes = await client.lire_table(
        "recipes", "resultid,resultname,resultlevel,jobid,ingredientids_json,quantities_json", ordre="resultid")
    types = {t["id"]: t.get("craftrxratio") for t in await client.lire_table("item_types", "id,craftrxratio")}
    items = await client.lire_table("items", "id,name,level,typeid,craftxpratio")
    par_id = {i["id"]: i for i in items}
    utiles: set[int] = set()
    sortie = []
    for r in recettes:
        ings = list(zip(r.get("ingredientids_json") or [], r.get("quantities_json") or [], strict=False))
        if not ings or r["jobid"] not in METIERS:
            continue
        utiles.add(r["resultid"])
        utiles.update(i for i, _ in ings)
        sortie.append([r["resultid"], r["jobid"], r["resultlevel"] or 0, [[i, q] for i, q in ings]])
    noms = {}
    for i in sorted(utiles):
        o = par_id.get(i)
        noms[i] = [o["name"] if o else f"Objet {i}", ratio_xp(o, types) if o else 0]
    return {"metiers": {str(k): v for k, v in METIERS.items()}, "objets": {str(k): v for k, v in noms.items()},
            "recettes": sortie, "montures": montures_de(items)}


def montures_de(items: list[dict]) -> dict:
    return {nom: [[i["id"], i["name"]] for i in sorted(items, key=lambda i: i["name"]) if i["typeid"] == t]
            for t, nom in TYPES_MONTURES.items()}


async def construire_classes(client: ClientDuffus) -> list[dict]:
    classes = await client.lire_table("breeds", "id,shortname,description,gameplaydescription,breedspellsid_json")
    ids = sorted({s for c in classes for s in c.get("breedspellsid_json") or []})
    sorts: dict[int, dict] = {}
    niveaux: dict[int, list[dict]] = {}
    for debut in range(0, len(ids), PAQUET_IDS):
        paquet = ",".join(map(str, ids[debut:debut + PAQUET_IDS]))
        for s in await client.lire_table("spells", "id,name,description,order", filtres={"id": f"in.({paquet})"}):
            sorts[s["id"]] = s
        for n in await client.lire_table(
                "spell_levels", "id,spellid,grade,apcost,minrange,range,criticalhitprobability,maxcastperturn,"
                "mincastinterval,minplayerlevel", filtres={"spellid": f"in.({paquet})"}):
            niveaux.setdefault(n["spellid"], []).append(n)
    sortie = []
    for c in sorted(classes, key=lambda c: c["shortname"]):
        liste = []
        for sid in c.get("breedspellsid_json") or []:
            s = sorts.get(sid)
            if s is None:
                continue
            gr = sorted(niveaux.get(sid, []), key=lambda n: n["grade"])
            liste.append({"id": sid, "nom": s["name"], "texte": s["description"] or "", "niveaux": [
                [n["grade"], n["apcost"], n["minrange"], n["range"], n["criticalhitprobability"],
                 n["maxcastperturn"], n["mincastinterval"], n["minplayerlevel"]] for n in gr]})
        sortie.append({"id": c["id"], "nom": c["shortname"], "texte": c["gameplaydescription"] or "",
                       "histoire": c["description"] or "", "sorts": liste})
    return sortie


async def aspirer(client: ClientDuffus) -> list[Path]:
    craft = await construire_craft(client)
    fichiers = [ecrire("craft.json", {k: v for k, v in craft.items() if k != "montures"})]
    generations = await client.lire_table("mount_generations", "item_id,generation", ordre="item_id")
    gen = {g["item_id"]: g["generation"] for g in generations}
    montures = {n: [[i, nom, gen.get(i)] for i, nom in liste] for n, liste in craft["montures"].items()}
    fichiers.append(ecrire("montures.json", montures))
    fichiers.append(ecrire("classes.json", await construire_classes(client)))
    return fichiers
