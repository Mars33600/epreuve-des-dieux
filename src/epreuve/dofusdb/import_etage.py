"""Import d'un étage : fichier YAML → DofusDB → base.

    python -m epreuve.dofusdb.import_etage config/etages/etage-0.yaml [--a-blanc]

Deux étapes bien séparées :
1. `developper_etage` lit le YAML et développe les raccourcis grâce à DofusDB
   (par exemple `dofusdb_succes_du_donjon: 90` devient les 5 succès du donjon) ;
2. `ecrire_etage` écrit le résultat en base. L'écriture est rejouable : relancée, elle met à jour
   au lieu de dupliquer.

`--a-blanc` s'arrête après l'étape 1 et affiche ce qui serait écrit, sans toucher à la base.

Le fichier doit décrire exactement les paliers 1, 2 et 3, chacun avec au moins un contenu
(SPEC §8 bis, f) : sinon un Collectionneur ne pourrait jamais atteindre ses 3 points.

Le statut de l'étage (scellé, ouvert, terminé) n'est fixé qu'à la création : l'étage 0 est créé
ouvert, les suivants scellés (ils s'ouvriront par `/etage ouvrir`, au jalon lancement).
Un nouvel import ne change jamais ce statut.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from epreuve.db import tables as t
from epreuve.db.session import creer_moteur
from epreuve.dofusdb.client import ClientDofusDB


class ConfigInvalide(ValueError):
    """Le fichier YAML ne décrit pas un étage utilisable."""


@dataclass
class ContenuPrepare:
    type: str
    nom: str
    nom_court: str
    dofusdb_type: str
    dofusdb_id: int
    dofusdb_ids_couverts: list[int] | None = None

    @property
    def cle(self) -> tuple[str, int]:
        """Ce qui identifie un contenu d'un import à l'autre."""
        return (self.dofusdb_type, self.dofusdb_id)


@dataclass
class PalierPrepare:
    rang: int
    libelle: str
    contenus: list[tuple[str, int]] = field(default_factory=list)  # clés des contenus


@dataclass
class EtagePrepare:
    numero: int
    nom: str
    level_cap: int
    seuil_pourcent: int
    ouvert_le: datetime | None
    date_plancher_suivant: datetime | None
    zone_quetes: str
    donjons_affiches: list[str]
    paliers: list[PalierPrepare]
    contenus: dict[tuple[str, int], ContenuPrepare]  # un contenu partagé par 2 paliers n'est créé qu'une fois


def _date(valeur) -> datetime | None:
    """PyYAML lit déjà `2026-10-30T17:00:00+01:00` comme un datetime ; on exige le fuseau."""
    if valeur is None:
        return None
    d = valeur if isinstance(valeur, datetime) else datetime.fromisoformat(str(valeur))
    if d.tzinfo is None:
        raise ConfigInvalide(f"date sans fuseau horaire : {valeur!r} (ajoute par exemple +01:00)")
    return d


def _verifier_paliers(config: dict) -> list[dict]:
    paliers = config.get("paliers") or []
    rangs = sorted(int(p.get("rang", 0)) for p in paliers)
    if rangs != [1, 2, 3]:
        raise ConfigInvalide(f"il faut exactement les paliers de rang 1, 2 et 3 (trouvés : {rangs})")
    for p in paliers:
        if not p.get("contenus"):
            raise ConfigInvalide(f"le palier {p['rang']} « {p.get('libelle', '')} » n'a aucun contenu")
    return sorted(paliers, key=lambda p: int(p["rang"]))


async def developper_etage(config: dict, client: ClientDofusDB) -> EtagePrepare:
    paliers_cfg = _verifier_paliers(config)
    pourcent = int(config.get("seuil_pourcent", 75))
    if not 1 <= pourcent <= 100:
        raise ConfigInvalide(f"seuil_pourcent doit être entre 1 et 100 (trouvé : {pourcent})")

    contenus: dict[tuple[str, int], ContenuPrepare] = {}
    paliers: list[PalierPrepare] = []

    def ajouter(c: ContenuPrepare, palier: PalierPrepare, nom_court: str | None) -> None:
        if c.cle not in contenus:
            contenus[c.cle] = c
        if nom_court:  # un nom court donné dans le YAML l'emporte (ex. « Kardorim vaincu »)
            contenus[c.cle].nom_court = nom_court
        if c.cle not in palier.contenus:
            palier.contenus.append(c.cle)

    for cfg in paliers_cfg:
        palier = PalierPrepare(int(cfg["rang"]), cfg["libelle"])
        for raccourci in cfg["contenus"]:
            nom_court = raccourci.get("nom_court")
            if "dofusdb_achievement" in raccourci:
                s = await client.succes(int(raccourci["dofusdb_achievement"]))
                ajouter(ContenuPrepare("succes", s["name"]["fr"], s["name"]["fr"], "achievement", s["id"]),
                        palier, nom_court)
            elif "dofusdb_succes_du_donjon" in raccourci:
                # On part de l'objet donjon, pas d'une recherche par nom : ça écarte les succès
                # Temporis qui portent le même nom mais ne sont pas dans `achievements`.
                donjon = await client.donjon(int(raccourci["dofusdb_succes_du_donjon"]))
                for id_succes in donjon["achievements"]:
                    s = await client.succes(id_succes)
                    ajouter(ContenuPrepare("succes", s["name"]["fr"], s["name"]["fr"], "achievement", s["id"]),
                            palier, None)
            elif "dofusdb_categorie_quetes" in raccourci:
                cat = await client.categorie_quetes(int(raccourci["dofusdb_categorie_quetes"]))
                quetes = list(cat["questIds"])
                lot = raccourci.get("lot_quetes") or f"Toutes les quêtes de {cat['name']['fr']}"
                ajouter(ContenuPrepare("lot_quetes", f"{lot} ({len(quetes)})", lot, "quest_category",
                                       cat["id"], quetes), palier, nom_court)
            else:
                raise ConfigInvalide(f"raccourci de contenu inconnu au palier {palier.rang} : {raccourci}")
        paliers.append(palier)

    return EtagePrepare(
        numero=int(config["numero"]), nom=config["nom"], level_cap=int(config["level_cap"]),
        seuil_pourcent=pourcent, ouvert_le=_date(config.get("ouvert_le")),
        date_plancher_suivant=_date(config.get("date_plancher_suivant")),
        zone_quetes=config.get("zone_quetes", ""), donjons_affiches=list(config.get("donjons_affiches", [])),
        paliers=paliers, contenus=contenus,
    )  # fmt: skip


def decrire(e: EtagePrepare) -> str:
    """Ce qui serait écrit, lisible par un humain (mode --a-blanc)."""
    lignes = [f"Étage {e.numero} · {e.nom} — cap {e.level_cap}, seuil {e.seuil_pourcent} %, quêtes : {e.zone_quetes}",
              f"  ouverture {e.ouvert_le}, date plancher {e.date_plancher_suivant}",
              f"  {len(e.contenus)} contenus :"]
    for c in e.contenus.values():
        couverts = f", {len(c.dofusdb_ids_couverts)} quêtes" if c.dofusdb_ids_couverts else ""
        lignes.append(f"    - [{c.dofusdb_type} {c.dofusdb_id}] {c.nom_court} ({c.type}{couverts})")
    for p in e.paliers:
        noms = ", ".join(e.contenus[cle].nom_court for cle in p.contenus)
        lignes.append(f"  palier {p.rang} « {p.libelle} » : {noms}")
    return "\n".join(lignes)


async def ecrire_etage(moteur: AsyncEngine, e: EtagePrepare) -> int:
    """Écrit (ou met à jour) l'étage, ses contenus et ses paliers. Renvoie l'id de l'étage."""
    async with moteur.begin() as c:
        champs = dict(nom=e.nom, level_cap=e.level_cap, seuil_pourcent=e.seuil_pourcent, ouvert_le=e.ouvert_le,
                      date_plancher_suivant=e.date_plancher_suivant, zone_quetes=e.zone_quetes,
                      donjons_affiches=e.donjons_affiches)
        etage_id = (await c.execute(select(t.etage.c.id).where(t.etage.c.numero == e.numero))).scalar()
        if etage_id is None:
            statut = "ouvert" if e.numero == 0 else "scelle"
            etage_id = (await c.execute(
                insert(t.etage).values(numero=e.numero, statut=statut, **champs).returning(t.etage.c.id)
            )).scalar_one()  # fmt: skip
        else:
            await c.execute(update(t.etage).where(t.etage.c.id == etage_id).values(**champs))

        ids_contenus: dict[tuple[str, int], int] = {}
        for cle, ct in e.contenus.items():
            valeurs = dict(type=ct.type, nom=ct.nom, nom_court=ct.nom_court,
                           dofusdb_ids_couverts=ct.dofusdb_ids_couverts)
            existant = (await c.execute(select(t.contenu.c.id).where(
                t.contenu.c.etage_id == etage_id, t.contenu.c.dofusdb_type == ct.dofusdb_type,
                t.contenu.c.dofusdb_id == ct.dofusdb_id,
            ))).scalar()  # fmt: skip
            if existant is None:
                existant = (await c.execute(insert(t.contenu).values(
                    etage_id=etage_id, dofusdb_type=ct.dofusdb_type, dofusdb_id=ct.dofusdb_id, **valeurs
                ).returning(t.contenu.c.id))).scalar_one()  # fmt: skip
            else:
                await c.execute(update(t.contenu).where(t.contenu.c.id == existant).values(**valeurs))
            ids_contenus[cle] = existant

        for p in e.paliers:
            palier_id = (await c.execute(select(t.palier.c.id).where(
                t.palier.c.etage_id == etage_id, t.palier.c.rang == p.rang
            ))).scalar()  # fmt: skip
            if palier_id is None:
                palier_id = (await c.execute(insert(t.palier).values(
                    etage_id=etage_id, rang=p.rang, libelle=p.libelle
                ).returning(t.palier.c.id))).scalar_one()  # fmt: skip
            else:
                await c.execute(update(t.palier).where(t.palier.c.id == palier_id).values(libelle=p.libelle))
            # Les liens palier → contenus sont remplacés en bloc : le YAML fait foi.
            await c.execute(delete(t.palier_contenu).where(t.palier_contenu.c.palier_id == palier_id))
            await c.execute(insert(t.palier_contenu), [
                {"palier_id": palier_id, "contenu_id": ids_contenus[cle]} for cle in p.contenus
            ])  # fmt: skip
    return etage_id


async def importer(chemin: Path, a_blanc: bool, database_url: str | None,
                   client: ClientDofusDB | None = None) -> str:
    config = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    async with client or ClientDofusDB() as cl:
        prepare = await developper_etage(config, cl)
    rapport = decrire(prepare)
    if a_blanc:
        return rapport + "\n(à blanc : rien n'a été écrit)"
    if not database_url:
        raise SystemExit("DATABASE_URL n'est pas défini (voir .env.example)")
    moteur = creer_moteur(database_url)
    try:
        etage_id = await ecrire_etage(moteur, prepare)
    finally:
        await moteur.dispose()
    return rapport + f"\nÉcrit en base (étage id {etage_id})."


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Importe un étage depuis son fichier YAML et DofusDB.")
    parser.add_argument("fichier", type=Path)
    parser.add_argument("--a-blanc", action="store_true", help="affiche ce qui serait écrit, sans écrire")
    args = parser.parse_args(argv)
    print(asyncio.run(importer(args.fichier, args.a_blanc, os.environ.get("DATABASE_URL"))))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
