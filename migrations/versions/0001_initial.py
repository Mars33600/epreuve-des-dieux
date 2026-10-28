"""Schéma initial du lot B : étages, contenu, fiches, grimpeurs, coches, bilans, sessions, journal.

Révision : 0001_initial (réécrite au lot B : aucune base de production n'existait).
Écrit en SQL, volontairement : c'est exactement ce que Postgres exécute, contraintes comprises.
Référence : ARCHITECTURE.md §5.

Ajouts au tableau d'ARCHITECTURE §5, nécessaires aux interfaces figées du dépôt :
- `masque_par` (admin | construction) : une reconstruction démasque ce qui revient dans la source, mais
  jamais ce qu'un admin a masqué ;
- `corrections` (jsonb) : les libellés corrigés par un admin (nom, condition), qui survivent à une
  reconstruction (critère 26) ;
- `donjon_disponible` : la liste complète des donjons aspirés, avec leurs succès, pour qu'un admin ajoute
  un donjon à un étage (T-03) sans réseau.
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

TABLES = ("journal", "session", "bilan_etage", "coche_quete", "coche_case", "grimpeur", "liste_officielle",
          "fiche_quete", "quete", "case_succes", "donjon", "donjon_disponible", "etage")

UPGRADE = f"""
CREATE SCHEMA IF NOT EXISTS epreuve;

CREATE TABLE epreuve.etage (
    id                     serial PRIMARY KEY,
    numero                 integer NOT NULL UNIQUE CHECK (numero >= 0),
    nom                    text NOT NULL,
    niveau_min             integer NOT NULL CHECK (niveau_min BETWEEN 1 AND 200),
    niveau_max             integer NOT NULL CHECK (niveau_max BETWEEN 1 AND 200),
    level_cap              integer NOT NULL CHECK (level_cap BETWEEN 1 AND 200),
    statut                 text NOT NULL DEFAULT 'scelle' CHECK (statut IN ('scelle', 'ouvert', 'termine')),
    ouvert_le              timestamptz,
    date_plancher_suivant  timestamptz,
    palier_manuel          integer CHECK (palier_manuel >= 1),
    duffus_tranche_id      text,
    ambiance_url           text,
    alertes                jsonb NOT NULL DEFAULT '[]'::jsonb,
    corrections            jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    maj_le                 timestamptz NOT NULL DEFAULT now(),
    CHECK (niveau_min <= niveau_max)
);
CREATE UNIQUE INDEX etage_un_seul_ouvert ON epreuve.etage (statut) WHERE statut = 'ouvert';

CREATE TABLE epreuve.donjon_disponible (
    duffus_id      text PRIMARY KEY,
    nom            text NOT NULL,
    niveau         integer,
    dofusdb_id     integer,
    succes_source  text NOT NULL CHECK (succes_source IN ('duffus', 'dofusdb')),
    succes         jsonb NOT NULL DEFAULT '[]'::jsonb,
    maj_le         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE epreuve.donjon (
    id             serial PRIMARY KEY,
    etage_id       integer NOT NULL REFERENCES epreuve.etage(id) ON DELETE RESTRICT,
    nom            text NOT NULL,
    niveau         integer,
    ordre          integer NOT NULL,
    bloc           text,
    duffus_id      text,
    dofusdb_id     integer,
    origine        text NOT NULL DEFAULT 'propose' CHECK (origine IN ('propose', 'admin')),
    succes_source  text NOT NULL CHECK (succes_source IN ('duffus', 'dofusdb')),
    masque         boolean NOT NULL DEFAULT false,
    masque_par     text CHECK (masque_par IN ('admin', 'construction')),
    corrections    jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    UNIQUE (etage_id, duffus_id)
);

CREATE TABLE epreuve.case_succes (
    id             serial PRIMARY KEY,
    donjon_id      integer NOT NULL REFERENCES epreuve.donjon(id) ON DELETE RESTRICT,
    ordre          integer NOT NULL CHECK (ordre >= 1),
    nom            text NOT NULL,
    condition      text NOT NULL DEFAULT '',
    est_classique  boolean NOT NULL DEFAULT false,
    duffus_id      text,
    masquee        boolean NOT NULL DEFAULT false,
    masque_par     text CHECK (masque_par IN ('admin', 'construction')),
    corrections    jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    CONSTRAINT case_succes_ordre UNIQUE (donjon_id, ordre) DEFERRABLE INITIALLY DEFERRED,
    UNIQUE (donjon_id, duffus_id)
);
CREATE UNIQUE INDEX case_succes_une_classique ON epreuve.case_succes (donjon_id) WHERE est_classique;

CREATE TABLE epreuve.quete (
    id              serial PRIMARY KEY,
    etage_id        integer NOT NULL REFERENCES epreuve.etage(id) ON DELETE RESTRICT,
    nom             text NOT NULL,
    niveau          integer,
    bloc            text NOT NULL,
    ordre           integer NOT NULL,
    nature          text NOT NULL CHECK (nature IN ('principale', 'secondaire')),
    nature_origine  text NOT NULL CHECK (nature_origine IN ('duffus', 'dofusdb', 'admin')),
    nature_motif    text,
    dofus           text[] NOT NULL DEFAULT '{{}}',
    jusqu_ou        text,
    a_lier          text,
    duffus_id       text,
    dofusdb_id      integer,
    masquee         boolean NOT NULL DEFAULT false,
    masque_par      text CHECK (masque_par IN ('admin', 'construction')),
    corrections     jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    UNIQUE (etage_id, duffus_id),
    CHECK (nature_origine <> 'admin' OR nature_motif IS NOT NULL)
);

CREATE TABLE epreuve.fiche_quete (
    quete_id  integer PRIMARY KEY REFERENCES epreuve.quete(id) ON DELETE CASCADE,
    source    text NOT NULL CHECK (source IN ('duffus', 'duffus+dofusdb', 'dofusdb')),
    contenu   jsonb NOT NULL
);

CREATE TABLE epreuve.liste_officielle (
    discord_user_id  bigint PRIMARY KEY,
    statut_initial   text NOT NULL DEFAULT 'actif' CHECK (statut_initial IN ('actif', 'pause')),
    ajoute_par       bigint,
    ajoute_le        timestamptz NOT NULL
);

CREATE TABLE epreuve.grimpeur (
    id               serial PRIMARY KEY,
    discord_user_id  bigint NOT NULL UNIQUE,
    nom_discord      text NOT NULL,
    pseudo_ig        text NOT NULL CHECK (char_length(pseudo_ig) BETWEEN 2 AND 30),
    classe           text CHECK (classe IN ({_CLASSES_SQL})),
    statut           text NOT NULL DEFAULT 'actif' CHECK (statut IN ('actif', 'pause', 'exclu')),
    niveau_declare   integer CHECK (niveau_declare BETWEEN 1 AND 200),
    inscrit_le       timestamptz NOT NULL
);
CREATE UNIQUE INDEX grimpeur_pseudo_unique ON epreuve.grimpeur (lower(pseudo_ig));

CREATE TABLE epreuve.coche_case (
    grimpeur_id  integer NOT NULL REFERENCES epreuve.grimpeur(id) ON DELETE RESTRICT,
    case_id      integer NOT NULL REFERENCES epreuve.case_succes(id) ON DELETE RESTRICT,
    cochee_le    timestamptz NOT NULL,
    cochee_par   bigint,
    PRIMARY KEY (grimpeur_id, case_id)
);

CREATE TABLE epreuve.coche_quete (
    grimpeur_id  integer NOT NULL REFERENCES epreuve.grimpeur(id) ON DELETE RESTRICT,
    quete_id     integer NOT NULL REFERENCES epreuve.quete(id) ON DELETE RESTRICT,
    cochee_le    timestamptz NOT NULL,
    cochee_par   bigint,
    PRIMARY KEY (grimpeur_id, quete_id)
);

CREATE TABLE epreuve.bilan_etage (
    etage_id  integer PRIMARY KEY REFERENCES epreuve.etage(id) ON DELETE RESTRICT,
    fige_le   timestamptz NOT NULL,
    actifs    integer NOT NULL CHECK (actifs >= 0),
    palier    integer NOT NULL CHECK (palier >= 0),
    score     integer NOT NULL CHECK (score >= 0),
    detail    jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    force     boolean NOT NULL DEFAULT false,
    motif     text,
    CHECK (NOT force OR motif IS NOT NULL)
);

CREATE TABLE epreuve.session (
    id_hache           bytea PRIMARY KEY,
    discord_user_id    bigint NOT NULL,
    nom_discord        text NOT NULL,
    est_admin          boolean NOT NULL,
    roles_verifies_le  timestamptz NOT NULL,
    cree_le            timestamptz NOT NULL,
    expire_le          timestamptz NOT NULL,
    jeton_oauth        text NOT NULL,
    csrf               text NOT NULL
);
CREATE INDEX session_expire_le ON epreuve.session (expire_le);

CREATE TABLE epreuve.journal (
    id                 bigserial PRIMARY KEY,
    horodatage         timestamptz NOT NULL,
    acteur_discord_id  bigint,
    type               text NOT NULL,
    grimpeur_id        integer REFERENCES epreuve.grimpeur(id),
    etage_id           integer REFERENCES epreuve.etage(id),
    details            jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    public             boolean NOT NULL DEFAULT false
);
CREATE INDEX journal_horodatage ON epreuve.journal (horodatage DESC)
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
