"""Les blocs hybrides coupés en deux moitiés (décision de Marceau et Shadoaze, 06/11).

Révision : h1_blocs_hybrides, après g3_annonce_lancement.

Un bloc du guide qui contient des quêtes principales ET des quêtes secondaires devient deux lignes `bloc` de même
titre et de même numéro : la moitié principale (ses quêtes principales) et la moitié secondaire (ses secondaires).
Chacune se coche à part ; le barème, le « qui a fait quoi » et le tableau de bord marchent alors sans cas spécial.

- `epreuve.bloc.partie` : la nature des quêtes de la ligne. La clé d'une ligne devient (étage, titre, partie) au lieu
  de (étage, titre) : la reconstruction retrouve ainsi chaque moitié, sans doublon et avec ses coches.
- Reprise : chaque bloc hybride déjà en base reçoit sa moitié secondaire, et ses quêtes secondaires y passent. Une
  quête masquée par la construction (disparue de Duffus) ne compte pas pour décider si le bloc est hybride.
- Règle des corrections d'admin : une correction posée sur un bloc entier reste tant qu'il est entier ; sur un bloc
  hybride, elle ne s'applique plus (chaque moitié prend la nature de ses quêtes). Pour déplacer une quête d'une
  moitié à l'autre, l'admin corrige la nature de la quête.
- Les coches d'un bloc hybride restent sur sa moitié principale (ce sont des données de test, effacées le 12/11).
"""

from alembic import op

revision = "h1_blocs_hybrides"
down_revision = "g3_annonce_lancement"
branch_labels = None
depends_on = None

# Les quêtes qui comptent pour couper un bloc : toutes, sauf celles que la construction a masquées.
_COMPTE = "(NOT q.masquee OR q.masque_par IS DISTINCT FROM 'construction')"


def _executer(script: str) -> None:
    """Une instruction par appel : asyncpg refuse plusieurs commandes dans une même requête préparée."""
    for instruction in script.split(";\n"):
        if instruction.strip():
            op.execute(instruction.strip())


def upgrade() -> None:
    _executer(f"""
ALTER TABLE epreuve.bloc ADD COLUMN partie text;
UPDATE epreuve.bloc b SET partie = CASE WHEN EXISTS (
    SELECT 1 FROM epreuve.quete q WHERE q.bloc_id = b.id AND q.nature = 'principale' AND {_COMPTE})
    THEN 'principale' ELSE 'secondaire' END;
ALTER TABLE epreuve.bloc ALTER COLUMN partie SET NOT NULL;
ALTER TABLE epreuve.bloc ADD CONSTRAINT bloc_partie_check CHECK (partie IN ('principale', 'secondaire'));
ALTER TABLE epreuve.bloc DROP CONSTRAINT bloc_etage_id_titre_key;
ALTER TABLE epreuve.bloc ADD CONSTRAINT bloc_etage_titre_partie_key UNIQUE (etage_id, titre, partie);

-- Les hybrides : une moitié principale (la ligne existante) qui a aussi des quêtes secondaires.
CREATE TEMPORARY TABLE hybride ON COMMIT DROP AS
    SELECT b.id FROM epreuve.bloc b WHERE b.partie = 'principale' AND EXISTS (
        SELECT 1 FROM epreuve.quete q WHERE q.bloc_id = b.id AND q.nature = 'secondaire' AND {_COMPTE});
INSERT INTO epreuve.bloc (etage_id, titre, numero, ordre, nature, nature_origine, partie, duffus_url, duffus_ancre,
                          masque, masque_par)
    SELECT etage_id, titre, numero, ordre, 'secondaire', 'construction', 'secondaire', duffus_url, duffus_ancre,
           masque, masque_par
    FROM epreuve.bloc WHERE id IN (SELECT id FROM hybride);
UPDATE epreuve.quete q SET bloc_id = moitie.id
    FROM epreuve.bloc ancien, epreuve.bloc moitie
    WHERE q.bloc_id = ancien.id AND ancien.id IN (SELECT id FROM hybride) AND q.nature = 'secondaire'
      AND moitie.etage_id = ancien.etage_id AND moitie.titre = ancien.titre AND moitie.partie = 'secondaire';
UPDATE epreuve.bloc SET nature = 'principale', nature_origine = 'construction', nature_motif = NULL
    WHERE id IN (SELECT id FROM hybride)
""")  # noqa: S608 (_COMPTE est une constante du module, pas une saisie)


def downgrade() -> None:
    """Recolle les moitiés : la secondaire rend ses quêtes à la principale, puis disparaît avec ses coches."""
    _executer("""
CREATE TEMPORARY TABLE moitie ON COMMIT DROP AS
    SELECT s.id AS secondaire, p.id AS principale FROM epreuve.bloc s JOIN epreuve.bloc p
        ON p.etage_id = s.etage_id AND p.titre = s.titre AND p.partie = 'principale'
    WHERE s.partie = 'secondaire';
UPDATE epreuve.quete q SET bloc_id = m.principale FROM moitie m WHERE q.bloc_id = m.secondaire;
DELETE FROM epreuve.coche_bloc WHERE bloc_id IN (SELECT secondaire FROM moitie);
DELETE FROM epreuve.bloc WHERE id IN (SELECT secondaire FROM moitie);
ALTER TABLE epreuve.bloc DROP CONSTRAINT bloc_etage_titre_partie_key;
ALTER TABLE epreuve.bloc ADD CONSTRAINT bloc_etage_id_titre_key UNIQUE (etage_id, titre);
ALTER TABLE epreuve.bloc DROP COLUMN partie
""")
