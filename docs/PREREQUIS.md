# L'Épreuve des Dieux : prérequis

Version 4, 27/10/2026. Ce que **Marceau** doit faire lui-même, et ce qu'il doit **demander à Shadoaze ou à l'auteur de Duffus**, avant chaque lot. Les étapes sont concrètes et dans l'ordre.

Légende : 🧑‍💻 Marceau seul · 🤝 avec Shadoaze · ✉️ avec l'auteur de Duffus · ✅ déjà fait.

## Ce qui change en v4

- **Aucun bot pour le site** (arbitrage du chef de projet). Plus d'intents à activer, de permissions à régler ni de commandes. Le seul bot qui reste est le « bot d'atelier » de Marceau, qui lit les salons (EX-93) : il est hors du site.
- **Nouveau : la connexion avec Discord (OAuth2).** Il faut un *Client Secret* et une **adresse de retour** déclarée dans le portail Discord (section C).
- **Nouveau : un nom de domaine**, à acheter et à relier à Fly **avant le 3/11**, pour le teaser (section B).
- **Nouveau : la lecture de la base de Duffus**, à cadrer avec son auteur (section D).
- **Plus de compte Anthropic** pour les lots A et B : l'IA de lecture des screens est retirée.
- **Supabase** : un seul projet de production suffit. Les tests tournent sur un Postgres local sous Docker, ou dans la CI.
- L'ordre suit le calendrier : **lot A** (teaser) avant le 3/11, **lot B** (cœur) avant le 10/11.

---

## État réel au 27/10/2026

| Élément | État |
|---|---|
| Marceau admin du serveur Discord « L'Épreuve des Dieux » | ✅ |
| Application Discord « Gardien de la Tour », Application ID **1564210808509038622** | ✅ créée |
| Jeton du bot (`DISCORD_TOKEN`) dans `.env`, qui est bien dans `.gitignore` | ✅ |
| Intent **Message Content** activé | ✅. Il n'est **pas** nécessaire au site. Le garder seulement si le bot d'atelier en a besoin pour lire les salons. |
| Bot présent sur le serveur | **Probable** : les exports de `docs/discord/` portent la mention « lu par le bot le 27/10 ». Le site n'en a pas besoin (C.1). Il n'a pas accès aux salons d'étage, mais ce n'est plus utile : ils ne sont pas une source de données. |
| OAuth2 (Client Secret, adresse de retour) | ❌ à faire (C.2) |
| Domaine, Fly.io, Supabase, dépôt GitHub distant | ❌ à faire (`DATABASE_URL` est vide dans `.env`, et il n'y a pas de dépôt distant) |
| Accès à la base de Duffus | Accord de principe de l'auteur ✅. Modalités ❌ à cadrer (D). |
| Page teaser et DA | ✅ `docs/design/teaser.html`, `DA.md`, `maquette-v2.html` |

---

## A. Questions et messages (le plus tôt possible, dès le 27/10)

### A.1 Les questions pour Shadoaze (🤝)

Ce sont les huit questions de `SPEC.md` §8.2, dans le même ordre. Les plus urgentes sont **Q1** (étage ↔ tranche et cap) et **Q2** (donjons des étages 0 et 1), à obtenir **avant le 7/11** pour construire les étages. Chaque question a déjà une réponse par défaut appliquée : rien ne bloque le développement. Message proposé :

> Salut Shadoaze ! Le site avance : connexion avec Discord, cases à cocher, jauge 2 × actifs, tour en pyramide. J'ai besoin de toi sur quelques points. Pour chacun, je te donne ce que j'applique si tu ne dis rien, et un « ok » suffit :
> 1. Étage ↔ tranche Duffus : étage 0 = la première tranche (jusqu'au niveau 20), puis une tranche par étage, et le cap = le haut de la tranche ?
> 2. Donjons des étages 0 et 1 : je prends ceux dont le niveau est dans la tranche, et je t'envoie la liste à valider.
> 3. Un étage sans quête principale (l'étage 0, sûrement) : la catégorie disparaît et le palier baisse en proportion (18 au lieu de 24 pour 12 joueurs). Ok ?
> 4. Les Dofus qui rendent une quête « principale » : tous ceux qui ont un guide chez Duffus ?
> 5. Points bonus d'événement (pas pour le lancement, plus tard) : à un joueur ou à toute la guilde, au choix de l'admin ? Pas pour un joueur en pause ?
> 6. Encyclopédie et builder : les refaire coûte des semaines. Je propose des liens vers les outils existants. Ça te va ?
> 7. Tu peux ajouter « palier = 2 × grimpeurs actifs » dans #concept-et-règles ?
> 8. Tu as généré des images pour chaque étage : tu peux me les passer ? Elles serviraient de décor sur la page de l'étage (sinon : « Étage N » et la tranche, sans image).
> Merci !

### A.2 La liste officielle des grimpeurs (🤝)

✅ Les 10 identifiants Discord sont dans `docs/discord/liste-grimpeurs.md`. Le jour du déploiement (10/11), Marceau les colle dans *Admin → Grimpeurs → Liste officielle*. Les inscrits suivants y seront ajoutés de la même façon, et Shadoaze, en tant qu'admin, pourra le faire lui-même.

---

## B. Lot A : domaine et hébergement (🧑‍💻, environ 1 h, avant le 2/11)

### B.1 Acheter le nom de domaine (15 min)

1. Choisir un registrar : **OVHcloud** ou **Gandi** (français), ou **Porkbun**. Compter 7 à 12 € par an pour un `.fr` ou un `.com`.
2. Choisir un nom **qui ne révèle rien avant le reveal** : le domaine sera public. Par exemple `epreuve-des-dieux.fr`.
3. Activer le renouvellement automatique et la protection des données du titulaire (« WHOIS privacy »), souvent gratuite.
4. Ne rien configurer d'autre pour l'instant : les enregistrements DNS viennent à l'étape B.3.

### B.2 Fly.io (20 min)

1. https://fly.io → **Sign up** avec GitHub. **Ajouter une carte bancaire** : il n'y a plus d'offre gratuite pour les nouveaux comptes, et la facturation se fait à l'usage. Compter 2 à 3 $ par mois.
2. **Billing** → alerte de dépense à 10 $ par mois.
3. Sur le Mac : `brew install flyctl`, puis `fly auth login`.
4. Le dev crée l'application (`fly launch --no-deploy`, région `cdg`, nom `epreuve-des-dieux` déjà prévu dans `fly.toml`). Marceau lance ensuite le premier `fly deploy` avec le dev.

### B.3 Relier le domaine à Fly (15 min, puis attendre la propagation)

1. `fly ips list` donne une adresse IPv4 (partagée) et une IPv6.
2. Chez le registrar, zone DNS du domaine :
   - `A` sur `@` → l'adresse IPv4 de Fly ;
   - `AAAA` sur `@` → l'adresse IPv6 de Fly ;
   - `CNAME` sur `www` → `epreuve-des-dieux.fly.dev`.
3. `fly certs add epreuve-des-dieux.fr`, puis `fly certs add www.epreuve-des-dieux.fr`. `fly certs show <domaine>` indique quand le certificat HTTPS est émis : quelques minutes à quelques heures, selon la propagation DNS.
4. Vérifier `https://<domaine>/sante` dans un navigateur.

Plan B gratuit et immédiat, si le DNS traîne : l'adresse `https://epreuve-des-dieux.fly.dev` fonctionne dès le premier déploiement.

### B.4 GitHub (10 min)

1. Créer un dépôt **privé** `epreuve-des-dieux` et y pousser le dépôt local (branche `v4`). La CI des tests et l'analyse des secrets s'activent seules.
2. Les secrets de la sauvegarde viennent à l'étape E.3.

### B.5 Le jour du reveal (6/11 au plus tard)

- Vérifier sur téléphone que `https://<domaine>` affiche le teaser, et seulement lui.
- Donner le lien sur Discord quand Shadoaze le décide.

---

## C. Lot B : Discord (🧑‍💻, 20 min, avant le 3/11, pour l'intégration du 4/11)

### C.1 Le bot : rien à faire pour le site

Le site n'utilise **aucun bot**. « Gardien de la Tour » sert seulement d'application pour la connexion OAuth2 (C.2), et elle n'a pas besoin d'un bot présent sur le serveur. Si le bot d'atelier y est déjà, le laisser tel quel. Dans le portail (onglet Bot), désactiver **Public Bot**.

### C.2 Configurer OAuth2 pour la connexion au site

Dans https://discord.com/developers/applications → « Gardien de la Tour » → onglet **OAuth2** :
1. **Client ID** : c'est l'Application ID, `1564210808509038622`. Il n'est pas secret.
2. **Client Secret** → *Reset Secret* → le copier **une seule fois** dans le gestionnaire de mots de passe. C'est `DISCORD_CLIENT_SECRET`. **Secret** : ne jamais le coller dans Discord, un commit ou une capture d'écran.
3. **Redirects** → *Add Redirect*, une ligne par adresse, **à l'identique**, sans barre finale :
   - `https://<domaine>/auth/discord/retour` (production) ;
   - `http://localhost:8080/auth/discord/retour` (développement sur le Mac).

   Discord refuse toute adresse de retour qui n'est pas dans cette liste. C'est une protection : personne ne peut détourner la connexion vers un autre site.
4. **Rien d'autre à cocher.** Les portées (`identify`, `guilds.members.read`) sont demandées par le site dans l'adresse de connexion. Le « générateur d'URL » du portail ne sert pas ici.

Pourquoi `guilds.members.read` : c'est la portée qui permet au site de lire **l'appartenance au serveur et les rôles** du joueur qui se connecte, avec son propre jeton, sans passer par le bot.

### C.3 Copier les identifiants

Avec le mode développeur (Paramètres utilisateur → Avancés → Mode développeur), faire un clic droit, puis « Copier l'identifiant » :
- le serveur → `DISCORD_GUILD_ID` ;
- le rôle « Administrateur » → `DISCORD_ADMIN_ROLE_IDS` ;
- son propre compte et celui de Shadoaze → `ADMINS_SUPPLEMENTAIRES`, un filet si le rôle était mal réglé.

### C.4 Un serveur de test (5 min)

Créer un petit serveur « Tour – test » avec un rôle « Administrateur », pour que le testeur vérifie les refus (non-membre, non-admin) sans toucher au vrai serveur. Un second compte Discord sert de « joueur ». La **même application** suffit : seul `DISCORD_GUILD_ID` change dans le `.env` de test.

---

## D. Lot B : la base de Duffus (✉️ et 🧑‍💻, avant le 28/10 au matin)

L'auteur a donné son accord, mais **ne peut pas fournir d'export**. On lit donc sa base nous-mêmes, comme le fait son propre site. Méthode, règles de politesse et limites : ARCHITECTURE §6.

### D.1 Message à l'auteur (✉️, à envoyer le 27/10)

> Bonjour, et encore merci pour ton accord ! Pour être transparents sur la façon dont on récupère les données :
> - un script lancé **à la main**, quelques fois au total (avant chaque nouvel étage, au plus une fois par semaine), qui lit tes tables publiques (`guide_ranges`, `quest_list`, `quest_pages`, `dungeon_pages`, `achievements`, `achievement_objectives`, `dofus_list`) avec la clé publique de ton site, à **1 requête par seconde au plus**, avec un User-Agent qui nous identifie ;
> - **jamais** d'appel chez toi pendant que nos joueurs naviguent : tout est copié chez nous, derrière une connexion réservée aux participants ;
> - un « Merci Duffus » avec un lien vers duffus.fr en pied de chaque page.
>
> Est-ce que ça te convient ? Peux-tu me confirmer l'adresse de ta base et la clé publique à utiliser ? Tu préfères qu'on évite certaines tables ou certains horaires ? Et si tu changes la structure de ta base, tu pourrais nous prévenir ? Notre script s'arrêtera proprement de toute façon.

Garder sa réponse écrite. Si elle restreint quelque chose, le noter dans ARCHITECTURE §6.2.

### D.2 La clé et l'adresse (🧑‍💻)

L'adresse du projet Supabase de Duffus et sa **clé publique** (« anon ») : on les demande à l'auteur dans le message D.1 plutôt que de les extraire du code de son site. Les mettre **dans le `.env` local seulement** :

```
DUFFUS_SUPABASE_URL=https://<projet>.supabase.co
DUFFUS_SUPABASE_CLE=<clé anon publique>
```

Elles ne vont **ni sur Fly ni dans le dépôt**. Le site n'en a jamais besoin, puisque seul le script d'aspiration, lancé depuis le Mac, les utilise.

Si l'auteur n'a pas répondu le **30/10 au soir**, c'est un déclencheur du plan de repli (`LOTS.md`, lot B).

### D.3 Lancer le relevé, puis l'aspiration (🧑‍💻 avec le dev)

- Le 28/10 : `uv run python -m epreuve.duffus releve` (chantier B0), pour relever le schéma.
- Le 29/10 : `uv run python -m epreuve.duffus aspirer`, puis la relecture du `git diff` des extraits. Ces extraits servent aux tests du lot B et à la décision de repli du 31/10.
- Le 4/11 : `uv run python -m epreuve.contenu construire --etage 0` puis `--etage 1`, pour la relecture de Shadoaze.
- Les 7 et 8/11 : une nouvelle aspiration seulement si le guide a changé (au plus une par semaine), puis `construire --etage N` pour chaque étage.

---

## E. Lot B : base de données et sauvegarde (🧑‍💻, 30 min, avant le 3/11)

### E.1 Supabase

1. https://supabase.com → se connecter avec GitHub → **New project** : nom `epreuve-des-dieux`, région **West EU (Paris)**, offre **Free**, mot de passe de base **long, généré, composé uniquement de lettres et de chiffres** (un caractère spécial casserait l'adresse de connexion), rangé dans le gestionnaire de mots de passe.
2. **Connect** → *Session pooler* (port 5432). Copier l'adresse, y mettre le mot de passe, et remplacer `postgresql://` par `postgresql+asyncpg://`. C'est `DATABASE_URL`. **Secret.**
3. **Le déposer tout de suite sur Fly** (`fly secrets set DATABASE_URL=…`), même pendant le lot A. `/sante` interrogera la base toutes les 30 secondes, ce qui empêche Supabase d'endormir le projet gratuit après 7 jours sans activité.

### E.2 Postgres local pour les tests (dès le 28/10, les devs en ont besoin)

Docker Desktop, puis :

```
docker run -d --rm --name epreuve-pg-test -p 54329:5432 -e POSTGRES_PASSWORD=test -e POSTGRES_DB=epreuve_test postgres:17-alpine
```

Sans ce conteneur, les tests marqués `db` sont sautés. C'est ce qui explique les 62 échecs relevés le 27/10 sur `main`.

### E.3 Sauvegarde chiffrée

1. `brew install age`, puis `age-keygen -o ~/cle-sauvegarde-epreuve.txt`. La ligne `# public key: age1…` est la clé **publique**. Le fichier, lui, est la clé **privée** : à ranger hors du dépôt, dans le gestionnaire de mots de passe.
2. GitHub → Settings → Secrets and variables → Actions : `DATABASE_URL` (la même adresse) et `AGE_RECIPIENT` (la clé publique `age1…`).
3. Une fois les premières données en base, lancer l'action « sauvegarde » à la main et tester la restauration une fois (commande en tête de `.github/workflows/sauvegarde.yml`).

---

## F. Déposer les réglages sur Fly (🧑‍💻 avec le dev, le 10/11)

```
fly secrets set DATABASE_URL=… DISCORD_CLIENT_SECRET=… DISCORD_GUILD_ID=… \
  DISCORD_ADMIN_ROLE_IDS=… ADMINS_SUPPLEMENTAIRES=…
```

`SITE_MODE=auto`, `SITE_OUVERT_LE`, `SITE_URL` et `DISCORD_CLIENT_ID` sont dans `fly.toml` (non secrets). Les clés Duffus et le jeton du bot ne vont **pas** sur Fly.

---

## G. Le jour J, vendredi 13/11 (🧑‍💻)

- **16 h 30** : `fly status` (machine en marche), `https://<domaine>/sante` en `ok`, et connexion admin vérifiée.
- **16 h 50** : `fly secrets set TEASER_LIEN_ENTRER=https://<domaine>/`. Le bouton « Entrer dans la tour » apparaîtra à la fin du compte à rebours.
- **17 h 00** : le mode `auto` bascule seul.
- **17 h 01** : vérifier sur téléphone que l'accueil remplace le teaser et que la connexion fonctionne.
- **En cas de souci** : `fly secrets set SITE_MODE=teaser` remet le teaser en quelques secondes.

---

## Récapitulatif par date

### Le 27/10
- [ ] A.1 Questions envoyées à Shadoaze
- [ ] D.1 Message envoyé à l'auteur de Duffus
- [ ] B.1 Domaine acheté

### Avant le 28/10 au matin (chantier B0)
- [ ] D.2 `DUFFUS_SUPABASE_URL` et `DUFFUS_SUPABASE_CLE` dans `.env` (sinon : plan de repli si rien le 30/10 au soir)
- [ ] E.2 Docker pour les tests locaux

### Le 29/10
- [ ] D.3 Première aspiration Duffus, extraits relus

### Avant le 2/11 (lot A)
- [ ] B.2 Compte Fly.io, carte, alerte de dépense, `flyctl`
- [ ] B.3 DNS du domaine vers Fly, certificats émis
- [ ] B.4 Dépôt GitHub privé
- [ ] E.1 Projet Supabase et `DATABASE_URL` déposé sur Fly

### Avant le 3/11 (intégration du lot B le 4/11)
- [ ] C.2 Client Secret et adresses de retour OAuth2
- [ ] C.3 Identifiants copiés
- [ ] C.4 Serveur de test

### Avant le 6/11
- [ ] B.5 Teaser vérifié sur téléphone, lien donné quand Shadoaze le décide

### Avant le 7/11 (construction des étages)
- [ ] Réponses de Shadoaze à Q1 et Q2, ou défauts acceptés
- [ ] D.3 Étages 0 et 1 relus par Shadoaze, puis étages 0 à 25 construits

### Avant le 10/11 (lot B)
- [ ] E.3 Sauvegarde chiffrée (clé age, secrets GitHub)
- [ ] F Réglages déposés sur Fly
- [ ] A.2 Liste officielle collée dans l'admin

### Le 13/11
- [ ] G Le déroulé du jour J
