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


def image_monstre(ident: int | None) -> str | None:
    return f"https://api.dofusdb.fr/img/monsters/{ident}.png" if ident else None
