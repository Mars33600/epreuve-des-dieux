"""Client de lecture de la base Supabase de duffus.fr (ARCHITECTURE §6.2), poli par construction.

Les règles de politesse sont dans le code, pas laissées à la discipline de celui qui lance la commande :
- au plus 1 requête par seconde, une seule à la fois ;
- un User-Agent qui nous identifie ;
- arrêt immédiat sur 401, 403 ou 404 (accès refusé ou schéma changé : on n'insiste jamais) ;
- sur 429 ou 5xx, attente de `Retry-After` (30 s par défaut), 3 essais au plus.

On ne lit que ce que la clé publique « anon » du site permet déjà à n'importe quel visiteur. L'adresse et la
clé viennent de l'environnement (DUFFUS_SUPABASE_URL, DUFFUS_SUPABASE_CLE) et ne sont jamais affichées.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable

import httpx

USER_AGENT = ("EpreuveDesDieux-aspiration/1.0 (projet de fans non lucratif ; lecture polie et mise en cache ; "
              "https://epreuve-des-dieux.fr)")
INTERVALLE = 1.0  # secondes entre deux requêtes, au moins
ESSAIS = 3
ATTENTE_PAR_DEFAUT = 30.0
TAILLE_PAGE = 1000  # le maximum par défaut de PostgREST chez Supabase


class ErreurDuffus(Exception):
    """Arrêt de l'aspiration, avec un message à lire tel quel."""


class AccesRefuse(ErreurDuffus):
    """401 ou 403 : la clé est refusée."""


class Absente(ErreurDuffus):
    """404 : la table ou le chemin n'existe pas (ou plus)."""


def lire_environnement() -> tuple[str, str]:
    url = os.environ.get("DUFFUS_SUPABASE_URL", "").strip()
    cle = os.environ.get("DUFFUS_SUPABASE_CLE", "").strip()
    if not url or not cle:
        raise ErreurDuffus("DUFFUS_SUPABASE_URL et DUFFUS_SUPABASE_CLE doivent être définies (voir .env.example)")
    return url.rstrip("/"), cle


class ClientDuffus:
    def __init__(self, url: str, cle: str, transport: httpx.AsyncBaseTransport | None = None,
                 horloge: Callable[[], float] = time.monotonic,
                 dormir: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        # `transport`, `horloge` et `dormir` permettent aux tests de simuler le réseau et le temps.
        self._http = httpx.AsyncClient(
            base_url=f"{url.rstrip('/')}/rest/v1",
            headers={"apikey": cle, "Authorization": f"Bearer {cle}", "User-Agent": USER_AGENT},
            timeout=30, transport=transport,
        )  # fmt: skip
        self._horloge = horloge
        self._dormir = dormir
        self._derniere: float | None = None
        self._verrou = asyncio.Lock()
        self.nb_requetes = 0

    async def __aenter__(self) -> ClientDuffus:
        return self

    async def __aexit__(self, *exc) -> None:
        await self._http.aclose()

    async def _patienter(self, secondes: float) -> None:
        if secondes > 0:
            await self._dormir(secondes)

    async def _get(self, chemin: str, params: dict | None = None, entetes: dict | None = None) -> httpx.Response:
        async with self._verrou:  # une seule requête à la fois
            for essai in range(1, ESSAIS + 1):
                if self._derniere is not None:
                    await self._patienter(INTERVALLE - (self._horloge() - self._derniere))
                self._derniere = self._horloge()
                self.nb_requetes += 1
                r = await self._http.get(chemin, params=params, headers=entetes)
                if r.status_code in (401, 403):
                    raise AccesRefuse(f"accès refusé par Duffus ({r.status_code}) sur {chemin} : on s'arrête")
                if r.status_code == 404:
                    raise Absente(f"{chemin} introuvable (404) : le schéma de Duffus a changé, refaire le relevé")
                if r.status_code == 429 or r.status_code >= 500:
                    if essai == ESSAIS:
                        raise ErreurDuffus(f"Duffus répond {r.status_code} après {ESSAIS} essais sur {chemin}")
                    await self._patienter(_retry_after(r))
                    self._derniere = self._horloge()
                    continue
                if r.status_code >= 400:
                    raise ErreurDuffus(f"requête refusée ({r.status_code}) sur {chemin} : {r.text[:200]}")
                return r
        raise AssertionError("inatteignable")  # pragma: no cover

    async def openapi(self) -> dict | None:
        """La description OpenAPI de PostgREST (tables et colonnes visibles), ou None si elle est fermée."""
        try:
            r = await self._get("/", entetes={"Accept": "application/openapi+json"})
        except (AccesRefuse, Absente):
            return None
        try:
            donnees = r.json()
        except ValueError:
            return None
        return donnees if isinstance(donnees, dict) and donnees.get("definitions") else None

    async def une_ligne(self, table: str) -> list[dict]:
        return (await self._get(f"/{table}", params={"select": "*", "limit": "1"})).json()

    async def echantillon(self, table: str) -> tuple[dict | None, int | None]:
        """Une ligne et le nombre total de lignes (en-tête Content-Range de PostgREST), en une requête."""
        r = await self._get(f"/{table}", params={"select": "*", "limit": "1"}, entetes={"Prefer": "count=exact"})
        total = (r.headers.get("Content-Range") or "").rpartition("/")[2]
        lignes = r.json()
        return (lignes[0] if lignes else None), (int(total) if total.isdigit() else None)

    async def lire_table(self, table: str, colonnes: str = "*", ordre: str = "id",
                         filtres: dict[str, str] | None = None) -> list[dict]:
        """Toute la table, page par page (en-tête Range), triée par `ordre` pour un résultat stable."""
        lignes: list[dict] = []
        debut = 0
        while True:
            params = {"select": colonnes, "order": f"{ordre}.asc", **(filtres or {})}
            r = await self._get(f"/{table}", params=params,
                                entetes={"Range-Unit": "items", "Range": f"{debut}-{debut + TAILLE_PAGE - 1}"})
            page = r.json()
            lignes.extend(page)
            if len(page) < TAILLE_PAGE:
                return lignes
            debut += TAILLE_PAGE


def _retry_after(r: httpx.Response) -> float:
    try:
        return max(0.0, float(r.headers.get("Retry-After", ATTENTE_PAR_DEFAUT)))
    except ValueError:
        return ATTENTE_PAR_DEFAUT
