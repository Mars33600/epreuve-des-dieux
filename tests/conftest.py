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


@pytest.fixture(scope="session")
def url_base() -> str:
    if not _base_joignable():
        pytest.skip(f"Postgres de test injoignable ({URL_TEST}) : voir tests/conftest.py")
    resultat = alembic("upgrade", "head")
    assert resultat.returncode == 0, resultat.stderr
    return URL_TEST


@pytest.fixture(scope="session")
async def moteur(url_base):
    m = creer_moteur(url_base)
    yield m
    await m.dispose()


@pytest.fixture
async def depot(moteur) -> Depot:
    """Un dépôt sur une base vidée (les identifiants repartent de 1)."""
    async with moteur.begin() as c:
        await c.execute(text(
            "TRUNCATE epreuve.journal, epreuve.validation, epreuve.preuve, epreuve.grimpeur, "
            "epreuve.palier_contenu, epreuve.contenu, epreuve.palier, epreuve.etage RESTART IDENTITY CASCADE"
        ))
    return Depot(moteur)


@pytest.fixture
async def etage0(depot, moteur) -> Depot:
    """Le dépôt, avec l'étage 0 importé depuis etage-0.yaml et les réponses DofusDB enregistrées."""
    import yaml

    from epreuve.dofusdb.client import ClientDofusDB
    from epreuve.dofusdb.import_etage import developper_etage, ecrire_etage

    config = yaml.safe_load((RACINE / "config/etages/etage-0.yaml").read_text(encoding="utf-8"))
    async with ClientDofusDB(transport=transport_dofusdb()) as client:
        prepare = await developper_etage(config, client)
    await ecrire_etage(moteur, prepare)
    return depot


def pytest_collection_modifyitems(items):
    # Tout test qui utilise la base reçoit le marqueur `db` (pour `pytest -m "not db"`).
    for item in items:
        if {"url_base", "moteur", "depot", "etage0"} & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.db)
