"""Lot E3 : les variantes d'un build (un second objet par emplacement, avec sa forgemagie, hors des totaux).

Révision : e3_variantes, après f4_suivi_etapes. Référence : docs/lots/E3.md §3 quinquies.
"""

from alembic import op

revision = "e3_variantes"
down_revision = "f4_suivi_etapes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE epreuve.build ADD COLUMN variantes jsonb NOT NULL DEFAULT '{}'")


def downgrade() -> None:
    op.execute("ALTER TABLE epreuve.build DROP COLUMN variantes")
