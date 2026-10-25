"""Le dépôt : toutes les lectures et écritures en base, derrière des fonctions simples.

Le reste du programme ne voit jamais de SQL : il appelle `depot.grimpeurs()` et reçoit des
objets du domaine. Chaque écriture se fait dans UNE transaction (`async with self._moteur.begin()`)
qui écrit aussi la ligne de journal : soit tout est enregistré, soit rien.

Toutes les écritures reçoivent `acteur` (l'id Discord de l'admin, ou du joueur qui déclare) et
`maintenant` : ça rend le journal complet et les tests reproductibles (pas d'horloge cachée).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from epreuve.db import tables as t
from epreuve.domaine.inclusion import doit_etre_inclus, est_retardataire, inclus_des_l_inscription, niveau_plancher
from epreuve.domaine.modeles import (
    Contenu,
    EntreeJournal,
    Etage,
    Grimpeur,
    Instantane,
    Palier,
    Validation,
)

# --- Erreurs métier remontées au bot -------------------------------------------------------------


class ErreurDepot(Exception):
    """Une écriture refusée pour une raison compréhensible par un admin."""


class PseudoDejaPris(ErreurDepot):
    pass


class MembreDejaRelie(ErreurDepot):
    pass


class Introuvable(ErreurDepot):
    pass


class DejaValide(ErreurDepot):
    """L'index unique a bloqué une deuxième validation acceptée (deux admins en même temps)."""


@dataclass(frozen=True)
class PreuveDiscord:
    """Le lien d'un message Discord, découpé, et la date du message."""

    guild_id: int
    channel_id: int
    message_id: int
    lien: str
    poste_le: datetime


@dataclass(frozen=True)
class LigneValidation:
    """Une validation avec ce qu'il faut pour l'afficher dans `/grimpeur voir`."""

    validation: Validation
    contenu: str
    motif: str | None
    preuve: str | None


def _contrainte(e: IntegrityError) -> str:
    """Le nom de la contrainte violée, lu dans l'erreur d'asyncpg (ou le message à défaut)."""
    cause = getattr(e.orig, "__cause__", None)
    return getattr(cause, "constraint_name", None) or str(e.orig)


# --- Conversions ligne de base → objet du domaine ------------------------------------------------


def _etage(r) -> Etage:
    return Etage(r.id, r.numero, r.nom, r.level_cap, r.seuil_pourcent, r.statut, r.ouvert_le,
                 r.date_plancher_suivant, r.zone_quetes, tuple(r.donjons_affiches or ()))


def _grimpeur(r) -> Grimpeur:
    return Grimpeur(r.id, r.pseudo_ig, r.classe, r.difficulte, r.statut, r.niveau_connu, r.inscrit_le,
                    r.inclus_le, r.inclusion_forcee)


def _validation(r) -> Validation:
    return Validation(r.id, r.grimpeur_id, r.contenu_id, r.niveau, r.statut, r.forcee, r.source, r.realisee_le)


def _contenu(r) -> Contenu:
    return Contenu(r.id, r.etage_id, r.type, r.nom, r.nom_court)


def _entree(r) -> EntreeJournal:
    return EntreeJournal(r.id, r.horodatage, r.type, r.public, r.grimpeur_id, r.details)


# Dernière activité d'un grimpeur, lue dans le journal : ses validations, ses déclarations
# et les mises à jour de son niveau. Les validations d'un groupe sont dans `details.validations`.
_SQL_ACTIVITE = text("""
    SELECT gid, max(horodatage) AS derniere FROM (
        SELECT grimpeur_id AS gid, horodatage FROM epreuve.journal
        WHERE type = 'niveau' AND grimpeur_id IS NOT NULL
        UNION ALL
        SELECT (v ->> 'grimpeur_id')::int AS gid, j.horodatage
        FROM epreuve.journal j, jsonb_array_elements(j.details -> 'validations') AS v
        WHERE j.type IN ('validation', 'declaration')
    ) AS activite GROUP BY gid
""")


class Depot:
    def __init__(self, moteur: AsyncEngine) -> None:
        self._moteur = moteur

    # --- Santé -----------------------------------------------------------------------------------

    async def ping(self) -> bool:
        try:
            async with self._moteur.connect() as c:
                await c.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001 — toute erreur veut dire « base injoignable »
            return False

    # --- Lectures --------------------------------------------------------------------------------

    async def etages(self) -> list[Etage]:
        async with self._moteur.connect() as c:
            return await self._etages(c)

    @staticmethod
    async def _etages(c: AsyncConnection) -> list[Etage]:
        return [_etage(r) for r in await c.execute(select(t.etage).order_by(t.etage.c.numero))]

    async def etage_ouvert(self) -> Etage | None:
        return next((e for e in await self.etages() if e.statut == "ouvert"), None)

    async def paliers(self, etage_id: int) -> list[Palier]:
        async with self._moteur.connect() as c:
            return await self._paliers(c, etage_id)

    @staticmethod
    async def _paliers(c: AsyncConnection, etage_id: int) -> list[Palier]:
        lignes = (await c.execute(
            select(t.palier).where(t.palier.c.etage_id == etage_id).order_by(t.palier.c.rang)
        )).all()  # fmt: skip
        liens = (await c.execute(
            select(t.palier_contenu).join(t.palier).where(t.palier.c.etage_id == etage_id)
        )).all()  # fmt: skip
        contenus: dict[int, set[int]] = {}
        for lien in liens:
            contenus.setdefault(lien.palier_id, set()).add(lien.contenu_id)
        return [Palier(r.id, r.etage_id, r.rang, r.libelle, frozenset(contenus.get(r.id, set()))) for r in lignes]

    async def contenus(self, etage_id: int) -> list[Contenu]:
        async with self._moteur.connect() as c:
            res = await c.execute(
                select(t.contenu).where(t.contenu.c.etage_id == etage_id).order_by(t.contenu.c.id)
            )
            return [_contenu(r) for r in res]

    async def grimpeurs(self, statut: str | None = None) -> list[Grimpeur]:
        """Tous les grimpeurs, ou ceux d'un statut (`retardataire` : actifs pas encore inclus)."""
        requete = select(t.grimpeur).order_by(func.lower(t.grimpeur.c.pseudo_ig))
        if statut == "retardataire":
            requete = requete.where(t.grimpeur.c.statut == "actif", t.grimpeur.c.inclus_le.is_(None))
        elif statut:
            requete = requete.where(t.grimpeur.c.statut == statut)
        async with self._moteur.connect() as c:
            return [_grimpeur(r) for r in await c.execute(requete)]

    async def grimpeur_par_pseudo(self, pseudo: str) -> Grimpeur | None:
        async with self._moteur.connect() as c:
            r = (await c.execute(
                select(t.grimpeur).where(func.lower(t.grimpeur.c.pseudo_ig) == pseudo.strip().lower())
            )).first()  # fmt: skip
            return _grimpeur(r) if r else None

    async def grimpeur_par_discord(self, discord_user_id: int) -> Grimpeur | None:
        """Le grimpeur relié à ce compte Discord (pour /quetes)."""
        async with self._moteur.connect() as c:
            r = (await c.execute(
                select(t.grimpeur).where(t.grimpeur.c.discord_user_id == discord_user_id)
            )).first()  # fmt: skip
            return _grimpeur(r) if r else None

    async def discord_du_grimpeur(self, grimpeur_id: int) -> int | None:
        """L'id Discord relié (affiché aux admins seulement, jamais sur le site)."""
        async with self._moteur.connect() as c:
            return (await c.execute(
                select(t.grimpeur.c.discord_user_id).where(t.grimpeur.c.id == grimpeur_id)
            )).scalar()  # fmt: skip

    async def validations(self) -> list[Validation]:
        async with self._moteur.connect() as c:
            return [_validation(r) for r in await c.execute(select(t.validation).order_by(t.validation.c.id))]

    async def validation_acceptee(self, grimpeur_id: int, contenu_id: int) -> Validation | None:
        async with self._moteur.connect() as c:
            r = (await c.execute(select(t.validation).where(
                t.validation.c.grimpeur_id == grimpeur_id,
                t.validation.c.contenu_id == contenu_id,
                t.validation.c.statut == "acceptee",
            ))).first()  # fmt: skip
            return _validation(r) if r else None

    async def validations_du_grimpeur(self, grimpeur_id: int) -> list[LigneValidation]:
        """Toutes ses validations et déclarations, annulées comprises (rien ne s'efface)."""
        async with self._moteur.connect() as c:
            res = await c.execute(
                select(t.validation, t.contenu.c.nom_court, t.preuve.c.lien)
                .join(t.contenu, t.contenu.c.id == t.validation.c.contenu_id)
                .outerjoin(t.preuve, t.preuve.c.id == t.validation.c.preuve_id)
                .where(t.validation.c.grimpeur_id == grimpeur_id)
                .order_by(t.validation.c.id)
            )
            return [LigneValidation(_validation(r), r.nom_court, r.motif, r.lien) for r in res]

    async def journal(self, limite: int = 100, public: bool | None = None) -> list[EntreeJournal]:
        requete = select(t.journal).order_by(t.journal.c.horodatage.desc(), t.journal.c.id.desc())
        if public is not None:
            requete = requete.where(t.journal.c.public == public)
        async with self._moteur.connect() as c:
            return [_entree(r) for r in await c.execute(requete.limit(limite))]

    async def dernieres_activites(self) -> dict[int, datetime]:
        """{grimpeur_id: date de dernière activité} (réservé aux admins, jamais sur le site)."""
        async with self._moteur.connect() as c:
            return {r.gid: r.derniere for r in await c.execute(_SQL_ACTIVITE)}

    async def derniere_activite(self, grimpeur_id: int) -> datetime | None:
        return (await self.dernieres_activites()).get(grimpeur_id)

    async def charger_instantane(self) -> Instantane:
        """Tout ce que le site affiche, lu sur une seule connexion."""
        async with self._moteur.connect() as c:
            etages = await self._etages(c)
            ouvert = next((e for e in etages if e.statut == "ouvert"), None)
            paliers, contenus = [], []
            if ouvert:
                paliers = await self._paliers(c, ouvert.id)
                res = await c.execute(select(t.contenu).where(t.contenu.c.etage_id == ouvert.id))
                contenus = [_contenu(r) for r in res]
            grimpeurs = [_grimpeur(r) for r in await c.execute(select(t.grimpeur))]
            validations = [_validation(r) for r in await c.execute(select(t.validation))]
            # On lit plus de 30 entrées : certaines seront masquées (validation annulée, exclu).
            res = await c.execute(
                select(t.journal).where(t.journal.c.public.is_(True))
                .order_by(t.journal.c.horodatage.desc(), t.journal.c.id.desc()).limit(200)
            )
            journal = [_entree(r) for r in res]
        return Instantane(tuple(etages), tuple(paliers), tuple(contenus), tuple(grimpeurs),
                          tuple(validations), tuple(journal))

    # --- Écritures : outils internes --------------------------------------------------------------

    @staticmethod
    async def _journaliser(c: AsyncConnection, type_: str, acteur: int | None, maintenant: datetime,
                           details: dict, grimpeur_id: int | None = None, etage_id: int | None = None,
                           public: bool = False) -> None:
        await c.execute(insert(t.journal).values(
            horodatage=maintenant, acteur_discord_id=acteur, type=type_, grimpeur_id=grimpeur_id,
            etage_id=etage_id, details=details, public=public,
        ))  # fmt: skip

    async def _inclure_si_rattrape(self, c: AsyncConnection, grimpeur_id: int, acteur: int,
                                   maintenant: datetime) -> bool:
        """Après une mise à jour de niveau ou une reprise : un retardataire qui a rattrapé le grimpeur
        compté le moins avancé (le niveau plancher) devient compté."""
        tous = [_grimpeur(r) for r in await c.execute(select(t.grimpeur))]
        g = next(x for x in tous if x.id == grimpeur_id)
        etage = next((e for e in await self._etages(c) if e.statut == "ouvert"), None)
        if etage is None:
            return False
        plancher = niveau_plancher(tous, etage)
        if not doit_etre_inclus(g, plancher):
            return False
        await c.execute(update(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id).values(inclus_le=maintenant))
        await self._journaliser(c, "inclusion", acteur, maintenant,
                                {"raison": "rattrapage", "niveau": g.niveau_connu, "niveau_plancher": plancher},
                                grimpeur_id=grimpeur_id, etage_id=etage.id)
        return True

    # --- Écritures : registre des grimpeurs ------------------------------------------------------

    async def ajouter_grimpeur(self, pseudo: str, classe: str, difficulte: str, discord_user_id: int | None,
                               acteur: int, maintenant: datetime) -> Grimpeur:
        """Inscrit un grimpeur. Si l'étage en cours est déjà ouvert, il arrive en retardataire."""
        try:
            async with self._moteur.begin() as c:
                ouvert = next((e for e in await self._etages(c) if e.statut == "ouvert"), None)
                inclus_le = maintenant if inclus_des_l_inscription(maintenant, ouvert) else None
                r = (await c.execute(insert(t.grimpeur).values(
                    pseudo_ig=pseudo, classe=classe, difficulte=difficulte, statut="actif",
                    discord_user_id=discord_user_id, inscrit_le=maintenant, inclus_le=inclus_le,
                ).returning(t.grimpeur))).one()  # fmt: skip
                await self._journaliser(c, "inscription", acteur, maintenant,
                                        {"pseudo": pseudo, "classe": classe, "difficulte": difficulte,
                                         "retardataire": inclus_le is None}, grimpeur_id=r.id)
                return _grimpeur(r)
        except IntegrityError as e:
            raise self._traduire(e, pseudo) from None

    @staticmethod
    def _traduire(e: IntegrityError, pseudo: str) -> ErreurDepot:
        nom = _contrainte(e)
        if "grimpeur_pseudo_unique" in nom:
            return PseudoDejaPris(f"le pseudo « {pseudo} » est déjà inscrit")
        if "grimpeur_discord_unique" in nom:
            return MembreDejaRelie("ce membre Discord est déjà relié à un autre grimpeur")
        raise e

    async def modifier_grimpeur(self, grimpeur_id: int, acteur: int, maintenant: datetime, *,
                                pseudo: str | None = None, classe: str | None = None,
                                difficulte: str | None = None, niveau: int | None = None,
                                discord_user_id: int | None = None) -> tuple[Grimpeur, dict]:
        """Change les champs donnés. Renvoie le grimpeur à jour et les changements {champ: [avant, après]}.

        Le changement de difficulté et celui de niveau ont chacun leur ligne de journal ; un niveau
        qui rattrape le groupe inclut un retardataire (ligne « inclusion », clé `inclus` des changements).
        """
        try:
            async with self._moteur.begin() as c:
                avant = (await c.execute(
                    select(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id).with_for_update()
                )).first()  # fmt: skip
                if avant is None:
                    raise Introuvable("grimpeur introuvable")
                voulu = {"pseudo_ig": pseudo, "classe": classe, "difficulte": difficulte,
                         "niveau_connu": niveau, "discord_user_id": discord_user_id}
                valeurs = {k: v for k, v in voulu.items() if v is not None and v != getattr(avant, k)}
                if not valeurs:
                    return _grimpeur(avant), {}
                if "niveau_connu" in valeurs:
                    valeurs["niveau_maj_le"] = maintenant
                await c.execute(update(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id).values(**valeurs))
                changements = {k: [getattr(avant, k), v] for k, v in valeurs.items() if k != "niveau_maj_le"}
                if "discord_user_id" in changements:  # pas d'identifiant Discord en clair au journal
                    changements["discord_user_id"] = ["…", "relié"]
                for champ, type_ in (("difficulte", "difficulte"), ("niveau_connu", "niveau")):
                    if champ in changements:
                        av, ap = changements[champ]
                        await self._journaliser(c, type_, acteur, maintenant, {"avant": av, "apres": ap},
                                                grimpeur_id=grimpeur_id)
                autres = {k: v for k, v in changements.items() if k not in ("difficulte", "niveau_connu")}
                if autres:
                    await self._journaliser(c, "modification", acteur, maintenant, autres, grimpeur_id=grimpeur_id)
                if "niveau_connu" in changements:
                    if await self._inclure_si_rattrape(c, grimpeur_id, acteur, maintenant):
                        changements["inclus"] = [False, True]
                apres = (await c.execute(select(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id))).one()
                return _grimpeur(apres), changements
        except IntegrityError as e:
            raise self._traduire(e, pseudo or "") from None

    async def inclure(self, grimpeur_id: int, motif: str | None, acteur: int, maintenant: datetime) -> Grimpeur:
        """`/grimpeur inclure` : un admin fait entrer un retardataire dans le maximum."""
        async with self._moteur.begin() as c:
            r = (await c.execute(select(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id).with_for_update())).first()
            if r is None:
                raise Introuvable("grimpeur introuvable")
            if not est_retardataire(_grimpeur(r)):
                raise ErreurDepot(f"{r.pseudo_ig} n'est pas retardataire")
            r = (await c.execute(
                update(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id)
                .values(inclus_le=maintenant, inclusion_forcee=True).returning(t.grimpeur)
            )).one()  # fmt: skip
            await self._journaliser(c, "inclusion", acteur, maintenant, {"raison": "admin", "motif": motif},
                                    grimpeur_id=grimpeur_id)
            return _grimpeur(r)

    async def changer_statut(self, grimpeur_id: int, statut: str, motif: str | None, type_journal: str,
                             acteur: int, maintenant: datetime) -> Grimpeur:
        """Pause, reprise ou exclusion : on change le statut et on l'écrit au journal (non public).

        Une reprise rend retardataire (Shadoaze, §8 bis e) : `inclus_le` repasse à vide, puis la règle
        de rattrapage s'applique tout de suite (s'il est déjà au niveau du groupe, il est réinclus).
        """
        async with self._moteur.begin() as c:
            valeurs = {"statut": statut, "inclus_le": None} if statut == "actif" else {"statut": statut}
            r = (await c.execute(
                update(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id).values(**valeurs).returning(t.grimpeur)
            )).first()  # fmt: skip
            if r is None:
                raise Introuvable("grimpeur introuvable")
            await self._journaliser(c, type_journal, acteur, maintenant, {"statut": statut, "motif": motif},
                                    grimpeur_id=grimpeur_id)
            if statut == "actif":
                await self._inclure_si_rattrape(c, grimpeur_id, acteur, maintenant)
            return _grimpeur((await c.execute(select(t.grimpeur).where(t.grimpeur.c.id == grimpeur_id))).one())

    # --- Écritures : validations et déclarations -------------------------------------------------

    async def creer_validations(self, etage: Etage, contenu: Contenu, couples: list[tuple[Grimpeur, int, bool]],
                                realisee_le: datetime, preuve: PreuveDiscord | None, acteur: int,
                                maintenant: datetime) -> list[int]:
        """Crée une validation par couple (grimpeur, niveau, forcée ?), TOUT OU RIEN, et une entrée publique.

        Les contrôles métier sont faits avant, par le domaine. Ici, la base apporte la garantie
        finale : si une validation acceptée existe déjà pour un couple (deux admins en même temps),
        l'index unique fait échouer la transaction entière et on lève `DejaValide`.
        """
        try:
            async with self._moteur.begin() as c:
                preuve_id = await self._preuve(c, preuve) if preuve else None
                lignes = []
                for g, niveau, forcee in couples:
                    vid = (await c.execute(insert(t.validation).values(
                        grimpeur_id=g.id, contenu_id=contenu.id, preuve_id=preuve_id, niveau=niveau,
                        statut="acceptee", forcee=forcee, source="manuelle",
                        decidee_par=acteur, decidee_le=maintenant, realisee_le=realisee_le,
                    ).returning(t.validation.c.id))).scalar_one()  # fmt: skip
                    lignes.append({"id": vid, "grimpeur_id": g.id, "niveau": niveau, "contenu": contenu.nom_court,
                                   "forcee": forcee})
                await self._journaliser(c, "validation", acteur, maintenant, {
                    "contenu_id": contenu.id, "validations": lignes, "preuve": preuve.lien if preuve else None,
                }, etage_id=etage.id, public=True)  # fmt: skip
                forcees = [ligne for ligne in lignes if ligne["forcee"]]
                if forcees:
                    await self._journaliser(c, "depassement_accepte", acteur, maintenant,
                                            {"cap": etage.level_cap, "validations": forcees}, etage_id=etage.id)
                for g, niveau, _ in couples:
                    # Niveau connu : le plus haut niveau vu sur une validation acceptée.
                    monte = (await c.execute(
                        update(t.grimpeur).where(t.grimpeur.c.id == g.id)
                        .where(func.coalesce(t.grimpeur.c.niveau_connu, 0) < niveau)
                        .values(niveau_connu=niveau, niveau_maj_le=maintenant)
                    )).rowcount  # fmt: skip
                    if monte:
                        await self._inclure_si_rattrape(c, g.id, acteur, maintenant)
                return [ligne["id"] for ligne in lignes]
        except IntegrityError as e:
            if "validation_une_acceptee" in _contrainte(e):
                raise DejaValide("déjà validé") from None
            raise

    async def declarer(self, etage: Etage, contenus: list[Contenu], g: Grimpeur, preuve: PreuveDiscord | None,
                       acteur: int, maintenant: datetime) -> list[int]:
        """`/quetes` : des validations acceptées, source « declaration », sans niveau. Une entrée publique."""
        try:
            async with self._moteur.begin() as c:
                preuve_id = await self._preuve(c, preuve) if preuve else None
                lignes = []
                for contenu in contenus:
                    vid = (await c.execute(insert(t.validation).values(
                        grimpeur_id=g.id, contenu_id=contenu.id, preuve_id=preuve_id, niveau=None,
                        statut="acceptee", forcee=False, source="declaration",
                        decidee_par=acteur, decidee_le=maintenant, realisee_le=maintenant,
                    ).returning(t.validation.c.id))).scalar_one()  # fmt: skip
                    lignes.append({"id": vid, "grimpeur_id": g.id, "niveau": None, "contenu": contenu.nom_court})
                await self._journaliser(c, "declaration", acteur, maintenant,
                                        {"validations": lignes, "preuve": preuve.lien if preuve else None},
                                        grimpeur_id=g.id, etage_id=etage.id, public=True)
                return [ligne["id"] for ligne in lignes]
        except IntegrityError as e:
            if "validation_une_acceptee" in _contrainte(e):
                raise DejaValide("déjà déclaré") from None
            raise

    @staticmethod
    async def _preuve(c: AsyncConnection, p: PreuveDiscord) -> int:
        """Retrouve ou crée la preuve : un même screen peut servir à plusieurs commandes."""
        existante = (await c.execute(
            select(t.preuve.c.id).where(t.preuve.c.discord_message_id == p.message_id)
        )).scalar()  # fmt: skip
        if existante is not None:
            return existante
        return (await c.execute(insert(t.preuve).values(
            discord_guild_id=p.guild_id, discord_channel_id=p.channel_id, discord_message_id=p.message_id,
            lien=p.lien, poste_le=p.poste_le, statut_ia="sans", cree_le=func.now(),
        ).returning(t.preuve.c.id))).scalar_one()  # fmt: skip

    async def annuler_validation(self, validation_id: int, motif: str, acteur: int,
                                 maintenant: datetime) -> Validation:
        """Passe une validation ou une déclaration en « annulée ». Elle reste en base et au journal."""
        async with self._moteur.begin() as c:
            r = (await c.execute(
                update(t.validation)
                .where(t.validation.c.id == validation_id, t.validation.c.statut == "acceptee")
                .values(statut="annulee", motif=motif, decidee_par=acteur, decidee_le=maintenant)
                .returning(t.validation)
            )).first()  # fmt: skip
            if r is None:
                raise Introuvable(f"pas de validation acceptée n° {validation_id}")
            await self._journaliser(c, "annulation", acteur, maintenant,
                                    {"validation_id": validation_id, "motif": motif}, grimpeur_id=r.grimpeur_id)
            return _validation(r)
