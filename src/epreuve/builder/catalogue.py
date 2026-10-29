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
from epreuve.builder.effets import (
    EFFET_CARAC,
    EMPLACEMENTS,
    EXCLUS,
    TYPES_ARMES,
    TYPES_DOFUS,
    TYPES_FAMILIERS,
    valeur_effet,
)

DOSSIER = Path(__file__).resolve().parents[3] / "donnees" / "duffus" / "builder"
URL_ICONE = "https://api.dofusdb.fr/img/items/{}.png"  # autorisée par la CSP (img-src)
Effet = tuple[int, int, int]  # (effectId, from, to)


def normaliser(texte: str) -> str:
    """Comme `Hs` chez Duffus : minuscules, sans accents, œ → oe, æ → ae."""
    t = unicodedata.normalize("NFD", (texte or "").strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.replace("œ", "oe").replace("æ", "ae")


def caracs_des_effets(effets: tuple[Effet, ...], fm: dict[int, int] | None = None) -> dict[str, int]:
    """Somme des effets par caractéristique (fonction `Nn` de Duffus).

    `fm` (forgemagie, `fm_overrides` chez Duffus) : effectId → valeur choisie. Elle remplace le jet de l'effet
    de l'objet ; un effet absent de l'objet est un exo, ajouté en plus.
    """
    fm = fm or {}
    total: dict[str, int] = {}
    vus: set[int] = set()
    for eid, de, a in effets:
        carac = EFFET_CARAC.get(eid)
        v = fm[eid] if eid in fm else valeur_effet(de, a)
        if carac and v != 0:
            vus.add(eid)
            total[carac] = total.get(carac, 0) + v
    for eid, v in fm.items():
        carac = EFFET_CARAC.get(eid)
        if eid not in vus and carac and v != 0:
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

    def caracs(self, fm: dict[int, int] | None = None) -> dict[str, int]:
        return caracs_des_effets(self.effets, fm)

    def resume(self) -> dict:
        """Ce que la page affiche d'un objet."""
        return {"id": self.id, "nom": self.nom, "niveau": self.niveau, "type": self.type,
                "icone": URL_ICONE.format(self.icone) if self.icone else None, "panoplie": self.panoplie,
                "conditions": self.conditions,
                "caracs": [[k, v] for k, v in self.caracs().items()],
                "effets": [[e, de, a, EFFET_CARAC[e], valeur_effet(de, a)] for e, de, a in self.effets]}


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

    def niveau_panoplie(self, p: Panoplie) -> int:
        """`levelMax` de Duffus : le niveau de l'objet le plus haut de la panoplie."""
        return max((o.niveau for i in p.objets if (o := self.objets.get(i))), default=0)

    def chercher_panoplies(self, *, texte: str = "", niveau_min: int | None = None, niveau_max: int | None = None,
                           caracs: list[str] | None = None, limite: int = 30,
                           decalage: int = 0) -> tuple[int, list[dict]]:
        """Le navigateur de panoplies : nom, niveau (objet le plus haut), caractéristiques du bonus complet."""
        cherche = normaliser(texte) if len(texte.strip()) >= 2 else ""
        voulues = set(caracs or [])
        trouvees = []
        for p in self.panoplies.values():
            niveau = self.niveau_panoplie(p)
            if not niveau or (niveau_min is not None and niveau < niveau_min) or \
                    (niveau_max is not None and niveau > niveau_max):
                continue
            if cherche and cherche not in normaliser(p.nom):
                continue
            complet = max((k for k, v in p.bonus.items() if v), default=0)
            bonus = _caracs_bonus(p.bonus.get(complet, ()))
            if voulues and not voulues <= {c for c, v in bonus if v > 0}:
                continue
            trouvees.append({"id": p.id, "nom": p.nom, "niveau": niveau,
                             "nb_objets": sum(1 for i in p.objets if i in self.objets), "bonus_complet": bonus,
                             "nb_complet": complet})
        trouvees.sort(key=lambda x: (-x["niveau"], -x["id"]))
        return len(trouvees), trouvees[decalage:decalage + limite]

    def panoplie(self, panoplie_id: int) -> dict | None:
        p = self.panoplies.get(panoplie_id)
        if p is None:
            return None
        objets = [o for i in p.objets if (o := self.objets.get(i))]
        places = emplacements_panoplie(objets)
        return {"id": p.id, "nom": p.nom, "niveau": self.niveau_panoplie(p),
                "objets": [{**o.resume(), "emplacement": places.get(o.id)} for o in objets],
                "bonus": [[k, _caracs_bonus(v)] for k, v in sorted(p.bonus.items()) if v]}

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


def _caracs_bonus(effets: tuple[Effet, ...]) -> list[list]:
    return [[k, v] for k, v in caracs_des_effets(effets).items()]


def emplacements_panoplie(objets: list[Objet]) -> dict[int, str]:
    """Où va chaque objet quand on équipe la panoplie entière (`Ri` chez Duffus) : par type, les anneaux dans
    l'ordre (anneau 1 puis 2) ; les Dofus et trophées ne sont pas placés."""
    par_type = {16: "coiffe", 17: "cape", 1: "amulette", 10: "ceinture", 11: "bottes", 82: "bouclier",
                **{t: "arme" for t in TYPES_ARMES}, **{t: "familier" for t in TYPES_FAMILIERS.values()}}
    places: dict[int, str] = {}
    anneaux = ["anneau1", "anneau2"]
    for o in objets:
        if o.type == 9:
            if anneaux:
                places[o.id] = anneaux.pop(0)
        elif o.type in par_type and par_type[o.type] not in places.values():
            places[o.id] = par_type[o.type]
    return places


@cache
def catalogue_par_defaut() -> Catalogue:
    return Catalogue.depuis_dossier()
