"""Construire un étage à partir d'une aspiration Duffus, sans réseau (ARCHITECTURE §6.5).

Développer (ici) puis écrire (`ecrire.py`) : la construction produit un `EtagePrepare`, l'objet complet de
l'étage, qu'on peut afficher (`--a-blanc`) ou tester sans base. Le rattachement à la tranche, la case
« classique » et la lecture des fiches suivent l'addendum B0 de LOTS.md.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from epreuve.contenu.fiche_duffus import lire_fiche, nettoyer_fiche  # noqa: F401 (interface figée : nettoyer_fiche vit ici)
from epreuve.db.depot import ContenuFiche
from epreuve.domaine.modeles import Nature, OrigineNature
from epreuve.domaine.nature import classer

RACINE = Path(__file__).resolve().parents[3]
SEUIL_SANS_FICHE = 0.05  # au-delà, la construction s'arrête sans --forcer (décision de Marceau)


class ConfigInvalide(ValueError):
    pass


class ConstructionArretee(RuntimeError):
    """La construction s'arrête et le rapport demande une décision (ex. trop de quêtes sans fiche)."""


# --- Ce que la construction produit ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CasePreparee:
    duffus_id: str
    ordre: int
    nom: str
    condition: str
    est_classique: bool


@dataclass(frozen=True)
class DonjonPrepare:
    duffus_id: str
    nom: str
    niveau: int | None
    ordre: int
    bloc: str | None
    dofusdb_id: int | None
    succes_source: Literal["duffus", "dofusdb"]
    cases: tuple[CasePreparee, ...]


@dataclass(frozen=True)
class QuetePreparee:
    duffus_id: str
    nom: str
    niveau: int | None
    bloc: str
    ordre: int
    nature: Nature
    nature_origine: OrigineNature
    dofus: tuple[str, ...]
    jusqu_ou: str | None
    a_lier: str | None
    fiche: ContenuFiche | None
    source_fiche: Literal["duffus", "duffus+dofusdb", "dofusdb"] | None


@dataclass
class EtagePrepare:
    numero: int
    nom: str
    tranche: str
    niveau_min: int
    niveau_max: int
    level_cap: int
    ambiance_url: str | None
    ouvert_le: datetime | None
    date_plancher_suivant: datetime | None
    donjons: list[DonjonPrepare] = field(default_factory=list)
    quetes: list[QuetePreparee] = field(default_factory=list)
    disponibles: list[DonjonPrepare] = field(default_factory=list)  # tous les donjons aspirés (T-03)
    alertes: list[str] = field(default_factory=list)
    sans_fiche: list[str] = field(default_factory=list)
    rappels: list[str] = field(default_factory=list)

    def rapport(self) -> str:
        lignes = [f"Étage {self.numero} « {self.nom} » = tranche {self.tranche} (niveaux {self.niveau_min} à "
                  f"{self.niveau_max}, cap {self.level_cap})",
                  f"  {len(self.donjons)} donjons, {sum(len(d.cases) for d in self.donjons)} cases, "
                  f"{len(self.quetes)} quêtes ({sum(1 for q in self.quetes if q.nature == 'principale')} principales)",
                  f"  quêtes sans fiche Duffus : {len(self.sans_fiche)}"
                  + (f" ({', '.join(self.sans_fiche)})" if self.sans_fiche else "")]
        lignes += [f"  alerte : {a}" for a in self.alertes]
        return "\n".join(lignes)


# --- Configuration ----------------------------------------------------------------------------------------


class _ConfigEtage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tranche: str | None = None
    nom: str | None = None
    level_cap: int | None = None
    ambiance_url: str | None = None
    ouvert_le: datetime | None = None
    date_plancher_suivant: datetime | None = None


class _ConfigEtages(BaseModel):
    model_config = ConfigDict(extra="forbid")
    etages: dict[int, _ConfigEtage] = {}


def lire_config_etages(chemin: Path = RACINE / "config" / "etages.yaml") -> dict[int, _ConfigEtage]:
    try:
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
        cfg = _ConfigEtages.model_validate(brut or {}).etages
    except (yaml.YAMLError, ValidationError) as e:
        raise ConfigInvalide(f"{chemin.name} invalide : {e}") from None
    for n, c in cfg.items():
        for d in (c.ouvert_le, c.date_plancher_suivant):
            if d is not None and d.utcoffset() is None:
                raise ConfigInvalide(f"{chemin.name}, étage {n} : une date doit porter son fuseau")
        if c.ambiance_url and "duffus" in c.ambiance_url.lower():
            raise ConfigInvalide(f"{chemin.name}, étage {n} : aucune image prise sur duffus.fr (EX-70)")
    return cfg


def lire_dofus_retenus(chemin: Path = RACINE / "config" / "dofus.yaml") -> frozenset[str]:
    try:
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ConfigInvalide(f"{chemin.name} illisible : {e}") from None
    dofus = brut.get("dofus") if isinstance(brut, dict) else None
    if not isinstance(dofus, list) or not all(isinstance(d, str) for d in dofus):
        raise ConfigInvalide(f"{chemin.name} : une liste « dofus: » de noms est attendue")
    return frozenset(dofus)


# --- Lecture de l'aspiration ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Aspiration:
    dossier: Path
    ranges: list[dict]
    quetes: dict[int, dict]
    pages: dict[str, dict]
    donjons: dict[str, dict]
    succes: list[dict]
    dofus: list[dict]

    @staticmethod
    def lire(dossier: Path) -> Aspiration:
        def charger(nom: str) -> list[dict]:
            f = dossier / f"{nom}.json"
            if not f.exists():
                raise ConfigInvalide(f"aspiration incomplète : {f} absent")
            return json.loads(f.read_text(encoding="utf-8"))

        return Aspiration(dossier, charger("guide_ranges"), {q["id"]: q for q in charger("quest_list")},
                          {p["slug"]: p for p in charger("quest_pages")},
                          {d["slug"]: d for d in charger("dungeon_pages")}, charger("achievements"),
                          charger("dofus_list"))


def derniere_aspiration(racine: Path = RACINE / "donnees" / "duffus") -> Path:
    dossiers = sorted(d for d in racine.glob("????-??-??") if d.is_dir())
    if not dossiers:
        raise ConfigInvalide(f"aucune aspiration dans {racine} : lancer « python -m epreuve.duffus aspirer »")
    return dossiers[-1]


def slug_quete(entree: Mapping) -> str | None:
    url = entree.get("url") or ""
    return url.removeprefix("/quete/").strip("/") or None if url.startswith("/quete/") else None


def _niveau(texte: object) -> int | None:
    m = re.search(r"\d+", str(texte or ""))
    return int(m.group()) if m else None


def bornes(range_key: str) -> tuple[int, int]:
    """« 1-20 » → (1, 20) ; « 200-3 » (tranches après le niveau 200) → (200, 200)."""
    a, _, b = range_key.partition("-")
    bas, haut = int(a), int(b or a)
    return (bas, haut) if haut >= bas else (bas, bas)


# --- Les succès d'un donjon (case « classique », addendum B0) ----------------------------------------------


def succes_duffus(page: Mapping, succes: list[dict]) -> list[CasePreparee]:
    """La classique (nom = titre du donjon, sans défi), puis « (Duo) », puis les défis par `order`.

    Liste vide si Duffus ne donne pas la classique : le repli DofusDB prend alors le relais."""
    meta = page.get("meta") or {}
    titre, boss = meta.get("title"), meta.get("bossName") or ""
    classiques = [s for s in succes if s["name"] == titre and "[challenge," not in (s["description"] or "")]
    if len(classiques) != 1:
        return []
    c = classiques[0]
    autres = [s for s in succes if s["category_id"] == c["category_id"] and "[challenge," in (s["description"] or "")
              and s["name"].startswith(boss + " (") and "Compagnon" not in s["name"]]
    autres.sort(key=lambda s: (not s["name"].endswith("(Duo)"), s["order"] or 0, s["id"]))
    regle = ((page.get("successes") or {}).get("special") or {}).get("rule")

    def condition(s: dict) -> str:
        texte = re.sub(r"\s*\[challenge,\d+\]", "", s["description"] or "").strip()
        if s["name"].endswith("(Spécial)") and regle:
            texte = f"{texte} Règle : {regle}"
        return texte

    return [CasePreparee(str(s["id"]), i, s["name"], condition(s), i == 1) for i, s in enumerate([c, *autres], 1)]


def donjon_prepare(page: Mapping, aspi: Aspiration, ordre: int, bloc: str | None) -> tuple[DonjonPrepare, list[str]]:
    meta = page.get("meta") or {}
    cases = succes_duffus(page, aspi.succes)
    alertes = []
    nom = meta.get("title") or page["slug"]
    if not cases:
        alertes.append(f"donjon « {nom} » : succès introuvables chez Duffus, repli DofusDB à faire")
    elif len(cases) != 5:
        alertes.append(f"donjon « {nom} » : {len(cases)} succès au lieu de 5")
    d = DonjonPrepare(page["slug"], nom, _niveau(meta.get("level")), ordre, bloc, None, "duffus", tuple(cases))
    return d, alertes


# --- L'étage ---------------------------------------------------------------------------------------------


def construire(numero: int, aspi: Aspiration, config: Mapping[int, _ConfigEtage], dofus_retenus: frozenset[str],
               forcees: Mapping[str, Nature] | None = None, quetes_ouvertes: Mapping[str, str] | None = None,
               forcer: bool = False) -> EtagePrepare:
    """L'étage `numero`, prêt à écrire. `forcees` : natures choisies par un admin (duffus_id → nature) ;
    `quetes_ouvertes` : slug → notre adresse, pour les quêtes des étages déjà visibles (liens des fiches).

    ConstructionArretee au-delà de 5 % de quêtes sans fiche Duffus, sauf `forcer`."""
    actives = sorted((r for r in aspi.ranges if r["is_active"]), key=lambda r: r["order_index"])
    cfg = config.get(numero) or _ConfigEtage()
    if cfg.tranche is not None:
        tranche = next((r for r in actives if r["range_key"] == cfg.tranche), None)
        if tranche is None:
            raise ConfigInvalide(f"étage {numero} : tranche « {cfg.tranche} » absente de l'aspiration")
    elif 0 <= numero < len(actives):
        tranche = actives[numero]
    else:
        raise ConfigInvalide(f"étage {numero} : le guide n'a que {len(actives)} tranches "
                             f"(étages 0 à {len(actives) - 1})")
    bas, haut = bornes(tranche["range_key"])
    e = EtagePrepare(numero, cfg.nom or f"Étage {numero}", tranche["range_key"], bas, haut, cfg.level_cap or haut,
                     cfg.ambiance_url, cfg.ouvert_le, cfg.date_plancher_suivant)
    slug_vers_id = {s: str(q["id"]) for q in aspi.quetes.values() if (s := slug_quete(q))}
    ouvertes = quetes_ouvertes or {}

    vues_quetes: set[int] = set()
    brutes: list[tuple[dict, str]] = []
    for bloc in tranche["categories"]:
        titre = bloc.get("title") or "Quêtes"
        for item in bloc.get("items", []):
            if item.get("type") != "quest":
                continue
            entree = aspi.quetes.get(item["id"])
            if entree is None:
                e.alertes.append(f"entrée {item['id']} du bloc « {titre} » absente de quest_list")
                continue
            for dj in entree.get("dungeons") or []:
                slug = (dj.get("url") or "").removeprefix("/donjon/").strip("/")
                if slug and all(d.duffus_id != slug for d in e.donjons):
                    page = aspi.donjons.get(slug)
                    if page is None:
                        e.alertes.append(f"donjon « {dj.get('info') or slug} » sans page Duffus")
                        continue
                    d, alertes = donjon_prepare(page, aspi, len(e.donjons) + 1, titre)
                    e.donjons.append(d)
                    e.alertes += alertes
            if not entree.get("quest_ornot"):
                e.rappels.append(entree["title"])
                continue
            if entree["id"] not in vues_quetes:
                vues_quetes.add(entree["id"])
                brutes.append((entree, titre))
    if tranche.get("dungeon_count") is not None and tranche["dungeon_count"] != len(e.donjons):
        e.alertes.append(f"{len(e.donjons)} donjons trouvés, Duffus en annonce {tranche['dungeon_count']}")

    # Nature : guides par Dofus introuvables dans les tables relevées (addendum B0), aucune supposition.
    guides_duffus: dict[str, frozenset[int]] = {}
    forcees_ids = {int(k): v for k, v in (forcees or {}).items()}
    classement = classer([q["id"] for q, _ in brutes], guides_duffus, {}, dofus_retenus, forcees_ids)
    if not guides_duffus and brutes:
        e.alertes.append("nature non déterminée : les guides par Dofus ne sont pas dans les tables Duffus relevées "
                         "(addendum B0) ; toutes les quêtes sont secondaires sauf choix d'un admin")

    for ordre, (entree, bloc) in enumerate(brutes, 1):
        slug = slug_quete(entree)
        page = aspi.pages.get(slug) if slug else None
        fiche = lire_fiche(page, entree, slug_vers_id, ouvertes) if page else None
        if fiche is None:
            e.sans_fiche.append(entree["title"])
        c = classement[entree["id"]]
        e.quetes.append(QuetePreparee(str(entree["id"]), entree["title"].strip(), _niveau(entree.get("level")), bloc,
                                      ordre, c.nature, c.origine, c.dofus, None, None, fiche,
                                      "duffus" if fiche else None))
    if e.quetes and len(e.sans_fiche) / len(e.quetes) > SEUIL_SANS_FICHE:
        message = (f"{len(e.sans_fiche)} quêtes sur {len(e.quetes)} sans fiche Duffus (plus de 5 %) : "
                   "décision de Marceau nécessaire, relancer avec --forcer pour passer outre")
        if not forcer:
            raise ConstructionArretee(message)
        e.alertes.append(message)
    if e.sans_fiche:
        e.alertes.append(f"{len(e.sans_fiche)} quête(s) sans fiche Duffus : {', '.join(e.sans_fiche)}")

    for page in sorted(aspi.donjons.values(), key=lambda p: p["slug"]):
        d, _ = donjon_prepare(page, aspi, 0, None)
        if d.cases:
            e.disponibles.append(d)
    return e
