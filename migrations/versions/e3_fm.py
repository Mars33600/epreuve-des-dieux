"""Lot E3 : la forgemagie d'un build (jets choisis et exos, par emplacement).

Révision : e3_fm, après e3_builds. Référence : docs/lots/E3.md §3 quater.
"""

from alembic import op

revision = "e3_fm"
down_revision = "e3_builds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE epreuve.build ADD COLUMN fm jsonb NOT NULL DEFAULT '{}'")


def downgrade() -> None:
    op.execute("ALTER TABLE epreuve.build DROP COLUMN fm")
