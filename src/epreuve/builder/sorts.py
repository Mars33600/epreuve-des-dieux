"""Le calculateur de sorts, à l'identique de l'onglet « Sorts » du builder de Duffus (fonction `Rt`).

Les sorts et leurs niveaux viennent des tables de l'encyclopédie (`ency_classe`, `ency_sort`, lot E2) : aucune
aspiration de plus. Pour une classe et un niveau de personnage, on prend le grade le plus haut accessible, puis
chaque ligne de dommages, de vol, de soin ou de poussée, en normal (`effets`) et en critique (`effets_cc`).
Arrondis : vers le bas à chaque étape (`Math.floor`), sauf les soins (`Math.round`).
"""

from __future__ import annotations

import math

from epreuve.builder.arme import arrondi

# effectId → (libellé, catégorie) : table `Be` du calculateur de sorts de Duffus.
EFFETS_SORT: dict[int, tuple[str, str]] = {
    95: ("vol Neutre", "neutre"), 92: ("vol Terre", "terre"), 94: ("vol Feu", "feu"), 91: ("vol Eau", "eau"),
    93: ("vol Air", "air"), 100: ("dommages Neutre", "neutre"), 97: ("dommages Terre", "terre"),
    99: ("dommages Feu", "feu"), 96: ("dommages Eau", "eau"), 98: ("dommages Air", "air"), 108: ("soins", "soin"),
    2822: ("do. meilleur élément", "meilleur"), 2828: ("vol meilleur élément", "meilleur"),
    2832: ("do. pire élément", "pire"), 2890: ("vol pire élément", "pire"), 5: ("dommages Poussée", "poussee"),
}  # fmt: skip
STAT_ELEMENT = {"neutre": ("Force", "Do Neutre"), "terre": ("Force", "Do Terre"), "feu": ("Intelligence", "Do Feu"),
                "eau": ("Chance", "Do Eau"), "air": ("Agilité", "Do Air")}
ORDRE_ELEMENTS = (("Force", "Do Terre"), ("Intelligence", "Do Feu"), ("Agilité", "Do Air"), ("Chance", "Do Eau"))


def _extreme(c: dict[str, int], meilleur: bool) -> tuple[str, str]:
    """`$t` (meilleur) et `qt` (pire) : le premier élément en cas d'égalité."""
    choisi = ORDRE_ELEMENTS[0]
    for stat, do in ORDRE_ELEMENTS[1:]:
        v, ref = c.get(stat, 0), c.get(choisi[0], 0)
        if (v > ref) if meilleur else (v < ref):
            choisi = (stat, do)
    return choisi


def _paire(p: int, f: int) -> tuple[int, int]:
    if p and not f:
        return p, p
    if f and not p:
        return f, f
    return p, f


def jet_sort(effet: list[int] | tuple[int, ...], c: dict[str, int], mode: str = "melee", critique: bool = False,
             niveau: int = 200) -> tuple[int, int] | None:
    """Fonction `Rt` : (min, max) d'une ligne de sort, ou None si elle est vide ou n'est pas un dommage."""
    eid, de, a = int(effet[0]), int(effet[1]), int(effet[2])
    if eid not in EFFETS_SORT:
        return None
    categorie = EFFETS_SORT[eid][1]
    if eid == 5:
        if not de:
            return None
        v = math.floor((niveau / 2 + c.get("Do Pou", 0) + 32) * de / 4)
        return v, v
    if not de and not a:
        return None
    if categorie == "soin":
        k, soins = (c.get("Intelligence", 0) + 100) / 100, max(0, c.get("Soins", 0))
        return _paire(arrondi(k * de + soins) if de else 0, arrondi(k * a + soins) if a else 0)
    if categorie in ("meilleur", "pire"):
        stat, do = _extreme(c, categorie == "meilleur")
    else:
        stat, do = STAT_ELEMENT[categorie]
    k = (c.get("Puissance", 0) + c.get(stat, 0) + 100) / 100
    fixe = c.get(do, 0) + c.get("Dommages", 0) + (c.get("Do Critique", 0) if critique else 0)
    sorts, portee = c.get("% Do Sorts", 0), c.get("% Do Mélée" if mode == "melee" else "% Do Dist", 0)

    def un(d: int) -> int:
        if not d:
            return 0
        v = math.floor(k * d) + fixe
        v = math.floor(v * (100 + sorts) / 100)
        return math.floor(v * (100 + portee) / 100)

    return _paire(un(de), un(a))


def grade_pour(niveaux: list[dict], niveau_joueur: int) -> dict | None:
    """Le grade le plus haut dont le niveau requis est atteint (`_minPlayerLevels` de Duffus)."""
    permis = [n for n in niveaux if (n.get("niveau") or 0) <= niveau_joueur]
    return max(permis, key=lambda n: n.get("grade") or 0) if permis else None


def calculer_sort(sort: dict, totaux: dict[str, int], niveau: int, mode: str = "melee") -> dict | None:
    """Un sort de classe au niveau du build ; None s'il n'est pas encore appris."""
    grade = grade_pour(sort.get("niveaux") or [], niveau)
    if grade is None:
        return None

    def lignes(effets: list, critique: bool) -> list[dict]:
        return [{"effet": int(e[0]), "libelle": EFFETS_SORT[int(e[0])][0],
                 "soin": EFFETS_SORT[int(e[0])][1] == "soin", "jet": list(j)}
                for e in effets or [] if (j := jet_sort(e, totaux, mode, critique, niveau)) is not None]

    cc = grade.get("cc") or 0
    return {"id": sort["id"], "nom": sort["nom"], "icone": sort.get("icone"), "grade": grade.get("grade"),
            "pa": grade.get("pa"), "po": [grade.get("po_min"), grade.get("po_max")], "cc": cc,
            "taux_critique": min(100, cc + totaux.get("% Critique", 0)) if cc > 0 else 0,
            "normal": lignes(grade.get("effets"), False), "critique": lignes(grade.get("effets_cc"), True)}
