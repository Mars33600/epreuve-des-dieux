"""Repli : la fiche d'une quête que Duffus n'a pas, construite depuis DofusDB (données officielles du jeu).

Règles (décision de Marceau) :
- elle n'est tentée QUE pour une quête sans aucune fiche Duffus : `a_completer` filtre, jamais l'inverse ;
- elle a la même forme qu'une fiche Duffus (`ContenuFiche`) ; ce que DofusDB ne donne pas reste vide
  (pas de « jusqu'où », pas de succès lié, pas d'XP ni de kamas : DofusDB ne donne que des coefficients) ;
- le rapprochement se fait par le NOM exact normalisé (casse, accents et ponctuation ignorés). Duffus ne donne
  pas d'id de quête du jeu : `quest_list.dofus_id` est l'id d'un Dofus, pas d'une quête. Si le nom désigne
  plusieurs quêtes (d'un côté ou de l'autre) ou aucune, pas de fiche et une alerte : jamais d'approximation.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from html import escape

from epreuve.contenu.fiche_duffus import nettoyer_fiche
from epreuve.db.depot import ContenuFiche, PrerequisBrut
from epreuve.domaine.fiche import Besoin, EtapeFiche, Position

_JETON = re.compile(r"\{(npc|monster|item),(\d+)[^}]*\}")
_COMBAT = {"QuestObjectiveFightMonsterData", "QuestObjectiveMultiFightMonsterData"}
_APPORTER = "QuestObjectiveBringItemToNpcData"
_GENRE = {"npc": "npcs", "monster": "monsters", "item": "items"}


@dataclass(frozen=True)
class FicheRepli:
    """Le résultat pour une quête : la fiche, ou l'alerte qui dit pourquoi il n'y en a pas."""

    fiche: ContenuFiche | None
    alerte: str | None = None


def construire_fiche(q: Mapping, noms: Mapping[str, Mapping[int, str | None]], cartes: Mapping[int, list[int] | None],
                     nom_quete: Callable[[int], str | None],
                     duffus_par_nom: Callable[[str], str | None] = lambda _: None) -> ContenuFiche:
    """`q` : une quête allégée (`dofusdb.repli.alleger_quete_fiche`) ; `noms[genre][id]` et `cartes[id]` : les
    noms et coordonnées déjà lus (voir `ids_utiles`)."""

    def nom(genre: str, id_: int) -> str:
        return noms.get(genre, {}).get(id_) or "(inconnu)"

    def texte(brut: str) -> str:
        return _JETON.sub(lambda m: nom(_GENRE[m.group(1)], int(m.group(2))), brut).strip()

    etapes: list[EtapeFiche] = []
    positions: list[Position] = []
    monstres: dict[str, int] = {}
    objets: dict[str, int] = {}
    recompenses: list[str] = []
    for d in q.get("depart") or []:
        xy = cartes.get(d.get("mapId"))
        if xy:
            positions.append(Position(f"Départ : {nom('npcs', d['npcId'])}" if d.get("npcId") else "Départ",
                                      xy[0], xy[1], None))
    for item_id, qte in q.get("objets") or []:
        objets[nom("items", item_id)] = max(objets.get(nom("items", item_id), 0), int(qte))
    for e in q["etapes"]:
        lignes = []
        for o in e["objectifs"]:
            t = texte(o["texte"])
            if t:
                lignes.append(t)
            if o["position"]:
                positions.append(Position(t or "Position", o["position"][0], o["position"][1], None))
            if o["genre"] in _COMBAT and o["parametres"][0]:
                n = nom("monsters", o["parametres"][0])
                monstres[n] = monstres.get(n, 0) + max(int(o["parametres"][1]), 1)
            if o["genre"] == _APPORTER and o["parametres"][1]:
                n = nom("items", o["parametres"][1])
                objets[n] = max(objets.get(n, 0), int(o["parametres"][2]), 1)
        description = nettoyer_fiche(escape(e["description"]), {}) if e["description"].strip() else ""
        etapes.append(EtapeFiche(len(etapes) + 1, e["nom"].strip() or "Étape", description, tuple(lignes)))
        for r in e["recompenses"]:
            recompenses += [f"{qte} × {nom('items', i)}" for i, qte in r["itemsReward"]]
    vus: set[tuple] = set()
    positions = [p for p in positions if (p.x, p.y, p.libelle) not in vus and not vus.add((p.x, p.y, p.libelle))]
    prerequis = [PrerequisBrut(duffus_id=duffus_par_nom(n), nom=n)
                 for i in q.get("prerequis") or [] if (n := nom_quete(i))]
    return ContenuFiche(
        prerequis=prerequis, etapes=etapes, objets=[Besoin(n, c) for n, c in objets.items()],
        monstres=[Besoin(n, c) for n, c in monstres.items()], positions=positions, succes_lie=None,
        recompenses=list(dict.fromkeys(recompenses)),
    )  # fmt: skip


def ids_utiles(quetes: Iterable[Mapping]) -> tuple[dict[str, set[int]], set[int]]:
    """Les ids de PNJ, monstres, objets (par genre DofusDB) et de cartes à nommer pour ces quêtes."""
    noms: dict[str, set[int]] = defaultdict(set)
    cartes: set[int] = set()
    for q in quetes:
        for d in q.get("depart") or []:
            if d.get("npcId"):
                noms["npcs"].add(d["npcId"])
            if d.get("mapId"):
                cartes.add(d["mapId"])
        noms["items"].update(i for i, _ in q.get("objets") or [])
        for e in q["etapes"]:
            for o in e["objectifs"]:
                for genre, id_ in _JETON.findall(o["texte"]):
                    noms[_GENRE[genre]].add(int(id_))
                if o["genre"] in _COMBAT and o["parametres"][0]:
                    noms["monsters"].add(o["parametres"][0])
                if o["genre"] == _APPORTER and o["parametres"][1]:
                    noms["items"].add(o["parametres"][1])
            for r in e["recompenses"]:
                noms["items"].update(i for i, _ in r["itemsReward"])
    return dict(noms), cartes


async def fiches_de_repli(a_completer: Mapping[int, str], client, normaliser: Callable[[str], str],
                          duffus_par_nom: Mapping[str, list[int]]) -> dict[int, FicheRepli]:
    """Pour chaque quête SANS fiche Duffus (`a_completer` : id Duffus → titre), sa fiche DofusDB ou l'alerte.

    `duffus_par_nom` : nom normalisé → ids Duffus de toutes les quêtes (pour les prérequis et l'ambiguïté)."""
    if not a_completer:
        return {}
    index = await client.index_quetes()
    nom_de: dict[int, str] = {}
    par_nom: dict[str, list[int]] = defaultdict(list)
    for x in index:
        n = (x.get("name") or {}).get("fr", "")
        nom_de[x["id"]] = n
        par_nom[normaliser(n)].append(x["id"])
    sortie: dict[int, FicheRepli] = {}
    choisies: dict[int, int] = {}
    for id_duffus, titre in a_completer.items():
        cle = normaliser(titre)
        jumeaux = [i for i in duffus_par_nom.get(cle, []) if i in a_completer]
        candidates = par_nom.get(cle, [])
        if len(jumeaux) > 1 or len(candidates) > 1:
            sortie[id_duffus] = FicheRepli(
                None, f"« {titre} » : rapprochement DofusDB ambigu ({len(candidates)} quêtes du jeu, "
                      f"{len(jumeaux)} chez Duffus), pas de fiche")
        elif not candidates:
            sortie[id_duffus] = FicheRepli(None, f"« {titre} » : aucune quête DofusDB de ce nom, pas de fiche")
        else:
            choisies[id_duffus] = candidates[0]
    detail = await client.quetes_completes(set(choisies.values())) if choisies else {}
    ids, cartes_ids = ids_utiles(detail.values())
    noms = {g: await client.noms(g, v) for g, v in ids.items()}
    cartes = await client.cartes(cartes_ids) if cartes_ids else {}

    def nom_duffus(n: str) -> str | None:
        trouves = duffus_par_nom.get(normaliser(n), [])
        return str(trouves[0]) if len(trouves) == 1 else None

    for id_duffus, id_jeu in choisies.items():
        q = detail.get(id_jeu)
        if q is None or not q["etapes"]:
            sortie[id_duffus] = FicheRepli(
                None, f"« {a_completer[id_duffus]} » : quête DofusDB {id_jeu} sans étape, pas de fiche")
            continue
        sortie[id_duffus] = FicheRepli(construire_fiche(q, noms, cartes, nom_de.get, nom_duffus))
    return sortie
