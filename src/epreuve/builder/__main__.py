"""python -m epreuve.builder aspirer : relit les objets et panoplies de Duffus vers donnees/duffus/builder/.

Lancé à la main, jamais automatiquement (même règle que `python -m epreuve.duffus`).
"""

from __future__ import annotations

import asyncio
import sys

from epreuve.builder.catalogue import DOSSIER
from epreuve.duffus.__main__ import RACINE, _charger_env
from epreuve.duffus.client import ClientDuffus, ErreurDuffus, lire_environnement


async def _principal() -> int:
    from epreuve.builder.aspirer import aspirer

    url, cle = lire_environnement()
    async with ClientDuffus(url, cle) as client:
        n_objets, n_panoplies = await aspirer(client, DOSSIER)
        print(f"{n_objets} objets, {n_panoplies} panoplies → {DOSSIER.relative_to(RACINE)} "
              f"({client.nb_requetes} requêtes)")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["aspirer"]:
        print("usage : python -m epreuve.builder aspirer", file=sys.stderr)
        return 2
    _charger_env(RACINE / ".env")
    try:
        return asyncio.run(_principal())
    except ErreurDuffus as e:
        print(f"Arrêt : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
