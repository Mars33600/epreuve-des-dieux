"""Les blocs du guide Duffus, unité de cochage de la v5 (SPEC-V5 §3 à §5).

Révision : g2_blocs, après g1_recherche.

- `epreuve.bloc` : un bloc du guide d'une tranche (titre exact de Duffus, rang dans tout le guide, ordre dans la
  tranche), sa nature (« principale » si le bloc contient au moins une quête principale, sinon « secondaire »,
  corrigeable par un admin avec un motif, et la correction survit aux reconstructions), et le lien vers duffus.fr.
- `epreuve.quete.bloc_id` : le bloc qui contient la quête (le nombre de quêtes d'un bloc et celui de ses principales
  se comptent à la lecture, jamais stockés : ils ne peuvent pas se périmer).
- `epreuve.coche_bloc` : la coche d'un bloc par un grimpeur. Les coches de quêtes ne servent plus au barème ;
  `coche_quete` reste en base (on désactive, on ne supprime pas).
- Reprise : les quêtes déjà en base reçoivent leurs blocs, tirés de leur colonne `bloc`. La reconstruction d'un
  étage (`python -m epreuve.contenu construire --etage N`) les complète avec le rang et le lien Duffus exacts.
"""

from alembic import op

revision = "g2_blocs"
down_revision = "g1_recherche"
branch_labels = None
depends_on = None

URL_GUIDE = "https://duffus.fr/guide-complet"


def _executer(script: str) -> None:
    """Une instruction par appel : asyncpg refuse plusieurs commandes dans une même requête préparée."""
    for instruction in script.split(";\n"):
        if instruction.strip():
            op.execute(instruction.strip())


def upgrade() -> None:
    _executer(f"""
CREATE TABLE epreuve.bloc (
    id               serial PRIMARY KEY,
    etage_id         integer NOT NULL REFERENCES epreuve.etage(id) ON DELETE RESTRICT,
    titre            text NOT NULL,
    numero           integer CHECK (numero >= 1),
    ordre            integer NOT NULL,
    nature           text NOT NULL CHECK (nature IN ('principale', 'secondaire')),
    nature_origine   text NOT NULL DEFAULT 'construction' CHECK (nature_origine IN ('construction', 'admin')),
    nature_motif     text,
    duffus_url       text,
    duffus_ancre     text,
    masque           boolean NOT NULL DEFAULT false,
    masque_par       text CHECK (masque_par IN ('admin', 'construction')),
    UNIQUE (etage_id, titre),
    CHECK (nature_origine <> 'admin' OR nature_motif IS NOT NULL)
);
CREATE INDEX bloc_etage ON epreuve.bloc (etage_id, ordre);

ALTER TABLE epreuve.quete ADD COLUMN bloc_id integer REFERENCES epreuve.bloc(id) ON DELETE SET NULL;
CREATE INDEX quete_bloc ON epreuve.quete (bloc_id);

CREATE TABLE epreuve.coche_bloc (
    grimpeur_id  integer NOT NULL REFERENCES epreuve.grimpeur(id) ON DELETE RESTRICT,
    bloc_id      integer NOT NULL REFERENCES epreuve.bloc(id) ON DELETE RESTRICT,
    cochee_le    timestamptz NOT NULL,
    cochee_par   bigint,
    PRIMARY KEY (grimpeur_id, bloc_id)
);
CREATE INDEX coche_bloc_bloc ON epreuve.coche_bloc (bloc_id);

ALTER TABLE epreuve.bloc ENABLE ROW LEVEL SECURITY;
ALTER TABLE epreuve.coche_bloc ENABLE ROW LEVEL SECURITY;

-- Reprise des étages déjà construits : un bloc par titre de quête, dans l'ordre du guide.
INSERT INTO epreuve.bloc (etage_id, titre, ordre, nature, duffus_url)
SELECT etage_id, bloc,
       row_number() OVER (PARTITION BY etage_id ORDER BY min(ordre)),
       CASE WHEN bool_or(nature = 'principale') THEN 'principale' ELSE 'secondaire' END,
       '{URL_GUIDE}'
FROM epreuve.quete GROUP BY etage_id, bloc;
UPDATE epreuve.quete q SET bloc_id = b.id FROM epreuve.bloc b WHERE b.etage_id = q.etage_id AND b.titre = q.bloc;
""")  # noqa: S608 (URL_GUIDE est une constante du module, pas une saisie)


def downgrade() -> None:
    _executer("""
DROP TABLE epreuve.coche_bloc;
ALTER TABLE epreuve.quete DROP COLUMN bloc_id;
DROP TABLE epreuve.bloc;
""")
