# L'Épreuve des Dieux : liste des exigences

Version 1, 27/10/2026. Rédigée par l'analyste fonctionnel à partir d'une relecture ligne à ligne des sources ci-dessous. Ce document **prime sur `SPEC.md`** quand ils se contredisent (voir l'en-tête de `SPEC.md`).

## Sources et ordre de priorité

| Abréviation | Source | Poids |
|---|---|---|
| **Info Marceau** | Informations données par Marceau le 27/10 : accord de l'auteur de duffus.fr (« Merci Duffus » en pied de page, pas d'export), duffus.fr source unique du contenu des étages, pause et réintégration manuelles. | Font foi. |
| **Conv.** | Conversation privée Marceau (« Mars ») ↔ Shadoaze, du 25/10 15 h 21 au 27/10 13 h 49. Confidentielle : seuls de courts extraits sont cités. | Ce qui est dit **après** le CdC n° 4 l'emporte sur lui. |
| **Règlement** | `docs/discord/concept-et-règles.md`, règlement officiel de Shadoaze, version exportée le 27/10 (déjà réécrite avec le barème à 4 points). | Ce que voient les joueurs. |
| **CdC n° 1 à 4** | `docs/sources/` : n° 1 (prérequis et questions, 25/10 17 h 17), n° 2 (26/10 12 h 37), n° 3 (26/10 12 h 52), n° 4 (26/10 14 h 06, **validé**). | Le n° 4 fait foi sauf sur ce qui a été tranché après. |
| **DV4** | `docs/DECISIONS-V4.md`, synthèse de Marceau. | Comparé, ne fait pas foi. |
| **Ancien règlement** | `docs/REGLES.md` (copie du 25/10) et `docs/REPONSES-SHADOAZE.md`. | Historique. |

## Comment lire ce document

- Chaque exigence a un numéro **EX-nn**, un énoncé, une **source** (date, heure, auteur, courte citation) et un **statut** :
  - **ferme** : décidé et non contredit ensuite ;
  - **à confirmer** : évoqué, mais pas tranché, ou tranché seulement par interprétation ;
  - **abandonnée** : remplacée par une autre exigence, indiquée.
- Les citations reprennent l'orthographe d'origine.
- Tout ce qui est **interprétation** de l'analyste est signalé par la mention *(interprétation)*.
- Les points ouverts ont un identifiant **T-nn** (section « Contradictions et trous »), chacun avec une réponse par défaut.

---

## 1. Règles du jeu et barème

**EX-01 · Quatre catégories, un point chacune.** Par étage, chaque grimpeur peut gagner un point dans chacune de ces 4 catégories : (1) donjons validés, (2) donjons en full succès, (3) quêtes principales, (4) quêtes secondaires. Il rapporte donc de 0 à 4 points par étage.
- Source : Conv. 26/10 13 h 35, Shadoaze : « Tout compte 1 point parmis 4 catégories ». Règlement III : « jusqu'à 4 points gagnés par joueur par étage ».
- Statut : **ferme**. Remplace EX-17, EX-18, EX-19.

**EX-02 · Point « donjons » : tous les donjons de l'étage.** Le point n'est accordé que lorsque le grimpeur a vaincu **tous** les donjons de l'étage.
- Source : Règlement III : « Valider tout les donjons présents dans un étage = 1 point ». Conv. 26/10 13 h 52, Shadoaze : « Mon but est que "tout le monde fasse au minimum tout les donjons" ».
- Statut : **ferme**. Contredit la lettre du CdC n° 4 (voir T-01).

**EX-03 · Point « full succès » : les 5 succès de tous les donjons de l'étage.** Le point n'est accordé que lorsque les 5 cases de **chaque** donjon de l'étage sont cochées.
- Source : Règlement III : « Valider tout le full succès de tout les donjons présents dans un étage = 1 point ». CdC n° 4 §3 : le point « n'est accordé […] que lorsque les 5 sous-cases de ce donjon […] sont intégralement à TRUE ».
- Statut : **ferme** (le CdC n° 4 parle d'un point par donjon : voir T-01).

**EX-04 · Point « quêtes principales » : toutes celles de l'étage.**
- Source : Règlement III : « Valider toutes les quêtes principales ( prérequis ou quêtes permettant l'acquisition des dofus ) d'un étage = 1 point ».
- Statut : **ferme**.

**EX-05 · Point « quêtes secondaires » : toutes celles de l'étage.**
- Source : Règlement III : « Valider toutes les quêtes secondaires (quêtes utiles pour les joueurs cherchant le 100% succès) d'un étage = 1 point ».
- Statut : **ferme**.

**EX-06 · Aucun point partiel.** Pas de point par donjon, par succès ni par quête. Avoir 4 succès sur 5, ou une partie des quêtes, ne rapporte rien.
- Source : Conv. 26/10 13 h 48, Mars propose 1 point par succès ; 13 h 52, Shadoaze refuse : « ça va commencer a faire des sommes de points énorme » et « tu en as qui seront peut être tenter de bypass certains donjons » ; 13 h 53, Mars : « ok ok parfait on reste comme ca ».
- Statut : **ferme**. Le CdC n° 4 dit le contraire (« 1 quête cochée = +1 point ») : voir T-01.

**EX-07 · Pas de profil de joueur : chacun choisit à chaque étage.** Les 4 catégories sont indépendantes. Un grimpeur peut viser n'importe lesquelles et changer d'un étage à l'autre.
- Source : Conv. 26/10 13 h 33, Shadoaze : « Ça t enfermé pas dans une catégorie et tu peux alterner a chaque étage en fonction de ta motivation » ; 13 h 42 : « on peut enlever le concept de difficulté et d éclaireur / aventurier ».
- Statut : **ferme**.

**EX-08 · Le full succès implique le donjon vaincu.** Le succès de base « vaincre le boss » fait partie des 5 succès : un donjon en full succès est forcément vaincu, donc compte pour la catégorie 1.
- Source : Conv. 25/10 17 h 33, Shadoaze : « le full succes représente bien les 5 succès liés au donjon et quelqu un qui fait le full succes passerait donc de 1 point a 2 points ». CdC n° 2 et 3 : « Faire le Full Succès valide automatiquement le donjon simple ».
- Statut : **ferme**.

**EX-09 · Palier de l'étage = 2 × nombre de grimpeurs actifs.** L'étage est éligible à l'ouverture quand la somme des points des grimpeurs actifs atteint ce palier.
- Source : Conv. 26/10 13 h 35, Shadoaze : « Palier pour valider un étage = 2* le nombre de joueurs actifs » ; 13 h 37 : « vu que la moyenne théorique est a 2.5 ça fait une moyenne basse atteignable ». CdC n° 4 §1. Règlement I : « Les points nécessaires dépendent du nombre de grimpeurs actifs actuellement » (sans la formule).
- Statut : **ferme**. Remplace le seuil de 75 % (EX-19). Cas d'une catégorie vide : T-11.

**EX-10 · Le palier suit en direct le nombre d'actifs.** Un grimpeur en pause (ou pas encore intégré) ne compte ni dans le palier ni dans le score, et le palier se recalcule immédiatement.
- Source : CdC n° 4 §1 : « Son état passe à inactif, ce qui baisse immédiatement le Palier ». CdC n° 3 : « son score max et actuel passent à 0 ».
- Statut : **ferme**.

**EX-11 · Seul le contenu de l'étage en cours rapporte des points.** Ce sont les donjons et quêtes de la tranche de niveau de l'étage en cours qui comptent. Valider d'autres donjons ou quêtes n'a aucun effet sur la jauge.
- Source : Conv. 26/10 14 h 11, Shadoaze : « les donjons/quêtes et tout sont ceux compris dans l étage en cours » ; 14 h 15 : « c est les quêtes et donjons liés a cette tranche qui rapporte des points pour l étage en cours ( pour pas que valider d autres donjons / quêtes n est d impact ) ».
- Statut : **ferme**.

**EX-12 · Le premier point doit rester facile.** Le point « donjons » doit rester à la portée des joueurs qui ont peu de temps, pour qu'ils se sentent utiles.
- Source : Conv. 26/10 13 h 54, Shadoaze : « j'ai envie que le 1 er point soit " facile" a aller chercher pour les gens qui ont le moins de temps a investir ». Règlement III : « Les premiers points seront plus faciles à gagner ».
- Statut : **ferme** (principe de conception du contenu ; rien à coder, sinon dans le choix des donjons d'un étage, voir T-03).

**EX-13 · Cap de niveau par étage.** Chaque étage a un cap. Une fois le cap atteint, le grimpeur bloque son XP jusqu'à l'ouverture de l'étage suivant. Un dépassement involontaire est toléré (« 21 au lieu de 20 »).
- Source : Règlement I. Conv. 25/10 17 h 56, Shadoaze : « Pas de marge réelle sur le cap, je compte sur la bonne volonté des gens et autorise cette "marge" dans le cas où le cap […] aurait était dépassé sans faire exprès ».
- Statut : **ferme** (règle de jeu sur l'honneur, non vérifiée). Évolution : le CdC n° 1 prévoyait une « tolérance +1 » codée ; remplacée par la bonne volonté. Valeur du cap de chaque étage : T-04.

**EX-14 · Jouer sous le cap est autorisé.** Seul le dépassement pose problème.
- Source : Conv. 25/10 17 h 33, Shadoaze : « 3. Exactement ». CdC n° 4 §3.
- Statut : **ferme**.

**EX-15 · Entre grimpeurs uniquement, sans PL.** Les donjons et succès doivent être faits entre grimpeurs, au cap indiqué. Un PL ou la présence d'un joueur extérieur à l'événement dans le groupe fait que le donjon ne compte pas (le grimpeur ne doit pas le cocher).
- Source : Règlement II : « La complétion de donjons/succès doit se faire entre grimpeurs et au level cap indiqué » et « Le Pl n'est pas "autorisé" et n'entrainera pas la validation d une étape ». Conv. 25/10 17 h 56, réponse 10 : « Oui » (validation refusée si un joueur hors event est dans le groupe).
- Statut : **ferme** (règle sur l'honneur, non vérifiée par le site).

**EX-16 · Système de confiance, exclusion en cas de triche.** Aucune vérification n'est demandée. La triche et le contournement volontaire peuvent entraîner une exclusion.
- Source : Règlement II : « aucune vérification ne sera demandé » et « La triche, la falsification de preuves […] peuvent entraîner une exclusion ». Conv. 26/10 13 h 02, Shadoaze : « En vrai on peut trust et si les gens "trichent" c est dommage pour eux ».
- Statut : **ferme**.

**EX-17 · Fractions 1/4, 1/2, 3/4.** Déblocage quand 1/4 des grimpeurs ont fait toutes les quêtes, 1/2 le full succès et 3/4 vaincu les donjons, les 3 conditions étant requises.
- Source : Ancien règlement I. Conv. 25/10 15 h 28, Shadoaze : « les 3 ! comme ça ça oblige a ce que 75% de la commu participe ».
- Statut : **abandonnée**. Remplacée le 25/10 17 h 33 par une jauge à points (EX-19), puis le 26/10 13 h 35 par EX-01 et EX-09.

**EX-18 · Trois difficultés (Collectionneur, Éclaireur, Aventurier).** Historique des évolutions :
1. 25/10 15 h 30-15 h 32, Shadoaze : les difficultés mesurent le temps de jeu (« 1 : 15/20 h semaine, 2 : 10h env, 3 : 4 a 7h max ») ; la difficulté 1 est la plus dure (Mars croyait l'inverse et demande d'inverser l'ordre, 15 h 34).
2. 25/10 15 h 42, Shadoaze : « les "difficultés" sont plus a titre informatif ».
3. 25/10 17 h 33 : chaque difficulté rapporte 3, 2 ou 1 point (EX-19).
4. 25/10 22 h 14, Shadoaze : Collectionneurs = quêtes principales + annexes + donjons en full succès ; Éclaireur = quêtes principales optionnelles + full succès ; Aventurier = quêtes principales optionnelles + donjons vaincus.
5. 26/10 13 h 12 : confusion sur l'ordre. Mars écrit « c'est éclaireur, puis aventurier, puis colelctionneur » alors que le barème de 22 h 14 met l'Éclaireur (full succès, 2 points) au-dessus de l'Aventurier (1 point). Contradiction jamais levée, devenue sans objet.
6. 26/10 13 h 42, Shadoaze : « on peut enlever le concept de difficulté et d éclaireur / aventurier et tout ».
- Statut : **abandonnée**. Remplacée par EX-07.

**EX-19 · Barème 1/2/3 points et seuil à 75 %.** Aventurier 1, Éclaireur 2, Collectionneur 3 points ; étage débloqué à 75 % du maximum théorique (somme des maxima des actifs) ; seuil de 75 % à tous les étages.
- Source : Conv. 25/10 17 h 33 (« la barre devrait être remplie a 75% de cette valeur ») ; 21 h 22, réponse 6 : « oui » ; CdC n° 2 et 3.
- Statut : **abandonnée**. Remplacée par EX-01 et EX-09 (26/10 13 h 35). L'idée de Shadoaze du 26/10 13 h 16 (« un cap fixe en fonction du nombre de joueurs ») est l'étape intermédiaire.

**EX-20 · Sur-performance et paliers stricts.** Un joueur pouvait rapporter plus que sa difficulté sans augmenter l'objectif ; pas de point pour les quêtes sans le full succès.
- Source : Conv. 25/10 20 h 46 (Mars) puis 21 h 05, Shadoaze : « exact » ; 21 h 22, réponses 1 et 2 : « ok ». CdC n° 2 et 3.
- Statut : **abandonnée** (sans objet sans difficultés). Dans le modèle EX-01, les quêtes rapportent un point à elles seules.

**EX-21 · Changement de difficulté par un admin, avec recalcul du seuil.**
- Source : Conv. 25/10 17 h 56, réponse 7 : « pourra choisir de la changer en contactant un admin entraînant le recalcul des points nécessaire ».
- Statut : **abandonnée** (plus de difficulté, EX-07).

**EX-22 · Quêtes sans valeur pour Éclaireur et Aventurier ; Collectionneur = 100 % du guide complet.**
- Source : Conv. 25/10 22 h 27, Shadoaze : « pour éclaireur et aventurier les quêtes servent seulement a acquérir les Dofus mais aucune obligation et ça rapporte pas de point » ; 21 h 22 : Collectionneurs = « 100% de complétion sur ce guide complet » (duffus.fr/guide-complet).
- Statut : **abandonnée**. Remplacée par EX-04 et EX-05 : les quêtes de la tranche rapportent désormais des points à tout le monde *(interprétation : « quêtes principales + quêtes secondaires » d'un étage = l'ensemble des quêtes de la tranche dans le guide complet)*.

---

## 2. Étages et calendrier

**EX-23 · Un étage = une tranche de niveau du guide Duffus.** Le guide complet de Duffus découpe le jeu en tranches de niveau ; chaque tranche correspond à un étage. Exemple donné : la tranche 40-50 serait l'étage 3.
- Source : Conv. 26/10 10 h 41, Shadoaze : « a chaque fois t'as une tranche de niveau qui correspondrait a nos étages » ; 10 h 42 : « la tranche 40 50 qui serait notre "étage 3" » ; 14 h 15 : « chaque étage est représentée par une tranche de niveau sur le site duffus ».
- Statut : **ferme** pour le principe. La table exacte étage ↔ tranche est **à confirmer** (T-04).

**EX-24 · duffus.fr est la source unique du contenu des étages.** Donjons, succès détaillés, quêtes principales et secondaires viennent de duffus.fr. Les salons Discord « étage-X » de Shadoaze ne sont pas une source de données.
- Source : Info Marceau. Conv. 26/10 14 h 13, Mars : « L'intégralité des listes de quêtes principales, quêtes secondaires, ainsi que l'ensemble des succès détaillés de chaque donjon seront extraits […] depuis le site source duffus.fr » ; 14 h 15, Shadoaze : « Oui parfait ». CdC n° 4 §3.
- Statut : **ferme**. Les salons d'étage (Conv. 25/10 21 h 22 : « j'ai fait les 10 premiers ») comme source : **abandonnée**. Limite : le guide Duffus ne contient pas les succès de donjon (T-02).

**EX-25 · Chaque étage a des donjons et des quêtes.**
- Source : Conv. 25/10 21 h 22, réponse 5 : « oui ».
- Statut : **ferme** (affirmation de Shadoaze, à vérifier à l'import de chaque étage ; cas d'une catégorie vide : T-11).

**EX-26 · Le cap de chaque étage est connu des joueurs.** *(interprétation : les joueurs doivent connaître le cap pour bloquer leur XP, EX-13 ; le site est le meilleur endroit pour l'afficher.)*
- Source : Règlement I : « Un level cap est lié à chaque étage ».
- Statut : **à confirmer** (valeur et affichage, T-04).

**EX-27 · Ouverture manuelle par un admin, jamais automatique.** Quand le palier est atteint, un admin fait une dernière vérification puis ouvre l'étage.
- Source : Conv. 25/10 17 h 56, réponse 13 : « Je préfère qu un admin ouvre manuellement l étage une fois les conditions remplies afin de pouvoir faire une dernière vérification manuelle ». CdC n° 2, 3 et 4.
- Statut : **ferme**.

**EX-28 · Étage 0 : vendredi 30/10/2026 à 17 h (accès anticipé).** Phase de deux semaines : création du personnage, entrée dans la guilde, métiers, découverte, bêta-test, questions.
- Source : Conv. 25/10 17 h 56, réponse 5 : « release l étage 0 vendredi 30/10 a 17h » ; 26/10 11 h 06 : « dans 3 jours c'est purement "l'acces anticipé" ». Règlement IV. CdC n° 4 §4.
- Statut : **ferme**.

**EX-29 · Étage 1 : jamais avant le vendredi 13/11/2026 à 17 h,** même si le palier de l'étage 0 est atteint.
- Source : Conv. 25/10 17 h 56 : « étage 1 bloqué jusqu au vendredi 13/11 17h même si la jauge de complétion est remplie ». Règlement IV : « il sera impossible de débloquer l'étage 1 avant le vendredi 13/11/2026 à 17h ». CdC n° 4 §4.
- Statut : **ferme**.

**EX-30 · Vrai départ mi-novembre ; le site doit être prêt pour le 13/11.** La date peut glisser un peu si besoin, sans aller jusqu'à mi-décembre. Le site ne sera pas complet le 30/10.
- Source : Conv. 26/10 11 h 06, Shadoaze : « le vrai départ il est vers mi Novembre mais on peut décaler un peu pour etre full pret » ; 11 h 03, Mars : « pas mi décembre non plus » ; 27/10 13 h 09, Mars : « Pour le 13 c'est bon c'est « « sur » » / Pour le 30 non tout sera pas prêt ».
- Statut : **ferme**.

**EX-31 · Les étages non ouverts sont invisibles.** Ils restent cachés pour garder la surprise. Ils ne sont pas générés du tout dans l'interface, et le nombre total d'étages n'est pas révélé.
- Source : Conv. 25/10 17 h 56, réponse 14 : « on garde les étages non ouvert cachés afin de maintenir la surprise ». CdC n° 4 §2 : « ne sont pas encore générés graphiquement, rendant leur accès et leur visualisation techniquement impossibles ». Lore (#présentation) : « Nul ne connaît le nombre de ses étages ».
- Statut : **ferme** (le nombre d'étages non révélé est une *interprétation* tirée du lore). Évolution : cadenas visuel (EX-76) remplacé par la non-génération.

**EX-32 · Une jauge par étage.** Chaque étage, y compris l'étage 0, a sa propre jauge et son propre palier.
- Source : CdC n° 4 §1 (« la jauge globale de l'étage ») et §4 (« même si le palier de l'étage 0 est atteint »).
- Statut : **ferme**. Ce que devient la jauge d'un étage après son ouverture : T-18.

**EX-33 · Dates « minuit » du 31/10 et du 15/11.**
- Source : Ancien règlement IV ; CdC n° 1, question 5.
- Statut : **abandonnée**. Remplacée par EX-28 et EX-29 (Conv. 25/10 17 h 56).

**EX-34 · Contenu de l'étage 0 : Kardorim et 24 quêtes d'Incarnam.** Donjon Crypte de Kardorim, full succès = 5 succès, « toutes les quêtes d'Incarnam » = 24 quêtes sur une capture, cap 20, nom « Le Seuil ».
- Source : Ancien règlement I (exemple) ; CdC n° 1 §A.2 ; Conv. 25/10 17 h 46, Shadoaze : « pour les quêtes on se basera sur les paroles des gens ».
- Statut : **abandonnée** en tant que définition : remplacée par EX-23 et EX-24 (contenu = tranche Duffus de l'étage 0). Le Kardorim peut rester un donjon de l'étage 0 ; le nom « Le Seuil » est **à confirmer** (T-28).

---

## 3. Comptes et rôles

**EX-35 · Un compte par grimpeur, avec connexion.** Le site n'est pas consultatif : chacun coche sa progression, donc chacun se connecte.
- Source : Conv. 26/10 12 h 44, Mars : « faut que j'intgère aussi un syteme de mdp login pour le syteme de coche » ; 12 h 46, Shadoaze : « pour que chacun est son "compte" ».
- Statut : **ferme**. Le moyen de connexion (mot de passe ou Discord) et la création des comptes sont **à confirmer** (T-19).

**EX-36 · Accès réservé aux participants.** Le site n'est pas trouvable ni consultable par le public. Le lien est donné dans le Discord de l'événement.
- Source : Conv. 26/10 10 h 09, Shadoaze demande un accès « limité a ceux qui participent » à cause des droits d'auteur ; Mars : « c'est restreint / Le lien sera donné dans le discord ».
- Statut : **ferme**.

**EX-37 · Rôle admin : « Administrateur ».** Les admins sont ceux qui ont ce rôle sur le Discord. Marceau est admin.
- Source : Conv. 25/10 17 h 56, réponse 6 : « Administrateur » ; 21 h 22 : « je t'ai passer admin ».
- Statut : **ferme**. La liste des admins du site : T-20.

**EX-38 · Fiche grimpeur : pseudo en jeu, classe.** L'inscription se fait auprès de Shadoaze avec le pseudo en jeu. La classe est un choix informatif parmi les 19 classes. La liste officielle compte 10 grimpeurs au 26/10, la plupart sans pseudo en jeu.
- Source : Règlement IV : « votre pseudo IG » ; #choix-classe : « Purement informatif » ; #liste-grimpeurs (26/10 19 h 54) : « ( pseudo ig à renseigner ) ».
- Statut : **à confirmer** pour les champs exacts (T-20). La **difficulté** dans le registre (CdC n° 1 §A.4) : **abandonnée** (EX-07).

**EX-39 · Pause : le grimpeur sort du calcul.** Un admin peut passer un grimpeur en pause ; il ne compte alors plus dans la jauge (ni palier, ni score). Le grimpeur prévient l'organisateur ; c'est un admin qui agit.
- Source : Conv. 25/10 21 h 41, Shadoaze : « juste avoir une option pour passer un joueur en pause afain qu'il ne compte pas dans l'algorithme est déja un tres bon point ». Règlement V : « geler votre personnage au niveau de l'événement ». Info Marceau : pause manuelle par un admin.
- Statut : **ferme**.

**EX-40 · Retardataire : hors calcul tant qu'il n'est pas intégré.** Un grimpeur arrivé en cours de route ne compte pas dans l'algorithme (ni ses points, ni le palier) tant qu'un admin ne l'a pas intégré.
- Source : Conv. 25/10 17 h 56, réponse 8 : « n est pas pris en compte tant qu'il n' a pas rattrapé les autres grimpeurs » ; 21 h 22, réponse 3 : « non, quelqu'un qui commence le projet genre 1 mois après n'est intégré à l'algorithme que si il rattrape au minimum le grimpeur le moins avancé » (Mars proposait que ses points comptent avant).
- Statut : **ferme**.

**EX-41 · Réintégration manuelle, au cas par cas.** Retour de pause et intégration d'un retardataire sont décidés par un admin. Le critère « avoir rattrapé au minimum le grimpeur actif le moins avancé » est jugé par l'admin, sans calcul automatique.
- Source : Conv. 25/10 21 h 41, Shadoaze : « Ne pas s'embeter avec ça en vrai on réintégrera manuellement les joueurs en pause / les retardataires au cas par cas ». Règlement V : « Vous pourrez à tout moment le "dégeler " en rattrapant la progression du groupe ( au minimum le grimpeur actif le moins avancé) ». Info Marceau.
- Statut : **ferme**.

**EX-42 · Critère automatique de rattrapage.** Successivement : « atteindre le cap de l'étage en cours » (Mars, 25/10 20 h 46, approuvé « exact » par Shadoaze à 21 h 05, puis contredit par son « non » de 21 h 22), puis « le moins avancé en niveau, déclaré avec /niveau » (Mars, 21 h 35).
- Statut : **abandonnée**. Remplacée par EX-41 (Shadoaze, 21 h 41).

**EX-43 · Exclusion.** Un grimpeur peut être exclu pour non-respect des règles ou pour absence de signe de vie d'environ 3 semaines. Ce qui compte comme signe de vie est laissé au jugement des admins.
- Source : Règlement V : « pas de signe de vie pendant 3 semaines ». Conv. 25/10 17 h 56, réponse 11 : « Ce sera au jugement des admins ».
- Statut : **ferme** (règle). Le site doit permettre de retirer un exclu du calcul *(interprétation)*. Aide à la décision : T-29.

---

## 4. Progression et cases à cocher

**EX-44 · Le grimpeur coche chaque quête faite.** La case cochée sert à la fois de preuve et d'indicateur de progression (« où tu en es »).
- Source : Conv. 26/10 10 h 14 et 10 h 50, Shadoaze (fonction du site Duffus : « quand tu as validé une quete tu peux la cocher et comme ça tu sais 1. ou tu en est ») ; 12 h 53, Mars : « vu que tu veux qu'on coche, ca peut etre ca les preuves non ? » ; 12 h 55, Shadoaze : « Oui clairement ».
- Statut : **ferme**.

**EX-45 · Cinq cases par donjon.** Chaque donjon a 5 cases : « vaincre le boss » (succès de base) et 4 succès propres au boss, dont le Duo. Les sites communautaires n'affichent que les 4 derniers, le succès de base étant commun à tous les boss.
- Source : Conv. 25/10 22 h 23, Shadoaze : « a chaque fois t en as 5 / Le succès de base c est battre le boss / Le 2 eme.succes c est toujours duo » ; 26/10 14 h 01 : « sur les sites ils vont indiquer 4 succès » ; 14 h 03, Mars : « c'est 4 succèes+ le valider classico ». CdC n° 4 §3.
- Statut : **ferme**. Les succès sont les mêmes pour tout le monde mais propres à chaque donjon (26/10 13 h 00).

**EX-46 · Les cases de succès servent au suivi entre sessions.** Le grimpeur coche chaque succès au fil de ses tentatives pour savoir où il en est ; seule la case « vaincre » et la complétion des 5 cases ont un effet sur les points (EX-02, EX-03).
- Source : Conv. 26/10 14 h 00, Mars : « rajouter 5 sous cases à cocher à titre informatif pour que le joueur les cochent […] si c'es sur plusiuers sessions différentes ».
- Statut : **ferme**. Cocher un succès coche-t-il « vaincre » ? T-16.

**EX-47 · Chaque validation en jeu se reporte sur le site.**
- Source : Règlement II : « A chaque fois que vous validez un succès/donjon, il faudra le valider sur le site pour actualiser votre progression et donc la progression de l'événement ».
- Statut : **ferme**.

**EX-48 · La coche met à jour immédiatement la progression personnelle et la jauge du groupe.**
- Source : Conv. 26/10 12 h 58, Mars : « ca augmentera ta prog à toi et donc la prog du groupe ». Règlement II (citation EX-47).
- Statut : **ferme**.

**EX-49 · Tableau de bord personnel.** Il montre le pourcentage d'avancement global et la progression, succès de donjon compris.
- Source : Conv. 26/10 10 h 50, Shadoaze : « dans ton dashboard tu voix exactement ta progression . par . de ton avancé globale » ; 11 h 05 : un onglet de succès « qui pourrait aussi etre rajouté dans la progression du dashboard ». CdC n° 2, 3.
- Statut : **ferme**.

**EX-50 · Pour chaque grimpeur : ce qu'il a fait et ce qui lui manque,** en quêtes, donjons et succès.
- Source : Conv. 26/10 13 h 02, Mars : « on aura pour chaque personne son niveau de prog de quetes s'il en a, de donjon, de succes etc, et lesquelles il lui manque ».
- Statut : **ferme**.

---

## 5. Guide Duffus

### 5.1 À garder

**EX-51 · Le guide, à l'identique.** Reprendre la partie guide de duffus.fr avec ses fonctions : tranches de niveau à gauche, sous-catégories (à peu près les zones), quêtes dans l'ordre optimisé (les quêtes qui demandent le même donjon sont regroupées), précision de « jusqu'où faire la quête », cases à cocher.
- Source : Conv. 26/10 10 h 41-10 h 44, Shadoaze (description) ; 10 h 47 : « le but serait de reprendre a l'identique sa partie guide parce qu 'elle est pixel mais en bloquant les étapes des étages qui sont pas encore dévoilées » ; 11 h 05 : « la partie guide à l'identique avec les features qu'on a évoqués ».
- Statut : **ferme**.

**EX-52 · La fiche de quête.** Un clic sur une quête affiche son guide : comment la réaliser, ce dont on a besoin, le succès lié, les prérequis.
- Source : Conv. 26/10 10 h 44, Shadoaze : « quand tu cliques sur une quete ça t'affiche un guide qui t'explique comment la réaliser , ce dont t'as besoin, le succes lié, les prérequis ».
- Statut : **ferme**.

**EX-53 · Archimonstres : suivi des archis et boss capturés** (sans la bourse aux échanges, EX-60).
- Source : Conv. 26/10 11 h 05 : « la partie archimonstres pour pouvoir track les archis et boss qu'on a capturés ».
- Statut : **ferme**. Suivi personnel ou collectif : T-25.

**EX-54 · Avis de recherche, à l'identique.**
- Source : Conv. 26/10 11 h 05 : « la section avis de recherche à l'identique ».
- Statut : **ferme**.

**EX-55 · Encyclopédie, à l'identique.**
- Source : Conv. 26/10 11 h 05 : « la partie encyclopédie à l'identique ».
- Statut : **ferme**. Conflit avec les étages cachés : T-08.

**EX-56 · Outils : tout, sauf les tutoriels.**
- Source : Conv. 26/10 11 h 05 : « dans outils tout garder en enlevant la partie sur les tutoriels ».
- Statut : **ferme** (le contenu exact de « Outils » reste à inventorier sur duffus.fr).

**EX-57 · Stuffs : tout.** Source : Conv. 26/10 11 h 05 : « stuffs tout garder ». Statut : **ferme**.

**EX-58 · Builder : tout.** Source : Conv. 26/10 11 h 05 : « builder tout garder ». Statut : **ferme**.

**EX-59 · Tableau de bord : tout.** Source : Conv. 26/10 11 h 05 : « dashboard tout garder ». Statut : **ferme**.

### 5.2 À retirer

**EX-60 · Retirer la bourse aux échanges** de la section archimonstres.
- Source : Conv. 26/10 11 h 05 : « retirer : la partie bourse aux échanges dans la section archimonstres ». CdC n° 2, 3, 4.
- Statut : **ferme**.

**EX-61 · Retirer l'habillage de Duffus.** En-têtes, logos, liens Twitch, Discord, liens de soutien et widgets de dons, lien direct vers son Discord.
- Source : Conv. 26/10 11 h 05 : « tout ce qui est lié à duffus : les entêtes, ses liens twitch, discord, les liens pour le soutenir / le lien direct vers le discord ». CdC n° 4 §4 « Nettoyage obligatoire ».
- Statut : **ferme**, avec l'exception EX-62.

### 5.3 À ajouter

**EX-62 · « Merci Duffus » en pied de page.** Condition de l'accord de l'auteur.
- Source : Info Marceau.
- Statut : **ferme**. Présence d'un lien vers duffus.fr : T-09.

**EX-63 · Verrouiller les étapes des étages non dévoilés.** Dans le guide, seules les tranches des étages ouverts sont accessibles ; on ne peut pas faire défiler ni voir la suite.
- Source : Conv. 26/10 10 h 10 : « en bloquant les étapes en fonction du taux de déblocage des étages » ; 10 h 47 (citation EX-51). CdC n° 3 et 4.
- Statut : **ferme**.

**EX-64 · Validation des succès de chaque boss, intégrée au tableau de bord.** Le guide Duffus n'a pas les succès de donjon : il faut les ajouter.
- Source : Conv. 26/10 10 h 52, Shadoaze : « pour les succes donjon ça n'y est pas mais on peut peut etre le rajouter si c'est faisable » ; 11 h 05 : « a rajouter : un onglet pour valider les succes que l'on a réaliser sur chacun des boss qui pourrait aussi etre rajouté dans la progression du dashboard ».
- Statut : **ferme**. Forme : onglet séparé ou lignes dans la liste de l'étage (EX-78) : T-17. Source des données : T-02.

**EX-65 · Distinguer quête principale et quête secondaire, quête par quête.** Code couleur, badge ou encadré net. Le marquage se fait au niveau de la quête, pas du bloc : un bloc qui contient une seule quête utile ne devient pas « principal » en entier.
- Source : Conv. 26/10 10 h 47 : « encadrés ou rajouter quelque chose qui préciserait sur les sous étapes lesquelles sont principales et lesquelles sont secondaires » ; 11 h 09, Shadoaze : « ( en mode y a une seule quete utile dans un bloc ça met tout le bloc en principal) » (crainte à éviter). CdC n° 2, 3, 4.
- Statut : **ferme**.

**EX-66 · Définition de « principale » et « secondaire ».** Principale = nécessaire pour obtenir un Dofus, y compris une quête qui ne donne pas de Dofus mais est le prérequis d'une quête qui en donne un. Secondaire = tout le reste (points de succès, XP, kamas, émotes, complétion).
- Source : Conv. 26/10 11 h 16-11 h 17, Shadoaze : « oui ça me va » (secondaire = pas nécessaire pour un Dofus) ; 11 h 18 : « y a des quetes qui ne permettent pas d'obtenir un dofus MAIS qui sont des prérequis pour d'autres quetes qui permettent de l'obtenir ». Règlement III.
- Statut : **ferme**.

**EX-67 · Classement déterministe, à partir des guides par Dofus de Duffus.** Pas de classement « deviné » par une IA.
- Source : Conv. 26/10 11 h 09, Shadoaze demande si l'IA peut le faire « sans que ça fasse de la merde » ; 11 h 10, Mars : « Si c'est du déterminisme c'est sûr que y'aura pas d'erreur » ; 11 h 11, Shadoaze : « c'est écris meme dans son site tu as des guides " à l'unité" pour chaque dofus avec les quetes et les prérequis ».
- Statut : **ferme**.

**EX-68 · Un seul guide pour tous, avec un filtre.** On garde toutes les quêtes et on filtre ; pas de deuxième guide.
- Source : Conv. 26/10 13 h 37, Shadoaze hésite : « est ce qu on fait 2 guides […] Ou est ce que juste on met en évidence les quêtes principales […] et on laisse un guide pour tout le monde ? » ; 13 h 41, Mars : « on met tout, et on met un filtre » ; 13 h 42, Shadoaze : « Du coup on peut enlever le concept de difficulté ». CdC n° 4 §2 « Onglet Unique par Étage ».
- Statut : **ferme**.

**EX-69 · Deux guides (Collectionneur et Éclaireur), choisis au départ.**
- Source : Conv. 26/10 11 h 05, 11 h 14-11 h 15, Shadoaze : « tu pick soit le guide collectionneur soit le guide éclaireur ». CdC n° 2 et 3 (« Double Guide Dynamique »).
- Statut : **abandonnée**. Remplacée par EX-68.

**EX-70 · Contenu intégré, sans renvoi vers duffus.fr.** Le contenu de l'étage est repris sur notre site, pas sous forme de lien vers la page Duffus (qui laisserait voir les tranches suivantes).
- Source : Conv. 26/10 10 h 16, Mars : « je peux lui dire de me créer une page sur mon site à moi qui reprend le contenu / Comme ça les gens seront pas tentés d'être curieux sur l'étape d'après » ; 10 h 27 : « Ça sera pas un link ou quoi juste le contenu du mec ».
- Statut : **ferme**. L'idée de lier l'étape Duffus correspondante (Mars, 10 h 15-10 h 16) est **abandonnée**.

**EX-71 · Récupération des données par nos soins.** L'auteur ne fournit pas d'export.
- Source : Info Marceau.
- Statut : **ferme**.

---

## 6. Jauge et tour

**EX-72 · Jauge collective visible de tous les participants.** Elle donne le « visuel global » de l'ascension : score de l'étage en cours et palier.
- Source : Conv. 26/10 10 h 15, Shadoaze : « les gens pourront s en servir d outil + de visuel global sur le concept ». Ancien règlement II : « un site annexe […] afin de suivre la progression globale ».
- Statut : **ferme**.

**EX-73 · La jauge signale quand l'étage devient éligible** (score ≥ palier), pour que l'admin puisse l'ouvrir.
- Source : CdC n° 4 §1 : « L'étage peut être validé si : Score Actuel ≥ Palier de validation ».
- Statut : **ferme**.

**EX-74 · Interface en pyramide symbolisant la tour.**
- Source : CdC n° 4 §2 : « L'interface globale du site doit être modélisée sous forme de pyramide symbolisant la tour ».
- Statut : **ferme**.

**EX-75 · Pas de règle anti-« bonus » pour l'instant.** Si l'équilibre se révèle mauvais (étages débloqués trop vite), une règle sera ajoutée plus tard.
- Source : Conv. 26/10 13 h 15, Mars : « si jamais on voit que y'a souvent des points bonus on pourra implémenter une règle à ce moment là / pas besoin de la coder de suite ».
- Statut : **ferme** (ne rien coder). Le contexte (Éclaireurs à +2) a disparu avec les difficultés, mais l'intention reste : ajuster plus tard si besoin (voir EX-109).

**EX-76 · Cadenas visuel et défilement interdit sur les étages supérieurs.**
- Source : CdC n° 2 et 3 : « Un cadenas visuel bloque l'interface ».
- Statut : **abandonnée**. Remplacée par EX-31 (CdC n° 4 : étages non générés).

---

## 7. Fiches et filtres

**EX-77 · La fiche de chaque grimpeur est consultable par tous les participants,** pour voir qui n'a pas fait quoi et trouver des partenaires.
- Source : Conv. 26/10 13 h 04, Shadoaze : « en allant consulter les fiches des autres tu peux voir qui a pas fait quoi ça peut permettre de t aider a trouver des gens qui ont pas fait la même chose que toi ».
- Statut : **ferme**.

**EX-78 · Filtrer par quête, donjon ou succès de l'étage pour voir qui ne l'a pas fait.**
- Source : Conv. 26/10 13 h 04, Mars : « par personne, et par donjons/succes/quetes de l'étage […] je peux aussi filtrer par la quete/succes qui m'intéresse / et ca me dit qui les a pas fait non plus / et je te mp ».
- Statut : **ferme**.

**EX-79 · Une liste unique par étage, la même pour tous.**
- Source : CdC n° 4 §2 : « Pour l'étage actif ouvert, tout le monde consulte la même interface et la même liste unifiée ».
- Statut : **ferme**.

**EX-80 · Filtre cumulatif par cases sur les 4 catégories.** Le grimpeur affiche le mélange qu'il veut : quêtes principales, quêtes secondaires, donjons, full succès, ou tout.
- Source : CdC n° 4 §2 « Filtre Classique Cumulatif ». Conv. 26/10 13 h 41 (citation EX-68).
- Statut : **ferme**.

**EX-81 · Un badge ou une couleur par catégorie de ligne** (quête principale, quête secondaire, donjon normal, full succès).
- Source : CdC n° 4 §2 « Mise en valeur visuelle ».
- Statut : **ferme**.

---

## 8. Admin

**EX-82 · Bouton d'ouverture d'étage.** Actif seulement si la jauge atteint le palier et, pour l'étage 1, après le 13/11/2026 à 17 h.
- Source : Conv. 25/10 17 h 56, réponses 5 et 13. CdC n° 2 : « Un administrateur devra presser un bouton manuellement après vérification des scores ». CdC n° 4 §1 et §4.
- Statut : **ferme**.

**EX-83 · L'admin peut vérifier le détail avant d'ouvrir.** Il voit qui a gagné quels points, pour faire sa « dernière vérification manuelle ».
- Source : Conv. 25/10 17 h 56, réponse 13 (citation EX-27). CdC n° 2 : « après vérification des scores ».
- Statut : **ferme** (le contenu exact de la vue est une *interprétation*).

**EX-84 · Gestion des grimpeurs par un admin.** Ajouter un inscrit, mettre en pause, réintégrer, intégrer un retardataire, exclure.
- Source : EX-39 à EX-43. Info Marceau.
- Statut : **ferme**.

**EX-85 · Annuler la coche d'un grimpeur.** Un admin peut retirer une validation contraire aux règles.
- Source : Conv. 25/10 21 h 18, Mars, question 7 : « un admin pourra toujours annuler » ; 21 h 22 : « oui ». CdC n° 2 : « les admins peuvent révoquer ». Le CdC n° 4 n'en parle plus.
- Statut : **à confirmer** (accordé sous l'ancien modèle, non repris dans le CdC n° 4 ; voir T-15).

**EX-86 · Validations admin et refus non affichés.** Les admins validaient chaque preuve ; un refus n'était pas affiché publiquement.
- Source : Conv. 25/10 17 h 24, Mars, question 12 ; 17 h 56 : « oui si la validation est refusée juste ça refuse ».
- Statut : **abandonnée** (plus de validation par admin, EX-88). L'esprit (« garder l'ambiance chill ») peut s'appliquer à EX-85 *(interprétation)*.

**EX-87 · Admins qui valident avec le bot.**
- Source : Conv. 25/10 17 h 24, Mars, question 6 : « C'est eux qui pourront valider avec le bot ».
- Statut : **abandonnée** (EX-88).

---

## 9. Bot et preuves

**EX-88 · Zéro screen : la case cochée est la preuve.** Aucune capture n'est demandée, ni pour les quêtes ni pour les donjons.
- Source : Conv. 26/10 13 h 01, Mars : « si la seule manière de valider c'est le screen et que tu oublie c'est chiant » ; 13 h 02, Shadoaze : « En vrai on peut trust » ; Mars : « vasy je chafnge ca dans les preuves ». CdC n° 4 §3 : « Système de Preuves (Zéro Screen) : Aucun screen n'est demandé ». Règlement II : « aucune vérification ne sera demandé ».
- Statut : **ferme**.

**EX-89 · Screen obligatoire du récapitulatif de combat pour les donjons.**
- Source : Conv. 25/10 22 h 25, Shadoaze : « je pensais a un screen du récap post combat » ; 26/10 12 h 56 : « pour les donjons je trouve ça stylé la validation par screen ». CdC n° 2 et 3.
- Statut : **abandonnée** (26/10 13 h 02). Remplacée par EX-88.

**EX-90 · Screen dans #screen-validation, validé par les admins.**
- Source : Ancien règlement II.
- Statut : **abandonnée**. Remplacée par EX-88 et EX-47.

**EX-91 · Quêtes sur parole, screen facultatif.**
- Source : Conv. 25/10 17 h 46 (« on se basera sur les paroles des gens ») ; 21 h 18, question 7 : « Il pourra en joindre un s'il veut » ; 21 h 22 : « oui ».
- Statut : **abandonnée** comme mécanisme : la parole devient la case cochée (EX-44, EX-88). Le screen facultatif n'est pas repris dans le CdC n° 4.

**EX-92 · Bot de validation avec IA lisant les screens.** Commandes `/grimpeur`, `/valider`, `/refuser`, `/niveau`, IA qui pré-remplit, message de transparence sur l'IA.
- Source : CdC n° 1 §A, §A.6, §C.3. Conv. 25/10 21 h 35 (`/niveau`).
- Statut : **abandonnée** (EX-88). Rôle restant du bot : T-14.

**EX-93 · Bot d'atelier dans un salon caché.** Un bot dans un salon visible seulement de Marceau et Shadoaze, qui lit les salons du Discord et dialogue avec l'IA de Marceau ; les échanges de travail s'y font ensuite.
- Source : Conv. 26/10 10 h 27, Mars : « Le bot aura accès aux contenus des Channel du discord et il parlera avec mon IA » ; 10 h 38, Shadoaze : « Vas y ça marche ».
- Statut : **ferme** (outil interne, pas une fonction pour les joueurs ; il semble en place : les exports de `docs/discord/` sont « lus par le bot le 27/10 »).

**EX-94 · Rôle du bot auprès des joueurs.** Les CdC n° 2 à 4 annoncent toujours « un bot Discord de validation », mais plus aucune fonction ne lui est attribuée.
- Source : CdC n° 4, en-tête : « un bot Discord de validation ».
- Statut : **à confirmer** (T-14).

---

## 10. Teaser, reveal et trailer

**EX-95 · Le projet reste secret jusqu'à un reveal.**
- Source : Conv. 26/10 19 h 01, Mars : « si t'es chaud on peut garder ca secret et on fera une présentation stylée […] un reveal cool » ; Shadoaze : « Chaud ! » ; 20 h 16, Mars : « D'ici là motus ».
- Statut : **ferme**.

**EX-96 · Page d'accueil en compte à rebours, rien d'autre.** Le site est donné aux joueurs vers le 6/11 (date souple), mais seule une grande page d'accueil soignée avec un décompte est visible.
- Source : Conv. 27/10 13 h 47, Mars : « Le site sera donné le 6 ou X on s'en fou mais que la page d'accueil pimpé en mode compte à rebours et tout » ; 13 h 48 : « Rien du site sera visible juste une énorme page d'accueil avec un décompte » ; 13 h 49, Shadoaze : « Stylé de fou ça ».
- Statut : **ferme**. Date de mise en ligne et échéance du décompte : T-06.

**EX-97 · Annoncer qu'on prépare quelque chose, sans dévoiler.**
- Source : Conv. 26/10 11 h 03, Mars : « on devrait annoncer qu'on prépare un truc propre, surprise on dit pas ». Fait par Shadoaze dans #général le 26/10 13 h 59 : « on est en train de cook une master class vous allez être choqués ».
- Statut : **ferme** (déjà fait).

**EX-98 · Trailer teaser posté le 6/11.** Une vidéo pour faire monter la hype, à une semaine de l'événement.
- Source : Conv. 27/10 12 h 53, Shadoaze : « un trailer pour tease qu on poste le 6, a une semaine de l évent ». 12 h 58, Mars : « Je focus sur le site avant et on voit ça après ». 13 h 12, Shadoaze : les IA vidéo gratuites « génère des du truc de 5s max ».
- Statut : **à confirmer** (moyen de production non trouvé, priorité au site). Voir aussi la section « Idées hors périmètre ».

**EX-99 · Trailer de présentation du projet, des règles et du site.**
- Source : Conv. 27/10 12 h 53, Shadoaze : « rien qu'un trailer qui présente le projet et les règles avec le site ce serait un banger ».
- Statut : **à confirmer** (même raison qu'EX-98).

**EX-100 · Présentation par un appel avec tout le monde.**
- Source : Conv. 27/10 12 h 56, Mars : « Quand je disais présentation c'était un truc comme ça pas genre un call avec tout le monde ».
- Statut : **abandonnée** (clarification : le reveal est une vidéo ou une page, pas un appel).

---

## 11. Design

**EX-101 · Partir de l'esprit des maquettes de Marceau.** Shadoaze les a accueillies avec enthousiasme et veut que ses notes soient mises « en beau » de la même façon.
- Source : Conv. 25/10 16 h 57, Mars : « je me sis amusé à faire quelques maquettes » ; 17 h 06, Shadoaze : « justement que je te donne ce que j'ai fait pour le faire en beau comme t as fait » et « omega master class ».
- Statut : **ferme** (direction générale ; les maquettes envoyées sont des images, non archivées dans `docs/`).

**EX-102 · Le guide garde l'ergonomie de Duffus.**
- Source : Conv. 26/10 10 h 47 (« a l'identique sa partie guide parce qu 'elle est pixel ») ; 10 h 18 : « son travail est de loin le plus complet, le plus opti et le plus ergonomique ». CdC n° 3 §3 : « Le site doit cloner l'ergonomie de duffus.fr ».
- Statut : **ferme**. Articulation avec la pyramide et l'identité du site : T-10.

**EX-103 · Utiliser le lore de la tour** (texte de #présentation : la tour des Dieux, Goultard, « Oserez-vous franchir le seuil ? ») dans le site et le teaser.
- Source : #présentation (25/10 10 h 48). Conv. 25/10 15 h 21 : Shadoaze veut « paufinner le truc ».
- Statut : **à confirmer** *(interprétation : rien ne le demande explicitement, mais la pyramide et le « brouillard » vont dans ce sens ; Mars : « je trouve que ça colle bien au lore », 25/10 17 h 24)*.

**EX-104 · Images d'étage de Shadoaze.** Shadoaze a généré des images pour chaque étage.
- Source : Conv. 27/10 12 h 56, Mars : « Les images toi de chaque étages tu les as généré avec quoi? » ; 12 h 57, Shadoaze : « Tout les ia disponibles gratuites ».
- Statut : **à confirmer** (leur usage sur le site n'a pas été discuté ; T-28).

---

## 12. Hébergement, accès restreint et budget

**EX-105 · Hébergement payant d'environ 3 à 4 € par mois.**
- Source : Conv. 26/10 10 h 09, Mars : « Je vais payer un truc 3-4 balles par mois c'est ok c'est prévu ».
- Statut : **ferme**.

**EX-106 · Tout le contenu repris de Duffus est derrière la connexion.** La restriction d'accès répond à la question des droits d'auteur.
- Source : Conv. 26/10 10 h 09, Shadoaze : « je demande ça par rapport aux" droits d auteur" […] si seul ceux qui ont accès au site sont ici on peut plagier des contenus déjà existant ». EX-36.
- Statut : **ferme** *(interprétation pour la page teaser : elle reste publique pour les invités du lien, mais ne montre aucun contenu Duffus, EX-96)*.

**EX-107 · Projet non lucratif.**
- Source : Conv. 26/10 10 h 20, Mars : « on va rien vendre c'est un projet entre 10 potes ». Info Marceau (accord de Duffus pour un projet non lucratif).
- Statut : **ferme** (aucune publicité, aucun paiement, aucun don *(interprétation)*).

**EX-108 · Site hébergé en local.**
- Source : Conv. 26/10 10 h 09, Shadoaze : « le site sera hebergé en.local avec accès limité » (question).
- Statut : **abandonnée**. Remplacée par EX-105 et EX-36 (hébergement en ligne à accès restreint).

---

## 13. Non-fonctionnel

**EX-109 · Règles faciles à ajuster.** Le multiplicateur du palier, les catégories et les dates doivent pouvoir changer sans réécrire le site : les règles « seront actualisés au fur et à mesure ».
- Source : #général 26/10 13 h 59, Shadoaze : « les règles seront actualisés au fur et a mesure par rapport aux retours » ; Règlement IV : « potentiellement adapter les règles » ; Conv. 25/10 19 h 52, Mars : « Ya vraiment rien qui est figé dans le marbre ».
- Statut : **ferme** (le paramétrage précis est une *interprétation*).

**EX-110 · Prêt et testé avant le 13/11 à 17 h.** Des tests sont nécessaires avant l'ouverture aux joueurs.
- Source : Conv. 27/10 13 h 09, Mars (citation EX-30) ; 13 h 12, Shadoaze : « puis faudra qu on fasse les tests dessus avant aussi ».
- Statut : **ferme**. Qui teste et quand : T-05.

**EX-111 · Aucun contenu d'un étage scellé n'arrive au navigateur.** L'accès doit être « techniquement impossible », pas seulement caché à l'écran.
- Source : CdC n° 4 §2 (citation EX-31).
- Statut : **ferme**.

**EX-112 · Le manuel plutôt que l'automatique compliqué.** Quand une règle est délicate (rattrapage, signe de vie, ouverture), un admin décide ; le site l'aide sans décider à sa place.
- Source : Conv. 25/10 21 h 41, Shadoaze : « Ne pas s'embeter avec ça » ; 17 h 56, réponses 11 et 13.
- Statut : **ferme**.

**EX-113 · Données Duffus récupérées une fois et conservées chez nous.** On ne dépend pas de duffus.fr pendant la navigation des joueurs. *(interprétation : découle d'EX-71 et du respect du site de l'auteur.)*
- Source : Info Marceau (« on récupère les données nous-mêmes »). DV4 §10 (« import ponctuel et poli […] mis en cache »).
- Statut : **à confirmer** (fréquence de mise à jour : T-26).

**EX-114 · Petite échelle, en français.** Une dizaine de grimpeurs (liste officielle : 10 ; exemples à 12), tous francophones.
- Source : #liste-grimpeurs ; Conv. 25/10 17 h 33 (« Imaginons que l'on soit 12 ») ; 26/10 10 h 20 (« 10 potes »).
- Statut : **ferme** (hypothèse de dimensionnement).

**EX-115 · Utilisable sur téléphone.** *(interprétation : Marceau et Shadoaze échangent souvent depuis leur téléphone, et une capture de Shadoaze vient d'un navigateur mobile, 26/10 14 h 01 ; rien n'est demandé explicitement.)*
- Source : Conv. 25/10 22 h 17, Mars : « Je suis sur le tel uniquement là ».
- Statut : **à confirmer**.

---

## Récapitulatif des statuts

| Statut | Nombre | Exigences |
|---|---|---|
| **ferme** | 86 | toutes les autres |
| **à confirmer** | 10 | EX-26, EX-38, EX-85, EX-94, EX-98, EX-99, EX-103, EX-104, EX-113, EX-115 |
| **abandonnée** | 19 | EX-17 à EX-22, EX-33, EX-34, EX-42, EX-69, EX-76, EX-86, EX-87, EX-89 à EX-92, EX-100, EX-108 |

Plusieurs exigences fermes ont un détail encore ouvert, renvoyé vers un point T-nn.

---

## Contradictions et trous

Chaque point indique les sources en conflit, puis une **réponse par défaut** à appliquer tant que Shadoaze n'a pas tranché.

**T-01 · Point par action (CdC n° 4) ou point par catégorie complète (règlement) ?**
Le CdC n° 4 validé dit « 1 quête cochée = +1 point au score actuel global » et accorde le point « donjon » dès qu'on coche « Finir le donjon classique », donjon par donjon. Le règlement III et Shadoaze (26/10 13 h 52, avant le CdC n° 4) parlent de **tous** les donjons et **toutes** les quêtes d'un étage, pour 4 points maximum par joueur. Shadoaze a validé le CdC n° 4 sans relever l'écart (il n'a vérifié que la notion d'étage en cours, 14 h 11-14 h 15).
**Par défaut** : point par catégorie complète (EX-02 à EX-06). C'est le seul comptage compatible avec « 4 points max » et « 2 × actifs ». Demander une confirmation écrite.

**T-02 · D'où viennent les succès des donjons ?**
Marceau pose duffus.fr comme source unique, y compris pour les succès (CdC n° 4 §3, Info Marceau). Mais Shadoaze dit que le guide Duffus ne contient pas les succès de donjon (26/10 10 h 52) et suggère de les récupérer sur « un site genre Dofus pour les noobs » (14 h 01).
**Par défaut** : les prendre dans l'encyclopédie de duffus.fr si elle les contient ; sinon, compléter depuis une source ouverte (DofusDB), en le signalant à Marceau et en le notant dans le contenu de l'étage. Décision de Marceau requise, car elle touche la règle « source unique ».

**T-03 · Quels donjons appartiennent à un étage ?**
Le guide Duffus est organisé en quêtes ; rien ne dit comment on obtient la liste des donjons d'une tranche (donjons cités par les quêtes ? donjons dont le niveau tombe dans la tranche ?). Les salons d'étage de Shadoaze listaient des donjons, mais ne sont plus une source. EX-12 (premier point facile) dépend de ce choix : un étage à 6 ou 7 donjons (13 h 52) rend le point « donjons » moins facile.
**Par défaut** : les donjons dont le niveau est dans la tranche de l'étage, d'après duffus.fr, et une liste relue et validée par Shadoaze avant chaque ouverture.

**T-04 · Correspondance étage ↔ tranche, et cap de chaque étage.**
Seul repère : 40-50 = étage 3 (26/10 10 h 42). Shadoaze précise que les sous-catégories ne sont « pas exactement » des zones, et répond « Oui et non » quand Marceau demande si les étages suivent les étapes du site (25/10 21 h 51). L'ancien règlement donne 20 comme cap de l'étage 0. Rien ne dit si toutes les tranches font 10 niveaux.
**Par défaut** : étage 0 = première tranche Duffus (jusqu'au niveau 20), puis une tranche par étage ; le cap d'un étage = la borne haute de sa tranche. Table complète à faire valider par Shadoaze.

**T-05 · Bêta-test pendant les deux semaines, ou secret jusqu'au reveal ?**
Le règlement IV et Shadoaze (25/10 22 h 28 : « cette phase 1 de 2 semaines un peu longue pour "beta test" ») prévoient que les joueurs bêta-testent « ce que l'on va mettre en place » pendant l'accès anticipé. Depuis le 26/10 19 h 01, le site est secret jusqu'au reveal (EX-95, EX-96). Shadoaze demande aussi des tests avant l'ouverture (27/10 13 h 12).
**Par défaut** : bêta fermée (Marceau, Shadoaze et un ou deux joueurs de confiance) avant le reveal ; pas de bêta publique.

**T-06 · Quand la page à compte à rebours sort-elle, et vers quoi compte-t-elle ?**
Shadoaze propose de poster le teaser « le 6 » (27/10 12 h 53) ; Marceau dit « le 6 ou X on s'en fou » (13 h 47). L'échéance du décompte n'est pas dite.
**Par défaut** : page en ligne au plus tard le vendredi 6/11, décompte jusqu'au vendredi 13/11 à 17 h.

**T-07 · L'étage 0 et sa jauge pendant que le site est caché.**
L'étage 0 a un palier (EX-32) et l'étage 1 ne s'ouvre que si ce palier est atteint. Mais si le site complet n'ouvre qu'à la fin du décompte (13/11), personne n'a pu cocher sa progression de l'étage 0 (30/10-13/11) : la jauge de l'étage 0 serait vide au moment où l'étage 1 devient possible.
**Par défaut** : à l'ouverture du site, chacun coche rétroactivement ce qu'il a fait à l'étage 0 (système de confiance) ; l'admin ouvre l'étage 1 dès que le palier est atteint. Alternative à proposer à Shadoaze : ouvrir le site complet quelques jours avant le 13/11.

**T-08 · Encyclopédie, stuffs, builder « à l'identique » contre étages cachés.**
Ces outils montrent tout le jeu, y compris le contenu des étages futurs (donjons, quêtes, objets de haut niveau). Shadoaze veut cacher les étages « afin de maintenir la surprise » (EX-31) mais garder ces outils à l'identique (EX-55 à EX-58).
**Par défaut** : seuls le guide, la liste d'étage et la pyramide sont verrouillés ; l'encyclopédie et les outils restent complets (ce sont des données du jeu, déjà visibles en jeu). À confirmer.

**T-09 · « Retirer tout ce qui est lié à Duffus » contre « Merci Duffus ».**
Shadoaze demandait de retirer toute trace de Duffus (26/10 11 h 05). L'accord de l'auteur impose « Merci Duffus » en pied de page (Info Marceau). DV4 §10 ajoute un lien vers duffus.fr, qui n'est pas dans la condition rapportée par Marceau, et un lien direct permettrait de voir les tranches suivantes (EX-70).
**Par défaut** : « Merci Duffus » dans le pied de page de chaque page, avec un lien vers la page d'accueil de duffus.fr seulement si l'auteur le souhaite ; aucun lien par quête ou par étape.

**T-10 · Ergonomie Duffus « à l'identique » contre pyramide et identité propre.**
Le CdC n° 4 veut une interface en pyramide ; Shadoaze veut le guide « a l'identique » ; Marceau propose « Autant faire tout nous même mais avec le contenu des étages de ton site » (26/10 10 h 12).
**Par défaut** : la pyramide sert de navigation entre étages ; à l'intérieur d'un étage, la liste et les fiches de quête reprennent l'organisation de Duffus (sous-catégories, ordre, fiches), avec le style visuel du site.

**T-11 · Catégorie vide dans un étage.**
Shadoaze dit que chaque étage a des donjons et des quêtes (EX-25), pas forcément des quêtes principales (une tranche peut n'avoir aucune quête liée à un Dofus). Avec 3 catégories possibles, 2 × N devient plus dur à atteindre.
**Par défaut** : une catégorie vide ne rapporte pas de point et le palier devient ⌈ N × K ÷ 2 ⌉, K étant le nombre de catégories non vides (égal à 2 × N quand K = 4). C'est le choix déjà fait dans `SPEC.md` §5.3. À confirmer.

**T-12 · Où placer une quête principale ?**
Shadoaze avait placé les quêtes de Dofus « aux bons étages », par exemple à l'étage où il faut faire le donjon demandé (25/10 22 h 20). Le guide Duffus peut les placer dans une autre tranche.
**Par défaut** : la tranche de Duffus fait foi (Info Marceau) ; signaler les écarts à Shadoaze lors de la préparation de l'étage.

**T-13 · Le retardataire ou le grimpeur en pause peut-il cocher ?**
Il est hors calcul (EX-39, EX-40), mais rien ne dit s'il peut tenir sa progression à jour.
**Par défaut** : oui, ses coches sont enregistrées et visibles sur sa fiche ; elles ne comptent qu'à partir de sa (ré)intégration.

**T-14 · Que fait encore le bot ?**
Les CdC parlent d'un « bot Discord de validation », mais la validation n'existe plus (EX-88). Seul le bot d'atelier (EX-93) a une mission claire.
**Par défaut** : aucun bot côté joueurs pour le lancement. Option à proposer : un message automatique dans le salon d'annonces quand un étage s'ouvre.

**T-15 · Un admin peut-il retirer une coche ?**
Accordé sous l'ancien modèle (EX-85), absent du CdC n° 4, alors que le règlement prévoit l'exclusion pour triche.
**Par défaut** : oui, avec un motif, journalisé, jamais affiché publiquement (dans l'esprit de la réponse 12 du 25/10).

**T-16 · Cocher un succès coche-t-il « vaincre » ?**
Le full succès implique le donjon vaincu (EX-08), mais rien n'est dit pour un succès isolé.
**Par défaut** : oui, cocher n'importe lequel des 4 succès coche aussi « vaincre » (on ne peut pas réussir un succès de boss sans le battre) ; décocher « vaincre » décoche les 4 succès.

**T-17 · Succès de donjon : onglet séparé ou dans la liste de l'étage ?**
Shadoaze demande « un onglet pour valider les succes » (26/10 11 h 05) ; le CdC n° 4 les met dans la liste unique de l'étage, sous chaque donjon.
**Par défaut** : dans la liste de l'étage (CdC n° 4, plus récent), plus une vue récapitulative des succès dans le tableau de bord.

**T-18 · Que devient la jauge d'un étage une fois ouvert le suivant ?**
Rien n'est dit. Les points ne comptent que pour l'étage en cours (EX-11).
**Par défaut** : la jauge de l'étage terminé est figée à l'ouverture du suivant et reste consultable comme historique ; les coches faites ensuite sur cet étage comptent pour la progression personnelle, pas pour la jauge.

**T-19 · Comment se connecter, et qui crée les comptes ?**
Marceau parle de « mdp login » (26/10 12 h 44). `SPEC.md` v4 a choisi la connexion par Discord et l'inscription libre pour les membres de la liste officielle. Personne n'a tranché avec Shadoaze.
**Par défaut** : connexion par Discord, réservée aux membres de la liste officielle (#liste-grimpeurs), car elle évite de gérer des mots de passe ; c'est un choix technique qui ne change rien pour Shadoaze.

**T-20 · Champs de la fiche et liste des admins.**
Règlement : pseudo en jeu. #choix-classe : classe informative. Aucune mention du pseudo Discord, ni de la liste des admins du site (seul le rôle « Administrateur » est connu).
**Par défaut** : pseudo en jeu, classe (facultative, modifiable), pseudo Discord (pour se contacter, EX-78) ; admins = membres du rôle « Administrateur » (aujourd'hui Shadoaze et Marceau).

**T-21 · Le palier de 2 × N n'est pas écrit dans le règlement.**
Le règlement dit seulement que les points nécessaires « dépendent du nombre de grimpeurs actifs ».
**Par défaut** : appliquer 2 × N et le montrer sur le site à côté de la jauge ; suggérer à Shadoaze de l'écrire dans #concept-et-règles.

**T-22 · Points bonus des événements spéciaux.**
Le règlement III les annonce ; aucun mécanisme n'est décrit (qui les donne, combien, s'ils comptent dans la jauge de l'étage en cours).
**Par défaut** : rien à coder pour le lancement ; prévoir plus tard un ajout manuel de points par un admin, avec un motif, dans la jauge de l'étage en cours. `SPEC.md` v4 l'a déjà prévu : à confirmer avec Shadoaze avant de le construire.

**T-23 · Date du lancement : 13/11 ou 15/11 ?**
L'ancien règlement et le CdC n° 1 disent 15/11 ; Shadoaze, le règlement officiel et le CdC n° 4 disent 13/11 à 17 h. Certaines notes de projet parlent encore du 15/11.
**Par défaut** : 13/11/2026 à 17 h (heure de Paris).

**T-24 · Le « oui » puis le « non » sur le rattrapage.**
Shadoaze a répondu « exact » (25/10 21 h 05) au message où Marceau définissait le rattrapage par le cap de l'étage en cours, puis « non » à la même question à 21 h 22.
**Par défaut** : sans objet, tranché par la gestion manuelle (EX-41).

**T-25 · Archimonstres : suivi personnel ou collectif ?**
« les archis et boss qu'on a capturés » (26/10 11 h 05) peut se lire des deux façons.
**Par défaut** : suivi personnel (comme sur duffus.fr), consultable sur la fiche de chacun.

**T-26 · Mise à jour du contenu Duffus.**
Le guide de Duffus peut évoluer (patchs du jeu). Rien n'est dit sur la fréquence de reprise.
**Par défaut** : import de chaque étage lors de sa préparation, relu par un admin, puis figé ; nouvel import seulement à la main.

**T-27 · Outils et tutoriels de Duffus : inventaire inconnu.**
« Outils : tout sauf les tutoriels », « stuffs », « builder » : personne n'a listé ce que contiennent ces sections.
**Par défaut** : inventaire de duffus.fr par l'équipe, soumis à Shadoaze avant de construire ces modules (ils ne sont pas nécessaires au 13/11).

**T-28 · Noms et images des étages.**
« Le Seuil » vient des maquettes de Marceau (CdC n° 1 §A.2). Shadoaze a des images d'étage (EX-104) et des salons nommés par étage.
**Par défaut** : « Étage N » et la tranche de niveau ; nom et image fournis par Shadoaze s'il le souhaite.

**T-29 · Aider l'admin à juger le « signe de vie ».**
Le critère est laissé aux admins (EX-43), sans outil.
**Par défaut** : la vue admin montre la date de dernière coche de chaque grimpeur, sans alerte ni notification.

**T-30 · Ressources de Shadoaze pas encore transmises.**
Shadoaze a « des trucs de fait en caché » (25/10 17 h 03) et veut montrer « les ressources que je compte utiliser » lors d'un appel (21 h 05), prévu le samedi 31/10 (22 h 29-22 h 31).
**Par défaut** : ne rien bloquer en attendant ; préparer pour l'appel la liste des T-nn ouverts.

**T-31 · Contradiction interne de DV4.**
DV4 §3 présente les salons d'étage comme contenant « les donjons et les quêtes principales recommandées » ; DV4 §11 dit qu'ils ne sont pas une source.
**Par défaut** : §11 l'emporte (Info Marceau).

**T-32 · Écarts entre `SPEC.md` v4 et ces exigences** (pour mise à jour de la spec).
- « Chaque quête renvoie vers sa fiche Duffus » contredit EX-70 (Conv. 26/10 10 h 27 : « Ça sera pas un link »).
- « Pied de page avec un lien vers https://duffus.fr » : voir T-09.
- « Inscription libre si sur la liste officielle » et « connexion avec Discord » : voir T-19.
- Points bonus déjà au périmètre : voir T-22.

---

## Écarts avec DECISIONS-V4

### Oublis

1. **Les dates comme contraintes du système** : étage 0 le 30/10 à 17 h, et surtout le **verrou de l'étage 1 avant le 13/11 à 17 h** même si le palier est atteint (EX-28, EX-29). DV4 §8 ne parle que de « vrai départ vers le 13/11 ».
2. **L'interface du CdC n° 4** : pyramide, liste unique par étage, filtre cumulatif sur les **4** catégories, badge distinct pour chacune (EX-74, EX-79 à EX-81). DV4 §4 ne mentionne qu'un filtre principal / secondaire.
3. **Le marquage quête par quête, pas bloc par bloc** (EX-65, crainte explicite de Shadoaze à 11 h 09).
4. **Le guide Duffus n'a pas les succès de donjon** (Shadoaze, 10 h 52) et Shadoaze proposait une autre source (14 h 01). DV4 §11 affirme que les succès détaillés viennent de Duffus (T-02). La question « quels donjons pour un étage ? » n'est pas posée (T-03).
5. **Les règles de jeu toujours en vigueur** : cap de niveau et tolérance, jouer sous le cap autorisé, donjons entre grimpeurs, PL interdit, joueur hors événement, exclusion, 3 semaines sans signe de vie (EX-13 à EX-16, EX-43).
6. **Le retardataire ne compte pas du tout avant son intégration** : ni ses points, ni le palier (EX-40, réponse « non » de 21 h 22). DV4 §6 dit seulement « réintégration manuelle ».
7. **Full succès ⇒ donjon vaincu** (EX-08).
8. **Les fonctions du guide à reprendre** : ordre optimisé, regroupements, « jusqu'où faire la quête », fiche de quête au clic (EX-51, EX-52), et le principe « contenu intégré, pas de lien » (EX-70).
9. **Le rôle « Administrateur »**, la motivation « droits d'auteur » de l'accès restreint, le budget de 3 à 4 € par mois (EX-37, EX-105, EX-106).
10. **Le bêta-test prévu pendant les deux semaines** et la demande de tests avant ouverture (T-05, EX-110), et le problème de la jauge de l'étage 0 si le site reste caché (T-07).
11. **Les points bonus des événements spéciaux** du règlement III (T-22).
12. **Le conflit entre les outils « à l'identique » et les étages cachés** (T-08).
13. **L'écart du CdC n° 4 sur le comptage** (point par action) : DV4 donne la bonne règle mais ne signale pas que le texte validé dit autre chose (T-01).

### Déformations et sur-interprétations

1. **DV4 §5 : le screen « reste une option »**. Les sources disent le contraire : Marceau change les preuves (13 h 02), le CdC n° 4 dit « Zéro Screen. Aucun screen n'est demandé », le règlement « aucune vérification ». L'auto-validation par screen n'est qu'une idée (section suivante).
2. **DV4 §8 : « Un trailer est en option (diaporama animé et voix off) »**. Le format « diaporama animé et voix off » n'apparaît dans aucune source. Shadoaze parle d'un trailer de présentation ou d'un teaser posté le 6 (EX-98, EX-99) ; Marceau a dit qu'il verrait après le site.
3. **DV4 §8 : « Idée retenue : vers le 6/11 »**. Le 6/11 est la date proposée par Shadoaze pour le **trailer** ; pour le site, Marceau dit « le 6 ou X on s'en fou » (T-06).
4. **DV4 §8 : « Le site n'est pas attendu à cette date »**. Vrai pour le site complet, mais l'accès anticipé devait aussi servir de bêta-test (T-05).
5. **DV4 §3 : « L'étage N correspond à la tranche N du guide »** (aussi en §11). Le seul repère est 40-50 = étage 3, et Shadoaze nuance (« Oui et non », « pas exactement ») (T-04).
6. **DV4 §10 : lien vers duffus.fr dans le pied de page** et **« export fourni par l'auteur si possible »**. Marceau a seulement rapporté « Merci Duffus » ; l'export n'existe pas (T-09, EX-71). Le §9 (« sans accord, DofusDB… ») est devenu caduc.
7. **DV4 §2 : « Si les points bonus faussent l'équilibre, une règle sera ajoutée plus tard »**. La phrase de Marceau (13 h 15) visait les Éclaireurs qui gagnaient +2 dans l'ancien modèle ; dans le nouveau, il n'y a plus de « bonus » au sens de sur-performance. L'intention de pouvoir ajuster reste valable (EX-75).
8. **DV4 §2 : « Ces cases sont informatives »**. Seules les 4 cases de succès isolées le sont ; la case « vaincre » donne le point donjons (avec les autres donjons) et l'ensemble des 5 cases donne le point full succès (EX-46).
9. **DV4 §7 : « sous réserve, voir §9 »**. La réserve est levée par l'accord de l'auteur.

---

## Idées évoquées hors périmètre

À garder en mémoire, sans rien construire pour le lancement.

| Idée | Source | Où en est-elle |
|---|---|---|
| **Trailer** de présentation (projet, règles, site) | Conv. 27/10 12 h 53, Shadoaze | Pas de moyen de production trouvé (IA vidéo limitées à 5 s, 13 h 12) ; Marceau verra après le site (EX-99). |
| **Trailer teaser** posté le 6/11 | Conv. 27/10 12 h 53, Shadoaze | Idem (EX-98). |
| **Affiches** générées par IA | Conv. 27/10 12 h 58, Mars : « J'ai de quoi générer des images cool aussi en mode affiche » | Non discuté plus avant. |
| **Points bonus d'événements spéciaux** | Règlement III : « Des événements spéciaux et exceptionnels pourront être organisés afin de gagner des points bonus » | Mécanisme à définir (T-22). |
| **Promotion d'une catégorie** à la catégorie supérieure si un joueur en fait souvent plus | Conv. 26/10 13 h 07-13 h 12, Mars ; Shadoaze explique que les quêtes s'enchaînent, donc qu'un Aventurier devient rarement Collectionneur | Sans objet depuis la fin des difficultés. |
| **Collectionneur qui rapporte plus** que 3 points | Conv. 26/10 13 h 07, Shadoaze : « on peut même peut être lui faire rapporter plus » | Sans objet. |
| **Un point par succès**, pondéré selon la difficulté du succès | Conv. 26/10 13 h 48, Mars | Refusé par Shadoaze (13 h 52). |
| **« 75 % des joueurs ont fini l'étage »** comme condition | Conv. 26/10 13 h 16, Mars | Remplacé par 2 × N. |
| **Règle anti-déblocage trop rapide** | Conv. 26/10 13 h 15, Mars | « pas besoin de la coder de suite » (EX-75). |
| **Auto-validation par screen** envoyé au bot ou au site | Conv. 26/10 12 h 58, Shadoaze : « si le fait d envoyer le screen a un bot ou sur le site auto validé ta progression […] c est stylé » | Écarté au profit des cases (13 h 02) ; possible confort futur, jamais obligatoire. |
| **Récupérer les succès sur « Dofus pour les noobs »** | Conv. 26/10 14 h 01, Shadoaze | Source de repli possible (T-02). |
| **Deux guides** (Collectionneur, Éclaireur) | Conv. 26/10 11 h 05-11 h 15 | Abandonné (EX-69). |
| **IA qui lit les screens** et message de transparence | CdC n° 1 | Abandonné (EX-92). |
| **Images d'étage** de Shadoaze | Conv. 27/10 12 h 56-12 h 57 | Usage à discuter (T-28). |
| **« D'autres surprises »** de l'organisateur | Règlement IV : « ( et d'autres surprises 😈 ) » | Inconnu. |
| **Ressources et notes de Shadoaze** à intégrer | Conv. 25/10 17 h 03, 21 h 05 | À voir lors de l'appel du 31/10 (T-30). |
| Activités libres en jeu (métiers, PvP, archis, prisonniers), guilde des grimpeurs, serveur Kourial | Règlement II et IV | Hors site : règles de jeu sans fonction à construire. |
