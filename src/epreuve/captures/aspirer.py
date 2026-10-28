"""L'aspiration du module E1 : les tables Duffus utiles → donnees/duffus/AAAA-MM-JJ/ (fichiers ci-dessous).

Même client poli que le lot B (`duffus/client.py` : 1 requête par seconde au plus, arrêt sur 401/403/404),
mêmes règles d'écriture (`duffus/aspirer.serialiser` : stable, une ligne par enregistrement), en lecture
seule. On ne lit que ce dont le catalogue a besoin, environ 10 requêtes :

    archimonstres.json    archimonstres          les 286 archimonstres
    boss_ocre.json        boss_ocre              les boss de la quête du Dofus Ocre
    wanted2.json          wanted2                les avis de recherche
    monstres_e1.json      monsters               niveaux, race et apparence des archis et des boss (par chemin JSON)
    monster_races.json    monster_races          les races des boss homonymes (pour écarter expéditions et mémoires)
    monstres_avis.json    monsters               les grades des monstres des avis, réduits à ce qui est affiché
    subareas.json         subareas (+ areas)     les sous-zones nommées par les archis, leur aire, et leurs
                                                 monstres quand un nom de sous-zone existe dans plusieurs aires
    areas.json            areas                  les aires

Rien n'est écrit si une colonne exigée manque (le schéma de Duffus a changé).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from epreuve.captures import schema as s
from epreuve.captures.catalogue import id_monstre_archi, normaliser, zones_de
from epreuve.duffus.aspirer import Table, serialiser, valider
from epreuve.duffus.client import ClientDuffus

NB_GRADES = 8  # Duffus lit 8 grades au plus
CHAMPS_GRADE = ("grade", "level", "lifePoints", "actionPoints", "movementPoints", "tackleEvade", "tackleBonus",
                "apAttack", "mpAttack", "paLostDodge", "mpLostDodge", "reductionNeutral", "reductionEarth",
                "reductionFire", "reductionWater", "reductionAir")
COLONNES_NIVEAUX = "id,name,race,gfxid," + ",".join(f"n{i}:grades_json->{i}->level" for i in range(NB_GRADES))


def _table(nom: str, source: str, modele: type[BaseModel], cle: str = "id") -> Table:
    return Table(nom, source, modele, cle)


T_ARCHIS = _table("archimonstres", "archimonstres", s.ArchimonstreDuffus)
T_BOSS = _table("boss_ocre", "boss_ocre", s.BossOcre)
T_AVIS = _table("wanted2", "wanted2", s.Avis)
T_MONSTRES = _table("monstres_e1", "monsters", s.MonstreNiveaux)
T_RACES = _table("monster_races", "monster_races", s.Race)
T_MONSTRES_AVIS = _table("monstres_avis", "monsters", s.MonstreGrades)
T_SOUS_ZONES = _table("subareas", "subareas", s.SousZone)
T_SOUS_ZONES_MONSTRES = _table("subareas_monstres", "subareas", s.SousZoneMonstres)
T_AIRES = _table("areas", "areas", s.Aire)


def liste_in(valeurs) -> str:
    """Le filtre PostgREST `in.(…)`, chaque valeur entre guillemets (les noms ont des virgules, des apostrophes)."""
    def q(v) -> str:
        return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
    return "in.(" + ",".join(q(v) for v in valeurs) + ")"


def reduire_grades(grades: list[dict]) -> list[dict]:
    """Garde les caractéristiques affichées sur la fiche d'un avis (Duffus : PV, PA, PM, fuite, tacle…)."""
    return [{k: g.get(k) for k in CHAMPS_GRADE} for g in grades[:NB_GRADES] if isinstance(g, dict)]


def ids_monstres_des_sous_zones(monstres_json: list | None) -> list[int]:
    sortie = []
    for m in monstres_json or []:
        v = m.get("monsterId") if isinstance(m, dict) else m
        if isinstance(v, int):
            sortie.append(v)
    return sorted(set(sortie))


@dataclass
class RapportE1:
    dossier: Path
    comptes: dict[str, int] = field(default_factory=dict)
    requetes: int = 0

    def texte(self) -> str:
        lignes = [f"Aspiration E1 → {self.dossier}"]
        lignes += [f"  {nom} : {n} lignes" for nom, n in self.comptes.items()]
        lignes.append(f"  ({self.requetes} requêtes)")
        return "\n".join(lignes)


async def lire(client: ClientDuffus) -> dict[str, list[dict]]:
    """Lit et valide tout ; rien n'est écrit ici."""
    async def table(t: Table, colonnes: str, filtres: dict[str, str] | None = None) -> list[dict]:
        return valider(t, await client.lire_table(t.source, colonnes, t.cle, filtres))

    archis = await table(T_ARCHIS, "id,nom,etape,zone,image")
    boss = await table(T_BOSS, "id,nom,etape")
    avis = await table(T_AVIS, "id,slug,nom,lvl,zone,milice,recompense,recompense_type,chasse,dofus_monster_id,"
                               "resume_html")
    ids_archis = sorted({i for a in archis if (i := id_monstre_archi(a["image"])) is not None})
    monstres = await table(T_MONSTRES, COLONNES_NIVEAUX, {"id": liste_in(ids_archis)}) if ids_archis else []
    noms_boss = sorted({b["nom"] for b in boss})
    if noms_boss:
        deja = {m["id"] for m in monstres}
        monstres += [m for m in await table(T_MONSTRES, COLONNES_NIVEAUX, {"name": liste_in(noms_boss)})
                     if m["id"] not in deja]
        monstres.sort(key=lambda m: m["id"])
    races_boss = sorted({m["race"] for m in monstres if m["name"] in set(noms_boss) and m["race"] is not None})
    races = await table(T_RACES, "id,name", {"id": liste_in(races_boss)}) if races_boss else []
    ids_avis = sorted({int(a["dofus_monster_id"]) for a in avis if (a["dofus_monster_id"] or "").isdigit()})
    monstres_avis = await table(T_MONSTRES_AVIS, "id,name,gfxid,grades_json", {"id": liste_in(ids_avis)}) \
        if ids_avis else []
    for m in monstres_avis:
        m["grades_json"] = reduire_grades(m["grades_json"])
    sous_zones = await table(T_SOUS_ZONES, "id,name,areaid")
    # Un nom de sous-zone peut exister dans plusieurs aires : Duffus tranche par les monstres de la sous-zone.
    noms_archis = {normaliser(z) for a in archis for z in zones_de(a["zone"])}
    par_nom: dict[str, set] = {}
    for z in sous_zones:
        par_nom.setdefault(normaliser(z["name"]), set()).add(z["areaid"])
    ambigues = sorted(z["id"] for z in sous_zones
                      if normaliser(z["name"]) in noms_archis and len(par_nom[normaliser(z["name"])]) > 1)
    monstres_sz = {}
    if ambigues:
        for z in await table(T_SOUS_ZONES_MONSTRES, "id,monsters_json", {"id": liste_in(ambigues)}):
            monstres_sz[z["id"]] = ids_monstres_des_sous_zones(z["monsters_json"])
    utiles = [dict(z, monstres=monstres_sz.get(z["id"], [])) for z in sous_zones
              if normaliser(z["name"]) in noms_archis]
    aires = await table(T_AIRES, "id,name")
    return {"archimonstres": archis, "boss_ocre": boss, "wanted2": avis, "monstres_e1": monstres,
            "monster_races": races, "monstres_avis": monstres_avis, "subareas": utiles, "areas": aires}


async def aspirer(client: ClientDuffus, racine: Path, jour: date) -> RapportE1:
    extraits = await lire(client)
    dossier = racine / jour.isoformat()
    dossier.mkdir(parents=True, exist_ok=True)
    rapport = RapportE1(dossier, requetes=client.nb_requetes)
    for nom, lignes in extraits.items():
        (dossier / f"{nom}.json").write_text(serialiser(lignes), encoding="utf-8")
        rapport.comptes[nom] = len(lignes)
    return rapport
