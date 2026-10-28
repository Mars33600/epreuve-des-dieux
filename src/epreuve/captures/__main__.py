"""python -m epreuve.captures aspirer | charger [--dossier donnees/duffus/AAAA-MM-JJ]

- `aspirer` lit les tables Duffus du module E1 (environ 10 requêtes, 1 par seconde au plus, lecture seule)
  et écrit donnees/duffus/<aujourd'hui>/ ; l'adresse et la clé viennent de l'environnement ou de `.env` ;
- `charger` construit le catalogue depuis la dernière aspiration (ou `--dossier`) et l'écrit en base
  (DATABASE_URL) : rejouable, il met à jour sans rien supprimer, et retire de l'affichage ce que Duffus
  n'a plus. Les captures des grimpeurs ne sont jamais touchées.

Lancé à la main par un admin, jamais automatiquement.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from epreuve.captures.catalogue import construire, derniere_aspiration, lire_dossier
from epreuve.duffus.__main__ import DONNEES, RACINE, _charger_env
from epreuve.duffus.client import ClientDuffus, ErreurDuffus, lire_environnement


async def _aspirer() -> int:
    from epreuve.captures.aspirer import aspirer

    url, cle = lire_environnement()
    async with ClientDuffus(url, cle) as client:
        rapport = await aspirer(client, DONNEES, date.today())
    print(rapport.texte())
    return 0


async def _charger(dossier: Path | None) -> int:
    from epreuve.captures.depot import DepotCaptures
    from epreuve.db.session import creer_moteur

    dossier = dossier or derniere_aspiration(DONNEES)
    if dossier is None:
        print("Aucune aspiration E1 dans donnees/duffus/ : lancer d'abord « aspirer ».", file=sys.stderr)
        return 1
    catalogue = construire(lire_dossier(dossier))
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL n'est pas défini.", file=sys.stderr)
        return 1
    moteur = creer_moteur(url)
    try:
        comptes = await DepotCaptures(moteur).charger_catalogue(catalogue, datetime.now(UTC))
    finally:
        await moteur.dispose()
    print(f"Catalogue chargé depuis {dossier.name} : " + ", ".join(f"{k} {v}" for k, v in comptes.items()))
    for a in catalogue.alertes:
        print(f"  alerte : {a}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m epreuve.captures")
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("aspirer", help="aspirer les tables Duffus du module E1")
    c = sous.add_parser("charger", help="écrire le catalogue en base depuis une aspiration")
    c.add_argument("--dossier", type=Path, help="dossier d'aspiration (par défaut : le plus récent)")
    args = p.parse_args(argv)
    _charger_env(RACINE / ".env")
    try:
        if args.commande == "aspirer":
            return asyncio.run(_aspirer())
        return asyncio.run(_charger(args.dossier))
    except ErreurDuffus as e:
        print(f"Arrêt : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
