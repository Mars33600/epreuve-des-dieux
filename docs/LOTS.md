# L'Épreuve des Dieux : découpage en lots

Version 4, 27/10/2026. Chaque lot suit le circuit de l'équipe : **architecte** (spec technique) → **PO** (critères d'acceptation) → **dev** → **testeur + relecteur** → **rédacteur** → **recette** par Marceau, et par Shadoaze pour ce qui le concerne. Les devs travaillent sur Opus. Les **interfaces figées** ci-dessous sont les contrats entre agents : un dev ne les change pas sans repasser par l'architecte.

## Ce qui change en v4

- **Les dates sont maintenant imposées.** Le teaser doit être en ligne **au plus tard le vendredi 6/11**, et le cœur doit être prêt et testé **pour le vendredi 13/11 à 17:00**. En v3, aucune date n'était imposée.
- **Les lots changent de nature.**
  - **Lot A** : la page teaser, l'hébergement et le domaine.
  - **Lot B** : le cœur de l'application web, à savoir la connexion Discord, les cases à cocher, la jauge 2 × N, la tour, les fiches, les filtres et l'admin (pause, bonus, contenu d'étage, ouverture). Le contenu vient de l'aspiration de Duffus.
  - **Lots C à E** : les enrichissements.

  Les anciens « lot 1 bêta / lancement » et « lot 2 » sont abandonnés.
- **Le bot sort du chemin critique.** Plus de commandes slash ni de connexion à la passerelle Discord. Une annonce facultative par API REST au lot B.
- **Une grande partie du code existant est reprise** (voir l'inventaire), mais le modèle de points (difficultés, paliers, retardataires, contrôles de cap) et tout le bot sont **retirés**.
- **`docs/EXIGENCES.md` est intégré.** Chaque exigence est rattachée à un lot (section « Traçabilité » ci-dessous, détail dans l'annexe A de SPEC). Les points ouverts T-nn qui reçoivent une réponse par défaut se règlent **sans code** : `config/regles.yaml`, `config/etages.yaml` ou une action d'admin.
- Le lot B se fait en **deux chantiers parallèles** (B1 : domaine, base et contenu ; B2 : web), précédés d'une demi-journée de relevé du schéma Duffus (B0). Le lot B est trop gros pour un seul chantier dans les délais. Les interfaces figées permettent de travailler en parallèle.

---

## Calendrier

Aujourd'hui : mardi 27/10/2026. Heure de Paris.

| Jour | Lot A (teaser) | Lot B (cœur) | Marceau et Shadoaze |
|---|---|---|---|
| mar. 27/10 | — | — | Questions à Shadoaze (SPEC §8). Achat du domaine. Comptes Fly et Supabase (PREREQUIS). |
| mer. 28/10 | Dev A | **B0** : relevé du schéma Duffus (½ j), puis l'architecte fige `duffus/schema.py` | Clé et adresse Duffus dans `.env`. OAuth2 réglé chez Discord. |
| jeu. 29 → ven. 30/10 | Dev A, puis test et relecture | **B1** et **B2** en parallèle | 30/10 à 17 h : étage 0 en jeu (le site n'est pas attendu) |
| sam. 31/10 → lun. 2/11 | Recette, **déploiement en mode teaser sur le domaine** | B1 et B2 | Recette A |
| **mar. 3/11** | **Objectif : teaser en ligne** (marge de 3 jours) | B1 et B2 | — |
| mer. 4 → jeu. 5/11 | Correctifs éventuels | Fin de B1 et B2, intégration | Shadoaze relit `config/dofus.yaml` et les étages 0 et 1 construits |
| **ven. 6/11** | **Date limite du teaser en ligne**, publication du lien | Testeur et relecteur | Reveal |
| sam. 7 → dim. 8/11 | — | Correctifs, rédacteur | Construction et revue des étages 0 à 25 (scellés) |
| lun. 9/11 | — | **Recette par Marceau** | — |
| **mar. 10/11** | — | **Déploiement derrière le teaser.** Admins et bêta-testeurs sur le site réel. | Saisie de la liste officielle. Lien « Prépare ta fiche » annoncé sur Discord. |
| mer. 11 → jeu. 12/11 | — | Bêta (correctifs seulement). **Gel du code jeudi 12/11 à 18 h.** | Les grimpeurs créent leur fiche |
| **ven. 13/11, 17:00** | Le teaser s'efface (mode `auto`) | **Ouverture du site** | Marceau renseigne `TEASER_LIEN_ENTRER` et vérifie à 17 h 01 |
| après le 13/11 | — | — | Lots C, D, E |

**Si le lot B glisse** : le teaser reste affiché (`SITE_MODE=teaser`), et rien ne casse côté jeu. Les grimpeurs jouent l'étage 0 sans site, puisque l'étage 1 ne peut de toute façon pas s'ouvrir avant le 13/11, et ils cochent dès l'ouverture tout ce qu'ils ont fait. Un glissement de quelques jours est acceptable (DECISIONS §8 : « pas mi-décembre non plus »). En revanche, **un lot B ouvert mais faux** serait grave : on ne sacrifie pas les tests pour tenir la date.

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

def voit_site_complet(mode: ModeEffectif, est_admin: bool, est_testeur: bool) -> bool:
    """Vrai en mode ouvert, ou pour un admin ou un testeur."""

CHEMINS_TOUJOURS_PERMIS: frozenset[str] = frozenset({"/", "/sante"})
PREFIXES_TOUJOURS_PERMIS: tuple[str, ...] = ("/static/",)
# Le lot B ajoute : "/connexion", "/auth/discord/retour", "/deconnexion", "/inscription".
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

Pour le **13/11 à 17:00**, un grimpeur de la liste officielle se connecte avec Discord, crée sa fiche, voit la tour, coche sa progression dans la liste unique de l'étage 0, voit la jauge 2 × N, les fiches des autres et les filtres « qui ne l'a pas fait ». Un admin gèle et réintègre, donne des bonus, revoit et ajuste le contenu d'un étage, et ouvre l'étage suivant quand c'est permis. Les étages 0 à 25 sont construits depuis l'aspiration Duffus, scellés sauf l'étage 0.

### Découpage en chantiers

| Chantier | Qui | Quoi | Dépend de |
|---|---|---|---|
| **B0** (½ j, le 28/10) | dev B1 + architecte | `duffus/client.py` et la commande `releve`. Relevé du schéma réel. L'architecte fige ensuite `duffus/schema.py` (colonnes utiles) et la règle de repérage de la case « classique », dans un addendum à ce document. | Clé et adresse Duffus dans `.env` |
| **B1** | dev 1 | `domaine/` (sauf `mode_site`), `db/`, migration, `duffus/aspirer.py`, `dofusdb/`, `contenu/`, `discord/annonces.py` | B0 |
| **B2** | dev 2 | `discord/oauth.py`, `web/` (auth, pages, API, admin, gabarits, JS), `web/demo.py` | Interfaces figées ci-dessous. B2 code contre `demo.py` et un faux dépôt tant que B1 n'est pas fini. |
| **Intégration** (4-5/11) | dev 1 | Branchement du vrai dépôt, tests de bout en bout | B1 et B2 |

### Périmètre de fichiers

B1 :
- `src/epreuve/domaine/{modeles,textes,bareme,progression,ouverture,visibilite,nature}.py` ;
- `src/epreuve/db/{tables,depot}.py` et `migrations/versions/0001_initial.py` ;
- `src/epreuve/duffus/{client,schema,aspirer,__main__}.py` ;
- `src/epreuve/dofusdb/{client,repli}.py` et `src/epreuve/contenu/{construire,ecrire,__main__}.py` ;
- `src/epreuve/discord/annonces.py` ;
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
                   palier_manuel: int | None; lien_guide: str | None; ambiance_url: str | None
class Donjon:      id: int; etage_id: int; nom: str; niveau: int | None; ordre: int; bloc: str | None
                   dofusdb_id: int | None; origine: Literal["propose", "admin"]
                   succes_source: Literal["duffus", "dofusdb"]; masque: bool
class CaseSucces:  id: int; donjon_id: int; ordre: int; nom: str; condition: str; est_classique: bool; masquee: bool
class Quete:       id: int; etage_id: int; nom: str; niveau: int | None; bloc: str; ordre: int
                   nature: Nature; nature_origine: OrigineNature; dofus: tuple[str, ...]
                   jusqu_ou: str | None; a_une_fiche: bool; masquee: bool   # le HTML de la fiche est lu à part
class Grimpeur:    id: int; discord_user_id: int; nom_discord: str; pseudo: str; classe: str | None; statut: Statut
                   niveau_declare: int | None; inscrit_le: datetime      # __post_init__ : classe (si donnée) et statut valides

class Regles:      # lu depuis config/regles.yaml (SPEC §8.1) ; valeurs par défaut = réponses par défaut d'EXIGENCES
                   points_par_joueur: Fraction = Fraction(2)        # palier = ⌈ m × N × K ÷ 4 ⌉ (EX-09, EX-109)
                   categorie_vide: Literal["ignoree", "offerte"] = "ignoree"   # T-11
                   succes_coche_vaincu: bool = True                 # T-16
                   pause_peut_cocher: bool = True                   # T-13
                   classe_obligatoire: bool = False                 # T-20
                   afficher_nom_discord: bool = True                # T-20
                   bonus_actif: bool = True                         # T-22
                   bonus_individuel_si_pause: bool = False          # T-22
                   liste_officielle_obligatoire: bool = True        # T-19
                   verrouiller_modules_par_etage: bool = False      # T-08 (lot E)
class Bonus:       id: int; etage_id: int; grimpeur_id: int | None; points: int; motif: str; annule: bool
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
                       points_par_categorie: dict[Categorie, int]; bonus: int
                       @property pleine -> bool        # actifs > 0 and score >= palier
                       @property manquants -> int      # max(0, palier - score)
def calculer_jauge(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur],
                   coches: Mapping[int, Coches], bonus: Iterable[Bonus], regles: Regles) -> EtatJauge:
    """Seuls les grimpeurs actifs comptent. Bonus non annulés (si regles.bonus_actif) : collectifs, et
    individuels d'un actif (ou d'un gelé si regles.bonus_individuel_si_pause). Sans entrée dans `coches` : 0 point."""
def detail_par_grimpeur(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur], coches: Mapping[int, Coches],
                        bonus: Iterable[Bonus], regles: Regles) -> list[tuple[Grimpeur, dict[Categorie, EtatCategorie], int]]
    """Pour la vérification avant ouverture (EX-83) : chaque grimpeur, ses catégories, ses points (bonus compris)."""

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
def avancement(contenu: ContenuEtage, coches: Coches) -> tuple[int, int]   # (cochés visibles, total visible)
def moins_avance(contenu: ContenuEtage, grimpeurs: Iterable[Grimpeur],
                 coches: Mapping[int, Coches]) -> Grimpeur | None           # min (points, cochés), puis pseudo
```

```python
# src/epreuve/domaine/ouverture.py
class Decision:  ok: bool; raisons: tuple[str, ...]   # raisons lisibles, en français, même si ok (force)
class Bilan:     fige_le: datetime; actifs: int; palier: int; score: int
                 points_par_categorie: dict[Categorie, int]; bonus: int; force: bool; motif: str | None
def peut_ouvrir(jauge: EtatJauge, en_cours: Etage, prochain: Etage | None, maintenant: datetime) -> Decision
    # raisons possibles : « aucun étage préparé », « jauge : il manque N points »,
    # « pas avant le vendredi 13 novembre à 17 h », « l'étage en cours n'est pas ouvert »
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
def extraire_ids_discord(texte: str) -> list[int]         # « <@123> <@!456> 789 » → [123, 456, 789], sans doublon
```

#### Dépôt (B1 écrit, B2 consomme)

```python
# src/epreuve/db/depot.py : toutes les méthodes sont async ; acteur = id Discord ; maintenant = datetime UTC.
class ErreurDepot(Exception); class Introuvable(ErreurDepot); class PseudoDejaPris(ErreurDepot)
class PasSurLaListe(ErreurDepot); class DejaInscrit(ErreurDepot); class EtatInvalide(ErreurDepot)

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
    bonus_etage(etage_id: int) -> list[Bonus]
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
    cocher(grimpeur_id, ref: ElementRef, cochee: bool, acteur, maintenant, regles: Regles) -> tuple[ElementRef, ...]
        # éléments réellement changés, cascade T-16 comprise (bareme.cascade_coche), dans UNE transaction ;
        # EtatInvalide si l'élément est masqué, son étage scellé, ou le grimpeur gelé avec pause_peut_cocher faux ; idempotent
    cocher_donjon(grimpeur_id, donjon_id, acteur, maintenant) -> int                  # nb de cases nouvellement cochées
    # écriture admin (toutes journalisées)
    ajouter_liste(discord_ids: list[int], statut_initial: Statut, acteur, maintenant) -> list[int]  # ids ajoutés
    changer_statut(grimpeur_id, statut: Statut, motif: str | None, acteur, maintenant) -> Grimpeur
    ajouter_bonus(etage_id, grimpeur_id: int | None, points: int, motif: str, acteur, maintenant) -> Bonus
    annuler_bonus(bonus_id, acteur, maintenant) -> Bonus
    regler_palier(etage_id, palier: int | None, motif: str, acteur, maintenant) -> Etage
    regler_date_plancher(etage_id, date: datetime | None, acteur, maintenant) -> Etage
    modifier_quete(quete_id, acteur, maintenant, *, nature: Nature | None = None, motif: str | None = None,
                   masquee: bool | None = None, nom: str | None = None) -> Quete
    modifier_donjon(donjon_id, acteur, maintenant, *, masque=None, nom=None) -> Donjon
    ajouter_donjon(etage_id, duffus_id: str, acteur, maintenant) -> Donjon     # T-03 : origine « admin », avec ses succès
    donjons_disponibles() -> list[tuple[str, str, int | None]]                   # (duffus_id, nom, niveau) de l'aspiration en base
    regler_etage(etage_id, acteur, maintenant, *, nom=None, ambiance_url=None, level_cap=None) -> Etage  # T-04, T-28
    fiche_quete(quete_id: int) -> str | None                                     # HTML déjà nettoyé
    modifier_case(case_id, acteur, maintenant, *, masquee=None, nom=None, condition=None) -> CaseSucces
    ouvrir_etage(numero: int, bilan_precedent: Bilan, acteur, maintenant) -> Etage
        # une transaction, verrou FOR UPDATE sur les étages : précédent → termine + bilan, numero → ouvert
        # EtatInvalide si numero n'est pas scellé, ou si un autre admin vient d'ouvrir
    # sessions
    creer_session(id_hache: bytes, discord_user_id, nom, est_admin, jeton_oauth, csrf, maintenant, duree) -> None
    session(id_hache: bytes, maintenant) -> Session | None    # None si expirée
    maj_roles_session(id_hache, est_admin, maintenant) -> None
    supprimer_session(id_hache) -> str | None                 # renvoie le jeton OAuth, à révoquer
    purger_sessions(maintenant) -> int
```

#### Discord (B2)

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

# src/epreuve/discord/annonces.py (B1) : rien ne se passe si channel_id ou jeton est absent
async def annoncer(texte: str, channel_id: int | None, jeton_bot: SecretStr | None,
                   transport: httpx.AsyncBaseTransport | None = None) -> bool
```

#### API JSON (B2 écrit, `app.js` consomme)

`POST /api/coches`, avec l'en-tête `X-CSRF-Token` et le corps `{"type": "case" | "quete" | "donjon", "id": 12, "cochee": true, "grimpeur_id": 3}`. Le champ `grimpeur_id` est facultatif, et réservé aux admins. `"donjon"` coche les 5 cases, et `cochee` doit alors valoir `true`.

```json
{"ok": true,
 "changement": true,
 "moi": {"points": 1, "bonus": 0,
         "categories": {"donjons": {"faits": 4, "total": 6, "acquise": false}, "...": "..."}},
 "jauge": {"score": 19, "palier": 24, "actifs": 12, "en_pause": 2, "pleine": false, "bonus": 0,
           "points_par_categorie": {"donjons": 10, "full_succes": 3, "principales": 4, "secondaires": 2}},
 "compteurs": {"case:12": 7}}
```

Codes d'erreur :
- 401 : pas de session ;
- 403 : CSRF invalide, `Origin` étranger, grimpeur cible non permis, ou étage non cochable ;
- 404 : élément inconnu, masqué ou d'un étage scellé ;
- 409 : pas de fiche ;
- 422 : corps invalide.

Le corps d'erreur est `{"ok": false, "message": "…"}`, en français.

`GET /api/etages/{numero}/manque?type=case|quete&id=…` renvoie `{"pas_fait": [{"id", "pseudo", "classe"}], "fait": [...]}` (actifs seulement).

### Critères d'acceptation

**Connexion et fiche**
1. « Se connecter avec Discord » mène à l'écran d'autorisation de Discord, avec les portées « identify » et « guilds.members.read » seulement. Au retour, un membre du serveur est connecté. Un non-membre voit le message de refus, et aucune session n'est créée.
2. Un `state` absent, faux ou expiré refuse la connexion.
3. Un membre de la liste officielle sans fiche arrive sur « Créer ma fiche ». Un membre hors liste voit le message « envoie ta validation en MP à Shadoaze ».
4. Le pseudo est unique sans tenir compte de la casse (« Brindille » et « brindille » sont refusés ensemble), et la classe est l'une des 19.
5. Le statut de la fiche créée est le statut initial de la liste (`actif` par défaut).
6. Un admin dont on retire le rôle sur Discord perd l'accès admin à sa première action d'admin plus de 10 minutes après le retrait.
7. La déconnexion supprime la session (le cookie ne fonctionne plus) et révoque le jeton chez Discord.

**Tour et étage**
8. La tour ne contient **que** les étages ouverts et terminés, plus 6 blocs « ? » décoratifs. Le HTML et le JSON ne contiennent aucun nom, numéro ou identifiant d'un étage scellé. `/etages/{n}` répond 404 pour un étage scellé, sauf pour un admin.
9. La liste unique de l'étage suit l'ordre du guide, avec les badges de catégorie de la DA, lisibles sans la couleur.
10. Le filtre cumulatif à 4 cases affiche exactement les catégories cochées, dans toutes les combinaisons. « Seulement ce qui me reste » masque ce qui est fait. Le choix survit à un rechargement.
11. Un donjon se déplie sur ses 5 sous-cases, la case classique en premier. « Tout le donjon » coche les 5. Cocher un succès coche aussi la case classique, et décocher la case classique décoche les 4 autres (T-16). Avec `succes_coche_vaincu: false`, plus de cascade.
11 bis. Un toucher sur une quête ouvre sa **fiche intégrée** (comment, besoins, succès lié, prérequis). Elle ne contient **aucun** lien vers duffus.fr, aucune image distante ni balise `<script>`, `<style>`, `on*=` (test sur toutes les fiches de l'aspiration réelle). Le seul lien vers duffus.fr du site est celui du pied de page (T-09).
12. Cocher met à jour sans rechargement la case, mes catégories, mes points, la jauge et le compteur. Un double toucher rapide ne crée pas d'incohérence. En cas d'échec réseau, la case revient en arrière avec le message prévu.
13. On ne peut pas cocher pour un autre grimpeur (403), sauf en étant admin. On ne peut pas cocher sur un étage scellé ni un élément masqué (404).
14. Un grimpeur en pause peut cocher. Ses points n'entrent pas dans le score.

**Calcul**
15. Pour l'étage de démonstration de référence (`tests/fabrique.py` : 3 donjons, 4 principales, 5 secondaires, 12 grimpeurs dont 2 en pause, coches fixées), la jauge affiche exactement le score, le palier et le détail calculés à la main dans le test.
16. Palier = 2 × N avec 4 catégories, ⌈N × K ÷ 2⌉ avec K catégories non vides, ou le palier manuel s'il est réglé. Le texte de la jauge le dit. Changer `points_par_joueur` ou `categorie_vide` dans `config/regles.yaml`, puis redéployer, change le calcul **sans modifier le code** (EX-109).
17. Les bonus individuels d'un actif et les bonus collectifs s'ajoutent au score. Un bonus annulé ne compte plus. Les bonus ne changent pas le palier.
18. Le compteur « 7/12 » et « Qui ne l'a pas fait ? » ne comptent que les actifs, et sont cohérents entre eux pour chaque élément (propriété testée).

**Fiches et filtres**
19. La liste des grimpeurs ne trie jamais par score. Les exclus n'y figurent pas, sauf pour un admin.
20. La fiche montre les 4 catégories, les points, les bonus et l'avancement pour l'étage ouvert et chaque étage terminé.
21. Le filtre par élément affiche « Pas encore fait » et « Déjà fait, ils peuvent accompagner », conformes au calcul.

**Admin**
22. Coller des mentions `<@…>` ajoute les identifiants à la liste officielle, sans doublon.
23. Geler et réintégrer modifient le palier immédiatement. L'écran annonce l'effet (« Palier 24 → 22 ») avant confirmation. La ligne d'un grimpeur gelé montre aussi le moins avancé des actifs.
24. Exclure demande un motif et une confirmation. C'est réversible.
25. Ajouter et annuler un bonus (individuel ou collectif) fonctionnent, avec un motif obligatoire et des points entre −10 et +10, non nuls.
26. Revue d'étage : changer la nature d'une quête (motif obligatoire, origine `admin`), masquer ou démasquer un donjon, une case ou une quête, corriger un libellé, **ajouter un donjon** depuis la liste des donjons aspirés (T-03), régler le nom, l'image d'ambiance et le cap (T-04, T-28). Ces choix **survivent à une reconstruction** de l'étage. La source des succès de chaque donjon (Duffus ou DofusDB) est affichée (T-02).
27. Avant d'ouvrir, l'admin voit le **détail par grimpeur** (catégories, points, bonus, dernière activité, EX-83). **Ouvrir le prochain étage** n'est actif que si `peut_ouvrir` est vrai. Sinon, le bouton affiche les raisons. Forcer exige un motif. L'ouverture fige le bilan, passe l'étage précédent à `termine` et fait apparaître le nouvel étage. Deux admins qui ouvrent en même temps produisent **une seule** ouverture (l'autre reçoit un message clair).
28. Toute écriture d'admin et toute coche apparaissent dans *Admin → Journal* avec l'auteur, la date et les détails.
29. Si le salon d'annonces est configuré, l'ouverture poste le message. S'il ne l'est pas, rien ne se passe et rien n'échoue.

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
38. Thème sombre uniquement, rendu conforme à `maquette-v2.html` à 360 et 1440 px, sans défilement horizontal, avec des cases de 44 px de haut au moins.
39. `ruff` passe. La couverture des modules `domaine/` est de **100 %**. Les tests de la base tournent dans la CI (Postgres de service).

### Plan de tests

| Fichier | Contenu |
|---|---|
| `tests/domaine/test_bareme.py` | Chaque catégorie seule ; indépendance (quêtes sans donjons) ; full succès ⇒ donjons ; catégorie vide jamais acquise ; donjon masqué, case masquée, donjon sans case classique visible ; `palier` (2N, ⌈N×K/2⌉ pour K = 0 à 4, manuel, entrées invalides) ; `calculer_jauge` : pauses et exclus exclus, bonus (individuel d'un actif, d'un gelé, collectif, annulé), N = 0. **Propriétés** (hypothesis) : 0 ≤ points ≤ 4 ; cocher ne fait jamais baisser les points ; palier(N, 4) = 2N ; la jauge est la somme des points des actifs plus les bonus. |
| `tests/domaine/test_regles.py` | `config/regles.yaml` absent → défauts ; valeur inconnue → erreur claire au démarrage ; `points_par_joueur: 5/2` exact ; chaque réglage change bien le comportement attendu (`categorie_vide`, `succes_coche_vaincu`, `pause_peut_cocher`, `bonus_*`). `cascade_coche` : succès → classique, décoche de la classique → les 4, réglage coupé → rien. |
| `tests/domaine/test_progression.py` | `compteurs` et `qui` cohérents (propriété : pour tout élément, compteur + len(qui(pas fait)) = nombre d'actifs) ; `avancement` ; `moins_avance` : égalités départagées par le pseudo, aucun actif. |
| `tests/domaine/test_ouverture.py` | Chaque raison de refus ; ok exactement à la date plancher ; pas de prochain étage ; `bilan_etage` forcé sans motif refusé. |
| `tests/domaine/test_visibilite.py` | Les scellés ne sortent jamais pour un non-admin ; tri ; `etage_cochable` ; `peut_modifier_coches`. |
| `tests/domaine/test_nature.py` | `quetes_obligatoires` sur des critères réels : `Qf=1462&PL>39` → {1462}, la quête 275 avec son « OU » → ∅, parenthèses imbriquées, critère vide ; `fermeture` avec cycle et diamant ; `classer` : priorité admin > Duffus > repli, Dofus non retenu ignoré, tri des Dofus. Données réelles : la fermeture de l'Émeraude sur les réponses enregistrées donne 15 quêtes. |
| `tests/domaine/test_textes.py` | Dates en heure de Paris (heure d'hiver), pseudos, extraction des mentions. |
| `tests/db/test_depot.py` (Postgres) | Contraintes (coche en double, une seule case classique, un seul étage ouvert, `ON DELETE RESTRICT` sur un élément coché, pseudo sans tenir compte de la casse) ; `cocher` idempotent ; `creer_grimpeur` (pas sur la liste, déjà inscrit) ; **concurrence** : 20 coches simultanées du même élément donnent une seule ligne, deux `ouvrir_etage` simultanés donnent une seule ouverture ; journal écrit dans la même transaction ; sessions expirées. |
| `tests/duffus/test_aspirer.py` | Faux transport : pagination par `Range`, débit (horloge simulée, au plus 1 req/s), `User-Agent`, arrêt sur 401, 403 et 404, `Retry-After` sur 429 (3 essais), colonne manquante, extraits stables (deux exécutions donnent les mêmes octets), rapport de différences. |
| `tests/contenu/test_construire.py` | À partir des extraits réels de `donnees/duffus/` : étage 0 complet ; succès de donjon pris chez Duffus quand ils y sont, sinon chez DofusDB, avec la source notée (T-02) ; donjons proposés par niveau, donjon ajouté par l'admin conservé à la reconstruction (T-03) ; `nettoyer_fiche` sur **toutes** les fiches réelles (aucun `<script>`, `on*=`, `<img>`, lien duffus.fr) ; donjon à 4 ou 6 succès → alerte ; repli DofusDB ; nature forcée conservée ; reconstruction idempotente ; garde-fou de 10 % ; `--a-blanc` n'écrit rien. |
| `tests/web/test_auth.py` | Faux Discord (`MockTransport`) : flux complet, `state` faux, non-membre (404), admin par rôle et par liste supplémentaire, revérification après 10 minutes (horloge injectée), déconnexion et révocation, cookie `__Host-` `Secure` `HttpOnly` `SameSite=Lax`. |
| `tests/web/test_pages.py` | Chaque page pour chaque profil (visiteur, membre sans fiche, grimpeur, gelé, admin) ; brouillard (aucune trace d'un étage scellé : on cherche son nom et son numéro dans le HTML) ; pied de page sur chaque route ; mode teaser (routes permises au lot B, admin et testeur passent). |
| `tests/web/test_api.py` | `POST /api/coches` : tous les codes d'erreur, la forme JSON exacte, coche d'admin pour un autre, `donjon`. |
| `tests/web/test_admin.py` | Chaque action, ses validations et sa ligne de journal ; un non-admin reçoit 403 sur chaque route d'admin (énumération des routes). |
| `tests/qa/test_qa_site.py` | Tests adverses : XSS par pseudo et par libellé de quête, CSRF, `Origin`, identifiants Discord absents des réponses, base vide, étage sans grimpeur, 0 actif. |
| **Manuel** (testeur, puis Marceau) | Parcours complet sur téléphone réel avec un compte Discord de test sur le **serveur de test**. Ouverture d'un étage. Gel et réintégration. Rendu comparé à `maquette-v2.html`. |

### Plan de repli si Duffus résiste (décision au plus tard le 31/10)

Si au 31/10 le schéma Duffus n'est pas exploitable (accès fermé, ou structure trop différente de ce qu'on attend) :
- **étages 0 et 1** : construits à partir de **DofusDB** (§6.7 d'ARCHITECTURE : donjons, succès sans les Compagnons, fermeture des Dofus). Les tranches et la liste des quêtes sont saisies par un admin dans un fichier `config/etages-manuels/etage-N.yaml`. Le lien vers le chapitre Duffus est gardé ;
- l'aspiration Duffus passe au lot C. Le reste du lot B est inchangé, puisque `ContenuEtage` ne sait pas d'où vient le contenu.

---

## Traçabilité des exigences (EXIGENCES.md → lots)

Le détail exigence par exigence, avec la section de spec, est dans **SPEC, annexe A**. En résumé :

| Lot | Exigences couvertes |
|---|---|
| **A** (teaser, 6/11) | EX-30 (calendrier), EX-36 (rien d'autre que le teaser n'est public), EX-61, EX-62 (pied de page), EX-95 à EX-97, EX-101, EX-103 (DA, lore), EX-105, EX-107 (hébergement économe, non lucratif), EX-114, EX-115 (mobile) |
| **B** (cœur, 13/11) | EX-01 à EX-16, EX-23 à EX-32, EX-35 à EX-41, EX-43 à EX-52, EX-59, EX-62 à EX-68, EX-70 à EX-74, EX-77 à EX-85, EX-88, EX-94 (annonce facultative), EX-104, EX-106, EX-109 à EX-113. Points ouverts réglables : T-02 à T-29 (SPEC §8.1). |
| **C** (vie de la tour) | Confort autour d'EX-72 et EX-78 (fil d'activité, suggestions d'entraide), EX-94 (annonces automatiques), T-26 (bouton de réaspiration) |
| **E** (modules Duffus) | EX-53, EX-54, EX-56, EX-57 (archimonstres, avis de recherche, outils, stuffs), EX-60, et EX-55, EX-58 selon la réponse de Shadoaze (SPEC §8.2 Q7) ; T-08, T-25, T-27 |
| Hors site ou abandonnées | EX-17 à EX-22, EX-33, EX-34, EX-42, EX-69, EX-75 (rien à coder), EX-76, EX-86, EX-87, EX-89 à EX-93, EX-98 à EX-100, EX-108 |

## Lot C : la vie de la tour (après le 13/11, objectif fin novembre)

- **Fil d'activité** visible des grimpeurs : les dernières coches et ouvertures, jamais les actions de modération.
- **Annonces automatiques** sur Discord : jauge pleine (salon des admins), étage ouvert. L'appel REST du lot B est réutilisé. Pas de passerelle.
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
- **E3** : stuffs, en liens d'abord (0,5 j), puis intégration (environ 3 j) ;
- **E4** : boîte à outils avec liens et Almanax (1,5 j).

L'encyclopédie et le builder restent des liens. Chaque module réutilise la mécanique des cases, des compteurs et de « qui ne l'a pas fait » du lot B, et l'aspiration Duffus (tables `monsters` et autres).
