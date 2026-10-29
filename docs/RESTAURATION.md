# Sauvegardes et retour en arrière

## Ce qui est sauvegardé

- **La base** : chaque nuit vers 3 h, le workflow GitHub `sauvegarde` fait un `pg_dump` du schéma `epreuve`, le chiffre avec age et le garde 30 jours dans les artefacts du dépôt.
- **Le code** : le dépôt GitHub, plus l'historique des versions déployées chez Fly.

La clé privée age est dans `~/epreuve-des-dieux/cle-sauvegarde.txt` (hors git) et dans le gestionnaire de mots de passe de Marceau. Sans elle, les sauvegardes sont illisibles.

Restauration vérifiée le 29/10/2026 : 24 étages, 1 010 quêtes, 21 554 objets relus depuis la sauvegarde de la nuit.

## Revenir à la version précédente du site (une mise à jour bugue)

```
fly releases                      # la liste des versions, avec leur image
fly deploy --image registry.fly.io/epreuve-des-dieux:deployment-XXXX
```

Si la version fautive a changé le schéma, redescendre aussi la migration : `fly ssh console -C 'alembic downgrade -1'`.

## Restaurer la base

1. Télécharger la sauvegarde : `gh run list --workflow sauvegarde.yml`, puis `gh run download <id>`.
2. La déchiffrer : `age -d -i cle-sauvegarde.txt epreuve.dump.age > epreuve.dump` (ou, sans age installé : `uv run --with pyrage python -c "…"`).
3. La restaurer avec un client Postgres 18 :
   - **sur Supabase** : `pg_restore --clean --if-exists --no-owner -d "<adresse postgresql:// de Supabase>" epreuve.dump` ;
   - **sur un Postgres ordinaire** (test) : créer d'abord le schéma des extensions, comme sur Supabase, sinon les index de recherche échouent :
     `psql -c "CREATE SCHEMA IF NOT EXISTS extensions; CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA extensions;"`.
