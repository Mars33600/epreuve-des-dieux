"""Poster sur un webhook Discord : l'annonce d'un étage qui s'ouvre (demande de Shadoaze).

Un webhook de salon plutôt qu'un bot : une simple adresse à laquelle on POSTe un message, sans processus à
héberger ni jeton à protéger en permanence. L'envoi part APRÈS l'ouverture enregistrée, en tâche de fond :
un Discord lent ou en panne ne doit jamais retarder ni annuler une ouverture. D'où un délai court et une
fonction qui ne lève jamais : un échec est journalisé (sans l'adresse, qui est un secret), c'est tout.

Le transport httpx est injectable : les tests simulent Discord avec `httpx.MockTransport`, sans réseau.
"""

from __future__ import annotations

import logging

import httpx

journal = logging.getLogger("epreuve.discord.webhook")
DELAI = 5.0  # secondes : au-delà, Discord est en difficulté et on abandonne plutôt que d'occuper le serveur


async def poster_webhook(url: str, corps: dict, *, transport: httpx.AsyncBaseTransport | None = None,
                         delai: float = DELAI) -> bool:
    """POST `corps` sur le webhook. True si Discord l'a accepté ; False (journalisé) sinon. Ne lève jamais."""
    try:
        async with httpx.AsyncClient(transport=transport, timeout=delai) as client:
            r = await client.post(url, json=corps)
        if r.status_code >= 400:
            journal.warning("annonce Discord refusée : HTTP %s", r.status_code)
            return False
        return True
    except Exception as e:  # noqa: BLE001 — réseau, délai, adresse mal formée : rien ne doit remonter
        # `type(e).__name__` et non `e` : le message d'une erreur httpx contient l'adresse, donc le secret.
        journal.warning("annonce Discord non envoyée : %s", type(e).__name__)
        return False
