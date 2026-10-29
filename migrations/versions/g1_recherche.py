"""Recherche globale : index trigrammes (pg_trgm) sur les noms, sans accents ni casse.

Révision : g1_recherche, après f3_prologue.

- `epreuve.cle_recherche(text)` : minuscules, sans accents ni ligatures, ponctuation en espaces. Même règle que
  `cle_recherche` côté Python (encyclopédie), mais en SQL immuable pour pouvoir être indexée (`unaccent` ne l'est
  pas, et son extension n'est pas toujours disponible : on se contente de `pg_trgm`).
- index GIN trigrammes : sur la colonne `cle_recherche` déjà présente de l'encyclopédie, et sur l'expression pour
  les grimpeurs, quêtes et donjons. Un `LIKE '%mot%'` les utilise, même pour un mot partiel au milieu d'un nom.
"""

from alembic import op

revision = "g1_recherche"
down_revision = "f3_prologue"
branch_labels = None
depends_on = None

ENCY = ("ency_objet", "ency_monstre", "ency_panoplie", "ency_sort", "ency_pnj", "ency_quete")
EPREUVE = (("grimpeur", "pseudo_ig"), ("quete", "nom"), ("donjon", "nom"))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(r"""
    CREATE FUNCTION epreuve.cle_recherche(texte text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
      SELECT btrim(regexp_replace(
        translate(replace(replace(lower(texte), 'œ', 'oe'), 'æ', 'ae'),
                  'àáâãäåçèéêëìíîïñòóôõöùúûüýÿ', 'aaaaaaceeeeiiiinooooouuuuyy'),
        '[^0-9a-z]+', ' ', 'g'))
    $$""")
    for table in ENCY:
        op.execute(f"CREATE INDEX {table}_trgm ON epreuve.{table} USING gin (cle_recherche gin_trgm_ops)")
    for table, colonne in EPREUVE:
        op.execute(f"CREATE INDEX {table}_trgm ON epreuve.{table} "
                   f"USING gin (epreuve.cle_recherche({colonne}) gin_trgm_ops)")


def downgrade() -> None:
    for table, _ in EPREUVE:
        op.execute(f"DROP INDEX IF EXISTS epreuve.{table}_trgm")
    for table in ENCY:
        op.execute(f"DROP INDEX IF EXISTS epreuve.{table}_trgm")
    op.execute("DROP FUNCTION IF EXISTS epreuve.cle_recherche(text)")
