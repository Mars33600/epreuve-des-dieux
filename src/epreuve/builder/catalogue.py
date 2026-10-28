"""Les objets et panoplies du builder, chargés une fois en mémoire depuis donnees/duffus/builder/.

Environ 3 800 équipements : la recherche se fait en Python, sans base, avec les mêmes règles que la fenêtre
de choix de Duffus (nom sans accents, niveaux, types, caractéristiques ; tri par niveau décroissant).
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from epreuve.builder.arme import Arme
from epreuve.builder.effets import EFFET_CARAC, EMPLACEMENTS, EXCLUS, TYPES_DOFUS, valeur_effet

DOSSIER = Path(__file__).resolve().parents[3] / "donnees" / "duffus" / "builder"
URL_ICONE = "https://api.dofusdb.fr/img/items/{}.png"  # autorisée par la CSP (img-src)
Effet = tuple[int, int, int]  # (effectId, from, to)


def normaliser(texte: str) -> str:
    """Comme `Hs` chez Duffus : minuscules, sans accents, œ → oe, æ → ae."""
    t = unicodedata.normalize("NFD", (texte or "").strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.replace("œ", "oe").replace("æ", "ae")


def caracs_des_effets(effets: tuple[Effet, ...]) -> dict[str, int]:
    """Somme des effets par caractéristique (fonction `Nn` de Duffus, sans forgemagie)."""
    total: dict[str, int] = {}
    for eid, de, a in effets:
        carac = EFFET_CARAC.get(eid)
        v = valeur_effet(de, a)
        if carac and v != 0:
            total[carac] = total.get(carac, 0) + v
    return total


@dataclass(frozen=True)
class Objet:
    id: int
    nom: str
    niveau: int
    type: int
    icone: int | None
    panoplie: int | None
    conditions: str | None
    effets: tuple[Effet, ...]
    arme: Arme | None = None

    def caracs(self) -> dict[str, int]:
        return caracs_des_effets(self.effets)

    def resume(self) -> dict:
        """Ce que la page affiche d'un objet."""
        return {"id": self.id, "nom": self.nom, "niveau": self.niveau, "type": self.type,
                "icone": URL_ICONE.format(self.icone) if self.icone else None, "panoplie": self.panoplie,
                "conditions": self.conditions,
                "caracs": [[k, v] for k, v in self.caracs().items()]}


@dataclass(frozen=True)
class Panoplie:
    id: int
    nom: str
    objets: tuple[int, ...]
    bonus: dict[int, tuple[Effet, ...]]  # nombre d'objets portés → effets


class Catalogue:
    def __init__(self, objets: list[Objet], panoplies: list[Panoplie]) -> None:
        self.objets = {o.id: o for o in objets}
        self.panoplies = {p.id: p for p in panoplies}
        self._noms = {o.id: normaliser(o.nom) for o in objets}

    @classmethod
    def depuis_json(cls, objets: list[dict], panoplies: list[dict]) -> Catalogue:
        return cls(
            [Objet(o["id"], o["nom"], o["niveau"], o["type"], o.get("icone"), o.get("panoplie"),
                   o.get("conditions"), tuple(tuple(e) for e in o.get("effets", [])), _arme(o.get("arme")))
             for o in objets],
            [Panoplie(p["id"], p["nom"], tuple(p.get("objets", [])),
                      {int(k): tuple(tuple(e) for e in v) for k, v in p.get("bonus", {}).items()})
             for p in panoplies],
        )  # fmt: skip

    @classmethod
    def depuis_dossier(cls, dossier: Path = DOSSIER) -> Catalogue:
        lire = lambda nom: json.loads((dossier / nom).read_text(encoding="utf-8"))  # noqa: E731
        return cls.depuis_json(lire("objets.json"), lire("panoplies.json"))

    def objet(self, objet_id: int | None) -> Objet | None:
        return self.objets.get(objet_id) if objet_id is not None else None

    def rechercher(self, emplacement: str, *, texte: str = "", niveau_min: int | None = None,
                   niveau_max: int | None = None, types: list[int] | None = None,
                   caracs: list[str] | None = None, limite: int = 30, decalage: int = 0) -> tuple[int, list[Objet]]:
        """Les objets possibles pour un emplacement : (nombre total, la page demandée).

        Mêmes règles que Duffus : texte d'au moins 2 caractères cherché dans le nom ; `types` restreint la famille
        de l'emplacement ; chaque caractéristique demandée doit être apportée en positif par l'objet.
        Tri : niveau décroissant puis identifiant décroissant (Dofus, Trophées, Prysmaradites d'abord par type).
        """
        permis = set(EMPLACEMENTS[emplacement])
        if types:
            permis &= set(types)
        cherche = normaliser(texte) if len(texte.strip()) >= 2 else ""
        voulues = set(caracs or [])
        trouves = []
        for o in self.objets.values():
            if o.type not in permis or o.id in EXCLUS:
                continue
            if niveau_min is not None and o.niveau < niveau_min:
                continue
            if niveau_max is not None and o.niveau > niveau_max:
                continue
            if cherche and cherche not in self._noms[o.id]:
                continue
            if voulues:
                positives = {EFFET_CARAC[e] for e, de, a in o.effets if valeur_effet(de, a) > 0}
                if not voulues <= positives:
                    continue
            trouves.append(o)
        rang = {t: i for i, t in enumerate(TYPES_DOFUS.values())}
        if emplacement.startswith("dofus"):
            trouves.sort(key=lambda o: (rang.get(o.type, 99), -o.niveau, -o.id))
        else:
            trouves.sort(key=lambda o: (-o.niveau, -o.id))
        return len(trouves), trouves[decalage:decalage + limite]


def _arme(d: dict | None) -> Arme | None:
    if not d:
        return None
    return Arme(d["pa"], d["po_min"], d["po"], d["cc"], d["bonus_cc"], d["lancers"],
                tuple(tuple(e) for e in d["effets"]))


@cache
def catalogue_par_defaut() -> Catalogue:
    return Catalogue.depuis_dossier()
