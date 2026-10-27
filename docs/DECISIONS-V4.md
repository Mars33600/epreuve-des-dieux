# Décisions du 26 et 27/10/2026 (conversation Marceau ↔ Shadoaze)

Synthèse de l'export de la conversation privée. Elle **remplace** le modèle de points de `REPONSES-SHADOAZE.md`
(difficultés et paliers 1/2/3) et s'ajoute au reste. L'export brut n'est pas versionné : c'est une conversation privée.

## 1. Fin des difficultés

> « Du coup on peut enlever le concept de difficulté et d'éclaireur / aventurier et tout, en vrai ce sera plus compréhensible. »

Plus d'Aventurier, d'Éclaireur ni de Collectionneur. Chacun choisit librement, à chaque étage, ce qu'il fait.

## 2. Nouveau barème : 4 catégories, 1 point chacune, par joueur et par étage

> « Tout compte 1 point parmi 4 catégories : Donjons validés / Donjons validés en full succès / Quêtes principales / Quêtes secondaires. Palier pour valider un étage = 2 × le nombre de joueurs actifs. »

- Un joueur peut donc rapporter de 0 à 4 points par étage.
- **Seuil de déblocage = 2 × nombre de joueurs actifs**, soit une moyenne de 2 points par joueur. La moyenne théorique est de 2,5.
- Les points se gagnent **à la complétion de la catégorie sur tout l'étage**, pas donjon par donjon. Shadoaze l'explique ainsi : un étage peut avoir 6 ou 7 donjons à 5 succès chacun, et l'objectif est que tout le monde fasse au minimum tous les donjons. Un point par succès ferait grimper les sommes et pousserait à contourner certains donjons.
- **Full succès** : chaque donjon a 5 cases à cocher (le succès de base « vaincre le boss », « Duo », puis 3 conditions spéciales). Ces cases sont informatives. Le point « full succès » n'est accordé que quand toutes les cases de tous les donjons de l'étage sont cochées. Les sites communautaires n'affichent que 4 succès, car le succès de base est commun à tous les boss.
- Seuls les donjons et quêtes **de la tranche de niveau de l'étage** rapportent des points pour cet étage.
- Le premier point (les donjons de l'étage) doit rester accessible aux joueurs qui ont peu de temps.
- Si les points bonus faussent l'équilibre, une règle sera ajoutée plus tard. Rien à coder pour l'instant.

## 3. Étages = tranches de niveau du guide Duffus

> « Chaque étage est représenté par une tranche de niveau sur le site Duffus, et ce sont les quêtes et donjons liés à cette tranche qui rapportent des points pour l'étage en cours. »

Exemple : la tranche 40-50 serait l'étage 3. Chaque tranche contient des sous-catégories (des blocs) de quêtes, dans l'ordre optimisé.

Shadoaze a écrit les **10 premiers étages dans des salons Discord**, un par étage. On y trouve les donjons et les quêtes principales recommandées. Marceau est admin et y a accès.

## 4. Quêtes principales et secondaires

- **Principale** = nécessaire pour obtenir un Dofus, prérequis compris. Une quête qui ne donne pas de Dofus mais qui est requise par une quête qui en donne un compte comme principale.
- **Secondaire** = tout le reste : succès, XP, kamas, émotes, complétion.
- Le classement doit être **déterministe**, pas deviné par une IA. Duffus publie un guide par Dofus, avec ses quêtes et leurs prérequis.
- On garde **un seul guide** pour tout le monde, avec un code couleur ou un filtre principal / secondaire. On ne fait pas deux guides.

## 5. Saisie et preuves : la confiance

- **Les joueurs cochent eux-mêmes** leurs quêtes, donjons et succès sur le site. La case cochée sert de preuve.
  > « En vrai on peut trust et si les gens trichent c'est dommage pour eux plus qu'autre chose. »
- La validation par screen, éventuellement auto-validée par un bot, a été jugée « stylée ». Elle reste une **option**, pas l'obligation : oublier un screen obligerait à refaire le donjon.
- Il faut donc **un compte par joueur**, avec connexion.
- Chaque fiche joueur est visible par tous. On peut **filtrer par quête ou par succès** pour voir qui ne l'a pas encore fait, et lui proposer de s'y mettre ensemble.

## 6. Pause et retardataires : gestion manuelle par un admin

> « On réintégrera manuellement les joueurs en pause / les retardataires au cas par cas, juste avoir une option pour passer un joueur en pause afin qu'il ne compte pas dans l'algorithme est déjà un très bon point. »

## 7. Ce que Shadoaze voudrait reprendre de duffus.fr (sous réserve, voir §9)

- **À garder** : le guide (cases à cocher, fiches de quête, progression), les archimonstres (suivi des captures), les avis de recherche, l'encyclopédie, les outils (sauf les tutoriels), les stuffs, le builder, le tableau de bord.
- **À retirer** : la bourse aux échanges, et tout ce qui renvoie à Duffus (en-têtes, liens Twitch, Discord, soutien).
- **À ajouter** : un onglet de validation des succès de donjon, intégré à la progression du tableau de bord, et le marquage principal / secondaire.
- Les étages non débloqués restent **verrouillés et cachés** dans le guide.

## 8. Calendrier et révélation

- **30/10 à 17 h : accès anticipé seulement.** Les joueurs créent leur personnage et rejoignent la guilde. Le site n'est pas attendu à cette date.
- **Vrai départ vers le 13/11.** Il peut glisser un peu, « pas mi-décembre non plus ».
- **Le projet reste secret jusqu'à un reveal.** Idée retenue : vers le 6/11, publier une **page d'accueil en compte à rebours**, sans rien montrer d'autre du site. Un trailer est en option (diaporama animé et voix off) ; Marceau s'en occupe à part.
- L'accès au site sera restreint. Le lien sera donné dans le Discord de l'événement.

## 9. Point ouvert : le contenu de duffus.fr

Reprendre à l'identique le guide et les outils de duffus.fr en retirant le nom de son auteur pose deux problèmes :
- le guide est son travail éditorial ;
- ses données sont dans une base privée, qu'on ne nous a pas autorisés à lire.

Position du projet : **demander l'accord de l'auteur** avant de reprendre son contenu, et en le créditant. Sans accord, le site s'appuie sur des sources ouvertes (DofusDB pour les quêtes, donjons, succès et monstres) et sur le contenu de Shadoaze (salons d'étage), avec un lien vers le chapitre Duffus correspondant.

## 10. Mise à jour du 27/10 : accord de Duffus

Selon Marceau, l'auteur de duffus.fr a donné son accord pour réutiliser son contenu dans ce projet non lucratif. Conditions retenues :
- le pied de page de chaque page du site affiche **« Merci Duffus »**, avec un lien vers duffus.fr ;
- les données sont récupérées par un export fourni par l'auteur si possible, sinon par un import ponctuel et poli de ses points d'accès publics, mis en cache.

À faire : garder une trace écrite de l'accord (capture du message) dans `docs/`.

## 11. Précision : source du contenu des étages

**duffus.fr est la source unique du contenu des étages.** L'étage N correspond à la tranche N du guide. Les donjons, les succès détaillés, les quêtes principales et secondaires de chaque tranche en viennent. Le classement principal / secondaire se déduit des guides « par Dofus » de Duffus.

Les salons Discord `étage-X` de Shadoaze n'étaient qu'une aide provisoire pour les joueurs : ce n'est pas une source de données.

## 12. Réponses de Marceau du 28/10 (priment sur les défauts de SPEC §8.2)

- **Q1 (étage ↔ tranche, cap)** : oui. Étage 0 = la première tranche du guide Duffus, puis une tranche par étage. Le cap est la borne haute de la tranche.
- **Q2 (donjons d'un étage)** : ceux que duffus.fr rattache à la tranche, comme sur le site Duffus.
- **Q3 et Q4** : aucune supposition. Le contenu de chaque étage (catégories, quêtes principales, Dofus) se déduit **uniquement des données de duffus.fr**. La règle du palier pour une catégorie vide ne s'applique que si Duffus ne donne effectivement rien.
- **Q8 (images des étages)** : à récupérer depuis le Discord, en lecture seule.
- **Duffus** : le projet est autonome. On ne sollicite pas l'auteur. L'import passe par les points d'accès publics du site, de façon polie et mise en cache, avec « Merci Duffus » en pied de page.
