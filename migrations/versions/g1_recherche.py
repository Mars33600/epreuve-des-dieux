"""Recherche globale : index trigrammes (pg_trgm) sur les noms, sans accents ni casse.

Révision : g1_recherche, après f3_prologue.

- `epreuve.cle_recherche(text)` : minuscules, sans accents ni ligatures, ponctuation en espaces. Même règle que
  `cle_recherche` côté Python (encyclopédie), mais en SQL immuable pour pouvoir être indexée (`unaccent` ne l'est
  pas, et son extension n'est pas toujours disponible : on se contente de `pg_trgm`).
- l'extension est créée `IF NOT EXISTS`, dans le schéma `extensions` s'il existe (convention Supabase), sinon dans le
  schéma par défaut ; les index citent la classe d'opérateurs avec son schéma (indépendant du search_path).
- index GIN trigrammes : sur la colonne `cle_recherche` déjà présente de l'encyclopédie, et sur l'expression pour
  les grimpeurs, quêtes et donjons. Un `LIKE '%mot%'` les utilise, même pour un mot partiel au milieu d'un nom.
"""

from alembic import op
from sqlalchemy import text

revision = "g1_recherche"
down_revision = "f3_prologue"
branch_labels = None
depends_on = None

ENCY = ("ency_objet", "ency_monstre", "ency_panoplie", "ency_sort", "ency_pnj", "ency_quete")
EPREUVE = (("grimpeur", "pseudo_ig"), ("quete", "nom"), ("donjon", "nom"))


def _schema_trgm() -> str:
    """Le schéma où vit pg_trgm : celui de l'extension, qu'elle soit déjà là (Supabase la pose souvent dans
    `extensions`, qui n'est pas toujours dans le search_path de la connexion) ou qu'on vienne de la créer."""
    return op.get_bind().execute(text(
        "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace "
        "WHERE e.extname = 'pg_trgm'")).scalar_one()


def upgrade() -> None:
    # Sur Supabase, la convention est le schéma `extensions` (déjà dans le search_path du rôle) ; ailleurs, le
    # schéma par défaut. `IF NOT EXISTS` : rejouable, et sans effet si l'extension existe déjà quelque part.
    avec_schema = op.get_bind().execute(text("SELECT 1 FROM pg_namespace WHERE nspname = 'extensions'")).scalar()
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm" + (" WITH SCHEMA extensions" if avec_schema else ""))
    ops = f'"{_schema_trgm()}".gin_trgm_ops'  # qualifié : ne dépend plus du search_path
    op.execute(r"""
    CREATE FUNCTION epreuve.cle_recherche(texte text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
      SELECT btrim(regexp_replace(
        translate(replace(replace(lower(texte), 'œ', 'oe'), 'æ', 'ae'),
                  'àáâãäåçèéêëìíîïñòóôõöùúûüýÿ', 'aaaaaaceeeeiiiinooooouuuuyy'),
        '[^0-9a-z]+', ' ', 'g'))
    $$""")
    for table in ENCY:
        op.execute(f"CREATE INDEX {table}_trgm ON epreuve.{table} USING gin (cle_recherche {ops})")
    for table, colonne in EPREUVE:
        op.execute(f"CREATE INDEX {table}_trgm ON epreuve.{table} "
                   f"USING gin (epreuve.cle_recherche({colonne}) {ops})")


def downgrade() -> None:
    for table, _ in EPREUVE:
        op.execute(f"DROP INDEX IF EXISTS epreuve.{table}_trgm")
    for table in ENCY:
        op.execute(f"DROP INDEX IF EXISTS epreuve.{table}_trgm")
    op.execute("DROP FUNCTION IF EXISTS epreuve.cle_recherche(text)")
