"""L'aspiration (ARCHITECTURE §6.4) : les tables utiles de Duffus → donnees/duffus/AAAA-MM-JJ/<table>.json.

1. chaque table est lue page par page, avec les règles de politesse du client ;
2. chaque ligne est validée contre son modèle (`duffus/schema.py`) : une colonne exigée absente arrête tout,
   AVANT la moindre écriture ;
3. les extraits sont triés par clé, une ligne par enregistrement, avec les seules colonnes retenues : deux
   aspirations identiques donnent des fichiers identiques octet par octet, et un `git diff` montre ce que
   l'auteur a changé ;
4. un rapport de différences compare à l'aspiration précédente ;
5. `a_blanc` affiche le rapport sans rien écrire.

Les fiches complètes (`quest_pages`) ne sont lues que pour les tranches des étages demandés ; pour toutes les
autres quêtes, on ne lit que les prérequis, qui suffisent à suivre les chaînes vers les Dofus.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ValidationError

from epreuve.duffus import schema as s
from epreuve.duffus.client import ClientDuffus, ErreurDuffus


@dataclass(frozen=True)
class Table:
    nom: str  # nom du fichier écrit
    source: str  # table Duffus
    modele: type[BaseModel]
    cle: str = "id"


TABLES: dict[str, Table] = {t.nom: t for t in (
    Table("guide_ranges", "guide_ranges", s.GuideRange),
    Table("quest_list", "quest_list", s.QuestListe),
    Table("quest_prereqs", "quest_pages", s.QuestePrerequis, "slug"),
    Table("quest_pages", "quest_pages", s.QuestePage, "slug"),
    Table("dungeon_pages", "dungeon_pages", s.DonjonPage),
    Table("achievements", "achievements", s.Succes),
    Table("dofus_list", "dofus_list", s.DofusListe),
    Table("guide_pages", "guide_pages", s.GuidePage, "slug"),
    Table("quest_resources", "quest_resources", s.QuestRessource),
)}  # fmt: skip


def _colonnes(modele: type[BaseModel]) -> str:
    return ",".join(f'"{c}"' if not c.islower() else c for c in modele.model_fields)


def valider(table: Table, lignes: list[dict]) -> list[dict]:
    """Valide et réduit aux colonnes retenues, trié par clé. ErreurDuffus si une colonne exigée manque."""
    sortie = []
    for brute in lignes:
        try:
            ligne = table.modele.model_validate(brute).model_dump(mode="json")
        except ValidationError as e:
            err = e.errors()[0]
            col = ".".join(str(x) for x in err["loc"])
            quoi = "manquant" if err["type"] == "missing" else f"invalide ({err['msg']})"
            raise ErreurDuffus(f"`{table.source}.{col}` {quoi} : le schéma de Duffus a changé, refaire le relevé"
                               ) from None
        if "meta" in ligne:
            garder = s.META_DONJON if table.nom == "dungeon_pages" else s.META_QUETE
            ligne["meta"] = {k: v for k, v in ligne["meta"].items() if k in garder}
        sortie.append(ligne)
    return sorted(sortie, key=lambda r: r[table.cle])


def serialiser(lignes: list[dict]) -> str:
    """Stable : clés triées, une ligne par enregistrement, UTF-8 lisible."""
    if not lignes:
        return "[]\n"
    return "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in lignes) + "\n]\n"


def tranches_des_etages(ranges: list[dict], etages: tuple[int, ...]) -> list[dict]:
    """Étage N = la (N+1)-ième tranche active par `order_index` (DECISIONS-V4 §12, Q1)."""
    actives = sorted((r for r in ranges if r["is_active"]), key=lambda r: r["order_index"])
    return [actives[n] for n in etages if 0 <= n < len(actives)]


def slugs_des_tranches(tranches: list[dict], quetes: dict[int, dict]) -> list[str]:
    slugs = set()
    for r in tranches:
        for bloc in r["categories"]:
            for item in bloc.get("items", []):
                q = quetes.get(item.get("id")) if item.get("type") == "quest" else None
                if q and (q.get("url") or "").startswith("/quete/"):
                    slugs.add(q["url"].removeprefix("/quete/"))
    return sorted(slugs)


@dataclass
class Rapport:
    dossier: Path
    a_blanc: bool
    comptes: dict[str, int] = field(default_factory=dict)
    differences: dict[str, tuple[int, int, int]] = field(default_factory=dict)  # ajoutées, retirées, modifiées
    precedente: str | None = None
    ecrits: list[str] = field(default_factory=list)

    def texte(self) -> str:
        lignes = [f"Aspiration {'à blanc ' if self.a_blanc else ''}→ {self.dossier.name}"
                  + (f" (comparée à {self.precedente})" if self.precedente else " (première aspiration)")]
        for nom, n in self.comptes.items():
            d = self.differences.get(nom)
            ecart = f" : +{d[0]} −{d[1]} ~{d[2]}" if d and any(d) else (" : inchangée" if d else "")
            lignes.append(f"  {nom} : {n} lignes{ecart}")
        if self.a_blanc:
            lignes.append("  rien n'a été écrit (--a-blanc)")
        return "\n".join(lignes)


def _precedente(racine: Path, jour: date) -> Path | None:
    dossiers = sorted(d for d in racine.glob("????-??-??") if d.is_dir() and d.name < jour.isoformat())
    return dossiers[-1] if dossiers else None


def _differences(table: Table, avant: list[dict], apres: list[dict]) -> tuple[int, int, int]:
    a = {r[table.cle]: r for r in avant}
    b = {r[table.cle]: r for r in apres}
    return len(b.keys() - a.keys()), len(a.keys() - b.keys()), sum(1 for k in a.keys() & b.keys() if a[k] != b[k])


async def lire(client: ClientDuffus, noms: tuple[str, ...], etages: tuple[int, ...] | None) -> dict[str, list[dict]]:
    """Lit et valide les tables demandées ; rien n'est écrit ici."""
    extraits: dict[str, list[dict]] = {}
    filtre_fiches: dict[str, str] | None = None
    if "quest_pages" in noms and etages is not None:
        ranges = extraits.get("guide_ranges") or valider(TABLES["guide_ranges"], await client.lire_table(
            "guide_ranges", _colonnes(s.GuideRange)))
        quetes = {q["id"]: q for q in (extraits.get("quest_list") or valider(TABLES["quest_list"],
                                       await client.lire_table("quest_list", _colonnes(s.QuestListe))))}
        slugs = slugs_des_tranches(tranches_des_etages(ranges, etages), quetes)
        filtre_fiches = {"slug": f"in.({','.join(slugs)})"}
        if "guide_ranges" in noms:
            extraits["guide_ranges"] = ranges
        if "quest_list" in noms:
            extraits["quest_list"] = list(quetes.values())
    for nom in noms:
        if nom in extraits:
            continue
        t = TABLES[nom]
        brutes = await client.lire_table(t.source, _colonnes(t.modele), t.cle,
                                         filtre_fiches if nom == "quest_pages" else None)
        lignes = valider(t, brutes)
        if nom == "achievements":
            lignes = [r for r in lignes if s.MARQUE_SUCCES_DONJON in (r["description"] or "")]
        extraits[nom] = lignes
    return {n: extraits[n] for n in noms}


async def aspirer(client: ClientDuffus, racine: Path, jour: date, tables: tuple[str, ...] | None = None,
                  etages: tuple[int, ...] | None = None, a_blanc: bool = False) -> Rapport:
    noms = tables or tuple(TABLES)
    inconnues = [n for n in noms if n not in TABLES]
    if inconnues:
        raise ErreurDuffus(f"table inconnue : {', '.join(inconnues)} (connues : {', '.join(TABLES)})")
    extraits = await lire(client, noms, etages)
    dossier = racine / jour.isoformat()
    rapport = Rapport(dossier, a_blanc)
    precedente = _precedente(racine, jour)
    rapport.precedente = precedente.name if precedente else None
    for nom, lignes in extraits.items():
        rapport.comptes[nom] = len(lignes)
        if precedente and (precedente / f"{nom}.json").exists():
            avant = json.loads((precedente / f"{nom}.json").read_text(encoding="utf-8"))
            rapport.differences[nom] = _differences(TABLES[nom], avant, lignes)
    if not a_blanc:
        dossier.mkdir(parents=True, exist_ok=True)
        for nom, lignes in extraits.items():
            (dossier / f"{nom}.json").write_text(serialiser(lignes), encoding="utf-8")
            rapport.ecrits.append(nom)
    return rapport
