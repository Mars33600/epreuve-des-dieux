# L'Épreuve des Dieux : spécification produit

Version 2, 25/10/2026. Sources, par ordre de priorité :
1. `docs/REPONSES-SHADOAZE.md` : les réponses de l'organisateur, qui priment sur tout le reste ;
2. `docs/REGLES.md` : le règlement ;
3. `docs/maquette-v1.html` : la maquette validée, point de départ visuel.

**Ce qui change par rapport à la version 1** : les trois jauges à fractions (1/4, 1/2, 3/4) sont remplacées par **une jauge unique à points**, calculée d'après la difficulté choisie par chaque grimpeur (§5). Les quêtes deviennent **déclaratives** : c'est notre lecture de la phrase de Shadoaze « pour les quêtes on se basera sur les paroles des gens car […] compliqué à vérifier », à confirmer (§8 bis, l). Le cap n'a plus de tolérance automatique. Les dates passent au **vendredi 30/10 à 17:00** et au **vendredi 13/11 à 17:00**. Les nouveaux arrivants ne comptent qu'une fois qu'ils ont rattrapé les autres.

Ce document dit **quoi** construire et **pourquoi**. Le **comment** technique est dans `ARCHITECTURE.md`, le découpage dans le temps dans `LOTS.md`, les démarches à faire dans `PREREQUIS.md`.

**Calendrier** : aucune date n'est imposée à l'outil. On vise la meilleure qualité, livrée le plus vite possible. Les dates du jeu servent de **repères indicatifs** : l'étage 0 ouvre en jeu le **vendredi 30/10/2026 à 17:00**, et l'étage 1 reste bloqué jusqu'au **vendredi 13/11/2026 à 17:00** (heure de Paris), même si la jauge est pleine. Entre les deux se déroulent la mise en place et le bêta-test. Le **lot 1** couvre tout le cœur du produit et se livre en deux jalons :
- **bêta** : registre, saisie par commande, déclaration des quêtes, site avec la jauge et la répartition des classes ;
- **lancement** : clic droit, retour au joueur, ouverture d'étage, assistance IA.

Le **lot 2** apporte le confort. Voir `LOTS.md`.

---

## 1. Le produit en une phrase

Un bot Discord qui enregistre la progression des grimpeurs, et un site public en lecture seule qui montre où en est la communauté sur l'étage en cours. Les admins valident les donjons et succès, en s'appuyant sur une IA qui lit les screens, et les joueurs déclarent leurs quêtes. Le site montre **une jauge de points**, les grimpeurs, les classes représentées et les dernières validations.

### Ce qui est décidé (ne pas rouvrir)

| Décision | Conséquence pour le produit |
|---|---|
| La progression est collective, pas une course. | Le cœur du site, c'est la jauge de l'étage. Les fiches individuelles existent, sans classement ni podium. |
| Site public en lecture seule, saisie par Discord. | Pas de compte ni de mot de passe sur le site. Toute écriture passe par une commande Discord. |
| Validation des donjons et succès assistée par IA, humain dans la boucle. | L'IA propose et un admin décide. Aucune validation de donjon ou de succès n'entre dans la jauge sans un clic d'admin. |
| **Quêtes déclaratives** : notre lecture de la réponse de Shadoaze à Q4, « pour les quêtes on se basera sur les paroles des gens car […] compliqué à vérifier ». À confirmer (§8 bis, l). | Le joueur déclare ses quêtes lui-même. Aucune preuve n'est exigée, mais il peut joindre un screen s'il en a un. Un admin peut annuler une déclaration. |
| **Jauge unique à points** (Shadoaze, Q1 et Q7). | Chaque grimpeur rapporte de 0 à 3 points selon le palier atteint. Le maximum dépend des difficultés choisies, et le seuil vaut 75 % de ce maximum, réglable par les admins. |
| Les grimpeurs en pause ne comptent pas. | Ils sortent du maximum et des points. |
| **Ouverture d'étage manuelle**, étages fermés cachés, refus non publics (Shadoaze, Q12 à Q14). | Le bot prévient, un admin vérifie et ouvre. Les étages non ouverts restent des « ? ». Un refus n'apparaît jamais sur le site. |

### Ce que le produit ne fait pas

- Il ne lit pas la progression dans le jeu : aucune API Ankama ne la donne. **Les preuves des donjons et succès sont les screens.**
- Il ne valide jamais seul.
- Il n'envoie pas de MP de relance aux joueurs.
- Il ne remplace pas le jugement de l'organisateur sur la triche ni sur l'inactivité.
- Il ne vérifie ni le serveur de jeu (Kourial), ni le personnage neuf, ni l'absence de PL par un niveau 200. Le règlement l'exige, mais seul l'œil de l'admin sur le screen en juge (§8, Q10).

---

## 2. Vocabulaire

| Terme | Sens dans ce projet |
|---|---|
| **Grimpeur** | Un joueur inscrit à l'événement, identifié par son **pseudo en jeu**. Il est relié à son compte Discord pour pouvoir déclarer ses quêtes. |
| **Difficulté** | Le mode choisi par le grimpeur : *Aventurier* (Easy), *Éclaireur* (Medium) ou *Collectionneur* (Hard). Elle fixe ses **points visés** : 1, 2 ou 3. Seul un admin peut la changer, à la demande du joueur. |
| **Statut** | `actif`, `pause` ou `exclu`. |
| **Retardataire** | Un grimpeur actif arrivé après l'ouverture de l'étage en cours, qui n'a pas encore « rattrapé les autres », c'est-à-dire **atteint le cap** de cet étage. Il n'entre pas dans le maximum de la jauge. Un admin peut forcer son inclusion. |
| **Grimpeur compté** | Actif, et pas retardataire. Il entre dans le maximum. |
| **Étage** | Une épreuve, numérotée à partir de 0. Elle porte un **level cap**, un **pourcentage de seuil** (75 par défaut), une date d'ouverture et une **date plancher** avant laquelle l'étage suivant ne peut pas s'ouvrir. |
| **Contenu** | Une chose réalisable sur un étage : un succès de donjon, une quête, ou un « lot de quêtes » (par exemple « Toutes les quêtes d'Incarnam »). Chaque contenu est relié, quand c'est possible, à son identifiant DofusDB. |
| **Palier** | Un niveau d'accomplissement de l'étage, de rang 1, 2 ou 3. Chaque palier ajoute des contenus aux précédents. **Palier 1** : tous les donjons de l'étage vaincus. **Palier 2** : full succès de tous les donjons de l'étage. **Palier 3** : en plus, toutes les quêtes de la tranche de niveau. |
| **Points d'un grimpeur** | Le rang du plus haut palier atteint, **en respectant l'ordre** : on ne passe pas au palier 3 sans le palier 2. Ce nombre va de 0 à 3. |
| **Jauge** | La somme des points des grimpeurs, comparée au **seuil**. Le seuil vaut ⌈ pourcentage × maximum ⌉, et le maximum est la somme des points visés par les grimpeurs comptés. |
| **Preuve** | Un screen posté dans #screen-validation : le lien du message Discord et, dès le lancement, une copie de l'image. Elle est facultative pour une déclaration de quêtes. |
| **Validation** | Le fait qu'**un grimpeur** a réalisé **un contenu**. Pour un donjon ou un succès, elle porte un niveau et une preuve, et un admin la décide. Pour une quête, c'est une **déclaration** du joueur. Elle peut être acceptée, refusée ou annulée. |
| **Proposition IA** | Le pré-remplissage d'une ou plusieurs validations à partir d'un screen (lot 1, jalon lancement). Ce n'est pas une validation tant qu'un admin ne l'a pas confirmée. |
| **Journal** | L'historique horodaté de tout ce qui change : inscriptions, pauses, changements de difficulté, inclusions, validations, déclarations, annulations, ouvertures d'étage, changements de seuil. |

---

## 3. Acteurs

| Acteur | Qui | Ce qu'il peut faire | Par où |
|---|---|---|---|
| **Visiteur** | N'importe qui ayant le lien | Consulter l'étage en cours, la jauge, les classes, les grimpeurs et les dernières validations | Site public |
| **Grimpeur** | Joueur inscrit, relié à son compte Discord | Poster ses screens et **déclarer ses quêtes**. Dès le lancement : déclarer son niveau et consulter sa fiche | #screen-validation, `/quetes`, `/moi`, `/niveau` |
| **Admin** | Les membres du rôle Discord **« Administrateur »** (Shadoaze, Q6) | Gérer le registre (dont la difficulté et l'inclusion des retardataires), valider, refuser ou annuler, ouvrir un étage, régler le seuil | Commandes Discord réservées, boutons sur les propositions IA |
| **Bot** | L'application Discord | Enregistrer, calculer, afficher, signaler les anomalies, et analyser les screens dès le lancement | Serveur Discord |
| **IA (Claude Haiku)** | Modèle vision appelé par le bot | Lire un screen et proposer contenu, membres et niveaux | Appel API, jamais directement dans Discord |
| **Mainteneur** | Marceau | Déployer, importer le contenu des étages depuis DofusDB, corriger les données en dernier recours | Hébergeur, console de la base de données |

---

## 4. Parcours

### 4.1 Le grimpeur fait valider un donjon ou un succès

Sans IA (jalon bêta, ou IA coupée) :
1. Le grimpeur termine un donjon ou un succès **avec d'autres grimpeurs**, sans dépasser le cap.
2. Il poste le screen dans #screen-validation, comme aujourd'hui. Rien ne change pour lui.
3. Un admin le valide (§4.3). Dès le lancement, le bot pose ✅ sur le message du grimpeur, ou ❌ en cas de refus. C'est le seul retour au grimpeur : pas de MP.
4. Le site se met à jour dans la minute : jauge, fiche et fil.

Avec IA (jalon lancement) :
1. Le grimpeur poste le screen. Le bot pose 👀 sur son message : « vu, en cours d'analyse ».
2. Le bot copie l'image, l'envoie à l'IA et publie une **proposition** dans le salon privé des admins.
3. Quand un admin tranche, 👀 est remplacé par ✅ ou ❌.

### 4.2 Le grimpeur déclare ses quêtes (dès la bêta)

`/quetes contenu:<choix ou « toutes »> [preuve:<lien d'un screen>]`
- Le grimpeur doit être relié à son compte Discord. Sinon, le bot lui répond « Demande à un admin de relier ton compte » et n'écrit rien.
- `contenu` propose les quêtes, ou lots de quêtes, de l'étage en cours que le grimpeur n'a pas encore déclarées. « toutes » déclare d'un coup tout ce qui reste.
- **Aucune preuve ni aucun niveau ne sont exigés.** C'est notre lecture de la phrase de Shadoaze « pour les quêtes on se basera sur les paroles des gens car […] compliqué à vérifier », en attendant sa confirmation (§8 bis, l). Si le joueur a un screen, il peut en donner le lien avec l'option `preuve`. Le lien est alors gardé avec la déclaration et visible des admins. La déclaration est enregistrée tout de suite comme validation acceptée, avec la source `declaration`. Elle apparaît dans le fil public : « Brindille a déclaré avoir terminé « Toutes les quêtes d'Incarnam » ».
- Un admin peut l'annuler avec `/annuler`, et peut déclarer pour un grimpeur non relié avec `/quetes pour:<pseudo>`.
- Les quêtes ne rapportent des points que si le palier 2 est atteint (§5).

### 4.3 L'admin valide un donjon ou un succès

**Jalon bêta : saisie par commande slash.**
`/valider contenu:<choix> grimpeur1:<pseudo> niveau1:<n> [grimpeur2 niveau2 … grimpeur8 niveau8] [preuve:<lien du message>]`
- `contenu` et les pseudos se complètent automatiquement : on tape « Kar » et Discord propose « Kardorim vaincu ». Seuls les succès de donjon sont proposés, puisque les quêtes passent par `/quetes`.
- Une commande crée **une validation par grimpeur**. Un groupe de 4 donne 4 validations qui partagent la même preuve.
- Contrôles **bloquants** (rien n'est écrit, la réponse éphémère liste tous les motifs) :
  - grimpeur inconnu, en pause ou exclu ;
  - contenu hors de l'étage en cours ;
  - validation réalisée avant l'ouverture ;
  - validation acceptée déjà présente.
- **Dépassement du cap** (Shadoaze, Q9 : pas de marge, mais une tolérance au cas par cas pour un dépassement involontaire) : ce n'est **pas** un refus automatique. Le bot affiche un avertissement, par exemple « Mirelune : niveau 21, au-dessus du cap 20 », et deux boutons : **Accepter malgré le dépassement** et **Annuler la saisie**. Accepter enregistre les validations comme `forcée`, avec le nom de l'admin au journal. L'admin tranche.
- Le bot répond avec un récapitulatif et les numéros des validations créées, qui servent à annuler.
- `/annuler validation:<numéro> motif:<texte>` passe une validation, ou une déclaration, en « annulée ». Elle sort de la jauge, mais reste au journal.

**Jalon lancement : refus direct.** `/refuser preuve:<lien du message> motif:<texte>` refuse un screen sans passer par une proposition IA. Le joueur voit ❌ et le motif en réponse.

**Jalon lancement : depuis le message lui-même.** Clic droit sur le screen → Applications → « Valider ce screen ». Le bot ouvre le formulaire de saisie avec la preuve déjà remplie, et copie l'image.

**Jalon lancement : depuis la proposition IA.** Dans le salon admin, le bot publie une carte avec le screen, le contenu détecté, les membres reconnus avec leurs niveaux, et les anomalies. Les anomalies sont de deux sortes :
- **bloquantes**, en rouge : un membre du groupe qui n'est pas grimpeur (Shadoaze, Q10 : la validation est refusée), un grimpeur en pause, un doublon ;
- **à trancher**, en orange : un dépassement de cap.

Trois boutons :
- **Valider** : possible seulement sans anomalie bloquante. Un dépassement de cap demande la même confirmation qu'avec `/valider`.
- **Corriger** : la saisie s'ouvre pré-remplie, l'admin ajuste puis valide.
- **Refuser** : un motif est demandé, et le grimpeur voit ❌.

Un seul admin suffit. Le premier clic l'emporte, et les boutons se désactivent ensuite.

### 4.4 Le visiteur consulte le site

Une seule page, fidèle à la maquette (mise à jour en version jauge unique) :
1. **En-tête** : titre et compte à rebours, vers l'ouverture de l'étage 0 (30/10 à 17:00), puis vers la date plancher de l'étage suivant (13/11 à 17:00).
2. **La tour** : l'étage en cours mis en avant, les étages passés en dessous, les étages non ouverts **cachés** au-dessus, marqués « ? » (Q14). On n'affiche pas le nombre d'étages.
3. **L'étage en cours** :
   - le cap, les donjons et la zone de quêtes ;
   - **la jauge** : une barre remplie à min(points ÷ maximum, 100 %), avec un repère au seuil (75 %), et le texte « 14 points sur 18 requis, il en manque 4 » ;
   - le **détail du maximum** : « Maximum 24 points : 4 Collectionneurs × 3 + 4 Éclaireurs × 2 + 4 Aventuriers × 1. Seuil : 75 % » ;
   - le **détail des points par palier** : « 9 grimpeurs ont vaincu le Kardorim, 5 ont le full succès, 2 ont aussi fini les quêtes » ;
   - le **verdict** : « L'étage 1 s'ouvre quand la jauge atteint le seuil, et pas avant le vendredi 13 novembre à 17 h. 12 grimpeurs comptés, 1 en pause, 1 retardataire ».
4. **Qui peut faire avancer la jauge** (lot 2) : suggestions d'entraide calculées.
5. **Les classes de la guilde** : la répartition des grimpeurs actifs sur les 19 classes de Dofus 3 (Féca, Osamodas, Enutrof, Sram, Xélor, Ecaflip, Eniripsa, Iop, Crâ, Sadida, Sacrieur, Pandawa, Roublard, Zobal, Steamer, Eliotrope, Huppermage, Ouginak, Forgelance).
   - Les 19 classes sont toujours affichées, dans l'ordre du jeu, avec leur nombre de grimpeurs.
   - Les classes que **personne ne joue encore** sont mises en évidence (« Personne encore »). But : en monocompte, chacun ne joue qu'un personnage. Un nouveau venu voit d'un coup d'œil ce qui manque au groupe.
   - Les grimpeurs en pause sont indiqués à part (« + 1 en pause »). Les exclus n'apparaissent pas.
   - Lecture par rôle : au lot 2, si Shadoaze fournit la grille (§8 bis).
6. **Les grimpeurs** : cartes avec :
   - pseudo, difficulté, classe ;
   - **points obtenus sur points visés** (« 2 / 3 ») ;
   - niveau connu par rapport au cap, avec « Dépasse le cap » en orange au-delà ;
   - statut : actif, en pause, ou **retardataire** (« Rattrape le groupe ») ;
   - trois marques : Donjons, Full succès et Quêtes (« déclarées »). Une marque montre que ses contenus sont faits. Les points, eux, suivent l'ordre des paliers : un grimpeur peut avoir la marque Quêtes et seulement 1 point.

   Filtres par difficulté. Tri : actifs d'abord, puis ordre alphabétique. **Pas de tri par score.** Clic sur une carte : fiche en lecture seule.
7. **Dernières validations** : le fil public du journal (validations acceptées, déclarations de quêtes, inscriptions, pauses, ouvertures d'étage). **Jamais de refus** (Q12).

Le « mode admin » de la maquette **disparaît du site** : l'administration se fait dans Discord.

### 4.5 L'admin gère le registre des grimpeurs

Inscription : un MP à l'organisateur avec pseudo IG et difficulté. L'admin reporte l'inscription dans le bot :
- `/grimpeur ajouter pseudo classe difficulte [membre:@discord]`. Si l'étage 0 est déjà ouvert, le grimpeur est créé **retardataire**. Le bot le dit dans sa réponse et rappelle `/grimpeur inclure`.
- `/grimpeur modifier pseudo [nouveau_pseudo] [classe] [difficulte] [niveau] [membre]`. Un **changement de difficulté** est inscrit au journal, avec l'ancienne et la nouvelle valeur, et **recalcule immédiatement** le maximum et le seuil (Shadoaze, Q1). La réponse affiche l'effet : « Maximum 24 → 25, seuil 18 → 19 ».
- `/grimpeur inclure pseudo [motif]` : fait entrer un retardataire dans le maximum avant qu'il ait atteint le cap.
- `/grimpeur pause pseudo [motif]` et `/grimpeur reprendre pseudo`.
- `/grimpeur exclure pseudo motif` : demande une confirmation. L'exclusion est réversible par `/grimpeur reprendre`.
- `/grimpeur voir pseudo` : fiche complète, avec la **date de dernière activité** (dernière validation, déclaration ou mise à jour de niveau), en réponse éphémère.
- `/grimpeur liste [statut]` : le registre, avec la date de dernière activité, triable. Le bot **ne décide pas** de l'inactivité : c'est le jugement des admins (Q11).

### 4.6 L'admin ouvre un étage (jalon lancement)

1. Marceau prépare le contenu de l'étage suivant à partir de la liste fournie par Shadoaze : un fichier de configuration importé depuis DofusDB (ARCHITECTURE §6). L'étage est créé à l'état **scellé**, invisible sur le site.
2. Quand la jauge atteint le seuil **et** que la date plancher est passée, le bot l'annonce dans le salon admin : « Conditions remplies pour ouvrir l'étage 1 ».
3. Un admin fait sa **dernière vérification manuelle** (Q13), puis tape `/etage ouvrir numero:1`. Le bot affiche un récapitulatif (points, maximum, seuil, comptés, date), puis l'admin confirme.
4. L'ouverture **fige une photo** de l'étage précédent (points, maximum, seuil, nombre de grimpeurs par palier, date) dans le journal. L'étage 1 devient l'étage en cours sur le site.

`/etage seuil etage pourcent` (jalon lancement) change le pourcentage, par exemple 75 → 70. Le changement est inscrit au journal avec l'ancienne et la nouvelle valeur. D'ici là, le pourcentage se règle dans le fichier de configuration de l'étage.

`/etage etat` (dès la bêta) affiche la jauge, le détail du maximum et le verdict, en message éphémère ou, avec `public:oui`, visible de tous. `/ia stats` (lancement) donne aux admins le volume d'analyses, le coût du mois et le taux de propositions confirmées, corrigées et refusées.

---

## 5. Règles de calcul de la jauge

Traduction des réponses de Shadoaze (Q1, Q2, Q7, Q8), complétée par les décisions de suivi du §8 bis.

### 5.1 Paliers d'un étage

Pour un étage *E*, trois paliers cumulatifs, chacun défini par un **ensemble de contenus** :

| Rang | Libellé | Contenus (étage 0) |
|---|---|---|
| 1 | Tous les donjons de l'étage vaincus | Succès de base de chaque donjon. Étage 0 : 33 *Crypte de Kardorim* |
| 2 | Full succès de tous les donjons de l'étage | Tous les succès de chaque donjon. Étage 0 : 33, 487 *Duo*, 571 *Zombie*, 574 *Premier*, 6148 *Spécial* |
| 3 | Full succès et toutes les quêtes de la tranche | Les quêtes de la tranche. Étage 0 : le lot « Toutes les quêtes d'Incarnam (24) » |

Un étage doit avoir au moins un contenu à chaque palier. L'import refuse un étage dont un palier est vide (§8 bis, question f).

### 5.2 Points d'un grimpeur

Un **contenu est fait** par le grimpeur *g* s'il existe une validation de *g* sur ce contenu qui est :
- au statut `acceptee` ;
- réalisée **après l'ouverture** de l'étage *E* : date du message de preuve, sinon date de saisie ou de déclaration ;
- pour un donjon ou un succès : à un niveau **≤ cap(E)**, ou acceptée malgré le dépassement par un admin (`forcée`). Une déclaration de quête n'a pas de niveau, et donc pas de contrôle de cap.

Le palier *k* est **atteint** si tous les contenus des paliers 1 à *k* sont faits.

**points(g)** = le plus grand *k* tel que les paliers 1 à *k* sont atteints, ou 0. Les paliers sont **stricts** (§8 bis, b) : des quêtes sans full succès ne font pas passer de 1 à 3 points.

**visés(g)** = 1 pour un Aventurier, 2 pour un Éclaireur, 3 pour un Collectionneur.

### 5.3 La jauge

- **Grimpeurs comptés** C = grimpeurs `actifs` et **non retardataires**.
- **Maximum** M = Σ visés(g) pour g ∈ C. Exemple de Shadoaze : 12 grimpeurs, 4 par difficulté → 4 × 3 + 4 × 2 + 4 × 1 = **24**.
- **Points** P = Σ points(g) pour g ∈ C, c'est-à-dire **sans les retardataires** (§8 bis, d : « n'est intégré à l'algorithme que s'il rattrape »). Un grimpeur peut rapporter **plus que ses points visés** : un Aventurier qui fait le full succès rapporte 2 points. Ses points en trop aident la jauge, mais ne changent pas le maximum (§8 bis, a).
- **Seuil** S = ⌈ M × p / 100 ⌉, où p est le pourcentage de l'étage (75 par défaut, réglable par les admins). Le calcul se fait **en entiers** : `(M × p + 99) // 100`. Exemple : M = 24, p = 75 → S = 18. Aucun nombre à virgule, donc aucune erreur d'arrondi.
- **Jauge pleine** ⇔ M > 0 et P ≥ S.
- **Étage suivant déblocable** ⇔ jauge pleine **et** maintenant ≥ date plancher(E). Pour l'étage 0, la date plancher est le **13/11/2026 à 17:00, heure de Paris** (Q5).
- **Étage suivant ouvert** ⇔ un admin l'a ouvert (§4.6).
- **Affichage** : remplissage = min(P ÷ M, 100 %), repère à p %. Le texte donne toujours P, S et M, pour que la jauge reste lisible sans la couleur.

### 5.4 Retardataires et inclusion

- Un grimpeur inscrit **avant** l'ouverture de l'étage en cours est compté.
- Un grimpeur inscrit **après** est retardataire. Un grimpeur qui **revient de pause** redevient retardataire lui aussi (§8 bis, e). Un retardataire n'entre ni dans le maximum ni dans les points (§8 bis, d).
- Il devient compté (le champ `inclus_le` est renseigné) dès que l'une de ces conditions est remplie :
  - son niveau connu atteint **le niveau du grimpeur compté le moins avancé**, c'est-à-dire le plus petit niveau connu parmi les grimpeurs comptés (§8 bis, c). Le niveau vient d'une validation, d'un admin, ou de sa déclaration avec `/niveau` dès le lancement. Si aucun grimpeur compté n'a de niveau connu, on prend le cap de l'étage ;
  - un admin l'inclut avec `/grimpeur inclure`.
- Une fois compté, un grimpeur le reste aux étages suivants, sauf en cas de pause ou d'exclusion.
- Un retardataire toujours en retard à l'ouverture de l'étage suivant reste retardataire, avec la même règle de rattrapage.
- L'inclusion d'un retardataire fait **monter** le maximum. Le bot l'indique dans le journal admin.

### 5.5 Cohérence garantie

Les marques des cartes, les points d'un grimpeur et la jauge sont calculés par **les mêmes fonctions**. Le site ne peut pas se contredire.

### Configuration de l'étage 0

Cap 20, sans tolérance. Seuil 75 %. Ouverture le **30/10/2026 à 17:00**, date plancher le **13/11/2026 à 17:00** (heure de Paris). Données vérifiées sur DofusDB le 25/10/2026 : donjon 90 « Crypte de Kardorim », ses 5 succès, et la catégorie de quêtes 19 « Incarnam » (24 quêtes), déclarée en un seul lot.

---

## 6. Modèle de données

Les noms sont en français, comme le domaine. Le type exact de chaque colonne est dans ARCHITECTURE §5.

```
etage ──< palier >──< palier_contenu >── contenu >── etage
  │                                        │
  │                                        └──< validation >── grimpeur
  │                                                 │
  └──────────────── journal ─────────────────── preuve (screen, facultative)
```

| Table | Rôle | Champs clés |
|---|---|---|
| `etage` | Une épreuve de la tour | numéro, nom, level_cap, **seuil_pourcent** (75), statut (`scelle` / `ouvert` / `termine`), ouvert_le, date_plancher_suivant, zone_quetes, donjons affichés |
| `palier` | Un niveau d'accomplissement | étage, **rang** (1, 2 ou 3), libellé |
| `palier_contenu` | Quels contenus composent quel palier | palier, contenu. Les ensembles peuvent se recouper : le succès 33 est aux paliers 1 et 2. |
| `contenu` | Une chose réalisable | étage, type (`succes` / `quete` / `lot_quetes` / `autre`), nom, nom_court, source DofusDB (type et id, facultatifs), ids DofusDB couverts pour un lot de quêtes |
| `grimpeur` | Le registre | pseudo_ig (unique), classe, difficulté, statut, discord_user_id, niveau_connu, niveau_maj_le, inscrit_le, **inclus_le** (vide si retardataire), **inclusion_forcee** |
| `preuve` | Un screen | lien du message Discord, ids salon et message, auteur Discord, posté_le, chemin de la copie d'image, analyse IA brute, statut d'analyse |
| `validation` | Une décision ou une déclaration | grimpeur, contenu, preuve (vide pour une déclaration), **niveau (vide pour une déclaration)**, statut (`acceptee` / `refusee` / `annulee`), forcée, motif, source (`manuelle` / `ia_confirmee` / `ia_corrigee` / **`declaration`**), décidée_par (id Discord de l'admin, ou du joueur qui déclare), décidée_le, réalisée_le |
| `journal` | Tout ce qui change | horodatage, acteur, type d'événement, grimpeur et étage concernés, détails (JSON), public (oui/non) |

Règles d'intégrité :
- Au plus **une** validation `acceptee` par couple (grimpeur, contenu). C'est un index unique partiel dans la base.
- Un niveau est obligatoire pour toute validation qui n'est pas une déclaration. C'est une contrainte `CHECK` dans la base.
- Rien ne s'efface. On change un statut et on écrit au journal.
- Le site n'expose jamais un identifiant Discord, seulement les pseudos en jeu.
- Le niveau connu d'un grimpeur vaut le plus haut niveau parmi ses validations acceptées, ou le niveau saisi par un admin ou déclaré par le joueur s'il est plus récent.
- La date de dernière activité d'un grimpeur est calculée à partir du journal. Elle n'est pas stockée.

---

## 7. Cas limites et comment on les traite

| Cas | Traitement retenu | Source |
|---|---|---|
| **Niveau au-dessus du cap** (21 pour 20) | Pas de refus automatique. Le bot signale, et l'admin accepte malgré le dépassement (validation `forcée`, inscrite au journal) ou annule. | Q9 |
| **Niveau sous le cap** (Kardorim au niveau 15) | Valide : seul le dépassement pose problème. | Q3 |
| **Grimpeur au-dessus du cap** | Sa carte affiche « Dépasse le cap » en orange (niveau connu > cap). Ses futures validations seront signalées à l'admin. | Q9 |
| **Changement de difficulté** | Uniquement par un admin. Inscrit au journal. Maximum et seuil recalculés immédiatement. Les points du grimpeur ne changent pas, puisqu'ils dépendent de ce qu'il a fait. | Q1 |
| **Aventurier qui fait le full succès** | Il rapporte 2 points. Le maximum ne bouge pas. | §8 bis, a |
| **Quêtes faites sans full succès** | Le grimpeur reste au palier atteint (1 point s'il a vaincu les donjons). La carte montre quand même la marque Quêtes. | §8 bis, b |
| **Déclaration de quêtes fausse** | Un admin l'annule (`/annuler`). La parole des joueurs fait foi : c'est notre lecture de Q4. | Q4, §8 bis, l |
| **Joueur non relié à Discord qui veut déclarer** | Le bot refuse poliment. Un admin relie le compte ou déclare pour lui. | — |
| **Pause** | Le grimpeur sort du maximum et des points. À sa reprise, il redevient retardataire jusqu'à rattraper le grimpeur compté le moins avancé. | §8 bis, e |
| **Exclusion** | Comme une pause, en définitive : la carte disparaît du site, et les validations restent au journal. | — |
| **Inactivité** | Le bot montre la date de dernière activité aux admins, qui jugent. Rien d'automatique. | Q11 |
| **Nouvel inscrit en cours d'étage** | Il est retardataire : hors du maximum et des points jusqu'à ce qu'il atteigne le niveau du grimpeur compté le moins avancé, ou qu'un admin l'inclue. | Q8, §8 bis, c |
| **Jauge pleine avant le 13/11 à 17:00** | Le verdict l'indique, mais l'étage suivant reste fermé jusqu'à cette date. | Q5 |
| **Jauge pleine, puis plus pleine** (inclusion ou reprise qui fait monter le maximum) | Le site affiche l'état réel. L'admin ouvre manuellement, et la photo prise à l'ouverture fait foi. | Q13 |
| **Validation réalisée avant l'ouverture de l'étage** | Refusée. La date retenue est celle du message Discord de la preuve, ou celle de la déclaration. | — |
| **Validation d'un étage passé** | Au lot 1, la saisie se limite à l'étage en cours. Le reste est en question de suivi. | §8 bis, g |
| **Doublon** (même screen ou même déclaration) | Le second enregistrement est rejeté avec « déjà validé le … par … ». | — |
| **Erreur de saisie de l'admin** | `/annuler`, puis nouvelle saisie. | — |
| **Membre du groupe non inscrit** (ami extérieur, PL) | La validation est refusée. L'IA le signale comme anomalie bloquante. | Q10 |
| **Changement de pseudo ou reroll** | `/grimpeur modifier nouveau_pseudo`. L'identifiant interne ne change pas. | — |
| **Maximum nul** (personne de compté) | Jauge vide, avec le verdict « Aucun grimpeur compté ». | — |
| **Changement du pourcentage de seuil** | Pris en compte immédiatement, inscrit au journal, visible sur le site. | Q1 |
| **Refus d'une validation** | Le grimpeur voit ❌ et le motif. Rien sur le site. | Q12 |
| **L'IA se trompe ou refuse d'analyser** | La proposition indique « analyse impossible » et l'admin valide à la main. | — |
| **Le bot est en panne au moment d'un screen** | Au redémarrage, le bot rattrape les messages postés pendant la panne. Si l'IA est coupée, l'admin saisit par clic droit ou par commande. | — |

---

## 8. Questions posées à Shadoaze : toutes tranchées

La numérotation est celle de `QUESTIONS-SHADOAZE.md`, et les réponses sont celles de `REPONSES-SHADOAZE.md`.

| # | Question | Réponse de Shadoaze | Ce que ça change |
|---|---|---|---|
| **1** | Qui compte dans le calcul des 1/4, 1/2, 3/4 ? | ✅ **Tranchée** par la jauge à points (voir 7) : les inscrits actifs comptent selon leur difficulté. Les pauses sont exclues (décision du projet), et les retardataires aussi (voir 8). | §5.3 |
| **2** | Full succès = les 5 succès, et vaut-il victoire ? | ✅ **Oui.** Les 5 succès du donjon. Faire le full succès fait passer de 1 à 2 points. | Palier 2 inclut le palier 1 |
| **3** | Donjon sous le cap valide ? | ✅ **Oui.** Seul le dépassement pose problème. | Pas de borne basse |
| **4** | Quêtes d'Incarnam : lesquelles, quelle preuve ? | ✅ **Tranchée, avec notre interprétation.** Shadoaze a écrit : « pour les quêtes on se basera sur les paroles des gens car […] compliqué à vérifier », parce qu'aux étages suivants ce seront des quêtes isolées. **Notre lecture** : le joueur déclare, aucun screen n'est exigé, mais il peut en joindre un. Ce n'est pas une règle qu'il a formulée telle quelle : à confirmer (§8 bis, l). | Commande `/quetes` avec `preuve` facultative, source `declaration` |
| **5** | Heure exacte des ouvertures ? | ✅ **Étage 0 le vendredi 30/10 à 17:00. Étage 1 bloqué jusqu'au vendredi 13/11 à 17:00**, même si la jauge est pleine. | Dates de l'étage 0 |
| **6** | Rôle des admins ? | ✅ **« Administrateur ».** | `DISCORD_ADMIN_ROLE_ID` |
| **7** | Les chiffres selon les difficultés ? | ✅ **Une jauge unique à points.** Difficile 3 points (full succès et toutes les quêtes de la tranche), intermédiaire 2 (full succès), facile 1 (donjons battus). Maximum = somme selon les difficultés choisies, et déblocage à **75 %**. Changement de difficulté en contactant un admin, avec recalcul. | §5 entier |
| **8** | Arrivée en cours de route ? | ✅ **Pas pris en compte tant qu'il n'a pas rattrapé les autres.** | Retardataires, §5.4 |
| **9** | Marge sur le cap ? | ✅ **Pas de marge réelle.** Une tolérance au cas par cas pour un dépassement involontaire. | Plus de tolérance automatique : le bot signale, l'admin tranche |
| **10** | Joueur hors event dans le groupe ? | ✅ **Validation refusée.** | Anomalie bloquante |
| **11** | Signe de vie ? | ✅ **Jugement des admins.** | Date de dernière activité affichée aux admins, sans automatisme |
| **12** | Refus non affichés sur le site ? | ✅ **Oui**, un refus ne s'affiche pas. | Fil public sans refus |
| **13** | Ouverture automatique ou manuelle ? | ✅ **Manuelle**, pour une dernière vérification. | `/etage ouvrir` |
| **14** | Étages suivants cachés ? | ✅ **Oui**, pour la surprise. | Étages non ouverts en « ? » |

**Conséquence sur `REGLES.md`** : le texte « 1/4, 1/2, 3/4 » et les dates « 31/10 à minuit » et « 15/11 » sont dépassés. `REGLES.md` reste la copie du salon Discord. Les réponses de Shadoaze priment tant que le salon n'est pas mis à jour (§8 bis, k).

## 8 bis. Questions de suivi

Points restés flous après les réponses. Pour chacun, **la décision par défaut est appliquée** dans cette spec et dans le code. Elle sera confirmée ou corrigée par Shadoaze lors d'un prochain échange. Les points a, b et c sont décidés par le coordinateur. Les points d à k sont proposés par l'architecte. Le point l est demandé par le coordinateur.

| # | Question de suivi | Décision par défaut appliquée |
|---|---|---|
| **a** | Un grimpeur peut-il rapporter **plus** que les points de sa difficulté ? | ✅ **Confirmée par Shadoaze.** **Oui.** Un Aventurier qui fait le full succès rapporte 2 points. Ses points en trop aident la jauge, mais le maximum ne bouge pas. L'affichage plafonne à 100 %. |
| **b** | Les paliers sont-ils **stricts** ? Toutes les quêtes sans le full succès rapportent-elles quelque chose ? | ✅ **Confirmée par Shadoaze.** **Stricts.** Les quêtes sans full succès ne rapportent rien de plus que le palier atteint. |
| **c** | « Rattraper les autres », concrètement ? | ✅ **Tranchée** : rattraper au minimum le grimpeur le moins avancé. Notre lecture : atteindre le plus petit niveau connu parmi les grimpeurs comptés. L'admin peut forcer l'inclusion. |
| **d** | Les points d'un retardataire comptent-ils dans la jauge avant son inclusion ? | ✅ **Tranchée : non.** « Il n'est intégré à l'algorithme que s'il rattrape. » Ni maximum ni points. |
| **e** | Un grimpeur qui revient d'une longue pause redevient-il retardataire ? | ✅ **Tranchée : oui.** Il doit rattraper au minimum le grimpeur le moins avancé avant d'être réintégré. |
| **f** | Tous les étages auront-ils des donjons **et** des quêtes ? Sinon, un Collectionneur ne pourrait jamais atteindre 3 points. | ✅ **Confirmée par Shadoaze.** Oui par hypothèse : l'import refuse un palier vide. À confirmer avant l'étage 1. |
| **g** | Une validation d'un étage déjà dépassé (quêtes de l'étage 0 finies pendant l'étage 1) compte-t-elle pour la fiche du grimpeur ? | Fiche personnelle seulement, sans effet sur les jauges figées (lot 2). |
| **h** | Lecture des classes par **rôle** (soin, protection, placement…) : la veux-tu, et avec quelle grille ? | Classes seules au lot 1. Rôles au lot 2 si une grille est fournie. |
| **i** | Le seuil reste-t-il à 75 % à **tous** les étages ? | ✅ **Confirmée par Shadoaze.** Oui par défaut, réglable étage par étage avec `/etage seuil`. |
| **j** | Le **cap** s'applique-t-il aux quêtes déclarées ? | Non : une déclaration n'a pas de niveau. |
| **k** | Mettre à jour le **salon des règles** Discord (jauge à points, dates du 30/10 et du 13/11) ? | À proposer à Shadoaze. On recopiera ensuite le texte dans `REGLES.md`. |
| **l** | Pour les quêtes, la simple déclaration du joueur suffit, sans screen obligatoire ? | ✅ **Confirmée par Shadoaze.** **Oui** : c'est notre lecture de sa phrase. Le joueur peut joindre un screen s'il en a un, et un admin peut annuler une déclaration. |

---

## 9. Exigences non fonctionnelles

- **Disponibilité** : un événement entre amis. Une coupure de quelques heures est acceptable, une perte de données ne l'est pas. Sauvegarde quotidienne de la base, et rien ne s'efface (§6).
- **Fraîcheur du site** : moins d'une minute entre une validation et son affichage.
- **Mobile d'abord** : la plupart des joueurs ouvriront le lien depuis Discord sur leur téléphone. La page s'affiche sans défilement horizontal à 360 px.
- **Accessibilité** : contraste suffisant en clair et en sombre, jauge lisible sans la couleur (le texte « 14 points sur 18 requis » est toujours présent), focus visible.
- **Coût** : environ 4 à 6 $ par mois au total, IA comprise (ARCHITECTURE §8). Le poste principal est la machine toujours allumée.
- **Confidentialité** : aucune donnée personnelle au-delà du pseudo en jeu, de la classe et de la progression. Les identifiants Discord restent côté serveur. La date de dernière activité n'est montrée qu'aux admins.
- **Traçabilité** : toute écriture a un auteur et une date (journal).
- **Fuseau** : toutes les dates sont stockées en UTC et affichées en heure de Paris.
