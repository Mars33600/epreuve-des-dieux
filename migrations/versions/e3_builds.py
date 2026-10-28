"""Lot E3 : les builds du builder (un build par ligne, à un grimpeur, partageable dans la guilde).

Révision : e3_builds, après 0001_initial. Référence : docs/lots/E3.md §5.
"""

from alembic import op

revision = "e3_builds"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE epreuve.build (
    id            serial PRIMARY KEY,
    grimpeur_id   integer NOT NULL REFERENCES epreuve.grimpeur(id) ON DELETE CASCADE,
    nom           text NOT NULL CHECK (char_length(nom) BETWEEN 1 AND 80),
    classe        text NOT NULL,
    niveau        integer NOT NULL CHECK (niveau BETWEEN 1 AND 200),
    objets        jsonb NOT NULL DEFAULT '{}',
    caracs_base   jsonb NOT NULL DEFAULT '{}',
    caracs_parcho jsonb NOT NULL DEFAULT '{}',
    note          text NOT NULL DEFAULT '' CHECK (char_length(note) <= 2000),
    partage       boolean NOT NULL DEFAULT false,
    cree_le       timestamptz NOT NULL,
    maj_le        timestamptz NOT NULL
)""")
    # Une instruction par appel : asyncpg refuse plusieurs commandes dans une requête préparée.
    op.execute("CREATE INDEX build_grimpeur ON epreuve.build (grimpeur_id, maj_le DESC)")
    op.execute("CREATE INDEX build_partage ON epreuve.build (maj_le DESC) WHERE partage")


def downgrade() -> None:
    op.execute("DROP TABLE epreuve.build")
