# L'Épreuve des Dieux : spécification produit

Version 4, 27/10/2026. Ce document dit **quoi** construire et **pourquoi**. Le **comment** est dans `ARCHITECTURE.md`, le découpage dans le temps dans `LOTS.md`, les démarches dans `PREREQUIS.md`.

Sources, par ordre de priorité. Une source plus récente prime sur une plus ancienne quand elles se contredisent :
1. **Les arbitrages du coordinateur du 27/10** :
   - duffus.fr est la **source unique** du contenu des étages, avec l'accord de son auteur ;
   - le bot n'a pas de rôle indispensable ;
   - les salons d'étage ne sont pas une source de données ;
   - aucun export Duffus : on lit sa base nous-mêmes, poliment.
2. `docs/DECISIONS-V4.md` : les décisions du 26 et 27/10 entre Marceau et Shadoaze.
3. `docs/discord/concept-et-règles.md` : le **règlement officiel** mis à jour par Shadoaze.
4. `docs/sources/4-cahier-des-charges-VALIDE-26-10-14h06.txt` : le **cahier des charges validé** par Shadoaze. Il prime sur les résumés, sauf sur les points tranchés après lui (voir §1.3).
5. `docs/REPONSES-SHADOAZE.md` et `docs/REGLES.md` : ce qui n'est pas contredit reste valable (rôle « Administrateur », ouverture manuelle, étages cachés).
6. `docs/design/DA.md`, `docs/design/teaser.html` et `docs/design/maquette-v2.html` : la direction artistique, le teaser et la maquette du site. **Ils font foi pour le visuel** (arbitrage du chef de projet).

`docs/EXIGENCES.md` (115 exigences EX-01 à EX-115, points ouverts T-01 à T-32) **prime sur ce document** en cas de contradiction. Cette version l'intègre, avec les arbitrages du chef de projet du 27/10 :
- **T-01** est tranché en faveur du règlement ;
- **T-09** : « Merci Duffus » avec un lien vers duffus.fr, et aucun lien par quête ;
- **T-02** : succès de donjon pris chez Duffus s'il les a, sinon chez DofusDB, au choix de l'import ;
- tous les autres T-nn reçoivent leur réponse par défaut, **réglable sans changer le code** (§8).

L'**annexe A** relie chaque exigence à sa section et à son lot.

## Ce qui change en v4

| Avant (v3) | Maintenant (v4) | Pourquoi |
|---|---|---|
| Un **bot Discord** où les admins saisissent les validations, plus un site public en lecture seule. | Une **application web privée** : chaque grimpeur se connecte avec Discord et **coche lui-même** sa progression. Le bot n'a plus de rôle indispensable. | Cahier des charges (CdC) §3 « zéro screen », règlement II, arbitrage du 27/10. |
| Trois difficultés, paliers de 1, 2 ou 3 points. | **Plus de difficulté.** **4 catégories, 1 point chacune** par grimpeur et par étage. | Règlement III, DECISIONS §1 et §2, CdC §1. |
| Seuil = 75 % d'un maximum. | **Palier de validation = 2 × nombre de grimpeurs actifs.** | CdC §1, DECISIONS §2. |
| Retardataires calculés automatiquement. | **Pause = « gel »** : le joueur sort du calcul. Il est **réintégré à la main** par un admin quand il a rattrapé le moins avancé des actifs. | CdC §1, règlement V, DECISIONS §6. |
| Pas de bonus. | **Points bonus** donnés par un admin lors d'événements spéciaux, journalisés. | Règlement III. |
| Contenu d'étage saisi depuis DofusDB. | **Tout le contenu vient de duffus.fr** (tranches, donjons, succès, quêtes, guides par Dofus), aspiré par un script lancé à la main, mis en cache chez nous, puis **validé par un admin**. DofusDB ne sert plus qu'en complément et en repli. | CdC §3, accord de l'auteur, arbitrage du 27/10. |
| Quêtes « toutes ou rien ». | Quêtes **principales** (requises pour un Dofus, prérequis compris) et **secondaires**, classées de façon **déterministe** à partir des guides par Dofus de Duffus. | DECISIONS §4, CdC §1. |
| Une page unique avec des cartes. | Une **tour en pyramide** (« brouillard de guerre ») et, par étage, une **liste unique** avec des **badges de catégorie** et un **filtre cumulatif** par cases. | CdC §2. |
| Site public dès le départ. | Une **page teaser** avec compte à rebours jusqu'au 13/11 à 17 h, puis un site **réservé aux participants**. | DECISIONS §8, CdC (en-tête). |
| Inscription saisie par un admin dans le bot. | Le grimpeur crée sa fiche lui-même s'il figure sur la **liste officielle** de l'expédition. | `docs/discord/liste-grimpeurs.md`. |

**Dates**, confirmées par le règlement et le CdC : l'**étage 0** s'ouvre le **vendredi 30/10/2026 à 17:00** (accès anticipé, le site n'est pas attendu). L'**étage 1** ne peut pas s'ouvrir avant le **vendredi 13/11/2026 à 17:00** (heure de Paris), le « vrai départ ». Le guide compte au moins **26 étages, de 0 à 25**.

Tout ce qui portait sur les difficultés, les paliers, les retardataires automatiques, `/valider`, `/quetes`, l'IA de lecture des screens et l'import par les salons Discord est **retiré**.

---

## 1. Le produit

### 1.1 En une phrase

Un site privé où chaque grimpeur se connecte avec Discord, monte la **tour** étage par étage, et coche sur une **liste unique** les donjons (avec leurs 5 succès) et les quêtes de l'étage ouvert. Il voit en direct **la jauge collective** qui permet aux admins d'ouvrir l'étage suivant. Toutes les fiches sont consultables, et des filtres montrent qui n'a pas encore fait telle quête ou tel succès, pour proposer de s'y mettre ensemble.

### 1.2 Ce qui est décidé (ne pas rouvrir)

| Décision | Conséquence pour le produit |
|---|---|
| La progression est collective, pas une course. | Le cœur du site, c'est la jauge. Pas de classement ni de podium. |
| **Confiance, zéro screen** : la case cochée est la preuve. | Aucune validation par un admin. Un admin peut corriger les coches d'un joueur, et tout passe au journal. |
| **4 catégories, 1 point chacune** par grimpeur et par étage (§5). | Un grimpeur rapporte de 0 à 4 points à l'étage en cours, plus d'éventuels bonus. |
| **Palier = 2 × grimpeurs actifs.** | Les grimpeurs en pause et les exclus ne comptent ni dans le palier ni dans le score. |
| **Ouverture manuelle** par un admin, possible seulement si la jauge atteint le palier, et jamais avant la date plancher. | Le bouton d'ouverture n'est actif que dans ces conditions. |
| **Brouillard de guerre** : les étages non ouverts ne sont pas générés. | Le serveur n'envoie **aucune** donnée sur un étage scellé, pas même leur nombre. La pyramide s'arrête à l'étage ouvert. |
| **Un seul guide**, une liste unique par étage, avec un code couleur. | Pas de « double guide » selon le profil : un filtre suffit. |
| **Duffus, source unique du contenu**, avec un **crédit**. | Le pied de chaque page affiche « Merci Duffus », avec un lien vers https://duffus.fr (T-09). **Aucun lien par quête ni par tranche** vers duffus.fr : le contenu est intégré chez nous (EX-70), pour ne pas laisser voir les tranches suivantes. Les autres marques du site d'origine (logos, Twitch, Discord, widgets de dons) ne sont **jamais** reprises (CdC §4). |
| **Pause et retour à la main.** | Un bouton admin gèle ou dégèle un grimpeur. Le site aide l'admin à juger, sans rien décider à sa place. |

### 1.3 Un écart entre les sources, tranché (T-01)

Le **CdC validé** (26/10, 14 h 06) dit, au pied de la lettre : « 1 quête cochée = +1 point au score actuel global ». C'est un point **par action**. Le **règlement officiel** (#concept-et-règles, publié après le CdC) dit au contraire : « valider **tous** les donjons présents dans un étage = 1 point », soit 4 points au maximum par joueur et par étage. Shadoaze a d'ailleurs refusé un point par succès, qui « ferait grimper les sommes ».

**Arbitrage du chef de projet (27/10) : le règlement fait foi.** Chaque catégorie **complète** de l'étage rapporte 1 point par joueur, 4 au maximum. Le comptage « 1 quête = 1 point » est **abandonné**. Le CdC reste suivi pour tout le reste : 5 sous-cases par donjon, full succès quand les 5 sont cochées, liste unique, filtres et pyramide.

### 1.4 Ce que le produit ne fait pas

- Il ne lit pas la progression dans le jeu : aucune API Ankama ne la fournit.
- Il ne vérifie ni le **cap de niveau**, ni l'**absence de PL**, ni la **présence d'un joueur hors événement** dans le groupe (CdC §3). Ces règles sont rappelées sur la page de l'étage, et le règlement compte sur le fair-play. Une coche contraire au règlement se règle par un admin, qui la retire avec un motif.
- Il n'envoie aucun message privé de relance.
- Il ne décide ni de la triche ni de l'inactivité. Les admins jugent, et le site leur montre la date de dernière activité.
- Il n'interroge **jamais** duffus.fr pendant la navigation d'un joueur.

---

## 2. Vocabulaire

| Terme | Sens dans ce projet |
|---|---|
| **Grimpeur** | Un participant de la liste officielle, identifié par son compte Discord. Sa fiche porte son pseudo en jeu, sa classe et un niveau déclaré facultatif. |
| **Statut** | `actif`, `pause` (gelé) ou `exclu`. Seuls les actifs comptent dans le palier et dans le score. |
| **Admin** | Un membre qui a le rôle Discord **« Administrateur »**, vérifié sur le serveur. |
| **Étage** | Une épreuve, numérotée à partir de 0. **Étage N = tranche de niveau N du guide Duffus.** Il porte un level cap, un statut (`scelle`, `ouvert` ou `termine`), une date d'ouverture et une **date plancher** avant laquelle l'étage suivant ne peut pas s'ouvrir. |
| **Donjon de l'étage** | Un donjon de la tranche, d'après Duffus. Il a **5 sous-cases** : « Finir le donjon classique », « Duo » et 3 défis propres au boss. |
| **Quête de l'étage** | Une quête de la tranche, d'après Duffus, rangée dans un **bloc** (dans l'ordre optimisé du guide). Elle est **principale** ou **secondaire**. |
| **Quête principale** | Une quête nécessaire pour obtenir un Dofus, directement ou comme prérequis. |
| **Quête secondaire** | Toute autre quête de l'étage : « quêtes annexes de complétion » (CdC), « utiles pour le 100 % succès » (règlement). |
| **Catégorie** | L'une des 4 sources de points : **Donjons**, **Full succès**, **Quêtes principales**, **Quêtes secondaires** (§5). |
| **Coche** | Une sous-case de donjon ou une quête cochée par un grimpeur. Elle est datée, et on peut la décocher. |
| **Bonus** | Des points ajoutés par un admin à un grimpeur, ou à toute la guilde, pour un événement spécial, avec un motif. |
| **Score** | La somme des points des grimpeurs actifs sur l'étage en cours, plus les bonus. |
| **Palier de validation** | Le score à atteindre pour que l'ouverture de l'étage suivant soit permise. |
| **Jauge** | Le score comparé au palier. |
| **Bilan d'étage** | La photo figée au moment où l'étage suivant s'ouvre. |
| **Journal** | L'historique horodaté de tout ce qui change. |
| **Aspiration** | La récupération ponctuelle des données de duffus.fr par un script lancé à la main (ARCHITECTURE §6). |
| **Mode du site** | `teaser` ou `ouvert` (§4.1). |

---

## 3. Acteurs

| Acteur | Qui | Ce qu'il peut faire |
|---|---|---|
| **Visiteur** | Quelqu'un qui a le lien, sans être connecté | Voir le teaser (avant l'ouverture du site) ou l'accueil avec « Se connecter avec Discord » (après). Rien d'autre. |
| **Membre** | Connecté avec Discord et membre du serveur, sans fiche | Créer sa fiche s'il est sur la liste officielle. Sinon, il voit un message qui l'invite à contacter Shadoaze. |
| **Grimpeur** | Membre avec une fiche | Cocher et décocher **sa** progression. Voir la tour, l'étage ouvert, les étages passés, toutes les fiches et les filtres. Modifier son pseudo, sa classe et son niveau déclaré. |
| **Testeur** | Un grimpeur listé dans la configuration `BETA_TESTEURS` | Voir le site complet pendant le mode teaser, pour le bêta-test que le règlement prévoit (IV). |
| **Admin** | Rôle « Administrateur » | Tout ce que fait un grimpeur, plus : gérer la liste officielle, geler, dégeler ou exclure, corriger des coches, donner des bonus, revoir et ajuster le contenu d'un étage, voir les étages scellés, ouvrir un étage, régler la date plancher ou le palier, lire le journal, **lancer l'aspiration Duffus** (en ligne de commande au lot B). |
| **Mainteneur** | Marceau | Déployer, lancer l'aspiration, corriger les données en dernier recours. |
| **Bot** | « Gardien de la Tour » | **Aucun rôle indispensable aux lots A et B.** Au lot B, s'il est configuré, il poste une annonce à l'ouverture d'un étage, par un simple appel REST. Les autres usages éventuels sont au lot C. |

---

## 4. Parcours

### 4.1 Avant l'ouverture du site : le teaser (lot A)

- Jusqu'à l'ouverture, toute personne qui ouvre le lien voit **une seule page**, le teaser du designer (`docs/design/teaser.html`), avec un **compte à rebours jusqu'au vendredi 13/11/2026 à 17:00, heure de Paris**.
- Aucune autre page n'est servie. Toute autre adresse renvoie vers le teaser, sauf `/sante`, les fichiers statiques et, à partir du lot B, la connexion et la création de fiche.
- Sans JavaScript, la date reste écrite en clair.
- Le pied de page ajoute « Merci Duffus » à la mention du designer, avec un lien.
- Au lot B, le teaser gagne un lien discret, **« Grimpeur ? Prépare ta fiche »**. Un participant de la liste officielle peut se connecter et créer sa fiche avant l'ouverture, pour que le palier soit juste dès la première minute. Après, il revoit le teaser avec « Fiche prête, rendez-vous le 13/11 à 17 h ».
- Les **admins et testeurs connectés** voient le site complet, avec un bandeau « Mode teaser : les grimpeurs ne voient pas encore cette page ».
- **Bascule** : le mode est réglé par `SITE_MODE` (ARCHITECTURE §7). En mode `auto` (le défaut), le site s'ouvre de lui-même à `SITE_OUVERT_LE`, le 13/11 à 17:00. On peut forcer `teaser` ou `ouvert` sans redéployer le code.
- **Le bouton « Entrer dans la tour »** du teaser n'apparaît qu'une fois le compte à rebours terminé, et seulement si la variable de configuration `TEASER_LIEN_ENTRER` est renseignée. Elle est vide par défaut et se remplit le jour J (arbitrage du chef de projet).

### 4.2 Connexion et fiche (lot B)

1. « Se connecter avec Discord ». Discord montre au grimpeur ce que le site demande, son identité et son appartenance au serveur, et il accepte.
2. Le site vérifie qu'il est **membre du serveur** de l'événement. Sinon : « Ce site est réservé aux grimpeurs de L'Épreuve des Dieux. »
3. S'il n'a pas de fiche :
   - **sur la liste officielle** : « Créer ma fiche » avec pseudo en jeu (2 à 30 caractères, unique sans tenir compte de la casse), classe (une des 19) et niveau (facultatif) ;
   - **hors de la liste** : « Tu n'es pas encore inscrit à l'expédition. Envoie ta validation en MP à Shadoaze. »
4. Le **statut** de la fiche est celui que l'admin a choisi en ajoutant le joueur à la liste, `actif` par défaut. Un joueur qui rejoint en cours de route peut être ajouté en `pause`, gelé jusqu'à ce qu'un admin le réintègre.
5. La session dure **7 jours**. Les droits d'admin sont revérifiés auprès de Discord **au plus toutes les 10 minutes**, au moment d'une action d'admin. Retirer le rôle sur Discord coupe donc l'accès admin en moins de 10 minutes.

### 4.3 La tour en pyramide (lot B)

- Page d'accueil après connexion : **la tour**, des blocs empilés en pyramide selon la DA (`docs/design/DA.md`, composant « Tour », et `maquette-v2.html`). L'**étage ouvert** est en pleine largeur, avec sa jauge miniature, et les étages terminés sont accessibles.
- **Brouillard de guerre** : au-dessus de l'étage ouvert, la DA dessine des blocs scellés marqués « ? », de plus en plus étroits, qui s'effacent dans la brume. Ce sont des **décors en nombre fixe** (6), identiques quel que soit l'état réel de la tour. Ils ne portent ni numéro, ni nom, ni lien, et ne révèlent pas combien d'étages existent. Le **serveur n'envoie aucune donnée** d'un étage scellé (CdC §2 : « techniquement impossible » d'y accéder), et une adresse comme `/etages/7` sur un étage scellé répond « introuvable » (404), exactement comme un étage qui n'existe pas.
- Chaque étage peut avoir une **image d'ambiance** (adresse réglée par un admin, facultative). Ce sont toujours des **créations originales** (dégradés, canvas, SVG ou images générées), **jamais des captures ou visuels du jeu** (DA, « À ne pas faire »).
- Toucher une assise ouvre **l'onglet de cet étage** (§4.4). Les étages terminés montrent leur bilan figé.
- En tête : la jauge de l'étage ouvert et la **répartition des 19 classes** (classes que personne ne joue mises en évidence, repris de la v3).

### 4.4 L'onglet d'un étage : liste unique, badges et filtre cumulatif (lot B)

Tout le monde voit **la même liste unifiée** pour un étage donné (CdC §2).

1. **En-tête** : numéro, nom (par défaut « Étage N », sinon le nom réglé par un admin, T-28), tranche (« Niveaux 40 à 50 »), **level cap** (EX-26), rappel des règles (« entre grimpeurs, sans dépasser le cap, sans PL ») et la **formule du palier** (T-21). À gauche sur grand écran, ou dans un menu sur mobile, **les tranches des étages ouverts** seulement, comme la colonne du guide Duffus (EX-51, EX-63).
2. **Ma progression** : mes 4 catégories avec leur avancement (« Donjons 4/6 », « Full succès 17/30 », « Principales 8/8 ✓ », « Secondaires 12/40 »), mes points (« 1 point sur 4 ») et mes bonus.
3. **La jauge** (§4.5).
4. **Le filtre cumulatif** : quatre cases à cocher, **☑ Donjons · ☑ Full succès · ☑ Quêtes principales · ☑ Quêtes secondaires**, toutes cochées par défaut. Le site n'affiche que les lignes des catégories cochées. On peut composer n'importe quel mélange, par exemple « Principales + Donjons » ou « Secondaires seules ». Une cinquième case, **« Seulement ce qui me reste »**, masque ce que j'ai déjà fait. Le choix est mémorisé sur l'appareil.
5. **La liste unique**, dans l'ordre du guide Duffus : les donjons à leur place dans les blocs, sinon en tête de liste. Chaque ligne porte un **badge de catégorie** très net, à la fois en couleur, en icône et en texte, pour rester lisible sans la couleur. Couleurs et icônes sont celles de la DA : Donjons jade (porte en arche), Full succès améthyste (étoile), Principales azur (œuf de Dofus), Secondaires corail (parchemin).
   - **Quête principale** : pilule « Principale » à fond azur teinté et bordure pleine, avec le ou les Dofus visés ;
   - **Quête secondaire** : pilule « Secondaire » à contour corail **en pointillés**. Le trait plein ou pointillé distingue les deux sans la couleur ;
   - **Donjon** : une ligne repliable avec deux badges d'état, **« Donjon »** (allumé si la case classique est cochée) et **« Full succès »** (allumé si les 5 le sont). Une fois dépliée, elle montre les **5 sous-cases** : *Finir le donjon classique*, *Duo*, puis les 3 défis du boss, chacun avec son intitulé et sa condition (venus de Duffus). Le filtre « Donjons » ou « Full succès » affiche les lignes de donjon. Avec « Full succès » seul, elles s'ouvrent dépliées.
   - chaque quête porte en plus sa case, son niveau, la précision « **jusqu'où faire la quête** » quand le guide la donne (EX-51), et le compteur « 7/12 » (le nombre de grimpeurs actifs qui l'ont cochée). Chaque sous-case de donjon a aussi son compteur ;
   - **la fiche de quête** (EX-52) : un toucher sur le nom d'une quête ouvre sa fiche **intégrée chez nous**. Elle montre comment la réaliser, ce dont on a besoin, le succès lié et les prérequis, d'après Duffus. Il n'y a **aucun lien vers duffus.fr** (EX-70). Les liens internes du texte Duffus sont retirés ou réécrits vers nos propres fiches s'ils visent un étage ouvert. Les images de Duffus ne sont pas reprises au lot B, puisque les afficher ferait appeler son site pendant la navigation (§10).

Règles de la coche :
- Un toucher suffit. L'enregistrement est immédiat, et la jauge et les compteurs se mettent à jour sans recharger la page.
- On ne peut cocher que sur un étage **ouvert ou terminé**. Un étage terminé reste cochable pour la fiche, sans effet sur son bilan figé (§5.5).
- Si le réseau échoue, la case revient à son état précédent avec « Pas enregistré, réessaie ».
- **Cocher un succès de donjon coche aussi « Finir le donjon classique »**, puisqu'on ne réussit pas un succès de boss sans le battre. **Décocher la case classique décoche les 4 autres** (T-16, réglable : `coches.succes_coche_vaincu`).
- Un grimpeur **en pause** peut continuer à cocher : c'est comme ça qu'il rattrape son retard. Ses coches comptent dès sa réintégration (T-13, réglable : `coches.pause_peut_cocher`).
- Chaque coche ou décoche est **au journal**, avec son auteur.

### 4.5 La jauge

Le texte est toujours présent et lisible sans la couleur : « **Score 19 sur un palier de 24**, il en manque 5. 12 grimpeurs actifs, 2 en pause. »
- La jauge a **une encoche par point requis** (DA, « Jauge d'étage »). Les encoches se remplissent dans l'ordre des catégories, chacune de sa couleur, puis avec les bonus. Au-dessus : le grand chiffre « 20 / 24 points » et la formule du palier. Au-delà du palier, elle affiche « plein » avec le score réel.
- **Détail** : « Donjons 10 · Full succès 3 · Principales 4 · Secondaires 2 · Bonus 0 », c'est-à-dire le nombre de grimpeurs actifs qui ont le point dans chaque catégorie, plus le total des bonus.
- **Verdict** :
  - « Un admin pourra ouvrir le prochain étage quand la jauge sera pleine, et pas avant le vendredi 13 novembre à 17 h » ;
  - ou « Jauge pleine : un admin va vérifier et ouvrir le prochain étage ».
  - On ne nomme jamais un étage scellé.

### 4.6 Fiches et filtres par élément (lot B)

- **Les grimpeurs** : toutes les fiches, actifs d'abord, puis en pause, par ordre alphabétique. **Jamais de tri par score.** Chaque carte montre le pseudo en jeu, le **nom Discord** (pour se contacter, T-20, réglable : `fiche.afficher_nom_discord`), la classe (facultative), le statut, le niveau déclaré et les 4 pastilles de l'étage ouvert.
- **La fiche d'un grimpeur** (son « tableau de bord ») : pour l'étage ouvert et chaque étage passé, ses 4 catégories, ses points, ses bonus, son **pourcentage d'avancement** (cases cochées ÷ cases de l'étage) et le détail de ce qu'il a coché ou non. Tous les grimpeurs connectés peuvent la voir. Seuls lui et les admins peuvent la modifier.
- **« Qui ne l'a pas fait ? »** : un toucher sur le compteur « 7/12 » d'une quête ou d'une sous-case ouvre la liste des grimpeurs **actifs** qui ne l'ont pas cochée, avec leur classe (DECISIONS §5).
- **Filtre par élément** sur la page des grimpeurs (DA, « Filtre qui n'a pas fait… ? ») : une liste déroulante groupée (catégories, donjons, succès, quêtes de l'étage ouvert) affiche deux listes, **« Pas encore fait »** et **« Déjà fait, ils peuvent accompagner »**. Les cartes concernées sont entourées, les autres estompées.
- Les exclus n'apparaissent nulle part, sauf pour les admins.

### 4.7 L'admin gère les grimpeurs (lot B)

Page **Admin → Grimpeurs** :
- **Liste officielle** : on ajoute un participant par son identifiant Discord, ou par la mention `<@…>` copiée de #liste-grimpeurs, avec un statut initial (`actif` par défaut). Un champ accepte plusieurs mentions collées d'un coup. Les 10 de `docs/discord/liste-grimpeurs.md` passent en un collage.
- **Tableau** : pseudo (ou « fiche à créer »), classe, statut, niveau déclaré, **dernière activité** (dernière coche), date d'inscription.
- **Geler** ou **réintégrer**, avec un motif facultatif. L'effet sur le palier s'affiche avant de confirmer : « Palier 24 → 22 ». Pour aider à juger d'une réintégration (« rattraper au minimum le grimpeur actif le moins avancé »), la ligne d'un grimpeur gelé montre ses points et son avancement sur l'étage ouvert, et son niveau déclaré, à côté de ceux du **moins avancé des actifs** (le moins de points, puis le plus faible avancement). C'est une information : l'admin décide.
- **Exclure**, avec un motif obligatoire et une confirmation. C'est réversible.
- **Corriger** le pseudo ou la classe. **Modifier les coches** en ouvrant la fiche en mode édition, par exemple pour retirer une validation contraire au règlement.
- **Bonus** : des points pour un grimpeur ou pour toute la guilde, sur l'étage ouvert. Un nombre de −10 à +10 et un motif obligatoire, par exemple « Événement Halloween ». Un bonus s'annule mais ne s'efface pas.

### 4.8 L'admin prépare et ouvre un étage (lot B)

1. **Aspiration** (un admin en ligne de commande au lot B, un bouton au lot C) : le script lit les tables publiques de Duffus à faible débit, puis enregistre une copie datée (ARCHITECTURE §6). Il ne touche à rien de visible.
2. **Construction de l'étage** : à partir de la copie, l'outil crée ou met à jour l'étage N à l'état **scellé**, invisible pour les grimpeurs. Il y met la tranche que `config/etages.yaml` associe à l'étage N (T-04), les **donjons proposés** (ceux dont le niveau est dans la tranche, T-03) et leurs 5 succès, les quêtes par bloc avec leur fiche, et la nature de chaque quête (§6). On peut préparer d'avance tous les étages.
3. **Revue** dans *Admin → Étages → Étage N (scellé)* : l'admin voit l'étage tel que les grimpeurs le verront. Les **alertes** sont en tête :
   - donjon qui n'a pas 5 succès ;
   - succès pris chez DofusDB faute de données Duffus (T-02) ;
   - quête sans nature déterminable ;
   - quête principale que le guide place dans une autre tranche (T-12 : la tranche Duffus fait foi, l'écart est seulement signalé) ;
   - changement depuis la dernière aspiration.

   L'admin peut :
   - **valider la liste des donjons** (T-03) : retirer un donjon proposé, ou en **ajouter** un depuis la liste complète des donjons aspirés ;
   - changer la nature d'une quête. Ce choix prime et survit aux réimports ;
   - **masquer** un donjon, une sous-case ou une quête, qui sort alors des points ;
   - corriger un libellé ;
   - régler la date plancher, le level cap, le **nom** et l'**image d'ambiance** de l'étage (T-28 ; ce sont des créations originales, par exemple les images générées par Shadoaze, EX-104, jamais des captures du jeu).
4. **Ouverture** : le bouton **Ouvrir le prochain étage** n'est actif que si **la jauge de l'étage en cours est pleine** et **la date plancher est passée**. L'admin voit un récapitulatif (score, palier, actifs, date) **et le détail par grimpeur** : qui a gagné quel point, ses coches, sa dernière activité (EX-83, sa « dernière vérification manuelle »). Puis il confirme. Sinon, le bouton est grisé et donne la raison. Il reste **forçable** avec un motif obligatoire inscrit au journal, pour un cas exceptionnel voulu par Shadoaze. Le récapitulatif l'affiche en rouge.
5. L'ouverture **fige le bilan** de l'étage précédent, qui passe à `termine`, et fait apparaître le nouvel étage dans la pyramide. Si un salon d'annonces est configuré, le bot y poste « 🗼 L'étage N est ouvert ! ».

**Palier manuel** : *Admin → Étage ouvert → Palier* remplace la formule par un nombre fixe, avec un motif. C'est la soupape si une catégorie est vide (§5.3) ou si Shadoaze veut ajuster. Vider le champ rétablit la formule. Chaque changement passe au journal.

**L'étage 0** est construit ouvert, avec `ouvert_le = 30/10/2026 17:00` et `date_plancher_suivant = 13/11/2026 17:00` (EX-28, EX-29). Dès l'ouverture du site, les grimpeurs y **cochent rétroactivement** ce qu'ils ont fait depuis le 30/10 (T-07). L'alternative proposée à Shadoaze, ouvrir le site quelques jours avant le 13/11, ne demande qu'un réglage : `SITE_OUVERT_LE`.

### 4.9 Le journal (lot B)

*Admin → Journal* : une liste filtrable par grimpeur, par type et par étage. Le fil des dernières coches, visible des grimpeurs, est au lot C.

---

## 5. Règles de calcul

### 5.1 Les 4 catégories d'un étage *E* pour un grimpeur *g*

Seuls les éléments **non masqués** de *E* comptent : seuls ceux de la tranche rapportent des points pour l'étage.

| Catégorie | Le point est acquis quand… | Exemple avec 6 donjons |
|---|---|---|
| **Donjons** | la sous-case « Finir le donjon classique » de **chaque** donjon de *E* est cochée | 6 cases |
| **Full succès** | **les 5 sous-cases** de **chaque** donjon de *E* sont cochées | 30 cases |
| **Quêtes principales** | toutes les quêtes principales de *E* sont cochées | par exemple 8 |
| **Quêtes secondaires** | toutes les quêtes secondaires de *E* sont cochées | par exemple 40 |

- **points(g, E)** = le nombre de catégories acquises, de 0 à 4.
- Les catégories sont **indépendantes** : on peut avoir le point des quêtes sans celui des donjons (EX-07, ferme). Le full succès implique de toute façon le point Donjons, puisque la case classique fait partie des 5.
- Une catégorie **vide**, par exemple un étage sans quête principale, ne peut pas être acquise (§5.3).
- Les sous-cases servent à « savoir exactement où on en est » (CdC §3). Une à une, elles ne rapportent rien.

### 5.2 Score, palier et jauge de l'étage en cours

- **Actifs** A = les grimpeurs au statut `actif`, et N = leur nombre.
- **Score** P = Σ points(g, E) pour g ∈ A, **+** les bonus individuels non annulés des grimpeurs de A, **+** les bonus collectifs non annulés, sur *E*.
- **K** = le nombre de catégories **non vides** de *E* (4 en général).
- **Palier** S : le palier manuel s'il est fixé, sinon **S = ⌈ m × N × K ÷ 4 ⌉**, où **m** = `palier.points_par_joueur` (réglage, **2** par défaut, EX-109). Avec m = 2 et 4 catégories, **S = 2 × N**, la règle du CdC (EX-09). Le calcul est exact, en fractions (`fractions.Fraction`) et en entiers, sans nombre à virgule. Les bonus ne changent pas le palier.
- **Jauge pleine** ⇔ N > 0 et P ≥ S.
- **Prochain étage ouvrable** ⇔ jauge pleine **et** maintenant ≥ date plancher de *E* (si elle existe) **et** un étage scellé de numéro supérieur existe.

| Situation | N | K | S | P | Pleine ? |
|---|---|---|---|---|---|
| 12 actifs, 4 catégories | 12 | 4 | 24 | 26 | oui |
| 12 actifs, aucune quête principale | 12 | 3 | 18 | 17 | non |
| 11 actifs, 3 catégories | 11 | 3 | 17 (16,5 arrondi au-dessus) | 17 | oui |
| 10 actifs, bonus collectif de 2 | 10 | 4 | 20 | 18 + 2 | oui |
| Personne d'actif | 0 | 4 | 0 | 0 | non (« Aucun grimpeur actif ») |

### 5.3 Pourquoi ⌈ N × K ÷ 2 ⌉ quand une catégorie est vide

« 2 × joueurs actifs », c'est demander **la moitié des points possibles** : 2 sur 4 en moyenne. Si un étage n'a que 3 catégories, garder 2 × N exigerait les deux tiers des points possibles, et l'étage deviendrait nettement plus dur sans que personne l'ait voulu. On garde donc **la même proportion** : avec m = 2, on obtient ⌈ N × K ÷ 2 ⌉. C'est la réponse par défaut de T-11. Le réglage `palier.categorie_vide` vaut `ignoree` par défaut. Avec `offerte`, une catégorie vide rapporte son point à tous et K reste à 4. Le palier manuel reste la soupape.

### 5.4 Cohérence garantie

Les badges, les points, les compteurs « 7/12 », les filtres et la jauge sont calculés par **les mêmes fonctions du domaine**. Le site ne peut pas se contredire.

### 5.5 Bilan figé

À l'ouverture d'un étage, on enregistre pour l'étage qui se termine la date, N, S, P, les points par catégorie et les bonus. Les coches faites ensuite enrichissent les fiches, mais **ne changent pas le bilan**.

---

## 6. Contenu d'un étage : Duffus, source unique

### 6.1 Qui fournit quoi

| Donnée | Source | Note |
|---|---|---|
| Tranches | **Duffus** (`guide_ranges`) | La correspondance étage ↔ tranche et le cap sont **réglés dans `config/etages.yaml`** (T-04). Par défaut : étage 0 = première tranche (jusqu'au niveau 20), puis une tranche par étage, cap = borne haute. |
| Donjons de la tranche (proposés par niveau, **liste validée par un admin**, T-03), leurs **5 succès** (intitulé, condition) | **Duffus** (`dungeon_pages`) ; succès dans `achievements` / `achievement_objectives` **s'ils y sont, sinon DofusDB** : le choix se fait à l'import, donjon par donjon (T-02) | Le guide Duffus lui-même n'a pas les succès de donjon (EX-64) |
| Quêtes de la tranche, **blocs**, ordre, « jusqu'où », **fiche intégrée** (comment, besoins, succès lié, prérequis) | **Duffus** (`quest_list`, `quest_pages`) | — |
| **Principal / secondaire** | **Duffus**, guides par Dofus (`dofus_list` et les quêtes et prérequis de chaque guide) | Calcul déterministe (§6.3) |
| Icônes de Dofus, de monstres et d'objets, détails des monstres | **DofusDB** (complément) | Pour l'affichage seulement |
| **Repli** : succès d'un donjon, ou classement principal / secondaire, si une donnée Duffus manque | **DofusDB** | Marqué « repli » dans la revue, à valider par l'admin |
| Ajustements | **Admins** | Ils priment, et passent au journal |

Les noms de tables Duffus ci-dessus ont été repérés dans le code public de son site. **Leur structure exacte (colonnes et liens) reste à relever** lors de la première aspiration, qui est la première tâche du lot B (`LOTS.md`). Les **salons d'étage** de Shadoaze ne sont **pas** une source de données : c'était une aide provisoire pour les joueurs.

Les **fiches de quête** (`quest_pages`) sont **recopiées** chez nous à l'aspiration (EX-52, EX-70), et leur texte est nettoyé : HTML filtré par liste blanche, liens vers duffus.fr retirés, images non reprises. Le prix : la copie vieillit si l'auteur modifie une fiche. La parade : une nouvelle aspiration, dont le rapport de différences montre les fiches changées (ARCHITECTURE §6).

### 6.2 Les 5 sous-cases d'un donjon

Les succès du donjon, dans l'ordre : *Finir le donjon classique*, puis *Duo*, puis les 3 défis du boss. Ils viennent des tables `achievements` / `achievement_objectives` de Duffus **si elles les contiennent**, sinon de DofusDB. Le choix se fait **à l'import, donjon par donjon**, et il est affiché dans la revue (T-02, arbitrage du chef de projet). Le guide Duffus lui-même n'a pas ces succès (EX-64). Si la source ne donne pas exactement 5 succès, l'import lève une **alerte** et l'admin garde ce que le jeu donne ou masque une sous-case.

Avec DofusDB (vérifié le 27/10/2026) : le champ `achievements` du donjon, sans la catégorie *Compagnons* (142). *Maison Fantôme* (34) et *Donjon des Bworks* (13) ont par exemple un 6e succès « (Compagnon) », qui ne fait pas partie des 5.

### 6.3 Principal ou secondaire : un classement déterministe

**Règle** : une quête de l'étage est **principale** si elle figure dans **au moins un guide par Dofus** de Duffus, c'est-à-dire si elle est nécessaire pour obtenir ce Dofus ou si elle en est un prérequis. Sinon, elle est **secondaire**.
- Si Duffus donne les prérequis de façon récursive (la quête A exige B, qui exige C), on calcule la **fermeture** : tous les prérequis, directs ou indirects, des quêtes de chaque guide.
- **Seuls les Dofus retenus** comptent (§8.2, Q4). La liste est dans `config/dofus.yaml`, tenue par les admins.
- L'admin peut forcer la nature d'une quête, avec un motif. L'ordre de priorité est donc : **choix de l'admin**, puis **Duffus**, puis **DofusDB** en repli.
- Le résultat est **reproductible** : les mêmes données donnent toujours le même classement, sans aucune IA.

**Le repli DofusDB**, vérifié sur l'API le 27/10/2026, ne sert que si un guide Dofus manque chez Duffus :
- un Dofus est l'objet de type 23. Il est rarement la récompense directe d'une quête, mais l'objet porte `questsThatReward` (3 Dofus) ou `achievementsThatReward` (24 Dofus ; par exemple Émeraude → succès 1048) ;
- les objectifs de ces succès donnent les quêtes racines (`Qf=<quête>`, ou `OA=<succès>` à suivre) ;
- les prérequis se lisent dans `startCriterion` (par exemple `Qf=1462&PL>39`). **Piège** : le champ `need.quests` met à plat les « OU ». Pour `(Qf=272|Qf=273|Qf=274)`, il donne les trois quêtes, alors qu'une seule suffit. On n'y garde donc que les « ET » ;
- essai réel : 15 quêtes pour le Dofus Émeraude, 74 pour le Dofus Argenté. Aucune donnée pour Ocre, Kaliptus, Cacao, Verdoyant, Dom de Pin ni Jyfus.

### 6.4 Les quêtes d'un étage

Toutes les quêtes de la **tranche N du guide Duffus**, tous blocs confondus, moins celles qu'un admin masque (défaut : toutes, réglable par l'admin dans la revue).

---

## 7. Modèle de données (vue produit)

Le type exact de chaque colonne est dans ARCHITECTURE §5.

```
etage ──< donjon ──< case_succes ──< coche_case >──┐
  │                                                 ├── grimpeur
  ├──< quete ─────────────────────< coche_quete >──┘      │
  ├──< bonus (grimpeur facultatif)                     liste_officielle
  └── bilan_etage
journal · session (connexions)
```

| Table | Rôle | Champs clés |
|---|---|---|
| `etage` | Une épreuve | numéro, nom, **niveau_min / niveau_max**, level_cap, statut, ouvert_le, date_plancher_suivant, **palier_manuel** (vide = formule), id de la tranche Duffus, nom et adresse de l'image d'ambiance (facultatifs, T-28) |
| `donjon` | Un donjon de l'étage | étage, nom, niveau, ordre, bloc, id Duffus, id DofusDB (pour l'icône), masqué |
| `case_succes` | Une des 5 sous-cases | donjon, ordre (1 = classique), nom, condition, **est_classique**, id Duffus, masquée |
| `quete` | Une quête de l'étage | étage, nom, niveau, **bloc**, ordre, « jusqu'où », **fiche** (texte nettoyé), **nature**, **origine de la nature** (duffus, dofusdb ou admin), Dofus visés, ids Duffus et DofusDB, masquée |
| `liste_officielle` | Qui peut créer une fiche | id Discord, statut initial, ajouté par, ajouté le |
| `grimpeur` | Une fiche | **discord_user_id** (unique), pseudo en jeu (unique sans tenir compte de la casse), classe, statut, niveau déclaré, inscrit_le |
| `coche_case`, `coche_quete` | Ce qu'un grimpeur a coché | grimpeur, élément, cochée_le, cochée_par |
| `bonus` | Points bonus | étage, grimpeur (vide = collectif), points, motif, par, le, annulé |
| `bilan_etage` | La photo à l'ouverture du suivant | étage, figé_le, actifs, palier, score, détail |
| `journal` | Tout ce qui change | horodatage, acteur (id Discord), type, grimpeur, étage, détails, public |
| *(fichiers, pas une table)* | Copies datées des tables Duffus | `donnees/duffus/AAAA-MM-JJ/<table>.json`, versionnées dans le dépôt privé (ARCHITECTURE §6) |

Règles d'intégrité :
- une coche par couple (grimpeur, élément), garantie par la clé primaire ;
- **décocher supprime la ligne de coche**, et le journal en garde la trace. Une coche est un état que le joueur gère, pas une décision ;
- un élément coché par quelqu'un n'est **jamais supprimé**, seulement masqué. Un bonus est annulé, jamais effacé ;
- le site n'expose **jamais** un identifiant Discord numérique. Il montre le pseudo en jeu et, aux seuls participants connectés, le nom Discord (T-20) ;
- la date de dernière activité se calcule à partir des coches.

---

## 8. Réglages, points ouverts et questions pour Shadoaze

### 8.1 Tout ce qui peut changer se règle sans toucher au code (EX-109)

Les réponses par défaut d'EXIGENCES.md vont être soumises à Shadoaze. Chacune se règle donc **par configuration** (fichier versionné et redéploiement, environ 2 minutes, sans modifier le code) ou **par une action d'admin** sur le site.

- `config/regles.yaml` : les règles de jeu ;
- `config/etages.yaml` : la correspondance étage ↔ tranche ;
- `config/dofus.yaml` : la liste des Dofus ;
- les variables d'environnement, pour le mode du site.

| Point | Défaut appliqué | Comment le changer |
|---|---|---|
| T-01 Comptage des points | Par catégorie complète, 4 au maximum (**tranché**) | — |
| EX-09, EX-109 Multiplicateur du palier | m = 2, soit un palier de 2 × N | `regles.yaml` → `palier.points_par_joueur` ; palier manuel par étage (admin) |
| T-11 Catégorie vide | Ignorée, palier ⌈N × K ÷ 2⌉ | `regles.yaml` → `palier.categorie_vide: ignoree | offerte` ; palier manuel (admin) |
| T-02 Source des succès de donjon | Duffus s'il les a, sinon DofusDB, donjon par donjon | Automatique à l'import, signalé dans la revue ; l'admin masque ou corrige une sous-case |
| T-03 Donjons d'un étage | Ceux dont le niveau est dans la tranche, puis liste **validée par un admin** | Action admin : retirer ou ajouter un donjon (§4.8) |
| T-04 Étage ↔ tranche, cap | Étage 0 = première tranche (jusqu'au niveau 20), une tranche par étage, cap = borne haute | `etages.yaml` (tranche, cap, nom, dates) ; le cap se règle aussi par action admin |
| T-05 Bêta-test | Bêta fermée avant l'ouverture : admins et `BETA_TESTEURS` | Variable `BETA_TESTEURS` |
| T-06 Teaser | En ligne au plus tard le 6/11, compte à rebours jusqu'au 13/11 à 17 h | `SITE_OUVERT_LE` ; `TEASER_LIEN_ENTRER` le jour J |
| T-07 Étage 0 pendant le teaser | Cochage rétroactif à l'ouverture du site | `SITE_OUVERT_LE` pour ouvrir plus tôt |
| T-08 Encyclopédie et outils contre étages cachés | Non verrouillés (données du jeu) | `regles.yaml` → `modules.verrouiller_par_etage` (lot E) |
| T-09 Crédit | « Merci Duffus » avec lien vers duffus.fr, aucun lien par quête (**tranché**) | — |
| T-10 Ergonomie | La pyramide pour naviguer, l'organisation Duffus à l'intérieur d'un étage | — (choix de conception) |
| T-12 Quête principale hors de sa tranche | La tranche Duffus fait foi, l'écart est signalé | Action admin : masquer ou changer la nature |
| T-13 Coches d'un grimpeur en pause | Permises, elles comptent à la réintégration | `regles.yaml` → `coches.pause_peut_cocher` |
| T-14 Bot | Aucun bot côté joueurs. Annonce d'ouverture facultative. | Variable `DISCORD_ANNONCE_CHANNEL_ID` (vide = pas d'annonce) |
| T-15 Retrait d'une coche par un admin | Oui, avec un motif, journalisé, jamais affiché publiquement | — |
| T-16 Un succès coche « vaincre » | Oui, et décocher « vaincre » décoche les 4 autres | `regles.yaml` → `coches.succes_coche_vaincu` |
| T-17 Succès de donjon | Dans la liste de l'étage, plus un récapitulatif sur la fiche | — |
| T-18 Jauge d'un étage terminé | Figée (bilan), consultable | — |
| T-19 Connexion | Discord, réservée à la liste officielle | `regles.yaml` → `inscription.liste_officielle_obligatoire` |
| T-20 Champs de la fiche | Pseudo en jeu, classe facultative, nom Discord visible des participants | `regles.yaml` → `fiche.classe_obligatoire`, `fiche.afficher_nom_discord` |
| T-21 Palier non écrit dans le règlement | Formule affichée à côté de la jauge | — (suggérer à Shadoaze de l'écrire dans #concept-et-règles) |
| T-22 Points bonus | Ajout manuel par un admin, avec motif, sur l'étage en cours (demande du coordinateur) | `regles.yaml` → `bonus.actif`, `bonus.individuel_si_pause` |
| T-25 Archimonstres | Suivi personnel | Lot E2 |
| T-26 Mise à jour Duffus | Aspiration à la préparation de chaque étage, relue, puis figée | Commande lancée à la main |
| T-28 Nom et image des étages | « Étage N », sans image | `etages.yaml` ou action admin |
| T-29 Signe de vie | Date de dernière coche dans l'admin, sans alerte | — |
| Dofus qui rendent une quête principale | Tous ceux qui ont un guide chez Duffus | `config/dofus.yaml` |

### 8.2 Questions pour Shadoaze

Seulement ce qui **bloque la préparation des étages** ou change ce que voient les joueurs le 13/11. Pour chaque question, le défaut du §8.1 est déjà appliqué.

| # | Question | Défaut | Nécessaire avant |
|---|---|---|---|
| **Q1** | **Quelle tranche du guide Duffus pour chaque étage, et quel cap ?** (T-04) | Étage 0 = première tranche (jusqu'au niveau 20), puis une tranche par étage, cap = borne haute | La construction des étages, le 7/11 |
| **Q2** | **Quels donjons pour l'étage 0 et l'étage 1 ?** On propose ceux dont le niveau est dans la tranche. Tu valides ou tu corriges la liste. (T-03, EX-12 : le premier point doit rester facile) | Ceux de la tranche | La revue des étages 0 et 1, le 7/11 |
| **Q3** | Un étage **sans quête principale** (probablement l'étage 0) : la catégorie disparaît et le palier baisse en proportion (18 au lieu de 24 pour 12 joueurs), ou le point est offert à tous ? (T-11) | Elle disparaît, palier ⌈N × K ÷ 2⌉ | L'ouverture du site, le 13/11 |
| **Q4** | Quels **Dofus** rendent une quête « principale » ? Ceux d'événement (Cacao, Dom de Pin, Jyfus, Dofoozbz) et ceux qui se fabriquent (Dofawa, Dokoko, Dotruche) en font-ils partie ? | Tous ceux qui ont un guide chez Duffus | La construction des étages |
| **Q5** | Peut-on montrer le site aux grimpeurs **avant le 13/11**, pour qu'ils cochent l'étage 0 au fil de l'eau ? (T-05, T-07) | Non : bêta fermée, puis cochage rétroactif le 13/11 | Le 10/11 |
| **Q6** | **Points bonus** : à un joueur, à toute la guilde, ou les deux ? Comptent-ils pour un joueur en pause ? (T-22) | Les deux ; pas pour un joueur en pause | Le premier événement |
| **Q7** | Encyclopédie, stuffs, builder : vu leur coût (§9), acceptes-tu des **liens** vers les outils existants au lieu d'une copie « à l'identique » (EX-55 à EX-58) ? Et faut-il y cacher le contenu des étages futurs ? (T-08) | Liens pour l'encyclopédie et le builder ; rien de caché | Le lot E (après le 13/11) |
| **Q8** | Peux-tu ajouter la formule du palier (**2 × grimpeurs actifs**) au salon #concept-et-règles ? (T-21) | Formule affichée sur le site | — |

## 9. Les autres modules de duffus.fr

Le CdC (§4) demande de cloner l'Encyclopédie, les Avis de recherche, les Stuffs et le Builder, et les Archimonstres (sans la bourse). L'accord de l'auteur et l'accès à sa base **lèvent le blocage juridique et l'obstacle des données**. **Ils ne rendent pas le développement gratuit.** Les estimations sont en jours de dev d'un agent sur Opus, tests compris, avec la structure des tables Duffus déjà relevée.

| Module | Proposition | Effort réel | Priorité |
|---|---|---|---|
| **Guide** (cases, fiches, progression) | **Lot B**, c'est le cœur. | inclus | — |
| **Tableau de bord** | **Lot B** : la fiche du grimpeur et la tour. | inclus | — |
| **Avis de recherche** | **À refaire** (lot E1) : une liste à cocher par grimpeur, avec la mécanique et les filtres du guide. | 1 à 1,5 j | 1 |
| **Archimonstres** (suivi des captures, sans la bourse) | **À refaire** (lot E2) : environ 300 monstres par grimpeur, par étape et par zone, avec compteurs, filtre « qui a capturé X » pour s'entraider, et lien avec le Dofus Ocre. Le coût est surtout l'écran : 300 cases sur mobile doivent rester utilisables (recherche, regroupement, « toute l'étape »). Données : table `monsters` de Duffus, icônes DofusDB. | 3 à 4 j | 2 |
| **Stuffs** (stuffs recommandés par tranche) | Au début, des **liens** vers la page Duffus de la tranche, depuis l'en-tête de l'étage. **Intégration** ensuite si la table s'y prête. | 0,5 j (liens) ; environ 3 j (intégration) | 3 |
| **Encyclopédie** (objets, monstres, ressources…) | Des **liens**, vers DofusDB ou Duffus. La refaire, ce sont des milliers de fiches à afficher, chercher et tenir à jour à chaque version du jeu, pour un service qui existe déjà. | 0,5 j (liens) ; plus de 10 j pour la refaire | 4, en liens seulement (Q7) |
| **Builder** | Un **lien** vers un builder existant. C'est un produit à part entière (caractéristiques, conditions, panoplies, effets), de plusieurs semaines, que la moindre erreur de calcul rend inutile. | plusieurs semaines | hors périmètre, à rediscuter avec Shadoaze (Q7) |
| **Outils** (hors tutoriels) | Une page « Boîte à outils » avec des liens, plus un encart Almanax du jour. | 0,5 j + 1 j | 5 |
| **Bourse aux échanges** | **Retirée** (CdC §4, DECISIONS §7). | — | — |

**Ordre proposé après le lot C** : avis de recherche, archimonstres (suivi personnel, T-25), stuffs (liens puis intégration), boîte à outils. Encyclopédie et builder restent des liens, sauf demande expresse de Shadoaze une fois les coûts connus.

**Honnêteté sur l'écart** : EX-55 à EX-58 demandent ces modules « à l'identique », avec le statut « ferme ». Notre recommandation (des liens pour l'encyclopédie et le builder) s'en écarte **pour des raisons de coût**, pas de faisabilité. C'est donc à Shadoaze de trancher, en connaissant les chiffres (§8.2, Q7). Si ces outils sont recopiés, la question du verrouillage du contenu des étages futurs se pose aussi (T-08, réglage `modules.verrouiller_par_etage`).

---

## 10. Exigences non fonctionnelles

- **Calendrier** : teaser en ligne **au plus tard le vendredi 6/11** (lot A). Cœur prêt et testé **pour le vendredi 13/11 à 17:00** (lot B).
- **Disponibilité** : une coupure de quelques heures est acceptable, une perte de coches ne l'est pas. Sauvegarde quotidienne chiffrée (ARCHITECTURE §5).
- **Fraîcheur** : les coches des autres apparaissent quand on recharge la page. Pas de temps réel poussé au lot B.
- **Mobile d'abord** : pas de défilement horizontal à 360 px, et des cases d'au moins 44 × 44 px au toucher.
- **Thème sombre uniquement** (`color-scheme: dark`), sans aucun fond blanc ni thème clair : arbitrage du chef de projet et DA. Aucun visuel, logo, police ou capture d'Ankama. Le pied de page « projet de fans, non officiel » de la DA est obligatoire, à côté de « Merci Duffus ».
- **Accessibilité** : badges, pastilles et jauge lisibles sans la couleur (icône, forme ou texte), de vraies cases à cocher (clavier, lecteur d'écran), focus visible, contrastes mesurés de la DA (texte 15:1, catégories de 7,4 à 9:1), `prefers-reduced-motion` respecté.
- **Confidentialité** : le site est **privé**, réservé aux participants (CdC) : toutes les pages sauf le teaser exigent la connexion. Il ne montre que le pseudo en jeu, la classe, le niveau déclaré et la progression. Les identifiants Discord restent côté serveur. Les pages demandent aux moteurs de recherche de ne pas les indexer.
- **Crédit et nettoyage** : « Merci Duffus » avec un lien vers duffus.fr dans le pied de **chaque** page, teaser compris (T-09). Aucun autre lien vers duffus.fr. Aucun logo, lien Twitch, serveur Discord ou widget de dons du site d'origine (EX-61). Aucune publicité ni demande de don (EX-107).
- **Politesse envers Duffus** : jamais d'appel à duffus.fr ni à sa base pendant la navigation. L'aspiration est lancée à la main, à faible débit (ARCHITECTURE §6).
- **Traçabilité** : toute écriture a un auteur et une date (journal).
- **Fuseau** : tout est stocké en UTC et affiché en heure de Paris.
- **Coût** : environ 5 $ par mois, plus un nom de domaine à environ 10 € par an (ARCHITECTURE §8).

---

## Annexe A : traçabilité des exigences

Chaque exigence d'`EXIGENCES.md` → section de cette spec → lot. « — » = abandonnée (remplacée par l'exigence indiquée) ou hors du site.

| Exigence | Section | Lot |
|---|---|---|
| EX-01 à EX-06 (4 catégories, point par catégorie complète, aucun point partiel) | §5.1, §1.3 | B |
| EX-07 (catégories indépendantes, pas de profil) | §5.1 | B |
| EX-08 (full succès ⇒ vaincu) | §5.1, §4.4 (T-16) | B |
| EX-09, EX-10 (palier 2 × actifs, recalcul immédiat) | §5.2, §4.7 | B |
| EX-11 (seul le contenu de l'étage compte) | §5.1, §6.4 | B |
| EX-12 (premier point facile) | §8.2 Q2 (choix des donjons) | B |
| EX-13, EX-14, EX-26 (cap, jouer sous le cap, cap affiché) | §4.4 en-tête, §1.4, §8.1 T-04 | B |
| EX-15, EX-16 (entre grimpeurs, sans PL, confiance, exclusion) | §1.2, §1.4, §4.7 | B |
| EX-17 à EX-22 (fractions, difficultés, barème 1/2/3) | — (remplacées par EX-01 à EX-09) | — |
| EX-23, EX-24 (étage = tranche Duffus, source unique) | §6.1, §8.1 T-04 | B |
| EX-25 (donjons et quêtes à chaque étage) | §5.3 (T-11) | B |
| EX-27 (ouverture manuelle) | §4.8 | B |
| EX-28, EX-29 (étage 0 le 30/10, étage 1 pas avant le 13/11) | §4.8 | B |
| EX-30 (prêt pour le 13/11) | §10, LOTS calendrier | A, B |
| EX-31, EX-111 (étages non générés, rien côté navigateur) | §4.3 | B |
| EX-32 (une jauge par étage) | §5.2, §5.5 | B |
| EX-33, EX-34 (anciennes dates, ancien contenu de l'étage 0) | — (EX-28, EX-29, EX-23) | — |
| EX-35, EX-36 (un compte par grimpeur, accès réservé) | §4.2, §10 | B (accès réservé dès A) |
| EX-37 (rôle « Administrateur ») | §3, §4.2 | B |
| EX-38 (fiche : pseudo, classe) | §4.2, §4.6 (T-20) | B |
| EX-39 à EX-41 (pause, retardataire, réintégration manuelle) | §4.7 | B |
| EX-42 (rattrapage automatique) | — (EX-41) | — |
| EX-43 (exclusion, signe de vie) | §4.7 (T-29) | B |
| EX-44 à EX-48 (cocher, 5 cases, suivi, mise à jour immédiate) | §4.4, §6.2 | B |
| EX-49, EX-50, EX-59 (tableau de bord, ce qui manque) | §4.6 | B |
| EX-51, EX-102 (guide à l'identique, ergonomie Duffus) | §4.4 (T-10) | B |
| EX-52 (fiche de quête) | §4.4, §6.1 | B |
| EX-53 (archimonstres) | §9 | E2 |
| EX-54 (avis de recherche) | §9 | E1 |
| EX-55 à EX-58 (encyclopédie, outils, stuffs, builder) | §9, §8.2 Q7 | E (à trancher) |
| EX-60, EX-61 (sans bourse, sans habillage Duffus) | §9, §10 | A, B |
| EX-62 (« Merci Duffus ») | §1.2, §10 | A, B |
| EX-63 (tranches non dévoilées verrouillées) | §4.3, §4.4 | B |
| EX-64 (succès de boss ajoutés) | §4.4, §6.1 (T-02) | B |
| EX-65 à EX-68 (principale ou secondaire par quête, définition, déterministe, un seul guide) | §4.4, §6.3 | B |
| EX-69 (deux guides) | — (EX-68) | — |
| EX-70 (contenu intégré, sans lien) | §4.4, §6.1 | B |
| EX-71, EX-113 (récupération par nos soins, copie chez nous) | §6, ARCHITECTURE §6 | B |
| EX-72, EX-73 (jauge visible, éligibilité signalée) | §4.5 | B |
| EX-74 (pyramide) | §4.3 | B |
| EX-75 (pas de règle anti-bonus) | rien à coder | — |
| EX-76 (cadenas visuel) | — (EX-31) | — |
| EX-77, EX-78 (fiches publiques, qui ne l'a pas fait) | §4.6 | B |
| EX-79 à EX-81 (liste unique, filtre cumulatif, badges) | §4.4 | B |
| EX-82, EX-83 (bouton d'ouverture, vérification détaillée) | §4.8 | B |
| EX-84, EX-85 (gestion des grimpeurs, retrait d'une coche) | §4.7 (T-15) | B |
| EX-86, EX-87, EX-89 à EX-92 (validation admin, screens, bot IA) | — (EX-88) | — |
| EX-88 (zéro screen) | §1.2 | B |
| EX-93 (bot d'atelier) | hors site (outil interne existant) | — |
| EX-94 (rôle du bot) | §3, §8.1 T-14 | B (annonce facultative), C |
| EX-95 à EX-97 (secret, teaser, annonce) | §4.1 | A |
| EX-98, EX-99 (trailers) | hors site (Marceau, après le site) | — |
| EX-100, EX-108 (appel, hébergement local) | — | — |
| EX-101, EX-103 (esprit des maquettes, lore) | DA, §4.1, §4.3 | A, B |
| EX-104 (images d'étage) | §4.3, §4.8 (T-28) | B |
| EX-105, EX-107 (budget de 3 à 4 € par mois, non lucratif) | §10, ARCHITECTURE §10 | A |
| EX-106 (contenu Duffus derrière la connexion) | §10 | B |
| EX-109 (règles ajustables) | §8.1 | B |
| EX-110 (testé avant le 13/11) | LOTS calendrier | B |
| EX-112 (le manuel plutôt que l'automatique) | §1.2, §4.7, §4.8 | B |
| EX-114, EX-115 (petite échelle, téléphone) | §10 | A, B |
