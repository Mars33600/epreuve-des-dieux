"""Les replis DofusDB (T-02, SPEC §6.3, ARCHITECTURE §6.7), quand Duffus ne donne pas une donnée.

- **succès d'un donjon** : `GET /dungeons/{id}` → `achievements`, sans la catégorie Compagnons (142) ; la
  classique est le succès sans défi (pas de `[challenge,` dans sa description) ;
- **nature** pour un Dofus retenu sans guide Duffus : l'objet Dofus (type 23) → `questsThatReward` et
  `achievementsThatReward` → objectifs `Qf=<quête>` / `OA=<succès>` suivis récursivement → prérequis lus dans
  `startCriterion` (les « ET » seulement, `nature.quetes_obligatoires`).

Toutes les réponses lues sont mises en cache dans un dossier (`donnees/dofusdb/`), commité : une
reconstruction relit le cache sans réseau, et les tests tournent sur des réponses réelles.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection
from pathlib import Path

from epreuve.dofusdb.client import ClientDofusDB
from epreuve.domaine.nature import quetes_obligatoires

CATEGORIE_COMPAGNONS = 142
TYPE_DOFUS = 23
_QF = re.compile(r"\bQf=(\d+)")
_OA = re.compile(r"\bOA=(\d+)")


# Ce qu'on garde d'une réponse : le reste (monstres détaillés dans les critères lisibles…) pèserait des Mo.
_GARDER = {
    "dungeon": ("id", "name", "achievements", "optimalPlayerLevel"),
    "achievement": ("id", "name", "description", "categoryId", "objectives"),
    "quest": ("id", "name", "startCriterion", "levelMin", "levelMax"),
    "item": ("id", "name", "typeId", "img", "questsThatReward", "achievementsThatReward"),
}


def alleger(genre: str, donnees):
    """Réduit une réponse DofusDB aux champs utiles (récursif pour les listes)."""
    if isinstance(donnees, list):
        return [alleger(genre, d) for d in donnees]
    if not isinstance(donnees, dict) or genre not in _GARDER:
        return donnees
    sortie = {k: donnees[k] for k in _GARDER[genre] if k in donnees}
    if "objectives" in sortie:
        sortie["objectives"] = [{k: o.get(k) for k in ("id", "order", "criterion")} for o in sortie["objectives"] or []]
    return sortie


class ClientEnCache:
    """Lit d'abord `<cache>/<fichier>.json`, sinon DofusDB, puis enregistre la réponse."""

    def __init__(self, client: ClientDofusDB | None, cache: Path) -> None:
        self._client = client
        self._cache = cache

    async def _lire(self, fichier: str, appel, *args):
        f = self._cache / f"{fichier}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        if self._client is None:
            raise LookupError(f"{f.name} absent du cache et aucun accès réseau")
        donnees = alleger(fichier.split("-")[0], await appel(*args))
        self._cache.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(donnees, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return donnees

    def _c(self) -> ClientDofusDB:
        return self._client  # type: ignore[return-value]  # appelé seulement si le cache manque

    async def donjon(self, id_: int) -> dict:
        return await self._lire(f"dungeon-{id_}", lambda i: self._c().donjon(i), id_)

    async def chercher_donjon(self, nom: str) -> list[dict]:
        cle = re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-")
        return await self._lire(f"dungeon-recherche-{cle}", lambda n: self._c().chercher_donjon(n), nom)

    async def succes(self, id_: int) -> dict:
        return await self._lire(f"achievement-{id_}", lambda i: self._c().succes(i), id_)

    async def quete(self, id_: int) -> dict:
        return await self._lire(f"quest-{id_}", lambda i: self._c().quete(i), id_)

    async def index_quetes(self) -> list[dict]:
        """Toutes les quêtes du jeu (`id`, `name`), en un seul fichier de cache."""
        return await self._lire("quest-index", lambda: self._c().index_quetes())

    async def quetes_completes(self, ids: Collection[int]) -> dict[int, dict]:
        """Les quêtes demandées, allégées (`alleger_quete_fiche`), un fichier de cache chacune ; les absentes
        du jeu sont omises. Les manquantes du cache sont demandées par paquets de 50."""
        manque = sorted(i for i in set(ids) if not (self._cache / f"questfiche-{i}.json").exists())
        if manque:
            if self._client is None:
                raise LookupError(f"questfiche-{manque[0]}.json absent du cache et aucun accès réseau")
            self._cache.mkdir(parents=True, exist_ok=True)
            for brut in await self._client.lot("/quests/", manque):
                self._ecrire(f"questfiche-{brut['id']}", alleger_quete_fiche(brut))
        trouvees = {}
        for i in sorted(set(ids)):
            f = self._cache / f"questfiche-{i}.json"
            if f.exists():
                trouvees[i] = json.loads(f.read_text(encoding="utf-8"))
        return trouvees

    async def noms(self, genre: str, ids: Collection[int]) -> dict[int, str | None]:
        """Noms français de PNJ, monstres ou objets (`genre` : npcs, monsters, items), un fichier par genre.
        Un id que DofusDB ne connaît pas vaut None (et n'est plus redemandé)."""
        return await self._table(f"noms-{genre}", f"/{genre}/", ids, ("id", "name"), lambda d: _fr(d.get("name")))

    async def cartes(self, ids: Collection[int]) -> dict[int, list[int] | None]:
        """Coordonnées [x, y] des cartes, un fichier de cache."""
        return await self._table("cartes", "/maps/", ids, ("id", "posX", "posY"),
                                 lambda d: [d["posX"], d["posY"]] if "posX" in d and "posY" in d else None)

    async def _table(self, fichier: str, chemin: str, ids: Collection[int], select: tuple[str, ...], reduire) -> dict:
        f = self._cache / f"{fichier}.json"
        table = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        manque = sorted(i for i in set(ids) if str(i) not in table)
        if manque:
            if self._client is None:
                raise LookupError(f"{f.name} : ids {manque[:3]}… absents du cache et aucun accès réseau")
            trouves = {d["id"]: reduire(d) for d in await self._client.lot(chemin, manque, select)}
            table.update({str(i): trouves.get(i) for i in manque})
            self._cache.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(table, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        return {i: table.get(str(i)) for i in set(ids)}

    def _ecrire(self, fichier: str, donnees) -> None:
        (self._cache / f"{fichier}.json").write_text(
            json.dumps(donnees, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    async def dofus(self) -> list[dict]:
        return await self._lire(f"item-type-{TYPE_DOFUS}", lambda t: self._c().objets_par_type(t), TYPE_DOFUS)


def alleger_quete_fiche(brut: dict) -> dict:
    """Une quête complète réduite à ce que lit la fiche : textes français, objectifs, positions, récompenses."""
    etapes = []
    for e in brut.get("steps") or []:
        objectifs = []
        for o in e.get("objectives") or []:
            carte = o.get("map") or {}
            p = o.get("parameters") or {}
            objectifs.append({
                "genre": o.get("className", ""), "texte": _fr(o.get("text")),
                "parametres": [p.get("parameter0", 0), p.get("parameter1", 0), p.get("parameter2", 0)],
                "position": [carte["posX"], carte["posY"]] if "posX" in carte and "posY" in carte else None,
            })
        recompenses = [{k: r.get(k) or [] for k in ("itemsReward", "emotesReward", "titlesReward")}
                       for r in e.get("rewards") or []]
        etapes.append({"id": e.get("id"), "nom": _fr(e.get("name")), "description": _fr(e.get("description")),
                       "objectifs": objectifs, "recompenses": recompenses})
    return {"id": brut["id"], "nom": _fr(brut.get("name")), "prerequis": (brut.get("need") or {}).get("quests", []),
            "objets": list(zip((brut.get("need") or {}).get("items", []),
                               (brut.get("need") or {}).get("quantities", []), strict=False)),
            "depart": brut.get("startPosition") or [], "etapes": etapes}


def _fr(valeur) -> str:
    return (valeur or {}).get("fr", "") if isinstance(valeur, dict) else str(valeur or "")


async def succes_du_donjon(client: ClientEnCache, dofusdb_id: int) -> list[tuple[str, str, str, bool]]:
    """(id, nom, condition, est_classique) dans l'ordre : la classique, « (Duo) », puis les autres par id."""
    donjon = await client.donjon(dofusdb_id)
    succes = [await client.succes(i) for i in donjon.get("achievements", [])]
    succes = [s for s in succes if s.get("categoryId") != CATEGORIE_COMPAGNONS]

    def defi(s: dict) -> bool:
        return "[challenge," in _fr(s.get("description"))

    succes.sort(key=lambda s: (defi(s), not _fr(s.get("name")).endswith("(Duo)"), s["id"]))
    sortie = []
    for i, s in enumerate(succes):
        description = _fr(s.get("description"))
        condition = description.split(" en validant")[0].strip() + "." if defi(s) else description
        sortie.append((f"dofusdb:{s['id']}", _fr(s.get("name")), condition, i == 0 and not defi(s)))
    return sortie


async def id_du_donjon(client: ClientEnCache, nom: str) -> int | None:
    trouves = await client.chercher_donjon(nom)
    return trouves[0]["id"] if len(trouves) == 1 else None


async def quetes_du_succes(client: ClientEnCache, succes_id: int, vus: set[int]) -> set[int]:
    """Les quêtes exigées par un succès : `Qf=` dans ses objectifs, et ceux des succès `OA=` (récursif)."""
    if succes_id in vus:
        return set()
    vus.add(succes_id)
    s = await client.succes(succes_id)
    quetes: set[int] = set()
    for o in s.get("objectives") or []:
        critere = o.get("criterion") or ""
        quetes |= {int(x) for x in _QF.findall(critere)}
        for a in _OA.findall(critere):
            quetes |= await quetes_du_succes(client, int(a), vus)
    return quetes


async def fermeture_dofusdb(client: ClientEnCache, racines: set[int]) -> dict[int, str]:
    """Quêtes racines et tous leurs prérequis obligatoires (« ET » de `startCriterion`) : id → nom."""
    noms: dict[int, str] = {}
    a_voir = list(racines)
    while a_voir:
        q = a_voir.pop()
        if q in noms:
            continue
        donnees = await client.quete(q)
        noms[q] = _fr(donnees.get("name"))
        a_voir.extend(quetes_obligatoires(donnees.get("startCriterion") or ""))
    return noms


async def guides_repli(client: ClientEnCache, dofus: Collection[str]) -> dict[str, dict[int, str]]:
    """Pour chaque Dofus demandé que DofusDB connaît : ses quêtes (id DofusDB → nom). Vide si aucune donnée."""
    guides: dict[str, dict[int, str]] = {}
    for objet in await client.dofus():
        nom = _fr(objet.get("name"))
        if nom not in dofus:
            continue
        racines = set(objet.get("questsThatReward") or [])
        vus: set[int] = set()
        for a in objet.get("achievementsThatReward") or []:
            racines |= await quetes_du_succes(client, int(a), vus)
        guides[nom] = await fermeture_dofusdb(client, racines) if racines else {}
    return guides
