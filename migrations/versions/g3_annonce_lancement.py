"""L'annonce du lancement du site, une seule fois : un index unique partiel sur le journal.

Révision : g3_annonce_lancement, après g2_blocs.

Le Gardien de la Tour annonce l'ouverture du site sur Discord avec un `@everyone` : un doublon (redémarrage, deux
machines qui veillent en même temps) préviendrait tout le serveur deux fois. La veille inscrit d'abord une ligne
`annonce_lancement` au journal, puis envoie. Cet index n'admet qu'UNE ligne de ce type : la seconde inscription
est refusée par Postgres lui-même (`ON CONFLICT DO NOTHING`), quel que soit l'ordre d'arrivée, et celle-là n'envoie
rien. Partiel (`WHERE`) : les autres types du journal gardent autant de lignes qu'ils veulent.
"""

from alembic import op

revision = "g3_annonce_lancement"
down_revision = "g2_blocs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX journal_annonce_lancement_unique ON epreuve.journal (type) "
               "WHERE type = 'annonce_lancement'")


def downgrade() -> None:
    op.execute("DROP INDEX epreuve.journal_annonce_lancement_unique")
