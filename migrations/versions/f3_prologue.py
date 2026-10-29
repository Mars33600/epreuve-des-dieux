"""Prologue de Shadoaze : retient la première fois qu'un grimpeur a passé le prologue plein écran.

Révision : f3_prologue, après f4_suivi_etapes. Référence : docs/DECISIONS-V4.md §13.
"""

from alembic import op

revision = "f3_prologue"
down_revision = "f4_suivi_etapes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE epreuve.grimpeur ADD COLUMN prologue_vu_le timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE epreuve.grimpeur DROP COLUMN prologue_vu_le")
