"""Les métiers de Dofus 3 et le recensement de la guilde (demande de BillyBarkMan, 15/11).

Chaque grimpeur déclare ses métiers et leur niveau sur son tableau de bord ; la page « Métiers » liste, pour un
métier et un niveau minimum, qui peut fabriquer (« un bijoutier 25 pour un anneau Bouftou ? »). La liste suit les
métiers de DofusDB (`/jobs`), sans « Base ». Un niveau vide ou à 0 veut dire « pas ce métier ».
"""

from __future__ import annotations

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
