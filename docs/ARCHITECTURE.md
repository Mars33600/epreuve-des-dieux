# L'Épreuve des Dieux : architecture

Version 4, 27/10/2026. Ce document dit **comment** on construit ce que décrit `SPEC.md`, et **pourquoi**. Les décisions sont prises. Les alternatives écartées sont notées, pour qu'on puisse y revenir en connaissance de cause.

## Ce qui change en v4

| Avant (v3) | Maintenant (v4) | Pourquoi |
|---|---|---|
| Un seul programme : **bot discord.py** connecté en permanence + site FastAPI en lecture seule. | Un **site FastAPI** seul, avec des pages rendues par le serveur et un peu de JavaScript pour les cases. **Plus de bot connecté en permanence.** | Les joueurs cochent sur le site. Le bot n'a plus de rôle indispensable. |
| Pas de compte sur le site. | **Connexion avec Discord (OAuth2)**, sessions côté serveur, protection CSRF (§8). | Chaque joueur écrit sa propre progression. |
| Import DofusDB depuis un YAML par étage. | **Aspiration polie de la base Supabase de Duffus**, lancée à la main, puis **extraits versionnés** dans le dépôt, puis construction des étages (§6). DofusDB passe en complément et en repli. | Duffus est la source unique, et l'auteur ne peut pas fournir d'export. |
| Domaine : paliers, difficultés, retardataires, contrôles de cap. | Domaine : **barème à 4 catégories**, palier ⌈N × K ÷ 2⌉, progression, filtres, ouverture, **mode du site**, classement principal / secondaire (§4). | Nouveau modèle de points. |
| Règles écrites en dur dans le code. | **`config/regles.yaml`** : tout point encore ouvert avec Shadoaze (EXIGENCES T-nn) se règle sans toucher au code (§4). | EX-109 et arbitrage du chef de projet. |
| IA vision (Claude Haiku) au jalon lancement. | **Retirée** du périmètre des lots A et B. Une validation par screen en option au lot D, en reprenant la conception v3. | Confiance, zéro screen. |
| Machine Fly de 512 Mo, intents Discord, permissions du bot. | Machine Fly de **256 Mo** (sans bot ni Pillow), **nom de domaine**, page **teaser** servie en mode `teaser` (§7). | Calendrier du reveal. |

---

## 1. La stack en bref

| Brique | Choix | Pourquoi, en une ligne |
|---|---|---|
| Langage | **Python 3.12** | Marceau le maîtrise. Domaine, site, aspiration et tests restent dans une seule langue. |
| Site | **FastAPI + gabarits Jinja2 + JavaScript « vanilla »** (un fichier, sans outil de build) | Des pages rendues par le serveur : simples à sécuriser (le serveur décide de ce qui est envoyé, essentiel pour le brouillard de guerre), rapides sur mobile, et sans Node ni bundler. Le JS ne sert qu'aux cases, aux filtres et au compte à rebours. |
| Connexion | **Discord OAuth2**, écrit à la main avec `httpx` (environ 100 lignes) | Pas de mot de passe à gérer, et l'identité est celle du serveur (§8). |
| Sessions | **Table `session` en base** et cookie opaque `__Host-` | Déconnexion réelle, révocation possible, rien de sensible dans le cookie. |
| Base de données | **PostgreSQL chez Supabase** (offre gratuite), schéma dédié `epreuve` | Déjà choisi en v3. Une console web pour corriger une donnée en urgence. |
| Accès aux données | **SQLAlchemy 2 (async) + asyncpg, migrations Alembic** | Déjà en place et testé. |
| Données de jeu | **Duffus** (aspiration ponctuelle) + **DofusDB** (icônes, monstres, repli) | Arbitrage du 27/10 (§6). |
| Hébergement | **Fly.io**, une machine à Paris (`cdg`) + **nom de domaine** | Déjà configuré (`fly.toml`). HTTPS automatique, y compris pour un domaine à nous. |
| Outils | **uv**, **pytest** (+ hypothesis), **ruff** | Déjà en place. |

Dépendances ajoutées : `python-multipart` (formulaires FastAPI) et **`nh3`**, qui filtre par liste blanche le HTML des fiches de quête recopiées de Duffus (§6.5). C'est une bibliothèque Rust maintenue, le successeur recommandé de `bleach`. `discord.py` est **retiré** de l'exécution. Il reste dans l'historique git pour un éventuel lot D.

---

## 2. Schéma des composants

```
  Navigateur du grimpeur (mobile d'abord)
     │  HTTPS (domaine à nous → Fly.io)
     ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Machine Fly.io (Paris) : UN programme Python (uvicorn + FastAPI)     │
│                                                                      │
│  web/securite.py : en-têtes, mode teaser, CSRF, session ──────┐      │
│  web/pages.py   web/api.py   web/admin.py   web/auth.py        │      │
│        │             │            │             │              │      │
│        ▼             ▼            ▼             ▼              │      │
│  ┌──────────────────────────┐   ┌─────────────────────────┐    │      │
│  │ domaine/ (Python pur)     │   │ discord/oauth.py (httpx) │────┼──► discord.com (connexion,
│  │ barème, palier, jauge,    │   │ (connexion seulement)    │    │     rôles ; aucun bot)
│  │ progression, ouverture,   │   └─────────────────────────┘    │      │
│  │ mode du site, nature      │                                  │      │
│  └────────────▲─────────────┘                                  │      │
│               │ objets du domaine                              │      │
│  ┌────────────┴───────────────────────────────────────────┐    │      │
│  │ db/ : dépôt (SQLAlchemy async)                          │◄───┘      │
│  └────────────┬───────────────────────────────────────────┘           │
└───────────────┼───────────────────────────────────────────────────────┘
                │ Postgres (TLS)
                ▼
        Supabase (schéma epreuve)
                ▲
                │ écrit les étages (scellés) après revue
   Poste d'un admin (hors ligne du site) :
   python -m epreuve.duffus aspirer ──HTTPS, ≤ 1 req/s──► base Supabase de Duffus (lecture, clé publique)
        └─► donnees/duffus/AAAA-MM-JJ/*.json (extraits versionnés, revus dans git)
   python -m epreuve.contenu construire ──► DofusDB (repli, icônes) ──► notre base
```

**L'idée directrice : « le serveur décide de tout ce qui est montré ».**
- Le module `domaine/` applique les **règles** (points, palier, ouverture, visibilité des étages). C'est du Python pur, sans base ni réseau, donc facile à tester.
- Les gabarits ne reçoivent **que** des étages ouverts ou terminés. Un étage scellé n'existe pas pour un grimpeur, ni dans le HTML, ni dans le JSON, ni par son adresse.
- Le navigateur n'a jamais le dernier mot : une coche est revalidée côté serveur (session, étage cochable, élément visible).

### Pourquoi plus de bot connecté en permanence

Toute écriture passe maintenant par le site, et l'arbitrage du chef de projet exclut **tout bot**. Un bot connecté à la passerelle Discord n'apporterait que des annonces, au prix d'une connexion permanente, d'intents, d'une boucle asyncio partagée et de tests de faux objets Discord. L'admin annonce donc lui-même l'ouverture d'un étage. **Aucune écriture sur le serveur Discord** (ni bot, ni webhook), à aucun lot, sans demande explicite de Marceau. Le jeton du bot reste dans le `.env` de Marceau pour le bot d'atelier (EX-93), hors du site.

---

## 3. Arborescence du dépôt (cible du lot B)

```
epreuve-des-dieux/
├── pyproject.toml, uv.lock, Dockerfile, fly.toml, alembic.ini, .env.example
├── migrations/versions/0001_initial.py   # RÉÉCRITE en v4 (aucune donnée de production n'existe)
├── config/
│   ├── regles.yaml          # règles réglables sans code (SPEC §8.1) : multiplicateur du palier, catégorie vide,
│   │                        #   coches (succès ⇒ vaincu, pause), fiche, inscription, verrouillage des modules (bonus : lot C)
│   ├── etages.yaml          # étage ↔ tranche Duffus, cap, nom, image, dates (étage 0 : 30/10 et 13/11) (T-04, T-28)
│   └── dofus.yaml           # Dofus retenus pour « principale » (SPEC §8.2 Q4) + natures forcées
├── donnees/duffus/AAAA-MM-JJ/   # extraits versionnés de l'aspiration (§6)
├── src/epreuve/
│   ├── main.py              # uvicorn seul (plus de bot)
│   ├── config.py            # pydantic-settings
│   ├── domaine/             # Python pur : n'importe RIEN d'autre du projet
│   │   ├── modeles.py       # dataclasses figées : Etage, Donjon, CaseSucces, Quete, Grimpeur…
│   │   ├── fiche.py         # FicheQuete et masquer_prerequis_scelles (SPEC §4.4 bis)
│   │   ├── classes.py       # GARDÉ : les 19 classes, repartition_classes()
│   │   ├── bareme.py        # catégories, points, palier, jauge
│   │   ├── progression.py   # avancement, compteurs « 7/12 », qui, qui_categorie, moins_avance
│   │   ├── ouverture.py     # peut_ouvrir(), bilan_etage()
│   │   ├── visibilite.py    # étages visibles, étage cochable
│   │   ├── mode_site.py     # teaser / complet (lot A)
│   │   ├── nature.py        # principal / secondaire : fermeture des prérequis, critères DofusDB
│   │   └── textes.py        # liste_francaise, formats de dates et de nombres (repris de modeles.py)
│   ├── db/
│   │   ├── tables.py, session.py (GARDÉ), depot.py
│   ├── duffus/              # aspiration (lot B)
│   │   ├── client.py        # lecteur PostgREST poli (débit, pagination, User-Agent)
│   │   ├── schema.py        # modèles pydantic des tables lues (colonnes exigées)
│   │   └── aspirer.py       # CLI : relevé du schéma, aspiration, rapport de différences
│   ├── dofusdb/
│   │   ├── client.py        # GARDÉ et étendu (quêtes, objets, succès)
│   │   └── repli.py         # 5 succès d'un donjon, fermeture d'un Dofus (SPEC §6.3)
│   ├── contenu/
│   │   ├── construire.py    # extrait Duffus (+ repli) → EtagePrepare, alertes
│   │   ├── ecrire.py        # EtagePrepare → base (rejouable, garde-fous)
│   │   └── __main__.py      # CLI : python -m epreuve.contenu construire --etage N [--a-blanc]
│   ├── discord/
│   │   └── oauth.py         # échange du code, /users/@me, membre du serveur (aucun bot)
│   └── web/
│       ├── app.py           # creer_app() : assemblage (GARDÉ dans l'esprit)
│       ├── securite.py      # en-têtes, middleware du mode teaser, CSRF
│       ├── auth.py          # /connexion, /auth/discord/retour, /deconnexion, dépendances
│       ├── pages.py         # /, /etages/{n}, /grimpeurs, /grimpeurs/{id}, /inscription
│       ├── api.py           # POST /api/coches, GET /api/etages/{n}/manque
│       ├── admin.py         # /admin/…
│       ├── demo.py          # jeu de démonstration sans base (GARDÉ dans l'esprit)
│       ├── templates/       # base.html, teaser.html, tour.html, etage.html, …, admin/*.html
│       └── static/          # style.css, app.js, teaser/teaser.{css,js}, fonts/*.woff2
└── tests/ domaine/ db/ web/ duffus/ dofusdb/ contenu/ donnees/
```

**La règle de dépendance**, inchangée : `domaine/` n'importe rien d'autre du projet. `db/`, `web/`, `contenu/`, `duffus/` et `dofusdb/` importent `domaine/`, jamais l'inverse. C'est ce qui rend les règles testables sans base ni réseau, et c'est la première chose que le relecteur vérifie.

---

## 4. Le domaine : interfaces centrales

Les signatures exactes sont **figées dans `LOTS.md`** (lot B), qui fait foi en cas d'écart. Le principe :

- **Une photographie** : `ContenuEtage(etage, donjons, cases, quetes)` est le contenu **visible** d'un étage (sans les éléments masqués), et `Coches(grimpeur_id, cases, quetes)` l'ensemble de ce qu'un grimpeur a coché. Tout calcul part de ces deux objets.
- **Le barème** (`bareme.py`) :
  - `categories_grimpeur(contenu, coches) -> dict[Categorie, EtatCategorie]` donne pour chaque catégorie faits / total / acquise / vide ;
  - `points_grimpeur(contenu, coches, regles) -> int`, de 0 à 4 ;
  - `palier(nb_actifs, nb_categories, regles, palier_manuel) -> int` vaut ⌈ m × N × K ÷ 4 ⌉, avec m = `regles.points_par_joueur` (2 par défaut), ou le palier manuel.
- **Les règles** : `Regles` est une dataclass figée, lue depuis `config/regles.yaml` au démarrage et validée par pydantic, puis **passée en paramètre** aux fonctions du domaine. Le domaine ne lit jamais de fichier : il reste pur et testable avec n'importe quelle combinaison de règles.

  Pourquoi pas de nombres à virgule : `0,75 × 24` peut donner 18,000000000000004, et l'arrondi au-dessus donnerait alors 19 (le piège déjà noté en v3). On calcule avec `fractions.Fraction`, qui est exacte : m peut valoir 2 ou 5/2 sans erreur d'arrondi, et `math.ceil` d'une fraction est exact.
- **La jauge** : `calculer_jauge(contenu, grimpeurs, coches_par_grimpeur, regles) -> EtatJauge` donne le score, le palier, K, les actifs, les pauses, le détail par catégorie, `pleine` et `maximum`. Les bonus viendront au lot C. L'ouverture, qui dépend aussi de la date, est décidée par `ouverture.peut_ouvrir`. Elle s'appuie sur `points_grimpeur`. **Une seule fonction** alimente la page de l'étage, la tour, la fiche et l'admin (SPEC §5.4).
- **La progression** (`progression.py`) : `compteurs(contenu, grimpeurs, coches) -> dict[ElementRef, int]` pour les « 7/12 », `qui(element, grimpeurs, coches, fait)` et `qui_categorie(contenu, categorie, grimpeurs, coches, fait)` pour « qui ne l'a pas fait ? », `avancement(contenu, coches) -> tuple[int, int]` et `moins_avance(contenu, grimpeurs, coches, regles) -> Grimpeur | None`.
- **L'ouverture** (`ouverture.py`) : `peut_ouvrir(jauge, etage, prochain, maintenant) -> Decision(ok, raisons)` et `bilan_etage(jauge, maintenant, force, motif) -> Bilan`.
- **La visibilité** (`visibilite.py`) : `etages_visibles(etages, est_admin) -> list[Etage]`, `etage_cochable(etage) -> bool` et `peut_modifier_coches(acteur, est_admin, cible) -> bool`. Les gabarits ne reçoivent que le résultat de `etages_visibles`.
- **Le mode du site** (`mode_site.py`, lot A) : `mode_effectif(reglage, ouvert_le, maintenant) -> "teaser" | "ouvert"` et `voit_site_complet(mode, est_admin) -> bool` (le paramètre `est_testeur` du lot A est retiré en tête du lot B : aucun joueur avant le 13/11).
- **La nature** (`nature.py`) :
  - `quetes_obligatoires(critere: str) -> frozenset[int]` analyse un `startCriterion` DofusDB et ne garde que les « ET » ;
  - `fermeture(racines, prerequis) -> frozenset[int]` donne tous les prérequis, directs ou indirects ;
  - `classer(quetes, guides_duffus, guides_repli, dofus_retenus, forcees) -> dict[int, Classement]` (nature, origine, Dofus visés).

  Ce sont des fonctions pures, testées sur des graphes fabriqués et sur les vraies réponses enregistrées.

`classes.py` est **gardé tel quel** (19 classes, `repartition_classes`). La dataclass `Grimpeur` perd `difficulte` et gagne `discord_user_id` et `niveau_declare`.

---

## 5. Base de données

PostgreSQL chez Supabase, **schéma dédié `epreuve`**, hors de l'API REST automatique de Supabase, avec *Row Level Security* activée sans règle comme ceinture de sécurité. Rien ne change sur ces points depuis la v3. La migration `0001_initial.py` est **réécrite** : aucune base de production n'a encore été créée (`DATABASE_URL` est vide dans `.env`), donc pas de données à migrer.

| Table | Colonnes (type) | Contraintes |
|---|---|---|
| `etage` | id serial, numero int, nom text, niveau_min int, niveau_max int, level_cap int, statut text (scelle/ouvert/termine), ouvert_le timestamptz null, date_plancher_suivant timestamptz null, palier_manuel int null, duffus_tranche_id text null, ambiance_url text null, alertes jsonb (dernière construction), maj_le timestamptz | numero unique. **Au plus un étage `ouvert`** (index unique partiel). CHECK palier_manuel ≥ 1. Aucune colonne de lien vers duffus.fr (EX-70). |
| `donjon` | id, etage_id, nom, niveau int null, ordre int, bloc text null, duffus_id text null, dofusdb_id int null, origine text (propose/admin, T-03), succes_source text (duffus/dofusdb, T-02), masque bool | (etage_id, duffus_id) unique quand non nul |
| `case_succes` | id, donjon_id, ordre int (1 à n), nom, condition text, est_classique bool, duffus_id text null, masquee bool | (donjon_id, ordre) unique. **Une seule case classique par donjon** (index unique partiel). |
| `quete` | id, etage_id, nom, niveau int null, bloc text, ordre int, nature text (principale/secondaire), nature_origine text (duffus/dofusdb/admin), nature_motif text null, dofus text[], jusqu_ou text null, a_lier text null, duffus_id text null, dofusdb_id int null, masquee bool | (etage_id, duffus_id) unique quand non nul |
| `liste_officielle` | discord_user_id bigint PK, statut_initial text, ajoute_par bigint, ajoute_le timestamptz | — |
| `grimpeur` | id, discord_user_id bigint, nom_discord text (mis à jour à chaque connexion, T-20), pseudo_ig text, classe text null (facultative, T-20), statut text (actif/pause/exclu), niveau_declare int null, inscrit_le timestamptz | discord_user_id unique. pseudo unique sans tenir compte de la casse (`lower(pseudo_ig)`). CHECK classe ∈ 19 classes, CHECK niveau entre 1 et 200. |
| `coche_case` | grimpeur_id, case_id, cochee_le timestamptz, cochee_par bigint | **PK (grimpeur_id, case_id)** |
| `coche_quete` | grimpeur_id, quete_id, cochee_le, cochee_par | **PK (grimpeur_id, quete_id)** |
| `fiche_quete` | quete_id PK, source text (duffus / duffus+dofusdb / dofusdb), contenu jsonb (la `FicheQuete` sérialisée : étapes au HTML nettoyé par nh3, objets, monstres, positions, prérequis, succès lié, récompenses, « à lier ») | contenu validé par pydantic à l'écriture et à la lecture |
| *(lot C)* `bonus` | id, etage_id, grimpeur_id null, points int, motif text, par bigint, le timestamptz, annule_le timestamptz null, annule_par bigint null | CHECK points entre −10 et 10 et ≠ 0. motif non vide. |
| `bilan_etage` | etage_id PK, fige_le, actifs int, palier int, score int, detail jsonb, force bool, motif text null | — |
| `session` | id_hache bytea PK (SHA-256 du jeton du cookie), discord_user_id bigint, nom_discord text, est_admin bool, roles_verifies_le timestamptz, cree_le, expire_le, jeton_oauth text, csrf text | index sur expire_le. Purge des sessions expirées au démarrage et une fois par jour. |
| `journal` | id, horodatage, acteur_discord_id bigint null, type text, grimpeur_id null, etage_id null, details jsonb, public bool | index sur horodatage décroissant. `public` est faux pour la modération : coche d'un admin sur la fiche d'un autre (avec son motif, T-15), gel, exclusion. |

Choix notables :
- **Deux tables de coches plutôt qu'une table générique** (« type + id ») : chaque coche a une vraie clé étrangère, et la base refuse une coche vers une case qui n'existe pas. Le prix, c'est deux requêtes au lieu d'une : négligeable.
- **Une coche est une ligne qu'on supprime au décochage** (`INSERT … ON CONFLICT DO NOTHING` pour cocher, `DELETE` pour décocher). L'opération est idempotente : un double toucher ne crée pas deux lignes et ne casse rien. Le journal garde l'historique.
- **On masque, on ne supprime pas** un élément de contenu. `ON DELETE RESTRICT` sur les clés étrangères des coches : la base elle-même empêche de supprimer un élément coché.
- **Textes contrôlés par CHECK plutôt que types ENUM** (inchangé depuis la v3) : plus simples à faire évoluer.
- **Sessions en base, cookie opaque** (§8) : le cookie ne contient qu'un jeton aléatoire de 256 bits. La base ne stocke que son empreinte. Une fuite de la base ne permet donc pas de se faire passer pour quelqu'un.
- **Performances** : 30 grimpeurs × environ 300 éléments par étage, c'est au plus 9 000 coches par étage. On charge l'étage et toutes ses coches en deux requêtes, et on calcule en Python. Pas de cache au lot B.
- **Connexion** : pooler Supabase en **mode session** (port 5432), compatible avec les requêtes préparées d'asyncpg (inchangé).
- **Mise en veille** : Supabase met en pause un projet gratuit après 7 jours sans activité. La vérification de santé de Fly appelle `/sante` toutes les 30 secondes, et `/sante` interroge la base : le projet reste actif. On crée donc le projet avant le 2/11 et on dépose `DATABASE_URL` **tout de suite** sur Fly (PREREQUIS E.1) : pendant le lot A, `/sante` l'interroge déjà, et le projet ne s'endort pas. Le schéma, lui, n'est créé qu'au lot B (migration).
- **Sauvegardes** : action GitHub nocturne `pg_dump` **chiffrée avec age**, gardée 30 jours (version de la branche `wip/corrections-revue`, à reprendre telle quelle).

---

## 6. Données de jeu : aspiration de Duffus, DofusDB en complément

### 6.1 Le principe en trois étapes séparées

```
(1) ASPIRER  ──►  (2) REVOIR dans git  ──►  (3) CONSTRUIRE l'étage (scellé)  ──►  revue admin sur le site  ──►  ouverture
 base Duffus        donnees/duffus/            notre base Postgres
 (lecture seule)    AAAA-MM-JJ/*.json
```

Pourquoi trois étapes et non un seul import :
- **(1) ne touche que Duffus, et une seule fois.** Une aspiration donne une copie datée. Tout le reste (tests, constructions, corrections) travaille sur cette copie, **sans jamais réinterroger duffus.fr**.
- **(2) rend les changements visibles.** Les extraits sont des fichiers JSON triés et mis en forme de façon stable. Un `git diff` entre deux aspirations montre exactement ce que l'auteur a modifié dans son guide (une quête ajoutée, un succès renommé) avant que ça n'atteigne les joueurs.
- **(3) est rejouable et sans réseau** (sauf le repli DofusDB, lui aussi mis en cache). On peut reconstruire un étage autant de fois qu'on veut.

### 6.2 Comment on lit la base de Duffus

**Le constat**, établi par le coordinateur : duffus.fr est une application React qui lit ses données directement dans une base **Supabase**, avec une **clé publique** (la clé « anon », présente dans le code JavaScript livré à tout visiteur). Les tables repérées sont `guide_ranges`, `quest_list`, `quest_pages`, `dungeon_pages`, `achievements`, `achievement_objectives`, `monsters` et `dofus_list`, parmi d'autres. Une base Supabase s'interroge par **PostgREST**, une API REST générée automatiquement :

```
GET https://<projet-duffus>.supabase.co/rest/v1/guide_ranges?select=*&order=id.asc
    apikey: <clé anon publique>
    Authorization: Bearer <clé anon publique>
    Range: 0-999
    User-Agent: EpreuveDesDieux-aspiration/1.0 (projet non lucratif, accord de l'auteur ; contact : …)
```

**On ne lit que ce que la clé publique permet déjà à n'importe quel visiteur de son site**, avec **l'accord explicite de l'auteur**. On ne contourne aucune protection et on n'essaie aucune autre clé.

**Les règles de politesse**, codées dans `duffus/client.py` et non laissées à la discipline :

| Règle | Valeur | Pourquoi |
|---|---|---|
| Déclenchement | **À la main**, par un admin, en ligne de commande (lot B) | Jamais automatique, jamais pendant la navigation d'un joueur |
| Débit | **1 requête par seconde au plus**, une seule à la fois | Négligeable pour son projet Supabase, dont l'offre gratuite a ses propres quotas |
| Pagination | Pages de 1 000 lignes (en-tête `Range`), tri par clé pour un résultat stable | Le maximum par défaut de PostgREST chez Supabase |
| Colonnes | `select=` limité aux **colonnes utiles** une fois le schéma relevé | Moins de transfert. On ne récupère pas le texte long des fiches. |
| Identification | `User-Agent` explicite avec un contact | L'auteur sait qui l'appelle et peut nous joindre |
| Erreurs | Arrêt immédiat sur 401, 403 ou 404 ; sur 429 ou 5xx, attente de `Retry-After` (30 s par défaut), puis **3 essais au plus** | Ne jamais insister |
| Fréquence | Une aspiration avant la préparation des étages, puis **au plus une par semaine**, ou à la demande de l'auteur | Volume total estimé : quelques dizaines de requêtes par aspiration |

**La clé et l'adresse** sont des réglages (`DUFFUS_SUPABASE_URL`, `DUFFUS_SUPABASE_CLE`) dans le `.env` de l'admin qui aspire. Elles ne sont **pas** commitées. La clé est publique, mais elle appartient à l'auteur, et il doit pouvoir la changer sans que notre dépôt l'expose.

### 6.3 Le relevé du schéma : première tâche du lot B

On connaît les **noms** des tables, pas leurs **colonnes** ni leurs liens. La commande `python -m epreuve.duffus releve` :
1. demande l'**OpenAPI** que PostgREST publie à la racine `/rest/v1/` (la liste des tables et colonnes visibles avec la clé) ;
2. si c'est fermé, lit **une seule ligne** de chaque table connue (`limit=1`) ;
3. écrit le résultat dans `donnees/duffus/schema-AAAA-MM-JJ.json`.

À partir de ce relevé, l'architecte fige dans `duffus/schema.py` les **modèles pydantic** des tables utiles, avec les seules colonnes dont on a besoin, et le dev écrit la transformation vers notre modèle (§6.5). C'est le point de risque principal du lot B (voir §6.6 et le plan de repli de `LOTS.md`).

### 6.4 L'aspiration

`python -m epreuve.duffus aspirer [--tables t1,t2] [--a-blanc]` :
1. lit chaque table utile, page par page, avec les règles du §6.2 ;
2. **valide chaque ligne** contre son modèle pydantic : une colonne exigée absente ou d'un mauvais type arrête tout, avec un message clair (« `quest_list.range_id` manquant : le schéma de Duffus a changé, refaire le relevé ») ;
3. écrit `donnees/duffus/AAAA-MM-JJ/<table>.json`, trié par clé, une ligne par enregistrement, avec seulement les colonnes retenues ;
4. affiche un **rapport de différences** avec l'aspiration précédente : lignes ajoutées, retirées et modifiées par table, plus la liste des étages **ouverts** touchés ;
5. `--a-blanc` affiche le rapport sans rien écrire.

Les extraits sont **commités** dans le dépôt privé (avec l'accord de l'auteur). Ils servent aussi de **données de test réelles**.

### 6.5 La construction d'un étage

`python -m epreuve.contenu construire --etage N [--aspiration AAAA-MM-JJ] [--a-blanc] [--forcer]` :
1. **Tranche** : `config/etages.yaml` dit quelle tranche de `guide_ranges` correspond à l'étage N, avec le cap, le nom, l'image d'ambiance et les dates (T-04, T-28). Par défaut, l'étage N est la N-ième tranche et le cap est sa borne haute. Pour l'étage 0 : `ouvert_le` le 30/10 à 17:00 et `date_plancher_suivant` le 13/11 à 17:00.
2. **Donjons proposés** (`dungeon_pages`) : ceux dont le niveau est dans la tranche, avec l'origine `propose`. L'admin valide la liste dans la revue, retire ou **ajoute** un donjon pris dans la liste complète des donjons aspirés, avec l'origine `admin` (T-03). Une reconstruction **conserve** ces choix.
3. **Succès de chaque donjon** (T-02) : pris dans `achievements` / `achievement_objectives` de Duffus **si ces tables en donnent pour ce donjon**, sinon dans DofusDB (`achievements` du donjon, sans la catégorie Compagnons 142). La source retenue est notée (`succes_source`) et affichée dans la revue. La case « classique » est repérée par une règle à fixer après le relevé (par exemple, le succès qui porte le nom du donjon, sans condition de défi). Un donjon qui n'a pas 5 succès donne une **alerte**.
4. **Quêtes de la tranche** (`quest_list`), avec le bloc, l'ordre, « jusqu'où », « à lier » et la **fiche** (`quest_pages` et les tables qu'elle référence) **recopiée et structurée** en `FicheQuete` (SPEC §4.4 bis, EX-52, EX-70) : étapes et objectifs, objets, monstres, positions, prérequis, succès lié, récompenses. DofusDB complète les champs absents, avec la source notée. Les quêtes sans fiche Duffus sont listées dans le rapport, et la construction s'arrête au-delà de 5 % sans `--forcer`. Le HTML de la fiche passe par `nh3` avec une liste blanche de balises de mise en forme (titres, paragraphes, listes, gras, italique). Scripts, styles, attributs d'événement et **images** sont retirés : afficher une image de Duffus ferait appeler son site pendant la navigation. Les **liens vers duffus.fr sont retirés**, ou réécrits vers notre fiche s'ils visent une quête d'un étage ouvert. Le résultat est relu par un test sur toutes les fiches réelles aspirées.
5. **Nature** (`nature.classer`) à partir des guides par Dofus (`dofus_list` et ses quêtes et prérequis), de `config/dofus.yaml` et des natures déjà forcées par un admin en base, qui **priment toujours**. Pour un Dofus sans guide Duffus, le **repli DofusDB** (§6.7) s'applique, marqué comme tel.
6. **Écriture** (`contenu/ecrire.py`), dans une transaction :
   - un étage nouveau est créé `scelle`, sauf l'étage 0, créé `ouvert` ;
   - un étage existant est **mis à jour par identifiant Duffus** : on ajoute ce qui est nouveau, on met à jour les libellés, et on **masque** ce qui a disparu au lieu de le supprimer ;
   - **garde-fou** : sur un étage **ouvert**, si plus de 10 % des éléments disparaîtraient ou changeraient de nature, l'écriture est refusée sans `--forcer`, et le rapport l'explique ;
   - chaque changement d'un étage existant passe au **journal** (type `contenu_maj`, avant et après), repris de la branche `wip/corrections-revue`.

### 6.6 Limites et fragilité, dites franchement

| Risque | Ce qui se passe | Parade |
|---|---|---|
| **L'auteur change son schéma** (colonne renommée, table scindée) | L'aspiration s'arrête à la validation pydantic, avec un message clair. **Le site n'est pas touché** : il vit sur la dernière copie. | Refaire le relevé (§6.3), adapter `duffus/schema.py` et la transformation. Demander à l'auteur de prévenir avant un changement. |
| **L'auteur renumérote ses identifiants** | Les éléments seraient vus comme « disparus » et « nouveaux ». | Nos coches pointent vers **nos** identifiants, jamais vers ceux de Duffus. Le garde-fou de 10 % bloque une mise à jour massive d'un étage ouvert. Rapprochement par nom et niveau en dernier recours, revu par l'admin. |
| **La clé publique change, ou l'accès est fermé** (règles RLS, quotas) | Erreur 401 ou 403 : arrêt immédiat. | La dernière copie reste valable. On reprend contact avec l'auteur. Pour les étages pas encore préparés, repli DofusDB (§6.7). |
| **L'auteur modifie son guide** en cours d'événement | Rien ne change chez nous tant qu'on n'a pas réaspiré. | C'est voulu : un étage ouvert ne bouge pas sous les pieds des joueurs. On réaspire avant de préparer les étages suivants, et le rapport montre les écarts. |
| **Données incomplètes** (donjon sans succès, Dofus sans guide) | Alerte à la construction. | Repli DofusDB marqué, puis décision de l'admin dans la revue. |
| **Fiches de quête recopiées** | La copie vieillit si l'auteur corrige une fiche. Un HTML inattendu pourrait contenir du code. | Rapport de différences à chaque aspiration ; filtrage `nh3` par liste blanche, testé sur toutes les fiches réelles ; CSP stricte en dernière ceinture. |
| **Dépendance à un tiers** | Notre contenu est celui d'un projet amateur qui peut s'arrêter. | Les extraits versionnés sont une copie autonome. Le site n'a jamais besoin de duffus.fr pour fonctionner. |

Pourquoi ne pas lire Duffus « en direct » pendant la navigation : ce serait plus simple et toujours à jour, mais chaque visite d'un de nos joueurs deviendrait une requête chez lui (impoli et coûteux pour son quota), notre site tomberait avec le sien, et un changement de son côté changerait un étage ouvert sans revue. **Écarté.**

### 6.7 DofusDB : complément et repli

api.dofusdb.fr, publique et sans clé, déjà utilisée en v3 (`dofusdb/client.py` est gardé) :
- **Complément** : icônes (`img`) des Dofus, monstres et objets, détails des monstres. Elles sont lues à la construction et copiées en base (adresse de l'image), jamais pendant la navigation.
- **Repli des succès d'un donjon** : `GET /dungeons/{id}` → `achievements`, sans la catégorie 142 (*Compagnons*). Vérifié le 27/10 sur les donjons 34 et 13.
- **Repli de la nature**, vérifié le 27/10/2026 :
  - `GET /items?typeId=23` donne les 34 Dofus ;
  - chaque Dofus a `questsThatReward` ou `achievementsThatReward` ;
  - `GET /achievements/{id}` → `objectives[].criterion` contient `Qf=<quête>` ou `OA=<succès>`, à suivre récursivement ;
  - `GET /quests/{id}` → `startCriterion`, analysé par `nature.quetes_obligatoires`, qui ne garde que les « ET ». **Ne pas utiliser `need.quests`**, qui met à plat les « OU » (quête 275).

  Essais réels : 15 quêtes pour l'Émeraude, 74 pour l'Argenté, aucune donnée pour Ocre, Kaliptus, Cacao, Verdoyant, Dom de Pin et Jyfus.
- Les réponses DofusDB utilisées sont mises en cache dans `donnees/dofusdb/` (même principe que Duffus) et servent de données de test.

---

## 7. Le mode du site et la page teaser (lot A)

### 7.1 Le réglage

| Variable | Valeurs | Défaut |
|---|---|---|
| `SITE_MODE` | `auto`, `teaser` ou `ouvert` | `auto` |
| `SITE_OUVERT_LE` | date ISO avec fuseau | `2026-11-13T17:00:00+01:00` |
| `TEASER_LIEN_ENTRER` | adresse du bouton « Entrer dans la tour » | vide : bouton masqué ; **renseignée le jour J** (arbitrage du chef de projet) |

`mode_effectif(reglage, ouvert_le, maintenant)` donne `teaser` si le réglage est `teaser`, ou s'il est `auto` avant `SITE_OUVERT_LE`. Sinon, il donne `ouvert`. Pourquoi `auto` par défaut : la bascule tombe un vendredi à 17 h, et elle ne doit pas dépendre de la présence de Marceau devant son ordinateur. `teaser` et `ouvert` permettent de reprendre la main en une commande (`fly secrets set SITE_MODE=teaser`), qui redémarre la machine en quelques secondes.

### 7.2 Le middleware

`web/securite.py` contient un middleware qui, en mode `teaser`, laisse passer seulement :
- `/` (le teaser) et `/sante` ;
- `/static/…` ;
- au lot B, `/connexion`, `/auth/discord/retour` et `/deconnexion`, pour que les admins puissent se connecter. Un joueur connecté revoit le teaser, et `/inscription` n'est **pas** permise : aucune fiche n'est créée avant le 13/11 ;
- **toutes** les pages pour un **admin** connecté (recette). Il n'y a pas de rôle de testeur.

Toute autre requête reçoit une redirection 303 vers `/`, et les requêtes `/api/` reçoivent un 404. Le test de ce middleware énumère **toutes les routes déclarées** de l'application : une route ajoutée plus tard sans y penser est donc couverte d'office.

### 7.3 L'intégration du travail du designer

`docs/design/teaser.html` est une page autonome (HTML, CSS et JS en ligne, polices Google). `docs/design/DA.md` et `maquette-v2.html` **font foi pour le visuel** de tout le site. Au lot A, le dev transpose le teaser **sans toucher au rendu** :
- le CSS va dans `static/teaser/teaser.css` et le JS dans `static/teaser/teaser.js`. Ce découpage permet une politique de sécurité de contenu (CSP) stricte, `script-src 'self'`, sans script en ligne ;
- les constantes du JS, `OUVERTURE` et `LIEN_SITE`, ne sont plus écrites en dur : le gabarit les pose en attributs, `<body data-ouverture="2026-11-13T17:00:00+01:00" data-lien-site="…">`, à partir de `SITE_OUVERT_LE` et de `TEASER_LIEN_ENTRER`. Comme dans le code du designer, le bouton n'apparaît qu'après la fin du compte à rebours **et** si le lien est renseigné ;
- les **polices** de la DA (Alegreya SC, Alegreya Sans, IBM Plex Mono, licence libre SIL OFL) sont **auto-hébergées** dans `static/fonts/` au lieu d'être chargées chez Google. Le rendu est identique, mais on n'envoie pas l'adresse IP des visiteurs à Google et la CSP reste `'self'` ;
- **thème sombre uniquement** (`color-scheme: dark`) sur tout le site, teaser compris, et aucune feuille de style claire. Les décors sont générés (dégradés, canvas, SVG) ou sont des images originales : jamais de capture du jeu ;
- le pied de page ajoute « Merci [Duffus](https://duffus.fr) » ;
- les paramètres d'aperçu du designer (`?etat=ouvert`, `?dans=12`) sont gardés : ils ne révèlent rien ;
- sans JavaScript, la date est écrite en clair dans le HTML.

---

## 8. Connexion avec Discord (OAuth2)

### 8.1 Le choix est validé, avec ses raisons

| Option | Verdict |
|---|---|
| **Discord OAuth2** | ✅ **Retenue.** Tous les participants ont un compte Discord, puisque l'inscription passe par le serveur. Le site ne stocke **aucun mot de passe**. L'identité vérifiée est celle du serveur : on vérifie l'appartenance au serveur et le rôle « Administrateur » directement, sans saisie. La liste officielle est une liste d'identifiants Discord, ce qui rend le rapprochement automatique. |
| Mot de passe propre au site | ❌ Hachage, réinitialisation par e-mail (donc un service d'envoi), support des oublis. Plus de risques et de code pour moins de confort. |
| Lien magique par e-mail | ❌ Il faut collecter des e-mails (une donnée personnelle de plus) et un service d'envoi, et la délivrabilité est capricieuse. |
| Supabase Auth (fournisseur Discord) | ❌ Un second système d'authentification à côté de notre serveur, qui fait de toute façon toutes les écritures. Ça ajoute le client JS Supabase et des règles RLS à écrire. Pas de gain ici. |
| Bibliothèque OAuth (Authlib…) | ❌ Pour un seul fournisseur et un seul flux, 100 lignes avec `httpx` sont plus lisibles, plus faciles à tester (faux transport `httpx.MockTransport`) et plus pédagogiques. |

**Limites acceptées** : si Discord est en panne, personne ne peut **se connecter** (les sessions ouvertes continuent, puisqu'elles durent 7 jours). Chaque joueur doit accepter l'écran d'autorisation une fois.

### 8.2 Le flux

1. `GET /connexion` : le serveur tire un `state` aléatoire (32 octets), le pose dans un cookie `__Host-oauth_state` de courte durée (10 minutes, `Secure`, `HttpOnly`, `SameSite=Lax`) et redirige vers l'adresse ci-dessous. Pas besoin de signer ce cookie : un autre site ne peut ni le lire ni l'écrire, et c'est la **comparaison** entre le cookie et le paramètre renvoyé par Discord qui protège :
   `https://discord.com/oauth2/authorize?response_type=code&client_id=1564210808509038622&scope=identify%20guilds.members.read&redirect_uri=<REDIRECT>&state=<state>&prompt=none`
2. Discord renvoie vers `GET /auth/discord/retour?code=…&state=…`. Le serveur :
   - vérifie que `state` correspond au cookie. Sinon, c'est un refus (protection contre la falsification de requête) ;
   - échange le code : `POST https://discord.com/api/v10/oauth2/token` (formulaire : `grant_type=authorization_code`, `code`, `redirect_uri`, avec `client_id` et `client_secret`). Il reçoit un jeton d'accès valable 7 jours ;
   - `GET /api/v10/users/@me` donne l'identifiant et le nom affiché ;
   - `GET /api/v10/users/@me/guilds/{DISCORD_GUILD_ID}/member` (portée `guilds.members.read`, vérifié dans la documentation Discord le 27/10) donne le membre et ses **rôles**. Une erreur 404 veut dire « pas membre du serveur » : refus ;
   - **admin** ⇔ un des rôles est dans `DISCORD_ADMIN_ROLE_IDS`, ou l'identifiant est dans `ADMINS_SUPPLEMENTAIRES`. Ce dernier est un filet pour Marceau et Shadoaze si le rôle était mal réglé, parce que l'objet membre donne les rôles mais pas les permissions calculées ;
   - crée la **session** en base, avec un jeton aléatoire de 256 bits dans le cookie `__Host-session` (`Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, 7 jours), et ne stocke que son empreinte SHA-256 ;
   - redirige vers `/inscription` s'il n'y a pas de fiche, sinon vers `/`.
3. **Revérification des droits d'admin** : avant toute action d'admin, si `roles_verifies_le` date de plus de 10 minutes, le serveur rappelle `/users/@me/guilds/{id}/member` avec le jeton OAuth stocké dans la session. Si le jeton a expiré ou que le rôle a disparu, la session redevient non-admin. **Aucun bot n'est nécessaire.**
4. `POST /deconnexion` supprime la session en base et révoque le jeton chez Discord (`POST /oauth2/token/revoke`).

Le **jeton OAuth** stocké en base a une portée réduite à la lecture (identité et appartenance au serveur), dure 7 jours et est révoqué à la déconnexion. C'est un compromis assumé, qui évite de dépendre du bot pour revérifier les rôles.

### 8.3 Protection des écritures

- **CSRF** : chaque session a un jeton `csrf` aléatoire. Les formulaires le portent dans un champ caché, et les appels `fetch` dans l'en-tête `X-CSRF-Token`. Le serveur compare en temps constant (`hmac.compare_digest`). En plus, toute requête `POST` dont l'en-tête `Origin` n'est pas le nôtre est refusée. `SameSite=Lax` est une troisième ceinture.
- **Autorisation** : une coche n'est acceptée que pour **soi-même**, sauf pour un admin, qui donne alors un motif (T-15), et seulement sur un élément **visible** d'un étage **ouvert ou terminé**. Un exclu ne coche plus. C'est vérifié côté serveur, quelle que soit la requête.
- **Échappement** : Jinja échappe tout par défaut. Côté JS, uniquement `textContent`, jamais `innerHTML` avec des données (règle déjà établie en v3).

---

## 9. Le site : routes

| Route | Qui | Rôle |
|---|---|---|
| `GET /` | tous | Teaser (mode teaser), sinon accueil (non connecté) ou **tour** (connecté) |
| `GET /connexion`, `GET /auth/discord/retour`, `POST /deconnexion` | tous | §8 |
| `GET/POST /inscription` | membre sur la liste officielle | Création de la fiche |
| `GET /etages/{numero}` | grimpeur | L'onglet de l'étage. **404** si l'étage est scellé (sauf admin). |
| `GET /etages/{numero}/quetes/{id}` | grimpeur | La fiche de quête intégrée : fragment HTML (en-tête `Accept: text/html-fragment` envoyé par `app.js`), affiché en panneau plein écran sur mobile et en panneau latéral sur ordinateur, ou page complète sans JS. Les prérequis scellés sont toujours masqués (`masquer_prerequis_scelles`). 404 si l'étage est scellé. |
| `GET /grimpeurs`, `GET /grimpeurs/{id}` | grimpeur | Liste avec filtre par élément, fiche |
| `POST /grimpeurs/moi` | grimpeur | Modifier son pseudo, sa classe et son niveau |
| `POST /api/coches` | grimpeur | Corps JSON `{type: "case", "quete" ou "donjon", id, cochee, grimpeur_id?, motif?}` (détail et codes d'erreur dans LOTS). Répond avec l'état de la jauge et les compteurs mis à jour. |
| `GET /api/etages/{numero}/manque?type=…&id=…` | grimpeur | « Qui ne l'a pas fait ? », pour un élément ou une catégorie |
| `GET /admin`, `/admin/grimpeurs`, `/admin/etages`, `/admin/etages/{n}`, `/admin/journal` | admin | Pages d'admin |
| `POST /admin/liste`, `/admin/grimpeurs/{id}/statut`, `/admin/grimpeurs/{id}`, `/admin/etages/{n}/palier`, `/admin/etages/{n}/date-plancher`, `/admin/etages/{n}/ouvrir`, `/admin/etages/{n}/reglages` (nom, image, cap), `/admin/etages/{n}/donjons` (ajouter un donjon, T-03), `/admin/quetes/{id}`, `/admin/donjons/{id}`, `/admin/cases/{id}` | admin | Actions, toutes journalisées |
| `GET /sante` | tous | État de la base. Utilisé par Fly. |

« grimpeur » veut dire ici : connecté, avec une fiche qui n'est pas exclue, **ou** admin, même sans fiche (SPEC §4.2).

**En-têtes de sécurité** sur toutes les réponses :
- `Content-Security-Policy: default-src 'self'; img-src 'self' https://api.dofusdb.fr data:; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'` ;
- `X-Robots-Tag: noindex, nofollow` ;
- `Referrer-Policy: strict-origin-when-cross-origin` ;
- `X-Content-Type-Options: nosniff`.

Le pied de page « Merci Duffus » est dans `base.html`, que toutes les pages étendent. Le test le vérifie sur chaque route.

---

## 10. Hébergement, domaine et coût

- **Fly.io**, une machine `shared-cpu-1x` de **256 Mo** à Paris. Sans bot ni Pillow, le programme tient largement dans 256 Mo. On repasse à 512 Mo si les journaux montrent une pression mémoire. `min_machines_running = 1` et `auto_stop_machines = "off"` : pas de démarrage à froid le soir du reveal. Une seule machine suffit : le programme n'a plus de bot à ne pas dupliquer, mais une seule machine garde la purge des sessions simple.
- **Nom de domaine** : acheté chez un registrar (OVHcloud, Gandi ou Porkbun, entre 7 et 12 € par an pour un `.fr` ou un `.com`). On fait pointer le domaine vers Fly avec les enregistrements DNS donnés par `fly ips list`, puis `fly certs add <domaine>` obtient un certificat HTTPS automatiquement. Le domaine en `*.fly.dev` reste un plan B gratuit et immédiat.
- **Le domaine n'est pas un détail du lot B** : l'adresse de retour OAuth (`https://<domaine>/auth/discord/retour`) doit être déclarée chez Discord. En changer plus tard oblige à refaire ce réglage.

| Poste | Coût |
|---|---|
| Fly.io (256 Mo, Paris) | environ 2 à 3 $ par mois |
| Nom de domaine | environ 10 € par an |
| Supabase (offre gratuite) | 0 $ |
| GitHub (dépôt privé, actions) | 0 $ |
| **Total** | **environ 3 à 4 $ par mois**, plus le domaine |

---

## 11. Sécurité : secrets et réglages

| Variable | Secret ? | Où | Lot |
|---|---|---|---|
| `SITE_MODE`, `SITE_OUVERT_LE`, `FUSEAU`, `SITE_URL` | non | `fly.toml` [env] | A |
| `DATABASE_URL` | **oui** | Fly secrets, `.env`, secret GitHub (sauvegarde) | B |
| `DISCORD_CLIENT_ID` (1564210808509038622) | non | `fly.toml` | B |
| `DISCORD_CLIENT_SECRET` | **oui** | Fly secrets, `.env` | B |
| `DISCORD_GUILD_ID`, `DISCORD_ADMIN_ROLE_IDS`, `ADMINS_SUPPLEMENTAIRES` | non | Fly secrets (pour ne pas les publier dans le dépôt) | B |
| `DISCORD_TOKEN` (jeton du bot) | **oui** | `.env` de Marceau seulement (bot d'atelier, EX-93), **jamais sur Fly** | — (aucun bot sur le site) |
| `DUFFUS_SUPABASE_URL`, `DUFFUS_SUPABASE_CLE` | publique, mais appartient à l'auteur | `.env` de l'admin qui aspire, **jamais** sur Fly ni dans le dépôt | B |
| `AGE_RECIPIENT` | clé publique | secret GitHub | B |

Règles inchangées depuis la v3 :
- `.env` est dans `.gitignore` ;
- la configuration masque les secrets (`SecretStr`) ;
- en cas de fuite d'un jeton, on le **réinitialise** dans le portail Discord, puis `fly secrets set` ;
- `gitleaks` tourne en intégration continue.

**Le jeton du bot présent dans `.env`** : le site n'en a pas besoin, puisqu'il n'y a aucun bot. Il ne va pas sur Fly. Moins de secrets en production, c'est moins de risques.

---

## 12. Exploitation

- **Journaux** : sortie standard, lisible avec `fly logs`. Une ligne par action d'admin et par erreur, sans secret ni jeton.
- **Santé** : `GET /sante` renvoie l'état de la base (`ok`, `absente` en mode teaser sans base, ou `erreur`). Fly redémarre la machine si la vérification échoue.
- **Déploiement** : `fly deploy`. Les migrations Alembic passent avant la bascule (`release_command`). Au lot A, sans `DATABASE_URL`, la commande de release est désactivée.
- **Fuseau** : stockage en UTC (`timestamptz`), affichage en `Europe/Paris`.
- **Le soir du départ** (13/11 à 17:00) : en mode `auto`, rien à faire. Marceau vérifie à 17:01 que `/` montre bien l'accueil, et garde `fly secrets set SITE_MODE=teaser` sous la main en cas de souci.
