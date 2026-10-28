"""Le catalogue du module E1, construit sans réseau depuis une aspiration (donnees/duffus/AAAA-MM-JJ/).

Les règles reprennent celles du site Duffus (code public de ses pages, relevé du 28/10/2026) :
- l'identifiant du monstre d'un archimonstre est le nombre en tête du nom de son image
  (« /images/archis/2404_Blorie….png » → 2404) ; ses niveaux sont ceux de ses grades (« Niv. 52 à 60 ») ;
- la zone d'un archimonstre peut en citer plusieurs, séparées par « · » ; chacune est rangée dans son aire
  par le nom de la sous-zone (sans accents ni casse). Si ce nom existe dans plusieurs aires, on garde la
  sous-zone qui contient le monstre, sinon la première ;
- un boss du Dofus Ocre est le premier monstre de ce nom qui n'est ni d'une expédition ni d'une mémoire ;
  son niveau est le plus petit de ses grades ;
- le niveau d'un avis de recherche est celui du premier grade de son monstre (sinon le nombre de `lvl`).

Les icônes viennent de DofusDB (`api.dofusdb.fr/img/monsters/<gfxid>.png`, permis par la CSP), jamais du
stockage de Duffus. Le résumé d'un avis est nettoyé par liste blanche : ni image, ni lien, ni attribut.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import nh3

FICHIERS = ("archimonstres", "boss_ocre", "wanted2", "monstres_e1", "monster_races", "monstres_avis", "subareas",
            "areas")
BALISES_RESUME = {"b", "strong", "i", "em", "u", "ul", "ol", "li", "br", "div", "p", "span"}
_IMAGE_ARCHI = re.compile(r"^/images/archis/(\d+)_")
RACES_ECARTEES = ("expedition", "memoire de")
ICONE_DOFUSDB = "https://api.dofusdb.fr/img/monsters/{}.png"


def normaliser(texte: str | None) -> str:
    """Sans accents, en minuscules, sans espaces autour (la recherche de Duffus)."""
    t = unicodedata.normalize("NFD", str(texte or ""))
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


def zones_de(zone: str | None) -> list[str]:
    return [z.strip() for z in str(zone or "").split("·") if z.strip()]


def id_monstre_archi(image: str | None) -> int | None:
    m = _IMAGE_ARCHI.match(image or "")
    return int(m.group(1)) if m else None


def _entier(texte: str | int | None) -> int | None:
    if isinstance(texte, int):
        return texte
    m = re.search(r"\d+", str(texte or ""))
    return int(m.group()) if m else None


def icone(gfx_id: int | None) -> str | None:
    return ICONE_DOFUSDB.format(gfx_id) if gfx_id is not None else None


def nettoyer_resume(html: str | None) -> str:
    propre = nh3.clean(html or "", tags=BALISES_RESUME, clean_content_tags={"script", "style", "svg", "button"},
                       attributes={}, link_rel=None, url_schemes=set())
    return re.sub(r"(<div>\s*<br>\s*</div>\s*)+$", "", propre.strip())


# --- Modèles ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Zone:
    nom: str
    aire: str | None


@dataclass(frozen=True)
class Archimonstre:
    id: int
    nom: str
    etape: int | None
    zones: tuple[Zone, ...]
    monstre_id: int | None
    gfx_id: int | None
    niveau_min: int | None
    niveau_max: int | None

    @property
    def niveaux(self) -> str | None:
        if self.niveau_min is None or self.niveau_max is None:
            return None
        if self.niveau_min == self.niveau_max:
            return f"Niv. {self.niveau_min}"
        return f"Niv. {self.niveau_min} à {self.niveau_max}"

    @property
    def zone_texte(self) -> str:
        return " · ".join(z.nom for z in self.zones)

    @property
    def icone(self) -> str | None:
        return icone(self.gfx_id)


@dataclass(frozen=True)
class Boss:
    id: int
    nom: str
    etape: int | None
    monstre_id: int | None
    gfx_id: int | None
    niveau: int | None

    @property
    def niveaux(self) -> str | None:
        return f"Niv. {self.niveau}" if self.niveau is not None else None

    @property
    def niveau_max(self) -> int | None:  # pour les pierres d'âme : même calcul que les archis
        return self.niveau

    @property
    def zones(self) -> tuple[Zone, ...]:
        return ()

    @property
    def zone_texte(self) -> str:
        return ""

    @property
    def icone(self) -> str | None:
        return icone(self.gfx_id)


@dataclass(frozen=True)
class Grade:
    niveau: int | None
    pv: int | None
    pa: int | None
    pm: int | None
    fuite: int | None
    tacle: int | None
    retrait_pa: int | None
    retrait_pm: int | None
    esquive_pa: int | None
    esquive_pm: int | None
    resistances: tuple[int | None, int | None, int | None, int | None, int | None]  # neutre, terre, feu, eau, air


@dataclass(frozen=True)
class AvisRecherche:
    id: int
    slug: str
    nom: str
    niveau_texte: str | None
    niveau: int | None
    zone: str | None
    milice: str | None
    recompense: int | None
    recompense_type: str  # « aviton » ou « aliton »
    chasse: bool
    monstre_id: int | None
    gfx_id: int | None
    resume_html: str
    grades: tuple[Grade, ...]

    @property
    def icone(self) -> str | None:
        return icone(self.gfx_id)

    @property
    def niveau_tri(self) -> int:
        return self.niveau if self.niveau is not None else 0


@dataclass(frozen=True)
class Catalogue:
    archis: tuple[Archimonstre, ...]
    boss: tuple[Boss, ...]
    avis: tuple[AvisRecherche, ...]
    alertes: tuple[str, ...] = ()


# --- Construction -----------------------------------------------------------------------------------------


def _niveaux(m: dict) -> list[int]:
    return [int(m[f"n{i}"]) for i in range(8) if isinstance(m.get(f"n{i}"), int)]


def _aire(zone: str, monstre_id: int | None, candidats: dict[str, list[dict]], aires: dict[int, str]) -> str | None:
    liste = candidats.get(normaliser(zone)) or []
    if not liste:
        return None
    if len({c["areaid"] for c in liste}) == 1:
        return aires.get(liste[0]["areaid"])
    choisie = next((c for c in liste if monstre_id in (c.get("monstres") or [])), liste[0])
    return aires.get(choisie["areaid"])


def _grade(g: dict) -> Grade:
    def n(cle: str) -> int | None:
        v = g.get(cle)
        return v if isinstance(v, int) else None

    return Grade(n("level"), n("lifePoints"), n("actionPoints"), n("movementPoints"), n("tackleEvade"),
                 n("tackleBonus"), n("apAttack"), n("mpAttack"), n("paLostDodge"), n("mpLostDodge"),
                 (n("reductionNeutral"), n("reductionEarth"), n("reductionFire"), n("reductionWater"),
                  n("reductionAir")))


def construire(brut: dict[str, list[dict]]) -> Catalogue:
    alertes: list[str] = []
    monstres = {m["id"]: m for m in brut.get("monstres_e1", [])}
    races = {r["id"]: r["name"] for r in brut.get("monster_races", [])}
    aires = {a["id"]: a["name"] for a in brut.get("areas", [])}
    candidats: dict[str, list[dict]] = {}
    for sz in sorted(brut.get("subareas", []), key=lambda z: z["id"]):
        candidats.setdefault(normaliser(sz["name"]), []).append(sz)

    archis = []
    for a in brut.get("archimonstres", []):
        mid = id_monstre_archi(a.get("image"))
        m = monstres.get(mid) if mid is not None else None
        niv = _niveaux(m) if m else []
        zones = tuple(Zone(z, _aire(z, mid, candidats, aires)) for z in zones_de(a.get("zone")))
        if not niv:
            alertes.append(f"archimonstre sans niveaux : {a['nom']} (monstre {mid})")
        sans_aire = [z.nom for z in zones if z.aire is None]
        if sans_aire:
            alertes.append(f"zone sans aire pour {a['nom']} : {', '.join(sans_aire)}")
        archis.append(Archimonstre(a["id"], a["nom"].strip(), _entier(a.get("etape")), zones, mid,
                                   m.get("gfxid") if m else None, min(niv) if niv else None,
                                   max(niv) if niv else None))

    par_nom: dict[str, dict] = {}
    for m in sorted(monstres.values(), key=lambda m: m["id"]):
        if any(r in normaliser(races.get(m.get("race"), "")) for r in RACES_ECARTEES):
            continue
        par_nom.setdefault(m["name"], m)
    boss = []
    for b in brut.get("boss_ocre", []):
        m = par_nom.get(b["nom"])
        niv = _niveaux(m) if m else []
        if m is None:
            alertes.append(f"boss sans monstre : {b['nom']}")
        boss.append(Boss(b["id"], b["nom"].strip(), _entier(b.get("etape")), m["id"] if m else None,
                         m.get("gfxid") if m else None, min(niv) if niv else None))

    monstres_avis = {m["id"]: m for m in brut.get("monstres_avis", [])}
    avis = []
    for w in brut.get("wanted2", []):
        mid = _entier(w.get("dofus_monster_id"))
        m = monstres_avis.get(mid) if mid is not None else None
        grades = tuple(_grade(g) for g in (m or {}).get("grades_json", []))
        if m is None:
            alertes.append(f"avis sans monstre : {w['nom']}")
        niveau = grades[0].niveau if grades and grades[0].niveau is not None else _entier(w.get("lvl"))
        type_ = "aliton" if normaliser(w.get("recompense_type")) == "aliton" else "aviton"
        avis.append(AvisRecherche(w["id"], w["slug"], w["nom"].strip(), w.get("lvl"), niveau, w.get("zone"),
                                  (w.get("milice") or "").strip() or None, _entier(w.get("recompense")), type_,
                                  bool((w.get("chasse") or "").strip()), mid, m.get("gfxid") if m else None,
                                  nettoyer_resume(w.get("resume_html")), grades))
    return Catalogue(tuple(sorted(archis, key=lambda a: a.id)), tuple(sorted(boss, key=lambda b: b.id)),
                     tuple(sorted(avis, key=lambda w: w.id)), tuple(alertes))


def derniere_aspiration(racine: Path) -> Path | None:
    dossiers = sorted(d for d in racine.glob("????-??-??") if (d / "archimonstres.json").exists())
    return dossiers[-1] if dossiers else None


def lire_dossier(dossier: Path) -> dict[str, list[dict]]:
    """Les fichiers d'une aspiration E1 ; un fichier absent compte pour une liste vide."""
    brut = {}
    for nom in FICHIERS:
        f = dossier / f"{nom}.json"
        brut[nom] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    return brut
