"""Principal ou secondaire : un classement déterministe, sans IA (SPEC §6.3).

Une quête est principale si elle figure dans au moins un guide « par Dofus » d'un Dofus retenu, prérequis
directs ou indirects compris (la « fermeture »). L'admin peut forcer la nature : son choix prime toujours.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from epreuve.domaine.modeles import Nature, OrigineNature

_JETONS = re.compile(r"[()&|]|[^()&|]+")
_QF = re.compile(r"^Qf=(\d+)$")


def quetes_obligatoires(critere: str) -> frozenset[int]:
    """Ids Qf=… exigés en « ET » dans un startCriterion DofusDB ; tout groupe contenant « | » est ignoré.

    `Qf=1462&PL>39` → {1462} ; `(Qf=272|Qf=273|Qf=274)&Qf=10` → {10} : une seule des trois suffit, aucune
    n'est donc obligatoire. C'est pourquoi on n'utilise pas `need.quests`, qui met les « OU » à plat.
    """
    jetons = [j.strip() for j in _JETONS.findall(critere or "") if j.strip()]
    pos = 0

    def groupe() -> frozenset[int] | None:
        """Lit jusqu'à « ) » ou la fin. None si le groupe contient un « | » (ignoré en entier)."""
        nonlocal pos
        ids: set[int] = set()
        ou = False
        while pos < len(jetons):
            j = jetons[pos]
            pos += 1
            if j == ")":
                break
            if j == "|":
                ou = True
            elif j == "(":
                sous = groupe()
                ids |= sous or set()
            elif m := _QF.match(j):
                ids.add(int(m.group(1)))
        return None if ou else frozenset(ids)

    return groupe() or frozenset()


def fermeture(racines: Iterable[int], prerequis: Mapping[int, Iterable[int]]) -> frozenset[int]:
    """Racines et tous leurs prérequis directs ou indirects ; supporte les cycles."""
    vus: set[int] = set()
    a_voir = list(racines)
    while a_voir:
        q = a_voir.pop()
        if q not in vus:
            vus.add(q)
            a_voir.extend(prerequis.get(q, ()))
    return frozenset(vus)


@dataclass(frozen=True)
class Classement:
    nature: Nature
    origine: OrigineNature
    dofus: tuple[str, ...]


def _alphabetique(noms: Iterable[str]) -> tuple[str, ...]:
    def cle(n: str) -> tuple[str, str]:
        sans_accent = "".join(c for c in unicodedata.normalize("NFD", n) if not unicodedata.combining(c))
        return sans_accent.casefold(), n

    return tuple(sorted(set(noms), key=cle))


def classer(quetes: Iterable[int], guides_duffus: Mapping[str, Iterable[int]],
            guides_repli: Mapping[str, Iterable[int]], dofus_retenus: Collection[str],
            forcees: Mapping[int, Nature]) -> dict[int, Classement]:
    """Priorité : forcees (origine admin) > guides_duffus (fermés) > guides_repli (origine dofusdb).

    Le repli ne sert que pour un Dofus retenu SANS guide Duffus. Une quête dans aucun guide d'un Dofus retenu
    est secondaire (origine duffus). Ordre des dofus : alphabétique, sans tenir compte des accents.
    """
    duffus = {d: frozenset(qs) for d, qs in guides_duffus.items() if d in dofus_retenus}
    repli = {d: frozenset(qs) for d, qs in guides_repli.items() if d in dofus_retenus and d not in guides_duffus}
    resultat: dict[int, Classement] = {}
    for q in quetes:
        par_duffus = _alphabetique(d for d, qs in duffus.items() if q in qs)
        par_repli = _alphabetique(d for d, qs in repli.items() if q in qs)
        if q in forcees:
            nature = forcees[q]
            dofus = _alphabetique(par_duffus + par_repli) if nature == "principale" else ()
            resultat[q] = Classement(nature, "admin", dofus)
        elif par_duffus:
            resultat[q] = Classement("principale", "duffus", par_duffus)
        elif par_repli:
            resultat[q] = Classement("principale", "dofusdb", par_repli)
        else:
            resultat[q] = Classement("secondaire", "duffus", ())
    return resultat
