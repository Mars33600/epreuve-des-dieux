"""Les builds en base (table `epreuve.build`, migration `e3_builds`). Requêtes SQLAlchemy Core, asynchrones.

Seul l'auteur modifie ou supprime un build ; un build partagé se lit par tout grimpeur connecté (la page vérifie
la connexion). Les objets sont gardés par identifiant : une nouvelle aspiration met leurs statistiques à jour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Table, Text, delete, insert, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine

from epreuve.db import tables as t
from epreuve.encyclopedie import tables as ency

build = Table(
    "build", t.metadata,
    Column("id", Integer, primary_key=True),
    Column("grimpeur_id", Integer, ForeignKey("grimpeur.id"), nullable=False),
    Column("nom", Text, nullable=False),
    Column("classe", Text, nullable=False),
    Column("niveau", Integer, nullable=False),
    Column("objets", JSONB, nullable=False),
    Column("caracs_base", JSONB, nullable=False),
    Column("caracs_parcho", JSONB, nullable=False),
    Column("note", Text, nullable=False),
    Column("fm", JSONB, nullable=False),
    Column("partage", Boolean, nullable=False),
    Column("cree_le", DateTime(timezone=True), nullable=False),
    Column("maj_le", DateTime(timezone=True), nullable=False),
)  # fmt: skip


@dataclass(frozen=True)
class Contenu:
    """Ce que l'auteur écrit."""

    nom: str
    classe: str
    niveau: int
    objets: dict[str, int]
    caracs_base: dict[str, int]
    caracs_parcho: dict[str, int]
    note: str = ""
    partage: bool = False
    fm: dict[str, dict[str, int]] = field(default_factory=dict)  # emplacement → effectId (texte) → valeur


@dataclass(frozen=True)
class BuildEnregistre:
    id: int
    grimpeur_id: int
    auteur: str
    contenu: Contenu
    maj_le: datetime


class DepotBuilds:
    def __init__(self, moteur: AsyncEngine) -> None:
        self._moteur = moteur

    @staticmethod
    def _valeurs(c: Contenu) -> dict:
        return {"nom": c.nom, "classe": c.classe, "niveau": c.niveau, "objets": c.objets,
                "caracs_base": c.caracs_base, "caracs_parcho": c.caracs_parcho, "note": c.note, "partage": c.partage,
                "fm": c.fm}

    def _requete(self):
        return (select(build, t.grimpeur.c.pseudo_ig.label("pseudo"))
                .join(t.grimpeur, t.grimpeur.c.id == build.c.grimpeur_id))

    @staticmethod
    def _ligne(r) -> BuildEnregistre:
        return BuildEnregistre(r.id, r.grimpeur_id, r.pseudo,
                               Contenu(r.nom, r.classe, r.niveau, dict(r.objets), dict(r.caracs_base),
                                       dict(r.caracs_parcho), r.note, r.partage, dict(r.fm)), r.maj_le)

    async def creer(self, grimpeur_id: int, contenu: Contenu, maintenant: datetime) -> int:
        async with self._moteur.begin() as c:
            r = await c.execute(insert(build).values(grimpeur_id=grimpeur_id, cree_le=maintenant, maj_le=maintenant,
                                                     **self._valeurs(contenu)).returning(build.c.id))
            return r.scalar_one()

    async def modifier(self, build_id: int, grimpeur_id: int, contenu: Contenu, maintenant: datetime) -> bool:
        """Faux si le build n'existe pas ou n'est pas à ce grimpeur."""
        async with self._moteur.begin() as c:
            r = await c.execute(update(build).where(build.c.id == build_id, build.c.grimpeur_id == grimpeur_id)
                                .values(maj_le=maintenant, **self._valeurs(contenu)))
            return r.rowcount == 1

    async def supprimer(self, build_id: int, grimpeur_id: int) -> bool:
        async with self._moteur.begin() as c:
            r = await c.execute(delete(build).where(build.c.id == build_id, build.c.grimpeur_id == grimpeur_id))
            return r.rowcount == 1

    async def lire(self, build_id: int) -> BuildEnregistre | None:
        async with self._moteur.connect() as c:
            r = (await c.execute(self._requete().where(build.c.id == build_id))).one_or_none()
        return self._ligne(r) if r else None

    async def de_grimpeur(self, grimpeur_id: int) -> list[BuildEnregistre]:
        async with self._moteur.connect() as c:
            lignes = await c.execute(self._requete().where(build.c.grimpeur_id == grimpeur_id)
                                     .order_by(build.c.maj_le.desc(), build.c.id.desc()))
            return [self._ligne(r) for r in lignes]

    async def partages(self, sauf_grimpeur: int | None = None, limite: int = 200) -> list[BuildEnregistre]:
        """Les builds partagés dans la guilde, des autres grimpeurs, les plus récents d'abord."""
        q = self._requete().where(build.c.partage.is_(True))
        if sauf_grimpeur is not None:
            q = q.where(build.c.grimpeur_id != sauf_grimpeur)
        async with self._moteur.connect() as c:
            lignes = await c.execute(q.order_by(build.c.maj_le.desc(), build.c.id.desc()).limit(limite))
            return [self._ligne(r) for r in lignes]

    async def sorts_de_classe(self, classe: str) -> list[dict]:
        """Les sorts d'une classe (tables de l'encyclopédie), dans l'ordre du jeu ; [] si la classe est inconnue."""
        async with self._moteur.connect() as c:
            ids = (await c.execute(select(ency.ency_classe.c.sorts).where(ency.ency_classe.c.nom == classe))
                   ).scalar_one_or_none()
            if not ids:
                return []
            s = ency.ency_sort
            lignes = (await c.execute(select(s.c.id, s.c.nom, s.c.icone, s.c.niveaux).where(s.c.id.in_(ids)))
                      ).mappings().all()
        par_id = {r["id"]: dict(r) for r in lignes}
        return [par_id[i] for i in ids if i in par_id]
