"""Les tables `ency_*` pour SQLAlchemy Core (le schéma est créé par la migration `e2_encyclopedie`)."""

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

metadata = MetaData(schema="epreuve")

ency_type = Table("ency_type", metadata, Column("id", Integer, primary_key=True), Column("nom", Text),
                  Column("super_type", Integer), Column("famille", Text))
ency_effet = Table("ency_effet", metadata, Column("id", Integer, primary_key=True), Column("description", Text),
                   Column("caracteristique", Integer), Column("categorie", Integer), Column("priorite", Integer),
                   Column("element", Integer))
ency_panoplie = Table("ency_panoplie", metadata, Column("id", Integer, primary_key=True), Column("nom", Text),
                      Column("objets", ARRAY(Integer)), Column("bonus", JSONB))
ency_objet = Table(
    "ency_objet", metadata,
    Column("id", Integer, primary_key=True), Column("nom", Text), Column("cle_recherche", Text),
    Column("type_id", Integer), Column("famille", Text), Column("niveau", Integer), Column("description", Text),
    Column("icone", Integer), Column("panoplie_id", Integer), Column("effets", JSONB), Column("conditions", Text),
    Column("drops", ARRAY(Integer)), Column("prix", Integer), Column("poids", Integer), Column("arme", JSONB),
    Column("echangeable", Boolean), Column("legendaire", Boolean),
    Column("recherche", TSVECTOR),  # générée par Postgres : jamais écrite
)  # fmt: skip
ency_recette = Table("ency_recette", metadata, Column("objet_id", Integer, primary_key=True),
                     Column("niveau", Integer), Column("metier", Integer), Column("ingredients", JSONB),
                     Column("ingredient_ids", ARRAY(Integer)))
ency_race = Table("ency_race", metadata, Column("id", Integer, primary_key=True), Column("nom", Text),
                  Column("super_race", Integer))
ency_monstre = Table(
    "ency_monstre", metadata,
    Column("id", Integer, primary_key=True), Column("nom", Text), Column("cle_recherche", Text),
    Column("race_id", Integer), Column("gfx", Integer), Column("niveau_min", Integer), Column("niveau_max", Integer),
    Column("grades", JSONB), Column("drops", JSONB),
    Column("recherche", TSVECTOR),
)  # fmt: skip
ency_stuff = Table(
    "ency_stuff", metadata,
    Column("id", Text, primary_key=True), Column("nom", Text), Column("classe", Text), Column("niveau", Integer),
    Column("sexe", Text), Column("objets", JSONB), Column("dofus", ARRAY(Integer)), Column("tags", ARRAY(Text)),
    Column("caracs", JSONB), Column("maj_le", DateTime(timezone=True)),
)  # fmt: skip
