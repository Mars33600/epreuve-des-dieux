"""python -m epreuve.contenu construire --etage N [--aspiration AAAA-MM-JJ] [--a-blanc] [--forcer]

Construit l'étage N depuis la dernière aspiration Duffus (ou celle demandée), sans réseau, puis l'écrit
dans la base de DATABASE_URL. `--a-blanc` affiche le rapport sans toucher à la base.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from epreuve.contenu.construire import (
    RACINE,
    Aspiration,
    ConfigInvalide,
    ConstructionArretee,
    construire,
    derniere_aspiration,
    lire_config_etages,
    lire_dofus_retenus,
)
from epreuve.contenu.ecrire import EcritureRefusee, ecrire_etage


async def _forcees_et_ouvertes(url: str, numero: int) -> tuple[dict[str, str], dict[str, str]]:
    """Les natures forcées par un admin sur cet étage, et l'adresse de nos fiches des étages visibles."""
    from epreuve.db import tables as t
    from epreuve.db.session import creer_moteur

    moteur = creer_moteur(url)
    try:
        async with moteur.connect() as c:
            forcees = {r.duffus_id: r.nature for r in await c.execute(
                select(t.quete.c.duffus_id, t.quete.c.nature).join(t.etage)
                .where(t.etage.c.numero == numero, t.quete.c.nature_origine == "admin"))}
            # Les liens internes d'une fiche visent une quête par son slug Duffus, qu'on ne garde pas en base :
            # au lot B, seuls les prérequis (résolus à la lecture) sont des liens ; les autres sont retirés.
            return forcees, {}
    finally:
        await moteur.dispose()


async def _principal(args: argparse.Namespace) -> int:
    dossier = RACINE / "donnees" / "duffus" / args.aspiration if args.aspiration else derniere_aspiration()
    url = os.environ.get("DATABASE_URL", "")
    forcees, ouvertes = (await _forcees_et_ouvertes(url, args.etage)) if url and not args.a_blanc else ({}, {})
    e = construire(args.etage, Aspiration.lire(dossier), lire_config_etages(), lire_dofus_retenus(), forcees,
                   ouvertes, forcer=args.forcer)
    print(f"Aspiration {dossier.name}\n{e.rapport()}")
    if args.a_blanc:
        print("Rien n'a été écrit (--a-blanc).")
        return 0
    if not url:
        raise ConfigInvalide("DATABASE_URL n'est pas défini")
    from epreuve.db.session import creer_moteur

    moteur = creer_moteur(url)
    try:
        print((await ecrire_etage(moteur, e, datetime.now(UTC), forcer=args.forcer)).texte())
    finally:
        await moteur.dispose()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m epreuve.contenu")
    sous = p.add_subparsers(dest="commande", required=True)
    c = sous.add_parser("construire", help="construire un étage depuis l'aspiration Duffus")
    c.add_argument("--etage", type=int, required=True)
    c.add_argument("--aspiration", help="dossier AAAA-MM-JJ de donnees/duffus (défaut : la plus récente)")
    c.add_argument("--a-blanc", action="store_true")
    c.add_argument("--forcer", action="store_true", help="passer outre le seuil de 5 % et le garde-fou de 10 %")
    args = p.parse_args(argv)
    try:
        return asyncio.run(_principal(args))
    except (ConfigInvalide, ConstructionArretee, EcritureRefusee) as e:
        print(f"Arrêt : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
