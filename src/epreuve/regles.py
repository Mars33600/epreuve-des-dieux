"""Lecture et validation de config/regles.yaml → `domaine.modeles.Regles` (SPEC §8.1, EX-109).

Changer une règle de jeu, c'est modifier ce fichier et redéployer, sans toucher au code. Une valeur inconnue
ou mal écrite arrête le démarrage avec un message clair : mieux vaut un site qui ne démarre pas qu'un palier
calculé avec une règle mal lue.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from epreuve.domaine.modeles import Regles

CHEMIN_PAR_DEFAUT = Path(__file__).resolve().parents[2] / "config" / "regles.yaml"


class ReglesInvalides(ValueError):
    pass


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Palier(_Section):
    points_par_joueur: Fraction = Fraction(2)
    categorie_vide: Literal["ignoree", "offerte"] = "ignoree"

    @field_validator("points_par_joueur", mode="before")
    @classmethod
    def _fraction(cls, v: object) -> Fraction:
        # « 2 », « 5/2 » ou « 2.5 » : Fraction(str(...)) est exacte (2.5 → 5/2), jamais un flottant arrondi.
        if isinstance(v, bool) or not isinstance(v, int | float | str):
            raise ValueError("un nombre (2) ou une fraction (« 5/2 ») est attendu")
        try:
            f = Fraction(str(v).strip())
        except (ValueError, ZeroDivisionError) as e:
            raise ValueError(f"nombre illisible : {v!r}") from e
        if f <= 0:
            raise ValueError("doit être strictement positif")
        return f


class _Coches(_Section):
    succes_coche_vaincu: bool = True
    pause_peut_cocher: bool = True


class _Inscription(_Section):
    liste_officielle_obligatoire: bool = True


class _Fiche(_Section):
    classe_obligatoire: bool = False
    afficher_nom_discord: bool = True


class _Modules(_Section):
    verrouiller_par_etage: bool = False


class _Fichier(_Section):
    palier: _Palier = _Palier()
    coches: _Coches = _Coches()
    inscription: _Inscription = _Inscription()
    fiche: _Fiche = _Fiche()
    modules: _Modules = _Modules()


def regles_depuis(donnees: object) -> Regles:
    """Valide un dictionnaire (le YAML lu) et le transforme en `Regles`. ReglesInvalides sinon."""
    try:
        f = _Fichier.model_validate(donnees or {})
    except ValidationError as e:
        lignes = [f"{'.'.join(str(x) for x in err['loc'])} : {err['msg']}" for err in e.errors()]
        raise ReglesInvalides("config/regles.yaml invalide :\n  " + "\n  ".join(lignes)) from None
    return Regles(
        points_par_joueur=f.palier.points_par_joueur,
        categorie_vide=f.palier.categorie_vide,
        succes_coche_vaincu=f.coches.succes_coche_vaincu,
        pause_peut_cocher=f.coches.pause_peut_cocher,
        classe_obligatoire=f.fiche.classe_obligatoire,
        afficher_nom_discord=f.fiche.afficher_nom_discord,
        liste_officielle_obligatoire=f.inscription.liste_officielle_obligatoire,
        verrouiller_modules_par_etage=f.modules.verrouiller_par_etage,
    )


def lire_regles(chemin: Path = CHEMIN_PAR_DEFAUT) -> Regles:
    """Fichier absent → règles par défaut ; fichier illisible ou invalide → ReglesInvalides."""
    if not chemin.exists():
        return Regles()
    try:
        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ReglesInvalides(f"{chemin.name} n'est pas un YAML valide : {e}") from None
    return regles_depuis(donnees)
