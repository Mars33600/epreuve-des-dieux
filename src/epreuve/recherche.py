"""La recherche globale : un seul point d'entrée pour tout ce qu'on peut chercher sur le site.

Une requête = des mots entiers ou partiels, sans accents ni casse (« gelax » trouve la Gelaxième Dimension). Chaque
type de résultat a sa propre requête, qui s'appuie sur un index trigrammes (`pg_trgm`, migration `g1_recherche`) :
`cle LIKE '%mot%'` pour chaque mot. Les types sont interrogés en parallèle, `limite + 1` lignes chacun : la ligne
en trop dit seulement s'il y a un « voir tout », sans compter tout le reste.

Le brouillard de guerre : les quêtes et donjons d'un étage scellé n'entrent JAMAIS dans une réponse pour un
non-admin (la condition est dans le SQL, pas dans un filtre après coup). Même règle pour ce qui est masqué.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from epreuve.db import tables as d
from epreuve.encyclopedie import tables as e
from epreuve.encyclopedie.textes import cle_recherche

MAX_MOTS = 6
MAX_LIMITE = 100
# L'ordre est celui des groupes dans la réponse. (clé, libellé)
TYPES: tuple[tuple[str, str], ...] = (
    ("grimpeurs", "Grimpeurs"), ("quetes", "Quêtes"), ("donjons", "Donjons"), ("monstres", "Monstres"),
    ("objets", "Objets"), ("ressources", "Ressources"), ("panoplies", "Panoplies"), ("sorts", "Sorts"),
    ("pnj", "PNJ"), ("quetes_jeu", "Quêtes du jeu"), ("outils", "Outils"),
)
LIBELLES = dict(TYPES)


@dataclass(frozen=True)
class Resultat:
    nom: str
    lien: str
    detail: str = ""


@dataclass(frozen=True)
class Groupe:
    type: str
    libelle: str
    resultats: list[Resultat]
    plus: bool  # il y a d'autres résultats que ceux listés


def mots_de(saisie: str | None) -> list[str]:
    return cle_recherche(saisie[:80] if saisie else "").split()[:MAX_MOTS]


def _niveau(bas: int | None, haut: int | None = None) -> str:
    if bas is None:
        return ""
    return f"niv. {bas}" if haut in (None, bas) else f"niv. {bas}-{haut}"


def _filtrer(colonne, mots: list[str], conds: list) -> Select:
    """Les mots, chacun en sous-chaîne de la colonne (index trigramme)."""
    return and_(*(colonne.like(f"%{m}%") for m in mots), *conds)


def _rang(colonne, requete: str):
    """Début de nom d'abord, puis début de mot, puis le plus court."""
    return (colonne.like(f"{requete}%").desc(), colonne.like(f"% {requete}%").desc(), func.length(colonne), colonne)


class DepotRecherche:
    def __init__(self, moteur: AsyncEngine, outils: tuple[tuple[str, str, str], ...] = ()) -> None:
        self._moteur = moteur
        self._outils = outils  # (chemin, nom, résumé)

    async def _lignes(self, requete: Select, limite: int):
        async with self._moteur.connect() as c:
            return (await c.execute(requete.limit(limite + 1))).all()

    async def chercher(self, saisie: str | None, *, est_admin: bool, plafond: int | None, limite: int = 5,
                       types: tuple[str, ...] | None = None) -> list[Groupe]:
        mots = mots_de(saisie)
        if not mots:
            return []
        q = " ".join(mots)
        limite = max(1, min(limite, MAX_LIMITE))
        voulus = [k for k, _ in TYPES if types is None or k in types]
        listes = await asyncio.gather(*(self._type(k, mots, q, est_admin, plafond, limite) for k in voulus))
        return [Groupe(k, LIBELLES[k], r[:limite], len(r) > limite) for k, r in zip(voulus, listes, strict=True) if r]

    async def _type(self, cle: str, mots: list[str], q: str, est_admin: bool, plafond: int | None,
                    limite: int) -> list[Resultat]:
        if cle == "outils":
            return [Resultat(nom, f"/outils/{chemin}", resume) for chemin, nom, resume in self._outils
                    if all(m in cle_recherche(nom) for m in mots)][: limite + 1]
        requete, fabrique = getattr(self, f"_{cle}")(mots, q, est_admin, plafond)
        return [fabrique(r) for r in await self._lignes(requete, limite)]

    # --- Les grimpeurs, quêtes et donjons du défi ---------------------------------------------------------

    def _grimpeurs(self, mots, q, est_admin, plafond):
        g = d.grimpeur
        cle = func.epreuve.cle_recherche(g.c.pseudo_ig)
        requete = (select(g.c.id, g.c.pseudo_ig, g.c.classe).where(_filtrer(cle, mots, [g.c.statut != "exclu"]))
                   .order_by(*_rang(cle, q)))
        return requete, lambda r: Resultat(r.pseudo_ig, f"/grimpeurs/{r.id}", r.classe or "")

    def _quetes(self, mots, q, est_admin, plafond):
        qu, et = d.quete, d.etage
        cle = func.epreuve.cle_recherche(qu.c.nom)
        conds = [] if est_admin else [et.c.statut != "scelle", qu.c.masquee.is_(False)]
        requete = (select(qu.c.id, qu.c.nom, et.c.numero).join(et, et.c.id == qu.c.etage_id)
                   .where(_filtrer(cle, mots, conds)).order_by(*_rang(cle, q)))
        return requete, lambda r: Resultat(r.nom, f"/etages/{r.numero}/quetes/{r.id}", f"étage {r.numero}")

    def _donjons(self, mots, q, est_admin, plafond):
        dj, et = d.donjon, d.etage
        cle = func.epreuve.cle_recherche(dj.c.nom)
        conds = [] if est_admin else [et.c.statut != "scelle", dj.c.masque.is_(False)]
        requete = (select(dj.c.id, dj.c.nom, et.c.numero).join(et, et.c.id == dj.c.etage_id)
                   .where(_filtrer(cle, mots, conds)).order_by(*_rang(cle, q)))
        return requete, lambda r: Resultat(r.nom, f"/etages/{r.numero}", f"étage {r.numero}")

    # --- L'encyclopédie ------------------------------------------------------------------------------------

    @staticmethod
    def _borne(colonne, plafond: int | None) -> list:
        return [] if plafond is None else [colonne <= plafond]

    def _monstres(self, mots, q, est_admin, plafond):
        m = e.ency_monstre
        requete = (select(m.c.id, m.c.nom, m.c.niveau_min, m.c.niveau_max)
                   .where(_filtrer(m.c.cle_recherche, mots, self._borne(m.c.niveau_min, plafond)))
                   .order_by(*_rang(m.c.cle_recherche, q)))
        return requete, lambda r: Resultat(r.nom, f"/encyclopedie/monstres/{r.id}", _niveau(r.niveau_min, r.niveau_max))

    def _objets_famille(self, mots, q, plafond, ressource: bool):
        o = e.ency_objet
        famille = o.c.famille == "ressources" if ressource else o.c.famille.is_distinct_from("ressources")
        requete = (select(o.c.id, o.c.nom, o.c.niveau)
                   .where(_filtrer(o.c.cle_recherche, mots, [famille, *self._borne(o.c.niveau, plafond)]))
                   .order_by(*_rang(o.c.cle_recherche, q)))
        return requete, lambda r: Resultat(r.nom, f"/encyclopedie/objets/{r.id}", _niveau(r.niveau))

    def _objets(self, mots, q, est_admin, plafond):
        return self._objets_famille(mots, q, plafond, False)

    def _ressources(self, mots, q, est_admin, plafond):
        return self._objets_famille(mots, q, plafond, True)

    def _panoplies(self, mots, q, est_admin, plafond):
        p = e.ency_panoplie
        requete = (select(p.c.id, p.c.nom, p.c.niveau)
                   .where(_filtrer(p.c.cle_recherche, mots, self._borne(p.c.niveau, plafond)))
                   .order_by(*_rang(p.c.cle_recherche, q)))
        return requete, lambda r: Resultat(r.nom, f"/encyclopedie/panoplies/{r.id}", _niveau(r.niveau))

    def _sorts(self, mots, q, est_admin, plafond):
        s = e.ency_sort
        requete = (select(s.c.id, s.c.nom, s.c.niveau_min)
                   .where(_filtrer(s.c.cle_recherche, mots, self._borne(s.c.niveau_min, plafond)))
                   .order_by(*_rang(s.c.cle_recherche, q)))
        return requete, lambda r: Resultat(r.nom, f"/encyclopedie/sorts/{r.id}", _niveau(r.niveau_min))

    def _pnj(self, mots, q, est_admin, plafond):
        n = e.ency_pnj
        requete = (select(n.c.id, n.c.nom).where(_filtrer(n.c.cle_recherche, mots, [n.c.visible.is_(True)]))
                   .order_by(*_rang(n.c.cle_recherche, q)))
        return requete, lambda r: Resultat(r.nom, f"/encyclopedie/pnj/{r.id}")

    def _quetes_jeu(self, mots, q, est_admin, plafond):
        qu = e.ency_quete
        requete = (select(qu.c.id, qu.c.nom, qu.c.niveau_min, qu.c.niveau_max)
                   .where(_filtrer(qu.c.cle_recherche, mots, self._borne(qu.c.niveau_min, plafond)))
                   .order_by(*_rang(qu.c.cle_recherche, q)))
        return requete, lambda r: Resultat(r.nom, f"/encyclopedie/quetes/{r.id}", _niveau(r.niveau_min, r.niveau_max))


