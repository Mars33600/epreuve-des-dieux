"""Recensement des métiers (15/11) : le niveau de chaque métier déclaré par un grimpeur.

Révision : j1_metiers, après i1_dispo_guilde. Une ligne par (grimpeur, métier) ; pas de ligne = pas ce métier.
"""

from alembic import op

revision = "j1_metiers"
down_revision = "i1_dispo_guilde"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE epreuve.metier (
            grimpeur_id integer NOT NULL REFERENCES epreuve.grimpeur(id),
            metier text NOT NULL,
            niveau integer NOT NULL CHECK (niveau BETWEEN 1 AND 200),
            maj_le timestamptz NOT NULL,
            PRIMARY KEY (grimpeur_id, metier)
        )
    """)
    # Comme les autres tables : RLS sans politique, aucun accès par l'API publique de Supabase.
    op.execute("ALTER TABLE epreuve.metier ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TABLE epreuve.metier")
