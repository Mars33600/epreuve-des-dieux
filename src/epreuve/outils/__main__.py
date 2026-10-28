"""python -m epreuve.outils aspirer : régénère les données des outils depuis Duffus (lecture seule)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from epreuve.duffus.__main__ import _charger_env
from epreuve.duffus.client import ClientDuffus, lire_environnement
from epreuve.outils import aspirer

RACINE = Path(__file__).resolve().parents[3]


async def _principal() -> int:
    _charger_env(RACINE / ".env")
    url, cle = lire_environnement()
    async with ClientDuffus(url, cle) as client:
        for f in await aspirer.aspirer(client):
            print(f"{f.name} : {f.stat().st_size // 1024} ko")
        print(f"({client.nb_requetes} requêtes)")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["aspirer"]:
        sys.exit("usage : python -m epreuve.outils aspirer")
    sys.exit(asyncio.run(_principal()))
