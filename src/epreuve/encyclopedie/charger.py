"""Chargement des extraits `donnees/duffus/encyclopedie/*.jsonl` dans les tables `ency_*` (lot E2).

Tout ou rien : les tables sont vidées puis remplies dans **une seule transaction**. Pendant le chargement, le
site continue de servir l'ancienne copie ; une erreur laisse la base telle qu'elle était. Aucun réseau.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from epreuve.duffus.encyclopedie import chemin_jsonl, lire_jsonl
from epreuve.encyclopedie import tables as t
from epreuve.encyclopedie.textes import cle_recherche, famille_du_super_type

RACINE = Path(__file__).resolve().parents[3]
DOSSIER = RACINE / "donnees" / "duffus" / "encyclopedie"
PAQUET = 2000  # lignes par INSERT


class ExtraitManquant(Exception):
    pass


@dataclass
class RapportChargement:
    comptes: dict[str, int] = field(default_factory=dict)

    def texte(self) -> str:
        return "Encyclopédie chargée :\n" + "\n".join(f"  {k} : {n} lignes" for k, n in self.comptes.items())


def _lire(dossier: Path, nom: str) -> list[dict]:
    f = dossier / f"{nom}.jsonl"
    if not chemin_jsonl(f).exists():
        raise ExtraitManquant(f"{f.name} absent : lancer d'abord `python -m epreuve.duffus encyclopedie`")
    return lire_jsonl(f)


def _niveaux(grades: list[dict]) -> tuple[int | None, int | None]:
    niveaux = [g["niveau"] for g in grades if isinstance(g.get("niveau"), int)]
    return (min(niveaux), max(niveaux)) if niveaux else (None, None)


def _date(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def _guide_quetes(dossier: Path) -> dict[str, dict]:
    """Les quêtes du guide Duffus déjà importées (lot B), par titre sans accents : zone et catégorie.

    Facultatif : sans ce fichier, les fiches n'ont simplement ni zone ni catégorie.
    """
    fichiers = sorted((dossier.parent).glob("20*/quest_list.json"))
    if not fichiers:
        return {}
    guide: dict[str, dict] = {}
    for q in json.loads(fichiers[-1].read_text(encoding="utf-8")):
        cle = cle_recherche(q.get("title"))
        if cle and cle not in guide:
            guide[cle] = q
    return guide


def _sorts(dossier: Path) -> tuple[list[dict], list[dict]]:
    classes = _lire(dossier, "classes")
    classe_du_sort = {s: c["id"] for c in classes for s in c["sorts"]}
    niveaux: dict[int, list[dict]] = defaultdict(list)
    for n in _lire(dossier, "niveaux_sorts"):
        niveaux[n["sort"]].append({k: v for k, v in n.items() if k not in ("id", "sort")})
    sorts = []
    for s in _lire(dossier, "sorts"):
        if not s["nom"]:
            continue
        liste = sorted(niveaux.get(s["id"], []), key=lambda n: n["grade"] or 0)
        sorts.append({"id": s["id"], "nom": s["nom"], "cle_recherche": cle_recherche(s["nom"]),
                      "description": s["description"], "icone": s["icone"], "type_id": s["type"],
                      "classe_id": classe_du_sort.get(s["id"]),
                      "niveau_min": min((n["niveau"] for n in liste if n["niveau"] is not None), default=None),
                      "niveaux": liste})
    return ([{"id": c["id"], "nom": c["nom"] or f"Classe {c['id']}", "description": c["description"],
              "role": c["role"], "sorts": c["sorts"]} for c in classes], sorts)


def _quetes(dossier: Path) -> list[dict]:
    guide = _guide_quetes(dossier)
    objectifs: dict[int, list[dict]] = defaultdict(list)
    for o in _lire(dossier, "objectifs_quetes"):
        objectifs[o["etape"]].append(o)
    recompenses: dict[int, list[dict]] = defaultdict(list)
    for r in _lire(dossier, "recompenses_quetes"):
        recompenses[r["etape"]].append({k: v for k, v in r.items() if k not in ("id", "etape")})
    etapes: dict[int, dict] = {e["id"]: e for e in _lire(dossier, "etapes_quetes")}
    sortie = []
    for q in _lire(dossier, "quetes"):
        if not q["nom"]:
            continue
        g = guide.get(cle_recherche(q["nom"]), {})
        liste = []
        for ident in q["etapes"]:
            e = etapes.get(ident)
            if e:
                liste.append({"nom": e["nom"], "description": e["description"], "niveau": e["niveau"],
                              "objectifs": [{k: v for k, v in o.items() if k not in ("id", "etape", "type")}
                                            for o in objectifs[e["id"]]],
                              "recompenses": recompenses.get(e["id"], [])})
        sortie.append({
            "id": q["id"], "nom": q["nom"], "cle_recherche": cle_recherche(q["nom"]),
            "categorie": g.get("category") or None, "zone": g.get("zone") or None,
            "niveau_min": q["niveau_min"], "niveau_max": q["niveau_max"], "repetition": q["repetition"],
            "limite": q["limite"], "donjon": bool(q["donjon"]), "groupe": bool(q["groupe"]),
            "evenement": bool(q["evenement"]), "condition": q["condition"], "depart": q["depart"],
            "pnj_ids": sorted({d["pnj"] for d in q["depart"] if d.get("pnj")}), "etapes": liste})
    return sortie


def preparer(dossier: Path) -> dict[str, list[dict]]:
    """Lit les extraits et produit les lignes de chaque table (sans base : testable à part)."""
    types = _lire(dossier, "types")
    famille_type = {x["id"]: famille_du_super_type(x["super_type"]) for x in types}
    lignes: dict[str, list[dict]] = {}
    lignes["ency_type"] = [{"id": x["id"], "nom": x["nom"] or f"Type {x['id']}", "super_type": x["super_type"],
                            "famille": famille_type[x["id"]]} for x in types]
    lignes["ency_effet"] = [{"id": e["id"], "description": e["description"], "caracteristique": e["caracteristique"],
                             "categorie": e["categorie"], "priorite": e["priorite"], "element": e["element"]}
                            for e in _lire(dossier, "effets")]
    niveau_objet = {o["id"]: o["niveau"] for o in _lire(dossier, "objets")}
    lignes["ency_panoplie"] = [
        {"id": p["id"], "nom": p["nom"] or f"Panoplie {p['id']}", "objets": p["objets"], "bonus": p["bonus"],
         "cle_recherche": cle_recherche(p["nom"]),
         "niveau": max((niveau_objet.get(i) or 0 for i in p["objets"]), default=0) or None}
        for p in _lire(dossier, "panoplies")
    ]  # fmt: skip
    lignes["ency_objet"] = [
        {"id": o["id"], "nom": o["nom"], "cle_recherche": cle_recherche(o["nom"]), "type_id": o["type"],
         "famille": famille_type.get(o["type"], "autres"), "niveau": o["niveau"], "description": o["description"],
         "icone": o["icone"], "panoplie_id": o["panoplie"] if o["panoplie"] and o["panoplie"] > 0 else None,
         "effets": o["effets"], "conditions": o["conditions"], "drops": o["drops"], "prix": o["prix"],
         "poids": o["poids"], "arme": o.get("arme"), "echangeable": o["echangeable"], "legendaire": o["legendaire"]}
        for o in _lire(dossier, "objets") if o["nom"]
    ]  # fmt: skip
    lignes["ency_recette"] = [{"objet_id": r["objet"], "niveau": r["niveau"], "metier": r["metier"],
                               "ingredients": r["ingredients"], "ingredient_ids": [i for i, _ in r["ingredients"]]}
                              for r in _lire(dossier, "recettes")]
    lignes["ency_race"] = [{"id": r["id"], "nom": r["nom"] or f"Race {r['id']}", "super_race": r["super_race"]}
                           for r in _lire(dossier, "races")]
    lignes["ency_monstre"] = []
    for m in _lire(dossier, "monstres"):
        if not m["nom"]:
            continue
        bas, haut = _niveaux(m["grades"])
        lignes["ency_monstre"].append({
            "id": m["id"], "nom": m["nom"], "cle_recherche": cle_recherche(m["nom"]), "race_id": m["race"],
            "gfx": m["gfx"], "niveau_min": bas, "niveau_max": haut, "grades": m["grades"], "drops": m["drops"]})
    lignes["ency_stuff"] = [
        {"id": s["id"], "nom": s["nom"] or "Stuff", "classe": s["classe"], "niveau": s["niveau"], "sexe": s["sexe"],
         "objets": s["objets"], "dofus": s["dofus"], "tags": s["tags"],
         "caracs": {"base": s["caracs_base"], "parcho": s["caracs_parcho"]}, "maj_le": _date(s["maj_le"])}
        for s in _lire(dossier, "stuffs") if isinstance(s["niveau"], int) and 1 <= s["niveau"] <= 200
    ]  # fmt: skip
    lignes["ency_classe"], lignes["ency_sort"] = _sorts(dossier)
    lignes["ency_pnj"] = [{"id": p["id"], "nom": p["nom"], "cle_recherche": cle_recherche(p["nom"]),
                           "genre": p["genre"], "visible": bool(p["visible"])}
                          for p in _lire(dossier, "pnj") if p["nom"]]
    lignes["ency_quete"] = _quetes(dossier)
    return lignes


async def _remplir(c: AsyncConnection, lignes: dict[str, list[dict]]) -> None:
    await c.execute(text("TRUNCATE " + ", ".join(f"epreuve.{n}" for n in lignes)))
    for nom, rangs in lignes.items():
        table = t.metadata.tables[f"epreuve.{nom}"]
        for i in range(0, len(rangs), PAQUET):
            await c.execute(table.insert(), rangs[i:i + PAQUET])


async def charger(moteur: AsyncEngine, dossier: Path = DOSSIER) -> RapportChargement:
    lignes = preparer(dossier)
    async with moteur.begin() as c:
        await _remplir(c, lignes)
    return RapportChargement({k: len(v) for k, v in lignes.items()})
