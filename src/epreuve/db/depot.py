"""STUB B2 — remplacé par la version de B1 à l'intégration (interfaces figées de LOTS.md, lot B).

Seules les erreurs et les signatures sont là : le site se développe contre `web/demo.py`
(un dépôt en mémoire), en attendant le vrai dépôt Postgres de B1.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncEngine

from epreuve.domaine.fiche import FicheQuete
from epreuve.domaine.modeles import (
    CaseSucces,
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


class ErreurDepot(Exception): ...
class Introuvable(ErreurDepot): ...
class PseudoDejaPris(ErreurDepot): ...
class PasSurLaListe(ErreurDepot): ...
class DejaInscrit(ErreurDepot): ...
class EtatInvalide(ErreurDepot): ...
class CocheRefusee(ErreurDepot): ...


class Depot:  # pragma: no cover — stub
    def __init__(self, moteur: AsyncEngine) -> None:
        self._moteur = moteur

    async def ping(self) -> bool: raise NotImplementedError
    async def etages(self) -> list[Etage]: raise NotImplementedError
    async def etage_par_numero(self, numero: int) -> Etage | None: raise NotImplementedError
    async def contenu_etage(self, etage_id: int) -> ContenuEtage: raise NotImplementedError
    async def contenu_brut(self, etage_id: int) -> tuple[Etage, list[Donjon], list[CaseSucces], list[Quete]]:
        raise NotImplementedError
    async def alertes_etage(self, etage_id: int) -> list[str]: raise NotImplementedError
    async def coches_etage(self, etage_id: int) -> dict[int, Coches]: raise NotImplementedError
    async def grimpeurs(self) -> list[Grimpeur]: raise NotImplementedError
    async def grimpeur(self, grimpeur_id: int) -> Grimpeur | None: raise NotImplementedError
    async def grimpeur_par_discord(self, discord_user_id: int) -> Grimpeur | None: raise NotImplementedError
    async def liste_officielle(self) -> dict[int, Statut]: raise NotImplementedError
    async def dernieres_activites(self) -> dict[int, datetime]: raise NotImplementedError
    async def bilan(self, etage_id: int) -> Bilan | None: raise NotImplementedError
    async def journal(self, limite: int = 200, grimpeur_id: int | None = None, etage_id: int | None = None,
                      type_: str | None = None) -> list[EntreeJournal]: raise NotImplementedError
    async def creer_grimpeur(self, discord_user_id, nom_discord, pseudo, classe, niveau_declare,
                             maintenant) -> Grimpeur: raise NotImplementedError
    async def maj_nom_discord(self, discord_user_id, nom_discord) -> None: raise NotImplementedError
    async def modifier_grimpeur(self, grimpeur_id, acteur, maintenant, *, pseudo=None, classe=None,
                                niveau_declare=None) -> Grimpeur: raise NotImplementedError
    async def cocher(self, grimpeur_id, ref: ElementRef, cochee: bool, acteur, maintenant, regles: Regles,
                     motif: str | None = None) -> tuple[ElementRef, ...]: raise NotImplementedError
    async def cocher_donjon(self, grimpeur_id, donjon_id, acteur, maintenant, regles: Regles,
                            motif: str | None = None) -> int: raise NotImplementedError
    async def ajouter_liste(self, discord_ids: list[int], statut_initial: Literal["actif", "pause"], acteur,
                            maintenant) -> list[int]: raise NotImplementedError
    async def changer_statut(self, grimpeur_id, statut: Statut, motif: str | None, acteur,
                             maintenant) -> Grimpeur: raise NotImplementedError
    async def regler_palier(self, etage_id, palier: int | None, motif: str, acteur, maintenant) -> Etage:
        raise NotImplementedError
    async def regler_date_plancher(self, etage_id, date: datetime | None, acteur, maintenant) -> Etage:
        raise NotImplementedError
    async def modifier_quete(self, quete_id, acteur, maintenant, *, nature: Nature | None = None,
                             motif: str | None = None, masquee: bool | None = None,
                             nom: str | None = None) -> Quete: raise NotImplementedError
    async def modifier_donjon(self, donjon_id, acteur, maintenant, *, masque=None, nom=None) -> Donjon:
        raise NotImplementedError
    async def ajouter_donjon(self, etage_id, duffus_id: str, acteur, maintenant) -> Donjon: raise NotImplementedError
    async def donjons_disponibles(self) -> list[tuple[str, str, int | None]]: raise NotImplementedError
    async def regler_etage(self, etage_id, acteur, maintenant, *, nom=None, ambiance_url=None,
                           level_cap=None) -> Etage: raise NotImplementedError
    async def fiche_quete(self, quete_id: int) -> FicheQuete | None: raise NotImplementedError
    async def quetes_sans_fiche(self, etage_id: int) -> list[Quete]: raise NotImplementedError
    async def modifier_case(self, case_id, acteur, maintenant, *, masquee=None, nom=None,
                            condition=None) -> CaseSucces: raise NotImplementedError
    async def ouvrir_etage(self, numero: int, bilan_precedent: Bilan, acteur, maintenant) -> Etage:
        raise NotImplementedError
    async def creer_session(self, id_hache: bytes, discord_user_id, nom_discord, est_admin, jeton_oauth, csrf,
                            maintenant, duree: timedelta) -> None: raise NotImplementedError
    async def session(self, id_hache: bytes, maintenant) -> Session | None: raise NotImplementedError
    async def maj_roles_session(self, id_hache, est_admin, maintenant) -> None: raise NotImplementedError
    async def supprimer_session(self, id_hache) -> str | None: raise NotImplementedError
    async def purger_sessions(self, maintenant) -> int: raise NotImplementedError
