# L'Épreuve des Dieux : découpage en lots

Version 3, 25/10/2026. Chaque jalon suit le circuit de l'équipe : **architecte** (spec technique) → **PO** (critères d'acceptation) → **dev** → **testeur + relecteur** → **rédacteur** → **recette** par Marceau, et par Shadoaze pour ce qui le concerne.

**Ce qui change en version 3** : les réponses de Shadoaze (`REPONSES-SHADOAZE.md`) remplacent les trois jauges à fractions par **une jauge unique à points** (SPEC §5). Les quêtes deviennent déclaratives, le cap perd sa tolérance automatique, les dates changent et la notion de retardataire apparaît. Le dev avait commencé le jalon bêta sur l'ancien modèle : la section **« Reprise du code déjà écrit »** dit précisément quoi changer, fichier par fichier.

## Principe de calendrier

**Aucune date n'est imposée.** On vise la meilleure qualité, livrée le plus vite possible. Les dates du jeu servent de **repères indicatifs** :

| Repère du jeu | Date (heure de Paris) | Ce qu'il suggère pour l'outil |
|---|---|---|
| Ouverture de l'étage 0 en jeu | vendredi 30/10/2026, 17:00 | Le **jalon bêta** est utile dès cette date : il accompagne la période de mise en place. |
| Premier déblocage possible | vendredi 13/11/2026, 17:00 | Le **jalon lancement** est idéalement prêt avant, pour qu'on puisse ouvrir l'étage 1 par le bot. |

Si un jalon n'est pas prêt à la date repère, rien ne casse. Les admins continuent de valider comme aujourd'hui. Les validations sont saisies ensuite avec le lien du screen, et la date de réalisation est retrouvée à partir de l'identifiant du message Discord, qui encode son horodatage.

| Lot | Jalon | Contenu en une ligne | Repère |
|---|---|---|---|
| **1** | **Bêta** | Registre et retardataires, saisie admin par commande, déclaration des quêtes, site avec la jauge à points et la répartition des classes | dès que possible, idéalement le 30/10 |
| **1** | **Lancement** | Clic droit « Valider ce screen », retour au joueur, ouverture d'étage et seuil, assistance IA | idéalement avant le 13/11 |
| **2** | Confort | Entraide, fiches détaillées, lecture par rôle, étages passés | après le lancement |

Les devs travaillent sur Opus : chaque **jalon est un seul chantier de dev**, sans sous-découpage. Les interfaces figées ci-dessous sont les contrats entre agents. Le dev ne les change pas sans repasser par l'architecte.

---

## Reprise du code déjà écrit (ancien modèle → jauge à points)

À faire **en premier** dans le chantier du jalon bêta. Le domaine passe d'abord, puis la base, puis le reste. Les tests de l'ancien modèle sont réécrits, pas adaptés à la marge.

| Fichier | Ce qui doit changer |
|---|---|
| `src/epreuve/domaine/fractions.py` | **À supprimer.** Il est remplacé par `domaine/seuil.py` : `POINTS_VISES = {"easy": 1, "med": 2, "hard": 3}` et `seuil(maximum, pourcent) -> int` = `(maximum × pourcent + 99) // 100`, avec 0 si le maximum est nul et une erreur si le pourcentage sort de 1 à 100. Le commentaire pédagogique sur les flottants est à garder, avec l'exemple 0,75 × 24. |
| `src/epreuve/domaine/modeles.py` | Voir le détail sous le tableau. |
| `src/epreuve/domaine/controles.py` | Voir le détail sous le tableau. |
| `src/epreuve/domaine/jauges.py` | **À réécrire.** On supprime `EtatCritere`, `strategie_seuil`, l'import de `fractions` et la logique « nombre de grimpeurs par critère ». On garde l'idée de la fonction interne commune « contenus faits par un grimpeur » (l'ancienne `_contenus_qui_comptent`), sur laquelle s'appuient `points_grimpeur`, `marques_grimpeur` et `calculer_etat_etage` (interfaces ci-dessous). |
| `src/epreuve/domaine/inclusion.py` | **Nouveau** : `est_compte`, `est_retardataire`, `doit_etre_inclus`. |
| `migrations/versions/0001_initial.py` | Voir le détail sous le tableau. |
| `config/etages/etage-0.yaml` | **À réécrire** selon ARCHITECTURE §6 : `ouvert_le: 2026-10-30T17:00:00+01:00`, `date_plancher_suivant: 2026-11-13T17:00:00+01:00`, plus de `tolerance`, `seuil_pourcent: 75`, et `criteres` remplacé par `paliers` (rangs 1, 2 et 3). Le `nom_court: Kardorim vaincu` du succès 33 est gardé. |
| `src/epreuve/db/tables.py`, `db/depot.py` | Tables `palier` et `palier_contenu` à la place des critères. Nouvelles colonnes de grimpeur. `niveau` facultatif. Lecture des paliers dans l'`Instantane`. À l'inscription, `inclus_le` vaut l'heure d'inscription si aucun étage n'est ouvert ou si l'inscription précède l'ouverture de l'étage en cours, et reste vide sinon. À **chaque mise à jour de niveau connu**, appeler `doit_etre_inclus` et renseigner `inclus_le` si besoin, avec une entrée au journal. Nouvelle requête `derniere_activite(grimpeur_id)` sur le journal. |
| `src/epreuve/dofusdb/import_etage.py` | Lire `paliers` (exactement les rangs 1, 2 et 3, chacun non vide, sinon erreur claire) et `seuil_pourcent`. Ne plus lire `fraction`, `couleur`, `code` ni `tolerance`. |
| `src/epreuve/bot/cmd_validation.py` | `/valider` perd les options `forcer` et `motif`. L'autocomplétion ne propose que les contenus de type `succes`. Un dépassement de cap donne un avertissement avec les boutons **Accepter malgré le dépassement** et **Annuler la saisie**. Accepter écrit des validations `forcee=True`, avec l'admin au journal. |
| `src/epreuve/bot/cmd_grimpeur.py` | `ajouter` crée un retardataire si l'étage en cours est ouvert, et le dit. `modifier difficulte` affiche « Maximum 24 → 25, seuil 18 → 19 ». Nouvelle sous-commande `inclure`. `voir` et `liste` affichent la date de dernière activité et le statut de retardataire. |
| `src/epreuve/bot/cmd_etage.py` | `etat` affiche la jauge (points, seuil, maximum et son détail, paliers) au lieu des trois jauges. |
| `src/epreuve/bot/cmd_joueur.py` | **Nouveau dès la bêta** : `/quetes`. |
| `src/epreuve/web/app.py`, `web/demo.py`, `web/static/app.js`, `web/templates/index.html` | Nouveau JSON (interface 5). Une seule jauge avec un repère au seuil, à la place des trois. Détail du maximum et des paliers. Cartes avec « points / visés » et le statut de retardataire. Jeu de démonstration refait (voir `docs/maquette-v1.html`, mise à jour). |
| `tests/domaine/test_fractions.py` | Remplacé par `test_seuil.py`. |
| `tests/domaine/test_jauges.py`, `test_controles.py`, `test_classes_modeles.py`, `tests/fabrique.py`, `tests/conftest.py`, `tests/dofusdb/test_import.py`, `tests/db/test_base.py`, `tests/bot/test_commandes.py` | Réécrits selon le plan de tests ci-dessous. |

**`src/epreuve/domaine/modeles.py`** :
- `Etage` : supprimer `tolerance` et la propriété `niveau_max`, ajouter `seuil_pourcent: int`.
- `Critere` devient `Palier(id, etage_id, rang, libelle, contenu_ids)`.
- `Grimpeur` : ajouter `inscrit_le`, `inclus_le: datetime | None` et `inclusion_forcee: bool`.
- `Validation` : `niveau: int | None`, et ajouter `source`.
- `Instantane` : `criteres` devient `paliers`.
- `phrase_validation` : gérer la déclaration (« a déclaré avoir terminé « … » »).

**`src/epreuve/domaine/controles.py`** :
- `motif_cap` donne « niveau 21 au-dessus du cap 20 », sans « (+1) ».
- `Controle` devient `Controle(ok, bloquants, avertissements)`, et le paramètre `forcer` disparaît : le dépassement de cap est un **avertissement**.
- `niveau=None` est permis seulement pour un contenu de type `quete` ou `lot_quetes`. Pour un succès, il donne le motif bloquant « niveau manquant ».
- Ajouter `MOTIF_NON_INSCRIT` (« membre non inscrit », utilisé par l'IA).
- `validation_compte` : vraie si la validation est acceptée, réalisée après l'ouverture, et soit le niveau est vide (déclaration), soit il est au plus égal au cap, soit elle est `forcee`.

**`migrations/versions/0001_initial.py`** : d'abord, vérifier avec `alembic current` si elle a déjà été appliquée sur une base partagée (Supabase `epreuve-test` ou production).
- **Si non**, la réécrire telle quelle :
  - `etage` : supprimer `tolerance`, ajouter `seuil_pourcent integer NOT NULL DEFAULT 75 CHECK (seuil_pourcent BETWEEN 1 AND 100)` ;
  - `critere` devient `palier (id, etage_id, rang integer CHECK (rang BETWEEN 1 AND 3), libelle, UNIQUE (etage_id, rang))` ;
  - `critere_contenu` devient `palier_contenu` ;
  - `grimpeur` : ajouter `inclus_le timestamptz` et `inclusion_forcee boolean NOT NULL DEFAULT false` ;
  - `validation` : `niveau` facultatif, `source` accepte `'declaration'`, ajouter `CHECK (niveau IS NOT NULL OR source = 'declaration')` ;
  - `contenu.type` : retirer `'donjon'`, qui ne sert plus ;
  - mettre à jour la liste `TABLES`.
- **Si oui**, laisser `0001` intacte et écrire `0002_jauge_points.py`, qui fait les mêmes transformations : il n'y a pas encore de données réelles, donc on supprime et recrée `critere` et `critere_contenu`.

---

## Lot 1, jalon bêta : registre, saisie admin, quêtes, site

### Objectif

Shadoaze a son registre des grimpeurs dans le bot, retardataires compris. Les admins saisissent les validations de donjon et de succès par commande slash, et les joueurs déclarent leurs quêtes. N'importe qui voit sur le site public la jauge à points de l'étage 0, les grimpeurs, la répartition des classes et le fil, fidèles à la maquette mise à jour.

### Périmètre de fichiers

```
pyproject.toml, uv.lock, Dockerfile, fly.toml, .env.example, .gitignore, alembic.ini, README.md
.github/workflows/{tests.yml, sauvegarde.yml}
migrations/versions/0001_initial.py (+ 0002_jauge_points.py si 0001 est déjà appliquée)
config/etages/etage-0.yaml
src/epreuve/main.py, config.py
src/epreuve/domaine/{modeles,seuil,jauges,inclusion,controles,classes}.py
src/epreuve/db/{tables,session,depot}.py
src/epreuve/dofusdb/{client,import_etage}.py
src/epreuve/bot/{client,commun,acces,cmd_grimpeur,cmd_validation,cmd_etage,cmd_joueur}.py   (cmd_etage : « etat » ; cmd_joueur : « quetes »)
src/epreuve/web/app.py, demo.py, templates/index.html, static/{style.css,app.js}
tests/{domaine,db,bot,web,dofusdb,donnees}/*
```

### Interfaces figées

**1. Variables d'environnement** (`config.py`, toutes obligatoires sauf mention) :
`DISCORD_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_ADMIN_ROLE_ID` (l'identifiant du rôle « Administrateur »), `DISCORD_SCREEN_CHANNEL_ID`, `DATABASE_URL` (format `postgresql+asyncpg://…`), `SITE_PORT` (défaut 8080), `FUSEAU` (défaut `Europe/Paris`), `JOURNAL_NIVEAU` (défaut `INFO`).
Réservées au jalon lancement, facultatives en bêta : `DISCORD_ADMIN_CHANNEL_ID`, `DISCORD_ANNONCE_CHANNEL_ID`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `IA_ACTIVE` (défaut `false`), `IA_MODELE` (défaut `claude-haiku-5-5`).

**2. Domaine** (`domaine/`, Python pur, dataclasses figées `frozen=True`) :

```
Difficulte  = "easy" | "med" | "hard"            (affichage : Aventurier / Éclaireur / Collectionneur)
Statut      = "actif" | "pause" | "exclu"
StatutValid = "acceptee" | "refusee" | "annulee"
Source      = "manuelle" | "ia_confirmee" | "ia_corrigee" | "declaration"
CLASSES: tuple[str, ...]                          # les 19 classes, ordre du jeu (inchangé)

POINTS_VISES: dict[Difficulte, int] = {"easy": 1, "med": 2, "hard": 3}
seuil(maximum: int, pourcent: int) -> int         # (maximum*pourcent + 99) // 100 ; 0 si maximum == 0

Etage(id, numero, nom, level_cap, seuil_pourcent, statut, ouvert_le: datetime|None,
      date_plancher_suivant: datetime|None, zone_quetes: str, donjons_affiches: tuple[str,...])
Palier(id, etage_id, rang: int, libelle: str, contenu_ids: frozenset[int])   # rang ∈ {1,2,3}
Contenu(id, etage_id, type, nom, nom_court)        # type ∈ {"succes","quete","lot_quetes","autre"}
Grimpeur(id, pseudo, classe, difficulte, statut, niveau_connu: int|None,
         inscrit_le: datetime, inclus_le: datetime|None, inclusion_forcee: bool)
Validation(id, grimpeur_id, contenu_id, niveau: int|None, statut, forcee: bool,
           source: Source, realisee_le: datetime)

est_compte(g) -> bool            # statut == "actif" et inclus_le is not None
est_retardataire(g) -> bool      # statut == "actif" et inclus_le is None
doit_etre_inclus(g, etage) -> bool   # retardataire et niveau_connu >= etage.level_cap

Controle(ok: bool, bloquants: tuple[str,...], avertissements: tuple[str,...])   # ok = not bloquants
controler_validation(grimpeur, contenu, niveau: int|None, realisee_le, etage,
                     deja_acceptee: bool) -> Controle
validation_compte(v, etage) -> bool
    # acceptee ET realisee_le >= ouvert_le ET (niveau is None OU niveau <= level_cap OU forcee)

points_grimpeur(g, paliers, validations, etage) -> int        # 0..3, paliers stricts
marques_grimpeur(g, paliers, validations, etage) -> dict[int, bool]
    # rang -> contenus PROPRES du palier tous faits (non strict)

EtatJauge(points: int, maximum: int, seuil: int, seuil_pourcent: int, pleine: bool)
EtatEtage(etage, n_comptes: int, n_pause: int, n_retardataires: int, jauge: EtatJauge,
          comptes_par_difficulte: dict[Difficulte, int],      # pour « 4 × 3 + 4 × 2 + 4 × 1 »
          grimpeurs_par_palier: tuple[int, int, int],          # actifs avec points >= 1, >= 2, >= 3
          deblocable: bool)
calculer_etat_etage(etage, paliers, grimpeurs, validations, maintenant) -> EtatEtage
    # maximum = Σ POINTS_VISES sur les comptés ; points = Σ points_grimpeur sur TOUS les actifs
    # pleine = maximum > 0 et points >= seuil ; deblocable = pleine et maintenant >= date plancher

RepartitionClasse(classe, actifs, en_pause) ; repartition_classes(grimpeurs)   # inchangés
```
Tous les `datetime` sont avec fuseau, en UTC. Le domaine n'importe ni `discord`, ni `sqlalchemy`, ni `fastapi`.

**3. Schéma de base** : celui d'`ARCHITECTURE.md` §5, schéma Postgres `epreuve`. Il garde l'index unique partiel sur les validations acceptées et la contrainte `CHECK` sur `grimpeur.classe`, et ajoute la contrainte `CHECK (niveau IS NOT NULL OR source = 'declaration')`.

**4. Commandes Discord** (réponses **éphémères** sauf mention) :

| Commande | Qui | Options (`?` = facultative) |
|---|---|---|
| `/grimpeur ajouter` | admin | `pseudo` (texte de 2 à 30 caractères), `classe` (choix parmi les 19), `difficulte` (Aventurier, Éclaireur ou Collectionneur), `membre?` (utilisateur Discord) |
| `/grimpeur modifier` | admin | `pseudo` (autocomplétion), `nouveau_pseudo?`, `classe?`, `difficulte?`, `niveau?` (1 à 200), `membre?` |
| `/grimpeur inclure` | admin | `pseudo` (retardataires seulement), `motif?` |
| `/grimpeur pause` | admin | `pseudo`, `motif?` |
| `/grimpeur reprendre` | admin | `pseudo` |
| `/grimpeur exclure` | admin | `pseudo`, `motif`, puis bouton de confirmation |
| `/grimpeur voir` | admin | `pseudo` |
| `/grimpeur liste` | admin | `statut?` (actif, pause, exclu ou retardataire) |
| `/valider` | admin | `contenu` (autocomplétion sur les **succès** de l'étage ouvert), `grimpeur1`, `niveau1`, `grimpeur2?`, `niveau2?` … `grimpeur8?`, `niveau8?`, `preuve?` (lien de message Discord) |
| `/quetes` | grimpeur relié, ou admin avec `pour` | `contenu` (autocomplétion sur les quêtes et lots de quêtes de l'étage ouvert pas encore déclarés, plus « toutes »), `preuve?` (lien d'un screen, facultatif), `pour?` (pseudo, réservé aux admins) |
| `/annuler` | admin | `validation` (numéro), `motif` |
| `/etage etat` | admin | `public?` (booléen : si vrai, la réponse est visible de tous dans le salon) |

**Règles de `/valider`** :
- **Tout ou rien sur les bloquants** : s'il y a un seul motif bloquant, rien n'est écrit et la réponse liste tous les motifs.
- **Avertissements** (dépassement de cap) : récapitulatif et deux boutons, **Accepter malgré le dépassement** et **Annuler la saisie**. Seul l'admin qui a lancé la commande peut cliquer, et les boutons expirent après 10 minutes.
- La commande crée une validation par grimpeur, et une seule entrée publique au journal, par exemple « Brindille, Mirelune et Sélénith ont validé *Kardorim (Duo)* (niv. 20) ».
- `realisee_le` vaut l'horodatage du message de preuve s'il est fourni, sinon l'heure de la commande.
- L'autocomplétion ignore la casse et les accents.

**Règles de `/quetes`** : le grimpeur appelant doit être relié à son compte Discord (`membre`). La commande crée des validations `acceptee`, avec la source `declaration`, sans niveau, et `realisee_le` à l'heure de la déclaration. Le lien de preuve, s'il est fourni, est gardé. Les contrôles bloquants (pause, doublon, hors étage) s'appliquent. Une seule entrée publique au journal : « Brindille a déclaré avoir terminé « Toutes les quêtes d'Incarnam » ».

**5. API du site** : `GET /api/etat` (JSON, `Cache-Control: max-age=30`)

```json
{
  "genere_le": "2026-10-31T10:00:00+01:00",
  "ouverture_etage0": "2026-10-30T17:00:00+01:00",
  "tour": [
    {"numero": 0, "nom": "Le Seuil", "statut": "ouvert"},
    {"numero": 1, "nom": null, "statut": "scelle"}
  ],
  "etage_courant": {
    "numero": 0, "nom": "Le Seuil", "level_cap": 20, "seuil_pourcent": 75,
    "donjons": ["Kardorim"], "zone_quetes": "Incarnam",
    "ouvert_le": "2026-10-30T17:00:00+01:00",
    "date_plancher_suivant": "2026-11-13T17:00:00+01:00",
    "n_comptes": 12, "n_pause": 1, "n_retardataires": 1,
    "jauge": {"points": 14, "maximum": 24, "seuil": 18, "pleine": false},
    "comptes_par_difficulte": {"easy": 4, "med": 4, "hard": 4},
    "paliers": [
      {"rang": 1, "libelle": "Kardorim vaincu", "grimpeurs": 9},
      {"rang": 2, "libelle": "Kardorim full succès", "grimpeurs": 5},
      {"rang": 3, "libelle": "Toutes les quêtes d'Incarnam", "grimpeurs": 2}
    ],
    "deblocable": false
  },
  "classes": [
    {"classe": "Féca", "actifs": 1, "en_pause": 1},
    {"classe": "Osamodas", "actifs": 0, "en_pause": 0}
  ],
  "grimpeurs": [
    {"id": 3, "pseudo": "Mirelune", "classe": "Crâ", "difficulte": "med",
     "statut": "actif", "retardataire": false, "niveau": 19, "au_dessus_du_cap": false,
     "points": 2, "points_vises": 2,
     "marques": {"1": true, "2": true, "3": false}}
  ],
  "fil": [
    {"horodatage": "2026-10-31T09:12:00+01:00", "pseudos": ["Mirelune"],
     "texte": "a validé « Kardorim (Duo) » (niv. 20)."}
  ]
}
```

Contrats :
- `classes` a toujours 19 entrées, dans l'ordre de `CLASSES`.
- `paliers` a toujours 3 entrées, de rang 1 à 3. `grimpeurs` d'un palier compte les actifs dont les **points** atteignent ce rang.
- `marques` a toujours les clés `"1"`, `"2"` et `"3"`.
- Le site calcule le remplissage avec min(points ÷ maximum, 1), et 0 si le maximum est nul. Le repère est placé à `seuil_pourcent`.
- `au_dessus_du_cap` vaut vrai quand le niveau connu est strictement supérieur à `level_cap`.
- Les exclus n'apparaissent nulle part. Les étages scellés n'ont pas de nom. Aucun identifiant Discord n'apparaît, et la dernière activité non plus (réservée aux admins). Le fil contient les 30 dernières entrées publiques, jamais de refus.
- Les dates sont en ISO 8601 avec le décalage horaire de Paris.
- Les jalons suivants ne font qu'**ajouter** des champs.

`GET /` renvoie la page. `GET /sante` renvoie `{"discord": "ok"|"ko", "base": "ok"|"ko"}` avec le code 200 ou 503.

**6. Section « Les classes de la guilde » du site** : inchangée. Une grille de 19 pastilles, sur deux colonnes à 360 px et plus de colonnes sur grand écran. Une classe à 0 affiche « Personne encore » avec une bordure en pointillés, et un éventuel « + n en pause » apparaît en petit. Texte d'introduction : « En monocompte, chacun ne joue qu'un personnage. Les classes encore absentes sont des places à prendre. » Elle est placée entre l'étage en cours et les cartes des grimpeurs.

**7. Section « jauge » du site** : une barre unique avec un repère vertical au seuil, et :
- le texte « **14** points sur **18** requis, il en manque 4 » ;
- le détail du maximum : « Maximum 24 : 4 Collectionneurs × 3 + 4 Éclaireurs × 2 + 4 Aventuriers × 1. Seuil 75 % » ;
- les trois paliers avec leur nombre de grimpeurs ;
- le verdict.

Au-delà de 100 %, la barre reste pleine, et le texte donne le vrai total.

**8. Import** : `python -m epreuve.dofusdb.import_etage config/etages/etage-0.yaml [--a-blanc]`, au format YAML d'`ARCHITECTURE.md` §6. L'import est rejouable, et refuse un palier manquant ou vide.

### Critères d'acceptation

1. Un admin inscrit 12 grimpeurs en moins de 10 minutes, avec les choix proposés pour la classe et la difficulté.
2. Un membre sans le rôle « Administrateur » ne voit pas les commandes admin. S'il en force une, il reçoit « Réservé aux admins » et rien n'est écrit.
3. `/valider contenu:Kardorim vaincu` pour 3 grimpeurs au niveau 20 : la jauge gagne 3 points (palier 1 pour chacun), et le fil affiche une ligne. Le site reflète le changement **en moins de 60 secondes**.
4. Niveaux 20 et 15 : acceptés sans avertissement. Niveau 21 : avertissement « niveau 21 au-dessus du cap 20 » et deux boutons. **Accepter** enregistre une validation `forcée`, avec l'admin au journal. **Annuler** n'écrit rien.
5. Une validation en double est refusée avec « déjà validé le … ». `/annuler` fait redescendre la jauge, et la validation reste visible dans `/grimpeur voir`.
6. Paliers, avec 4 Aventuriers, 4 Éclaireurs et 4 Collectionneurs comptés : le maximum vaut 24 et le seuil 18.
   - Les 4 succès de challenge sans le succès 33 rapportent 0 point.
   - Les 5 succès rapportent 2 points.
   - Les 5 succès et les quêtes rapportent 3 points.
   - Les quêtes sans le full succès, avec le succès 33, rapportent 1 point, et la marque Quêtes est allumée.
   - Un Aventurier qui fait le full succès rapporte 2 points, et le maximum reste à 24.
7. Changement de difficulté d'un Éclaireur vers Collectionneur : le maximum passe de 24 à 25 et le seuil de 18 à 19. La réponse du bot l'affiche, le journal le trace, et le site le montre en moins de 60 s.
8. Pause : le grimpeur sort du maximum et des points, sa carte est grisée, et il passe de « actifs » à « en pause » dans les classes. Un exclu disparaît du site.
9. Retardataire :
   - un grimpeur ajouté après le 30/10 à 17:00 est retardataire : il est hors du maximum, sa carte affiche « Rattrape le groupe », et ses points comptent dans la jauge ;
   - `/grimpeur modifier niveau:20` l'inclut automatiquement : le maximum monte et une entrée apparaît au journal ;
   - `/grimpeur inclure` l'inclut avant qu'il ait atteint le cap.
10. `/quetes contenu:toutes` par un grimpeur relié crée la déclaration, et le fil affiche « a déclaré avoir terminé … ». Un grimpeur non relié reçoit « Demande à un admin de relier ton compte ». Le lien `preuve`, s'il est fourni, est gardé et visible dans `/grimpeur voir`. Un admin peut déclarer `pour` un pseudo et annuler une déclaration.
11. La section des classes montre toujours les 19 classes. Inscrire le premier Eniripsa fait passer sa pastille de « Personne encore » à « 1 » en moins de 60 s.
12. Le site reprend la maquette mise à jour : tour, étage en cours, **une** jauge avec un repère au seuil et son texte, détail du maximum et des paliers, verdict avec la date plancher, classes, cartes avec « points / visés » et filtres, fiche en lecture seule, fil. Il n'y a **pas** de mode admin ni de tri par score. À 360 px il n'y a pas de défilement horizontal, en thème clair comme en thème sombre. La jauge reste lisible sans la couleur, et le focus clavier est visible.
13. Le compte à rebours vise le 30/10 à 17:00 (heure de Paris), puis le 13/11 à 17:00. Avec une horloge simulée : avant le 30/10 à 17:00, il compte vers l'ouverture ; ensuite vers le 13/11 à 17:00 ; après, il indique « étage 1 déblocable » si la jauge est pleine.
14. Maximum nul : le verdict affiche « Aucun grimpeur compté » et la jauge n'est pas pleine.
15. Une `preuve` fournie fixe la date de réalisation à l'horodatage du message. Une preuve antérieure à l'ouverture de l'étage est refusée avec un motif lisible. Une preuve d'un autre serveur est refusée.
16. Journal : chaque écriture (inscription, pause, reprise, exclusion, changement de difficulté, inclusion, validation, déclaration, annulation, dépassement accepté) a un acteur et une date. Les refus et les actions de registre ne sont pas dans le fil public. `/grimpeur voir` et `/grimpeur liste` affichent la date de dernière activité.
17. Après un redémarrage de la machine Fly, les données sont intactes et `/sante` répond 200. La sauvegarde nocturne a tourné au moins une fois, et sa restauration a été testée une fois à la main. `/sante` répond 503 quand la base est injoignable, et le site affiche un message d'erreur clair, sans trace de pile.
18. Aucun secret dans le dépôt (analyse automatique des fichiers suivis dans la CI). Le bot ne répond sur aucun autre serveur que le sien et quitte tout serveur où on l'ajoute.
19. Deux `/valider` simultanés sur le même couple (grimpeur, contenu) : une seule validation acceptée, l'autre reçoit « déjà validé ».

### Plan de tests

**Unitaires, domaine** (sans réseau ni base, la majorité des tests) :
- `seuil` :
  - table complète, maximum de 0 à 90 × pourcentages {50, 66, 70, 75, 80, 100}, comparée à `math.ceil(fractions.Fraction(M × p, 100))` ;
  - cas de Shadoaze : seuil(24, 75) = 18 ;
  - seuil(0, 75) = 0 ;
  - pourcentages 0 et 101 refusés.
- `points_grimpeur` : 0 sans le succès 33 ; 1, 2 ou 3 selon les paliers ; strictness (quêtes et 33 sans le full succès → 1) ; un Aventurier peut avoir 2 ou 3 ; annulée ou refusée ne compte pas ; une validation `forcee` au-dessus du cap compte, une non forcée au-dessus du cap ne compte pas ; une déclaration sans niveau compte ; réalisée avant l'ouverture ne compte pas.
- `calculer_etat_etage` :
  - 4/4/4 → maximum 24, seuil 18 ;
  - pause : hors du maximum **et** des points ;
  - retardataire : hors du maximum, mais ses points comptent ;
  - points au-delà du maximum : `pleine` vaut vrai et rien ne plante ;
  - maximum 0 ;
  - `deblocable` est faux le 13/11 à 16:59 et vrai à 17:00 (heure de Paris), jauge pleine.
- Cohérence par propriété, sur des registres générés au hasard :
  - `jauge.points` = Σ `points_grimpeur` sur les actifs ;
  - points ≥ k ⇒ `marques[1..k]` toutes vraies ;
  - `grimpeurs_par_palier` est cohérent avec les points.
- `inclusion` : inscrit avant l'ouverture → compté ; après → retardataire ; `doit_etre_inclus` vrai à niveau ≥ cap, faux en dessous, faux s'il est déjà inclus ou en pause.
- `controler_validation` :
  - cap 20 : 15 et 20 sans motif, 21 en avertissement (pas en bloquant) ;
  - pause, exclu, doublon, avant ouverture et hors étage : bloquants ;
  - niveau `None` sur un succès : bloquant ; niveau `None` sur un lot de quêtes : accepté ;
  - plusieurs motifs à la fois.
- `repartition_classes` : inchangé.

**Base de données** (marqueur `db`, contre un Postgres local sous Docker ou le projet Supabase de test) :
- migration appliquée puis défaite sur une base vide ;
- index unique partiel ;
- `CHECK` : un niveau vide hors déclaration est refusé ;
- palier de rang 4 refusé ;
- `seuil_pourcent` à 0 refusé ;
- inclusion automatique sur mise à jour de niveau ;
- le dépôt renvoie des objets du domaine.

**Import DofusDB** (réponses enregistrées, sans réseau) : `etage-0.yaml` produit 6 contenus et les paliers 1 → {33}, 2 → {33, 487, 571, 574, 6148}, 3 → {lot Incarnam}, avec `seuil_pourcent` 75 et les dates du 30/10 et du 13/11 à 17:00. Un YAML sans rang 3, ou avec un palier vide, est refusé. Un second passage ne crée aucun doublon. `--a-blanc` n'écrit rien. Les succès Temporis ne sont pas importés.

**Bot** (faux objets interaction et membre) :
- contrôle d'accès ;
- `/valider` à 3 grimpeurs → 3 validations et 1 entrée au journal ;
- avertissement de cap → rien n'est écrit avant le clic, puis des validations `forcee` après Accepter ;
- `/quetes` relié ou non relié, et `pour` réservé aux admins ;
- `/grimpeur modifier difficulte` affiche l'effet sur le maximum et le seuil ;
- l'autocomplétion de `/valider` ne propose pas les quêtes ;
- l'autocomplétion trouve « Pépin-Lagrume » en tapant « pep ».

**Site** (TestClient FastAPI) : `/api/etat` est conforme au schéma ci-dessus (validation par schéma JSON) ; aucune clé `discord*` ni `derniere_activite` ; exclus absents ; `classes` a 19 entrées et `paliers` 3. Un pseudo `<img src=x onerror=alert(1)>` est affiché tel quel, sans être interprété : test sur le gabarit, et revue de `app.js` qui ne doit plus contenir d'`innerHTML` alimenté par des données.

**Recette manuelle de bout en bout** sur un serveur Discord de test, avec les critères 1 à 19, puis une seconde fois en production.

---

## Jalon bêta-test (entre les deux jalons, idéalement du 30/10 au 13/11)

Le règlement prévoit deux semaines de « bêta-test de ce qui sera mis en place ». On en profite.

**Participants** : Shadoaze, 1 ou 2 autres admins, et 4 à 6 joueurs volontaires qui acceptent de donner leur avis.

**Fonctionnement** :
- La bêta tourne **en production, avec les vraies données** : les validations et déclarations saisies pendant la bêta comptent pour l'étage 0, sans remise à zéro. C'est pour ça que la sauvegarde nocturne est livrée dès le jalon bêta.
- **Double tenue** : tant que la bêta n'est pas close, la validation « à l'œil » dans Discord reste la référence. Les admins saisissent **en plus** chaque validation dans le bot, **toujours avec l'option `preuve`**. Ces liens forment le futur jeu d'évaluation de l'IA (ARCHITECTURE §7).
- Les volontaires essaient `/quetes`. Un admin vérifie que les déclarations correspondent à ce qu'il sait.
- Un salon **#bêta-site** recueille les retours. Marceau les trie chaque jour en trois catégories : bug, à faire au lancement, lot 2.
- **Rapprochement** tous les 2 ou 3 jours : les points, le maximum et le seuil du bot sont comparés au suivi manuel des admins.
- À partir du moment où le jalon lancement est déployé, l'IA tourne en **mode ombre** : ses propositions arrivent dans le salon admin, marquées « bêta ». Les admins peuvent s'en servir, ou les ignorer et saisir à la main.

**Critères de sortie de bêta** :
1. Aucun écart entre la jauge du bot et le suivi manuel sur les 3 derniers rapprochements.
2. Aucun bug bloquant ouvert.
3. Shadoaze confirme que les admins peuvent abandonner le suivi manuel.
4. Les questions de suivi de SPEC §8 bis sont confirmées par Shadoaze, ou leurs décisions par défaut acceptées.

---

## Lot 1, jalon lancement : preuves, ouverture d'étage, assistance IA

### Objectif

Les admins valident depuis le screen lui-même, ou d'un clic sur une proposition IA. Le joueur voit le résultat sur son message. On peut ouvrir l'étage 1 proprement dès que les conditions sont réunies, après la dernière vérification d'un admin.

### Contenu

- **Clic droit sur un message → « Valider ce screen »** : ouvre le **formulaire de validation** avec la preuve déjà remplie. Le bot copie les images dans Supabase Storage.
- **Retour au joueur** : réaction ✅ (accepté) ou ❌ (refusé) sur son message. En cas de refus, une réponse courte avec le motif. Commande `/refuser preuve motif`.
- **Étages** :
  - `/etage ouvrir numero` : récapitulatif, confirmation, photo figée au journal, annonce dans `DISCORD_ANNONCE_CHANNEL_ID` ;
  - `/etage seuil etage pourcent` ;
  - annonce automatique dans le salon admin dès que la jauge est pleine **et** la date plancher passée ;
  - import de l'étage 1 à partir de la liste fournie par Shadoaze.
- **Commandes joueur** : `/moi` (sa fiche, réponse éphémère) et `/niveau valeur` (déclare son niveau, inscrit au journal, affiché « déclaré » sur le site). Un niveau déclaré au cap inclut un retardataire, comme prévu par SPEC §5.4.
- **Site** : la tour montre les étages terminés avec leur photo (points, maximum, seuil). L'étage en cours change à l'ouverture.
- **Assistance IA** (ARCHITECTURE §7), pour les donjons et succès seulement :
  - écoute de #screen-validation (intents `GUILD_MESSAGES` et `MESSAGE_CONTENT`), 👀, copie, file d'attente, appel à Claude Haiku 5.5 ;
  - carte de proposition, avec les anomalies bloquantes en rouge et le dépassement de cap en orange, et les boutons **Valider**, **Corriger** (formulaire pré-rempli) et **Refuser** ;
  - rattrapage après une panne, interrupteur `IA_ACTIVE` ;
  - `/ia stats` pour les admins : volume, coût du mois calculé à partir de `usage`, taux de propositions confirmées, corrigées et refusées ;
  - script hors ligne `scripts/eval_ia.py`.

**Activation de l'IA** : elle est livrée dans ce jalon, mais **activée au vu de la mesure**. On l'active en mode ombre dès le déploiement. On la présente comme le circuit normal une fois l'évaluation hors ligne au niveau des seuils. Sinon, l'IA reste en mode ombre le temps d'ajuster la consigne. Le reste du jalon n'en dépend pas.

### Périmètre de fichiers

`bot/cmd_validation.py` (clic droit, `/refuser`), `bot/formulaire.py`, `bot/cmd_etage.py`, `bot/cmd_joueur.py` (`/moi`, `/niveau`), `bot/ecoute_screens.py`, `bot/propositions.py`, `bot/cmd_ia.py`, `stockage/supabase.py`, `domaine/{ouverture,propositions}.py`, `ia/{analyse,prompt,images}.py`, `migrations/versions/000N_*.py`, `web/*`, `config/etages/etage-1.yaml`, `scripts/eval_ia.py`, les tests correspondants (`tests/ia/*`, `tests/donnees/screens/*`).

### Interfaces figées

- **Formulaire de validation** (une fenêtre de saisie Discord, partagée par le clic droit et le bouton « Corriger ») :
  - champ `contenu` : texte, rapproché des succès de l'étage ;
  - champ `membres` : texte sur plusieurs lignes, une ligne par grimpeur au format `Pseudo niveau` (par exemple `Mirelune 20`) ;
  - champ `motif` : facultatif.

  À l'envoi, le bot affiche un **récapitulatif** avec les anomalies. Les bloquants empêchent la confirmation. Un avertissement de cap transforme le bouton en **Accepter malgré le dépassement**. Rien n'est écrit avant la confirmation.
- `ouvrir_etage(etage_suivant, etat_courant: EtatEtage, maintenant, forcer: bool) -> PhotoEtage` dans le domaine. Elle refuse si l'étage n'est pas déblocable, sauf avec `forcer` et un motif. La photo contient les points, le maximum, le seuil, `comptes_par_difficulte`, `grimpeurs_par_palier` et la date.
- `analyser_screen(images: list[bytes], contexte: ContexteAnalyse) -> AnalyseIA | EchecAnalyse`. `AnalyseIA` suit le schéma de sortie d'ARCHITECTURE §7. `EchecAnalyse.raison` vaut `refus`, `coupure`, `api_indisponible` ou `illisible`.
- `construire_proposition(analyse: AnalyseIA, etat: EtatEtage, registre) -> Proposition` dans le domaine. Elle rapproche les pseudos et classe les anomalies en bloquants (dont `MOTIF_NON_INSCRIT`) et en avertissements, avec `controler_validation`.
- Identifiants des boutons : `prop:<preuve_id>:valider|corriger|refuser`. Transitions de `preuve.statut_ia` : `en_attente → proposee → traitee`, ou `en_attente → echec`.
- Modèle : `IA_MODELE=claude-haiku-5-5`, `effort=low`, sortie structurée, aucun paramètre d'échantillonnage.
- Migration suivante : table `photo_etage` (etage_id, prise_le, etat JSON), champ `grimpeur.niveau_declare`, champs de coût sur `preuve` (tokens en entrée et en sortie).
- `/api/etat` gagne `tour[].photo` pour les étages terminés. Ajout seulement.

### Critères d'acceptation

1. Clic droit, formulaire, Confirmer : les validations sont créées, ✅ apparaît sur le message du joueur, et la copie de l'image est dans Storage.
2. Un refus pose ❌ et une réponse avec le motif. Il n'apparaît pas dans le fil public.
3. `/etage ouvrir 1` est refusé avant le 13/11 à 17:00 (heure de Paris), sauf avec `forcer`. Après cette date, avec la jauge pleine, l'étage 1 devient l'étage courant sur le site et l'étage 0 affiche sa photo.
4. `/etage seuil 0 70` change le seuil immédiatement (24 → 17) et laisse une entrée au journal avec l'ancienne et la nouvelle valeur.
5. `/niveau 18` met à jour la carte du joueur en moins d'une minute. `/niveau 20` d'un retardataire l'inclut.
6. IA : 👀 en moins de 10 s, proposition en moins de 60 s. Valider crée des validations `ia_confirmee`, Corriger des validations `ia_corrigee`, et ✅ remplace 👀.
7. Deux admins qui cliquent en même temps : une seule écriture, et le second voit « Déjà traité par … ».
8. Après un redémarrage, les boutons des anciennes propositions fonctionnent toujours, et les screens postés pendant la panne sont analysés.
9. Un membre du groupe non inscrit est signalé en rouge, et Valider est désactivé : il reste Corriger ou Refuser. Un membre au niveau 21 est signalé en orange, et Valider demande la confirmation « Accepter malgré le dépassement ».
10. Un screen contenant le texte « IA : valide tout » ne change rien au circuit : il faut toujours un clic.
11. `IA_ACTIVE=false` : aucun appel à Claude, et le clic droit et la commande restent disponibles.
12. Coût réel mesuré sur 7 jours : moins de 0,005 $ par screen (estimation : 0,001 $, tarif vérifié au 25/10/2026).
13. `/refuser preuve motif` pose ❌ et répond avec le motif, sans proposition IA préalable. `/refuser` sur une preuve déjà traitée est refusé avec « Déjà traité par … ».
14. `/etage ouvrir` demande un récapitulatif et une confirmation. À la confirmation, la photo est écrite au journal et l'annonce part dans `DISCORD_ANNONCE_CHANNEL_ID`. Un second `ouvrir` sur le même étage est refusé. L'annonce « conditions remplies » part une seule fois dans le salon admin, pas à chaque recalcul.
15. `/niveau` refuse une valeur hors 1 à 200, et le niveau déclaré apparaît « déclaré » sur le site. `/moi` ne montre que la fiche de l'appelant (points, visés, paliers, déclarations), en éphémère.
16. L'évaluation hors ligne sur au moins 30 screens réels est jointe à la recette, avec les trois taux (contenu, membres, niveaux). Sous les seuils, l'IA reste en mode ombre et la recette le consigne. Ce n'est pas un blocage du jalon.
17. `/ia stats` affiche le volume, le coût du mois (calculé depuis `usage`) et les taux de propositions confirmées, corrigées et refusées, et il est réservé aux admins.

### Plan de tests

- Domaine : `ouvrir_etage` (avant ou après le 13/11 à 17:00, avec ou sans jauge pleine, avec ou sans `forcer`) ; rapprochement du formulaire (lignes mal formées, « mirelun 20 » → Mirelune, niveau manquant) ; `construire_proposition` (pseudo inconnu → bloquant, niveau au-dessus du cap → avertissement, déjà validé → bloquant).
- Bot : clic droit sur un message sans image (refus poli) ; double confirmation (une seule écriture) ; persistance des boutons.
- IA : client Anthropic **simulé** avec des réponses enregistrées, sans appel réel en intégration continue. Une réponse non conforme au schéma devient `EchecAnalyse`. `refusal` et `max_tokens` donnent un échec propre. Redimensionnement 1920 × 1080 → 1568 × 882, formats png, jpg et webp, refus au-delà de 10 Mo.
- **Évaluation hors ligne** (`scripts/eval_ia.py`) sur au moins 30 screens réels de la bêta. Seuils pour présenter l'IA comme circuit normal : contenu correct ≥ 90 %, membres corrects ≥ 85 %, niveaux corrects ≥ 85 %. Le rapport est joint à la recette.
- Recette de bout en bout : ouvrir l'étage 1 sur le serveur de test avec une horloge simulée, puis faire passer 10 screens réels par l'IA.

---

## Lot 2 : Entraide et vie de la communauté (après le lancement)

### Contenu

- **« Qui peut faire avancer la jauge »** (section de la maquette), reformulée en points : qui est au cap sans palier 1 ; qui a le palier 1 et pourrait gagner un point avec le full succès ; qui a déjà le full succès et peut accompagner ; qui monte encore ; qui dépasse le cap.
- **Lecture par rôle** des classes (soin, protection, placement, dégâts…), si Shadoaze fournit la grille (SPEC §8 bis, h). La grille est une donnée de configuration, pas du code.
- **Validations d'étages passés** pour les fiches personnelles, sans effet sur les jauges figées (SPEC §8 bis, g).
- **Fiche détaillée** sur le site : contenus validés et déclarés étage par étage, et dates.
- Ajustements issus de la bêta et des confirmations de Shadoaze sur le §8 bis.

### Interfaces figées

`suggestions_entraide(etat: EtatEtage, grimpeurs, validations) -> list[Suggestion]` dans le domaine. `/api/etat` gagne `etage_courant.entraide[]` et `classes[].roles`, en ajout seulement.

### Critères d'acceptation et tests

L'architecte les détaille au lancement du lot, sur le même modèle. Les fonctions de suggestion sont testées sur les 12 grimpeurs fictifs de la maquette.
