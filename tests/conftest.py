"""Fixtures partagées.

Base de test : un Postgres jetable, par défaut celui lancé par
    docker run -d --rm --name epreuve-pg-test -p 54329:5432 \
        -e POSTGRES_PASSWORD=test -e POSTGRES_DB=epreuve_test postgres:17-alpine
(ou l'adresse donnée par TEST_DATABASE_URL). Si la base est injoignable, les tests marqués `db`
sont sautés avec un message : le reste de la suite tourne quand même.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from epreuve.db.depot import Depot
from epreuve.db.session import creer_moteur

RACINE = Path(__file__).resolve().parent.parent
DONNEES = Path(__file__).parent / "donnees"
URL_TEST = os.environ.get("TEST_DATABASE_URL",
                          "postgresql+asyncpg://postgres:test@localhost:54329/epreuve_test")


# --- DofusDB : réponses enregistrées, sans réseau ------------------------------------------------


def transport_dofusdb(appels: list[str] | None = None) -> httpx.MockTransport:
    """Remplace api.dofusdb.fr par les fichiers de tests/donnees/dofusdb/. Note chaque chemin appelé."""
    fichiers = {
        "/dungeons/": "dungeon-{}.json",
        "/achievements/": "achievement-{}.json",
        "/quest-categories/": "quest-category-{}.json",
    }

    def repondre(requete: httpx.Request) -> httpx.Response:
        chemin = requete.url.path
        if appels is not None:
            appels.append(chemin)
        for prefixe, modele in fichiers.items():
            if chemin.startswith(prefixe):
                f = DONNEES / "dofusdb" / modele.format(chemin.removeprefix(prefixe))
                if f.exists():
                    return httpx.Response(200, json=json.loads(f.read_text(encoding="utf-8")))
        return httpx.Response(404, json={"message": "absent des réponses enregistrées"})

    return httpx.MockTransport(repondre)


# --- Postgres ------------------------------------------------------------------------------------


def _base_joignable() -> bool:
    async def essayer() -> bool:
        moteur = creer_moteur(URL_TEST)
        try:
            async with asyncio.timeout(3):
                async with moteur.connect() as c:
                    await c.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001
            return False
        finally:
            await moteur.dispose()

    return asyncio.run(essayer())


def alembic(*args: str) -> subprocess.CompletedProcess:
    """Lance Alembic dans un processus à part, comme on le ferait à la main."""
    env = {**os.environ, "DATABASE_URL": URL_TEST}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=RACINE, env=env,
                          capture_output=True, text=True, check=False)


async def _repartir_de_zero() -> None:
    """Supprime le schéma `epreuve` : la migration 0001 a été réécrite au lot B, une base de test plus
    ancienne serait sinon vue « à jour » par Alembic avec l'ancien schéma."""
    moteur = creer_moteur(URL_TEST)
    try:
        async with moteur.begin() as c:
            await c.execute(text("DROP SCHEMA IF EXISTS epreuve CASCADE"))
    finally:
        await moteur.dispose()


@pytest.fixture(scope="session")
def url_base() -> str:
    if not _base_joignable():
        pytest.skip(f"Postgres de test injoignable ({URL_TEST}) : voir tests/conftest.py")
    asyncio.run(_repartir_de_zero())
    resultat = alembic("upgrade", "head")
    assert resultat.returncode == 0, resultat.stderr
    return URL_TEST


@pytest.fixture(scope="session")
async def moteur(url_base):
    m = creer_moteur(url_base)
    yield m
    await m.dispose()


TABLES_A_VIDER = ("journal", "session", "bilan_etage", "coche_quete", "coche_case", "grimpeur", "liste_officielle",
                  "fiche_quete", "quete", "case_succes", "donjon", "donjon_disponible", "etage")


@pytest.fixture
async def depot(moteur) -> Depot:
    """Un dépôt sur une base vidée (les identifiants repartent de 1)."""
    async with moteur.begin() as c:
        await c.execute(text("TRUNCATE " + ", ".join(f"epreuve.{t}" for t in TABLES_A_VIDER)
                             + " RESTART IDENTITY CASCADE"))
    return Depot(moteur)


def pytest_collection_modifyitems(items):
    # Tout test qui utilise la base reçoit le marqueur `db` (pour `pytest -m "not db"`).
    for item in items:
        if {"url_base", "moteur", "depot"} & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.db)
