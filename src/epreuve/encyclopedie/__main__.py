"""python -m epreuve.encyclopedie charger [--dossier DOSSIER]

Charge les extraits `donnees/duffus/encyclopedie/*.jsonl` (aspirés par `python -m epreuve.duffus
encyclopedie`) dans la base de DATABASE_URL, en une transaction. Aucun réseau.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from epreuve.encyclopedie.charger import DOSSIER, ExtraitManquant, charger


async def _principal(url: str, dossier: Path) -> int:
    from epreuve.db.session import creer_moteur

    moteur = creer_moteur(url)
    try:
        print((await charger(moteur, dossier)).texte())
    finally:
        await moteur.dispose()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m epreuve.encyclopedie")
    sous = p.add_subparsers(dest="commande", required=True)
    c = sous.add_parser("charger", help="charger les extraits de l'encyclopédie dans la base")
    c.add_argument("--dossier", type=Path, default=DOSSIER)
    args = p.parse_args(argv)
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("Arrêt : DATABASE_URL n'est pas défini", file=sys.stderr)
        return 1
    try:
        return asyncio.run(_principal(url, args.dossier))
    except ExtraitManquant as e:
        print(f"Arrêt : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
