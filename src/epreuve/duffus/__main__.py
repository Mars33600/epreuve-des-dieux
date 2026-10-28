"""python -m epreuve.duffus releve | aspirer [--tables t1,t2] [--etages 0,1] [--a-blanc]

Lancé à la main par un admin, jamais automatiquement. L'adresse et la clé viennent de l'environnement
(DUFFUS_SUPABASE_URL, DUFFUS_SUPABASE_CLE), lues dans `.env` si elles n'y sont pas déjà.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

from epreuve.duffus.client import ClientDuffus, ErreurDuffus, lire_environnement

RACINE = Path(__file__).resolve().parents[3]
DONNEES = RACINE / "donnees" / "duffus"


def _charger_env(fichier: Path) -> None:
    """Lit les seules variables DUFFUS_* d'un fichier .env, sans jamais rien afficher."""
    if not fichier.exists():
        return
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        cle, egal, valeur = ligne.partition("=")
        if egal and cle.strip().startswith("DUFFUS_") and not os.environ.get(cle.strip()):
            os.environ[cle.strip()] = valeur.strip().strip("'\"")


async def _principal(args: argparse.Namespace) -> int:
    from epreuve.duffus import aspirer, releve

    url, cle = lire_environnement()
    async with ClientDuffus(url, cle) as client:
        if args.commande == "releve":
            tables = releve.TABLES_CONNUES + (releve.TABLES_LOT_E if args.lot_e else ())
            r = await releve.relever(client, tables)
            f = releve.ecrire_releve(r, DONNEES, date.today())
            print(f"Relevé ({r['source']}) : {len(r['tables'])} tables → {f.relative_to(RACINE)} "
                  f"({client.nb_requetes} requêtes)")
            return 0
        tables = tuple(args.tables.split(",")) if args.tables else None
        etages = tuple(int(x) for x in args.etages.split(",")) if args.etages else None
        rapport = await aspirer.aspirer(client, DONNEES, date.today(), tables=tables, etages=etages,
                                        a_blanc=args.a_blanc)
        print(rapport.texte())
        print(f"({client.nb_requetes} requêtes)")
        return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m epreuve.duffus")
    sous = p.add_subparsers(dest="commande", required=True)
    rel = sous.add_parser("releve", help="relever le schéma (tables, colonnes, nombre de lignes)")
    rel.add_argument("--lot-e", action="store_true", help="relever aussi les tables du lot E")
    a = sous.add_parser("aspirer", help="aspirer les tables utiles vers donnees/duffus/AAAA-MM-JJ/")
    a.add_argument("--tables", help="tables à aspirer (par défaut : toutes les tables utiles)")
    a.add_argument("--etages", help="limiter les fiches de quête aux tranches de ces étages, ex. 0,1")
    a.add_argument("--a-blanc", action="store_true", help="afficher le rapport sans rien écrire")
    args = p.parse_args(argv)
    _charger_env(RACINE / ".env")
    try:
        return asyncio.run(_principal(args))
    except ErreurDuffus as e:
        print(f"Arrêt : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
