"""Les formules du builder, à l'identique de duffus.fr (docs/lots/E3.md §3). Fonctions pures, sans base ni réseau.

1. Totaux (`Gt` chez Duffus) : objets + bonus de panoplie ; pour les 6 caractéristiques principales, s'y ajoutent
   les points de base et les parchemins.
2. Panoplies (`Om`) : par panoplie, le nombre d'objets portés n ≥ 2 donne le palier de bonus n.
3. Conditions d'équipement (`Bm`) : la chaîne `criterions` du jeu (« CS>140&CA>140 », « pk<2 »…).
4. Points de caractéristique (`vt`) : 5 par niveau au-delà du 1, coût par paliers.
5. Affichage (`Kn`) : PA, PM, vitalité, pods, initiative, tacle, fuite, esquives, retraits, prospection,
   invocations et dommages élémentaires, dérivés des totaux.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from epreuve.builder.catalogue import Catalogue, Objet, Panoplie
from epreuve.builder.effets import CARACS_PRINCIPALES, EFFET_CARAC, ELEMENTS, ORDRE_CARACS, valeur_effet

EMPLACEMENTS_ORDRE: tuple[str, ...] = (
    "coiffe", "cape", "amulette", "ceinture", "bottes", "anneau1", "anneau2", "bouclier", "arme", "familier",
    "dofus1", "dofus2", "dofus3", "dofus4", "dofus5", "dofus6",
)  # fmt: skip
NIVEAU_MIN, NIVEAU_MAX = 1, 200
PARCHO_MAX = 100


# --- Bases ----------------------------------------------------------------------------------------------------


def pa_de_base(niveau: int) -> int:
    return 7 if niveau > 99 else 6


def vitalite_de_base(niveau: int) -> int:
    return 55 + 5 * (niveau - 1)


def points_disponibles(niveau: int) -> int:
    return max(0, (niveau - 1) * 5)


def cout_points(carac: str, valeur: int) -> int:
    """Points de caractéristique dépensés pour `valeur` points de base (fonction `vt`)."""
    n = max(0, valeur)
    if carac == "Vitalité":
        return n
    if carac == "Sagesse":
        return n * 3
    cout = 0
    for seuil, prix in ((300, 4), (200, 3), (100, 2)):
        if n > seuil:
            cout += (n - seuil) * prix
            n = seuil
    return cout + n


# --- Panoplies ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PanoplieActive:
    id: int
    nom: str
    nb: int
    max_nb: int
    caracs: tuple[tuple[str, int], ...]


def panoplies_actives(objets: list[Objet], panoplies: dict[int, Panoplie]) -> list[PanoplieActive]:
    """Fonction `Om` : un objet porté deux fois (deux anneaux identiques) compte deux fois, comme chez Duffus."""
    par_panoplie: dict[int, int] = {}
    for o in objets:
        if o.panoplie is not None:
            par_panoplie[o.panoplie] = par_panoplie.get(o.panoplie, 0) + 1
    actives = []
    for pid in sorted(par_panoplie):
        nb, p = par_panoplie[pid], panoplies.get(pid)
        if nb < 2 or p is None:
            continue
        effets = p.bonus.get(nb)
        if not effets:
            continue
        max_nb = max((k for k, v in p.bonus.items() if v), default=nb)
        caracs = tuple((EFFET_CARAC[e], valeur_effet(de, a)) for e, de, a in effets
                       if e in EFFET_CARAC and valeur_effet(de, a) != 0)
        actives.append(PanoplieActive(pid, p.nom, nb, max_nb, caracs))
    return actives


# --- Conditions -----------------------------------------------------------------------------------------------

CONDITION_CARAC = {"CP": "PA", "CM": "PM", "CS": "Force", "CI": "Intelligence", "CA": "Agilité", "CC": "Chance",
                   "CV": "Vitalité", "CW": "Sagesse"}
_COND = re.compile(r"^([A-Za-z]{1,3})(>=|<=|>|<|=)(-?\d+)$")


def _jetons(texte: str) -> list[str]:
    jetons, courant = [], ""
    for ch in re.sub(r"\s+", "", texte):
        if ch in "&|()":
            if courant:
                jetons.append(courant)
                courant = ""
            jetons.append(ch)
        else:
            courant += ch
    if courant:
        jetons.append(courant)
    return jetons


def _arbre(jetons: list[str]):
    """Arbre ET/OU (le ET lie plus fort), tolérant comme celui de Duffus : un morceau illisible vaut « vrai »."""
    pos = 0

    def voir():
        return jetons[pos] if pos < len(jetons) else None

    def prendre():
        nonlocal pos
        j = voir()
        pos += 1
        return j

    def ou():
        g = et()
        while voir() == "|":
            prendre()
            g = ("ou", g, et())
        return g

    def et():
        g = atome()
        while voir() == "&":
            prendre()
            g = ("et", g, atome())
        return g

    def atome():
        if voir() == "(":
            prendre()
            f = ou()
            if voir() == ")":
                prendre()
            return f
        return ("cond", prendre() or "")

    return ou()


def _evaluer(noeud, valeur_reelle, niveau: int, nb_panoplies: int) -> bool:
    if noeud[0] == "et":
        return _evaluer(noeud[1], valeur_reelle, niveau, nb_panoplies) and \
            _evaluer(noeud[2], valeur_reelle, niveau, nb_panoplies)
    if noeud[0] == "ou":
        return _evaluer(noeud[1], valeur_reelle, niveau, nb_panoplies) or \
            _evaluer(noeud[2], valeur_reelle, niveau, nb_panoplies)
    m = _COND.match(noeud[1])
    if not m:
        return True
    cle, op, u = m.group(1), m.group(2), int(m.group(3))
    if cle.upper() == "PL":
        return {">": niveau >= u, ">=": niveau >= u, "<": niveau <= u, "<=": niveau <= u, "=": niveau == u}[op]
    if cle.upper() == "PK":
        g = nb_panoplies
        return {">": g > u, ">=": g >= u, "<": g < u, "<=": g <= u, "=": g == u}[op]
    carac = CONDITION_CARAC.get(cle) or CONDITION_CARAC.get("C" + re.sub(r"^[Cc]", "", cle))
    if not carac:
        return True
    p = valeur_reelle(carac)
    # Duffus compare « > » et « >= » strictement, de même « < » et « <= ».
    return p > u if op in (">", ">=") else p < u if op in ("<", "<=") else p == u


def conditions_remplies(conditions: str | None, totaux: dict[str, int], niveau: int,
                        actives: list[PanoplieActive]) -> bool:
    """Fonction `Bm` : PA et PM comptent leur base ; les autres caractéristiques, les totaux."""
    if not conditions:
        return True

    def valeur_reelle(carac: str) -> int:
        if carac == "PA":
            return totaux.get("PA", 0) + pa_de_base(niveau)
        if carac == "PM":
            return totaux.get("PM", 0) + 3
        return totaux.get(carac, 0)

    nb = sum(1 for a in actives if a.nb >= 2)
    return _evaluer(_arbre(_jetons(conditions)), valeur_reelle, niveau, nb)


# --- Le build complet -----------------------------------------------------------------------------------------


@dataclass
class Build:
    niveau: int = NIVEAU_MAX
    objets: dict[str, int | None] = field(default_factory=dict)  # emplacement → id d'objet
    caracs_base: dict[str, int] = field(default_factory=dict)
    caracs_parcho: dict[str, int] = field(default_factory=dict)
    fm: dict[str, dict[int, int]] = field(default_factory=dict)  # emplacement → effectId → valeur (forgemagie)


@dataclass(frozen=True)
class Resultat:
    totaux: dict[str, int]  # `Gt` : sans les bases (PA, PM, vitalité…)
    affichage: dict[str, int]  # `Kn` : ce que montre le panneau des caractéristiques
    panoplies: list[PanoplieActive]
    alertes: dict[str, list[str]]  # emplacement → raisons
    points_total: int
    points_depenses: int
    detail: dict[str, dict]  # caractéristique → d'où vient chaque point


def nettoyer(build: Build) -> Build:
    """Bornes de saisie de Duffus : niveau 1 à 200, parchemins 0 à 100, points de base entiers."""
    niveau = min(NIVEAU_MAX, max(NIVEAU_MIN, int(build.niveau)))
    base = {c: v for c in CARACS_PRINCIPALES if (v := int(build.caracs_base.get(c) or 0))}
    parcho = {c: v for c in CARACS_PRINCIPALES
              if (v := min(PARCHO_MAX, max(0, int(build.caracs_parcho.get(c) or 0))))}
    objets = {e: build.objets.get(e) for e in EMPLACEMENTS_ORDRE if build.objets.get(e) is not None}
    fm = {e: {int(k): int(v) for k, v in effets.items() if int(k) in EFFET_CARAC}
          for e, effets in build.fm.items() if e in objets}
    return Build(niveau, objets, base, parcho, {e: f for e, f in fm.items() if f})


def calculer(build: Build, catalogue: Catalogue) -> Resultat:
    b = nettoyer(build)
    portes: list[tuple[str, Objet]] = [(e, o) for e in EMPLACEMENTS_ORDRE
                                       if (o := catalogue.objet(b.objets.get(e))) is not None]
    caracs_objets = {e: o.caracs(b.fm.get(e)) for e, o in portes}
    actives = panoplies_actives([o for _, o in portes], catalogue.panoplies)
    bonus_panoplies: dict[str, int] = {}
    for a in actives:
        for carac, v in a.caracs:
            bonus_panoplies[carac] = bonus_panoplies.get(carac, 0) + v

    totaux: dict[str, int] = {}
    for carac in ORDRE_CARACS:
        v = sum(c.get(carac, 0) for c in caracs_objets.values()) + bonus_panoplies.get(carac, 0)
        if carac in CARACS_PRINCIPALES:
            v += b.caracs_base.get(carac, 0) + b.caracs_parcho.get(carac, 0)
        totaux[carac] = v

    detail = {c: {"objets": [[o.nom, caracs_objets[e][c]] for e, o in portes if caracs_objets[e].get(c)],
                  "panoplies": [[f"{a.nom} ({a.nb})", v] for a in actives for k, v in a.caracs if k == c],
                  "base": b.caracs_base.get(c, 0), "parchemin": b.caracs_parcho.get(c, 0)}
              for c in ORDRE_CARACS}

    alertes: dict[str, list[str]] = {}
    ids_dofus = [b.objets.get(f"dofus{i}") for i in range(1, 7)]
    a1, a2 = catalogue.objet(b.objets.get("anneau1")), catalogue.objet(b.objets.get("anneau2"))
    anneaux_doubles = a1 is not None and a2 is not None and a1.id == a2.id and a1.panoplie is not None
    for e, o in portes:
        raisons = []
        if o.niveau > b.niveau:
            raisons.append("Niveau insuffisant")
        if e != "familier" and not conditions_remplies(o.conditions, totaux, b.niveau, actives):
            raisons.append("Conditions non remplies")
        if e.startswith("dofus") and ids_dofus.count(o.id) > 1:
            raisons.append("Objet en double")
        if e in ("anneau1", "anneau2") and anneaux_doubles:
            raisons.append("Anneau en double (même panoplie)")
        if raisons:
            alertes[e] = raisons

    depenses = sum(cout_points(c, b.caracs_base.get(c, 0)) for c in CARACS_PRINCIPALES)
    return Resultat(totaux, affichage(totaux, b.niveau), actives, alertes, points_disponibles(b.niveau),
                    depenses, detail)


def affichage(totaux: dict[str, int], niveau: int) -> dict[str, int]:
    """Fonction `Kn` : les valeurs du panneau, bases et dérivés compris (arrondis vers le bas, comme `Math.floor`)."""
    x = dict(totaux)
    dommages = x.get("Dommages", 0)
    if dommages:
        for el in ("Do Neutre", "Do Terre", "Do Feu", "Do Eau", "Do Air"):
            x[el] = x.get(el, 0) + dommages
    x["PA"] = pa_de_base(niveau) + totaux.get("PA", 0)
    x["PM"] = 3 + totaux.get("PM", 0)
    x["Vitalité"] = x.get("Vitalité", 0) + vitalite_de_base(niveau)
    force, intel, agi, chance = (x.get(c, 0) for c in ("Force", "Intelligence", "Agilité", "Chance"))
    x["Pods"] = x.get("Pods", 0) + 1000 + force * 5
    x["Initiative"] = x.get("Initiative", 0) + force + intel + agi + chance
    for c in ("Fuite", "Tacle"):
        x[c] = x.get(c, 0) + agi // 10
    sagesse = x.get("Sagesse", 0)
    for c in ("Esquive PA", "Esquive PM", "Retrait PA", "Retrait PM"):
        x[c] = x.get(c, 0) + sagesse // 10
    x["Prospection"] = x.get("Prospection", 0) + 100 + chance // 10
    x["Invocations"] = x.get("Invocations", 0) + 1
    return x


def puissance_par_element(totaux: dict[str, int]) -> dict[str, int]:
    """La ligne « + Puissance » sous les caractéristiques : chaque élément augmenté de la puissance."""
    return {c: totaux.get(c, 0) + totaux.get("Puissance", 0) for c in ELEMENTS}
