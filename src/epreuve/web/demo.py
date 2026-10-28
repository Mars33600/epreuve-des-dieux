"""Le site sans base ni Discord : un dépôt en mémoire et un faux Discord, pour développer et montrer B2.

    uv run python -m epreuve.web.demo [--port 8080] [--mode ouvert|teaser]

`DepotDemo` a exactement l'interface du dépôt (`db/depot.py`, figée dans LOTS) et en respecte les
règles : coche idempotente avec cascade, élément masqué ou étage scellé « introuvable », exclu refusé,
motif obligatoire pour l'admin qui coche chez un autre, journal de chaque écriture. Les tests du site
l'utilisent comme faux dépôt ; le vrai dépôt Postgres (B1) le remplace à l'intégration.

Données fictives : l'étage 0 « Le Seuil » (3 donjons, 4 quêtes principales, 5 secondaires), 12 grimpeurs
dont 2 en pause, un exclu, et trois étages scellés que personne ne doit voir.
"""

from __future__ import annotations

import argparse
import copy
import itertools
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from fastapi import Request
from fastapi.responses import HTMLResponse
from pydantic import SecretStr

from epreuve.db.depot import (
    CocheRefusee,
    DejaInscrit,
    EtatInvalide,
    Introuvable,
    PasSurLaListe,
    PseudoDejaPris,
)
from epreuve.discord.oauth import ClientOAuth
from epreuve.domaine.bareme import cascade_coche
from epreuve.domaine.fiche import Besoin, EtapeFiche, FicheQuete, Position, Prerequis
from epreuve.domaine.modeles import (
    CaseSucces,
    Coches,
    ContenuEtage,
    Donjon,
    ElementRef,
    EntreeJournal,
    Etage,
    Grimpeur,
    Quete,
    Regles,
    Session,
    Statut,
)
from epreuve.domaine.ouverture import Bilan

PARIS = ZoneInfo("Europe/Paris")
HORLOGE_DEMO = datetime(2026, 11, 15, 18, 0, tzinfo=PARIS).astimezone(UTC)
OUVERTURE_ETAGE_0 = datetime(2026, 10, 30, 17, 0, tzinfo=PARIS).astimezone(UTC)
PLANCHER_ETAGE_0 = datetime(2026, 11, 13, 17, 0, tzinfo=PARIS).astimezone(UTC)
INSCRIPTION = datetime(2026, 11, 13, 17, 30, tzinfo=PARIS).astimezone(UTC)

ID_MARCEAU = 300000000000000100   # admin sans fiche
ID_SHADOAZE = 300000000000000101  # admin sans fiche
ID_NOUVELLE = 300000000000000050  # sur la liste officielle, sans fiche
ID_HORS_LISTE = 300000000000000060  # membre du serveur, pas sur la liste
ID_NON_MEMBRE = 300000000000000070  # pas membre du serveur
ROLE_ADMIN = 900000000000000001


def _id_discord(n: int) -> int:
    return 300000000000000000 + n


def _etages() -> dict[int, Etage]:
    def e(id_, numero, nom, nmin, nmax, statut, ouvert=None, plancher=None):
        return Etage(id_, numero, nom, nmin, nmax, nmax, statut, ouvert, plancher, None, None)

    return {1: e(1, 0, "Le Seuil", 1, 20, "ouvert", OUVERTURE_ETAGE_0, PLANCHER_ETAGE_0),
            2: e(2, 1, "Les Champs Murmurants", 21, 40, "scelle"),
            3: e(3, 2, "La Forêt des Abraknydes", 41, 60, "scelle"),
            4: e(4, 3, "Le Vallon Interdit", 61, 80, "scelle")}


DEFIS = {"Duo": "Finir le donjon à deux grimpeurs seulement",
         "Premier": "Achever le boss avant tout autre monstre",
         "Dernier": "Achever le boss en dernier",
         "Statue": "Ne jamais se déplacer pendant le combat",
         "Nomade": "Se déplacer à chaque tour",
         "Hardi": "Finir chaque tour au contact d'un ennemi",
         "Collant": "Finir chaque tour au contact d'un allié",
         "Pusillanime": "Ne jamais finir son tour au contact d'un ennemi"}


def _donjons_et_cases() -> tuple[dict[int, Donjon], dict[int, CaseSucces]]:
    brut = [(1, 1, "Donjon des Champs", 20, 0, None, ["Duo", "Pusillanime", "Hardi", "Premier"]),
            (2, 1, "Crypte de Kardorim", 12, 10, "Incarnam", ["Duo", "Premier", "Statue", "Hardi"]),
            (3, 1, "Donjon des Bouftous", 16, 30, "Astrub", ["Duo", "Collant", "Nomade", "Dernier"]),
            (4, 2, "Repaire des Murmures", 30, 0, None, ["Duo", "Premier", "Statue", "Nomade"])]
    donjons, cases = {}, {}
    for id_, etage_id, nom, niv, ordre, bloc, defis in brut:
        donjons[id_] = Donjon(id_, etage_id, nom, niv, ordre, bloc, 90 + id_, "propose",
                              "dofusdb" if id_ == 3 else "duffus", False)
        cases[id_ * 10 + 1] = CaseSucces(id_ * 10 + 1, id_, 1, "Vaincre le boss",
                                         "Succès de base : il valide le donjon", True, False)
        for k, d in enumerate(defis, start=2):
            cases[id_ * 10 + k] = CaseSucces(id_ * 10 + k, id_, k, d, DEFIS[d], False, False)
    return donjons, cases


A_LIER_105 = "Les pissenlits poussent sur le chemin de « L'Appel d'Incarnam » : fais les deux dans la foulée."


def _quetes() -> dict[int, Quete]:
    def q(id_, etage_id, nom, niv, bloc, ordre, nature, dofus=(), jusqu_ou=None, a_lier=None, fiche=True):
        return Quete(id_, etage_id, nom, niv, bloc, ordre, nature, "duffus", tuple(dofus), jusqu_ou, a_lier,
                     fiche, False)

    liste = [
        q(101, 1, "L'Appel d'Incarnam", 5, "Incarnam", 11, "principale", ["Dofus Cawotte"]),
        q(105, 1, "Le Bouftou égaré", 8, "Incarnam", 12, "secondaire", a_lier=A_LIER_105),
        q(106, 1, "Lettres pour Incarnam", 6, "Incarnam", 13, "secondaire"),
        q(102, 1, "La Graine de Mère Cawotte", 12, "Astrub", 21, "principale", ["Dofus Cawotte"],
          jusqu_ou="S'arrêter à l'étape 3 : la suite demande le niveau 25."),
        q(107, 1, "Champignons d'Astrub", 10, "Astrub", 22, "secondaire"),
        q(103, 1, "Le Potager des Dieux", 18, "Astrub", 31, "principale", ["Dofus Cawotte"]),
        q(108, 1, "Le Grenier du meunier", 15, "Astrub", 32, "secondaire"),
        q(104, 1, "Les Racines du Ciel", 19, "Astrub", 33, "principale", ["Dofus Cawotte", "Dofus Émeraude"]),
        q(109, 1, "Le Vieux Puits", 14, "Astrub", 34, "secondaire", fiche=False),
        q(201, 2, "Le Secret des Champs Murmurants", 28, "Champs", 11, "principale", ["Dofus Émeraude"]),
    ]
    return {x.id: x for x in liste}


def _fiches() -> dict[int, FicheQuete]:
    def f(quete_id, nom, niv, bloc, nature, dofus, etapes, objets=(), monstres=(), positions=(), prerequis=(),
          succes=None, recompenses=(), jusqu_ou=None, a_lier=None, source="duffus"):
        return FicheQuete(quete_id, 0, nom, niv, bloc, nature, tuple(dofus), jusqu_ou, a_lier, tuple(prerequis),
                          tuple(EtapeFiche(i, t, h, tuple(o)) for i, (t, h, o) in enumerate(etapes, start=1)),
                          tuple(objets), tuple(monstres), tuple(positions), succes, tuple(recompenses), source)

    ysolde = Position("PNJ Gardienne Ysolde", 3, -2, "Incarnam")
    return {
        101: f(101, "L'Appel d'Incarnam", 5, "Incarnam", "principale", ["Dofus Cawotte"],
               [("Parler à la Gardienne", "<p>Parler à la Gardienne Ysolde au pied de la statue d'Incarnam.</p>", []),
                ("Récolter", "<p>Récolter des <strong>Pétales de Pissenlit</strong> dans les champs.</p>",
                 ["Récolter 5 Pétales de Pissenlit"]),
                ("Combattre", "<p>Vaincre les Bouftons Blancs.</p>", ["Vaincre 3 Bouftons Blancs"]),
                ("Retour", "<p>Rapporter les pétales à Ysolde.</p>", [])],
               objets=[Besoin("Pétale de Pissenlit", 5, None)], monstres=[Besoin("Boufton Blanc", 3, None)],
               positions=[ysolde, Position("Champs de pissenlits", 1, -3, "Incarnam")],
               succes="L'Appel entendu", recompenses=["1 200 XP", "150 kamas", "Amulette de l'Éveil"],
               prerequis=[Prerequis(None, "Tutoriel d'Incarnam", "hors_guide")]),
        102: f(102, "La Graine de Mère Cawotte", 12, "Astrub", "principale", ["Dofus Cawotte"],
               [("Le potager", "<p>Retrouver Mère Cawotte dans son potager.</p>", []),
                ("Les graines", "<p>Lui apporter du blé et des graines.</p>",
                 ["Apporter 10 Blés", "Apporter 3 Graines"]),
                ("La Cawotte Enragée", "<p>Vaincre la Cawotte Enragée. Combat à deux conseillé.</p>", []),
                ("Le temple", "<p>Planter la graine bénie au Temple d'Astrub (niveau 25).</p>", [])],
               objets=[Besoin("Blé", 10, None), Besoin("Graine de Cawotte", 3, None)],
               monstres=[Besoin("Cawotte Enragée", 1, None)],
               positions=[Position("PNJ Mère Cawotte", 5, -17, "Astrub"), Position("Temple", 4, -20, "Astrub")],
               prerequis=[Prerequis(101, "L'Appel d'Incarnam", "visible")],
               succes="Main verte", recompenses=["4 800 XP", "600 kamas"],
               jusqu_ou="S'arrêter à l'étape 3 : la suite demande le niveau 25."),
        103: f(103, "Le Potager des Dieux", 18, "Astrub", "principale", ["Dofus Cawotte"],
               [("Aldric", "<p>Parler au Jardinier Aldric.</p>", []),
                ("Le bourgeon", "<p>Obtenir un Bourgeon Divin sur le boss du Donjon des Champs.</p>", []),
                ("Les vagues", "<p>Survivre à 3 vagues de Larves Bleues.</p>", [])],
               objets=[Besoin("Bourgeon Divin", 1, None), Besoin("Cawotte", 20, None)],
               monstres=[Besoin("Larve Bleue", 12, "https://api.dofusdb.fr/img/monsters/31.png")],
               positions=[Position("PNJ Jardinier Aldric", 3, -21, "Astrub")],
               prerequis=[Prerequis(101, "L'Appel d'Incarnam", "visible"),
                          Prerequis(102, "La Graine de Mère Cawotte", "visible")],
               succes="Le Gardien du Potager", recompenses=["9 500 XP", "1 200 kamas", "Dofus Cawotte"],
               source="duffus+dofusdb"),
        104: f(104, "Les Racines du Ciel", 19, "Astrub", "principale", ["Dofus Cawotte", "Dofus Émeraude"],
               [("Les racines", "<p>Suivre les racines jusqu'au sommet de la colline.</p>", [])],
               positions=[Position("Colline", 2, -25, "Astrub")],
               prerequis=[Prerequis(103, "Le Potager des Dieux", "visible"),
                          Prerequis(201, "Le Secret des Champs Murmurants", "visible")],
               recompenses=["3 000 XP"]),
        105: f(105, "Le Bouftou égaré", 8, "Incarnam", "secondaire", [],
               [("Tobin", "<p>Parler au Berger Tobin.</p>", []),
                ("Le bouftou", "<p>Retrouver le bouftou égaré et le ramener sans combattre.</p>", [])],
               monstres=[Besoin("Boufton Noir", 4, None)],
               positions=[Position("PNJ Berger Tobin", 0, -2, "Incarnam")], succes="Berger d'un jour",
               recompenses=["900 XP", "100 kamas"],
               a_lier=A_LIER_105),
        106: f(106, "Lettres pour Incarnam", 6, "Incarnam", "secondaire", [],
               [("Le facteur", "<p>Prendre les lettres auprès du Facteur Pléthore.</p>", ["Livrer 3 lettres"])],
               objets=[Besoin("Lettre scellée", 3, None)], positions=[ysolde], recompenses=["700 XP", "400 kamas"]),
        107: f(107, "Champignons d'Astrub", 10, "Astrub", "secondaire", [],
               [("Malva", "<p>Ramasser des champignons dans la forêt d'Astrub.</p>", [])],
               objets=[Besoin("Champignon", 8, None)], recompenses=["1 500 XP", "250 kamas"]),
        108: f(108, "Le Grenier du meunier", 15, "Astrub", "secondaire", [],
               [("Gaspard", "<p>Vaincre les rats du grenier.</p>", [])],
               monstres=[Besoin("Rat du grenier", 6, None)],
               prerequis=[Prerequis(106, "Lettres pour Incarnam", "visible")],
               recompenses=["2 600 XP", "Émote « Faire la sieste »"]),
        109: f(109, "Le Vieux Puits", 14, "Astrub", "secondaire", [], [], recompenses=["1 000 XP"], source="dofusdb"),
    }


# pseudo, classe, niveau, statut, cases cochées par donjon (Champs, Kardorim, Bouftous), principales, secondaires
BRUT = [
    (1, "Brindille", "Eniripsa", 20, "actif", (5, 5, 3), 4, 2),
    (2, "Kaskarot", "Iop", 20, "actif", (1, 1, 1), 4, 0),
    (3, "Mirelune", "Crâ", 19, "actif", (5, 5, 5), 2, 0),
    (4, "Torvald", "Sacrieur", 20, "actif", (2, 1, 1), 0, 1),
    (5, "Pépin-Lagrume", "Enutrof", 17, "actif", (1, 0, 0), 0, 5),
    (6, "Sélénith", "Xélor", 20, "actif", (5, 5, 5), 4, 5),
    (7, "Gromolo", "Pandawa", 20, "actif", (1, 1, 1), 0, 5),
    (8, "Ombrevive", "Sram", 18, "pause", (1, 1, 1), 1, 0),
    (9, "Fleur-de-Bwork", None, 14, "actif", (1, 0, 0), 0, 1),
    (10, "Cliquetis", "Steamer", 20, "actif", (1, 1, 1), 4, 5),
    (11, "Nalouette", "Osamodas", 21, "actif", (5, 5, 5), 0, 0),
    (12, "Vieux-Grain", "Féca", 11, "pause", (1, 0, 0), 0, 0),
    (13, "Fourbe", "Roublard", 20, "exclu", (5, 5, 5), 4, 5),
]
PRINCIPALES = (101, 102, 103, 104)
SECONDAIRES = (105, 106, 107, 108, 109)


class DepotDemo:
    """Un dépôt en mémoire : même interface et mêmes règles que `db.depot.Depot`."""

    def __init__(self) -> None:
        self._etages = _etages()
        self._donjons, self._cases = _donjons_et_cases()
        self._quetes = _quetes()
        self._fiches = _fiches()
        self._grimpeurs: dict[int, Grimpeur] = {}
        self._coches_cases: dict[int, set[int]] = {}
        self._coches_quetes: dict[int, set[int]] = {}
        self._activite: dict[int, datetime] = {}
        self._liste: dict[int, Statut] = {ID_NOUVELLE: "actif"}
        for id_, pseudo, classe, niv, statut, d, p, s in BRUT:
            did = _id_discord(id_)
            self._liste[did] = "actif" if statut == "exclu" else statut
            self._grimpeurs[id_] = Grimpeur(id_, did, f"{pseudo.lower()}#discord", pseudo, classe, statut, niv,
                                            INSCRIPTION)
            cases = {dj * 10 + k for dj, n in zip((1, 2, 3), d, strict=True) for k in range(1, n + 1)}
            self._coches_cases[id_] = cases
            self._coches_quetes[id_] = set(PRINCIPALES[:p]) | set(SECONDAIRES[:s])
            self._activite[id_] = INSCRIPTION + timedelta(hours=id_)
        self._sessions: dict[bytes, Session] = {}
        self._journal: list[EntreeJournal] = []
        self._bilans: dict[int, Bilan] = {}
        self._alertes = {1: ["Donjon des Bouftous : succès pris chez DofusDB, faute de données Duffus (T-02)."],
                         2: ["Repaire des Murmures : 4 succès seulement, il en faut 5."]}
        self._disponibles = [("d-120", "Grotte Hesque", 18), ("d-121", "Donjon des Larves", 15)]
        self._ids = itertools.count(1000)
        self.pannes = 0  # tests : nombre de prochains appels à `ping` qui échouent

    def copie(self) -> DepotDemo:
        return copy.deepcopy(self)

    # ------------------------------------------------------------------ lecture
    async def ping(self) -> bool:
        return True

    async def etages(self) -> list[Etage]:
        return sorted(self._etages.values(), key=lambda e: e.numero)

    async def etage_par_numero(self, numero: int) -> Etage | None:
        return next((e for e in self._etages.values() if e.numero == numero), None)

    def _brut(self, etage_id: int):
        etage = self._etages.get(etage_id)
        if etage is None:
            raise Introuvable("étage inconnu")
        donjons = [d for d in self._donjons.values() if d.etage_id == etage_id]
        ids = {d.id for d in donjons}
        cases = [c for c in self._cases.values() if c.donjon_id in ids]
        quetes = [q for q in self._quetes.values() if q.etage_id == etage_id]
        return etage, donjons, cases, quetes

    async def contenu_etage(self, etage_id: int) -> ContenuEtage:
        return ContenuEtage.visible(*self._brut(etage_id))

    async def contenu_brut(self, etage_id: int):
        etage, d, c, q = self._brut(etage_id)
        return etage, sorted(d, key=lambda x: x.ordre), sorted(c, key=lambda x: (x.donjon_id, x.ordre)), \
            sorted(q, key=lambda x: x.ordre)

    async def alertes_etage(self, etage_id: int) -> list[str]:
        return list(self._alertes.get(etage_id, []))

    async def coches_etage(self, etage_id: int) -> dict[int, Coches]:
        _, donjons, cases, quetes = self._brut(etage_id)
        ids_c, ids_q = {c.id for c in cases}, {q.id for q in quetes}
        return {g: Coches(g, frozenset(self._coches_cases.get(g, set()) & ids_c),
                          frozenset(self._coches_quetes.get(g, set()) & ids_q)) for g in self._grimpeurs}

    async def grimpeurs(self) -> list[Grimpeur]:
        return list(self._grimpeurs.values())

    async def grimpeur(self, grimpeur_id: int) -> Grimpeur | None:
        return self._grimpeurs.get(grimpeur_id)

    async def grimpeur_par_discord(self, discord_user_id: int) -> Grimpeur | None:
        return next((g for g in self._grimpeurs.values() if g.discord_user_id == discord_user_id), None)

    async def liste_officielle(self) -> dict[int, Statut]:
        return dict(self._liste)

    async def dernieres_activites(self) -> dict[int, datetime]:
        return dict(self._activite)

    async def bilan(self, etage_id: int) -> Bilan | None:
        return self._bilans.get(etage_id)

    async def journal(self, limite: int = 200, grimpeur_id: int | None = None, etage_id: int | None = None,
                      type_: str | None = None) -> list[EntreeJournal]:
        lignes = [e for e in reversed(self._journal)
                  if (grimpeur_id is None or e.grimpeur_id == grimpeur_id)
                  and (etage_id is None or e.etage_id == etage_id) and (type_ is None or e.type == type_)]
        return lignes[:limite]

    async def fiche_quete(self, quete_id: int) -> FicheQuete | None:
        q = self._quetes.get(quete_id)
        f = self._fiches.get(quete_id)
        if q is None or f is None:
            return None
        return replace(f, etage_numero=self._etages[q.etage_id].numero)

    async def quetes_sans_fiche(self, etage_id: int) -> list[Quete]:
        return [q for q in self._quetes.values() if q.etage_id == etage_id and not q.a_une_fiche]

    async def donjons_disponibles(self) -> list[tuple[str, str, int | None]]:
        return list(self._disponibles)

    # ------------------------------------------------------------------ journal
    def _journaliser(self, acteur, maintenant, type_, *, grimpeur_id=None, etage_id=None, public=True, **details):
        self._journal.append(EntreeJournal(next(self._ids), maintenant, acteur, type_, grimpeur_id, etage_id,
                                           details, public))

    # ------------------------------------------------------------------ écriture grimpeur
    async def creer_grimpeur(self, discord_user_id, nom_discord, pseudo, classe, niveau_declare, maintenant):
        if discord_user_id not in self._liste:
            raise PasSurLaListe("pas sur la liste officielle")
        if await self.grimpeur_par_discord(discord_user_id) is not None:
            raise DejaInscrit("déjà inscrit")
        self._pseudo_libre(pseudo)
        id_ = max(self._grimpeurs, default=0) + 1
        g = Grimpeur(id_, discord_user_id, nom_discord, pseudo, classe, self._liste[discord_user_id], niveau_declare,
                     maintenant)
        self._grimpeurs[id_] = g
        self._journaliser(discord_user_id, maintenant, "inscription", grimpeur_id=id_, pseudo=pseudo)
        return g

    def _pseudo_libre(self, pseudo: str, sauf: int | None = None) -> None:
        if any(g.pseudo.casefold() == pseudo.casefold() and g.id != sauf for g in self._grimpeurs.values()):
            raise PseudoDejaPris("pseudo déjà pris")

    async def maj_nom_discord(self, discord_user_id, nom_discord) -> None:
        g = await self.grimpeur_par_discord(discord_user_id)
        if g is not None:
            self._grimpeurs[g.id] = replace(g, nom_discord=nom_discord)

    async def modifier_grimpeur(self, grimpeur_id, acteur, maintenant, *, pseudo=None, classe=None,
                                niveau_declare=None):
        g = self._grimpeurs.get(grimpeur_id)
        if g is None:
            raise Introuvable("grimpeur inconnu")
        if pseudo is not None:
            self._pseudo_libre(pseudo, sauf=grimpeur_id)
        g = replace(g, pseudo=pseudo if pseudo is not None else g.pseudo,
                    classe=classe if classe is not None else g.classe,
                    niveau_declare=niveau_declare if niveau_declare is not None else g.niveau_declare)
        self._grimpeurs[grimpeur_id] = g
        self._journaliser(acteur, maintenant, "fiche_modifiee", grimpeur_id=grimpeur_id,
                          public=acteur == g.discord_user_id)
        return g

    def _element_visible(self, ref: ElementRef) -> Etage:
        if ref.type == "case":
            c = self._cases.get(ref.id)
            d = self._donjons.get(c.donjon_id) if c else None
            if c is None or c.masquee or d is None or d.masque:
                raise Introuvable("élément inconnu")
            etage = self._etages[d.etage_id]
        else:
            q = self._quetes.get(ref.id)
            if q is None or q.masquee:
                raise Introuvable("élément inconnu")
            etage = self._etages[q.etage_id]
        if etage.statut not in ("ouvert", "termine"):
            raise Introuvable("élément inconnu")
        return etage

    def _peut_cocher(self, grimpeur_id, acteur, regles: Regles, motif) -> Grimpeur:
        g = self._grimpeurs.get(grimpeur_id)
        if g is None:
            raise Introuvable("grimpeur inconnu")
        if g.statut == "exclu" or (g.statut == "pause" and not regles.pause_peut_cocher):
            raise CocheRefusee("coche refusée")
        if acteur != g.discord_user_id and not (motif or "").strip():
            raise ValueError("motif obligatoire pour une coche d'admin")
        return g

    async def cocher(self, grimpeur_id, ref: ElementRef, cochee: bool, acteur, maintenant, regles: Regles,
                     motif: str | None = None) -> tuple[ElementRef, ...]:
        etage = self._element_visible(ref)
        g = self._peut_cocher(grimpeur_id, acteur, regles, motif)
        contenu = await self.contenu_etage(etage.id)
        changes = []
        for r in (ref, *cascade_coche(contenu, ref, cochee, regles)):
            ens = (self._coches_cases if r.type == "case" else self._coches_quetes).setdefault(grimpeur_id, set())
            if (r.id in ens) != cochee:
                (ens.add if cochee else ens.discard)(r.id)
                changes.append(r)
        if changes:
            if cochee:
                self._activite[grimpeur_id] = maintenant
            self._journaliser(acteur, maintenant, "coche" if cochee else "decoche", grimpeur_id=grimpeur_id,
                              etage_id=etage.id, public=acteur == g.discord_user_id,
                              elements=[f"{r.type}:{r.id}" for r in changes], motif=motif)
        return tuple(changes)

    async def cocher_donjon(self, grimpeur_id, donjon_id, acteur, maintenant, regles: Regles,
                            motif: str | None = None) -> int:
        d = self._donjons.get(donjon_id)
        if d is None or d.masque:
            raise Introuvable("donjon inconnu")
        cases = [c for c in self._cases.values() if c.donjon_id == donjon_id and not c.masquee]
        n = 0
        for c in sorted(cases, key=lambda c: c.ordre):
            n += len(await self.cocher(grimpeur_id, ElementRef("case", c.id), True, acteur, maintenant, regles, motif))
        return n

    # ------------------------------------------------------------------ écriture admin
    async def ajouter_liste(self, discord_ids: list[int], statut_initial: Literal["actif", "pause"], acteur,
                            maintenant) -> list[int]:
        ajoutes = [i for i in dict.fromkeys(discord_ids) if i not in self._liste]
        for i in ajoutes:
            self._liste[i] = statut_initial
        self._journaliser(acteur, maintenant, "liste_officielle", public=False, ajoutes=len(ajoutes),
                          statut_initial=statut_initial)
        return ajoutes

    async def changer_statut(self, grimpeur_id, statut: Statut, motif: str | None, acteur, maintenant) -> Grimpeur:
        g = self._grimpeurs.get(grimpeur_id)
        if g is None:
            raise Introuvable("grimpeur inconnu")
        g = replace(g, statut=statut)
        self._grimpeurs[grimpeur_id] = g
        self._journaliser(acteur, maintenant, "statut", grimpeur_id=grimpeur_id, public=False, statut=statut,
                          motif=motif)
        return g

    def _etage(self, etage_id) -> Etage:
        e = self._etages.get(etage_id)
        if e is None:
            raise Introuvable("étage inconnu")
        return e

    async def regler_palier(self, etage_id, palier: int | None, motif: str, acteur, maintenant) -> Etage:
        e = replace(self._etage(etage_id), palier_manuel=palier)
        self._etages[etage_id] = e
        self._journaliser(acteur, maintenant, "palier", etage_id=etage_id, palier=palier, motif=motif)
        return e

    async def regler_date_plancher(self, etage_id, date: datetime | None, acteur, maintenant) -> Etage:
        e = replace(self._etage(etage_id), date_plancher_suivant=date)
        self._etages[etage_id] = e
        self._journaliser(acteur, maintenant, "date_plancher", etage_id=etage_id,
                          date=date.isoformat() if date else None)
        return e

    async def regler_etage(self, etage_id, acteur, maintenant, *, nom=None, ambiance_url=None, level_cap=None):
        e = self._etage(etage_id)
        e = replace(e, nom=nom if nom is not None else e.nom,
                    ambiance_url=ambiance_url if ambiance_url is not None else e.ambiance_url,
                    level_cap=level_cap if level_cap is not None else e.level_cap)
        self._etages[etage_id] = e
        self._journaliser(acteur, maintenant, "reglages_etage", etage_id=etage_id, nom=e.nom, level_cap=e.level_cap)
        return e

    async def modifier_quete(self, quete_id, acteur, maintenant, *, nature=None, motif=None, masquee=None, nom=None):
        q = self._quetes.get(quete_id)
        if q is None:
            raise Introuvable("quête inconnue")
        if nature is not None and not (motif or "").strip():
            raise ValueError("motif obligatoire pour changer la nature")
        q = replace(q, nature=nature or q.nature, nature_origine="admin" if nature else q.nature_origine,
                    masquee=q.masquee if masquee is None else masquee, nom=nom or q.nom)
        self._quetes[quete_id] = q
        self._journaliser(acteur, maintenant, "quete", etage_id=q.etage_id, quete=quete_id, nature=nature,
                          masquee=masquee, nom=nom, motif=motif)
        return q

    async def modifier_donjon(self, donjon_id, acteur, maintenant, *, masque=None, nom=None) -> Donjon:
        d = self._donjons.get(donjon_id)
        if d is None:
            raise Introuvable("donjon inconnu")
        d = replace(d, masque=d.masque if masque is None else masque, nom=nom or d.nom)
        self._donjons[donjon_id] = d
        self._journaliser(acteur, maintenant, "donjon", etage_id=d.etage_id, donjon=donjon_id, masque=masque, nom=nom)
        return d

    async def modifier_case(self, case_id, acteur, maintenant, *, masquee=None, nom=None, condition=None):
        c = self._cases.get(case_id)
        if c is None:
            raise Introuvable("case inconnue")
        c = replace(c, masquee=c.masquee if masquee is None else masquee, nom=nom or c.nom,
                    condition=condition or c.condition)
        self._cases[case_id] = c
        self._journaliser(acteur, maintenant, "case", etage_id=self._donjons[c.donjon_id].etage_id, case=case_id,
                          masquee=masquee, nom=nom)
        return c

    async def ajouter_donjon(self, etage_id, duffus_id: str, acteur, maintenant) -> Donjon:
        self._etage(etage_id)
        trouve = next((x for x in self._disponibles if x[0] == duffus_id), None)
        if trouve is None:
            raise Introuvable("donjon inconnu")
        id_ = max(self._donjons) + 1
        ordre = max((d.ordre for d in self._donjons.values() if d.etage_id == etage_id), default=0) + 1
        d = Donjon(id_, etage_id, trouve[1], trouve[2], ordre, None, None, "admin", "duffus", False)
        self._donjons[id_] = d
        noms = ["Vaincre le boss", "Duo", "Premier", "Statue", "Hardi"]
        for k, n in enumerate(noms, start=1):
            self._cases[id_ * 10 + k] = CaseSucces(id_ * 10 + k, id_, k, n, DEFIS.get(n, "Succès de base"), k == 1,
                                                   False)
        self._journaliser(acteur, maintenant, "donjon_ajoute", etage_id=etage_id, donjon=trouve[1])
        return d

    async def ouvrir_etage(self, numero: int, bilan_precedent: Bilan, acteur, maintenant) -> Etage:
        cible = await self.etage_par_numero(numero)
        if cible is None or cible.statut != "scelle":
            raise EtatInvalide("étage déjà ouvert ou inconnu")
        en_cours = next((e for e in self._etages.values() if e.statut == "ouvert"), None)
        if en_cours is not None:
            self._etages[en_cours.id] = replace(en_cours, statut="termine")
            self._bilans[en_cours.id] = bilan_precedent
        ouvert = replace(cible, statut="ouvert", ouvert_le=maintenant)
        self._etages[cible.id] = ouvert
        self._journaliser(acteur, maintenant, "ouverture", etage_id=cible.id, force=bilan_precedent.force,
                          motif=bilan_precedent.motif)
        return ouvert

    # ------------------------------------------------------------------ sessions
    async def creer_session(self, id_hache: bytes, discord_user_id, nom_discord, est_admin, jeton_oauth, csrf,
                            maintenant, duree: timedelta) -> None:
        self._sessions[id_hache] = Session(discord_user_id, nom_discord, est_admin, maintenant, maintenant + duree,
                                           jeton_oauth, csrf)
        await self.maj_nom_discord(discord_user_id, nom_discord)

    async def session(self, id_hache: bytes, maintenant) -> Session | None:
        s = self._sessions.get(id_hache)
        return s if s is not None and s.expire_le > maintenant else None

    async def maj_roles_session(self, id_hache, est_admin, maintenant) -> None:
        s = self._sessions.get(id_hache)
        if s is not None:
            self._sessions[id_hache] = replace(s, est_admin=est_admin, roles_verifies_le=maintenant)

    async def supprimer_session(self, id_hache) -> str | None:
        s = self._sessions.pop(id_hache, None)
        return s.jeton_oauth if s else None

    async def purger_sessions(self, maintenant) -> int:
        vieilles = [k for k, s in self._sessions.items() if s.expire_le <= maintenant]
        for k in vieilles:
            del self._sessions[k]
        return len(vieilles)


# ---------------------------------------------------------------------- faux Discord
PROFILS_DEMO: dict[int, tuple[str, bool]] = {
    ID_MARCEAU: ("Marceau (admin sans fiche)", True),
    ID_SHADOAZE: ("Shadoaze (admin sans fiche)", True),
    _id_discord(1): ("Brindille (grimpeuse)", False),
    _id_discord(8): ("Ombrevive (en pause)", False),
    _id_discord(13): ("Fourbe (exclu)", False),
    ID_NOUVELLE: ("Nouvelle (sur la liste, sans fiche)", False),
    ID_HORS_LISTE: ("Passant (membre, hors liste)", False),
}


def faux_discord(membres: dict[int, tuple[str, frozenset[int]]], appels: list[str] | None = None,
                 guild_id: int = 1) -> httpx.MockTransport:
    """Un Discord simulé : le code « code-<id> » donne le jeton « jeton-<id> ». `appels` reçoit chaque adresse."""

    def repondre(req: httpx.Request) -> httpx.Response:
        if appels is not None:
            appels.append(f"{req.method} {req.url.path}")
        chemin = req.url.path.removeprefix("/api/v10")
        if chemin == "/oauth2/token":
            code = dict(httpx.QueryParams(req.content.decode())).get("code", "")
            if not code.startswith("code-"):
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "jeton-" + code[5:], "token_type": "Bearer"})
        if chemin == "/oauth2/token/revoke":
            return httpx.Response(200, json={})
        jeton = req.headers.get("Authorization", "").removeprefix("Bearer jeton-")
        if not jeton.isdigit():
            return httpx.Response(401, json={"message": "401: Unauthorized"})
        uid = int(jeton)
        if chemin == "/users/@me":
            return httpx.Response(200, json={"id": str(uid), "username": f"u{uid}", "global_name": None})
        if chemin == f"/users/@me/guilds/{guild_id}/member":
            if uid not in membres:
                return httpx.Response(404, json={"message": "Unknown Guild"})
            nom, roles = membres[uid]
            return httpx.Response(200, json={"nick": nom, "roles": [str(r) for r in roles]})
        return httpx.Response(404, json={})

    return httpx.MockTransport(repondre)


def membres_demo(depot: DepotDemo) -> dict[int, tuple[str, frozenset[int]]]:
    membres = {g.discord_user_id: (g.nom_discord, frozenset()) for g in depot._grimpeurs.values()}
    membres[ID_MARCEAU] = ("Marceau", frozenset({ROLE_ADMIN}))
    membres[ID_SHADOAZE] = ("Shadoaze", frozenset({ROLE_ADMIN}))
    membres[ID_NOUVELLE] = ("Nouvelle", frozenset())
    membres[ID_HORS_LISTE] = ("Passant", frozenset())
    return membres


class ClientOAuthDemo(ClientOAuth):
    """Au lieu de l'écran de Discord, une page de la démo où l'on choisit qui l'on est."""

    def url_autorisation(self, state: str) -> str:
        return f"/demo/qui?state={state}"


def creer_app_demo(mode: str = "ouvert"):
    from epreuve.config import Config
    from epreuve.web.app import creer_app

    depot = DepotDemo()
    config = Config(SITE_MODE=mode, DISCORD_GUILD_ID=1,  # sans SITE_URL : l’origine attendue est celle de la requête
                    DISCORD_ADMIN_ROLE_IDS=str(ROLE_ADMIN), _env_file=None)  # la démo ne lit jamais .env
    oauth = ClientOAuthDemo(config.discord_client_id, SecretStr("demo"), config.redirect_uri, 1,
                            transport=faux_discord(membres_demo(depot)))
    app = creer_app(config, horloge=lambda: HORLOGE_DEMO, source=depot, oauth=oauth)

    @app.get("/demo/qui", response_class=HTMLResponse)
    async def qui(request: Request, state: str = ""):
        from epreuve.web.rendu import rendre

        profils = [*PROFILS_DEMO.items(), (ID_NON_MEMBRE, ("Inconnu (pas membre du serveur)", False))]
        return await rendre(request, "demo_qui.html", {
            "profils": [(f"/auth/discord/retour?code=code-{i}&state={state}", nom) for i, (nom, _) in profils]})

    return app


def main() -> None:  # pragma: no cover — lance un serveur
    import uvicorn

    parser = argparse.ArgumentParser(description="Site de démonstration, données fictives.")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--mode", choices=["ouvert", "teaser"], default="ouvert")
    args = parser.parse_args()
    print(f"Démo : http://127.0.0.1:{args.port}  (données fictives, Ctrl+C pour arrêter)")
    uvicorn.run(creer_app_demo(args.mode), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":  # pragma: no cover
    main()
