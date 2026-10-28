"""Le relevé du schéma de Duffus (ARCHITECTURE §6.3) : quelles tables, quelles colonnes, de quel type.

1. l'OpenAPI publiée par PostgREST à la racine `/rest/v1/` ;
2. si elle est fermée, une seule ligne de chaque table connue (`limit=1`), dont on lit les colonnes.
Le résultat va dans `donnees/duffus/schema-AAAA-MM-JJ.json`. Aucune valeur de ligne n'y est écrite.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from epreuve.duffus.client import Absente, ClientDuffus

TABLES_CONNUES = ("guide_ranges", "quest_list", "quest_pages", "dungeon_pages", "achievements",
                  "achievement_objectives", "monsters", "dofus_list")


def _type(v: object) -> str:
    return {bool: "boolean", int: "integer", float: "number", str: "string", list: "array",
            dict: "object", type(None): "null"}[type(v)]


def schema_depuis_openapi(api: dict) -> dict[str, dict[str, str]]:
    tables = {}
    for nom, d in sorted(api.get("definitions", {}).items()):
        tables[nom] = {col: p.get("format") or p.get("type", "?")
                       for col, p in sorted(d.get("properties", {}).items())}
    return tables


async def relever(client: ClientDuffus, tables: tuple[str, ...] = TABLES_CONNUES) -> dict:
    api = await client.openapi()
    if api is not None:
        return {"source": "openapi", "tables": schema_depuis_openapi(api)}
    resultat: dict[str, dict[str, str]] = {}
    for table in tables:
        try:
            lignes = await client.une_ligne(table)
        except Absente:
            resultat[table] = {}
            continue
        resultat[table] = {k: _type(v) for k, v in sorted(lignes[0].items())} if lignes else {}
    return {"source": "une_ligne", "tables": resultat}


def ecrire_releve(releve: dict, dossier: Path, jour: date) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    f = dossier / f"schema-{jour.isoformat()}.json"
    f.write_text(json.dumps(releve, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return f
