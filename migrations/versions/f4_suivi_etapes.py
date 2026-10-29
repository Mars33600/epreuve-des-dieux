"""Lot F4 : le suivi étape par étape d'une quête, pour le grimpeur connecté.

Révision : f4_suivi_etapes, après e3_fm. Une ligne = une étape cochée par un grimpeur sur une quête (`ordre` :
le numéro de l'étape dans la fiche). Cocher la dernière étape ne coche PAS la quête : la case « Faite »
(`coche_quete`) reste seule à compter pour les points. Personnel, hors journal.
"""

from alembic import op

revision = "f4_suivi_etapes"
down_revision = "e3_fm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE epreuve.suivi_etape (
    grimpeur_id  integer NOT NULL REFERENCES epreuve.grimpeur(id) ON DELETE RESTRICT,
    quete_id     integer NOT NULL REFERENCES epreuve.quete(id) ON DELETE RESTRICT,
    ordre        integer NOT NULL CHECK (ordre >= 1),
    cochee_le    timestamptz NOT NULL,
    PRIMARY KEY (grimpeur_id, quete_id, ordre)
)""")
    op.execute("ALTER TABLE epreuve.suivi_etape ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TABLE epreuve.suivi_etape")
