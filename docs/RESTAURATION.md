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

## Ouverture automatique des étages et annonces Discord

Quand la jauge de l'étage en cours est pleine, qu'un étage scellé suit et que la date plancher est passée, le site ouvre l'étage suivant tout seul : juste après la coche (ou le gel, le palier, le masquage) qui remplit la jauge, et sinon dans la minute qui suit la date plancher (une veille tourne en fond). Rien ne se passe pendant le teaser. Au journal admin, l'auteur de ces ouvertures est « système ».

- **Couper l'ouverture automatique** : `ouverture: automatique: false` dans `config/regles.yaml`, puis redéployer. L'ouverture manuelle (bouton de l'admin, forcée ou non) reste toujours possible.
- **Une ouverture de trop** : il n'y a pas de bouton « refermer » ; la base se corrige à la main (statut des deux étages, ligne de `bilan_etage`), d'où l'intérêt de bien régler palier et date plancher avant.

Chaque ouverture, automatique ou manuelle, est annoncée sur Discord par le « Gardien de la Tour » (un `@everyone` avec le nom, les niveaux et le lien de l'étage), si le webhook est réglé. Un webhook, c'est une adresse de salon à laquelle le site poste un message : aucun bot à héberger.

1. Sur Discord, dans le salon des annonces : **Paramètres du salon > Intégrations > Webhooks > Nouveau webhook**. Le nom et l'avatar importent peu (le site envoie « Gardien de la Tour ») ; vérifier que le salon permet de mentionner `@everyone` au webhook.
2. **Copier l'URL du webhook**. Elle vaut mot de passe : qui la connaît peut poster dans le salon.
3. La déposer sur Fly : `fly secrets set DISCORD_WEBHOOK_ANNONCES=https://discord.com/api/webhooks/… -a epreuve-des-dieux` (la machine redémarre en quelques secondes).

Sans cette variable, ou vide, aucune annonce ne part et tout le reste fonctionne pareil. Si Discord ne répond pas (délai de 5 s), l'ouverture est quand même faite et le journal du serveur note « annonce Discord non envoyée » ou « refusée : HTTP … », sans jamais écrire l'adresse. En cas de fuite de l'URL : supprimer le webhook dans Discord, en créer un autre, refaire l'étape 3.
