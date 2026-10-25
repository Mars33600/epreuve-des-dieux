"""Qui a le droit d'utiliser les commandes admin.

Deux protections (ARCHITECTURE §9) :
1. Discord masque les commandes admin à ceux qui n'ont pas « Gérer le serveur »
   (`default_permissions` dans les commandes), réglage modifiable dans le serveur ;
2. le code revérifie à CHAQUE commande, ici. Le masquage seul ne suffit pas.
"""

from __future__ import annotations

from typing import Protocol

REPONSE_REFUS = "Réservé aux admins"


class _Role(Protocol):
    id: int


class _Permissions(Protocol):
    manage_guild: bool


class _Membre(Protocol):
    roles: list[_Role]
    guild_permissions: _Permissions


def est_admin(membre: object, admin_role_id: int) -> bool:
    """Vrai si le membre a le rôle admin configuré, ou la permission « Gérer le serveur ».

    Un `discord.User` (message privé, hors serveur) n'a ni rôles ni permissions : refusé.
    """
    roles = getattr(membre, "roles", None)
    permissions = getattr(membre, "guild_permissions", None)
    if roles is None or permissions is None:
        return False
    return any(r.id == admin_role_id for r in roles) or bool(permissions.manage_guild)
