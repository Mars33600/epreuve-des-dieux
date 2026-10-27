# L'Épreuve des Dieux : découpage en lots

Version 4, 27/10/2026. Chaque lot suit le circuit de l'équipe : **architecte** (spec technique) → **PO** (critères d'acceptation) → **dev** → **testeur + relecteur** → **rédacteur** → **recette** par Marceau, et par Shadoaze pour ce qui le concerne. Les devs travaillent sur Opus. Les **interfaces figées** ci-dessous sont les contrats entre agents : un dev ne les change pas sans repasser par l'architecte.

## Ce qui change en v4

- **Les dates sont maintenant imposées.** Le teaser doit être en ligne **au plus tard le vendredi 6/11**, et le cœur doit être prêt et testé **pour le vendredi 13/11 à 17:00**. En v3, aucune date n'était imposée.
- **Les lots changent de nature.**
  - **Lot A** : la page teaser, l'hébergement et le domaine.
  - **Lot B** : le cœur de l'application web, à savoir la connexion Discord, les cases à cocher, la jauge 2 × N, la tour, les fiches, les filtres et l'admin (pause, contenu d'étage, ouverture). Les points bonus passent au lot C. Le contenu vient de l'aspiration de Duffus.
  - **Lots C à E** : les enrichissements.

  Les anciens « lot 1 bêta / lancement » et « lot 2 » sont abandonnés.
- **Plus de bot** (arbitrage du chef de projet). Plus de commandes slash ni de connexion à la passerelle Discord, et aucune annonce automatique au lot B : la connexion passe par OAuth2 seul, et l'admin annonce lui-même l'ouverture d'un étage.
- **Une grande partie du code existant est reprise** (voir l'inventaire), mais le modèle de points (difficultés, paliers, retardataires, contrôles de cap) et tout le bot sont **retirés**.
- **`docs/EXIGENCES.md` est intégré.** Chaque exigence est rattachée à un lot (section « Traçabilité » ci-dessous, détail dans l'annexe A de SPEC). Les points ouverts T-nn qui reçoivent une réponse par défaut se règlent **sans code** : `config/regles.yaml`, `config/etages.yaml` ou une action d'admin.
- Le lot B se fait en **deux chantiers parallèles** (B1 : domaine, base et contenu ; B2 : web), précédés d'une demi-journée de relevé du schéma Duffus (B0). Le lot B est trop gros pour un seul chantier dans les délais. Les interfaces figées permettent de travailler en parallèle.

---

## Calendrier

Aujourd'hui : mardi 27/10/2026. Heure de Paris.

| Jour | Lot A (teaser) | Lot B (cœur) | Marceau et Shadoaze |
|---|---|---|---|
| mar. 27/10 | — | — | Questions à Shadoaze (SPEC §8). Achat du domaine. Comptes Fly et Supabase (PREREQUIS). |
| mer. 28/10 | Dev A | **B0** : relevé du schéma Duffus (½ j), puis l'architecte fige `duffus/schema.py` | Clé et adresse Duffus dans `.env`. Docker lancé pour les tests de base (PREREQUIS E.2). |
| jeu. 29 → ven. 30/10 | Dev A, puis test et relecture | **B1** et **B2** en parallèle. **29/10 : première aspiration réelle**, dont les extraits servent aux tests de B1 et à la décision de repli. | 30/10 à 17 h : étage 0 en jeu (le site n'est pas attendu). **31/10 au plus tard : décision sur le repli** (ci-dessous). |
| sam. 31/10 → lun. 2/11 | Recette, **déploiement en mode teaser sur le domaine** | B1 et B2 | Recette A |
| **mar. 3/11** | **Objectif : teaser en ligne** (marge de 3 jours) | B1 et B2 | OAuth2 réglé chez Discord et serveur de test prêt (PREREQUIS C), pour l'intégration |
| mer. 4 → jeu. 5/11 | Correctifs éventuels | Fin de B1 et B2, intégration | Shadoaze relit `config/dofus.yaml` et les étages 0 et 1 construits |
| **ven. 6/11** | **Date limite du teaser en ligne**, publication du lien | Testeur et relecteur | Reveal |
| sam. 7 → dim. 8/11 | — | Correctifs, rédacteur | Construction et revue des étages 0 à 25 (scellés) |
| lun. 9/11 | — | **Recette par Marceau** | — |
| **mar. 10/11** | — | **Déploiement derrière le teaser.** Recette sur le site réel **par les admins seulement**. | Saisie de la liste officielle |
| mer. 11 → jeu. 12/11 | — | Recette par les admins (correctifs seulement). **Gel du code jeudi 12/11 à 18 h.** | **Aucun accès joueur avant le 13/11** (Marceau : « rien à cocher avant le 13, le site sera même pas accessible ») |
| **ven. 13/11, 17:00** | Le teaser s'efface (mode `auto`) | **Ouverture du site** ; les grimpeurs créent leur fiche à leur première connexion | Marceau renseigne `TEASER_LIEN_ENTRER` et vérifie à 17 h 01 |
| après le 13/11 | — | — | Lots C, D, E |

**Si le lot B glisse** : le teaser reste affiché (`SITE_MODE=teaser`), et rien ne casse côté jeu. Les grimpeurs jouent l'étage 0 sans site, puisque l'étage 1 ne peut de toute façon pas s'ouvrir avant le 13/11, et ils cochent dès l'ouverture tout ce qu'ils ont fait. Un glissement de quelques jours est acceptable (DECISIONS §8 : « pas mi-décembre non plus »). En revanche, **un lot B ouvert mais faux** serait grave : on ne sacrifie pas les tests pour tenir la date.

**Si le temps manque avant le gel du 12/11**, on coupe dans cet ordre, sans toucher au parcours joueur (connexion, fiche, coche, jauge, « qui ne l'a pas fait ? ») ni au parcours admin (liste, gel, revue, ouverture, journal) :
1. l'**image d'ambiance** par étage ;
2. la **répartition des 19 classes** sur la tour.

La **fiche de quête** (SPEC §4.4 bis) n'est **jamais** coupée : c'est une exigence forte de Marceau.

Chaque coupe passe au lot C, et ses critères sortent de la recette.

---

## Point de départ du code et inventaire

**Branche** : créer `v4` à partir de `wip/corrections-revue` (ed27bed). Cette branche contient les corrections de revue (erreurs du bot, sauvegarde chiffrée, actions épinglées par empreinte, `env_ignore_empty`, journal des imports, preuve sans doublon) et a déjà retiré les retardataires automatiques. Pour mémoire, sur `main`, 753 tests passent, et les 62 échecs restants viennent de l'absence du Postgres de test (Docker non lancé), pas d'un défaut du code.

Légende : **G** = gardé tel quel · **M** = modifié · **R** = réécrit (on garde l'idée ou la structure) · **S** = supprimé (reste dans l'historique git).

| Fichier existant | Sort | Lot | Ce qu'on en fait |
|---|---|---|---|
| `pyproject.toml`, `uv.lock` | M | A | Retirer `discord.py`, ajouter `python-multipart` (lot B). Le reste est gardé. |
| `Dockerfile` | M | A | Gardé (uv, utilisateur sans privilège). Copier `donnees/` au lot B. |
| `fly.toml` | M | A | Mémoire de 256 Mo. `[env]` : `SITE_MODE`, `SITE_OUVERT_LE`. `release_command` commenté au lot A, remis au lot B. |
| `.github/workflows/tests.yml`, `sauvegarde.yml` (version wip) | G | — | Sauvegarde chiffrée avec age. Elle ne s'active qu'avec les secrets du lot B. |
| `.gitignore`, `alembic.ini`, `migrations/env.py` | G | — | — |
| `.env.example` | R | A puis B | Nouvelles variables (ARCHITECTURE §11). |
| `README.md` | M | A puis B | Démarrage local en mode teaser, puis en mode complet avec la démo. |
| `src/epreuve/config.py` (version wip) | M | A puis B | Gardé (pydantic-settings, `SecretStr`, `env_ignore_empty`). Au lot A, **seules** les variables du mode sont obligatoires, et `DATABASE_URL` devient facultative. |
| `src/epreuve/main.py` | R | A | uvicorn seul : plus de bot ni d'`asyncio.gather`. |
| `src/epreuve/domaine/classes.py` | G | — | Les 19 classes et `repartition_classes`. |
| `src/epreuve/domaine/modeles.py` | R | B | Nouvelles dataclasses (interfaces B). `liste_francaise` part dans `textes.py`. `Grimpeur.__post_init__` (validation de la classe) est gardé. |
| `src/epreuve/domaine/seuil.py`, `jauges.py`, `controles.py` | S | B | Remplacés par `bareme.py`, `progression.py`, `ouverture.py` et `visibilite.py`. Le commentaire pédagogique sur les entiers est repris dans `bareme.py`. |
| `src/epreuve/domaine/inclusion.py` (`main` seulement) | S | — | Déjà supprimé sur la branche wip. |
| `src/epreuve/db/session.py` | G | — | — |
| `src/epreuve/db/tables.py` | R | B | Nouveau schéma (ARCHITECTURE §5). |
| `src/epreuve/db/depot.py` | R | B | On garde la structure : classe `Depot`, `ping`, `_journaliser`, la hiérarchie `ErreurDepot`, `_contrainte` (lecture des violations d'unicité), `dernieres_activites` et le principe « renvoie des objets du domaine ». Les requêtes sont réécrites. |
| `migrations/versions/0001_initial.py` | R | B | Nouveau schéma. On garde le schéma `epreuve`, la RLS et les CHECK. Aucune base de production n'existe. |
| `src/epreuve/dofusdb/client.py` | M | B | Gardé (httpx, User-Agent, peu de requêtes). Ajout de `quete`, `objet`, `objets_par_type`, et de `succes` avec ses objectifs. |
| `src/epreuve/dofusdb/import_etage.py` (version wip) | R | B | Devient `contenu/construire.py` et `contenu/ecrire.py`. On garde : la séparation « développer puis écrire », le mode `--a-blanc`, l'import **rejouable**, le journal des changements (`_lisible`) et `ConfigInvalide`. |
| `config/etages/etage-0.yaml` | S | B | Remplacé par `config/etages.yaml` (étage ↔ tranche, cap, nom, image, dates : T-04, T-28), `config/dofus.yaml` et `config/regles.yaml`. |
| `src/epreuve/bot/*` (8 fichiers) | S | A | Plus de bot au lot B. `client.py` (verrou de serveur, `on_error`) et `acces.py` (logique de rôle) se récupèrent depuis ed27bed si un lot D en a besoin. La logique de rôle est reprise dans `discord/oauth.py`. |
| `src/epreuve/web/app.py` | R | A puis B | On garde la fabrique `creer_app(...)`, le gestionnaire d'erreurs générique, `/sante`, l'injection de `maintenant` pour les tests et le protocole `SourceEtat` (une source en base ou la démo). Les routes sont réécrites. |
| `src/epreuve/web/demo.py` | R | B | Même principe : un jeu de démonstration sans base, pour développer B2 avant que B1 soit fini. |
| `src/epreuve/web/templates/index.html`, `static/app.js`, `static/style.css` | S | B | Remplacés par les gabarits tirés de `docs/design/maquette-v2.html` et des tokens de `DA.md`. La fonction d'échappement de `app.js` est reprise. |
| `tests/conftest.py` | M | B | On garde la fixture Postgres jetable (Docker ou `TEST_DATABASE_URL`, saut propre si absente) et `transport_dofusdb`. On ajoute `transport_duffus` et `transport_discord` (faux `httpx.MockTransport`). |
| `tests/fabrique.py` | R | B | Même principe (constructeurs d'objets du domaine aux valeurs par défaut). |
| `tests/donnees/dofusdb/*.json` | G | — | Réponses réelles (donjon 90 et ses 5 succès). On y ajoute celles du repli (§6.7). |
| `tests/domaine/test_classes_modeles.py` | M | B | Les tests des classes sont gardés. Ceux des modèles sont adaptés. |
| `tests/domaine/test_seuil.py`, `test_jauges.py`, `test_controles.py`, `test_inclusion.py` | S | B | Remplacés par `test_bareme.py`, `test_progression.py`, `test_ouverture.py`, `test_visibilite.py` et `test_nature.py`. |
| `tests/db/test_base.py`, `tests/dofusdb/test_import.py`, `tests/web/test_site.py` | R | B | Mêmes catégories de tests, sur le nouveau modèle. |
| `tests/bot/*`, `tests/qa/test_qa_bot.py` | S | A | Le bot sort du périmètre. |
| `tests/qa/test_qa_site.py`, `test_qa_domaine.py` | R | B | On garde les **idées** de tests adverses : XSS par un pseudo, base vide, étage importé sans grimpeur, concurrence. On les réécrit pour le nouveau modèle. |
| `docs/maquette-v1.html` | G | — | Historique. La référence visuelle est maintenant `docs/design/`. |

En lignes, on réutilise environ **un quart du code applicatif** (configuration, session de base, client DofusDB, fabrique web, structure du dépôt, outillage) et **l'essentiel de l'outillage** (CI, sauvegarde, Docker, Fly, fixtures de test). Le domaine, le schéma, les pages et leurs tests sont réécrits, parce que le modèle a changé.

---

## Lot A : la page teaser, l'hébergement et le domaine

### Objectif

Le **vendredi 6/11 au plus tard** (objectif le 3/11), l'adresse du site affiche le teaser du designer, avec son compte à rebours vers le 13/11 à 17:00, en HTTPS sur notre domaine. Plus rien d'autre n'est servi. Ce lot pose aussi la plomberie que le lot B réutilise : Fly, le domaine, la configuration, le middleware du mode, les en-têtes de sécurité et le gabarit de base avec son pied de page.

### Périmètre de fichiers

| Fichier | Action |
|---|---|
| `src/epreuve/domaine/mode_site.py` | **Nouveau** |
| `src/epreuve/config.py` | Modifié (variables du mode, base facultative) |
| `src/epreuve/main.py` | Réécrit (uvicorn seul) |
| `src/epreuve/web/app.py` | Réécrit : `creer_app` minimal (teaser, `/sante`, statiques) |
| `src/epreuve/web/securite.py` | **Nouveau** : middleware du mode, en-têtes de sécurité |
| `src/epreuve/web/templates/base.html` | **Nouveau** : squelette sombre, pied de page (mention de fans + « Merci Duffus ») |
| `src/epreuve/web/templates/teaser.html` | **Nouveau** : transposition de `docs/design/teaser.html` |
| `src/epreuve/web/static/teaser/teaser.css`, `teaser.js` | **Nouveaux** : extraits du teaser, sans changer le rendu |
| `src/epreuve/web/static/fonts/*.woff2` (+ `LICENCE-OFL.txt`) | **Nouveaux** : polices de la DA auto-hébergées |
| `fly.toml`, `Dockerfile`, `.env.example`, `README.md`, `pyproject.toml` | Modifiés |
| `src/epreuve/bot/`, `tests/bot/`, `tests/qa/test_qa_bot.py` | **Supprimés** |
| `src/epreuve/web/templates/index.html`, `static/app.js`, `static/style.css`, `web/demo.py` | Laissés en place jusqu'au lot B, **non routés** |
| `tests/domaine/test_mode_site.py`, `tests/web/test_teaser.py` | **Nouveaux** |

Le domaine v3 (`seuil.py`, `jauges.py`…) et ses tests restent en place au lot A, inutilisés. Le lot B les remplace. On évite ainsi un lot A qui casse 700 tests pour rien.

### Interfaces figées

```python
# src/epreuve/domaine/mode_site.py
from typing import Literal
from datetime import datetime

ReglageMode = Literal["auto", "teaser", "ouvert"]
ModeEffectif = Literal["teaser", "ouvert"]

def mode_effectif(reglage: ReglageMode, ouvert_le: datetime, maintenant: datetime) -> ModeEffectif:
    """« teaser » si réglage = teaser, ou si réglage = auto et maintenant < ouvert_le ; sinon « ouvert ».
    Lève ValueError si ouvert_le ou maintenant n'ont pas de fuseau."""

def voit_site_complet(mode: ModeEffectif, est_admin: bool) -> bool:
    """Vrai en mode ouvert, ou pour un admin. Aucun joueur avant l'ouverture (arbitrage de Marceau)."""
# Changement après livraison du lot A : le paramètre est_testeur est RETIRÉ. Le code livré
# (domaine/mode_site.py, web/securite.py et leurs tests) est adapté par B2 en tête du lot B.

CHEMINS_TOUJOURS_PERMIS: frozenset[str] = frozenset({"/", "/sante"})
PREFIXES_TOUJOURS_PERMIS: tuple[str, ...] = ("/static/",)
# Le lot B ajoute : "/connexion", "/auth/discord/retour", "/deconnexion" (utiles aux admins seulement).
# "/inscription" n'est PAS permis en mode teaser : un joueur connecté y revoit le teaser.
```

```python
# src/epreuve/config.py (champs du lot A)
site_mode: ReglageMode = "auto"                         # SITE_MODE
site_ouvert_le: datetime = 2026-11-13T17:00:00+01:00    # SITE_OUVERT_LE (avec fuseau, sinon erreur)
teaser_lien_entrer: str = ""                            # TEASER_LIEN_ENTRER (vide = bouton masqué)
site_url: str | None = None                             # SITE_URL, ex. https://<domaine> (Origin attendu au lot B)
fuseau: str = "Europe/Paris"
database_url: SecretStr | None = None                   # facultative au lot A
```

```python
# src/epreuve/web/app.py
def creer_app(config: Config, horloge: Callable[[], datetime] = maintenant_utc,
              source: SourceEtat | None = None) -> FastAPI: ...
# GET /        → teaser.html (mode teaser) ; au lot A en mode ouvert : page « La tour s'ouvre » provisoire
# GET /sante   → 200 {"statut": "ok", "base": "absente" | "ok" | "erreur", "mode": "teaser" | "ouvert"}
#                toujours 200 en mode teaser (le teaser ne dépend pas de la base) ; au lot B, 503 si la base est injoignable
# toute autre route → 303 vers / (pages), 404 (chemins /api/…)
```

Contrat du gabarit `teaser.html` : `<body data-ouverture="{{ site_ouvert_le.isoformat() }}" data-lien-site="{{ teaser_lien_entrer }}">`. `teaser.js` lit ces deux attributs à la place des constantes `OUVERTURE` et `LIEN_SITE` du designer. Tout le reste du JS est inchangé.

En-têtes posés sur **toutes** les réponses par `web/securite.py` : la CSP de ARCHITECTURE §9, `X-Robots-Tag: noindex, nofollow`, `Referrer-Policy`, `X-Content-Type-Options`.

### Critères d'acceptation

1. `GET /` renvoie le teaser, **visuellement identique** à `docs/design/teaser.html` à 360, 768 et 1440 px. Comparaison à l'œil par Marceau et par le designer.
2. Le compte à rebours vise le **13/11/2026 à 17:00, heure de Paris**, quel que soit le fuseau de l'appareil. Testé avec le fuseau du navigateur à `America/New_York`.
3. La date est lisible **sans JavaScript**.
4. Le bouton « Entrer dans la tour » n'apparaît qu'après la fin du compte à rebours **et** si `TEASER_LIEN_ENTRER` est renseignée. Vérifié avec `?dans=5`.
5. Le pied de page contient la mention « projet de fans » de la DA **et** « Merci Duffus » avec un lien vers https://duffus.fr.
6. En mode teaser, **aucune autre adresse** ne renvoie de contenu : `/etages/0`, `/grimpeurs`, `/admin`, `/api/etat` et une adresse inventée donnent 303 vers `/` ou 404.
7. Le passage `SITE_MODE=auto` → `ouvert` à `SITE_OUVERT_LE` est vérifié par un test à horloge simulée. `SITE_MODE=teaser` force le teaser après la date.
8. Aucune requête vers un domaine tiers au chargement (onglet Réseau). Les polices sont servies par nous.
9. En-têtes : CSP sans `unsafe-inline` pour les scripts, `X-Robots-Tag: noindex`. Vérifié par un test et avec un outil en ligne d'analyse des en-têtes.
10. Thème sombre uniquement, et aucun visuel du jeu.
11. Le site répond en **HTTPS sur le domaine** (et sur `*.fly.dev`), avec redirection automatique de HTTP vers HTTPS. Le certificat est valide.
12. `GET /sante` répond 200 sans base configurée. La machine Fly redémarre seule si `/sante` échoue.
13. `prefers-reduced-motion` est respecté : décor figé, compte à rebours actif.
14. `ruff` passe, et la couverture de `domaine/mode_site.py` est de 100 %.

### Plan de tests

- `tests/domaine/test_mode_site.py` :
  - `auto` une seconde avant, à l'instant exact et une seconde après `ouvert_le` ;
  - `teaser` et `ouvert` forcés ;
  - dates sans fuseau refusées ;
  - `voit_site_complet` : les 8 combinaisons.
- `tests/web/test_teaser.py`, avec le `TestClient` de FastAPI et une horloge injectée :
  - `/` contient `data-ouverture="2026-11-13T17:00:00+01:00"`, la date en clair, « Merci Duffus » et le lien ;
  - **toutes les routes déclarées** de l'application (énumérées depuis `app.routes`), sauf les permises, renvoient 303 ou 404 en mode teaser ;
  - en-têtes présents sur `/`, `/sante`, un statique et une 404 ;
  - `data-lien-site` est vide par défaut, et égal à la variable si elle est renseignée ;
  - `/sante` sans base renvoie `"absente"`.
- **Manuel** (Marceau, sur la machine Fly) : critères 1, 2, 4, 8, 11 et 13, sur iPhone ou Android réel et sur ordinateur.

---

## Lot B : le cœur

### Objectif

Pour le **13/11 à 17:00**, un grimpeur de la liste officielle se connecte avec Discord **pour la première fois**, crée sa fiche, voit la tour, coche sa progression dans la liste unique de l'étage 0, voit la jauge 2 × N, les fiches des autres et les filtres « qui ne l'a pas fait ». Un admin gèle et réintègre, donne des bonus, revoit et ajuste le contenu d'un étage, et ouvre l'étage suivant quand c'est permis. Les étages 0 à 25 sont construits depuis l'aspiration Duffus, scellés sauf l'étage 0.

### Découpage en chantiers

| Chantier | Qui | Quoi | Dépend de |
|---|---|---|---|
| **B0** (½ j, le 28/10) | dev B1 + architecte | `duffus/client.py` et la commande `releve`. Relevé du schéma réel. L'architecte fige ensuite `duffus/schema.py` (colonnes utiles) et la règle de repérage de la case « classique », dans un addendum à ce document. | Clé et adresse Duffus dans `.env`. Sans elles, B1 commence par `domaine/` et `db/`, et B0 attend jusqu'au 30/10 au soir (voir le plan de repli). |
| **B1** | dev 1 | `domaine/` (sauf `mode_site`), `db/`, migration, `duffus/aspirer.py`, `dofusdb/`, `contenu/` | B0 |
| **B2** | dev 2 | `discord/oauth.py`, `web/` (auth, pages, API, admin, gabarits, JS), `web/demo.py` | Interfaces figées ci-dessous. B2 code contre `demo.py` et un faux dépôt tant que B1 n'est pas fini. |
| **Intégration** (4-5/11) | dev 1 | Branchement du vrai dépôt, tests de bout en bout | B1 et B2 |

### Périmètre de fichiers

B1 :
- `src/epreuve/domaine/{modeles,textes,bareme,progression,ouverture,visibilite,nature}.py` ;
- `src/epreuve/db/{tables,depot}.py` et `migrations/versions/0001_initial.py` ;
- `src/epreuve/duffus/{client,schema,aspirer,__main__}.py` ;
- `src/epreuve/dofusdb/{client,repli}.py` et `src/epreuve/contenu/{construire,ecrire,__main__}.py` ;
- `src/epreuve/regles.py` (lecture et validation de `config/regles.yaml` → `domaine.modeles.Regles`) ;
- `config/regles.yaml`, `config/etages.yaml`, `config/dofus.yaml`, `donnees/duffus/…`, `donnees/dofusdb/…` ;
- les tests correspondants dans `tests/domaine`, `tests/db`, `tests/duffus`, `tests/dofusdb` et `tests/contenu`.

B2 :
- `src/epreuve/discord/oauth.py` ;
- `src/epreuve/web/{app,securite,auth,pages,api,admin,demo}.py` ;
- `src/epreuve/web/templates/` : `base`, `accueil`, `tour`, `etage`, `grimpeurs`, `fiche`, `inscription`, `erreur` et `admin/*` ;
- `src/epreuve/web/static/{style.css,app.js}` (tokens et composants de `DA.md`, gabarits tirés de `maquette-v2.html`) ;
- `tests/web/*` et `tests/qa/test_qa_site.py`.

Les **suppressions** du lot B sont listées dans l'inventaire ci-dessus.

### Interfaces figées

#### Domaine (B1 écrit, B2 consomme)

```python
# src/epreuve/domaine/modeles.py : toutes les dataclasses sont frozen=True ; dates avec fuseau (UTC).
Categorie = Literal["donjons", "full_succes", "principales", "secondaires"]
CATEGORIES: tuple[Categorie, ...] = ("donjons", "full_succes", "principales", "secondaires")
NOM_CATEGORIE: dict[Categorie, str] = {"donjons": "Donjons", "full_succes": "Full succès",
                                       "principales": "Quêtes principales", "secondaires": "Quêtes secondaires"}
Statut = Literal["actif", "pause", "exclu"]
StatutEtage = Literal["scelle", "ouvert", "termine"]
Nature = Literal["principale", "secondaire"]
OrigineNature = Literal["duffus", "dofusdb", "admin"]
TypeElement = Literal["case", "quete"]

class Etage:       id: int; numero: int; nom: str; niveau_min: int; niveau_max: int; level_cap: int
                   statut: StatutEtage; ouvert_le: datetime | None; date_plancher_suivant: datetime | None
                   palier_manuel: int | None; ambiance_url: str | None   # aucun lien vers duffus.fr (EX-70)
class Donjon:      id: int; etage_id: int; nom: str; niveau: int | None; ordre: int; bloc: str | None
                   dofusdb_id: int | None; origine: Literal["propose", "admin"]
                   succes_source: Literal["duffus", "dofusdb"]; masque: bool
class CaseSucces:  id: int; donjon_id: int; ordre: int; nom: str; condition: str; est_classique: bool; masquee: bool
class Quete:       id: int; etage_id: int; nom: str; niveau: int | None; bloc: str; ordre: int
                   nature: Nature; nature_origine: OrigineNature; dofus: tuple[str, ...]
                   jusqu_ou: str | None; a_lier: str | None; a_une_fiche: bool; masquee: bool   # la fiche se lit à part (FicheQuete)
class Grimpeur:    id: int; discord_user_id: int; nom_discord: str; pseudo: str; classe: str | None; statut: Statut
                   niveau_declare: int | None; inscrit_le: datetime      # __post_init__ : classe (si donnée) et statut valides
class EntreeJournal: id: int; horodatage: datetime; acteur_discord_id: int | None; type: str
                   grimpeur_id: int | None; etage_id: int | None; details: Mapping[str, object]; public: bool
class Session:     discord_user_id: int; nom_discord: str; est_admin: bool; roles_verifies_le: datetime
                   expire_le: datetime; jeton_oauth: str; csrf: str   # jamais transmis à un gabarit

class Regles:      # lu depuis config/regles.yaml (SPEC §8.1) ; valeurs par défaut = réponses par défaut d'EXIGENCES
                   points_par_joueur: Fraction = Fraction(2)        # palier = ⌈ m × N × K ÷ 4 ⌉ (EX-09, EX-109)
                   categorie_vide: Literal["ignoree", "offerte"] = "ignoree"   # T-11
                   succes_coche_vaincu: bool = True                 # T-16
                   pause_peut_cocher: bool = True                   # T-13
                   classe_obligatoire: bool = False                 # T-20
                   afficher_nom_discord: bool = True                # T-20
                   liste_officielle_obligatoire: bool = True        # T-19
                   verrouiller_modules_par_etage: bool = False      # T-08 (lot E)
class ElementRef:  type: TypeElement; id: int
class Coches:      grimpeur_id: int; cases: frozenset[int]; quetes: frozenset[int]
                   def contient(self, ref: ElementRef) -> bool

class ContenuEtage:
    """Le contenu VISIBLE d'un étage : rien de masqué. Une case d'un donjon masqué est exclue."""
    etage: Etage; donjons: tuple[Donjon, ...]; cases: tuple[CaseSucces, ...]; quetes: tuple[Quete, ...]
    @staticmethod
    def visible(etage: Etage, donjons: Iterable[Donjon], cases: Iterable[CaseSucces],
                quetes: Iterable[Quete]) -> "ContenuEtage": ...
    def cases_du_donjon(self, donjon_id: int) -> tuple[CaseSucces, ...]: ...   # triées par ordre
    def elements(self) -> tuple[ElementRef, ...]: ...                          # toutes cases et quêtes visibles
```

```python
# src/epreuve/domaine/bareme.py
class EtatCategorie:   categorie: Categorie; faits: int; total: int
                       @property acquise -> bool   # total > 0 and faits == total
                       @property vide -> bool      # total == 0
def categories_grimpeur(contenu: ContenuEtage, coches: Coches) -> dict[Categorie, EtatCategorie]:
    """donjons : faits/total sur les cases classiques visibles (une par donjon visible qui en a une) ;
    full_succes : sur toutes les cases visibles ; principales, secondaires : sur les quêtes visibles."""
def points_grimpeur(contenu: ContenuEtage, coches: Coches, regles: Regles) -> int
    """0 à 4, catégories indépendantes. Si regles.categorie_vide == "offerte", une catégorie vide rapporte 1."""
def categories_comptees(contenu: ContenuEtage, regles: Regles) -> int
    """K : nombre de catégories non vides (« ignoree ») ou toujours 4 (« offerte »)."""
def palier(nb_actifs: int, nb_categories: int, regles: Regles, palier_manuel: int | None = None) -> int:
    """palier_manuel s'il n'est pas None ; sinon ceil(regles.points_par_joueur × nb_actifs × nb_categories / 4),
    en Fraction (exact). ValueError si une entrée est négative ou si nb_categories > 4."""
class EtatJauge:       score: int; palier: int; palier_manuel: bool; actifs: int; en_pause: int
                       nb_categories: int              # K, pour écrire la formule du palier à côté de la jauge
                       points_par_categorie: dict[Categorie, int]
                       @property pleine -> bool        # actifs > 0 and palier > 0 and score >= palier
                       @property maximum -> int        # nb_categories × actifs (« Maximum possible », DA)
                       @property manquants -> int      # max(0, palier - score)
def calculer_jauge(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur],
                   coches: Mapping[int, Coches], regles: Regles) -> EtatJauge:
    """Seuls les grimpeurs actifs comptent. Sans entrée dans `coches` : 0 point. Pas de bonus au lot B (lot C).
    Palier : contenu.etage.palier_manuel s'il est réglé, sinon la formule."""
def detail_par_grimpeur(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
                        regles: Regles) -> list[tuple[Grimpeur, dict[Categorie, EtatCategorie], int]]
    """Pour la vérification avant ouverture (EX-83) : chaque grimpeur, ses catégories, ses points."""

def cascade_coche(contenu: ContenuEtage, ref: ElementRef, cochee: bool, regles: Regles) -> tuple[ElementRef, ...]
    """Les éléments à changer en plus de `ref` (T-16) : cocher un succès non classique → la case classique du
    donjon ; décocher la case classique → les autres cases du donjon. Vide si regles.succes_coche_vaincu est faux."""
```

```python
# src/epreuve/domaine/progression.py
def compteurs(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur],
              coches: Mapping[int, Coches]) -> dict[ElementRef, int]        # nombre d'ACTIFS ayant coché
def qui(element: ElementRef, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
        fait: bool) -> list[Grimpeur]                                      # actifs seulement, tri par pseudo (casefold)
def qui_categorie(contenu: ContenuEtage, categorie: Categorie, grimpeurs: Iterable[Grimpeur],
                  coches: Mapping[int, Coches], fait: bool) -> list[Grimpeur]  # « fait » = a le point ; actifs, tri par pseudo
def avancement(contenu: ContenuEtage, coches: Coches) -> tuple[int, int]   # (cochés visibles, total visible)
def moins_avance(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
                 regles: Regles) -> Grimpeur | None     # parmi les actifs : min (points, cochés), puis pseudo
```

```python
# src/epreuve/domaine/ouverture.py
class Decision:  ok: bool; raisons: tuple[str, ...]   # raisons lisibles, en français, même si ok (force)
class Bilan:     fige_le: datetime; actifs: int; palier: int; score: int
                 points_par_categorie: dict[Categorie, int]; force: bool; motif: str | None
def peut_ouvrir(jauge: EtatJauge, en_cours: Etage, prochain: Etage | None, maintenant: datetime) -> Decision
    # raisons possibles : « aucun étage préparé », « jauge : il manque N points », « aucun grimpeur actif »,
    # « pas avant le <date_paris(en_cours.date_plancher_suivant)> », « l'étage en cours n'est pas ouvert »
def bilan_etage(jauge: EtatJauge, maintenant: datetime, force: bool, motif: str | None) -> Bilan
    # ValueError si force et motif vide
```

```python
# src/epreuve/domaine/visibilite.py
def etages_visibles(etages: Iterable[Etage], est_admin: bool) -> list[Etage]   # ouverts et terminés (admin : tous), par numéro
def etage_cochable(etage: Etage) -> bool                                     # ouvert ou terminé
def peut_modifier_coches(acteur_grimpeur_id: int | None, est_admin: bool, cible_grimpeur_id: int) -> bool
NB_SCELLES_DECORATIFS = 6                                                    # constante d'affichage, jamais calculée
```

```python
# src/epreuve/domaine/nature.py
def quetes_obligatoires(critere: str) -> frozenset[int]
    """Ids Qf=… exigés en « ET » dans un startCriterion DofusDB ; tout groupe contenant « | » est ignoré."""
def fermeture(racines: Iterable[int], prerequis: Mapping[int, Iterable[int]]) -> frozenset[int]
    """Racines et tous leurs prérequis directs ou indirects ; supporte les cycles."""
class Classement:  nature: Nature; origine: OrigineNature; dofus: tuple[str, ...]
def classer(quetes: Iterable[int], guides_duffus: Mapping[str, Iterable[int]],
            guides_repli: Mapping[str, Iterable[int]], dofus_retenus: Collection[str],
            forcees: Mapping[int, Nature]) -> dict[int, Classement]
    """Priorité : forcees (origine admin) > guides_duffus (fermés) > guides_repli (origine dofusdb).
    Une quête dans aucun guide d'un Dofus retenu est secondaire. Ordre des dofus : alphabétique."""
```

```python
# src/epreuve/domaine/textes.py
def liste_francaise(mots: list[str]) -> str               # repris tel quel
def date_paris(d: datetime) -> str                        # « vendredi 13 novembre à 17 h »
def valider_pseudo(pseudo: str) -> str                    # nettoyé ; ValueError si < 2 ou > 30 caractères
def nettoyer_fiche(html: str, quetes_ouvertes: Mapping[str, str]) -> str
    # DANS contenu/construire.py, pas dans le domaine (dépend de nh3) : liste blanche, sans image ni lien duffus.fr ;
    # quetes_ouvertes : id Duffus → notre adresse, pour réécrire les liens internes
```

```python
# src/epreuve/domaine/fiche.py : la fiche de quête (SPEC §4.4 bis), exigence forte de Marceau
SourceFiche = Literal["duffus", "duffus+dofusdb", "dofusdb"]
class EtapeFiche:      ordre: int; titre: str; texte_html: str          # texte_html déjà nettoyé par nettoyer_fiche
                       objectifs: tuple[str, ...]
class Position:        libelle: str; x: int; y: int; zone: str | None    # « PNJ Ganymède », [4, -19], « Incarnam »
class Besoin:          nom: str; quantite: int; icone_url: str | None    # objet nécessaire, ou monstre à vaincre
class Prerequis:       quete_id: int | None; nom: str | None
                       statut: Literal["visible", "scelle", "hors_guide"]
                       # visible : étage ouvert ou terminé → lien vers sa fiche ; scelle : nom ET id à None (EX-111) ;
                       # hors_guide : nom seul, sans lien
class FicheQuete:      quete_id: int; etage_numero: int; nom: str; niveau: int | None; bloc: str
                       nature: Nature; dofus: tuple[str, ...]
                       jusqu_ou: str | None; a_lier: str | None
                       prerequis: tuple[Prerequis, ...]; etapes: tuple[EtapeFiche, ...]
                       objets: tuple[Besoin, ...]; monstres: tuple[Besoin, ...]; positions: tuple[Position, ...]
                       succes_lie: str | None; recompenses: tuple[str, ...]   # « 1 200 XP », « 300 kamas », « Émote … »
                       source: SourceFiche
                       @property complete -> bool   # source != "dofusdb" (une fiche Duffus existe)
def masquer_prerequis_scelles(fiche: FicheQuete, etages_visibles: Collection[int],
                              etage_de_quete: Mapping[int, int]) -> FicheQuete
    """Remplace chaque prérequis d'un étage non visible par Prerequis(None, None, "scelle"). Toujours appelée
    avant de rendre une fiche à un non-admin : la page et le fragment n'ont aucun autre chemin."""
def extraire_ids_discord(texte: str) -> list[int]         # « <@123> <@!456> 789 » → [123, 456, 789], sans doublon
```

#### Dépôt (B1 écrit, B2 consomme)

```python
# src/epreuve/db/depot.py : toutes les méthodes sont async ; acteur = id Discord ; maintenant = datetime UTC.
class ErreurDepot(Exception); class Introuvable(ErreurDepot); class PseudoDejaPris(ErreurDepot)
class PasSurLaListe(ErreurDepot); class DejaInscrit(ErreurDepot); class EtatInvalide(ErreurDepot)
class CocheRefusee(ErreurDepot)   # grimpeur exclu, ou gelé avec pause_peut_cocher faux

class Depot:
    # lecture
    ping() -> bool
    etages() -> list[Etage]
    etage_par_numero(numero: int) -> Etage | None
    contenu_etage(etage_id: int) -> ContenuEtage                       # visible seulement (ContenuEtage.visible)
    contenu_brut(etage_id: int) -> tuple[Etage, list[Donjon], list[CaseSucces], list[Quete]]  # masqués compris (revue admin)
    alertes_etage(etage_id: int) -> list[str]                          # alertes de la dernière construction
    coches_etage(etage_id: int) -> dict[int, Coches]
    grimpeurs() -> list[Grimpeur]
    grimpeur(grimpeur_id: int) -> Grimpeur | None
    grimpeur_par_discord(discord_user_id: int) -> Grimpeur | None
    liste_officielle() -> dict[int, Statut]
    dernieres_activites() -> dict[int, datetime]
    bilan(etage_id: int) -> Bilan | None
    journal(limite: int = 200, grimpeur_id: int | None = None, etage_id: int | None = None,
            type_: str | None = None) -> list[EntreeJournal]
    # écriture grimpeur
    creer_grimpeur(discord_user_id, nom_discord, pseudo, classe, niveau_declare, maintenant) -> Grimpeur
    maj_nom_discord(discord_user_id, nom_discord) -> None                        # à chaque connexion
        # PasSurLaListe, DejaInscrit, PseudoDejaPris ; statut = statut initial de la liste officielle
    modifier_grimpeur(grimpeur_id, acteur, maintenant, *, pseudo=None, classe=None, niveau_declare=None) -> Grimpeur
    cocher(grimpeur_id, ref: ElementRef, cochee: bool, acteur, maintenant, regles: Regles,
           motif: str | None = None) -> tuple[ElementRef, ...]
        # éléments réellement changés, cascade T-16 comprise (bareme.cascade_coche), dans UNE transaction ; idempotent.
        # Introuvable si l'élément est inconnu, masqué ou d'un étage scellé ; CocheRefusee si le grimpeur est exclu,
        # ou gelé avec pause_peut_cocher faux. Si l'acteur (id Discord) n'est pas grimpeur.discord_user_id (admin) : motif obligatoire
        # (ValueError sinon), journal avec public = faux (T-15).
    cocher_donjon(grimpeur_id, donjon_id, acteur, maintenant, regles: Regles, motif: str | None = None) -> int
        # nb de cases nouvellement cochées ; mêmes règles que cocher
    # écriture admin (toutes journalisées)
    ajouter_liste(discord_ids: list[int], statut_initial: Literal["actif", "pause"], acteur, maintenant) -> list[int]  # ids ajoutés
    changer_statut(grimpeur_id, statut: Statut, motif: str | None, acteur, maintenant) -> Grimpeur
    regler_palier(etage_id, palier: int | None, motif: str, acteur, maintenant) -> Etage
    regler_date_plancher(etage_id, date: datetime | None, acteur, maintenant) -> Etage
    modifier_quete(quete_id, acteur, maintenant, *, nature: Nature | None = None, motif: str | None = None,
                   masquee: bool | None = None, nom: str | None = None) -> Quete
    modifier_donjon(donjon_id, acteur, maintenant, *, masque=None, nom=None) -> Donjon
    ajouter_donjon(etage_id, duffus_id: str, acteur, maintenant) -> Donjon     # T-03 : origine « admin », avec ses succès
    donjons_disponibles() -> list[tuple[str, str, int | None]]                   # (duffus_id, nom, niveau) de l'aspiration en base
    regler_etage(etage_id, acteur, maintenant, *, nom=None, ambiance_url=None, level_cap=None) -> Etage  # T-04, T-28
    fiche_quete(quete_id: int) -> FicheQuete | None                              # brute ; masquer_prerequis_scelles avant rendu
    quetes_sans_fiche(etage_id: int) -> list[Quete]                              # le repli, à signaler à Marceau
    modifier_case(case_id, acteur, maintenant, *, masquee=None, nom=None, condition=None) -> CaseSucces
    ouvrir_etage(numero: int, bilan_precedent: Bilan, acteur, maintenant) -> Etage
        # une transaction, verrou FOR UPDATE sur les étages : précédent → termine + bilan, numero → ouvert
        # EtatInvalide si numero n'est pas scellé, ou si un autre admin vient d'ouvrir
    # sessions
    creer_session(id_hache: bytes, discord_user_id, nom_discord, est_admin, jeton_oauth, csrf, maintenant, duree) -> None
        # mêmes noms de champs que la dataclass Session ; expire_le = maintenant + duree
    session(id_hache: bytes, maintenant) -> Session | None    # None si expirée
    maj_roles_session(id_hache, est_admin, maintenant) -> None
    supprimer_session(id_hache) -> str | None                 # renvoie le jeton OAuth, à révoquer
    purger_sessions(maintenant) -> int
```

#### Discord (B2) : connexion seulement, aucun bot

```python
# src/epreuve/discord/oauth.py
class ErreurDiscord(Exception); class PasMembre(ErreurDiscord)
class Identite:  discord_user_id: int; nom: str; roles: frozenset[int]
class ClientOAuth:
    def __init__(self, client_id: str, client_secret: SecretStr, redirect_uri: str, guild_id: int,
                 transport: httpx.AsyncBaseTransport | None = None): ...
    def url_autorisation(self, state: str) -> str                 # scope « identify guilds.members.read »
    async def echanger_code(self, code: str) -> str               # jeton d'accès
    async def identite(self, jeton: str) -> Identite              # /users/@me + /users/@me/guilds/{g}/member ; PasMembre si 404
    async def revoquer(self, jeton: str) -> None                  # erreurs ignorées et journalisées
def est_admin(identite: Identite, roles_admin: frozenset[int], admins_sup: frozenset[int]) -> bool
```

#### API JSON (B2 écrit, `app.js` consomme)

`POST /api/coches`, avec l'en-tête `X-CSRF-Token` et le corps `{"type": "case" | "quete" | "donjon", "id": 12, "cochee": true, "grimpeur_id": 3, "motif": "…"}`. Les champs `grimpeur_id` et `motif` sont facultatifs, et réservés aux admins : un admin qui modifie la fiche d'un autre doit donner un motif (422 sinon). Un admin sans fiche peut le faire. `"donjon"` coche les 5 cases, et `cochee` doit alors valoir `true`. Dans la réponse, `moi` décrit le grimpeur **ciblé**, et `compteurs` donne le nouveau compteur de chaque élément changé (clé `"case:<id>"` ou `"quete:<id>"`).

```json
{"ok": true,
 "changement": true,
 "moi": {"points": 1,
         "categories": {"donjons": {"faits": 4, "total": 6, "acquise": false}, "...": "..."}},
 "jauge": {"score": 19, "palier": 24, "actifs": 12, "en_pause": 2, "pleine": false,
           "points_par_categorie": {"donjons": 10, "full_succes": 3, "principales": 4, "secondaires": 2}},
 "compteurs": {"case:12": 7}}
```

Codes d'erreur :
- 401 : pas de session ;
- 403 : CSRF invalide, `Origin` étranger, grimpeur cible non permis, grimpeur exclu, ou gelé alors que `pause_peut_cocher` est faux (`CocheRefusee`) ;
- 404 : élément inconnu, masqué ou d'un étage scellé (`Introuvable`) ;
- 409 : pas de fiche, pour une coche sur soi-même ;
- 422 : corps invalide, ou motif absent pour une coche d'admin sur un autre.

Le corps d'erreur est `{"ok": false, "message": "…"}`, en français.

`GET /api/etages/{numero}/manque?type=case|quete&id=<entier>` ou `?type=categorie&id=donjons|full_succes|principales|secondaires` renvoie `{"pas_fait": [{"id", "pseudo", "classe"}], "fait": [...]}` (actifs seulement). Pour une catégorie, « fait » veut dire « a le point » (`progression.qui_categorie`). Un étage scellé donne 404.

### Critères d'acceptation

**Connexion et fiche**
1. « Se connecter avec Discord » mène à l'écran d'autorisation de Discord, avec les portées « identify » et « guilds.members.read » seulement. Au retour, un membre du serveur est connecté. Un non-membre voit le message de refus, et aucune session n'est créée.
2. Un `state` absent, faux ou expiré refuse la connexion.
3. Un membre de la liste officielle sans fiche arrive sur « Créer ma fiche ». Un membre hors liste voit le message « envoie ta validation en MP à Shadoaze ».
4. Le pseudo est unique sans tenir compte de la casse (« Brindille » et « brindille » sont refusés ensemble). La classe est facultative ; si elle est donnée, c'est l'une des 19.
4 bis. **Avant le 13/11** (mode teaser), un joueur non admin qui se connecte revoit le teaser. Aucune fiche n'est créée, `/inscription` renvoie 303 vers `/`, et aucune autre page ne lui est servie. Un admin connecté voit tout, avec le bandeau « Mode teaser ».
4 ter. Un admin sans fiche accède à l'admin et à toutes les pages de consultation, sans compter dans la jauge. Un exclu connecté ne voit que le message « Ta participation est suspendue ».
5. Le statut de la fiche créée est le statut initial de la liste (`actif` par défaut).
6. Un admin dont on retire le rôle sur Discord perd l'accès admin à sa première action d'admin plus de 10 minutes après le retrait.
7. La déconnexion supprime la session (le cookie ne fonctionne plus) et révoque le jeton chez Discord.

**Tour et étage**
8. La tour ne contient **que** les étages ouverts et terminés, plus 6 blocs « ? » décoratifs (3 à 360 px). Le HTML et le JSON ne contiennent aucun nom, contenu ou identifiant d'un étage scellé, ni le numéro d'un scellé autre que N+1. « Étage N+1 · prêt » n'apparaît que si la jauge est pleine, que l'étage N+1 existe ou non. `/etages/{n}` répond 404 pour un étage scellé, sauf pour un admin.
9. La liste unique de l'étage suit l'ordre du guide, avec les badges de catégorie de la DA, lisibles sans la couleur.
10. Le filtre cumulatif à 4 cases affiche exactement les catégories cochées, dans toutes les combinaisons. « Seulement ce qui me reste » masque ce qui est fait. Le choix survit à un rechargement.
11. Un donjon se déplie sur ses 5 sous-cases, la case classique en premier. « Tout le donjon » coche les 5. Cocher un succès coche aussi la case classique, et décocher la case classique décoche les 4 autres (T-16). Avec `succes_coche_vaincu: false`, plus de cascade.
11 bis. **Fiche de quête** (SPEC §4.4 bis) :
   - **Parité avec Duffus** : pour **chaque** quête des étages 0 et 1 qui a une fiche dans l'aspiration réelle, chaque champ non vide côté Duffus apparaît dans notre fiche : « jusqu'où », « à lier », prérequis, étapes et objectifs, objets, monstres, positions, succès lié, récompenses. Test automatique de comparaison des extraits avec `FicheQuete`, puis contrôle à l'œil par Marceau sur 5 quêtes tirées au hasard, comparées à duffus.fr.
   - Un prérequis d'un étage ouvert est un lien vers sa fiche. Un prérequis d'un étage scellé n'expose ni son nom ni son id, dans le HTML comme dans le fragment.
   - **Mobile** (360 px) : le panneau occupe tout l'écran. « ← Retour à la liste » et le bouton retour du navigateur le ferment, et la position de défilement de la liste est conservée. **Ordinateur** (1440 px) : panneau latéral, la liste reste défilable, `Échap` ferme, et le focus revient à la ligne de la quête. `/etages/{n}/quetes/{id}` fonctionne aussi en page complète, sans JavaScript.
   - La case à cocher de la fiche et celle de la liste restent synchronisées.
   - La fiche ne contient **aucun** lien vers duffus.fr, aucune image distante, aucune balise `<script>` ou `<style>` ni aucun attribut `on*=` (test sur toutes les fiches de l'aspiration réelle). Le seul lien vers duffus.fr du site est celui du pied de page (T-09).
   - Les quêtes **sans fiche Duffus** affichent « Fiche détaillée indisponible ». Elles sont listées dans le rapport de construction et comptées dans la revue de l'étage. **Au-delà de 5 % des quêtes d'un étage**, la construction s'arrête sans `--forcer` et le rapport demande la décision de Marceau.
12. Cocher met à jour sans rechargement la case, mes catégories, mes points, la jauge et le compteur. Un double toucher rapide ne crée pas d'incohérence. En cas d'échec réseau, la case revient en arrière avec le message prévu.
13. On ne peut pas cocher pour un autre grimpeur (403), sauf en étant admin. On ne peut pas cocher sur un étage scellé ni un élément masqué (404).
14. Un grimpeur en pause peut cocher. Ses points n'entrent pas dans le score. Un exclu reçoit 403.

**Calcul**
15. Pour l'étage de démonstration de référence (`tests/fabrique.py` : 3 donjons, 4 principales, 5 secondaires, 12 grimpeurs dont 2 en pause, coches fixées), la jauge affiche exactement le score, le palier et le détail calculés à la main dans le test.
16. Palier = 2 × N avec 4 catégories, ⌈N × K ÷ 2⌉ avec K catégories non vides, ou le palier manuel s'il est réglé. Le texte de la jauge le dit. Changer `points_par_joueur` ou `categorie_vide` dans `config/regles.yaml`, puis redéployer, change le calcul **sans modifier le code** (EX-109).
18. Le compteur « 7/12 » et « Qui ne l'a pas fait ? » ne comptent que les actifs, et sont cohérents entre eux pour chaque élément (propriété testée).

**Fiches et filtres**
19. La liste des grimpeurs ne trie jamais par score. Les exclus n'y figurent pas, sauf pour un admin.
20. La fiche montre les 4 catégories, les points et l'avancement pour l'étage ouvert et chaque étage terminé, l'avancement global, et le récapitulatif des succès de donjon.
21. Le filtre par élément affiche « Pas encore fait » et « Déjà fait, ils peuvent accompagner », conformes au calcul, pour une quête, une case, un donjon (sa case « Vaincre le boss ») et une catégorie (« a le point »). Le lien « Qui manque ? » de chaque tuile de catégorie donne la même liste.

**Admin**
22. Coller des mentions `<@…>` ajoute les identifiants à la liste officielle, sans doublon.
23. Geler et réintégrer modifient le palier immédiatement. L'écran annonce l'effet (« Palier 24 → 22 ») avant confirmation. La ligne d'un grimpeur gelé montre aussi le moins avancé des actifs.
24. Exclure demande un motif et une confirmation. C'est réversible.
26. Revue d'étage : changer la nature d'une quête (motif obligatoire, origine `admin`), masquer ou démasquer un donjon, une case ou une quête, corriger un libellé, **ajouter un donjon** depuis la liste des donjons aspirés (T-03), régler le nom, l'image d'ambiance et le cap (T-04, T-28). Ces choix **survivent à une reconstruction** de l'étage. La source des succès de chaque donjon (Duffus ou DofusDB) est affichée (T-02).
26 bis. *Admin → Étage ouvert* : régler un **palier manuel** (entier ≥ 1, motif obligatoire) change la jauge tout de suite, et le texte dit « palier fixé par un admin » ; vider le champ rétablit la formule. Régler la **date plancher** change la raison affichée par le bouton d'ouverture.
27. Avant d'ouvrir, l'admin voit le **détail par grimpeur** (catégories, points, dernière activité, EX-83). **Ouvrir le prochain étage** n'est actif que si `peut_ouvrir` est vrai. Sinon, le bouton affiche les raisons. Forcer exige un motif. L'ouverture fige le bilan, passe l'étage précédent à `termine` et fait apparaître le nouvel étage. Deux admins qui ouvrent en même temps produisent **une seule** ouverture (l'autre reçoit un message clair).
28. Toute écriture d'admin et toute coche apparaissent dans *Admin → Journal* avec l'auteur, la date et les détails.
28 bis. Un admin retire une coche d'un grimpeur depuis sa fiche en mode édition : sans motif, c'est refusé (422) ; avec motif, la coche disparaît, la jauge baisse, et le journal garde le motif avec `public` faux. La fiche du grimpeur ne montre ni le motif ni l'auteur.
29. Aucun bot : le site n'appelle Discord que pour la connexion (`oauth2/token`, `users/@me`, `users/@me/guilds/{id}/member`, `oauth2/token/revoke`). Aucun jeton de bot n'est lu par la configuration (test sur les appels du faux transport).

**Contenu**
30. `python -m epreuve.duffus aspirer --a-blanc` respecte les règles de politesse : au plus une requête par seconde, `User-Agent`, arrêt sur 401 ou 403. Il écrit des extraits triés et stables : deux aspirations identiques donnent des fichiers identiques octet par octet.
31. Une colonne exigée absente arrête l'aspiration avec le message prévu, et n'écrit rien.
32. `python -m epreuve.contenu construire --etage 0` crée l'étage 0 **ouvert** (30/10 à 17:00, date plancher le 13/11 à 17:00). Les étages 1 à 25 sont créés **scellés**. Une reconstruction ne crée aucun doublon, masque au lieu de supprimer, et respecte le garde-fou de 10 % sur un étage ouvert.
33. Les alertes (donjon sans 5 succès, repli DofusDB utilisé, quête sans nature) apparaissent en tête de la revue d'étage.

**Transverse**
34. Le pied de page « projet de fans » et « Merci Duffus » est présent sur **toutes** les pages (test sur chaque route GET).
35. Aucun identifiant Discord **numérique** dans le HTML ni dans le JSON servis aux grimpeurs (test qui cherche les identifiants de la fabrique dans chaque réponse). Le nom Discord n'apparaît qu'aux participants connectés, et seulement si `afficher_nom_discord` est vrai (T-20).
36. Un pseudo `<img src=x onerror=alert(1)>` s'affiche en texte partout : tour, fiche, filtres, admin et réponses JSON rendues par `app.js`.
37. Toute requête `POST` sans jeton CSRF valide, ou avec un `Origin` étranger, est refusée (403).
38. Thème sombre uniquement, sans défilement horizontal à 360 px, avec des cases de 44 px de haut au moins. Rendu comparé à l'œil par Marceau avec `maquette-v2.html` à 360 et 1440 px : mêmes composants (tour, jauge à encoches, tuiles de catégorie, pastilles, badges, cases, filtre).
39. `ruff` passe. La couverture des modules `domaine/` est de **100 %**. Les tests de la base tournent dans la CI (Postgres de service).

### Plan de tests

| Fichier | Contenu |
|---|---|
| `tests/domaine/test_bareme.py` | Chaque catégorie seule ; indépendance (quêtes sans donjons) ; full succès ⇒ donjons ; catégorie vide jamais acquise ; donjon masqué, case masquée, donjon sans case classique visible ; `palier` (2N, ⌈N×K/2⌉ pour K = 0 à 4, manuel, entrées invalides) ; `calculer_jauge` : pauses et exclus exclus, N = 0, palier 0 jamais plein, `maximum`. **Propriétés** (hypothesis) : 0 ≤ points ≤ 4 ; cocher ne fait jamais baisser les points ; palier(N, 4) = 2N ; la jauge est la somme des points des actifs. |
| `tests/domaine/test_regles.py` | `config/regles.yaml` absent → défauts ; valeur inconnue → erreur claire au démarrage ; `points_par_joueur: 5/2` exact ; chaque réglage change bien le comportement attendu (`categorie_vide`, `succes_coche_vaincu`, `pause_peut_cocher`). `cascade_coche` : succès → classique, décoche de la classique → les 4, réglage coupé → rien. |
| `tests/domaine/test_progression.py` | `compteurs` et `qui` cohérents (propriété : pour tout élément, compteur + len(qui(pas fait)) = nombre d'actifs) ; `qui_categorie` cohérent avec `categories_grimpeur` ; `avancement` ; `moins_avance` : gelés ignorés, égalités départagées par le pseudo, aucun actif. |
| `tests/domaine/test_ouverture.py` | Chaque raison de refus ; ok exactement à la date plancher ; pas de prochain étage ; `bilan_etage` forcé sans motif refusé. |
| `tests/domaine/test_visibilite.py` | Les scellés ne sortent jamais pour un non-admin ; tri ; `etage_cochable` ; `peut_modifier_coches`. |
| `tests/domaine/test_nature.py` | `quetes_obligatoires` sur des critères réels : `Qf=1462&PL>39` → {1462}, la quête 275 avec son « OU » → ∅, parenthèses imbriquées, critère vide ; `fermeture` avec cycle et diamant ; `classer` : priorité admin > Duffus > repli, Dofus non retenu ignoré, tri des Dofus. Données réelles : la fermeture de l'Émeraude sur les réponses enregistrées donne 15 quêtes. |
| `tests/domaine/test_textes.py` | Dates en heure de Paris (heure d'hiver), pseudos, extraction des mentions. |
| `tests/db/test_depot.py` (Postgres) | Contraintes (coche en double, une seule case classique, un seul étage ouvert, `ON DELETE RESTRICT` sur un élément coché, pseudo sans tenir compte de la casse) ; `cocher` idempotent ; `creer_grimpeur` (pas sur la liste, déjà inscrit) ; **concurrence** : 20 coches simultanées du même élément donnent une seule ligne, deux `ouvrir_etage` simultanés donnent une seule ouverture ; journal écrit dans la même transaction ; sessions expirées. |
| `tests/duffus/test_aspirer.py` | Faux transport : pagination par `Range`, débit (horloge simulée, au plus 1 req/s), `User-Agent`, arrêt sur 401, 403 et 404, `Retry-After` sur 429 (3 essais), colonne manquante, extraits stables (deux exécutions donnent les mêmes octets), rapport de différences. |
| `tests/contenu/test_construire.py` | À partir des extraits réels de `donnees/duffus/` : étage 0 complet ; **parité des fiches** (chaque champ Duffus non vide se retrouve dans `FicheQuete`) ; seuil de 5 % de quêtes sans fiche ; succès de donjon pris chez Duffus quand ils y sont, sinon chez DofusDB, avec la source notée (T-02) ; donjons proposés par niveau, donjon ajouté par l'admin conservé à la reconstruction (T-03) ; `nettoyer_fiche` sur **toutes** les fiches réelles (aucun `<script>`, `on*=`, `<img>`, lien duffus.fr) ; donjon à 4 ou 6 succès → alerte ; repli DofusDB ; nature forcée conservée ; reconstruction idempotente ; garde-fou de 10 % ; `--a-blanc` n'écrit rien. |
| `tests/web/test_auth.py` | Faux Discord (`MockTransport`) : flux complet, `state` faux, non-membre (404), admin par rôle et par liste supplémentaire, revérification après 10 minutes (horloge injectée), déconnexion et révocation, cookie `__Host-` `Secure` `HttpOnly` `SameSite=Lax`. |
| `tests/web/test_pages.py` | Chaque page pour chaque profil (visiteur, membre sans fiche, grimpeur, gelé, admin) ; **mode teaser** : un joueur connecté ne reçoit que le teaser ; fiche de quête en page complète et en fragment, prérequis scellé sans nom ni id, `masquer_prerequis_scelles` appelée sur chaque chemin ; brouillard (aucune trace d'un étage scellé : on cherche son nom et son numéro dans le HTML) ; pied de page sur chaque route ; mode teaser (routes permises au lot B, admin et testeur passent). |
| `tests/web/test_api.py` | `POST /api/coches` : tous les codes d'erreur, la forme JSON exacte, coche d'admin pour un autre, `donjon`. |
| `tests/web/test_admin.py` | Chaque action, ses validations et sa ligne de journal ; un non-admin reçoit 403 sur chaque route d'admin (énumération des routes). |
| `tests/qa/test_qa_site.py` | Tests adverses : XSS par pseudo et par libellé de quête, CSRF, `Origin`, identifiants Discord absents des réponses, base vide, étage sans grimpeur, 0 actif. |
| **Manuel** (testeur de l'équipe, puis recette par les admins) | Parcours complet sur téléphone réel avec un compte Discord de test sur le **serveur de test**. Ouverture d'un étage. Gel et réintégration. Rendu comparé à `maquette-v2.html`. |

### Plan de repli si Duffus résiste (décision au plus tard le 31/10)

**Quand le déclencher.** L'architecte constate, Marceau tranche, le 31/10 au plus tard. Un seul de ces cas suffit :
- pas de clé ni d'adresse Duffus le 30/10 au soir (PREREQUIS D.2) ;
- relevé ou aspiration refusés (401 ou 403) ;
- tables introuvables, ou structure qui ne permet pas de relier une quête ou un donjon à sa tranche.

**Ce qui change.**
- **Étages 0 et 1** : construits à partir d'un fichier saisi à la main, `config/etages-manuels/etage-N.yaml`, complété par **DofusDB** (ARCHITECTURE §6.7) : noms et niveaux des quêtes, donjons, succès sans les Compagnons, et fermeture des Dofus pour la nature. Format :

```yaml
etage: 0
niveau_min: 1
niveau_max: 20
level_cap: 20
donjons: [90, 34]                 # ids DofusDB
blocs:
  - nom: "Incarnam"
    quetes:
      - {dofusdb_id: 1462, jusqu_ou: null}
```

- **Qui le remplit** : Marceau, ou Shadoaze, en suivant le guide Duffus dans son navigateur comme un joueur. Compter 2 à 3 heures pour les deux étages. Les ids se trouvent avec la recherche de DofusDB.
- **Ce qu'on perd** : les **fiches de quête** (`a_une_fiche` faux) et la nature tirée des guides Duffus (repli DofusDB, puis choix de l'admin dans la revue).
- **Aucun lien vers duffus.fr**, ni par étage ni par quête (EX-70, T-09).
- **Code** : B1 ajoute `contenu/manuel.py`, qui lit et valide ce fichier et produit le même `EtagePrepare` que `construire.py` (environ ½ journée). Le reste du lot B est inchangé, puisque `ContenuEtage` ne sait pas d'où vient le contenu.
- L'aspiration Duffus passe au lot C. Les étages 2 et suivants se préparent de la même façon, ou par l'aspiration si l'accès revient, avant que la jauge de l'étage 1 se remplisse.

---

### Addendum B0 : relevé du schéma Duffus (28/10/2026)

**Fait par le dev B1, à valider par l'architecte** (qui fige `duffus/schema.py`). Relevé : `donnees/duffus/schema-2026-10-28.json` (9 requêtes ; l'OpenAPI de PostgREST est fermée, le relevé s'est fait par une ligne de chaque table). Aspiration des étages 0 et 1 : `donnees/duffus/2026-10-28/`, 10 requêtes, aucun refus. Les colonnes retenues sont dans `src/epreuve/duffus/schema.py`. Les images (stockage Duffus) ne sont jamais recopiées.

**Colonnes utiles.**

| Table Duffus | Fichier | Lignes | Colonnes retenues | Rôle |
|---|---|---|---|---|
| `guide_ranges` | `guide_ranges.json` | 24 | id, order_index, range_key, label, title, is_active, dungeon_count, **categories** | Les tranches. `categories` = les **blocs** du guide, chacun avec ses `items` dans l'ordre : `quest` (id → `quest_list.id`), `monster_success`, `tip`. |
| `quest_list` | `quest_list.json` | 1 205 | id, title, url, level, category, Order, **quest_ornot**, own_page, zone, pnj, pos, note, note2, succes, **is_dungeon**, dungeon_info, **dungeons**, **dofus_id** | Les entrées du guide. `url` = `/quete/<slug>` (fiche Duffus), `/guide/<dofus>` ou un site externe. |
| `quest_pages` | `quest_pages.json` (étages 0-1) et `quest_prereqs.json` (toutes, colonnes légères) | 69 / 616 | slug, published, status, meta (titre, niveau, zone, PNJ de départ, coordonnées), prereqs, **prereq_quests**, rewards, manual_resources, steps, **content_html** | Les fiches. Rattachées par `slug` = fin de `quest_list.url`. |
| `dungeon_pages` | `dungeon_pages.json` | 127 | id, slug, published, meta (title, bossName, level, zone, coords, dofusMonsterId), **successes**, linked_quests | Les donjons. `successes` = `challenge1`, `challenge2`, `special` (nom, règle). |
| `achievements` | `achievements.json` | 1 017 (sur 2 781) | id, name, description, category_id, level, order | Copie des succès du jeu ; seuls ceux « … dans son donjon … » sont gardés. |
| `dofus_list` | `dofus_list.json` | 26 | id, nom, quest_id, advised_level | Les Dofus ; `quest_id` → l'entrée `quest_list` qui fait obtenir le Dofus. |

Non retenues : `achievement_objectives` (les descriptions de `achievements` suffisent) et `monsters` (ni icône ni lien utiles : les icônes viendront de DofusDB).

**Rattachement aux tranches.** Étage N = la (N+1)-ième tranche active par `order_index` (24 tranches, de « 1-20 » à « 200-7 », donc **étages 0 à 23**, et non 0 à 25). Le contenu d'un étage est la liste des `items` de ses blocs :
- **quêtes** : les items `quest` dont l'entrée a `quest_ornot` vrai. Les autres entrées sont des **rappels** du guide (« Lancez la quête X », « Allez voir Rathrosk … ») : elles ne sont pas des quêtes à cocher, et leur texte est la meilleure source de « jusqu'où » pour la quête nommée (à valider) ;
- **donjons** : ceux que nomme une entrée du bloc (`dungeons[].url` = `/donjon/<slug>` → `dungeon_pages.slug`), ce qui suit DECISIONS-V4 §12 Q2 (« ceux que duffus.fr rattache à la tranche »). Le compte retrouve `dungeon_count` sur les deux étages ;
- les items `monster_success` et `tip` ne sont pas du contenu cochable.

| | Étage 0 (1-20) | Étage 1 (20-40) |
|---|---|---|
| Blocs | 2 (« Quêtes du tutoriel », « Quêtes d'Incarnam ») | 2 (« Quêtes d'Astrub et obtention du Dofus Argenté », « Quêtes pour débloquer la Diligence d'Astrub et l'accès à Pandala ») |
| Quêtes | 27 | 43 (+ 6 rappels, 11 `monster_success`) |
| Fiches Duffus | 27/27 | 42/43 (« Quête de classe » renvoie vers un site externe) |
| Donjons (`dungeon_count`) | 1 (1) : Crypte de Kardorim | 4 (4) : Grange du Tournesol Affamé, Château Ensablé, Cour du Bouftou Royal, Cache de Kankreblath |
| Succès de donjon trouvés chez Duffus | 5/5 | 5/5 pour chacun des 4 |

**Case « classique ».** Les 5 succès d'un donjon se trouvent dans `achievements` (T-02 : source Duffus) :
- la **classique** est le succès dont le `name` est exactement `meta.title` du donjon (« Crypte de Kardorim ») et dont la description ne contient pas `[challenge,` (« Vaincre Kardorim dans son donjon. ») ;
- les **4 autres** sont les succès de la même `category_id` dont le nom commence par `meta.bossName + " ("` et dont la description contient `[challenge,`, sans « (Compagnon) ». Ordre : la classique, « (Duo) », puis les autres par `order` ;
- couverture sur les 127 donjons : **102 donnent exactement 5**, 7 en donnent 6 (un défi de plus, alerte), 6 n'en donnent qu'un (bossName différent du nom des succès) et 12 n'ont pas de classique au nom exact. Ces 18 derniers passent par le repli DofusDB, avec une alerte. Les 5 donjons des étages 0 et 1 sont tous dans le premier cas.
- les noms de défi de `dungeon_pages.successes` (« Collant », « Premier ») et la règle du « special » complètent la condition affichée.

**Chaînes vers les Dofus : point bloquant pour la nature.** `dofus_list.quest_id` et `quest_list.dofus_id` ne désignent que l'entrée d'**obtention** (« Allez voir Rathrosk … »), dont l'`url` est `/guide/<dofus>` : le **guide par Dofus lui-même n'est dans aucune des 8 tables connues**, et l'entrée d'obtention n'a pas de fiche, donc pas de prérequis. `quest_pages.prereq_quests` donne bien des prérequis de quête à quête (448 fiches sur 616, 526 liens, 13 hors du guide), ce qui permet la **fermeture** une fois les racines connues. En l'état, **aucune quête des étages 0 et 1 ne peut être classée principale à partir des seules données Duffus**. Trois issues, à trancher par l'architecte et Marceau (DECISIONS-V4 §12 interdit la supposition) :
1. trouver dans le code public du site la table des guides par Dofus, puis l'ajouter au relevé ;
2. prendre comme racines les quêtes des blocs « … obtention du Dofus X » (c'est une lecture du guide, pas une donnée explicite) ;
3. repli DofusDB pour la nature (ARCHITECTURE §6.7), marqué « dofusdb ».
En attendant, la construction classe tout en secondaire avec l'alerte « nature non déterminée », et l'admin corrige dans la revue.

**Contenu des fiches** (69 fiches des étages 0 et 1). L'essentiel est dans `content_html`, structuré par classes CSS stables. Correspondance avec `FicheQuete` :

| Champ de `FicheQuete` | Source Duffus | Fiches qui l'ont (ét. 0 / ét. 1) |
|---|---|---|
| étapes | blocs `div.qstep` (dialogue, move, marche, clique, combat, craft, text) de `content_html` ; `steps` est toujours vide | 27/27 · 42/42 |
| objectif (en tête) | `div.qk-card.info` | presque toutes |
| positions | `.qpos` ; `meta.startNpc` + `meta.startCoords` | 21 · 41 |
| objets | blocs « à prévoir » (`.prevoir-qty`) ; `manual_resources` (1 seule fiche) | 7 · 5 |
| monstres | `.mob-stats-card` / `.combat-line` | 10 · 28 |
| prérequis | `prereq_quests` (JSON en texte : titre + `/quete/<slug>`) ; `prereqs` (texte libre) | 18 · 24 |
| récompenses | `rewards` : xp, kamas, items (qté, nom), others | 27 · 41 |
| succès lié | `quest_list.succes` (noms) | 25 · 41 |
| « jusqu'où », « à lier » | aucune colonne dédiée : `note`/`note2` de l'entrée, et les rappels « Lancez la quête … » | — |

Toutes les fiches contiennent des `<img>` (stockage Duffus), et 51 sur 69 des liens internes (`/monstre/…`, `/objet/…`, `/quete/…`, `/donjon/…`) : `nettoyer_fiche` retire les images et les liens, sauf les `/quete/<slug>` d'une quête d'un étage visible, réécrits vers notre fiche.

**Écarts avec la spec.** 24 tranches (étages 0 à 23) au lieu de 26 ; guides par Dofus absents des tables connues (ci-dessus) ; « jusqu'où » et « à lier » sans colonne dédiée ; les fiches complètes ne sont aspirées que pour les étages demandés (`--etages`), les prérequis pour toutes les quêtes.

---

## Traçabilité des exigences (EXIGENCES.md → lots)

Le détail exigence par exigence, avec la section de spec, est dans **SPEC, annexe A**. En résumé :

| Lot | Exigences couvertes |
|---|---|
| **A** (teaser, 6/11) | EX-30 (calendrier), EX-36 (rien d'autre que le teaser n'est public), EX-61, EX-62 (pied de page), EX-95 à EX-97, EX-101, EX-103 (DA, lore), EX-105, EX-107 (hébergement économe, non lucratif), EX-114, EX-115 (mobile) |
| **B** (cœur, 13/11) | EX-01 à EX-16, EX-23 à EX-32, EX-35 à EX-41, EX-43 à EX-52, EX-59, EX-62 à EX-68, EX-70 à EX-74, EX-77 à EX-85, EX-88, EX-102, EX-104, EX-106, EX-109 à EX-115. Points ouverts réglables : T-02 à T-29 (SPEC §8.1). |
| **C** (vie de la tour) | Confort autour d'EX-72 et EX-78 (fil d'activité, suggestions d'entraide), **T-22 (points bonus)**, T-26 (bouton de réaspiration) |
| **E** (modules Duffus) | EX-53, EX-54, EX-56, EX-57 (archimonstres, avis de recherche, outils, stuffs), EX-60, et EX-55, EX-58 selon la réponse de Shadoaze (SPEC §8.2 Q6) ; T-08, T-25, T-27 |
| Hors site ou abandonnées | EX-17 à EX-22, EX-33, EX-34, EX-42, EX-69, EX-75 (rien à coder), EX-76, EX-86, EX-87, EX-89 à EX-93, EX-98 à EX-100, EX-108 |

## Lot C : la vie de la tour (après le 13/11, objectif fin novembre)

- **Fil d'activité** visible des grimpeurs : les dernières coches et ouvertures, jamais les actions de modération.
- **Points bonus** (T-22, déplacés du lot B) : un admin ajoute des points à un grimpeur ou à toute la guilde, sur l'étage en cours, avec un motif. Les bonus s'ajoutent au score sans changer le palier, et se suppriment par annulation, jamais par effacement (table `bonus`, `EtatJauge.bonus`, réglages `bonus.*`). Les détails attendent la réponse de Shadoaze (SPEC §8.2 Q5).
- **Aucune écriture sur Discord** : ni bot, ni webhook, ni annonce automatique, sauf demande explicite de Marceau. L'admin annonce lui-même.
- **Bouton « Réaspirer Duffus »** dans l'admin, qui lance la même commande que le lot B, avec un verrou (une seule à la fois, au plus une par jour), puis la revue des différences en page.
- **Vue « tableau d'étage »** : une matrice grimpeurs × éléments, pour les admins et pour s'organiser.
- **Suggestions d'entraide** : « Brindille et Mirelune n'ont pas encore fait Kardorim (Duo) ».
- Interfaces figées et critères à écrire par l'architecte au début du lot.

## Lot D : validation par screen, en option (si Shadoaze le demande)

Une **option** (DECISIONS §5) : un grimpeur peut joindre un screen à une coche, et un bot ou une IA peut l'analyser. On reprend la conception IA de la v3 (`ARCHITECTURE.md` v3, §7, dans l'historique git : Claude Haiku, sortie structurée, humain dans la boucle). On ne la refait que si la confiance pose un vrai problème pendant les premiers étages.

## Lot E : les autres modules de duffus.fr

Dans l'ordre de SPEC §9 :
- **E1** : avis de recherche (1 à 1,5 j) ;
- **E2** : archimonstres (3 à 4 j) ;
- **E3** : stuffs, intégration (environ 3 j), sans lien vers duffus.fr ;
- **E4** : boîte à outils avec liens et Almanax (1,5 j).

L'encyclopédie et le builder restent des liens. Chaque module réutilise la mécanique des cases, des compteurs et de « qui ne l'a pas fait » du lot B, et l'aspiration Duffus (tables `monsters` et autres).
