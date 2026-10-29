"""Le dépôt : toutes les lectures et écritures en base, derrière des fonctions simples.

Le reste du programme ne voit jamais de SQL : il appelle `depot.grimpeurs()` et reçoit des objets du
domaine. Chaque écriture se fait dans UNE transaction (`async with self._moteur.begin()`) qui écrit aussi
sa ligne de journal : soit tout est enregistré, soit rien.

Toutes les écritures reçoivent `acteur` (l'id Discord de celui qui agit) et `maintenant` (UTC) : le journal
est complet et les tests reproductibles (pas d'horloge cachée). Signatures figées : docs/LOTS.md, lot B.

Les corrections d'un admin (libellé, masquage, nature) sont rangées à part de ce que donne la source
(`corrections`, `masque_par`, `nature_origine = 'admin'`) : une reconstruction de l'étage ne les écrase pas.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlalchemy import and_, delete, exists, func, insert, literal, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as insert_pg
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from epreuve.db import tables as t
from epreuve.domaine.bareme import cascade_coche
from epreuve.domaine.fiche import Besoin, EtapeFiche, FicheQuete, Position, Prerequis
from epreuve.domaine.modeles import (
    CaseSucces,
    Categorie,
    Coches,
    ContenuEtage,
    Donjon,
    ElementRef,
    EntreeJournal,
    Etage,
    Grimpeur,
    Nature,
    Quete,
    Regles,
    Session,
    Statut,
)
from epreuve.domaine.ouverture import Bilan
from epreuve.domaine.textes import valider_pseudo

# --- Erreurs métier -------------------------------------------------------------------------------------


class ErreurDepot(Exception):
    """Une écriture refusée pour une raison compréhensible, à afficher telle quelle (en français)."""


class Introuvable(ErreurDepot):
    pass


class PseudoDejaPris(ErreurDepot):
    pass


class PasSurLaListe(ErreurDepot):
    pass


class DejaInscrit(ErreurDepot):
    pass


class EtatInvalide(ErreurDepot):
    pass


class CocheRefusee(ErreurDepot):
    """Grimpeur exclu, ou gelé avec `pause_peut_cocher` faux."""


def _contrainte(e: IntegrityError) -> str:
    """Le nom de la contrainte violée, lu dans l'erreur d'asyncpg (ou le message à défaut)."""
    cause = getattr(e.orig, "__cause__", None)
    return getattr(cause, "constraint_name", None) or str(e.orig)


# --- La fiche de quête en base (jsonb validé par pydantic, à l'écriture comme à la lecture) ---------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PrerequisBrut(_Strict):
    """Un prérequis tel que la source le donne : l'id Duffus de la quête (s'il est connu) et son nom.

    Il est résolu à la lecture : une quête de notre base → « visible » (avec NOTRE id), sinon « hors_guide ».
    """

    duffus_id: str | None = None
    nom: str


class ContenuFiche(_Strict):
    """Le contenu de `fiche_quete.contenu`. Les champs de la quête (nom, nature…) viennent de la table quete."""

    prerequis: list[PrerequisBrut] = []
    etapes: list[EtapeFiche] = []
    objets: list[Besoin] = []
    monstres: list[Besoin] = []
    positions: list[Position] = []
    pnj_depart: str | None = None  # le PNJ de départ, même sans position connue
    succes_lie: str | None = None
    recompenses: list[str] = []
    infos_rapides: list[str] = []  # « Combats en groupe ×2 », « Donjon : X »… (infos rapides de Duffus)


SourceFiche = Literal["duffus", "duffus+dofusdb", "dofusdb"]
_FICHE = TypeAdapter(ContenuFiche)


def contenu_fiche_json(contenu: ContenuFiche) -> dict:
    """Pour l'écriture (contenu/ecrire.py) : revalidé, puis converti en JSON."""
    return _FICHE.dump_python(_FICHE.validate_python(contenu), mode="json")


# --- Conversions ligne de base → objet du domaine ---------------------------------------------------------


def _etage(r) -> Etage:
    return Etage(r.id, r.numero, r.nom, r.niveau_min, r.niveau_max, r.level_cap, r.statut, r.ouvert_le,
                 r.date_plancher_suivant, r.palier_manuel, r.ambiance_url)


def _donjon(r) -> Donjon:
    return Donjon(r.id, r.etage_id, r.corrections.get("nom", r.nom), r.niveau, r.ordre, r.bloc, r.dofusdb_id,
                  r.origine, r.succes_source, r.masque)


def _case(r) -> CaseSucces:
    return CaseSucces(r.id, r.donjon_id, r.ordre, r.corrections.get("nom", r.nom),
                      r.corrections.get("condition", r.condition), r.est_classique, r.masquee)


def _quete(r) -> Quete:
    return Quete(r.id, r.etage_id, r.corrections.get("nom", r.nom), r.niveau, r.bloc, r.ordre, r.nature,
                 r.nature_origine, tuple(r.dofus or ()), r.jusqu_ou, r.a_lier, bool(r.a_une_fiche), r.masquee,
                 r.source_fiche)


def _grimpeur(r) -> Grimpeur:
    return Grimpeur(r.id, r.discord_user_id, r.nom_discord, r.pseudo_ig, r.classe, r.statut, r.niveau_declare,
                    r.inscrit_le, r.prologue_vu_le is not None)


def _entree(r) -> EntreeJournal:
    return EntreeJournal(r.id, r.horodatage, r.acteur_discord_id, r.type, r.grimpeur_id, r.etage_id,
                         dict(r.details), r.public)


def _cle(ref: ElementRef) -> str:
    return f"{ref.type}:{ref.id}"


# « A une fiche » : une fiche Duffus existe, ou une fiche DofusDB construite (avec des étapes) ; une ligne
# DofusDB vide, c'est « Fiche détaillée indisponible ». `_SOURCE_FICHE` : d'où vient la fiche (revue admin).
_A_UNE_FICHE = exists().where(and_(t.fiche_quete.c.quete_id == t.quete.c.id, or_(
    t.fiche_quete.c.source != "dofusdb",
    func.jsonb_array_length(t.fiche_quete.c.contenu["etapes"]) > 0))).label("a_une_fiche")
_SOURCE_FICHE = (select(t.fiche_quete.c.source).where(t.fiche_quete.c.quete_id == t.quete.c.id)
                 .scalar_subquery().label("source_fiche"))
_TYPES_COCHE = ("coche", "coche_donjon")


class Depot:
    def __init__(self, moteur: AsyncEngine) -> None:
        self._moteur = moteur

    @property
    def moteur(self) -> AsyncEngine:
        """Pour les modules du lot E, qui ont leur propre dépôt de lecture sur la même base."""
        return self._moteur

    # --- Santé ------------------------------------------------------------------------------------------

    async def ping(self) -> bool:
        try:
            async with self._moteur.connect() as c:
                await c.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001 — toute erreur veut dire « base injoignable »
            return False

    # --- Lecture : étages et contenu ----------------------------------------------------------------------

    async def etages(self) -> list[Etage]:
        async with self._moteur.connect() as c:
            return [_etage(r) for r in await c.execute(select(t.etage).order_by(t.etage.c.numero))]

    async def etage_par_numero(self, numero: int) -> Etage | None:
        async with self._moteur.connect() as c:
            r = (await c.execute(select(t.etage).where(t.etage.c.numero == numero))).one_or_none()
        return _etage(r) if r else None

    @staticmethod
    async def _contenu_brut(c: AsyncConnection, etage_id: int
                            ) -> tuple[Etage, list[Donjon], list[CaseSucces], list[Quete]]:
        e = (await c.execute(select(t.etage).where(t.etage.c.id == etage_id))).one_or_none()
        if e is None:
            raise Introuvable("étage introuvable")
        donjons = await c.execute(select(t.donjon).where(t.donjon.c.etage_id == etage_id)
                                  .order_by(t.donjon.c.ordre, t.donjon.c.id))
        cases = await c.execute(select(t.case_succes).join(t.donjon).where(t.donjon.c.etage_id == etage_id)
                                .order_by(t.case_succes.c.donjon_id, t.case_succes.c.ordre))
        quetes = await c.execute(select(t.quete, _A_UNE_FICHE, _SOURCE_FICHE).where(t.quete.c.etage_id == etage_id)
                                 .order_by(t.quete.c.ordre, t.quete.c.id))
        return (_etage(e), [_donjon(r) for r in donjons], [_case(r) for r in cases], [_quete(r) for r in quetes])

    async def contenu_brut(self, etage_id: int) -> tuple[Etage, list[Donjon], list[CaseSucces], list[Quete]]:
        """Masqués compris (revue admin)."""
        async with self._moteur.connect() as c:
            return await self._contenu_brut(c, etage_id)

    async def contenu_etage(self, etage_id: int) -> ContenuEtage:
        """Visible seulement (ContenuEtage.visible)."""
        return ContenuEtage.visible(*await self.contenu_brut(etage_id))

    async def alertes_etage(self, etage_id: int) -> list[str]:
        """Les alertes de la dernière construction."""
        async with self._moteur.connect() as c:
            r = (await c.execute(select(t.etage.c.alertes).where(t.etage.c.id == etage_id))).one_or_none()
        if r is None:
            raise Introuvable("étage introuvable")
        return list(r.alertes)

    async def coches_etage(self, etage_id: int) -> dict[int, Coches]:
        cases: dict[int, set[int]] = defaultdict(set)
        quetes: dict[int, set[int]] = defaultdict(set)
        async with self._moteur.connect() as c:
            for r in await c.execute(
                    select(t.coche_case.c.grimpeur_id, t.coche_case.c.case_id)
                    .select_from(t.coche_case.join(t.case_succes).join(t.donjon))
                    .where(t.donjon.c.etage_id == etage_id)):
                cases[r.grimpeur_id].add(r.case_id)
            for r in await c.execute(
                    select(t.coche_quete.c.grimpeur_id, t.coche_quete.c.quete_id)
                    .select_from(t.coche_quete.join(t.quete)).where(t.quete.c.etage_id == etage_id)):
                quetes[r.grimpeur_id].add(r.quete_id)
        return {g: Coches(g, frozenset(cases[g]), frozenset(quetes[g])) for g in sorted(cases.keys() | quetes)}

    # --- Lecture : grimpeurs, liste, journal ----------------------------------------------------------------

    async def grimpeurs(self) -> list[Grimpeur]:
        async with self._moteur.connect() as c:
            return [_grimpeur(r) for r in await c.execute(select(t.grimpeur).order_by(t.grimpeur.c.id))]

    async def grimpeur(self, grimpeur_id: int) -> Grimpeur | None:
        async with self._moteur.connect() as c:
            r = (await c.execute(select(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id))).one_or_none()
        return _grimpeur(r) if r else None

    async def grimpeur_par_discord(self, discord_user_id: int) -> Grimpeur | None:
        async with self._moteur.connect() as c:
            r = (await c.execute(select(t.grimpeur).where(t.grimpeur.c.discord_user_id == discord_user_id))
                 ).one_or_none()
        return _grimpeur(r) if r else None

    async def liste_officielle(self) -> dict[int, Statut]:
        async with self._moteur.connect() as c:
            return {r.discord_user_id: r.statut_initial for r in await c.execute(select(t.liste_officielle))}

    async def dernieres_activites(self) -> dict[int, datetime]:
        """Date de la dernière coche de chaque grimpeur (T-29), lue dans le journal."""
        async with self._moteur.connect() as c:
            rs = await c.execute(
                select(t.journal.c.grimpeur_id, func.max(t.journal.c.horodatage).label("derniere"))
                .where(t.journal.c.type.in_(_TYPES_COCHE), t.journal.c.grimpeur_id.is_not(None))
                .group_by(t.journal.c.grimpeur_id))
            return {r.grimpeur_id: r.derniere for r in rs}

    async def bilan(self, etage_id: int) -> Bilan | None:
        async with self._moteur.connect() as c:
            r = (await c.execute(select(t.bilan_etage).where(t.bilan_etage.c.etage_id == etage_id))).one_or_none()
        if r is None:
            return None
        return Bilan(r.fige_le, r.actifs, r.palier, r.score, dict(r.detail), r.force, r.motif)

    async def journal(self, limite: int = 200, grimpeur_id: int | None = None, etage_id: int | None = None,
                      type_: str | None = None) -> list[EntreeJournal]:
        q = select(t.journal).order_by(t.journal.c.horodatage.desc(), t.journal.c.id.desc()).limit(limite)
        if grimpeur_id is not None:
            q = q.where(t.journal.c.grimpeur_id == grimpeur_id)
        if etage_id is not None:
            q = q.where(t.journal.c.etage_id == etage_id)
        if type_ is not None:
            q = q.where(t.journal.c.type == type_)
        async with self._moteur.connect() as c:
            return [_entree(r) for r in await c.execute(q)]

    # --- Écritures : outils internes ------------------------------------------------------------------------

    @staticmethod
    async def _journaliser(c: AsyncConnection, type_: str, acteur: int | None, maintenant: datetime,
                           details: dict, grimpeur_id: int | None = None, etage_id: int | None = None,
                           public: bool = False) -> None:
        await c.execute(insert(t.journal).values(
            horodatage=maintenant, acteur_discord_id=acteur, type=type_, grimpeur_id=grimpeur_id,
            etage_id=etage_id, details=details, public=public,
        ))  # fmt: skip

    @staticmethod
    async def _grimpeur_verrouille(c: AsyncConnection, grimpeur_id: int) -> Grimpeur:
        r = (await c.execute(select(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id).with_for_update())
             ).one_or_none()
        if r is None:
            raise Introuvable("grimpeur introuvable")
        return _grimpeur(r)

    @staticmethod
    def _motif(motif: str | None) -> str | None:
        return (motif or "").strip() or None

    # --- Écritures : le grimpeur ------------------------------------------------------------------------------

    async def creer_grimpeur(self, discord_user_id: int, nom_discord: str, pseudo: str, classe: str | None,
                             niveau_declare: int | None, maintenant: datetime, *,
                             liste_obligatoire: bool = True) -> Grimpeur:
        """PasSurLaListe, DejaInscrit, PseudoDejaPris ; statut = statut initial de la liste officielle.

        `liste_obligatoire` reprend `Regles.liste_officielle_obligatoire` (T-19) : faux, un membre hors liste
        s'inscrit actif.
        """
        pseudo = valider_pseudo(pseudo)
        Grimpeur(0, discord_user_id, nom_discord, pseudo, classe, "actif", niveau_declare, maintenant)  # contrôle
        try:
            async with self._moteur.begin() as c:
                liste = (await c.execute(select(t.liste_officielle.c.statut_initial).where(
                    t.liste_officielle.c.discord_user_id == discord_user_id))).one_or_none()
                if liste is None and liste_obligatoire:
                    raise PasSurLaListe("tu n'es pas sur la liste officielle : envoie ta validation en MP à Shadoaze")
                statut = liste.statut_initial if liste else "actif"
                r = (await c.execute(insert(t.grimpeur).values(
                    discord_user_id=discord_user_id, nom_discord=nom_discord, pseudo_ig=pseudo, classe=classe,
                    statut=statut, niveau_declare=niveau_declare, inscrit_le=maintenant,
                ).returning(t.grimpeur))).one()  # fmt: skip
                await self._journaliser(c, "inscription", discord_user_id, maintenant,
                                        {"pseudo": pseudo, "classe": classe, "statut": statut},
                                        grimpeur_id=r.id, public=True)
                return _grimpeur(r)
        except IntegrityError as e:
            raise self._traduire(e, pseudo) from None

    @staticmethod
    def _traduire(e: IntegrityError, pseudo: str) -> ErreurDepot:
        nom = _contrainte(e)
        if "grimpeur_pseudo_unique" in nom:
            return PseudoDejaPris(f"le pseudo « {pseudo} » est déjà pris")
        if "grimpeur_discord_user_id_key" in nom:
            return DejaInscrit("ce compte Discord a déjà une fiche")
        raise e

    async def maj_nom_discord(self, discord_user_id: int, nom_discord: str) -> None:
        """À chaque connexion (T-20) ; sans effet si le membre n'a pas de fiche."""
        async with self._moteur.begin() as c:
            await c.execute(update(t.grimpeur).where(t.grimpeur.c.discord_user_id == discord_user_id)
                            .values(nom_discord=nom_discord))

    async def marquer_prologue_vu(self, grimpeur_id: int, maintenant: datetime) -> None:
        """Retient que le grimpeur a passé le prologue (idempotent : la première date reste)."""
        async with self._moteur.begin() as c:
            await c.execute(update(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id,
                                                     t.grimpeur.c.prologue_vu_le.is_(None))
                            .values(prologue_vu_le=maintenant))

    async def modifier_grimpeur(self, grimpeur_id: int, acteur: int, maintenant: datetime, *,
                                pseudo: str | None = None, classe: str | None = None,
                                niveau_declare: int | None = None) -> Grimpeur:
        """Les champs à None ne changent pas. PseudoDejaPris, Introuvable, ValueError (valeur invalide)."""
        valeurs: dict[str, object] = {}
        if pseudo is not None:
            valeurs["pseudo_ig"] = valider_pseudo(pseudo)
        if classe is not None:
            valeurs["classe"] = classe
        if niveau_declare is not None:
            if not 1 <= niveau_declare <= 200:
                raise ValueError("le niveau va de 1 à 200")
            valeurs["niveau_declare"] = niveau_declare
        try:
            async with self._moteur.begin() as c:
                avant = await self._grimpeur_verrouille(c, grimpeur_id)
                if "classe" in valeurs:
                    Grimpeur(0, 0, "", avant.pseudo, classe, "actif", None, maintenant)  # classe contrôlée
                if not valeurs:
                    return avant
                r = (await c.execute(update(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id).values(**valeurs)
                                     .returning(t.grimpeur))).one()
                await self._journaliser(c, "fiche_modifiee", acteur, maintenant, {
                    k: {"avant": getattr(avant, "pseudo" if k == "pseudo_ig" else k), "apres": v}
                    for k, v in valeurs.items()
                }, grimpeur_id=grimpeur_id, public=acteur == avant.discord_user_id)  # fmt: skip
                return _grimpeur(r)
        except IntegrityError as e:
            raise self._traduire(e, str(valeurs.get("pseudo_ig", ""))) from None

    # --- Écritures : les coches -----------------------------------------------------------------------------

    async def _preparer_coche(self, c: AsyncConnection, grimpeur_id: int, acteur: int, regles: Regles,
                              motif: str | None) -> tuple[Grimpeur, str | None]:
        g = await self._grimpeur_verrouille(c, grimpeur_id)
        if g.statut == "exclu":
            raise CocheRefusee("ta participation est suspendue")
        if g.statut == "pause" and not regles.pause_peut_cocher:
            raise CocheRefusee("un grimpeur en pause ne peut pas cocher")
        motif = self._motif(motif)
        if acteur != g.discord_user_id and motif is None:
            raise ValueError("un admin qui modifie la fiche d'un autre doit donner un motif")
        return g, motif

    @staticmethod
    async def _etage_de(c: AsyncConnection, ref: ElementRef) -> int:
        """L'étage d'un élément cochable : visible, d'un étage ouvert ou terminé. Introuvable sinon."""
        if ref.type == "case":
            q = (select(t.donjon.c.etage_id).select_from(t.case_succes.join(t.donjon).join(t.etage))
                 .where(t.case_succes.c.id == ref.id, t.case_succes.c.masquee.is_(False),
                        t.donjon.c.masque.is_(False)))
        else:
            q = (select(t.quete.c.etage_id).select_from(t.quete.join(t.etage))
                 .where(t.quete.c.id == ref.id, t.quete.c.masquee.is_(False)))
        r = (await c.execute(q.where(t.etage.c.statut.in_(("ouvert", "termine"))))).one_or_none()
        if r is None:
            raise Introuvable("élément introuvable")
        return r.etage_id

    @staticmethod
    async def _appliquer(c: AsyncConnection, grimpeur_id: int, ref: ElementRef, cochee: bool, acteur: int,
                         maintenant: datetime) -> bool:
        """Coche ou décoche une ligne ; vrai si la base a vraiment changé (idempotent)."""
        table, col = (t.coche_case, "case_id") if ref.type == "case" else (t.coche_quete, "quete_id")
        if cochee:
            q = (insert_pg(table).values(grimpeur_id=grimpeur_id, **{col: ref.id}, cochee_le=maintenant,
                                         cochee_par=acteur)
                 .on_conflict_do_nothing().returning(table.c.grimpeur_id))
        else:
            q = (delete(table).where(table.c.grimpeur_id == grimpeur_id, table.c[col] == ref.id)
                 .returning(table.c.grimpeur_id))
        return (await c.execute(q)).first() is not None

    async def cocher(self, grimpeur_id: int, ref: ElementRef, cochee: bool, acteur: int, maintenant: datetime,
                     regles: Regles, motif: str | None = None) -> tuple[ElementRef, ...]:
        """Les éléments réellement changés, cascade T-16 comprise, dans UNE transaction ; idempotent."""
        async with self._moteur.begin() as c:
            g, motif = await self._preparer_coche(c, grimpeur_id, acteur, regles, motif)
            etage_id = await self._etage_de(c, ref)
            contenu = ContenuEtage.visible(*await self._contenu_brut(c, etage_id))
            changes = tuple([r for r in (ref, *cascade_coche(contenu, ref, cochee, regles))
                             if await self._appliquer(c, grimpeur_id, r, cochee, acteur, maintenant)])
            if changes:
                details: dict[str, object] = {"element": _cle(ref), "cochee": cochee,
                                              "changes": [_cle(r) for r in changes]}
                if motif is not None:
                    details["motif"] = motif
                await self._journaliser(c, "coche", acteur, maintenant, details, grimpeur_id=grimpeur_id,
                                        etage_id=etage_id, public=acteur == g.discord_user_id)
            return changes

    async def cocher_donjon(self, grimpeur_id: int, donjon_id: int, acteur: int, maintenant: datetime,
                            regles: Regles, motif: str | None = None) -> int:
        """Coche les cases visibles du donjon (« Tout le donjon ») ; le nombre de cases nouvellement cochées."""
        async with self._moteur.begin() as c:
            g, motif = await self._preparer_coche(c, grimpeur_id, acteur, regles, motif)
            d = (await c.execute(select(t.donjon.c.etage_id).select_from(t.donjon.join(t.etage)).where(
                t.donjon.c.id == donjon_id, t.donjon.c.masque.is_(False),
                t.etage.c.statut.in_(("ouvert", "termine"))))).one_or_none()
            if d is None:
                raise Introuvable("donjon introuvable")
            contenu = ContenuEtage.visible(*await self._contenu_brut(c, d.etage_id))
            n = 0
            for case in contenu.cases_du_donjon(donjon_id):
                n += await self._appliquer(c, grimpeur_id, ElementRef("case", case.id), True, acteur, maintenant)
            if n:
                details: dict[str, object] = {"donjon": donjon_id, "cases": n}
                if motif is not None:
                    details["motif"] = motif
                await self._journaliser(c, "coche_donjon", acteur, maintenant, details, grimpeur_id=grimpeur_id,
                                        etage_id=d.etage_id, public=acteur == g.discord_user_id)
            return n

    # --- Écritures d'admin : grimpeurs ---------------------------------------------------------------------

    async def ajouter_liste(self, discord_ids: list[int], statut_initial: Literal["actif", "pause"], acteur: int,
                            maintenant: datetime) -> list[int]:
        """Les ids réellement ajoutés (sans doublon, dans l'ordre donné)."""
        if statut_initial not in ("actif", "pause"):
            raise ValueError("statut initial : actif ou pause")
        ids = list(dict.fromkeys(discord_ids))
        if not ids:
            return []
        async with self._moteur.begin() as c:
            rs = await c.execute(insert_pg(t.liste_officielle).values([
                {"discord_user_id": i, "statut_initial": statut_initial, "ajoute_par": acteur, "ajoute_le": maintenant}
                for i in ids
            ]).on_conflict_do_nothing().returning(t.liste_officielle.c.discord_user_id))
            ajoutes = {r.discord_user_id for r in rs}
            ajoutes_ordonnes = [i for i in ids if i in ajoutes]
            if ajoutes_ordonnes:
                await self._journaliser(c, "liste_ajout", acteur, maintenant,
                                        {"nombre": len(ajoutes_ordonnes), "statut_initial": statut_initial})
            return ajoutes_ordonnes

    async def changer_statut(self, grimpeur_id: int, statut: Statut, motif: str | None, acteur: int,
                             maintenant: datetime) -> Grimpeur:
        """Geler, réintégrer, exclure (motif obligatoire pour exclure). Journal non public (modération)."""
        if statut not in ("actif", "pause", "exclu"):
            raise ValueError(f"statut inconnu : {statut!r}")
        motif = self._motif(motif)
        if statut == "exclu" and motif is None:
            raise ValueError("exclure demande un motif")
        async with self._moteur.begin() as c:
            avant = await self._grimpeur_verrouille(c, grimpeur_id)
            r = (await c.execute(update(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id).values(statut=statut)
                                 .returning(t.grimpeur))).one()
            await self._journaliser(c, "statut", acteur, maintenant,
                                    {"avant": avant.statut, "apres": statut, "motif": motif},
                                    grimpeur_id=grimpeur_id)
            return _grimpeur(r)

    # --- Écritures d'admin : étages --------------------------------------------------------------------------

    async def _maj_etage(self, etage_id: int, valeurs: dict, type_: str, details: dict, acteur: int,
                         maintenant: datetime, corrections: dict | None = None) -> Etage:
        async with self._moteur.begin() as c:
            if corrections:
                col = t.etage.c.corrections
                valeurs = {**valeurs, "corrections": col.op("||")(literal(corrections, col.type))}
            r = (await c.execute(update(t.etage).where(t.etage.c.id == etage_id).values(**valeurs, maj_le=maintenant)
                                 .returning(t.etage))).one_or_none()
            if r is None:
                raise Introuvable("étage introuvable")
            await self._journaliser(c, type_, acteur, maintenant, details, etage_id=etage_id, public=True)
            return _etage(r)

    async def regler_palier(self, etage_id: int, palier: int | None, motif: str, acteur: int,
                            maintenant: datetime) -> Etage:
        """Un palier manuel (≥ 1, motif obligatoire), ou None pour revenir à la formule."""
        motif_ = self._motif(motif)
        if palier is not None and (palier < 1 or motif_ is None):
            raise ValueError("palier manuel : un entier ≥ 1 et un motif")
        return await self._maj_etage(etage_id, {"palier_manuel": palier}, "palier",
                                     {"palier": palier, "motif": motif_}, acteur, maintenant)

    async def regler_date_plancher(self, etage_id: int, date: datetime | None, acteur: int,
                                   maintenant: datetime) -> Etage:
        if date is not None and date.utcoffset() is None:
            raise ValueError("la date plancher doit porter un fuseau")
        return await self._maj_etage(etage_id, {"date_plancher_suivant": date}, "date_plancher",
                                     {"date": date.isoformat() if date else None}, acteur, maintenant)

    async def regler_etage(self, etage_id: int, acteur: int, maintenant: datetime, *, nom: str | None = None,
                           ambiance_url: str | None = None, level_cap: int | None = None) -> Etage:
        """Nom, image d'ambiance, cap (T-04, T-28). Les choix survivent à une reconstruction (`corrections`).

        `ambiance_url=""` retire l'image. Aucun lien vers duffus.fr (EX-70) ; https seulement.
        """
        valeurs: dict[str, object] = {}
        if nom is not None:
            if not nom.strip():
                raise ValueError("le nom ne peut pas être vide")
            valeurs["nom"] = nom.strip()
        if ambiance_url is not None:
            url = ambiance_url.strip() or None
            interne = url is not None and re.fullmatch(r"/etages/\d+/image", url) is not None
            if url is not None and not interne and (not url.startswith("https://") or "duffus" in url.lower()):
                raise ValueError("image d'ambiance : une adresse https ou /etages/N/image, jamais duffus.fr")
            valeurs["ambiance_url"] = url
        if level_cap is not None:
            if not 1 <= level_cap <= 200:
                raise ValueError("le cap va de 1 à 200")
            valeurs["level_cap"] = level_cap
        if not valeurs:
            raise ValueError("rien à changer")
        return await self._maj_etage(etage_id, valeurs, "etage_regle", dict(valeurs), acteur, maintenant,
                                     corrections={k: True for k in valeurs})

    async def ouvrir_etage(self, numero: int, bilan_precedent: Bilan, acteur: int, maintenant: datetime) -> Etage:
        """Une transaction, verrou FOR UPDATE sur les étages : précédent → termine + bilan, numero → ouvert.

        EtatInvalide si `numero` n'est pas scellé, ou si un autre admin vient d'ouvrir.
        """
        async with self._moteur.begin() as c:
            etages = [_etage(r) for r in await c.execute(select(t.etage).order_by(t.etage.c.numero).with_for_update())]
            cible = next((e for e in etages if e.numero == numero), None)
            if cible is None:
                raise Introuvable(f"l'étage {numero} n'existe pas")
            if cible.statut != "scelle":
                raise EtatInvalide(f"l'étage {numero} est déjà ouvert : un autre admin vient sans doute de l'ouvrir")
            for e in etages:
                if e.statut == "ouvert":
                    await c.execute(update(t.etage).where(t.etage.c.id == e.id).values(statut="termine",
                                                                                       maj_le=maintenant))
                    b = bilan_precedent
                    await c.execute(insert(t.bilan_etage).values(
                        etage_id=e.id, fige_le=b.fige_le, actifs=b.actifs, palier=b.palier, score=b.score,
                        detail=dict(b.points_par_categorie), force=b.force, motif=b.motif))
            r = (await c.execute(update(t.etage).where(t.etage.c.id == cible.id)
                                 .values(statut="ouvert", ouvert_le=maintenant, maj_le=maintenant)
                                 .returning(t.etage))).one()
            await self._journaliser(c, "ouverture", acteur, maintenant, {
                "numero": numero, "score": bilan_precedent.score, "palier": bilan_precedent.palier,
                "force": bilan_precedent.force, "motif": bilan_precedent.motif,
            }, etage_id=cible.id, public=True)  # fmt: skip
            return _etage(r)

    # --- Écritures d'admin : revue du contenu ----------------------------------------------------------------

    async def _corriger(self, table, id_: int, acteur: int, maintenant: datetime, valeurs: dict,
                        corrections: dict, quoi: str):
        """Met à jour une ligne de contenu ; les libellés vont dans `corrections` (survivent à la reconstruction)."""
        if corrections:
            valeurs["corrections"] = table.c.corrections.op("||")(literal(corrections, table.c.corrections.type))
        if not valeurs:
            raise ValueError("rien à changer")
        async with self._moteur.begin() as c:
            avant = (await c.execute(select(table).where(table.c.id == id_).with_for_update())).one_or_none()
            if avant is None:
                raise Introuvable(f"{quoi} introuvable")
            r = (await c.execute(update(table).where(table.c.id == id_).values(**valeurs).returning(table))).one()
            if table is t.case_succes:
                etage_id = (await c.execute(select(t.donjon.c.etage_id).where(t.donjon.c.id == r.donjon_id))).scalar()
            else:
                etage_id = r.etage_id
            details = {k: v for k, v in valeurs.items() if k != "corrections"} | corrections
            await self._journaliser(c, "contenu_admin", acteur, maintenant, {"quoi": quoi, "id": id_, **details},
                                    etage_id=etage_id, public=False)
            return r

    @staticmethod
    def _masquage(champ: str, masque: bool | None) -> dict:
        if masque is None:
            return {}
        return {champ: masque, "masque_par": "admin" if masque else None}

    @staticmethod
    def _libelles(**libelles: str | None) -> dict:
        resultat = {}
        for k, v in libelles.items():
            if v is not None:
                if not v.strip():
                    raise ValueError(f"{k} ne peut pas être vide")
                resultat[k] = v.strip()
        return resultat

    async def modifier_quete(self, quete_id: int, acteur: int, maintenant: datetime, *, nature: Nature | None = None,
                             motif: str | None = None, masquee: bool | None = None, nom: str | None = None) -> Quete:
        """Changer la nature exige un motif (origine « admin »). Masquer, corriger le nom."""
        valeurs = self._masquage("masquee", masquee)
        if nature is not None:
            motif_ = self._motif(motif)
            if nature not in ("principale", "secondaire") or motif_ is None:
                raise ValueError("changer la nature exige une nature valide et un motif")
            valeurs |= {"nature": nature, "nature_origine": "admin", "nature_motif": motif_}
        await self._corriger(t.quete, quete_id, acteur, maintenant, valeurs, self._libelles(nom=nom), "quête")
        async with self._moteur.connect() as c:
            requete = select(t.quete, _A_UNE_FICHE, _SOURCE_FICHE).where(t.quete.c.id == quete_id)
            return _quete((await c.execute(requete)).one())

    async def modifier_donjon(self, donjon_id: int, acteur: int, maintenant: datetime, *,
                              masque: bool | None = None, nom: str | None = None) -> Donjon:
        return _donjon(await self._corriger(t.donjon, donjon_id, acteur, maintenant, self._masquage("masque", masque),
                                            self._libelles(nom=nom), "donjon"))

    async def modifier_case(self, case_id: int, acteur: int, maintenant: datetime, *, masquee: bool | None = None,
                            nom: str | None = None, condition: str | None = None) -> CaseSucces:
        corrections = self._libelles(nom=nom)
        if condition is not None:
            corrections["condition"] = condition.strip()  # une condition peut être vide
        return _case(await self._corriger(t.case_succes, case_id, acteur, maintenant,
                                          self._masquage("masquee", masquee), corrections, "case"))

    async def donjons_disponibles(self) -> list[tuple[str, str, int | None]]:
        """(duffus_id, nom, niveau) de l'aspiration en base, par niveau puis nom."""
        async with self._moteur.connect() as c:
            rs = await c.execute(select(t.donjon_disponible).order_by(
                t.donjon_disponible.c.niveau.asc().nulls_last(), t.donjon_disponible.c.nom))
            return [(r.duffus_id, r.nom, r.niveau) for r in rs]

    async def ajouter_donjon(self, etage_id: int, duffus_id: str, acteur: int, maintenant: datetime) -> Donjon:
        """T-03 : origine « admin », avec ses succès. Un donjon déjà présent mais masqué est démasqué."""
        async with self._moteur.begin() as c:
            dispo = (await c.execute(select(t.donjon_disponible).where(t.donjon_disponible.c.duffus_id == duffus_id))
                     ).one_or_none()
            if dispo is None:
                raise Introuvable("donjon absent de l'aspiration")
            e = (await c.execute(select(t.etage.c.id).where(t.etage.c.id == etage_id).with_for_update())).one_or_none()
            if e is None:
                raise Introuvable("étage introuvable")
            deja = (await c.execute(select(t.donjon).where(t.donjon.c.etage_id == etage_id,
                                                           t.donjon.c.duffus_id == duffus_id))).one_or_none()
            if deja is not None:
                if not deja.masque:
                    raise EtatInvalide("ce donjon est déjà dans l'étage")
                r = (await c.execute(update(t.donjon).where(t.donjon.c.id == deja.id).values(
                    masque=False, masque_par=None, origine="admin").returning(t.donjon))).one()
            else:
                ordre = (await c.execute(select(func.coalesce(func.max(t.donjon.c.ordre), 0))
                                         .where(t.donjon.c.etage_id == etage_id))).scalar() + 1
                r = (await c.execute(insert(t.donjon).values(
                    etage_id=etage_id, nom=dispo.nom, niveau=dispo.niveau, ordre=ordre, bloc=None, duffus_id=duffus_id,
                    dofusdb_id=dispo.dofusdb_id, origine="admin", succes_source=dispo.succes_source, masque=False,
                ).returning(t.donjon))).one()  # fmt: skip
                for i, s in enumerate(dispo.succes, 1):
                    await c.execute(insert(t.case_succes).values(
                        donjon_id=r.id, ordre=i, nom=s["nom"], condition=s.get("condition", ""),
                        est_classique=bool(s.get("est_classique")), duffus_id=s.get("id"), masquee=False))
            await self._journaliser(c, "contenu_admin", acteur, maintenant,
                                    {"quoi": "donjon_ajoute", "duffus_id": duffus_id, "nom": dispo.nom},
                                    etage_id=etage_id)
            return _donjon(r)

    # --- Fiches de quête ---------------------------------------------------------------------------------------

    async def fiche_quete(self, quete_id: int) -> FicheQuete | None:
        """Brute : appeler `masquer_prerequis_scelles` avant de la rendre à un non-admin."""
        async with self._moteur.connect() as c:
            r = (await c.execute(
                select(t.quete, t.fiche_quete.c.source, t.fiche_quete.c.contenu, t.etage.c.numero)
                .select_from(t.quete.join(t.fiche_quete).join(t.etage))
                .where(t.quete.c.id == quete_id))).one_or_none()
            if r is None:
                return None
            contenu = _FICHE.validate_python(r.contenu)
            ids = [p.duffus_id for p in contenu.prerequis if p.duffus_id]
            connues = {x.duffus_id: x.id for x in await c.execute(
                select(t.quete.c.duffus_id, t.quete.c.id).where(t.quete.c.duffus_id.in_(ids)))} if ids else {}
        prerequis = tuple(
            Prerequis(connues[p.duffus_id], p.nom, "visible") if p.duffus_id in connues
            else Prerequis(None, p.nom, "hors_guide")
            for p in contenu.prerequis
        )
        return FicheQuete(
            quete_id=r.id, etage_numero=r.numero, nom=r.corrections.get("nom", r.nom), niveau=r.niveau, bloc=r.bloc,
            nature=r.nature, dofus=tuple(r.dofus or ()), jusqu_ou=r.jusqu_ou, a_lier=r.a_lier, prerequis=prerequis,
            etapes=tuple(contenu.etapes), objets=tuple(contenu.objets), monstres=tuple(contenu.monstres),
            positions=tuple(contenu.positions), succes_lie=contenu.succes_lie,
            recompenses=tuple(contenu.recompenses), source=r.source, pnj_depart_connu=contenu.pnj_depart,
            infos_rapides=tuple(contenu.infos_rapides),
        )  # fmt: skip

    async def etapes_suivies(self, grimpeur_id: int, quete_id: int) -> frozenset[int]:
        """Les numéros d'étapes que ce grimpeur a cochées sur cette quête (suivi personnel, sans points)."""
        async with self._moteur.connect() as c:
            return frozenset(r.ordre for r in await c.execute(
                select(t.suivi_etape.c.ordre).where(t.suivi_etape.c.grimpeur_id == grimpeur_id,
                                                    t.suivi_etape.c.quete_id == quete_id)))

    async def suivre_etape(self, grimpeur_id: int, quete_id: int, ordre: int, faite: bool,
                           maintenant: datetime) -> None:
        """Coche ou décoche une étape ; idempotent. Ne touche jamais à `coche_quete` : la quête n'est pas
        cochée pour autant, même si c'est la dernière étape. Le contrôle des droits est fait par l'appelant."""
        async with self._moteur.begin() as c:
            if faite:
                await c.execute(insert_pg(t.suivi_etape).values(
                    grimpeur_id=grimpeur_id, quete_id=quete_id, ordre=ordre, cochee_le=maintenant,
                ).on_conflict_do_nothing())
            else:
                await c.execute(delete(t.suivi_etape).where(
                    t.suivi_etape.c.grimpeur_id == grimpeur_id, t.suivi_etape.c.quete_id == quete_id,
                    t.suivi_etape.c.ordre == ordre))

    async def etage_des_quetes(self) -> dict[int, int]:
        """id de quête → numéro d'étage, pour `masquer_prerequis_scelles`."""
        async with self._moteur.connect() as c:
            return {r.id: r.numero for r in await c.execute(select(t.quete.c.id, t.etage.c.numero).join(t.etage))}

    async def quetes_sans_fiche(self, etage_id: int) -> list[Quete]:
        """Les quêtes visibles sans fiche Duffus (le repli), à signaler à Marceau."""
        _, _, _, quetes = await self.contenu_brut(etage_id)
        return [q for q in quetes if not q.masquee and not q.a_une_fiche]

    # --- Sessions ----------------------------------------------------------------------------------------------

    async def creer_session(self, id_hache: bytes, discord_user_id: int, nom_discord: str, est_admin: bool,
                            jeton_oauth: str, csrf: str, maintenant: datetime, duree: timedelta) -> None:
        async with self._moteur.begin() as c:
            await c.execute(insert(t.session).values(
                id_hache=id_hache, discord_user_id=discord_user_id, nom_discord=nom_discord, est_admin=est_admin,
                roles_verifies_le=maintenant, cree_le=maintenant, expire_le=maintenant + duree,
                jeton_oauth=jeton_oauth, csrf=csrf))  # fmt: skip

    async def session(self, id_hache: bytes, maintenant: datetime) -> Session | None:
        """None si absente ou expirée."""
        async with self._moteur.connect() as c:
            r = (await c.execute(select(t.session).where(t.session.c.id_hache == id_hache,
                                                         t.session.c.expire_le > maintenant))).one_or_none()
        if r is None:
            return None
        return Session(r.discord_user_id, r.nom_discord, r.est_admin, r.roles_verifies_le, r.expire_le,
                       r.jeton_oauth, r.csrf)

    async def maj_roles_session(self, id_hache: bytes, est_admin: bool, maintenant: datetime) -> None:
        async with self._moteur.begin() as c:
            await c.execute(update(t.session).where(t.session.c.id_hache == id_hache)
                            .values(est_admin=est_admin, roles_verifies_le=maintenant))

    async def supprimer_session(self, id_hache: bytes) -> str | None:
        """Renvoie le jeton OAuth, à révoquer chez Discord."""
        async with self._moteur.begin() as c:
            r = (await c.execute(delete(t.session).where(t.session.c.id_hache == id_hache)
                                 .returning(t.session.c.jeton_oauth))).one_or_none()
        return r.jeton_oauth if r else None

    async def purger_sessions(self, maintenant: datetime) -> int:
        async with self._moteur.begin() as c:
            r = await c.execute(delete(t.session).where(t.session.c.expire_le <= maintenant))
        return r.rowcount


__all__ = ["Categorie", "ContenuFiche", "PrerequisBrut", "SourceFiche", "contenu_fiche_json"]
