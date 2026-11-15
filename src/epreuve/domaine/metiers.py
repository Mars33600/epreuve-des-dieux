"""Les métiers de Dofus 3 et le recensement de la guilde (demande de BillyBarkMan, 15/11).

Chaque grimpeur déclare ses métiers et leur niveau sur son tableau de bord ; la page « Métiers » liste, pour un
métier et un niveau minimum, qui peut fabriquer (« un bijoutier 25 pour un anneau Bouftou ? »). La liste suit les
métiers de DofusDB (`/jobs`), sans « Base ». Un niveau vide ou à 0 veut dire « pas ce métier ».
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Famille = Literal["recolte", "artisanat", "forgemagie", "autre"]
NIVEAU_MAX = 200


@dataclass(frozen=True)
class Metier:
    cle: str
    nom: str
    famille: Famille


@dataclass(frozen=True)
class NiveauMetier:
    grimpeur_id: int
    metier: str
    niveau: int
    maj_le: datetime


METIERS: tuple[Metier, ...] = (
    Metier("alchimiste", "Alchimiste", "recolte"), Metier("bucheron", "Bûcheron", "recolte"),
    Metier("chasseur", "Chasseur", "recolte"), Metier("mineur", "Mineur", "recolte"),
    Metier("paysan", "Paysan", "recolte"), Metier("pecheur", "Pêcheur", "recolte"),
    Metier("bijoutier", "Bijoutier", "artisanat"), Metier("bricoleur", "Bricoleur", "artisanat"),
    Metier("cordonnier", "Cordonnier", "artisanat"), Metier("faconneur", "Façonneur", "artisanat"),
    Metier("forgeron", "Forgeron", "artisanat"), Metier("sculpteur", "Sculpteur", "artisanat"),
    Metier("tailleur", "Tailleur", "artisanat"),
    Metier("cordomage", "Cordomage", "forgemagie"), Metier("costumage", "Costumage", "forgemagie"),
    Metier("facomage", "Façomage", "forgemagie"), Metier("forgemage", "Forgemage", "forgemagie"),
    Metier("joaillomage", "Joaillomage", "forgemagie"), Metier("parchomage", "Parchomage", "forgemagie"),
    Metier("sculptemage", "Sculptemage", "forgemagie"),
    Metier("bestiologue", "Bestiologue", "autre"), Metier("eleveur", "Éleveur", "autre"),
)  # fmt: skip
FAMILLES: tuple[tuple[Famille, str], ...] = (
    ("recolte", "Récolte"), ("artisanat", "Artisanat"), ("forgemagie", "Forgemagie"), ("autre", "Autres"),
)
PAR_CLE: dict[str, Metier] = {m.cle: m for m in METIERS}


def lire_niveaux(saisie: dict[str, str]) -> dict[str, int]:
    """Le formulaire ({clé: texte}) → {clé: niveau} des métiers déclarés. Vide ou 0 : pas ce métier.

    ValueError(clé) pour un métier inconnu ou un niveau qui n'est pas un entier de 0 à 200.
    """
    niveaux: dict[str, int] = {}
    for cle, brut in saisie.items():
        if cle not in PAR_CLE:
            raise ValueError(cle)
        texte = brut.strip()
        if not texte:
            continue
        if not texte.isdigit() or int(texte) > NIVEAU_MAX:
            raise ValueError(cle)
        if int(texte):
            niveaux[cle] = int(texte)
    return niveaux


def artisans(niveaux: list[NiveauMetier], cle: str, minimum: int = 1) -> list[NiveauMetier]:
    """Ceux qui ont le métier `cle` au niveau `minimum` ou plus, du plus haut niveau au plus bas."""
    return sorted((n for n in niveaux if n.metier == cle and n.niveau >= minimum),
                  key=lambda n: (-n.niveau, n.grimpeur_id))


# --- Le bot du salon « métiers » : « @Gardien paysan lvl 15 » ou « @Gardien Billy » ---------------------------

# Les anciens métiers de Dofus et les surnoms courants, ramenés aux métiers de Dofus 3.
ALIAS: dict[str, str] = {
    "boulanger": "paysan", "meunier": "paysan", "boucher": "chasseur", "poissonnier": "pecheur",
    "bijou": "bijoutier", "cordo": "cordonnier", "faco": "faconneur", "forge": "forgeron", "sculpt": "sculpteur",
    "alchi": "alchimiste", "bucheronne": "bucheron", "pecheuse": "pecheur", "paysanne": "paysan",
}
LIMITE_DISCORD = 1900  # un message Discord fait 2 000 caractères au plus


def plier(texte: str) -> str:
    """Minuscules, sans accents : « Bûcheron » et « bucheron » se valent."""
    return "".join(c for c in unicodedata.normalize("NFKD", texte.lower()) if not unicodedata.combining(c))


def trouver_metier(mot: str) -> Metier | None:
    """Un métier par sa clé, son nom, un alias, ou le début de son nom (4 lettres au moins, sans ambiguïté)."""
    m = plier(mot).strip(" .,!?:;")
    if m in PAR_CLE:
        return PAR_CLE[m]
    if m in ALIAS:
        return PAR_CLE[ALIAS[m]]
    debut = [x for x in METIERS if len(m) >= 4 and x.cle.startswith(m)]
    return debut[0] if len(debut) == 1 else None


@dataclass(frozen=True)
class Demande:
    metier: Metier | None
    minimum: int
    joueur: str | None


def interpreter(texte: str) -> Demande | None:
    """« paysan lvl 15 », « bijoutier 25 », « niv 30 forgeron » → un métier et un niveau minimum ; un autre texte
    (« Billy ») → un joueur ; rien → None. Le niveau se lit après « lvl », « niv », « niveau », ou seul."""
    plie = plier(texte)
    niveau = re.search(r"(?:lvl|lv|niv(?:eau)?|level)\s*\.?\s*(\d{1,3})", plie) or re.search(r"\b(\d{1,3})\b", plie)
    minimum = min(max(int(niveau.group(1)), 1), NIVEAU_MAX) if niveau else 1
    mots = re.findall(r"[a-z'-]+", plie)
    metier = next((m for m in map(trouver_metier, mots) if m is not None), None)
    if metier is not None:
        return Demande(metier, minimum, None)
    reste = " ".join(texte.split()).strip(" .,!?:;")
    return Demande(None, 1, reste) if reste else None


def texte_artisans(metier: Metier, minimum: int, liste: list[tuple[str, int]], site: str) -> str:
    """La réponse pour un métier : les pseudos (sans mention Discord), du plus haut niveau au plus bas."""
    seuil = f"niv. {minimum}+" if minimum > 1 else "tous niveaux"
    if not liste:
        return (f"Personne n'a déclaré **{metier.nom}** ({seuil}). "
                f"Déclarez vos métiers sur votre tableau de bord : {site}/tableau-de-bord")
    lignes = [f"**{metier.nom}** ({seuil}) : {len(liste)} grimpeur{'s' if len(liste) > 1 else ''}"]
    lignes += [f"• {pseudo} (niv. {niveau})" for pseudo, niveau in liste]
    return _couper("\n".join(lignes))


def texte_joueur(pseudo: str, niveaux: list[tuple[str, int]]) -> str:
    """La réponse pour un joueur : ses métiers, du plus haut niveau au plus bas."""
    if not niveaux:
        return f"**{pseudo}** n'a déclaré aucun métier."
    return _couper(f"**{pseudo}** : " + " · ".join(f"{nom} {niveau}" for nom, niveau in niveaux))


def texte_aide(site: str) -> str:
    return ("Demande-moi un métier et un niveau (`paysan lvl 15`, `bijoutier 25`) ou un joueur (`Billy`). "
            f"La liste complète : {site}/metiers")


def _couper(texte: str) -> str:
    return texte if len(texte) <= LIMITE_DISCORD else texte[:LIMITE_DISCORD].rsplit("\n", 1)[0] + "\n…"


def trouver_joueur(nom: str, pseudos: dict[int, str]) -> int | None:
    """Un grimpeur par son pseudo : exact (sans majuscules ni accents), sinon le seul qui commence ou contient `nom`."""
    cible = plier(nom).strip()
    if not cible:
        return None
    for test in (lambda p: p == cible, lambda p: p.startswith(cible), lambda p: cible in p):
        trouves = [gid for gid, pseudo in pseudos.items() if test(plier(pseudo))]
        if len(trouves) == 1:
            return trouves[0]
        if trouves:
            return None  # plusieurs grimpeurs : trop ambigu pour répondre
    return None
