"""Le calculateur de dégâts d'arme, à l'identique de celui de Duffus (fonctions `Ge` et `Qe`, docs/lots/E3.md §3 bis).

Entrées : l'arme (PA, critique, lignes de dégâts) et les totaux du build (`Gt`, sans les bases).
Pour chaque ligne, un jet minimal et maximal, normal et critique ; puis la moyenne par coup pondérée par le taux
de critique, par tour (lancers par tour) et par PA. Les arrondis sont ceux de `Math.round` (moitié vers le haut).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from epreuve.builder.effets import EFFETS_ARME

STAT_ELEMENT = {"neutre": ("Force", "Do Neutre"), "terre": ("Force", "Do Terre"), "feu": ("Intelligence", "Do Feu"),
                "eau": ("Chance", "Do Eau"), "air": ("Agilité", "Do Air")}
SOINS = frozenset({108, 2998, 2999, 3000, 3001})
VOLS = frozenset({95, 92, 94, 91, 93, 2828})
BONUS_CRITIQUE = frozenset({95, 92, 94, 91, 93, 100, 97, 99, 96, 98, 2822, 2828})  # `We` sans la poussée
BUFFS_PUISSANCE = {"": 0, "base": 300, "crit": 360}  # les deux boutons « +300 / +360 Puissance » de Duffus
MODES = ("melee", "distance")


@dataclass(frozen=True)
class Arme:
    pa: int
    po_min: int
    po: int
    cc: int  # probabilité de critique de l'arme, en %
    bonus_cc: int  # ajouté aux jets en critique
    lancers: int  # par tour (0 : 1)
    effets: tuple[tuple[int, int, int], ...]


def arrondi(x: float) -> int:
    """`Math.round` de JavaScript : la moitié va vers le haut, y compris pour les négatifs."""
    return math.floor(x + 0.5)


def _meilleur(c: dict[str, int]) -> tuple[str, str]:
    """`Me` : l'élément de plus haute caractéristique (Force, Intelligence, Agilité, Chance ; le premier si égalité)."""
    meilleur = ("Force", "Do Terre", c.get("Force", 0))
    for stat, do in (("Intelligence", "Do Feu"), ("Agilité", "Do Air"), ("Chance", "Do Eau")):
        if c.get(stat, 0) > meilleur[2]:
            meilleur = (stat, do, c.get(stat, 0))
    return meilleur[0], meilleur[1]


def _paire(p: float, f: float) -> tuple[int, int] | None:
    p, f = arrondi(p), arrondi(f)
    if p and not f:
        return p, p
    if f and not p:
        return f, f
    return p, f


def jet(effet: tuple[int, int, int], totaux: dict[str, int], mode: str = "melee", critique: bool = False,
        bonus_cc: int = 0, bonus_soin: int = 0) -> tuple[int, int] | None:
    """Fonction `Ge` : (min, max) d'une ligne, ou None si elle est vide. `bonus_soin` : la puissance du buff."""
    eid, de, a = effet
    o = dict(totaux)
    for c in ("Force", "Intelligence", "Chance", "Agilité", "Puissance"):
        o[c] = max(0, o.get(c, 0))
    if eid == 5:
        return de, de
    if critique and bonus_cc > 0 and eid in BONUS_CRITIQUE:
        de, a = (de + bonus_cc if de else 0), (a + bonus_cc if a else 0)
    if eid in SOINS:
        stat = STAT_ELEMENT[EFFETS_ARME[eid][1]][0]
        if critique and bonus_cc > 0:
            de, a = (de + bonus_cc if de else 0), (a + bonus_cc if a else 0)
        if not de and not a:
            return None
        k, soins = (o.get(stat, 0) + bonus_soin + 100) / 100, max(0, o.get("Soins", 0))
        return _paire(k * de + soins if de else 0, k * a + soins if a else 0)
    if EFFETS_ARME[eid][1] == "meilleur":
        stat, do = _meilleur(o)
    else:
        stat, do = STAT_ELEMENT[EFFETS_ARME[eid][1]]
    if not de and not a:
        return None
    k = (o["Puissance"] + o.get(stat, 0) + 100) / 100
    fixe = o.get(do, 0) + o.get("Dommages", 0) + (o.get("Do Critique", 0) if critique else 0)
    armes = 1 + o.get("% Do Armes", 0) / 100
    portee = 1 + o.get("% Do Mélée" if mode == "melee" else "% Do Dist", 0) / 100
    p = (k * de + fixe if de else 0) * armes
    f = (k * a + fixe if a else 0) * armes
    return _paire(p * portee, f * portee)


def calculer_arme(arme: Arme, totaux: dict[str, int], mode: str = "melee", buff: str = "") -> dict:
    """Fonction `Qe` : lignes normales et critiques, totaux, vol de vie, moyennes par coup, par tour et par PA."""
    puissance = BUFFS_PUISSANCE.get(buff, 0)
    caracs = {**totaux, "Puissance": totaux.get("Puissance", 0) + puissance}
    a_critique = arme.cc > 0
    lignes = []
    for eff in arme.effets:
        if eff[0] == 5:
            continue  # la poussée n'est pas une ligne de dégâts
        normal = jet(eff, caracs, mode, False, 0, puissance)
        crit = jet(eff, caracs, mode, True, arme.bonus_cc, puissance) if a_critique else None
        if normal is None and crit is None:
            continue
        lignes.append({"effet": eff[0], "libelle": EFFETS_ARME[eff[0]][0], "element": EFFETS_ARME[eff[0]][1],
                       "soin": eff[0] in SOINS, "vol": eff[0] in VOLS, "normal": normal, "critique": crit})

    def somme(cle: str, soin: bool) -> tuple[int, int]:
        js = [x[cle] for x in lignes if x["soin"] == soin and x[cle]]
        return sum(j[0] for j in js), sum(j[1] for j in js)

    def vol(cle: str) -> tuple[int, int] | None:
        js = [x[cle] for x in lignes if x["vol"] and x[cle]]
        if not js:
            return None
        lo, hi = sum(j[0] for j in js), sum(j[1] for j in js)
        return (lo // 2, hi // 2) if lo or hi else None

    degats, degats_cc = somme("normal", False), somme("critique", False)
    soins, soins_cc = somme("normal", True), somme("critique", True)
    taux = min(100, arme.cc + totaux.get("% Critique", 0)) / 100 if a_critique else 0
    moyenne = lambda n, c: arrondi((1 - taux) * (n[0] + n[1]) / 2 + taux * (c[0] + c[1]) / 2)  # noqa: E731
    par_coup, soin_coup = moyenne(degats, degats_cc), moyenne(soins, soins_cc)
    lancers = arme.lancers or 1
    return {"lignes": lignes, "degats": degats, "degats_critique": degats_cc,
            "soins": soins, "soins_critique": soins_cc,
            "vol": vol("normal"), "vol_critique": vol("critique"), "taux_critique": round(taux * 100),
            "par_coup": par_coup, "par_tour": par_coup * lancers, "soins_par_coup": soin_coup,
            "soins_par_tour": soin_coup * lancers,
            "par_pa": round(arrondi(par_coup / arme.pa * 10) / 10, 1) if arme.pa > 0 else None,
            "pa": arme.pa, "po": [arme.po_min, arme.po], "cc": arme.cc, "bonus_cc": arme.bonus_cc, "lancers": lancers}
