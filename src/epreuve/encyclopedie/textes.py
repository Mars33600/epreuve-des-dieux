"""Fonctions pures de l'encyclopédie : clé de recherche, requête plein texte, effets en clair, familles, stuffs.

Aucune base ni réseau ici : tout se teste à la main (tests/encyclopedie/test_textes.py).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

# Les familles d'objets de la page « Objets » : on range chaque type de Dofus par son super-type.
FAMILLES: dict[str, str] = {
    "equipements": "Équipements",
    "armes": "Armes",
    "familiers": "Familiers et montures",
    "ressources": "Ressources",
    "consommables": "Consommables",
    "quetes": "Objets de quête",
    "cosmetiques": "Cosmétiques",
    "autres": "Autres",
}
_SUPER_TYPES: dict[int, str] = {
    1: "equipements", 3: "equipements", 4: "equipements", 5: "equipements", 7: "equipements",
    10: "equipements", 11: "equipements", 13: "equipements", 2: "armes", 12: "familiers", 9: "ressources",
    6: "consommables", 16: "consommables", 17: "consommables", 18: "consommables", 19: "consommables",
    14: "quetes", 22: "cosmetiques", 25: "cosmetiques",
}  # fmt: skip

# Les métiers des recettes (identifiants du jeu), comme sur la fiche objet de Duffus.
METIERS: dict[int, str] = {2: "Bûcheron", 11: "Forgeron", 13: "Sculpteur", 15: "Cordonnier", 16: "Bijoutier",
                           24: "Mineur", 26: "Alchimiste", 27: "Tailleur", 28: "Paysan", 36: "Pêcheur",
                           41: "Chasseur", 60: "Façonneur", 65: "Bricoleur", 79: "Éleveur"}

# Emplacements d'un stuff, dans l'ordre d'affichage de Duffus.
EMPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("coiffe", "Coiffe"), ("cape", "Cape"), ("amulette", "Amulette"), ("anneau1", "Anneau"),
    ("anneau2", "Anneau"), ("ceinture", "Ceinture"), ("bottes", "Bottes"), ("arme", "Arme"),
    ("bouclier", "Bouclier"), ("familier", "Familier"),
)  # fmt: skip

TRIS = {"recents": "Plus récents", "niveau_desc": "Niveau (décroissant)", "niveau_asc": "Niveau (croissant)",
        "nom_asc": "Nom (A → Z)", "nom_desc": "Nom (Z → A)"}


def famille_du_super_type(super_type: int | None) -> str:
    return _SUPER_TYPES.get(super_type or -1, "autres")


def cle_recherche(texte: str | None) -> str:
    """Minuscules, sans accents ni ligatures, ponctuation remplacée par des espaces."""
    t = unicodedata.normalize("NFD", (texte or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c)).replace("œ", "oe").replace("æ", "ae")
    return " ".join(re.sub(r"[^0-9a-z]+", " ", t).split())


def requete_plein_texte(saisie: str | None) -> str | None:
    """« Épée boi » → « epee:* & boi:* » (chaque mot est un début de mot). None si rien à chercher.

    Les mots ne contiennent que [0-9a-z] après `cle_recherche` : aucun opérateur de tsquery ne peut passer.
    """
    mots = cle_recherche(saisie).split()[:8]
    return " & ".join(f"{m}:*" for m in mots) or None


# --- Effets ---------------------------------------------------------------------------------------------

_BLOC = re.compile(r"\{\{([^}]*)\}\}")


def formater_effet(modele: str | None, de_min: int, de_max: int, valeur: int = 0) -> str:
    """Le texte d'un effet, comme la fonction de Duffus : « #1{{~1~2 à }}#2 Force » + (7, 10) → « 7 à 10 Force ».

    - `#1` = la borne basse, `#2` = la borne haute (absente si égale ou nulle), `#3` = la valeur ;
    - `{{…~1~2…}}` ne s'affiche que s'il y a deux bornes, `{{~ps}}` met un pluriel ;
    - un « - » devant `#1` porte déjà le signe : la valeur s'écrit sans le sien.
    """
    if not modele:
        return ""
    bas: int | None
    haut: int | None
    if de_min and de_max:
        bas, haut = (de_min, None) if de_min == de_max else (de_min, de_max)
    elif de_min or de_max:
        bas, haut = de_min or de_max, None
    else:
        bas, haut = None, None

    def bloc(m: re.Match) -> str:
        contenu = m.group(1)
        if contenu.strip() == "~ps":
            pluriel = haut is not None or (bas is not None and abs(bas) != 1) or (
                bas is None and valeur is not None and abs(valeur) != 1)
            return "s" if pluriel else ""
        deux, un, deux_seul = "~1~2" in contenu, "~1" in contenu, "~2" in contenu
        if deux or (un and deux_seul):
            montrer = bas is not None and haut is not None
        elif un:
            montrer = bas is not None
        elif deux_seul:
            montrer = haut is not None
        else:
            montrer = True
        return contenu.replace("~1~2", "").replace("~1", "").replace("~2", "") if montrer else ""

    texte = _BLOC.sub(bloc, modele)

    def nombre(n: int | None, signe_ecrit: bool) -> str:
        if n is None:
            return ""
        return str(abs(n) if signe_ecrit and n < 0 else n)

    texte = texte.replace("#1", nombre(bas, bool(re.search(r"-\s*#1", modele))))
    texte = texte.replace("#2", nombre(haut, bool(re.search(r"-\s*#2", modele))))
    texte = texte.replace("#3", nombre(valeur, bool(re.search(r"-\s*#3", modele))))
    texte = texte.replace("~zs", "")
    texte = re.sub(r"--(\d)", r"-\1", texte)
    return " ".join(texte.split())


@dataclass(frozen=True)
class EffetLu:
    texte: str
    negatif: bool


def effets_en_clair(effets: Iterable[list[int]], modeles: dict[int, tuple[str | None, int | None]]
                    ) -> list[EffetLu]:
    """[[effet, min, max, valeur]] → textes, dans l'ordre de priorité du jeu ; effets sans texte omis."""
    lus: list[tuple[int, int, EffetLu]] = []
    for i, (ident, de_min, de_max, valeur) in enumerate(effets):
        modele, priorite = modeles.get(ident, (None, None))
        texte = formater_effet(modele, de_min, de_max, valeur)
        if texte:
            negatif = texte.startswith("-") or (modele or "").lstrip().startswith("-")
            lus.append((priorite if priorite is not None else 9999, i, EffetLu(texte, negatif)))
    return [e for _, _, e in sorted(lus, key=lambda x: (x[0], x[1]))]


# --- Stuffs et étages -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class TrancheVisible:
    """Ce qu'une page de stuffs sait d'un étage : seulement des étages visibles par la personne."""

    numero: int
    nom: str
    niveau_min: int
    niveau_max: int


def etage_du_niveau(niveau: int, tranches: Iterable[TrancheVisible]) -> TrancheVisible | None:
    """Le premier étage (par numéro) dont la tranche contient le niveau. None : hors des étages visibles."""
    for t in sorted(tranches, key=lambda t: t.numero):
        if t.niveau_min <= niveau <= t.niveau_max:
            return t
    return None


def icone_objet(icone: int | None) -> str | None:
    """Les images viennent de DofusDB (autorisé par la CSP), jamais du stockage de Duffus."""
    return f"https://api.dofusdb.fr/img/items/{icone}.png" if icone else None


def icone_sort(icone: int | None) -> str | None:
    # Les fichiers de DofusDB s'appellent « sort_<icône>.png » : « <icône>.png » seul répond 404.
    return f"https://api.dofusdb.fr/img/spells/sort_{icone}.png" if icone is not None else None


def image_monstre(gfx: int | None) -> str | None:
    """L'image d'un monstre porte le numéro de son apparence (`gfx`), pas celui du monstre : `<id>.png` répond 404."""
    return f"https://api.dofusdb.fr/img/monsters/{gfx}.png" if gfx else None


# --- Conditions d'objet et de quête ----------------------------------------------------------------------

_ATOME = re.compile(r"([A-Za-z]{2})([=<>!])([^&|()]*)")
_OPS = {"=": "égal à", "!": "différent de", "<": "inférieur à", ">": "supérieur à"}
_CARACS = {"s": "Force", "i": "Intelligence", "v": "Vitalité", "a": "Agilité", "c": "Chance", "w": "Sagesse"}
_AUTRES_CARACS = {"CP": "PA", "CM": "PM"}


def ids_des_conditions(texte: str | None) -> dict[str, set[int]]:
    """Les objets (`PO`) et les quêtes (`Qa`, `Qf`) cités par une condition, pour aller chercher leurs noms."""
    ids: dict[str, set[int]] = {"objets": set(), "quetes": set()}
    for code, _, valeur in _ATOME.findall(texte or ""):
        if valeur.isdigit():
            if code == "PO":
                ids["objets"].add(int(valeur))
            elif code in ("Qa", "Qf", "Qc"):
                ids["quetes"].add(int(valeur))
    return ids


def _atome(code: str, op: str, valeur: str, objets: dict[int, str], quetes: dict[int, str]) -> str:
    nombre = int(valeur) if valeur.isdigit() else None
    nom_quete = f"« {quetes.get(nombre, f'n°{valeur}')} »" if code in ("Qa", "Qf", "Qc") else ""
    egal, autre = op == "=", op == "!"
    if code == "PL":
        return f"Niveau {_OPS[op]} {valeur}"
    if code[0] in "Cc" and code[1].lower() in _CARACS:
        base = " de base" if code[0] == "c" else ""
        return f"{_CARACS[code[1].lower()]}{base} {_OPS[op]} {valeur}"
    if code in _AUTRES_CARACS:
        return f"{_AUTRES_CARACS[code]} {_OPS[op]} {valeur}"
    if code == "Qf" and (egal or autre):
        return f"Quête {nom_quete} {'terminée' if egal else 'non terminée'}"
    if code == "Qa" and (egal or autre):
        return f"Quête {nom_quete} {'en cours' if egal else 'pas en cours'}"
    if code == "Qc" and (egal or autre):
        return f"Quête {nom_quete} {'terminable' if egal else 'non terminable'}"
    if code == "Qo":
        return f"Objectif de quête {_OPS[op]} n°{valeur}"
    if code == "PO" and (egal or autre):
        nom = objets.get(nombre, f"n°{valeur}") if nombre is not None else valeur
        return f"{'Posséder' if egal else 'Ne pas posséder'} l'objet « {nom} »"
    if code == "PE" and (egal or autre):
        return f"{'Avoir' if egal else 'Ne pas avoir'} l'état n°{valeur}"
    if code == "OA" and (egal or autre):
        return f"{'Avoir' if egal else 'Ne pas avoir'} le succès n°{valeur}"
    if code == "PZ" and valeur == "1" and egal:
        return "Être abonné"
    return f"{code} {_OPS[op]} {valeur}"


def conditions_en_clair(texte: str | None, objets: dict[int, str] | None = None,
                        quetes: dict[int, str] | None = None) -> str:
    """« PL>99&(PB=609|PB=610) » → « Niveau supérieur à 99 et (PB égal à 609 ou PB égal à 610) ».

    Les codes connus sont traduits (niveau, caractéristiques, quêtes, objets possédés…). Les autres restent
    lisibles mais gardent leur code : mieux vaut un code honnête qu'une traduction inventée.
    """
    objets, quetes = objets or {}, quetes or {}
    if not texte:
        return ""
    texte = _ATOME.sub(lambda m: "\x00" + _atome(m[1], m[2], m[3].strip(), objets, quetes) + "\x01", texte)
    texte = texte.replace("&", " et ").replace("|", " ou ")
    return " ".join(texte.replace("\x00", "").replace("\x01", "").split())


# --- Quêtes -------------------------------------------------------------------------------------------------

REPETITIONS = {0: "Non répétable", 1: "Répétable", 2: "Répétable chaque jour", 3: "Répétable chaque semaine",
               4: "Répétable chaque mois"}


def ids_des_objectifs(objectifs: Iterable[dict]) -> dict[str, set[int]]:
    """PNJ, objets et monstres cités par des objectifs de quête."""
    ids: dict[str, set[int]] = {"pnj": set(), "objets": set(), "monstres": set()}
    for o in objectifs:
        p = [x or 0 for x in o["p"]]
        match o["classe"]:
            case "GoToNpc":
                ids["pnj"].add(p[0])
            case "BringItemToNpc":
                ids["pnj"].add(p[0])
                ids["objets"].add(p[1])
            case "BringSoulToNpc":
                ids["monstres"].add(p[0])
                ids["pnj"].add(p[1])
            case "FightMonster" | "MultiFightMonster" | "FightMonstersOnMap":
                ids["monstres"].add(p[0])
            case "CraftItem":
                ids["objets"].add(p[0])
    return ids


def objectif_en_clair(o: dict, pnj: dict[int, str], objets: dict[int, str], monstres: dict[int, str]) -> str:
    """Le texte d'un objectif de quête. Les types inconnus gardent leur texte ou leur nom de type."""
    p = [x or 0 for x in o["p"]]
    n_pnj, n_obj, n_mon = (lambda i: pnj.get(i, f"PNJ n°{i}")), (lambda i: objets.get(i, f"objet n°{i}")), (
        lambda i: monstres.get(i, f"monstre n°{i}"))
    lieu = f" en [{o['x']}, {o['y']}]" if o.get("x") is not None and o.get("y") is not None else ""
    match o["classe"]:
        case "FreeForm":
            return o["texte"] or "Objectif libre"
        case "GoToNpc":
            return f"Parler à {n_pnj(p[0])}"
        case "BringItemToNpc":
            return f"Apporter {p[2] or 1} × {n_obj(p[1])} à {n_pnj(p[0])}"
        case "BringSoulToNpc":
            return f"Apporter l'âme de {n_mon(p[0])} à {n_pnj(p[1])}"
        case "DiscoverMap":
            return f"Découvrir la carte n°{p[0]}"
        case "DiscoverSubArea":
            return f"Découvrir la sous-zone n°{p[0]}"
        case "FightMonster" | "MultiFightMonster":
            return f"Vaincre {p[1] or 1} × {n_mon(p[0])}{lieu}"
        case "FightMonstersOnMap":
            return f"Vaincre {p[1] or 1} × {n_mon(p[0])} sur la carte n°{p[2]}"
        case "CraftItem":
            return f"Fabriquer {p[1] or 1} × {n_obj(p[0])}"
    return o["texte"] or o["classe"] or "Objectif"
