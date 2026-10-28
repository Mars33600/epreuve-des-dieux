"""Lot E2 (suite) : sorts, classes, PNJ, quêtes et page panoplies de l'encyclopédie.

Révision : e2_encyclopedie_suite, après e2_encyclopedie. Référence : docs/lots/E2.md.

Même principe que la première migration : copie en lecture seule des extraits `donnees/duffus/encyclopedie/`,
sans clé étrangère, rechargée en bloc. Les niveaux d'un sort et les étapes d'une quête (avec objectifs et
récompenses) sont rangés en JSONB dans leur fiche : on ne les lit jamais seuls.
"""

from alembic import op

revision = "e2_encyclopedie_suite"
down_revision = "e2_encyclopedie"
branch_labels = None
depends_on = None

TABLES = ("ency_quete", "ency_pnj", "ency_sort", "ency_classe")

UPGRADE = """
ALTER TABLE epreuve.ency_panoplie ADD COLUMN cle_recherche text NOT NULL DEFAULT '';
ALTER TABLE epreuve.ency_panoplie ADD COLUMN niveau integer;
ALTER TABLE epreuve.ency_panoplie ADD COLUMN recherche tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', cle_recherche)) STORED;
CREATE INDEX ency_panoplie_recherche ON epreuve.ency_panoplie USING gin (recherche);
CREATE INDEX ency_panoplie_niveau ON epreuve.ency_panoplie (niveau, id);

CREATE TABLE epreuve.ency_classe (
    id           integer PRIMARY KEY,
    nom          text NOT NULL,
    description  text,
    role         text,
    sorts        integer[] NOT NULL DEFAULT '{}'
);

CREATE TABLE epreuve.ency_sort (
    id             integer PRIMARY KEY,
    nom            text NOT NULL,
    cle_recherche  text NOT NULL,
    description    text,
    icone          integer,
    type_id        integer,
    classe_id      integer,
    niveau_min     integer,
    niveaux        jsonb NOT NULL DEFAULT '[]',
    recherche      tsvector GENERATED ALWAYS AS (to_tsvector('simple', cle_recherche)) STORED
);
CREATE INDEX ency_sort_recherche ON epreuve.ency_sort USING gin (recherche);
CREATE INDEX ency_sort_classe ON epreuve.ency_sort (classe_id, niveau_min, id);

CREATE TABLE epreuve.ency_pnj (
    id             integer PRIMARY KEY,
    nom            text NOT NULL,
    cle_recherche  text NOT NULL,
    genre          integer,
    visible        boolean NOT NULL DEFAULT true,
    recherche      tsvector GENERATED ALWAYS AS (to_tsvector('simple', cle_recherche)) STORED
);
CREATE INDEX ency_pnj_recherche ON epreuve.ency_pnj USING gin (recherche);
CREATE INDEX ency_pnj_nom ON epreuve.ency_pnj (cle_recherche, id);

CREATE TABLE epreuve.ency_quete (
    id             integer PRIMARY KEY,
    nom            text NOT NULL,
    cle_recherche  text NOT NULL,
    categorie      text,
    zone           text,
    niveau_min     integer,
    niveau_max     integer,
    repetition     integer,
    limite         integer,
    donjon         boolean NOT NULL DEFAULT false,
    groupe         boolean NOT NULL DEFAULT false,
    evenement      boolean NOT NULL DEFAULT false,
    condition      text,
    depart         jsonb NOT NULL DEFAULT '[]',
    pnj_ids        integer[] NOT NULL DEFAULT '{}',
    etapes         jsonb NOT NULL DEFAULT '[]',
    recherche      tsvector GENERATED ALWAYS AS (to_tsvector('simple', cle_recherche)) STORED
);
CREATE INDEX ency_quete_recherche ON epreuve.ency_quete USING gin (recherche);
CREATE INDEX ency_quete_niveau ON epreuve.ency_quete (niveau_min, id);
CREATE INDEX ency_quete_pnj ON epreuve.ency_quete USING gin (pnj_ids);
"""


def upgrade() -> None:
    for instruction in UPGRADE.split(";\n"):
        if instruction.strip():
            op.execute(instruction)
    for table in TABLES:
        op.execute(f"ALTER TABLE epreuve.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE epreuve.{table}")
    op.execute("DROP INDEX epreuve.ency_panoplie_niveau")
    op.execute("DROP INDEX epreuve.ency_panoplie_recherche")
    for col in ("recherche", "niveau", "cle_recherche"):
        op.execute(f"ALTER TABLE epreuve.ency_panoplie DROP COLUMN {col}")
