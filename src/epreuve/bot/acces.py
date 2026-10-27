"""Qui a le droit d'utiliser les commandes admin.

Shadoaze (Q6) : les admins sont les membres du rôle « Administrateur ». On accepte aussi la
permission Discord « Administrateur » (le propriétaire du serveur, par exemple). « Gérer le serveur »
ne suffit pas.

Deux protections (ARCHITECTURE §9) :
1. Discord masque les commandes admin à ceux qui n'ont pas la permission Administrateur
   (`default_permissions` dans les commandes), réglage modifiable dans le serveur ;
2. le code revérifie à CHAQUE commande, ici. Le masquage seul ne suffit pas.
"""

from __future__ import annotations

REPONSE_REFUS = "Réservé aux admins"


def est_admin(membre: object, admin_role_id: int) -> bool:
    """Vrai si le membre a le rôle admin configuré, ou la permission Discord « Administrateur ».

    Un `discord.User` (message privé, hors serveur) n'a ni rôles ni permissions : refusé.
    """
    roles = getattr(membre, "roles", None)
    permissions = getattr(membre, "guild_permissions", None)
    if roles is None or permissions is None:
        return False
    return any(r.id == admin_role_id for r in roles) or bool(getattr(permissions, "administrator", False))
