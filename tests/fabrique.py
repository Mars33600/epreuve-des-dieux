"""Fabrique de données de test : des objets du domaine aux valeurs par défaut, et l'étage de référence.

Étage de référence (critère 15 du lot B) : 3 donjons de 5 cases (ids 1-5, 6-10, 11-15 ; la première de
chaque donjon est la case classique « Vaincre le boss »), 4 quêtes principales (ids 1-4), 5 secondaires
(ids 5-9), 12 grimpeurs dont 2 en pause (11 et 12). Les coches sont fixées dans COCHES_REFERENCE ; les
points attendus sont calculés à la main dans tests/domaine/test_bareme.py.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from epreuve.domaine.modeles import CaseSucces, Coches, ContenuEtage, Donjon, Etage, Grimpeur, Quete

PARIS = ZoneInfo("Europe/Paris")
OUVERTURE = datetime(2026, 10, 30, 17, 0, tzinfo=PARIS).astimezone(UTC)
PLANCHER = datetime(2026, 11, 13, 17, 0, tzinfo=PARIS).astimezone(UTC)
AVANT = OUVERTURE - timedelta(days=2)
PENDANT = OUVERTURE + timedelta(days=3)


def etage(id_: int = 1, numero: int = 0, statut: str = "ouvert", **kw) -> Etage:
    valeurs = dict(nom=f"Étage {numero}", niveau_min=1, niveau_max=20, level_cap=20,
                   ouvert_le=OUVERTURE if statut != "scelle" else None,
                   date_plancher_suivant=PLANCHER, palier_manuel=None, ambiance_url=None)
    valeurs.update(kw)
    return Etage(id=id_, numero=numero, statut=statut, **valeurs)


def donjon(id_: int, etage_id: int = 1, **kw) -> Donjon:
    valeurs = dict(nom=f"Donjon {id_}", niveau=10 * id_, ordre=id_, bloc=None, dofusdb_id=None,
                   origine="propose", succes_source="duffus", masque=False)
    valeurs.update(kw)
    return Donjon(id=id_, etage_id=etage_id, **valeurs)


def case(id_: int, donjon_id: int, ordre: int, **kw) -> CaseSucces:
    valeurs = dict(nom=f"Succès {id_}", condition="", est_classique=ordre == 1, masquee=False)
    valeurs.update(kw)
    return CaseSucces(id=id_, donjon_id=donjon_id, ordre=ordre, **valeurs)


def quete(id_: int, nature: str = "secondaire", etage_id: int = 1, **kw) -> Quete:
    valeurs = dict(nom=f"Quête {id_}", niveau=id_, bloc="Incarnam", ordre=id_, nature_origine="duffus",
                   dofus=("Émeraude",) if nature == "principale" else (), jusqu_ou=None, a_lier=None,
                   a_une_fiche=True, masquee=False)
    valeurs.update(kw)
    return Quete(id=id_, etage_id=etage_id, nature=nature, **valeurs)


def grimpeur(id_: int, statut: str = "actif", pseudo: str | None = None, classe: str | None = "Iop",
             **kw) -> Grimpeur:
    valeurs = dict(discord_user_id=900_000_000_000_000_000 + id_, nom_discord=f"discord{id_}",
                   niveau_declare=None, inscrit_le=AVANT)
    valeurs.update(kw)
    return Grimpeur(id=id_, pseudo=pseudo or f"Grimpeur{id_:02d}", classe=classe, statut=statut, **valeurs)


def coches(grimpeur_id: int, cases=(), quetes=()) -> Coches:
    return Coches(grimpeur_id, frozenset(cases), frozenset(quetes))


ETAGE_REF = etage()
DONJONS_REF = tuple(donjon(d) for d in (1, 2, 3))
CASES_REF = tuple(case((d - 1) * 5 + o, d, o) for d in (1, 2, 3) for o in range(1, 6))
QUETES_REF = tuple(quete(q, "principale") for q in range(1, 5)) + tuple(quete(q) for q in range(5, 10))
CONTENU_REF = ContenuEtage.visible(ETAGE_REF, DONJONS_REF, CASES_REF, QUETES_REF)
GRIMPEURS_REF = tuple(grimpeur(i, "pause" if i > 10 else "actif") for i in range(1, 13))

CLASSIQUES = (1, 6, 11)
TOUTES_CASES = tuple(range(1, 16))
PRINCIPALES = (1, 2, 3, 4)
SECONDAIRES = (5, 6, 7, 8, 9)
COCHES_REFERENCE = {
    1: coches(1, TOUTES_CASES, PRINCIPALES + SECONDAIRES),  # 4 points
    2: coches(2, CLASSIQUES, PRINCIPALES + SECONDAIRES),  # donjons, principales, secondaires : 3
    3: coches(3, TOUTES_CASES),  # donjons, full succès : 2
    4: coches(4, (), PRINCIPALES),  # 1
    5: coches(5, (), SECONDAIRES),  # 1
    6: coches(6, (1, 6), (1, 2, 3)),  # 0
    # 7 : rien coché, aucune entrée → 0
    8: coches(8, CLASSIQUES),  # 1
    9: coches(9, (), PRINCIPALES + SECONDAIRES),  # 2
    10: coches(10, TOUTES_CASES, PRINCIPALES),  # 3
    11: coches(11, TOUTES_CASES, PRINCIPALES + SECONDAIRES),  # en pause : 4, non comptés
}
