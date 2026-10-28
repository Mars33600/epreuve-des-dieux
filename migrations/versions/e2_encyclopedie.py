"""Lot E2 : encyclopédie (objets, ressources, monstres, recettes, panoplies) et stuffs recommandés.

Révision : e2_encyclopedie, après 0001_initial. Référence : docs/lots/E2.md.

Ces tables sont une copie en lecture seule des extraits `donnees/duffus/encyclopedie/*.jsonl`, rechargée en
bloc par `python -m epreuve.encyclopedie charger`. Aucune clé étrangère entre elles : les données du jeu
citent parfois un objet ou un monstre absent, et la page l'affiche alors comme « inconnu ».

Recherche rapide sans extension (rien à activer chez Supabase) : `cle_recherche` est le nom en minuscules
sans accents, calculé au chargement ; une colonne `tsvector` générée (configuration `simple`) et son index GIN
servent la recherche par début de mots (« epee boi » → « Épée de Boisaille »).
"""

from alembic import op

revision = "e2_encyclopedie"
down_revision = "e1_captures"
branch_labels = None
depends_on = None

TABLES = ("ency_stuff", "ency_monstre", "ency_race", "ency_recette", "ency_objet", "ency_panoplie", "ency_effet",
          "ency_type")

UPGRADE = """
CREATE TABLE epreuve.ency_type (
    id          integer PRIMARY KEY,
    nom         text NOT NULL,
    super_type  integer,
    famille     text NOT NULL CHECK (famille IN ('equipements', 'armes', 'familiers', 'ressources',
                                                 'consommables', 'quetes', 'cosmetiques', 'autres'))
);

CREATE TABLE epreuve.ency_effet (
    id               integer PRIMARY KEY,
    description      text,
    caracteristique  integer,
    categorie        integer,
    priorite         integer,
    element          integer
);

CREATE TABLE epreuve.ency_panoplie (
    id      integer PRIMARY KEY,
    nom     text NOT NULL,
    objets  integer[] NOT NULL DEFAULT '{}',
    bonus   jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE epreuve.ency_objet (
    id             integer PRIMARY KEY,
    nom            text NOT NULL,
    cle_recherche  text NOT NULL,
    type_id        integer NOT NULL,
    famille        text NOT NULL,
    niveau         integer,
    description    text,
    icone          integer,
    panoplie_id    integer,
    effets         jsonb NOT NULL DEFAULT '[]',
    conditions     text,
    drops          integer[] NOT NULL DEFAULT '{}',
    prix           integer,
    poids          integer,
    arme           jsonb,
    echangeable    boolean,
    legendaire     boolean,
    recherche      tsvector GENERATED ALWAYS AS (to_tsvector('simple', cle_recherche)) STORED
);
CREATE INDEX ency_objet_recherche ON epreuve.ency_objet USING gin (recherche);
CREATE INDEX ency_objet_famille_niveau ON epreuve.ency_objet (famille, niveau, id);
CREATE INDEX ency_objet_type_niveau ON epreuve.ency_objet (type_id, niveau, id);
CREATE INDEX ency_objet_panoplie ON epreuve.ency_objet (panoplie_id) WHERE panoplie_id IS NOT NULL;

CREATE TABLE epreuve.ency_recette (
    objet_id        integer PRIMARY KEY,
    niveau          integer,
    metier          integer,
    ingredients     jsonb NOT NULL,
    ingredient_ids  integer[] NOT NULL
);
CREATE INDEX ency_recette_ingredients ON epreuve.ency_recette USING gin (ingredient_ids);
CREATE INDEX ency_recette_metier ON epreuve.ency_recette (metier, niveau);

CREATE TABLE epreuve.ency_race (
    id          integer PRIMARY KEY,
    nom         text NOT NULL,
    super_race  integer
);

CREATE TABLE epreuve.ency_monstre (
    id             integer PRIMARY KEY,
    nom            text NOT NULL,
    cle_recherche  text NOT NULL,
    race_id        integer,
    gfx            integer,
    niveau_min     integer,
    niveau_max     integer,
    grades         jsonb NOT NULL DEFAULT '[]',
    drops          jsonb NOT NULL DEFAULT '[]',
    recherche      tsvector GENERATED ALWAYS AS (to_tsvector('simple', cle_recherche)) STORED
);
CREATE INDEX ency_monstre_recherche ON epreuve.ency_monstre USING gin (recherche);
CREATE INDEX ency_monstre_race_niveau ON epreuve.ency_monstre (race_id, niveau_min, id);
CREATE INDEX ency_monstre_niveau ON epreuve.ency_monstre (niveau_min, id);

CREATE TABLE epreuve.ency_stuff (
    id           text PRIMARY KEY,
    nom          text NOT NULL,
    classe       text,
    niveau       integer NOT NULL CHECK (niveau BETWEEN 1 AND 200),
    sexe         text,
    objets       jsonb NOT NULL DEFAULT '{}',
    dofus        integer[] NOT NULL DEFAULT '{}',
    tags         text[] NOT NULL DEFAULT '{}',
    caracs       jsonb NOT NULL DEFAULT '{}',
    maj_le       timestamptz
);
CREATE INDEX ency_stuff_niveau ON epreuve.ency_stuff (niveau);
"""


def upgrade() -> None:
    # asyncpg n'exécute qu'une instruction à la fois : on découpe sur les « ; » de fin de ligne.
    for instruction in UPGRADE.split(";\n"):
        if instruction.strip():
            op.execute(instruction)
    for table in TABLES:
        # Ceinture de sécurité, comme au lot B : hors de l'API REST de Supabase.
        op.execute(f"ALTER TABLE epreuve.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE epreuve.{table}")
