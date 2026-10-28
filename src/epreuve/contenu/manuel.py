"""Le plan de repli si Duffus résiste (LOTS, lot B) : un étage saisi à la main, complété par DofusDB.

`config/etages-manuels/etage-N.yaml` donne la tranche, les donjons (ids DofusDB) et les quêtes par bloc
(ids DofusDB, « jusqu'où »). DofusDB fournit les noms, les niveaux, les succès des donjons et la nature
(repli, origine « dofusdb »). Il n'y a pas de fiche de quête : c'est le prix de ce repli. Le résultat est le
même `EtagePrepare` que celui de `construire.py`, écrit par `ecrire.py` sans rien changer d'autre.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from epreuve.contenu.construire import CasePreparee, ConfigInvalide, DonjonPrepare, EtagePrepare, QuetePreparee
from epreuve.dofusdb.repli import ClientEnCache, guides_repli, succes_du_donjon
from epreuve.domaine.modeles import Nature
from epreuve.domaine.nature import classer


class _Quete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dofusdb_id: int
    jusqu_ou: str | None = None
    a_lier: str | None = None


class _Bloc(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nom: str
    quetes: list[_Quete]


class _EtageManuel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    etage: int
    niveau_min: int
    niveau_max: int
    level_cap: int
    nom: str | None = None
    ouvert_le: datetime | None = None
    date_plancher_suivant: datetime | None = None
    donjons: list[int] = []
    blocs: list[_Bloc]


def lire_etage_manuel(chemin: Path) -> _EtageManuel:
    try:
        return _EtageManuel.model_validate(yaml.safe_load(chemin.read_text(encoding="utf-8")) or {})
    except (OSError, yaml.YAMLError, ValidationError) as e:
        raise ConfigInvalide(f"{chemin.name} invalide : {e}") from None


async def construire_manuel(m: _EtageManuel, client: ClientEnCache, dofus_retenus: Collection[str],
                            forcees: Mapping[str, Nature] | None = None) -> EtagePrepare:
    e = EtagePrepare(m.etage, m.nom or f"Étage {m.etage}", f"manuel-{m.etage}", m.niveau_min, m.niveau_max,
                     m.level_cap, None, m.ouvert_le, m.date_plancher_suivant)
    for ordre, dofusdb_id in enumerate(m.donjons, 1):
        donnees = await client.donjon(dofusdb_id)
        succes = await succes_du_donjon(client, dofusdb_id)
        cases = tuple(CasePreparee(i, n, nom, cond, cl) for n, (i, nom, cond, cl) in enumerate(succes, 1))
        nom = (donnees.get("name") or {}).get("fr", f"Donjon {dofusdb_id}")
        e.donjons.append(DonjonPrepare(f"dofusdb:{dofusdb_id}", nom, donnees.get("optimalPlayerLevel"), ordre, None,
                                       dofusdb_id, "dofusdb", cases))
        if len(cases) != 5:
            e.alertes.append(f"donjon « {nom} » : {len(cases)} succès au lieu de 5")
    guides = {d: frozenset(q) for d, q in (await guides_repli(client, dofus_retenus)).items()}
    ids = [q.dofusdb_id for b in m.blocs for q in b.quetes]
    forcees_ids = {int(k.removeprefix("dofusdb:")): v for k, v in (forcees or {}).items()}
    classement = classer(ids, {}, guides, dofus_retenus, forcees_ids)
    ordre = 0
    for bloc in m.blocs:
        for q in bloc.quetes:
            ordre += 1
            donnees = await client.quete(q.dofusdb_id)
            c = classement[q.dofusdb_id]
            e.quetes.append(QuetePreparee(f"dofusdb:{q.dofusdb_id}", (donnees.get("name") or {}).get("fr", "?"),
                                          donnees.get("levelMin"), bloc.nom, ordre, c.nature,
                                          "admin" if c.origine == "admin" else "dofusdb", c.dofus,
                                          q.jusqu_ou, q.a_lier, None, None))
            e.sans_fiche.append(e.quetes[-1].nom)
    e.alertes.append(f"étage saisi à la main (repli) : {len(e.quetes)} quêtes sans fiche, nature tirée de DofusDB")
    return e
