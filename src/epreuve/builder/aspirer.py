"""Lecture des tables de référence du builder de Duffus : `items` (équipements seulement) et `item_sets`.

On ne lit jamais la table `builder` de Duffus : ce sont les builds de ses utilisateurs, avec leur identifiant.
Le client (`duffus/client.py`) impose la politesse : 1 requête par seconde au plus, arrêt sur refus.
Environ 5 requêtes : 4 pages d'objets (≈ 3 800 équipements) et 1 page de panoplies.

Le résultat est réduit à ce que le calcul utilise, trié par identifiant, une ligne par enregistrement :
deux aspirations identiques donnent des fichiers identiques, et un `git diff` montre les changements du jeu.
Les icônes ne sont pas recopiées : la page les demande à DofusDB par `iconid`.
"""

from __future__ import annotations

import json
from pathlib import Path

from epreuve.builder.effets import EFFET_CARAC, TOUS_LES_TYPES
from epreuve.duffus.client import ClientDuffus, ErreurDuffus

COLONNES_OBJETS = "id,name,level,typeid,iconid,itemsetid,simpleeffects_json,criterions"
COLONNES_PANOPLIES = "id,name,items_json,simple_effectsbycount_json"


def _effets(liste: list | None) -> list[list[int]]:
    """[[effectId, from, to], …] des seuls effets de caractéristique, dans l'ordre de l'objet."""
    sortie = []
    for e in liste or []:
        eid = int(e.get("effectId", 0))
        if eid in EFFET_CARAC:
            de, a = (e.get(k, 0) for k in ("from", "to"))
            sortie.append([eid, *(int(v) if isinstance(v, int | float) else 0 for v in (de, a))])
    return sortie


def _panoplie(v: object) -> int | None:
    """Duffus note « pas de panoplie » -1 (ou vide)."""
    return int(v) if isinstance(v, int) and v > 0 else None


def reduire_objet(brut: dict) -> dict:
    for col in ("id", "name", "level", "typeid"):
        if col not in brut:
            raise ErreurDuffus(f"items : colonne {col} absente, le schéma de Duffus a changé")
    return {"id": int(brut["id"]), "nom": brut["name"] or "", "niveau": int(brut["level"] or 1),
            "type": int(brut["typeid"]), "icone": brut.get("iconid"), "panoplie": _panoplie(brut.get("itemsetid")),
            "conditions": brut.get("criterions") or None, "effets": _effets(brut.get("simpleeffects_json"))}


def reduire_panoplie(brut: dict) -> dict:
    par_nombre = brut.get("simple_effectsbycount_json") or {}
    if isinstance(par_nombre, str):
        par_nombre = json.loads(par_nombre)
    objets = brut.get("items_json") or []
    if isinstance(objets, str):
        objets = json.loads(objets)
    bonus = {str(int(k)): _effets(v) for k, v in par_nombre.items() if str(k).isdigit()}
    return {"id": int(brut["id"]), "nom": brut.get("name") or "Panoplie", "objets": [int(x) for x in objets],
            "bonus": dict(sorted(bonus.items(), key=lambda kv: int(kv[0])))}


def _ecrire(f: Path, lignes: list[dict]) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    corps = ",\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in lignes)
    f.write_text("[\n" + corps + "\n]\n", encoding="utf-8")


async def aspirer(client: ClientDuffus, dossier: Path) -> tuple[int, int]:
    """Écrit `objets.json` et `panoplies.json` dans `dossier`. Renvoie (nb d'objets, nb de panoplies)."""
    types = ",".join(str(t) for t in sorted(TOUS_LES_TYPES))
    bruts = await client.lire_table("items", COLONNES_OBJETS, filtres={"typeid": f"in.({types})"})
    objets = sorted((reduire_objet(b) for b in bruts), key=lambda o: o["id"])
    utiles = {o["panoplie"] for o in objets if o["panoplie"]}
    panoplies = sorted((reduire_panoplie(b) for b in await client.lire_table("item_sets", COLONNES_PANOPLIES)
                        if int(b["id"]) in utiles), key=lambda p: p["id"])
    if not objets:
        raise ErreurDuffus("items : aucun équipement lu, on n'écrase pas les données existantes")
    _ecrire(dossier / "objets.json", objets)
    _ecrire(dossier / "panoplies.json", panoplies)
    return len(objets), len(panoplies)
