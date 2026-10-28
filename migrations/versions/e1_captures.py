"""Module E1 : archimonstres, boss du Dofus Ocre, avis de recherche, et les captures des grimpeurs.

Révision : e1_captures (après 0001_initial). Écrit en SQL, comme 0001. Référence : docs/lots/E1.md.

- le catalogue (`archimonstre`, `boss_ocre`, `avis_recherche`) garde les identifiants de Duffus, rechargé par
  `python -m epreuve.captures charger` ; un élément que Duffus n'a plus est `retire`, jamais supprimé ;
- une capture est une ligne : `nombre` d'exemplaires (1 à 999) pour un archi ou un boss, présence pour un
  avis ; à 0 ou au décochage, la ligne est supprimée ;
- `archi_personnages` : le nombre de personnages visé (1 à 8), 1 sans ligne ;
- clés étrangères en ON DELETE RESTRICT, comme les coches du lot B ; RLS activée sans règle.
"""

from alembic import op

revision = "e1_captures"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

TABLES = ("archi_personnages", "capture_avis", "capture_boss", "capture_archi", "avis_recherche", "boss_ocre",
          "archimonstre")

UPGRADE = """
CREATE TABLE epreuve.archimonstre (
    id          integer PRIMARY KEY,
    nom         text NOT NULL,
    etape       integer,
    zones       jsonb NOT NULL DEFAULT '[]'::jsonb,
    monstre_id  integer,
    gfx_id      integer,
    niveau_min  integer,
    niveau_max  integer,
    retire      boolean NOT NULL DEFAULT false,
    maj_le      timestamptz NOT NULL
);
CREATE TABLE epreuve.boss_ocre (
    id          integer PRIMARY KEY,
    nom         text NOT NULL,
    etape       integer,
    monstre_id  integer,
    gfx_id      integer,
    niveau      integer,
    retire      boolean NOT NULL DEFAULT false,
    maj_le      timestamptz NOT NULL
);
CREATE TABLE epreuve.avis_recherche (
    id               integer PRIMARY KEY,
    slug             text NOT NULL UNIQUE,
    nom              text NOT NULL,
    niveau_texte     text,
    niveau           integer,
    zone             text,
    milice           text,
    recompense       integer CHECK (recompense >= 0),
    recompense_type  text NOT NULL CHECK (recompense_type IN ('aviton', 'aliton')),
    chasse           boolean NOT NULL DEFAULT false,
    monstre_id       integer,
    gfx_id           integer,
    resume_html      text NOT NULL DEFAULT '',
    grades           jsonb NOT NULL DEFAULT '[]'::jsonb,
    retire           boolean NOT NULL DEFAULT false,
    maj_le           timestamptz NOT NULL
);
CREATE TABLE epreuve.capture_archi (
    grimpeur_id      integer NOT NULL REFERENCES epreuve.grimpeur(id) ON DELETE RESTRICT,
    archimonstre_id  integer NOT NULL REFERENCES epreuve.archimonstre(id) ON DELETE RESTRICT,
    nombre           integer NOT NULL CHECK (nombre BETWEEN 1 AND 999),
    maj_le           timestamptz NOT NULL,
    PRIMARY KEY (grimpeur_id, archimonstre_id)
);
CREATE INDEX capture_archi_element ON epreuve.capture_archi (archimonstre_id);
CREATE TABLE epreuve.capture_boss (
    grimpeur_id  integer NOT NULL REFERENCES epreuve.grimpeur(id) ON DELETE RESTRICT,
    boss_id      integer NOT NULL REFERENCES epreuve.boss_ocre(id) ON DELETE RESTRICT,
    nombre       integer NOT NULL CHECK (nombre BETWEEN 1 AND 999),
    maj_le       timestamptz NOT NULL,
    PRIMARY KEY (grimpeur_id, boss_id)
);
CREATE INDEX capture_boss_element ON epreuve.capture_boss (boss_id);
CREATE TABLE epreuve.capture_avis (
    grimpeur_id  integer NOT NULL REFERENCES epreuve.grimpeur(id) ON DELETE RESTRICT,
    avis_id      integer NOT NULL REFERENCES epreuve.avis_recherche(id) ON DELETE RESTRICT,
    capture_le   timestamptz NOT NULL,
    PRIMARY KEY (grimpeur_id, avis_id)
);
CREATE INDEX capture_avis_element ON epreuve.capture_avis (avis_id);
CREATE TABLE epreuve.archi_personnages (
    grimpeur_id  integer PRIMARY KEY REFERENCES epreuve.grimpeur(id) ON DELETE RESTRICT,
    nombre       integer NOT NULL CHECK (nombre BETWEEN 1 AND 8)
)
"""


def upgrade() -> None:
    # asyncpg n'exécute qu'une instruction à la fois : on découpe sur les « ; » de fin de ligne.
    for instruction in UPGRADE.split(";\n"):
        if instruction.strip():
            op.execute(instruction)
    for table in TABLES:
        op.execute(f"ALTER TABLE epreuve.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS epreuve.{table}")
