# L'Épreuve des Dieux : prérequis

Version 2, 25/10/2026 (après les réponses de Shadoaze). Ce que **Marceau** doit faire lui-même, et ce qu'il doit **demander à Shadoaze**, avant chaque jalon. Les étapes sont concrètes et dans l'ordre. Comptez environ 1 h 30 pour la partie « avant le jalon bêta ».

Légende : 🧑‍💻 Marceau seul · 🤝 avec Shadoaze · ⏳ peut attendre le jalon lancement.

---

## A. À demander à Shadoaze (le plus tôt possible)

### A.1 Les questions sur le règlement (🤝)

✅ **Fait.** Les 14 questions de `QUESTIONS-SHADOAZE.md` ont reçu leurs réponses (`REPONSES-SHADOAZE.md`), reportées dans `SPEC.md` §8. **Reste à faire** : soumettre à Shadoaze les **questions de suivi** de `SPEC.md` §8 bis (a à l). Ce sont surtout des confirmations, puisqu'une décision par défaut est déjà appliquée à chacune. Il faut aussi lui proposer de mettre à jour le salon des règles Discord (jauge à points, dates du 30/10 et du 13/11 à 17 h).

Plus tard, dans un second temps : lui demander d'ajouter le bot au serveur (section C), de créer #validations-admin et #bêta-site, et de fournir la liste des inscrits (A.4).

### A.2 Le contenu de l'étage 0, à faire confirmer (🤝)

Vérifié sur DofusDB le 25/10/2026 :
- cap de niveau **20**, **sans tolérance automatique** (un dépassement involontaire est jugé par un admin) ;
- donjon **Crypte de Kardorim** (DofusDB 90) ;
- « full succès » = **5 succès** : Crypte de Kardorim, Kardorim (Duo), Kardorim (Zombie), Kardorim (Premier), Kardorim (Spécial) ;
- « toutes les quêtes d'Incarnam » = **24 quêtes** de la catégorie Incarnam du journal de quêtes ;
- **jauge à points** : palier 1 = Kardorim vaincu, palier 2 = full succès, palier 3 = full succès et toutes les quêtes ; seuil **75 %** du maximum ;
- ouverture le **vendredi 30/10 à 17:00**, étage 1 bloqué jusqu'au **vendredi 13/11 à 17:00** (heure de Paris) ;
- nom de l'étage : « Le Seuil », repris de la maquette (à lui faire valider ou remplacer).

### A.3 Le contenu de l'étage 1 (🤝 ⏳)

À obtenir idéalement **au plus tard le 6/11**, pour l'importer et le tester avant le 13/11 : numéro, nom, level cap, donjons (pour les paliers 1 et 2), quêtes de la tranche (palier 3), et pourcentage du seuil s'il change. L'étage reste scellé, invisible sur le site, jusqu'à son ouverture.

### A.4 Le registre des grimpeurs (🤝)

Pour chaque inscrit : **pseudo en jeu**, **classe** (une des 19), **difficulté** (Aventurier, Éclaireur ou Collectionneur), et **pseudo Discord**, **indispensable** désormais : un grimpeur doit être relié à son compte pour déclarer ses quêtes avec `/quetes`. Préciser aussi qui s'inscrit **après** le 30/10 à 17:00 : ces joueurs seront retardataires. Le plus simple : Shadoaze les saisit lui-même avec `/grimpeur ajouter` le jour de la mise en service, en 10 minutes, avec Marceau à côté pour la première fois.

### A.5 Les volontaires de la bêta (🤝)

1 ou 2 admins et 4 à 6 joueurs qui acceptent de donner leur avis dans #bêta-site (voir `LOTS.md`, jalon bêta-test).

### A.6 Message de transparence à publier (🤝 ⏳, avant d'activer l'IA)

> 🤖 **Le bot de la Tour** : à partir du [date], les screens postés dans #screen-validation sont lus par une IA (Claude, d'Anthropic) qui pré-remplit la validation. **C'est toujours un admin qui valide.** Le bot garde une copie du screen comme preuve. Seuls ton pseudo en jeu, ta classe et ta progression apparaissent sur le site public.

---

## B. Discord : créer l'application (🧑‍💻, 15 min)

1. **Activer le mode développeur** dans Discord, pour pouvoir copier les identifiants : Paramètres utilisateur → Avancés → **Mode développeur**. Un clic droit sur un serveur, un salon ou un rôle propose alors « Copier l'identifiant ».
2. Aller sur **https://discord.com/developers/applications** → **New Application** → nom : « Gardien de la Tour » (ou autre) → accepter les conditions.
3. Onglet **General Information** : noter l'**Application ID**. Il n'est pas secret.
4. Onglet **Bot** :
   - **Reset Token**, puis copier le jeton **une seule fois** dans le gestionnaire de mots de passe. C'est `DISCORD_TOKEN`. **Il est secret** : quiconque l'a contrôle le bot. Ne jamais le coller dans Discord, dans un commit ou dans une capture.
   - **Public Bot** : le laisser **activé** le temps que Shadoaze invite le bot, puis le **désactiver** (étape C.4).
   - **Privileged Gateway Intents** : tout laisser **désactivé** pour le jalon bêta. Au jalon lancement, activer **Message Content Intent** (⏳). Les deux autres (Presence, Server Members) restent désactivés : on n'en a pas besoin.
5. Onglet **Installation** :
   - Installation Contexts : cocher **Guild Install** uniquement (décocher User Install).
   - Install Link : **None**. On utilise notre propre lien, plus précis.
6. **Créer un serveur Discord de test** à soi (« Tour – test ») avec les salons #screen-validation, #validations-admin, #annonces et un rôle « Administrateur ». C'est là que les devs et le testeur essaient tout avant le vrai serveur.
7. **Créer une seconde application** « Gardien de la Tour (test) » en refaisant les étapes 2 à 5, avec son propre jeton. Le bot de production ne répond que sur son serveur et quitte les autres : il faut donc un bot distinct pour le serveur de test. L'inviter sur le serveur de test avec le lien ci-dessous.

### Le lien d'invitation

Remplacer `APPLICATION_ID` par l'identifiant de l'étape 3 :

```
https://discord.com/oauth2/authorize?client_id=APPLICATION_ID&scope=bot+applications.commands&permissions=117824
```

`117824` est la somme exacte des 6 permissions nécessaires : Voir les salons, Envoyer des messages, Intégrer des liens, Joindre des fichiers, Voir l'historique des messages, Ajouter des réactions (détail et justification : `ARCHITECTURE.md` §9). Le lien est valable pour tous les jalons : on n'aura pas à refaire inviter le bot. **Aucune permission Administrateur.**

Tester d'abord le lien sur le serveur de test (étapes 6 et 7), avec l'application de test.

---

## C. Faire inviter le bot sur le vrai serveur (🤝, 5 min avec Shadoaze)

1. Envoyer le lien à Shadoaze. Il l'ouvre, choisit le serveur « L'Épreuve des Dieux », vérifie que la liste des permissions correspond aux 6 ci-dessus, puis clique sur **Autoriser**.
2. **Salons** : #screen-validation doit être visible par le bot (c'est le cas si le salon est public). Pour **#validations-admin**, qui est privé : Modifier le salon → Permissions → ajouter le rôle du bot (il porte le nom de l'application) avec Voir le salon, Envoyer des messages, Intégrer des liens, Joindre des fichiers et Voir l'historique.
3. **Visibilité des commandes admin** : Paramètres du serveur → **Intégrations** → le bot → pour les commandes `/grimpeur`, `/valider`, `/annuler`, `/etage` (puis `/refuser` et `/ia` au lancement), autoriser le rôle **« Administrateur »** (Shadoaze, Q6). Par défaut, seuls ceux qui ont « Gérer le serveur » les voient. La commande joueur **`/quetes`** reste visible de **tous**, ce qui est le réglage par défaut, et l'option `pour` est vérifiée par le bot. `/moi` et `/niveau` s'y ajoutent au lancement. Le bot revérifie de toute façon le rôle à chaque commande.
4. Revenir au portail développeur → Bot → **désactiver Public Bot**. Plus personne ne peut ajouter le bot ailleurs, et le bot quitterait de toute façon un serveur inconnu.
5. Récupérer, avec un clic droit puis « Copier l'identifiant » :
   - l'identifiant du serveur → `DISCORD_GUILD_ID`
   - le rôle « Administrateur » → `DISCORD_ADMIN_ROLE_ID`
   - #screen-validation → `DISCORD_SCREEN_CHANNEL_ID`
   - #validations-admin → `DISCORD_ADMIN_CHANNEL_ID` (⏳)
   - le salon d'annonces → `DISCORD_ANNONCE_CHANNEL_ID` (⏳)

   Faire de même sur le serveur de test : chaque environnement a ses propres identifiants.

---

## D. Comptes d'hébergement (🧑‍💻, 30 min)

### D.1 Supabase (base de données, gratuit)

1. https://supabase.com → **Start your project** → se connecter avec GitHub.
2. **New project** : nom `epreuve-des-dieux`, région **West EU (Paris)**, mot de passe de base **long et généré**, à conserver dans le gestionnaire de mots de passe. Offre **Free**.
3. **Connect** → onglet *Connection string* → choisir **Session pooler** (port 5432). Copier l'adresse, remplacer `[YOUR-PASSWORD]` par le mot de passe du projet, et remplacer `postgresql://` par `postgresql+asyncpg://`. Choisir à l'étape 2 un mot de passe composé uniquement de lettres et de chiffres, sinon un caractère spécial casserait l'adresse. C'est `DATABASE_URL`. **Secret.**
4. Créer de la même façon un second projet, **`epreuve-test`**, pour les tests d'intégration et le serveur Discord de test. L'offre gratuite permet 2 projets actifs.
5. ⏳ Jalon lancement : Storage → **New bucket** `preuves`, **privé**. Settings → API → copier **Project URL** (`SUPABASE_URL`) et la clé **service_role** (`SUPABASE_SERVICE_KEY`, **secret**, jamais côté navigateur).

À savoir : un projet gratuit est mis en pause après 7 jours sans activité. Le bot l'utilise en continu, donc ça ne devrait pas arriver. Si ça arrive, on le relance d'un clic depuis le tableau de bord.

### D.2 Fly.io (hébergement, environ 4 $ par mois)

1. https://fly.io → **Sign up** (avec GitHub). **Ajouter une carte bancaire** : il n'y a plus d'offre gratuite pour les nouveaux comptes, et la facturation se fait à l'usage.
2. Dans Billing, régler une **alerte de dépense** (par exemple 10 $ par mois).
3. Sur le Mac : `brew install flyctl`, puis `fly auth login`.
4. Le dev crée l'application (`fly launch --no-deploy`, région `cdg`). Marceau y dépose ensuite les secrets :
   `fly secrets set DISCORD_TOKEN=… DATABASE_URL=… DISCORD_GUILD_ID=… DISCORD_ADMIN_ROLE_ID=… DISCORD_SCREEN_CHANNEL_ID=…`
   Les secrets sont chiffrés chez Fly. Ils ne sont jamais écrits dans le dépôt.

### D.3 GitHub (code et sauvegarde, gratuit)

1. Créer un dépôt **privé** `epreuve-des-dieux` et y pousser le dépôt local.
2. Settings → Secrets and variables → Actions → **New repository secret** `DATABASE_URL`. La sauvegarde nocturne s'en sert.

### D.4 Anthropic (IA, ⏳ jalon lancement, environ 5 $ prépayés pour plusieurs mois)

1. https://console.anthropic.com → créer un compte, puis l'organisation.
2. **Billing** → acheter **5 $ de crédits**. Au rythme estimé (0,10 à 2 $ par mois), cela dure plusieurs mois.
3. **Limits** → fixer une **limite de dépense mensuelle** à 5 $. C'est le garde-fou contre une boucle qui s'emballerait.
4. Créer un **workspace** « epreuve-des-dieux », puis **API Keys** → *Create Key* dans ce workspace. C'est `ANTHROPIC_API_KEY`. **Secret.** Le déposer avec `fly secrets set` et dans le `.env` local.

---

## E. Poste de travail (🧑‍💻, 10 min)

- **uv** : `brew install uv` (gère Python 3.12 et les dépendances).
- **Docker Desktop** (facultatif) : pour les tests de base de données en local. Sans Docker, ces tests visent le projet Supabase `epreuve-test`.
- Un fichier **`.env`** à la racine du dépôt, à partir de `.env.example`, **jamais commité** (`.gitignore` l'exclut dès le premier commit) : jeton du bot **de test**, base `epreuve-test`, identifiants du serveur de test.

---

## Récapitulatif par jalon

### Avant le jalon bêta

- [x] A.1 : réponses aux 14 questions (reçues le 25/10)
- [ ] A.1 : questions de suivi du §8 bis soumises à Shadoaze (non bloquant : les décisions par défaut sont appliquées)
- [ ] A.2 : contenu de l'étage 0 confirmé
- [ ] A.4 : liste des inscrits, ou créneau de 15 min avec Shadoaze pour la saisie
- [ ] A.5 : volontaires de la bêta
- [ ] B : application Discord créée, jeton rangé, serveur de test prêt
- [ ] C : bot invité sur le vrai serveur, salons et rôle réglés, identifiants copiés, Public Bot désactivé
- [ ] D.1 : projets Supabase `epreuve-des-dieux` et `epreuve-test`
- [ ] D.2 : compte Fly.io avec carte et alerte de dépense, `flyctl` installé
- [ ] D.3 : dépôt GitHub privé et secret `DATABASE_URL`
- [ ] E : uv installé, `.env` local

### Avant le jalon lancement

- [ ] A.1 : confirmations du §8 bis reçues, ou décisions par défaut acceptées
- [ ] A.3 : contenu de l'étage 1
- [ ] A.6 : message de transparence publié
- [ ] B.4 : **Message Content Intent** activé dans le portail
- [ ] C.3 : visibilité des nouvelles commandes (`/refuser`, `/ia`) pour le rôle admin
- [ ] C.5 : identifiants de #validations-admin et du salon d'annonces
- [ ] D.1 : bucket `preuves` et clés Storage
- [ ] D.4 : compte Anthropic, 5 $ de crédits, limite mensuelle, clé API
