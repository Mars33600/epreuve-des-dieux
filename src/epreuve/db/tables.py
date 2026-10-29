"""Description des tables pour SQLAlchemy (mode « Core » : des tables et des requêtes, sans ORM).

Le schéma lui-même est créé par la migration `0001_initial` ; ce fichier sert à écrire les requêtes en
Python. Les deux doivent rester d'accord : les tests de base le vérifient en lisant et écrivant à travers
ces tables sur une base migrée. Les contraintes (CHECK, index uniques) ne sont écrites que dans la migration.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

SCHEMA = "epreuve"
metadata = MetaData(schema=SCHEMA)
Horodatage = DateTime(timezone=True)  # « timestamptz » : toujours avec fuseau


def _masquage() -> list[Column]:
    return [Column("masque_par", Text), Column("corrections", JSONB, nullable=False, server_default="{}")]


etage = Table(
    "etage", metadata,
    Column("id", Integer, primary_key=True),
    Column("numero", Integer, nullable=False, unique=True),
    Column("nom", Text, nullable=False),
    Column("niveau_min", Integer, nullable=False),
    Column("niveau_max", Integer, nullable=False),
    Column("level_cap", Integer, nullable=False),
    Column("statut", Text, nullable=False),
    Column("ouvert_le", Horodatage),
    Column("date_plancher_suivant", Horodatage),
    Column("palier_manuel", Integer),
    Column("duffus_tranche_id", Text),
    Column("ambiance_url", Text),
    Column("alertes", JSONB, nullable=False, server_default="[]"),
    Column("corrections", JSONB, nullable=False, server_default="{}"),
    Column("maj_le", Horodatage, nullable=False),
)

donjon_disponible = Table(
    "donjon_disponible", metadata,
    Column("duffus_id", Text, primary_key=True),
    Column("nom", Text, nullable=False),
    Column("niveau", Integer),
    Column("dofusdb_id", Integer),
    Column("succes_source", Text, nullable=False),
    Column("succes", JSONB, nullable=False),
    Column("maj_le", Horodatage, nullable=False),
)

donjon = Table(
    "donjon", metadata,
    Column("id", Integer, primary_key=True),
    Column("etage_id", Integer, ForeignKey("etage.id"), nullable=False),
    Column("nom", Text, nullable=False),
    Column("niveau", Integer),
    Column("ordre", Integer, nullable=False),
    Column("bloc", Text),
    Column("duffus_id", Text),
    Column("dofusdb_id", Integer),
    Column("origine", Text, nullable=False),
    Column("succes_source", Text, nullable=False),
    Column("masque", Boolean, nullable=False),
    *_masquage(),
)

case_succes = Table(
    "case_succes", metadata,
    Column("id", Integer, primary_key=True),
    Column("donjon_id", Integer, ForeignKey("donjon.id"), nullable=False),
    Column("ordre", Integer, nullable=False),
    Column("nom", Text, nullable=False),
    Column("condition", Text, nullable=False),
    Column("est_classique", Boolean, nullable=False),
    Column("duffus_id", Text),
    Column("masquee", Boolean, nullable=False),
    *_masquage(),
)

quete = Table(
    "quete", metadata,
    Column("id", Integer, primary_key=True),
    Column("etage_id", Integer, ForeignKey("etage.id"), nullable=False),
    Column("nom", Text, nullable=False),
    Column("niveau", Integer),
    Column("bloc", Text, nullable=False),
    Column("ordre", Integer, nullable=False),
    Column("nature", Text, nullable=False),
    Column("nature_origine", Text, nullable=False),
    Column("nature_motif", Text),
    Column("dofus", ARRAY(Text), nullable=False),
    Column("jusqu_ou", Text),
    Column("a_lier", Text),
    Column("duffus_id", Text),
    Column("dofusdb_id", Integer),
    Column("masquee", Boolean, nullable=False),
    *_masquage(),
)

fiche_quete = Table(
    "fiche_quete", metadata,
    Column("quete_id", Integer, ForeignKey("quete.id"), primary_key=True),
    Column("source", Text, nullable=False),
    Column("contenu", JSONB, nullable=False),
)

liste_officielle = Table(
    "liste_officielle", metadata,
    Column("discord_user_id", BigInteger, primary_key=True),
    Column("statut_initial", Text, nullable=False),
    Column("ajoute_par", BigInteger),
    Column("ajoute_le", Horodatage, nullable=False),
)

grimpeur = Table(
    "grimpeur", metadata,
    Column("id", Integer, primary_key=True),
    Column("discord_user_id", BigInteger, nullable=False, unique=True),
    Column("nom_discord", Text, nullable=False),
    Column("pseudo_ig", Text, nullable=False),
    Column("classe", Text),
    Column("statut", Text, nullable=False),
    Column("niveau_declare", Integer),
    Column("inscrit_le", Horodatage, nullable=False),
)

coche_case = Table(
    "coche_case", metadata,
    Column("grimpeur_id", Integer, ForeignKey("grimpeur.id"), primary_key=True),
    Column("case_id", Integer, ForeignKey("case_succes.id"), primary_key=True),
    Column("cochee_le", Horodatage, nullable=False),
    Column("cochee_par", BigInteger),
)

coche_quete = Table(
    "coche_quete", metadata,
    Column("grimpeur_id", Integer, ForeignKey("grimpeur.id"), primary_key=True),
    Column("quete_id", Integer, ForeignKey("quete.id"), primary_key=True),
    Column("cochee_le", Horodatage, nullable=False),
    Column("cochee_par", BigInteger),
)

suivi_etape = Table(
    "suivi_etape", metadata,
    Column("grimpeur_id", Integer, ForeignKey("grimpeur.id"), primary_key=True),
    Column("quete_id", Integer, ForeignKey("quete.id"), primary_key=True),
    Column("ordre", Integer, primary_key=True),
    Column("cochee_le", Horodatage, nullable=False),
)

bilan_etage = Table(
    "bilan_etage", metadata,
    Column("etage_id", Integer, ForeignKey("etage.id"), primary_key=True),
    Column("fige_le", Horodatage, nullable=False),
    Column("actifs", Integer, nullable=False),
    Column("palier", Integer, nullable=False),
    Column("score", Integer, nullable=False),
    Column("detail", JSONB, nullable=False),
    Column("force", Boolean, nullable=False),
    Column("motif", Text),
)

session = Table(
    "session", metadata,
    Column("id_hache", LargeBinary, primary_key=True),
    Column("discord_user_id", BigInteger, nullable=False),
    Column("nom_discord", Text, nullable=False),
    Column("est_admin", Boolean, nullable=False),
    Column("roles_verifies_le", Horodatage, nullable=False),
    Column("cree_le", Horodatage, nullable=False),
    Column("expire_le", Horodatage, nullable=False),
    Column("jeton_oauth", Text, nullable=False),
    Column("csrf", Text, nullable=False),
)

journal = Table(
    "journal", metadata,
    Column("id", BigInteger, primary_key=True),
    Column("horodatage", Horodatage, nullable=False),
    Column("acteur_discord_id", BigInteger),
    Column("type", Text, nullable=False),
    Column("grimpeur_id", Integer, ForeignKey("grimpeur.id")),
    Column("etage_id", Integer, ForeignKey("etage.id")),
    Column("details", JSONB, nullable=False),
    Column("public", Boolean, nullable=False),
)
