# L'Épreuve des Dieux

Bot Discord et site de suivi de « L'Épreuve des Dieux », aventure Dofus 3 communautaire.
Le bot tient le registre des grimpeurs et les validations ; le site public montre la jauge à points
de l'étage en cours (étage N = chapitre N du [guide Duffus](https://duffus.fr/guide-complet)),
les grimpeurs, la répartition des classes et le fil des validations.

Documentation : `docs/SPEC.md` (quoi), `docs/ARCHITECTURE.md` (comment), `docs/LOTS.md` (découpage),
`docs/REPONSES-SHADOAZE.md` (les règles tranchées par l'organisateur).

## Voir le site en local (données fictives, sans aucun compte)

```bash
uv run python -m epreuve.web.demo        # puis http://127.0.0.1:8080
```

La démo utilise le vrai calcul de la jauge sur les 12 grimpeurs fictifs de la maquette. L'horloge est
simulée au 8 novembre 2026 ; `?horloge=2026-10-29T12:00` ou `?horloge=2026-11-13T17:00` dans
l'adresse montre le compte à rebours avant l'ouverture ou après la date plancher.

## Lancer les tests

```bash
# Un Postgres jetable pour les tests marqués « db » (sinon ils sont sautés) :
docker run -d --rm --name epreuve-pg-test -p 54329:5432 \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=epreuve_test postgres:17-alpine

uv run pytest --cov=epreuve.domaine --cov-branch --cov-report=term-missing
uv run pytest -m "not db"                 # seulement ce qui tourne sans base
```

Le module de règles (`src/epreuve/domaine/`) doit rester couvert à 100 % (contrôlé par la CI).

## Organisation du code

| Dossier | Rôle |
|---|---|
| `src/epreuve/domaine/` | Les règles, en Python pur : seuil, jauge, paliers, contrôles, classes |
| `src/epreuve/db/` | Tables, connexion et dépôt (SQLAlchemy async) ; renvoie des objets du domaine |
| `src/epreuve/bot/` | Commandes Discord : une fonction métier testable + une fine couche Discord |
| `src/epreuve/web/` | FastAPI : `/`, `/api/etat`, `/sante`, et la démo locale |
| `src/epreuve/dofusdb/` | Import d'un étage depuis son YAML et l'API DofusDB (hors ligne) |
| `migrations/` | Schéma Postgres versionné (Alembic) |

## Mise en production (plus tard)

Copier `.env.example` en `.env` et le remplir. `--env-file .env` fait lire ce fichier par uv :
Alembic et l'outil d'import trouvent ainsi `DATABASE_URL` sans l'exporter à la main.

```bash
uv run --env-file .env alembic upgrade head                                   # crée le schéma
uv run --env-file .env python -m epreuve.dofusdb.import_etage config/etages/etage-0.yaml --a-blanc  # aperçu
uv run --env-file .env python -m epreuve.dofusdb.import_etage config/etages/etage-0.yaml            # import
uv run --env-file .env python -m epreuve.main                                 # bot + site
```

Le déploiement Fly.io, les secrets GitHub et la clé de chiffrement des sauvegardes sont décrits
dans `docs/PREREQUIS.md`.
