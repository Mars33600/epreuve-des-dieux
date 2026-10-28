"""Le catalogue et les captures du module E1 : en base (`DepotCaptures`) ou en mémoire (`CapturesMemoire`,
pour la démonstration et les tests du site). Les deux ont la même interface.

Tables (migration `e1_captures`) : `archimonstre`, `boss_ocre`, `avis_recherche` (le catalogue, rechargé par
`python -m epreuve.captures charger`), `capture_archi`, `capture_boss`, `capture_avis` (une ligne par
élément possédé ; supprimée à 0 exemplaire ou au décochage) et `archi_personnages` (le nombre de
personnages visé, 1 par défaut). Un élément que Duffus n'a plus est « retiré » (masqué), jamais supprimé :
la base refuse de supprimer un élément capturé (clé étrangère).

Les captures ne passent pas par le journal du lot B : c'est un suivi personnel, sans effet sur la jauge.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Protocol

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, Table, Text, delete, func, select, true, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncEngine

from epreuve.captures.catalogue import Archimonstre, AvisRecherche, Boss, Catalogue, Grade, Zone
from epreuve.captures.domaine import EXEMPLAIRES_MAX, Genre, borne_personnages


class ElementInconnu(Exception):
    """Archimonstre, boss ou avis inconnu (ou retiré)."""


class SourceCaptures(Protocol):
    async def archimonstres(self) -> list[Archimonstre]: ...
    async def boss(self) -> list[Boss]: ...
    async def avis(self) -> list[AvisRecherche]: ...
    async def nombres(self, grimpeur_id: int, genre: Genre) -> dict[int, int]: ...
    async def changer_nombre(self, grimpeur_id: int, genre: Genre, element_id: int, delta: int,
                             maintenant: datetime) -> int: ...
    async def avis_captures(self, grimpeur_id: int) -> set[int]: ...
    async def capturer_avis(self, grimpeur_id: int, avis_id: int, capture: bool, maintenant: datetime) -> bool: ...
    async def personnages(self, grimpeur_id: int) -> int: ...
    async def regler_personnages(self, grimpeur_id: int, nombre: int) -> int: ...
    async def detenteurs(self, genre: Genre | str, element_id: int) -> dict[int, int]: ...


# --- Tables (le schéma, contraintes comprises, est dans la migration e1_captures) -------------------------

metadata = MetaData(schema="epreuve")
Horodatage = DateTime(timezone=True)

t_archi = Table(
    "archimonstre", metadata,
    Column("id", Integer, primary_key=True), Column("nom", Text, nullable=False), Column("etape", Integer),
    Column("zones", JSONB, nullable=False), Column("monstre_id", Integer), Column("gfx_id", Integer),
    Column("niveau_min", Integer), Column("niveau_max", Integer),
    Column("retire", Boolean, nullable=False), Column("maj_le", Horodatage, nullable=False),
)  # fmt: skip
t_boss = Table(
    "boss_ocre", metadata,
    Column("id", Integer, primary_key=True), Column("nom", Text, nullable=False), Column("etape", Integer),
    Column("monstre_id", Integer), Column("gfx_id", Integer), Column("niveau", Integer),
    Column("retire", Boolean, nullable=False), Column("maj_le", Horodatage, nullable=False),
)  # fmt: skip
t_avis = Table(
    "avis_recherche", metadata,
    Column("id", Integer, primary_key=True), Column("slug", Text, nullable=False), Column("nom", Text, nullable=False),
    Column("niveau_texte", Text), Column("niveau", Integer), Column("zone", Text), Column("milice", Text),
    Column("recompense", Integer), Column("recompense_type", Text, nullable=False), Column("chasse", Boolean),
    Column("monstre_id", Integer), Column("gfx_id", Integer), Column("resume_html", Text, nullable=False),
    Column("grades", JSONB, nullable=False),
    Column("retire", Boolean, nullable=False), Column("maj_le", Horodatage, nullable=False),
)  # fmt: skip
t_capture_archi = Table(
    "capture_archi", metadata,
    Column("grimpeur_id", Integer, primary_key=True), Column("archimonstre_id", Integer, primary_key=True),
    Column("nombre", Integer, nullable=False), Column("maj_le", Horodatage, nullable=False),
)  # fmt: skip
t_capture_boss = Table(
    "capture_boss", metadata,
    Column("grimpeur_id", Integer, primary_key=True), Column("boss_id", Integer, primary_key=True),
    Column("nombre", Integer, nullable=False), Column("maj_le", Horodatage, nullable=False),
)  # fmt: skip
t_capture_avis = Table(
    "capture_avis", metadata,
    Column("grimpeur_id", Integer, primary_key=True), Column("avis_id", Integer, primary_key=True),
    Column("capture_le", Horodatage, nullable=False),
)  # fmt: skip
t_personnages = Table(
    "archi_personnages", metadata,
    Column("grimpeur_id", Integer, primary_key=True), Column("nombre", Integer, nullable=False),
)  # fmt: skip

# genre → (table du catalogue, table des captures, colonne de l'élément)
_GENRES = {"archi": (t_archi, t_capture_archi, "archimonstre_id"), "boss": (t_boss, t_capture_boss, "boss_id")}


def _genre(genre: str):
    if genre not in _GENRES:
        raise ElementInconnu(genre)
    return _GENRES[genre]


# --- Conversions ------------------------------------------------------------------------------------------


def _zones_json(zones: tuple[Zone, ...]) -> list[dict]:
    return [{"nom": z.nom, "aire": z.aire} for z in zones]


def _grades_json(grades: tuple[Grade, ...]) -> list[dict]:
    return [dataclasses.asdict(g) for g in grades]


def _grade(d: dict) -> Grade:
    return Grade(**{**d, "resistances": tuple(d.get("resistances") or (None,) * 5)})


def _archi(r) -> Archimonstre:
    return Archimonstre(r.id, r.nom, r.etape, tuple(Zone(z["nom"], z.get("aire")) for z in r.zones), r.monstre_id,
                        r.gfx_id, r.niveau_min, r.niveau_max)


def _boss(r) -> Boss:
    return Boss(r.id, r.nom, r.etape, r.monstre_id, r.gfx_id, r.niveau)


def _avis(r) -> AvisRecherche:
    return AvisRecherche(r.id, r.slug, r.nom, r.niveau_texte, r.niveau, r.zone, r.milice, r.recompense,
                         r.recompense_type, bool(r.chasse), r.monstre_id, r.gfx_id, r.resume_html,
                         tuple(_grade(g) for g in r.grades))


# --- Postgres ---------------------------------------------------------------------------------------------


class DepotCaptures:
    def __init__(self, moteur: AsyncEngine) -> None:
        self._moteur = moteur

    async def _lignes(self, requete):
        async with self._moteur.connect() as c:
            return (await c.execute(requete)).all()

    async def archimonstres(self) -> list[Archimonstre]:
        return [_archi(r) for r in await self._lignes(select(t_archi).where(~t_archi.c.retire).order_by(t_archi.c.id))]

    async def boss(self) -> list[Boss]:
        return [_boss(r) for r in await self._lignes(select(t_boss).where(~t_boss.c.retire).order_by(t_boss.c.id))]

    async def avis(self) -> list[AvisRecherche]:
        return [_avis(r) for r in await self._lignes(select(t_avis).where(~t_avis.c.retire).order_by(t_avis.c.id))]

    async def nombres(self, grimpeur_id: int, genre: Genre) -> dict[int, int]:
        _, tc, col = _genre(genre)
        lignes = await self._lignes(select(tc.c[col], tc.c.nombre).where(tc.c.grimpeur_id == grimpeur_id))
        return {r[0]: r[1] for r in lignes}

    async def changer_nombre(self, grimpeur_id: int, genre: Genre, element_id: int, delta: int,
                             maintenant: datetime) -> int:
        """Ajoute `delta` (±) au nombre d'exemplaires, borné à [0, 999], dans une transaction ; renvoie le nouveau
        nombre. À 0, la ligne disparaît."""
        tcat, tc, col = _genre(genre)
        async with self._moteur.begin() as c:
            existe = (await c.execute(select(tcat.c.id).where(tcat.c.id == element_id, ~tcat.c.retire))).first()
            if existe is None:
                raise ElementInconnu(f"{genre} {element_id}")
            cle = (tc.c.grimpeur_id == grimpeur_id) & (tc.c[col] == element_id)
            actuel = (await c.execute(select(tc.c.nombre).where(cle).with_for_update())).scalar() or 0
            nouveau = max(0, min(EXEMPLAIRES_MAX, actuel + delta))
            if nouveau == 0:
                await c.execute(delete(tc).where(cle))
            elif actuel == 0:
                await c.execute(insert(tc).values({"grimpeur_id": grimpeur_id, col: element_id, "nombre": nouveau,
                                                   "maj_le": maintenant}).on_conflict_do_update(
                    index_elements=["grimpeur_id", col], set_={"nombre": nouveau, "maj_le": maintenant}))
            elif nouveau != actuel:
                await c.execute(update(tc).where(cle).values(nombre=nouveau, maj_le=maintenant))
            return nouveau

    async def avis_captures(self, grimpeur_id: int) -> set[int]:
        t = t_capture_avis
        return {r[0] for r in await self._lignes(select(t.c.avis_id).where(t.c.grimpeur_id == grimpeur_id))}

    async def capturer_avis(self, grimpeur_id: int, avis_id: int, capture: bool, maintenant: datetime) -> bool:
        """Idempotent ; renvoie vrai si l'état a changé."""
        t = t_capture_avis
        async with self._moteur.begin() as c:
            if (await c.execute(select(t_avis.c.id).where(t_avis.c.id == avis_id, ~t_avis.c.retire))).first() is None:
                raise ElementInconnu(f"avis {avis_id}")
            if capture:
                r = await c.execute(insert(t).values(grimpeur_id=grimpeur_id, avis_id=avis_id, capture_le=maintenant)
                                    .on_conflict_do_nothing())
            else:
                r = await c.execute(delete(t).where(t.c.grimpeur_id == grimpeur_id, t.c.avis_id == avis_id))
            return r.rowcount > 0

    async def personnages(self, grimpeur_id: int) -> int:
        t = t_personnages
        lignes = await self._lignes(select(t.c.nombre).where(t.c.grimpeur_id == grimpeur_id))
        return lignes[0][0] if lignes else 1

    async def regler_personnages(self, grimpeur_id: int, nombre: int) -> int:
        n = borne_personnages(nombre)
        async with self._moteur.begin() as c:
            await c.execute(insert(t_personnages).values(grimpeur_id=grimpeur_id, nombre=n)
                            .on_conflict_do_update(index_elements=["grimpeur_id"], set_={"nombre": n}))
        return n

    async def detenteurs(self, genre: Genre | str, element_id: int) -> dict[int, int]:
        if genre == "avis":
            t = t_capture_avis
            return {r[0]: 1 for r in await self._lignes(select(t.c.grimpeur_id).where(t.c.avis_id == element_id))}
        _, tc, col = _genre(genre)
        return {r[0]: r[1] for r in await self._lignes(select(tc.c.grimpeur_id, tc.c.nombre)
                                                       .where(tc.c[col] == element_id))}

    async def charger_catalogue(self, catalogue: Catalogue, maintenant: datetime) -> dict[str, int]:
        """Upsert de tout le catalogue dans une transaction ; ce qui n'y est plus est retiré (masqué)."""
        lots = (
            (t_archi, [{"id": a.id, "nom": a.nom, "etape": a.etape, "zones": _zones_json(a.zones),
                        "monstre_id": a.monstre_id, "gfx_id": a.gfx_id, "niveau_min": a.niveau_min,
                        "niveau_max": a.niveau_max} for a in catalogue.archis]),
            (t_boss, [{"id": b.id, "nom": b.nom, "etape": b.etape, "monstre_id": b.monstre_id, "gfx_id": b.gfx_id,
                       "niveau": b.niveau} for b in catalogue.boss]),
            (t_avis, [{"id": w.id, "slug": w.slug, "nom": w.nom, "niveau_texte": w.niveau_texte, "niveau": w.niveau,
                       "zone": w.zone, "milice": w.milice, "recompense": w.recompense,
                       "recompense_type": w.recompense_type, "chasse": w.chasse, "monstre_id": w.monstre_id,
                       "gfx_id": w.gfx_id, "resume_html": w.resume_html, "grades": _grades_json(w.grades)}
                      for w in catalogue.avis]),
        )  # fmt: skip
        comptes = {}
        async with self._moteur.begin() as c:
            for table, lignes in lots:
                ids = [r["id"] for r in lignes]
                await c.execute(update(table).where(table.c.id.not_in(ids) if ids else true()).values(retire=True))
                if table is t_avis and lignes:
                    # Un slug qui change de propriétaire : on libère l'ancien (contrainte unique) avant l'upsert.
                    await c.execute(update(table).where(table.c.id.not_in(ids))
                                    .values(slug=func.concat("retire-", table.c.id)))
                for r in lignes:
                    valeurs = {**r, "retire": False, "maj_le": maintenant}
                    await c.execute(insert(table).values(valeurs).on_conflict_do_update(
                        index_elements=["id"], set_={k: v for k, v in valeurs.items() if k != "id"}))
                comptes[table.name] = len(lignes)
        return comptes


# --- En mémoire (démonstration, tests du site) ------------------------------------------------------------


class CapturesMemoire:
    def __init__(self, catalogue: Catalogue) -> None:
        self.catalogue = catalogue
        self._nombres: dict[tuple[str, int, int], int] = {}  # (genre, grimpeur, élément) → nombre
        self._avis: set[tuple[int, int]] = set()  # (grimpeur, avis)
        self._persos: dict[int, int] = {}

    def _ids(self, genre: str) -> set[int]:
        if genre == "archi":
            return {a.id for a in self.catalogue.archis}
        if genre == "boss":
            return {b.id for b in self.catalogue.boss}
        if genre == "avis":
            return {w.id for w in self.catalogue.avis}
        raise ElementInconnu(genre)

    async def archimonstres(self) -> list[Archimonstre]:
        return list(self.catalogue.archis)

    async def boss(self) -> list[Boss]:
        return list(self.catalogue.boss)

    async def avis(self) -> list[AvisRecherche]:
        return list(self.catalogue.avis)

    async def nombres(self, grimpeur_id: int, genre: Genre) -> dict[int, int]:
        self._ids(genre)
        return {e: n for (g, gid, e), n in self._nombres.items() if g == genre and gid == grimpeur_id}

    async def changer_nombre(self, grimpeur_id: int, genre: Genre, element_id: int, delta: int,
                             maintenant: datetime) -> int:
        if element_id not in self._ids(genre) or genre == "avis":
            raise ElementInconnu(f"{genre} {element_id}")
        cle = (genre, grimpeur_id, element_id)
        n = max(0, min(EXEMPLAIRES_MAX, self._nombres.get(cle, 0) + delta))
        if n:
            self._nombres[cle] = n
        else:
            self._nombres.pop(cle, None)
        return n

    async def avis_captures(self, grimpeur_id: int) -> set[int]:
        return {a for g, a in self._avis if g == grimpeur_id}

    async def capturer_avis(self, grimpeur_id: int, avis_id: int, capture: bool, maintenant: datetime) -> bool:
        if avis_id not in self._ids("avis"):
            raise ElementInconnu(f"avis {avis_id}")
        avant = (grimpeur_id, avis_id) in self._avis
        if capture:
            self._avis.add((grimpeur_id, avis_id))
        else:
            self._avis.discard((grimpeur_id, avis_id))
        return avant != capture

    async def personnages(self, grimpeur_id: int) -> int:
        return self._persos.get(grimpeur_id, 1)

    async def regler_personnages(self, grimpeur_id: int, nombre: int) -> int:
        self._persos[grimpeur_id] = borne_personnages(nombre)
        return self._persos[grimpeur_id]

    async def detenteurs(self, genre: Genre | str, element_id: int) -> dict[int, int]:
        if genre == "avis":
            return {g: 1 for g, a in self._avis if a == element_id}
        self._ids(genre)
        return {gid: n for (g, gid, e), n in self._nombres.items() if g == genre and e == element_id}
