"""Les colonnes utiles des tables de Duffus, relevées le 28/10/2026 (donnees/duffus/schema-2026-10-28.json).

Chaque modèle ne retient que les colonnes dont on a besoin (addendum B0 de docs/LOTS.md). Une colonne exigée
absente ou d'un mauvais type arrête l'aspiration avant toute écriture : c'est le signal que l'auteur a changé
son schéma et qu'il faut refaire le relevé. Les colonnes en plus sont ignorées (on ne les recopie pas).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Ligne(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class GuideRange(_Ligne):
    """Une tranche du guide (« 1 - 20 »). `categories` = les blocs, avec leurs éléments dans l'ordre du guide :
    {"title", "description", "items": [{"type": "quest" | "monster_success" | "tip", "id", "text"?}]}."""

    id: int
    order_index: int
    range_key: str
    label: str
    title: str
    is_active: bool
    dungeon_count: int | None = None
    categories: list[dict[str, Any]]


class QuestListe(_Ligne):
    """Une entrée du guide. `quest_ornot` vrai = une vraie quête ; sinon un rappel (« Lancez la quête … »).
    `is_dungeon` + `dungeons` (url /donjon/<slug>) = l'entrée fait passer par un donjon."""

    id: int
    title: str
    url: str | None
    level: str | None
    category: str | None
    Order: float | None
    quest_ornot: bool | None
    own_page: bool | None
    zone: str | None
    pnj: str | None
    pos: str | None
    note: str | None
    note2: str | None
    succes: list[str] | None
    is_dungeon: bool | None
    dungeon_info: str | None
    dungeons: list[dict[str, Any]] | None
    dofus_id: int | None = None  # renseigné sur l'entrée qui fait obtenir un Dofus (dofus_list.id)
    lancement: str | None = None  # comment lancer la quête (« Parlez à … : "Accepter" »)


class QuestePrerequis(_Ligne):
    """La partie légère d'une fiche, lue pour TOUTES les quêtes : de quoi suivre les chaînes vers les Dofus."""

    id: str
    slug: str
    prereq_quests: str | None  # JSON en texte : [{"title", "link": "/quete/<slug>", …}]


class QuestQuick(_Ligne):
    """Les « infos rapides » d'une fiche (nombre de combats, farm, donjons…), lues pour toutes les quêtes."""

    id: str
    slug: str
    quick: str | None  # JSON en texte : {"solo", "group", "songes", "tactic", "alea", "tiles", "farm", "dungeons", …}


class QuestePage(_Ligne):
    """La fiche complète d'une quête (lue pour les étages demandés seulement)."""

    id: str
    slug: str
    published: bool | None
    status: str | None
    meta: dict[str, Any]
    prereqs: list[Any] | None  # objets {"text", "icon"} ou simples textes
    prereq_quests: str | None
    rewards: dict[str, Any] | None
    manual_resources: list[Any] | None
    steps: list[Any] | None
    content_html: str | None


class DonjonPage(_Ligne):
    """Un donjon. `successes` = {"challenge1": {"name"}, "challenge2": {"name"}, "special": {"name", "rule"}}."""

    id: int
    slug: str
    published: bool | None
    meta: dict[str, Any]
    successes: dict[str, Any] | None
    linked_quests: list[dict[str, Any]] | None


class Succes(_Ligne):
    """Un succès du jeu, recopié par Duffus. On ne garde que ceux des donjons (« … dans son donjon … »)."""

    id: int
    name: str
    description: str | None
    category_id: int
    level: int | None
    order: int | None


class DofusListe(_Ligne):
    """Un Dofus et l'entrée du guide (`quest_id` → quest_list.id) qui le fait obtenir."""

    id: int
    nom: str
    quest_id: int | None
    advised_level: int | None


class GuidePage(_Ligne):
    """Un guide « par Dofus » (`type_guide = "dofus"`) ou d'événement. `categories` et `prerequis_categories`
    ont la même forme que les blocs de `guide_ranges` : leurs items `quest` désignent des `quest_list.id`."""

    id: str
    slug: str
    title: str
    type_guide: str | None
    item: int | None
    published: bool | None
    categories: list[dict[str, Any]] | None
    prerequis_categories: list[dict[str, Any]] | None


class QuestRessource(_Ligne):
    """Une ressource à prévoir pour une quête (`quest_id` → quest_list.id)."""

    id: int
    quest_id: int | None
    name: str | None
    qty: int | None


# Les clés de `dungeon_pages.meta` qu'on recopie (pas les images, qui pointent vers le stockage de Duffus).
META_DONJON = ("title", "bossName", "level", "zone", "coords", "dofusMonsterId")
META_QUETE = ("title", "level", "zone", "startNpc", "startCoords", "repeatable")
# Un succès de donjon dit « Vaincre X dans son donjon » : seuls ceux-là sont recopiés.
MARQUE_SUCCES_DONJON = "dans son donjon"
