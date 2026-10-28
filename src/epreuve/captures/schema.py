"""Les colonnes retenues des tables Duffus du module E1 (relevé du 28/10/2026, docs/lots/E1.md).

Même principe que `duffus/schema.py` : une colonne exigée absente ou d'un mauvais type arrête l'aspiration
avant toute écriture, et les colonnes en plus sont ignorées. Les images (stockage Duffus) ne sont jamais
recopiées : de `archimonstres.image`, on ne garde que le chemin, qui porte l'identifiant du monstre.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Ligne(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class ArchimonstreDuffus(_Ligne):
    """Un archimonstre. `image` = « /images/archis/<id du monstre>_<nom>.png » ; `zone` = une ou plusieurs
    sous-zones séparées par « · » ; `etape` = l'étape de la quête du Dofus Ocre (texte « 25 »)."""

    id: int
    nom: str
    etape: str | None
    zone: str | None
    image: str | None


class BossOcre(_Ligne):
    """Un boss de la quête du Dofus Ocre (onglet « Boss » de Duffus)."""

    id: int
    nom: str
    etape: int | None


class Avis(_Ligne):
    """Un avis de recherche. `lvl` est un texte (« Niv. > 9 ») ; `recompense` un nombre en texte ;
    `chasse` l'identifiant d'objet de la chasse au trésor légendaire, s'il y en a une."""

    id: int
    slug: str
    nom: str
    lvl: str | None
    zone: str | None
    milice: str | None
    recompense: str | None
    recompense_type: str | None
    chasse: str | None
    dofus_monster_id: str | None
    resume_html: str | None


class MonstreNiveaux(_Ligne):
    """Un monstre réduit à son nom, sa race, son apparence (gfxid → icône DofusDB) et les niveaux de ses
    grades (`n0` à `n7`, lus par chemin JSON : `grades_json` entier pèse ~13 ko par monstre)."""

    id: int
    name: str
    race: int | None
    gfxid: int | None
    n0: int | None = None
    n1: int | None = None
    n2: int | None = None
    n3: int | None = None
    n4: int | None = None
    n5: int | None = None
    n6: int | None = None
    n7: int | None = None


class MonstreGrades(_Ligne):
    """Le monstre d'un avis de recherche, avec ses grades complets (réduits à l'écriture, voir aspirer.py)."""

    id: int
    name: str
    gfxid: int | None
    grades_json: list[dict[str, Any]]


class Race(_Ligne):
    id: int
    name: str


class SousZone(_Ligne):
    id: int
    name: str
    areaid: int | None


class SousZoneMonstres(_Ligne):
    """Les monstres d'une sous-zone : lus seulement pour les noms de sous-zone ambigus (plusieurs aires)."""

    id: int
    monsters_json: list[Any] | None


class Aire(_Ligne):
    id: int
    name: str
