"""Aspiration des tables de l'encyclopédie et des stuffs (lot E2, docs/lots/E2.md).

Mêmes règles de politesse que le lot B (le client `ClientDuffus` : 1 requête par seconde, arrêt sur 401, 403
et 404), avec deux différences dues au volume (21 554 objets, 5 129 monstres) :

- **pagination par clé** (`id > dernier vu`, 1 000 lignes) plutôt que par décalage : une page ne dépend pas
  de ce qui précède, et l'aspiration **reprend** là où elle s'est arrêtée. Chaque page lue est écrite tout de
  suite dans `.en-cours/<table>/NNNNN.jsonl` ; une relance repart de la dernière clé écrite ;
- **réduction** des colonnes JSON volumineuses au moment de la validation : un effet d'objet garde
  `[effet, min, max, valeur]` au lieu de ses 30 champs, un grade de monstre ses caractéristiques utiles.

Quand une table est complète, ses pages sont fusionnées dans `donnees/duffus/encyclopedie/<table>.jsonl`
(une ligne JSON par enregistrement, triée par clé, clés triées : un `git diff` montre ce qui a changé) et le
dossier `.en-cours/<table>` est supprimé. Une table déjà complète n'est pas relue, sauf `refaire`.

Les stuffs recommandés sont ceux de la page « Équipements PvM » de duffus.fr : son code public lit la table
`builder` filtrée sur **le compte de l'auteur** (`COMPTE_STUFFS`) et `is_public`. On applique le même filtre :
aucun stuff d'utilisateur n'est lu, et l'identifiant du compte n'est pas recopié dans les extraits.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from epreuve.duffus.client import ClientDuffus, ErreurDuffus

TAILLE_PAGE = 1000
# Le compte de l'auteur dont la page « Équipements PvM » (/builds-pvm) affiche les stuffs publics.
COMPTE_STUFFS = "9034e4c8-e540-403c-9de2-2179d0a14ec6"


class _Ligne(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Objet(_Ligne):
    id: int
    name: str | None
    typeid: int
    level: int | None = None
    description: str | None = None
    iconid: int | None = None
    itemsetid: int | None = None
    possibleeffects_json: list[dict[str, Any]] | None = None
    criterions: str | None = None
    dropmonsterids_json: list[int] | None = None
    price: int | None = None
    realweight: int | None = None
    apcost: int | None = None
    range: int | None = None
    minrange: int | None = None
    maxcastperturn: int | None = None
    criticalhitprobability: int | None = None
    criticalhitbonus: int | None = None
    twohanded: bool | None = None
    etheral: bool | None = None
    exchangeable: bool | None = None
    islegendary: bool | None = None


class TypeObjet(_Ligne):
    id: int
    name: str | None
    supertypeid: int | None = None
    categoryid: int | None = None


class Panoplie(_Ligne):
    id: int
    name: str | None
    items_json: list[int] | None = None
    effectsbycount_json: dict[str, list[dict[str, Any]]] | None = None


class Recette(_Ligne):
    resultid: int
    resultlevel: int | None = None
    ingredientids_json: list[int]
    quantities_json: list[int]
    jobid: int | None = None


class Effet(_Ligne):
    id: int
    description: str | None
    characteristic: int | None = None
    category: int | None = None
    bonustype: int | None = None
    elementid: int | None = None
    effectpriority: int | None = None
    usedice: int | None = None


class Monstre(_Ligne):
    id: int
    name: str | None
    race: int | None = None
    gfxid: int | None = None
    grades_json: list[dict[str, Any]] | None = None
    drops_json: list[dict[str, Any]] | None = None


class Race(_Ligne):
    id: int
    name: str | None
    superraceid: int | None = None


class Stuff(_Ligne):
    id: str
    name: str | None
    classe: str | None = None
    level: int | None = None
    gender: str | None = None
    objets: dict[str, Any] | None = None
    dofus: list[int | None] | None = None
    tags: list[str] | None = None
    caracs_base: dict[str, Any] | None = None
    caracs_parcho: dict[str, Any] | None = None
    updated_at: str | None = None


# --- Réductions : on ne garde que ce que les fiches affichent -------------------------------------------


def effets_compacts(effets: list[dict] | None) -> list[list[int]]:
    """[[effet, min, max, valeur], …] ; `min`/`max` sont les dés du jeu (diceNum, diceSide)."""
    sortie = []
    for e in effets or []:
        ident = e.get("effectId", e.get("actionId"))
        if ident is None:
            continue
        sortie.append([int(ident), int(e.get("diceNum") or 0), int(e.get("diceSide") or 0), int(e.get("value") or 0)])
    return sortie


GRADE = {"grade": "grade", "level": "niveau", "lifePoints": "pv", "actionPoints": "pa", "movementPoints": "pm",
         "xp": "xp", "reductionNeutral": "res_neutre", "reductionEarth": "res_terre", "reductionFire": "res_feu",
         "reductionWater": "res_eau", "reductionAir": "res_air", "paLostDodge": "esq_pa", "mpLostDodge": "esq_pm"}


def grades_compacts(grades: list[dict] | None) -> list[dict]:
    return [{court: g.get(long) for long, court in GRADE.items()} for g in grades or []]


def drops_compacts(drops: list[dict] | None) -> list[list[int]]:
    """[[objet, % au grade 1, % au grade 5, sous condition (0/1)], …]"""
    sortie = []
    for d in drops or []:
        if d.get("objectId") is None:
            continue
        p1 = d.get("percentDropForGrade1") or 0
        p5 = d.get("percentDropForGrade5", p1) or 0
        condition = 1 if d.get("hasCriterions") else 0
        sortie.append([int(d["objectId"]), round(float(p1), 2), round(float(p5), 2), condition])
    return sortie


def _objet(o: Objet) -> dict:
    panoplie = o.itemsetid if o.itemsetid and o.itemsetid > 0 else None  # -1 : aucune
    ligne = {"id": o.id, "nom": o.name, "type": o.typeid, "niveau": o.level, "description": o.description,
             "icone": o.iconid, "panoplie": panoplie, "effets": effets_compacts(o.possibleeffects_json),
             "conditions": o.criterions or None, "drops": sorted(set(o.dropmonsterids_json or [])),
             "prix": o.price, "poids": o.realweight, "echangeable": o.exchangeable,
             "legendaire": o.islegendary, "etheree": o.etheral}
    if o.apcost:  # une arme
        ligne["arme"] = {"pa": o.apcost, "po_min": o.minrange, "po_max": o.range, "par_tour": o.maxcastperturn,
                         "cc": o.criticalhitprobability, "bonus_cc": o.criticalhitbonus, "deux_mains": o.twohanded}
    return ligne


def _recette(r: Recette) -> dict:
    if len(r.ingredientids_json) != len(r.quantities_json):
        raise ValueError("ingrédients et quantités de longueurs différentes")
    return {"objet": r.resultid, "niveau": r.resultlevel, "metier": r.jobid,
            "ingredients": [[i, q] for i, q in zip(r.ingredientids_json, r.quantities_json, strict=True)]}


def _stuff(s: Stuff) -> dict:
    objets = {k: v for k, v in (s.objets or {}).items() if isinstance(v, int) and not k.endswith("Var")}
    return {"id": s.id, "nom": s.name, "classe": s.classe, "niveau": s.level, "sexe": s.gender, "objets": objets,
            "dofus": [d for d in (s.dofus or []) if isinstance(d, int)], "tags": s.tags or [],
            "caracs_base": s.caracs_base or {}, "caracs_parcho": s.caracs_parcho or {}, "maj_le": s.updated_at}


@dataclass(frozen=True)
class TableE2:
    nom: str  # nom du fichier écrit
    source: str  # table Duffus
    modele: type[_Ligne]
    reduire: Callable[[Any], dict]
    cle: str = "id"  # clé de pagination côté Duffus
    cle_sortie: str = "id"  # clé de tri de l'extrait
    filtres: dict[str, str] = field(default_factory=dict)


TABLES: dict[str, TableE2] = {t.nom: t for t in (
    TableE2("types", "item_types", TypeObjet,
            lambda o: {"id": o.id, "nom": o.name, "super_type": o.supertypeid, "categorie": o.categoryid}),
    TableE2("effets", "effects", Effet,
            lambda e: {"id": e.id, "description": e.description, "caracteristique": e.characteristic,
                       "categorie": e.category, "bonus": e.bonustype, "element": e.elementid,
                       "priorite": e.effectpriority, "des": e.usedice}),
    TableE2("races", "monster_races", Race, lambda r: {"id": r.id, "nom": r.name, "super_race": r.superraceid}),
    TableE2("panoplies", "item_sets", Panoplie,
            lambda p: {"id": p.id, "nom": p.name, "objets": p.items_json or [],
                       "bonus": {k: effets_compacts(v) for k, v in sorted((p.effectsbycount_json or {}).items(),
                                                                           key=lambda kv: int(kv[0])) if v}}),
    TableE2("recettes", "recipes", Recette, _recette, cle="resultid", cle_sortie="objet"),
    TableE2("monstres", "monsters", Monstre,
            lambda m: {"id": m.id, "nom": m.name, "race": m.race, "gfx": m.gfxid,
                       "grades": grades_compacts(m.grades_json), "drops": drops_compacts(m.drops_json)}),
    TableE2("objets", "items", Objet, _objet),
    TableE2("stuffs", "builder", Stuff, _stuff,
            filtres={"user_id": f"eq.{COMPTE_STUFFS}", "is_public": "eq.true"}),
)}  # fmt: skip


def colonnes(modele: type[_Ligne]) -> str:
    return ",".join(modele.model_fields)


def valider(table: TableE2, brutes: list[dict]) -> list[dict]:
    sortie = []
    for brute in brutes:
        try:
            sortie.append(table.reduire(table.modele.model_validate(brute)))
        except ValidationError as e:
            err = e.errors()[0]
            col = ".".join(str(x) for x in err["loc"])
            quoi = "manquant" if err["type"] == "missing" else f"invalide ({err['msg']})"
            raise ErreurDuffus(f"`{table.source}.{col}` {quoi} : le schéma de Duffus a changé, refaire le relevé"
                               ) from None
        except ValueError as e:
            raise ErreurDuffus(f"`{table.source}` ligne {brute.get(table.cle)} : {e}") from None
    return sortie


def _jsonl(lignes: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in lignes)


def lire_jsonl(f: Path) -> list[dict]:
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]


def _ecrire(f: Path, contenu: str) -> None:
    """Écriture atomique : une coupure ne laisse jamais un fichier à moitié écrit."""
    tmp = f.with_suffix(f.suffix + ".tmp")
    tmp.write_text(contenu, encoding="utf-8")
    tmp.replace(f)


@dataclass
class RapportE2:
    comptes: dict[str, int] = field(default_factory=dict)
    reprises: dict[str, int] = field(default_factory=dict)  # table → pages déjà là au départ
    deja_completes: list[str] = field(default_factory=list)

    def texte(self) -> str:
        lignes = ["Aspiration de l'encyclopédie → donnees/duffus/encyclopedie/"]
        for nom, n in self.comptes.items():
            note = f" (reprise après {self.reprises[nom]} pages)" if self.reprises.get(nom) else ""
            lignes.append(f"  {nom} : {n} lignes{note}")
        for nom in self.deja_completes:
            lignes.append(f"  {nom} : déjà complète, non relue (--refaire pour la relire)")
        return "\n".join(lignes)


async def aspirer_table(client: ClientDuffus, table: TableE2, dossier: Path, refaire: bool = False,
                        taille: int = TAILLE_PAGE) -> tuple[int, int] | None:
    """Aspire une table avec reprise. Renvoie (lignes, pages reprises), ou None si elle était déjà complète."""
    final = dossier / f"{table.nom}.jsonl"
    partiel = dossier / ".en-cours" / table.nom
    if final.exists() and not refaire and not partiel.exists():
        return None
    partiel.mkdir(parents=True, exist_ok=True)
    pages = sorted(partiel.glob("*.jsonl"))
    reprises = len(pages)
    dernier: Any = None
    fini = False
    if pages:
        derniere = json.loads((partiel / ".cles.json").read_text(encoding="utf-8")) if (
            partiel / ".cles.json").exists() else {}
        dernier = derniere.get("dernier")
        fini = bool(derniere.get("fini"))
    n = len(pages)
    while not fini:
        params = {"select": colonnes(table.modele), "order": f"{table.cle}.asc", "limit": str(taille),
                  **table.filtres}
        if dernier is not None:
            params[table.cle] = f"gt.{dernier}"
        brutes = await client.lire_page(table.source, params)
        lignes = valider(table, brutes)
        if brutes:
            dernier = brutes[-1][table.cle]
            _ecrire(partiel / f"{n:05d}.jsonl", _jsonl(lignes))
            n += 1
        fini = len(brutes) < taille
        # La clé de reprise s'écrit APRÈS la page : une coupure entre les deux relit au pire une page.
        _ecrire(partiel / ".cles.json", json.dumps({"dernier": dernier, "fini": fini}))
    toutes: dict[Any, dict] = {}
    for f in sorted(partiel.glob("*.jsonl")):
        for r in lire_jsonl(f):
            toutes[r[table.cle_sortie]] = r
    lignes = [toutes[k] for k in sorted(toutes)]
    _ecrire(final, _jsonl(lignes))
    shutil.rmtree(partiel)
    return len(lignes), reprises


async def aspirer(client: ClientDuffus, dossier: Path, tables: tuple[str, ...] | None = None,
                  refaire: bool = False) -> RapportE2:
    noms = tables or tuple(TABLES)
    inconnues = [n for n in noms if n not in TABLES]
    if inconnues:
        raise ErreurDuffus(f"table inconnue : {', '.join(inconnues)} (connues : {', '.join(TABLES)})")
    dossier.mkdir(parents=True, exist_ok=True)
    rapport = RapportE2()
    for nom in noms:
        r = await aspirer_table(client, TABLES[nom], dossier, refaire)
        if r is None:
            rapport.deja_completes.append(nom)
        else:
            rapport.comptes[nom], rapport.reprises[nom] = r
    return rapport
