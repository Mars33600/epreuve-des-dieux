"""Pré-inscription (11/11) : la réponse à « dispo vendredi 16 h-17 h pour rejoindre la guilde ? ».

Révision : i1_dispo_guilde, après h1_blocs_hybrides. « oui », ou le texte libre « à partir de quand ».
"""

from alembic import op

revision = "i1_dispo_guilde"
down_revision = "h1_blocs_hybrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE epreuve.grimpeur ADD COLUMN dispo_guilde text")


def downgrade() -> None:
    op.execute("ALTER TABLE epreuve.grimpeur DROP COLUMN dispo_guilde")
