"""Schéma initial : étages, paliers, contenus, grimpeurs, preuves, validations, journal.

Révision : 0001_initial
Écrit en SQL, volontairement : c'est exactement ce que Postgres exécute, contraintes comprises.
Référence : ARCHITECTURE.md §5.
"""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Les 19 classes de Dofus 3, recopiées ici (et non importées depuis le code) : une migration
# est une photo figée du schéma, elle ne doit pas changer si le code change plus tard.
CLASSES = (
    "Féca", "Osamodas", "Enutrof", "Sram", "Xélor", "Ecaflip", "Eniripsa", "Iop", "Crâ", "Sadida",
    "Sacrieur", "Pandawa", "Roublard", "Zobal", "Steamer", "Eliotrope", "Huppermage", "Ouginak",
    "Forgelance",
)  # fmt: skip
_CLASSES_SQL = ", ".join("'" + c + "'" for c in CLASSES)

TABLES = ("journal", "validation", "preuve", "grimpeur", "palier_contenu", "contenu", "palier", "etage")

UPGRADE = f"""
CREATE SCHEMA IF NOT EXISTS epreuve;

CREATE TABLE epreuve.etage (
    id                     serial PRIMARY KEY,
    numero                 integer NOT NULL UNIQUE CHECK (numero >= 0),
    nom                    text NOT NULL,
    level_cap              integer NOT NULL CHECK (level_cap BETWEEN 1 AND 200),
    seuil_pourcent         integer NOT NULL DEFAULT 75 CHECK (seuil_pourcent BETWEEN 1 AND 100),
    statut                 text NOT NULL DEFAULT 'scelle' CHECK (statut IN ('scelle', 'ouvert', 'termine')),
    ouvert_le              timestamptz,
    date_plancher_suivant  timestamptz,
    zone_quetes            text NOT NULL DEFAULT '',
    donjons_affiches       text[] NOT NULL DEFAULT '{{}}',
    chapitre_guide         text            -- étage N = chapitre N du guide Duffus (palier 3)
);
-- Au plus un étage ouvert à la fois.
CREATE UNIQUE INDEX etage_un_seul_ouvert ON epreuve.etage (statut) WHERE statut = 'ouvert';

-- Les trois paliers de points d'un étage (1 = donjons, 2 = full succès, 3 = quêtes).
CREATE TABLE epreuve.palier (
    id        serial PRIMARY KEY,
    etage_id  integer NOT NULL REFERENCES epreuve.etage(id),
    rang      integer NOT NULL CHECK (rang BETWEEN 1 AND 3),
    libelle   text NOT NULL,
    UNIQUE (etage_id, rang)
);

CREATE TABLE epreuve.contenu (
    id                    serial PRIMARY KEY,
    etage_id              integer NOT NULL REFERENCES epreuve.etage(id),
    type                  text NOT NULL CHECK (type IN ('succes', 'quete', 'lot_quetes', 'autre')),
    nom                   text NOT NULL,
    nom_court             text NOT NULL,
    dofusdb_type          text,
    dofusdb_id            integer,
    dofusdb_ids_couverts  integer[]
);
CREATE UNIQUE INDEX contenu_dofusdb_unique ON epreuve.contenu (etage_id, dofusdb_type, dofusdb_id)
    WHERE dofusdb_id IS NOT NULL;

-- Les contenus qu'AJOUTE chaque palier (un contenu peut servir à deux paliers, comme le succès 33).
CREATE TABLE epreuve.palier_contenu (
    palier_id   integer NOT NULL REFERENCES epreuve.palier(id),
    contenu_id  integer NOT NULL REFERENCES epreuve.contenu(id),
    PRIMARY KEY (palier_id, contenu_id)
);

CREATE TABLE epreuve.grimpeur (
    id               serial PRIMARY KEY,
    pseudo_ig        text NOT NULL CHECK (char_length(pseudo_ig) BETWEEN 2 AND 30),
    classe           text NOT NULL CHECK (classe IN ({_CLASSES_SQL})),
    difficulte       text NOT NULL CHECK (difficulte IN ('easy', 'med', 'hard')),
    statut           text NOT NULL DEFAULT 'actif' CHECK (statut IN ('actif', 'pause', 'exclu')),
    discord_user_id  bigint,
    niveau_connu     integer CHECK (niveau_connu BETWEEN 1 AND 200),
    niveau_maj_le    timestamptz,
    inscrit_le       timestamptz NOT NULL DEFAULT now()
);
-- Pseudo unique sans tenir compte de la casse ; un compte Discord relié à un seul grimpeur.
CREATE UNIQUE INDEX grimpeur_pseudo_unique ON epreuve.grimpeur (lower(pseudo_ig));
CREATE UNIQUE INDEX grimpeur_discord_unique ON epreuve.grimpeur (discord_user_id)
    WHERE discord_user_id IS NOT NULL;

CREATE TABLE epreuve.preuve (
    id                  serial PRIMARY KEY,
    discord_guild_id    bigint NOT NULL,
    discord_channel_id  bigint NOT NULL,
    discord_message_id  bigint NOT NULL UNIQUE,
    lien                text NOT NULL,
    auteur_discord_id   bigint,          -- inconnu au jalon bêta (le bot ne lit pas le message)
    poste_le            timestamptz NOT NULL,
    image_chemin        text,
    analyse_ia          jsonb,
    statut_ia           text NOT NULL DEFAULT 'sans'
                        CHECK (statut_ia IN ('sans', 'en_attente', 'proposee', 'traitee', 'echec')),
    cree_le             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE epreuve.validation (
    id           serial PRIMARY KEY,
    grimpeur_id  integer NOT NULL REFERENCES epreuve.grimpeur(id),
    contenu_id   integer NOT NULL REFERENCES epreuve.contenu(id),
    preuve_id    integer REFERENCES epreuve.preuve(id),
    niveau       integer CHECK (niveau BETWEEN 1 AND 200),   -- vide pour une déclaration de quêtes
    statut       text NOT NULL CHECK (statut IN ('acceptee', 'refusee', 'annulee')),
    forcee       boolean NOT NULL DEFAULT false,
    motif        text,
    source       text NOT NULL DEFAULT 'manuelle'
                 CHECK (source IN ('manuelle', 'ia_confirmee', 'ia_corrigee', 'declaration')),
    decidee_par  bigint NOT NULL,         -- l'admin, ou le joueur qui déclare ses quêtes
    decidee_le   timestamptz NOT NULL,
    realisee_le  timestamptz NOT NULL,
    CHECK (niveau IS NOT NULL OR source = 'declaration')
);
-- La garantie centrale : jamais deux validations acceptées pour le même couple,
-- même si deux admins valident à la même seconde.
CREATE UNIQUE INDEX validation_une_acceptee ON epreuve.validation (grimpeur_id, contenu_id)
    WHERE statut = 'acceptee';

CREATE TABLE epreuve.journal (
    id                 bigserial PRIMARY KEY,
    horodatage         timestamptz NOT NULL DEFAULT now(),
    acteur_discord_id  bigint,
    type               text NOT NULL,
    grimpeur_id        integer REFERENCES epreuve.grimpeur(id),
    etage_id           integer REFERENCES epreuve.etage(id),
    details            jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    public             boolean NOT NULL DEFAULT false
);
CREATE INDEX journal_horodatage ON epreuve.journal (horodatage DESC);
"""


def upgrade() -> None:
    # asyncpg n'exécute qu'une instruction à la fois : on découpe sur les « ; » de fin de ligne.
    for instruction in UPGRADE.split(";\n"):
        if instruction.strip():
            op.execute(instruction)
    # Row Level Security sans aucune règle : ceinture de sécurité contre l'API REST de Supabase.
    # Notre programme se connecte en propriétaire des tables et n'est pas concerné.
    for table in TABLES:
        op.execute(f"ALTER TABLE epreuve.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Le schéma lui-même reste : il contient la table de version d'Alembic.
    for table in TABLES:
        op.execute(f"DROP TABLE epreuve.{table}")
