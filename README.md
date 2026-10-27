# L'Épreuve des Dieux

Site de suivi de « L'Épreuve des Dieux », aventure Dofus 3 communautaire.
Jusqu'au vendredi 13/11/2026 à 17 h (heure de Paris), le site ne montre que la page teaser, avec son
compte à rebours (lot A). Le cœur du site (connexion Discord, cases à cocher, jauge, tour) arrive au lot B.

Documentation : `docs/SPEC.md` (quoi), `docs/ARCHITECTURE.md` (comment), `docs/LOTS.md` (découpage),
`docs/PREREQUIS.md` (ce que Marceau prépare), `docs/design/` (la direction artistique, qui fait foi).

## Voir le teaser en local (sans aucun compte ni base)

```bash
uv sync
uv run python -m epreuve.main        # puis http://127.0.0.1:8080
```

Aperçus du designer, dans l'adresse : `?dans=12` lance un compte à rebours de 12 secondes pour voir la
bascule, `?etat=ouvert` montre l'état « Les portes sont ouvertes ». Le bouton « Entrer dans la tour »
n'apparaît que si `TEASER_LIEN_ENTRER` est renseignée :

```bash
TEASER_LIEN_ENTRER=https://exemple.fr uv run python -m epreuve.main
SITE_MODE=ouvert uv run python -m epreuve.main     # la page provisoire du mode ouvert
```

## Le mode du site

| Variable | Valeurs | Défaut |
|---|---|---|
| `SITE_MODE` | `auto`, `teaser` ou `ouvert` | `auto` : teaser jusqu'à `SITE_OUVERT_LE`, puis ouvert |
| `SITE_OUVERT_LE` | date ISO **avec fuseau** | `2026-11-13T17:00:00+01:00` |
| `TEASER_LIEN_ENTRER` | adresse du bouton | vide : bouton masqué |

En mode teaser, seuls `/`, `/sante` et `/static/…` répondent ; tout le reste renvoie vers `/` (303),
ou 404 pour `/api/…`. Chaque réponse porte une CSP stricte (aucun script en ligne) et `X-Robots-Tag: noindex`.
Les polices sont servies par le site (`src/epreuve/web/static/fonts/`, licence SIL OFL) : la page ne fait
aucune requête vers un autre domaine.

## Lancer les tests

```bash
# Un Postgres jetable pour les tests marqués « db » (sinon ils sont sautés) :
docker run -d --rm --name epreuve-pg-test -p 54329:5432 \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=epreuve_test postgres:17-alpine

uv run ruff check .
uv run pytest --cov=epreuve.domaine --cov-branch --cov-report=term-missing
```

Le module de règles (`src/epreuve/domaine/`, dont `mode_site.py`) doit rester couvert à 100 % (contrôlé par la CI).

## Organisation du code

| Dossier | Rôle |
|---|---|
| `src/epreuve/domaine/` | Les règles, en Python pur. `mode_site.py` : teaser ou ouvert. Le reste (v3) attend sa réécriture au lot B |
| `src/epreuve/web/` | FastAPI : `app.py` (le teaser, `/sante`), `securite.py` (filtre du mode, en-têtes), gabarits et statiques |
| `src/epreuve/db/` | Tables, connexion et dépôt (SQLAlchemy async) ; au lot A, seul `ping()` sert à `/sante` |
| `src/epreuve/dofusdb/` | Import depuis l'API DofusDB (réécrit au lot B) |
| `migrations/` | Schéma Postgres versionné (Alembic) |

## Mettre le teaser en ligne (Fly.io)

Prérequis : compte Fly, `flyctl` installé et connecté (`docs/PREREQUIS.md`, section B). Les réglages
publics sont dans `fly.toml` ; aucun secret n'est nécessaire au lot A.

```bash
fly launch --no-deploy --copy-config --name epreuve-des-dieux --region cdg   # une seule fois
fly deploy                                                                  # construit l'image et la déploie
fly status && curl https://epreuve-des-dieux.fly.dev/sante                  # {"statut":"ok",…,"mode":"teaser"}

# Facultatif, recommandé dès que Supabase existe (garde le projet gratuit éveillé, PREREQUIS E.1) :
fly secrets set DATABASE_URL='postgresql+asyncpg://…'

# Le domaine (PREREQUIS B.3) : enregistrements A et AAAA vers les adresses de `fly ips list`, puis
fly certs add <domaine>
fly certs show <domaine>                       # attendre « Issued »
```

Reprendre la main : `fly secrets set SITE_MODE=teaser` (ou `ouvert`) redémarre la machine en quelques secondes.
Le jour J vers 16 h 50 : `fly secrets set TEASER_LIEN_ENTRER=https://<domaine>/`.
