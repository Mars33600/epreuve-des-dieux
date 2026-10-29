"""Lectures de l'encyclopédie (lot E2) : recherche paginée et fiches détaillées. Lecture seule.

`plafond` : le niveau maximal montré quand `modules.verrouiller_par_etage` est vrai (T-08) ; None sinon.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from epreuve.encyclopedie import tables as t
from epreuve.encyclopedie.liens import Liens
from epreuve.encyclopedie.textes import (
    FAMILLES,
    METIERS,
    REPETITIONS,
    EffetLu,
    cle_recherche,
    conditions_en_clair,
    effets_en_clair,
    icone_objet,
    icone_sort,
    ids_des_conditions,
    ids_des_objectifs,
    image_monstre,
    nettoyer_balises,
    objectif_en_clair,
    requete_plein_texte,
)

PAR_PAGE = 30
MAX_UTILISE_DANS = 60


@dataclass(frozen=True)
class Page:
    lignes: list[dict]
    total: int
    page: int
    par_page: int = PAR_PAGE

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.par_page))


@dataclass(frozen=True)
class Filtres:
    q: str | None = None
    famille: str | None = None
    type_id: int | None = None
    race_id: int | None = None
    classe_id: int | None = None
    metier: int | None = None
    niveau_min: int | None = None
    niveau_max: int | None = None
    tri: str = "recents"
    page: int = 1


@dataclass
class _Cache:
    effets: dict[int, tuple[str | None, int | None]] = field(default_factory=dict)


def _tri(colonnes: dict[str, Any], tri: str) -> list:
    niveau, ident = colonnes["niveau"], colonnes["id"]
    return {
        "niveau_desc": [niveau.desc().nulls_last(), ident.desc()],
        "niveau_asc": [niveau.asc().nulls_last(), ident.asc()],
        "nom_asc": [colonnes["cle"].asc(), ident.asc()],
        "nom_desc": [colonnes["cle"].desc(), ident.desc()],
    }.get(tri, [ident.desc()])


def _niveaux(col, f: Filtres, plafond: int | None) -> list:
    conds = []
    if f.niveau_min is not None:
        conds.append(col >= f.niveau_min)
    if f.niveau_max is not None:
        conds.append(col <= f.niveau_max)
    if plafond is not None:
        conds.append(col <= plafond)
    return conds


class DepotEncyclopedie:
    def __init__(self, moteur: AsyncEngine) -> None:
        self._moteur = moteur
        self._cache = _Cache()

    async def _paginer(self, requete: Select, f: Filtres) -> Page:
        page = max(1, f.page)
        async with self._moteur.connect() as c:
            total = (await c.execute(select(func.count()).select_from(requete.order_by(None).subquery()))).scalar_one()
            lignes = (await c.execute(requete.limit(PAR_PAGE).offset((page - 1) * PAR_PAGE))).mappings().all()
        return Page([dict(r) for r in lignes], total, page)

    async def _effets(self) -> dict[int, tuple[str | None, int | None]]:
        if not self._cache.effets:
            async with self._moteur.connect() as c:
                rangs = (await c.execute(select(t.ency_effet.c.id, t.ency_effet.c.description,
                                                t.ency_effet.c.priorite))).all()
            self._cache.effets = {r.id: (r.description, r.priorite) for r in rangs}
        return self._cache.effets

    async def en_clair(self, effets: list[list[int]]) -> list[EffetLu]:
        return effets_en_clair(effets or [], await self._effets())

    # --- Listes pour les filtres -------------------------------------------------------------------------

    async def types_par_famille(self) -> list[tuple[str, str, list[tuple[int, str]]]]:
        """[(famille, libellé, [(type, nom)])] : seuls les types qui ont au moins un objet."""
        o = t.ency_objet
        async with self._moteur.connect() as c:
            rangs = (await c.execute(
                select(t.ency_type.c.id, t.ency_type.c.nom, t.ency_type.c.famille)
                .where(select(o.c.id).where(o.c.type_id == t.ency_type.c.id).exists())
                .order_by(t.ency_type.c.nom))).all()
        groupes: dict[str, list[tuple[int, str]]] = {k: [] for k in FAMILLES}
        for r in rangs:
            groupes.setdefault(r.famille, []).append((r.id, r.nom))
        return [(k, FAMILLES.get(k, k), v) for k, v in groupes.items() if v]

    async def races(self) -> list[tuple[int, str]]:
        m = t.ency_monstre
        async with self._moteur.connect() as c:
            rangs = (await c.execute(
                select(t.ency_race.c.id, t.ency_race.c.nom)
                .where(select(m.c.id).where(m.c.race_id == t.ency_race.c.id).exists())
                .order_by(t.ency_race.c.nom))).all()
        return [(r.id, r.nom) for r in rangs]

    async def liens(self, noms: Iterable[str] = (), plafond: int | None = None, **ids: Iterable[int]) -> Liens:
        """Résout les noms cités (et, par `objet=`, `monstre=`…, des identifiants) en fiches de l'encyclopédie.

        Un nom n'est retenu que s'il désigne une seule fiche ; `plafond` écarte les fiches au-dessus du cap de
        niveau (l'encyclopédie y répond 404 quand elle est verrouillée par étage).
        """
        cles = sorted({c for c in (cle_recherche(n) for n in noms) if c})
        t = self._tables_liens()
        par_nom: dict[tuple[str, str], int] = {}
        existants: set[tuple[str, int]] = set()
        async with self._moteur.connect() as c:
            for genre, (table, niveau, filtre) in t.items():
                bornes = [filtre] if filtre is not None else []
                if plafond is not None and niveau is not None:
                    bornes.append(niveau <= plafond)
                if cles:
                    rangs = (await c.execute(select(table.c.id, table.c.cle_recherche)
                                             .where(table.c.cle_recherche.in_(cles), *bornes))).all()
                    comptes = Counter(r.cle_recherche for r in rangs)
                    par_nom.update({(genre, r.cle_recherche): r.id for r in rangs if comptes[r.cle_recherche] == 1})
                voulus = sorted(set(ids.get(genre, ())))
                if voulus:
                    existants.update((genre, r.id) for r in await c.execute(
                        select(table.c.id).where(table.c.id.in_(voulus), *bornes)))
        return Liens(par_nom, frozenset(existants))

    @staticmethod
    def _tables_liens() -> dict:
        o, m, p, n, s = t.ency_objet, t.ency_monstre, t.ency_panoplie, t.ency_pnj, t.ency_sort
        return {"objet": (o, o.c.niveau, None), "monstre": (m, m.c.niveau_min, None),
                "panoplie": (p, p.c.niveau, None), "pnj": (n, None, n.c.visible.is_(True)),
                "sort": (s, s.c.niveau_min, None)}

    async def _noms(self, table, ids: set[int], plafond: int | None = None) -> dict[int, str]:
        """{id: nom} pour des ids cités par une condition ou un objectif (les absents restent « n°… »)."""
        if not ids:
            return {}
        async with self._moteur.connect() as c:
            rangs = (await c.execute(select(table.c.id, table.c.nom).where(table.c.id.in_(sorted(ids))))).all()
        return {r.id: r.nom for r in rangs}

    async def _conditions(self, texte: str | None) -> str:
        if not texte:
            return ""
        ids = ids_des_conditions(texte)
        return conditions_en_clair(texte, await self._noms(t.ency_objet, ids["objets"]),
                                   await self._noms(t.ency_quete, ids["quetes"]))

    # --- Objets et ressources ----------------------------------------------------------------------------

    async def chercher_objets(self, f: Filtres, plafond: int | None = None) -> Page:
        o, ty = t.ency_objet, t.ency_type
        conds = _niveaux(o.c.niveau, f, plafond)
        tsq = requete_plein_texte(f.q)
        if tsq:
            conds.append(o.c.recherche.op("@@")(func.to_tsquery(text("'simple'"), tsq)))
        if f.famille:
            conds.append(o.c.famille == f.famille)
        if f.type_id is not None:
            conds.append(o.c.type_id == f.type_id)
        requete = (select(o.c.id, o.c.nom, o.c.niveau, o.c.icone, o.c.famille, ty.c.nom.label("type"))
                   .join(ty, ty.c.id == o.c.type_id, isouter=True).where(and_(True, *conds))
                   .order_by(*_tri({"niveau": o.c.niveau, "nom": o.c.nom, "id": o.c.id, "cle": o.c.cle_recherche},
                                   f.tri)))
        page = await self._paginer(requete, f)
        for r in page.lignes:
            r["image"] = icone_objet(r["icone"])
        return page

    async def _mini_objets(self, ids: list[int], plafond: int | None) -> dict[int, dict]:
        if not ids:
            return {}
        o = t.ency_objet
        conds = [o.c.id.in_(ids), *_niveaux(o.c.niveau, Filtres(), plafond)]
        async with self._moteur.connect() as c:
            rangs = (await c.execute(select(o.c.id, o.c.nom, o.c.niveau, o.c.icone).where(*conds))).mappings().all()
        return {r["id"]: {**r, "image": icone_objet(r["icone"])} for r in rangs}

    async def objet(self, ident: int, plafond: int | None = None) -> dict | None:
        o, ty = t.ency_objet, t.ency_type
        async with self._moteur.connect() as c:
            r = (await c.execute(select(o, ty.c.nom.label("type")).join(ty, ty.c.id == o.c.type_id, isouter=True)
                                 .where(o.c.id == ident, *_niveaux(o.c.niveau, Filtres(), plafond)))
                 ).mappings().one_or_none()
            if r is None:
                return None
            fiche = {k: v for k, v in r.items() if k != "recherche"}
            recette = (await c.execute(select(t.ency_recette).where(t.ency_recette.c.objet_id == ident))
                       ).mappings().one_or_none()
            utilise = (await c.execute(
                select(t.ency_recette.c.objet_id).where(t.ency_recette.c.ingredient_ids.contains([ident]))
                .order_by(t.ency_recette.c.niveau, t.ency_recette.c.objet_id))).scalars().all()
            panoplie = None
            if fiche["panoplie_id"]:
                panoplie = (await c.execute(select(t.ency_panoplie).where(
                    t.ency_panoplie.c.id == fiche["panoplie_id"]))).mappings().one_or_none()
            monstres = []
            if fiche["drops"]:
                monstres = (await c.execute(
                    select(t.ency_monstre.c.id, t.ency_monstre.c.nom, t.ency_monstre.c.niveau_min,
                           t.ency_monstre.c.niveau_max, t.ency_monstre.c.drops, t.ency_monstre.c.gfx)
                    .where(t.ency_monstre.c.id.in_(fiche["drops"]),
                           *_niveaux(t.ency_monstre.c.niveau_min, Filtres(), plafond))
                    .order_by(t.ency_monstre.c.niveau_min, t.ency_monstre.c.id))).mappings().all()
        fiche["image"] = icone_objet(fiche["icone"])
        fiche["conditions_lues"] = await self._conditions(fiche["conditions"])
        fiche["effets_lus"] = await self.en_clair(fiche["effets"])
        fiche["recette"] = None
        if recette:
            ingr = await self._mini_objets([i for i, _ in recette["ingredients"]], None)
            fiche["recette"] = {
                "metier": METIERS.get(recette["metier"] or -1), "niveau": recette["niveau"],
                "ingredients": [{**ingr.get(i, {"id": i, "nom": f"Objet {i}", "image": None}), "qte": q}
                                for i, q in recette["ingredients"]]}  # fmt: skip
        mini = await self._mini_objets(list(utilise[:MAX_UTILISE_DANS]), plafond)
        fiche["utilise_dans"] = [mini[i] for i in utilise[:MAX_UTILISE_DANS] if i in mini]
        fiche["utilise_dans_total"] = len(utilise)
        fiche["panoplie"] = None
        if panoplie:
            membres = await self._mini_objets(list(panoplie["objets"]), None)
            paliers = sorted(((int(n), e) for n, e in panoplie["bonus"].items() if e), key=lambda x: x[0])
            fiche["panoplie"] = {
                "id": panoplie["id"], "nom": panoplie["nom"],
                "objets": sorted(membres.values(), key=lambda x: (x["niveau"] or 0, x["id"])),
                "bonus": [(n, await self.en_clair(e)) for n, e in paliers]}
        fiche["monstres"] = []
        for m in monstres:
            taux = next((d for d in m["drops"] if d[0] == ident), None)
            fiche["monstres"].append({"id": m["id"], "nom": m["nom"], "niveau_min": m["niveau_min"],
                                      "niveau_max": m["niveau_max"], "image": image_monstre(m["gfx"]),
                                      "taux": (taux[1], taux[2]) if taux else None,
                                      "condition": bool(taux and taux[3])})
        return fiche

    # --- Monstres ----------------------------------------------------------------------------------------

    async def chercher_monstres(self, f: Filtres, plafond: int | None = None) -> Page:
        m, ra = t.ency_monstre, t.ency_race
        conds = _niveaux(m.c.niveau_min, f, plafond)
        tsq = requete_plein_texte(f.q)
        if tsq:
            conds.append(m.c.recherche.op("@@")(func.to_tsquery(text("'simple'"), tsq)))
        if f.race_id is not None:
            conds.append(m.c.race_id == f.race_id)
        requete = (select(m.c.id, m.c.nom, m.c.niveau_min, m.c.niveau_max, m.c.gfx, ra.c.nom.label("race"))
                   .join(ra, ra.c.id == m.c.race_id, isouter=True).where(and_(True, *conds))
                   .order_by(*_tri({"niveau": m.c.niveau_min, "nom": m.c.nom, "id": m.c.id,
                                    "cle": m.c.cle_recherche}, f.tri)))
        page = await self._paginer(requete, f)
        for r in page.lignes:
            r["image"] = image_monstre(r.pop("gfx"))
        return page

    async def monstre(self, ident: int, plafond: int | None = None) -> dict | None:
        m, ra = t.ency_monstre, t.ency_race
        async with self._moteur.connect() as c:
            r = (await c.execute(select(m, ra.c.nom.label("race")).join(ra, ra.c.id == m.c.race_id, isouter=True)
                                 .where(m.c.id == ident, *_niveaux(m.c.niveau_min, Filtres(), plafond)))
                 ).mappings().one_or_none()
        if r is None:
            return None
        fiche = {k: v for k, v in r.items() if k != "recherche"}
        fiche["image"] = image_monstre(fiche["gfx"])
        objets = await self._mini_objets([d[0] for d in fiche["drops"]], plafond)
        fiche["butin"] = sorted(
            ({**objets[d[0]], "taux": (d[1], d[2]), "condition": bool(d[3])} for d in fiche["drops"] if d[0] in objets),
            key=lambda x: (-(x["taux"][1] or 0), x["nom"]))
        return fiche

    # --- Recettes ----------------------------------------------------------------------------------------

    async def chercher_recettes(self, f: Filtres, plafond: int | None = None) -> Page:
        o, r = t.ency_objet, t.ency_recette
        conds = _niveaux(o.c.niveau, f, plafond)
        tsq = requete_plein_texte(f.q)
        if tsq:
            conds.append(o.c.recherche.op("@@")(func.to_tsquery(text("'simple'"), tsq)))
        if f.metier is not None:
            conds.append(r.c.metier == f.metier)
        requete = (select(o.c.id, o.c.nom, o.c.niveau, o.c.icone, r.c.metier, r.c.ingredients)
                   .join(o, o.c.id == r.c.objet_id).where(and_(True, *conds))
                   .order_by(*_tri({"niveau": o.c.niveau, "nom": o.c.nom, "id": o.c.id, "cle": o.c.cle_recherche},
                                   f.tri)))
        page = await self._paginer(requete, f)
        ids = sorted({i for x in page.lignes for i, _ in x["ingredients"]})
        mini = await self._mini_objets(ids, None)
        for x in page.lignes:
            x["image"] = icone_objet(x["icone"])
            x["metier_nom"] = METIERS.get(x["metier"] or -1)
            x["ingredients"] = [{**mini.get(i, {"id": i, "nom": f"Objet {i}", "image": None}), "qte": q}
                                for i, q in x["ingredients"]]
        return page

    # --- Stuffs ------------------------------------------------------------------------------------------

    async def stuffs(self, niveau_max: int) -> list[dict]:
        """Les stuffs jusqu'à `niveau_max` (le haut du dernier étage visible) : rien au-delà ne sort de la base."""
        s = t.ency_stuff
        async with self._moteur.connect() as c:
            rangs = (await c.execute(select(s).where(s.c.niveau <= niveau_max)
                                     .order_by(s.c.niveau, s.c.classe, s.c.nom))).mappings().all()
        return [dict(r) for r in rangs]

    async def effets_de(self, ids: list[int]) -> dict[int, list[EffetLu]]:
        """Les effets en clair de plusieurs objets, en une requête (la fiche d'un stuff)."""
        if not ids:
            return {}
        async with self._moteur.connect() as c:
            rangs = (await c.execute(select(t.ency_objet.c.id, t.ency_objet.c.effets)
                                     .where(t.ency_objet.c.id.in_(ids)))).all()
        return {r.id: await self.en_clair(r.effets) for r in rangs}

    async def objets_de_stuffs(self, stuffs: list[dict]) -> dict[int, dict]:
        ids = sorted({i for st in stuffs for i in [*st["objets"].values(), *st["dofus"]] if isinstance(i, int)})
        return await self._mini_objets(ids, None)

    # --- Panoplies ---------------------------------------------------------------------------------------

    async def chercher_panoplies(self, f: Filtres, plafond: int | None = None) -> Page:
        p = t.ency_panoplie
        conds = _niveaux(p.c.niveau, f, plafond)
        tsq = requete_plein_texte(f.q)
        if tsq:
            conds.append(p.c.recherche.op("@@")(func.to_tsquery(text("'simple'"), tsq)))
        requete = (select(p.c.id, p.c.nom, p.c.niveau, func.cardinality(p.c.objets).label("nb_objets"))
                   .where(and_(True, *conds))
                   .order_by(*_tri({"niveau": p.c.niveau, "nom": p.c.nom, "id": p.c.id, "cle": p.c.cle_recherche},
                                   f.tri)))
        return await self._paginer(requete, f)

    async def panoplie(self, ident: int, plafond: int | None = None) -> dict | None:
        p = t.ency_panoplie
        async with self._moteur.connect() as c:
            r = (await c.execute(select(p.c.id, p.c.nom, p.c.niveau, p.c.objets, p.c.bonus)
                                 .where(p.c.id == ident, *_niveaux(p.c.niveau, Filtres(), plafond)))
                 ).mappings().one_or_none()
        if r is None:
            return None
        membres = await self._mini_objets(list(r["objets"]), None)
        paliers = sorted(((int(n), e) for n, e in r["bonus"].items() if e), key=lambda x: x[0])
        return {"id": r["id"], "nom": r["nom"], "niveau": r["niveau"],
                "objets": sorted(membres.values(), key=lambda x: (x["niveau"] or 0, x["id"])),
                "bonus": [(n, await self.en_clair(e)) for n, e in paliers]}

    # --- Sorts et classes --------------------------------------------------------------------------------

    async def classes(self) -> list[dict]:
        c_ = t.ency_classe
        async with self._moteur.connect() as c:
            return [dict(r) for r in (await c.execute(select(c_.c.id, c_.c.nom, c_.c.role).order_by(c_.c.nom))
                                      ).mappings().all()]

    async def chercher_sorts(self, f: Filtres, plafond: int | None = None) -> Page:
        s, cl = t.ency_sort, t.ency_classe
        conds = _niveaux(s.c.niveau_min, f, plafond)
        tsq = requete_plein_texte(f.q)
        if tsq:
            conds.append(s.c.recherche.op("@@")(func.to_tsquery(text("'simple'"), tsq)))
        if f.classe_id is not None:
            conds.append(s.c.classe_id == f.classe_id)
        requete = (select(s.c.id, s.c.nom, s.c.icone, s.c.niveau_min.label("niveau"), s.c.description,
                          cl.c.nom.label("classe"))
                   .join(cl, cl.c.id == s.c.classe_id, isouter=True).where(and_(True, *conds))
                   .order_by(*_tri({"niveau": s.c.niveau_min, "nom": s.c.nom, "id": s.c.id,
                                    "cle": s.c.cle_recherche}, f.tri)))
        page = await self._paginer(requete, f)
        for r in page.lignes:
            r["image"] = icone_sort(r["icone"])
            nettoyer_balises(r)
        return page

    async def sort(self, ident: int, plafond: int | None = None) -> dict | None:
        s, cl = t.ency_sort, t.ency_classe
        async with self._moteur.connect() as c:
            r = (await c.execute(select(s, cl.c.nom.label("classe")).join(cl, cl.c.id == s.c.classe_id, isouter=True)
                                 .where(s.c.id == ident, *_niveaux(s.c.niveau_min, Filtres(), plafond)))
                 ).mappings().one_or_none()
        if r is None:
            return None
        fiche = {k: v for k, v in r.items() if k != "recherche"}
        fiche["image"] = icone_sort(fiche["icone"])
        for n in fiche["niveaux"]:
            n["effets_lus"] = await self.en_clair(n["effets"])
            n["effets_cc_lus"] = await self.en_clair(n["effets_cc"])
        return nettoyer_balises(fiche)

    # --- PNJ ---------------------------------------------------------------------------------------------

    async def chercher_pnj(self, f: Filtres) -> Page:
        n = t.ency_pnj
        conds = [n.c.visible.is_(True)]
        tsq = requete_plein_texte(f.q)
        if tsq:
            conds.append(n.c.recherche.op("@@")(func.to_tsquery(text("'simple'"), tsq)))
        requete = (select(n.c.id, n.c.nom).where(and_(True, *conds))
                   .order_by(n.c.cle_recherche.desc() if f.tri == "nom_desc" else n.c.cle_recherche, n.c.id))
        return await self._paginer(requete, f)

    async def pnj(self, ident: int, plafond: int | None = None) -> dict | None:
        n, q = t.ency_pnj, t.ency_quete
        async with self._moteur.connect() as c:
            r = (await c.execute(select(n.c.id, n.c.nom, n.c.genre).where(n.c.id == ident))).mappings().one_or_none()
            if r is None:
                return None
            quetes = (await c.execute(
                select(q.c.id, q.c.nom, q.c.niveau_min, q.c.niveau_max, q.c.zone)
                .where(q.c.pnj_ids.contains([ident]), *_niveaux(q.c.niveau_min, Filtres(), plafond))
                .order_by(q.c.niveau_min, q.c.id))).mappings().all()
        return {**r, "quetes": [dict(x) for x in quetes]}

    # --- Quêtes ------------------------------------------------------------------------------------------

    async def chercher_quetes(self, f: Filtres, plafond: int | None = None) -> Page:
        q = t.ency_quete
        conds = _niveaux(q.c.niveau_min, f, plafond)
        tsq = requete_plein_texte(f.q)
        if tsq:
            conds.append(q.c.recherche.op("@@")(func.to_tsquery(text("'simple'"), tsq)))
        requete = (select(q.c.id, q.c.nom, q.c.niveau_min, q.c.niveau_max, q.c.zone, q.c.categorie)
                   .where(and_(True, *conds))
                   .order_by(*_tri({"niveau": q.c.niveau_min, "nom": q.c.nom, "id": q.c.id,
                                    "cle": q.c.cle_recherche}, f.tri)))
        return await self._paginer(requete, f)

    async def quete(self, ident: int, plafond: int | None = None) -> dict | None:
        q = t.ency_quete
        async with self._moteur.connect() as c:
            r = (await c.execute(select(q).where(q.c.id == ident, *_niveaux(q.c.niveau_min, Filtres(), plafond)))
                 ).mappings().one_or_none()
        if r is None:
            return None
        fiche = {k: v for k, v in r.items() if k != "recherche"}
        objectifs = [o for e in fiche["etapes"] for o in e["objectifs"]]
        ids = ids_des_objectifs(objectifs)
        recompenses = [x for e in fiche["etapes"] for rc in e["recompenses"] for x in rc["objets"]]
        pnj = await self._noms(t.ency_pnj, ids["pnj"] | {d["pnj"] for d in fiche["depart"] if d.get("pnj")})
        monstres = await self._noms(t.ency_monstre, ids["monstres"])
        objets = await self._noms(t.ency_objet, ids["objets"] | {i for i, _ in recompenses})
        for e in fiche["etapes"]:
            e["objectifs_lus"] = [objectif_en_clair(o, pnj, objets, monstres) for o in e["objectifs"]]
            e["recompenses_lues"] = [{"id": i, "nom": objets.get(i, f"Objet {i}"), "qte": qte}
                                     for rc in e["recompenses"] for i, qte in rc["objets"]]
        fiche["depart_lu"] = [{"pnj_id": d["pnj"], "pnj": pnj.get(d["pnj"], f"PNJ n°{d['pnj']}")}
                              for d in fiche["depart"] if d.get("pnj")]
        fiche["conditions_lues"] = await self._conditions(fiche["condition"])
        fiche["repetition_lue"] = REPETITIONS.get(fiche["repetition"] or 0, "Non répétable")
        return nettoyer_balises(fiche)
