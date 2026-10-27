"""Description des tables pour SQLAlchemy (mode « Core » : des tables et des requêtes, sans ORM).

Le schéma lui-même est créé par la migration `0001_initial` ; ce fichier sert à écrire
les requêtes en Python. Les deux doivent rester d'accord : les tests de base le vérifient
en lisant et écrivant à travers ces tables sur une base migrée.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

SCHEMA = "epreuve"
metadata = MetaData(schema=SCHEMA)
Horodatage = DateTime(timezone=True)  # « timestamptz » : toujours avec fuseau

etage = Table(
    "etage", metadata,
    Column("id", Integer, primary_key=True),
    Column("numero", Integer, nullable=False, unique=True),
    Column("nom", Text, nullable=False),
    Column("level_cap", Integer, nullable=False),
    Column("seuil_pourcent", Integer, nullable=False, server_default="75"),
    Column("statut", Text, nullable=False, server_default="scelle"),
    Column("ouvert_le", Horodatage),
    Column("date_plancher_suivant", Horodatage),
    Column("zone_quetes", Text, nullable=False, server_default=""),
    Column("donjons_affiches", ARRAY(Text), nullable=False, server_default="{}"),
    Column("chapitre_guide", Text),
)  # fmt: skip

palier = Table(
    "palier", metadata,
    Column("id", Integer, primary_key=True),
    Column("etage_id", Integer, ForeignKey("etage.id"), nullable=False),
    Column("rang", Integer, nullable=False),
    Column("libelle", Text, nullable=False),
)  # fmt: skip

contenu = Table(
    "contenu", metadata,
    Column("id", Integer, primary_key=True),
    Column("etage_id", Integer, ForeignKey("etage.id"), nullable=False),
    Column("type", Text, nullable=False),
    Column("nom", Text, nullable=False),
    Column("nom_court", Text, nullable=False),
    Column("dofusdb_type", Text),
    Column("dofusdb_id", Integer),
    Column("dofusdb_ids_couverts", ARRAY(Integer)),
)  # fmt: skip

palier_contenu = Table(
    "palier_contenu", metadata,
    Column("palier_id", Integer, ForeignKey("palier.id"), primary_key=True),
    Column("contenu_id", Integer, ForeignKey("contenu.id"), primary_key=True),
)  # fmt: skip

grimpeur = Table(
    "grimpeur", metadata,
    Column("id", Integer, primary_key=True),
    Column("pseudo_ig", Text, nullable=False),
    Column("classe", Text, nullable=False),
    Column("difficulte", Text, nullable=False),
    Column("statut", Text, nullable=False, server_default="actif"),
    Column("discord_user_id", BigInteger),
    Column("niveau_connu", Integer),
    Column("niveau_maj_le", Horodatage),
    Column("inscrit_le", Horodatage, nullable=False),
)  # fmt: skip

preuve = Table(
    "preuve", metadata,
    Column("id", Integer, primary_key=True),
    Column("discord_guild_id", BigInteger, nullable=False),
    Column("discord_channel_id", BigInteger, nullable=False),
    Column("discord_message_id", BigInteger, nullable=False, unique=True),
    Column("lien", Text, nullable=False),
    Column("auteur_discord_id", BigInteger),
    Column("poste_le", Horodatage, nullable=False),
    Column("image_chemin", Text),
    Column("analyse_ia", JSONB),
    Column("statut_ia", Text, nullable=False, server_default="sans"),
    Column("cree_le", Horodatage, nullable=False),
)  # fmt: skip

validation = Table(
    "validation", metadata,
    Column("id", Integer, primary_key=True),
    Column("grimpeur_id", Integer, ForeignKey("grimpeur.id"), nullable=False),
    Column("contenu_id", Integer, ForeignKey("contenu.id"), nullable=False),
    Column("preuve_id", Integer, ForeignKey("preuve.id")),
    Column("niveau", Integer),
    Column("statut", Text, nullable=False),
    Column("forcee", Boolean, nullable=False, server_default="false"),
    Column("motif", Text),
    Column("source", Text, nullable=False, server_default="manuelle"),
    Column("decidee_par", BigInteger, nullable=False),
    Column("decidee_le", Horodatage, nullable=False),
    Column("realisee_le", Horodatage, nullable=False),
)  # fmt: skip

journal = Table(
    "journal", metadata,
    Column("id", BigInteger, primary_key=True),
    Column("horodatage", Horodatage, nullable=False),
    Column("acteur_discord_id", BigInteger),
    Column("type", Text, nullable=False),
    Column("grimpeur_id", Integer, ForeignKey("grimpeur.id")),
    Column("etage_id", Integer, ForeignKey("etage.id")),
    Column("details", JSONB, nullable=False),
    Column("public", Boolean, nullable=False, server_default="false"),
)  # fmt: skip
