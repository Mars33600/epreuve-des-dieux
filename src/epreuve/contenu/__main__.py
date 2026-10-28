"""python -m epreuve.contenu construire --etage N [--aspiration AAAA-MM-JJ] [--manuel] [--sans-reseau]
                                        [--a-blanc] [--forcer]

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
    completer_par_dofusdb,
    construire,
    derniere_aspiration,
    guides_par_dofus,
    guides_repli_vers_duffus,
    lire_config_etages,
    lire_dofus_retenus,
)
from epreuve.contenu.ecrire import EcritureRefusee, ecrire_etage
from epreuve.contenu.manuel import construire_manuel, lire_etage_manuel
from epreuve.dofusdb.client import ClientDofusDB
from epreuve.dofusdb.repli import ClientEnCache, guides_repli


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


async def _preparer(args: argparse.Namespace, url: str, client: ClientEnCache):
    forcees, ouvertes = (await _forcees_et_ouvertes(url, args.etage)) if url and not args.a_blanc else ({}, {})
    retenus = lire_dofus_retenus()
    if args.manuel:
        m = lire_etage_manuel(RACINE / "config" / "etages-manuels" / f"etage-{args.etage}.yaml")
        return "saisie manuelle", await construire_manuel(m, client, retenus, forcees)
    dossier = RACINE / "donnees" / "duffus" / args.aspiration if args.aspiration else derniere_aspiration()
    aspi = Aspiration.lire(dossier)
    sans_guide = {d for d in retenus if d not in guides_par_dofus(aspi)}
    repli = guides_repli_vers_duffus(await guides_repli(client, sans_guide), aspi) if sans_guide else {}
    e = construire(args.etage, aspi, lire_config_etages(), retenus, forcees, ouvertes, forcer=args.forcer,
                   guides_repli=repli)
    return f"aspiration {dossier.name}", await completer_par_dofusdb(e, client)


async def _principal(args: argparse.Namespace) -> int:
    url = os.environ.get("DATABASE_URL", "")
    async with ClientDofusDB() as reseau:
        client = ClientEnCache(None if args.sans_reseau else reseau, RACINE / "donnees" / "dofusdb")
        source, e = await _preparer(args, url, client)
    print(f"Source : {source}\n{e.rapport()}")
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
    c.add_argument("--manuel", action="store_true", help="repli : config/etages-manuels/etage-N.yaml + DofusDB")
    c.add_argument("--sans-reseau", action="store_true", help="DofusDB : n'utiliser que le cache donnees/dofusdb")
    args = p.parse_args(argv)
    try:
        return asyncio.run(_principal(args))
    except (ConfigInvalide, ConstructionArretee, EcritureRefusee, LookupError) as e:
        print(f"Arrêt : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
