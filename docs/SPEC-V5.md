# Spec v5 : le site devient l'outil de validation, Duffus reste le guide

Source : conversation Marceau ↔ Shadoaze du 29/10/2026, 21 h 36 à 23 h 07, avec ses captures. Elle prime sur SPEC v4 partout où elles divergent. Rédigée le 03/11, pour une ouverture le **vendredi 13/11 à 17 h**.

## 1. Le changement de cap

Citations clés :
> « on peut faire de notre site juste un truc de validation pour décharger. Et on le fait marcher en tandem avec le site de duffus » (Shadoaze, 22 h 07)
> « les gens utilisent duffus pour le guide, et quand ils valident un bloc sur duffus ils peuvent le cocher sur notre site, SAUF que on a les blocs encadrés en différentes couleurs en fonction de si c'est principale ou secondaire » (22 h 54-55)
> « Le cochage unitaire se fait sur duffus. Et nous on a le bloc entier de notre côté. Le système de point reste. » (Marceau, 23 h 01, validé par Shadoaze)
> « on peut retirer la section outil… encyclo stuff builder… elle est présente sur le site duffus donc ça va faire doublon » (23 h 03-04)
> « scoring, déblocage et suivi des joueurs entre eux » (23 h 05)

Le site garde donc trois rôles : **le scoring, le déblocage des étages et le suivi des joueurs entre eux**. Le guide, les fiches de quête, l'encyclopédie et les outils, c'est **duffus.fr**, avec le compte Duffus de chaque joueur.

## 2. Ce qu'on retire de l'interface

On désactive, on ne supprime pas. Le code reste dans git et les tables restent en base, pour pouvoir revenir en arrière.

- Le menu **« Monde des Douze »** en entier : encyclopédie, stuffs, builder, outils, archimonstres et avis de recherche.
- La **liste des quêtes une par une**, la **fiche de quête** en fenêtre et le **suivi par étape**.
- La recherche globale **se limite** aux grimpeurs, aux blocs et aux donjons.
- Les routes désactivées répondent 404, pas d'erreur 500.
- Un réglage `modules.monde_des_douze: false` dans `config/regles.yaml` permet de tout rallumer.

## 3. La page d'étage, nouvelle structure

Dans l'ordre :

1. **Bandeau et jauge** : inchangés.
2. **Donjons de l'étage** : inchangés. Ce sont les 5 cases par donjon avec leur règle, et le compteur x/N.
3. **Blocs du guide**, c'est le cœur de la v5 :
   - les blocs Duffus de la tranche, **dans l'ordre du guide**, avec **le titre exact de Duffus** et son numéro (« Bloc 7 · Début des quêtes d'alignement ») ;
   - **cadre rouge = bloc principal**, **cadre jaune = bloc secondaire**, comme sur le dessin de Shadoaze. La couleur s'accompagne d'un libellé « Principal » ou « Secondaire », pour rester lisible sans la couleur ;
   - pour chaque bloc :
     - une case **« Bloc terminé »** ;
     - le nombre de quêtes du bloc, accordé (« 7 principales »), dans un menu plié qui liste leurs noms dans l'ordre du guide ;
     - plus de lien Duffus par bloc (retiré le 06/11, Duffus ne sait pas ouvrir un bloc précis) : un seul lien vers le guide Duffus, en tête de la section. La revue d'étage de l'admin garde le lien par bloc ;
     - le compteur « x grimpeurs l'ont fait » et le volet **« Fait par / Pas encore fait par »**.
4. **Filtres** : Donjons, Full succès, Blocs principaux, Blocs secondaires, « Seulement ce qui me reste ». Leur état est gardé dans l'URL.
5. **Grimpeurs actifs** : le dépliant reste inchangé.

## 4. Le barème (« le système de point reste »)

- **Donjons** et **Full succès** : inchangés.
- **Quêtes principales** : 1 point quand **tous les blocs principaux** de l'étage sont cochés (moitiés rouges des blocs hybrides comprises, §5 bis).
- **Quêtes secondaires** : 1 point quand **tous les blocs secondaires** de l'étage sont cochés (moitiés jaunes comprises).
- Le palier reste à 2 × grimpeurs actifs. Une catégorie vide est traitée comme en v4.
- En base : une nouvelle table `coche_bloc` (grimpeur, bloc, date). Les coches de quêtes ne servent plus au barème. La production n'en contient pas encore, donc il n'y a rien à migrer.

## 5. Bloc principal ou secondaire

- **Règle par défaut** : un bloc est principal s'il contient au moins une quête principale (classement déterministe tiré des guides par Dofus de Duffus, déjà en place). Sinon, il est secondaire.
- **Chaque bloc peut être corrigé par un admin** dans la revue d'étage. La correction est journalisée et prime sur la règle.
- La revue affiche, pour chaque bloc, le nombre de quêtes principales sur le total. L'admin voit ainsi d'un coup d'œil un bloc classé principal pour une seule quête utile, qui était la crainte de Shadoaze le 26/10.
- À faire valider par Shadoaze, étage par étage, avant chaque ouverture. Son exemple : « dans cette tranche, seul le bloc 7, début des quêtes d'alignement, est principal ».

### 5 bis. Blocs hybrides (décision de Marceau et Shadoaze, 06/11)

- Un bloc qui contient des quêtes principales **et** des quêtes secondaires est **coupé en deux moitiés côte à côte** (empilées sur un petit écran), même numéro et même titre : à gauche la **moitié rouge** (ses quêtes principales), à droite la **moitié jaune** (ses secondaires). Chacune se coche à part (case « Partie principale terminée », nommée « Bloc N, partie principale » pour un lecteur d'écran). Un bloc entièrement principal ou secondaire reste d'un seul morceau.
- Barème : « Quêtes principales » demande toutes les parties rouges (blocs entiers et moitiés), « Quêtes secondaires » toutes les parties jaunes. Une catégorie compte dès qu'elle a une partie : un étage dont un bloc est hybride a une catégorie secondaire, donc K et le palier montent (étages 0 et 1 : K passe de 3 à 4, le palier de ⌈1,5 × actifs⌉ à 2 × actifs).
- En base, une moitié est une ligne `bloc` de plus, de clé (étage, titre, `partie`) : la reconstruction retrouve les mêmes lignes, sans doublon et avec leurs coches ; chaque quête est rattachée à la moitié de sa nature. Coches, « qui a fait quoi » (une option par partie, « Bloc N · titre (principale) »), tableau de bord et recherche fonctionnent sans cas spécial. Migration `h1_blocs_hybrides`.
- Corrections d'admin : la nature d'une moitié suit ses quêtes ; l'admin **change la nature d'une quête**, qui passe aussitôt dans l'autre moitié (créée au besoin, masquée si elle se vide), comme le ferait la reconstruction. Une correction posée sur un **bloc entier** reste valable tant qu'il est entier ; si le bloc devient hybride, elle ne s'applique plus (journalisé à la reconstruction).

## 6. Le suivi entre joueurs

> « ça va pas mal épurer et simplifier aussi le qui l'a fait qui l'a pas fait » ; « ça peut même faire des calls en mode qui ce soir pour bloc 7 ? »

- La **fiche du grimpeur** montre, étage par étage, ses blocs, ses donjons et ses succès faits ou à faire.
- Le **filtre « qui a fait / qui n'a pas fait »** de la page Grimpeurs porte sur les **blocs**, les donjons et les succès.
- Le **tableau de bord** montre la progression par étage (blocs, donjons, succès) et garde l'onglet des succès de donjon.

## 7. Comptes et accès

- **Plus de liste officielle obligatoire.** Marceau : « les gens officiels sont ceux sur le discord ». Tout membre du serveur Discord peut créer sa fiche à partir du 13/11 (`regles.liste_officielle_obligatoire: false`).
- **« Créer ma fiche »** est bien visible dans l'en-tête pour toute personne connectée sans fiche, admins compris.
- **Admins** : ceux qui ont le rôle « Administrateur », plus `ADMINS_SUPPLEMENTAIRES`, qui contient Shadoaze, propriétaire du serveur sans rôle. On ajoute aussi : **le propriétaire du serveur est admin d'office**.
- Avant le 13/11, rien ne change : seul le compte à rebours est visible, sauf pour les admins.

## 8. Calendrier

| Date | Étape |
|---|---|
| 03 → 06/11 | Développement v5 |
| 06/11 | Le teaser est déjà en ligne : on donne le lien sur le Discord (reveal) |
| 07 → 09/11 | Recette par le testeur, puis par Marceau et Shadoaze ; validation des blocs principaux des étages 0 et 1 par Shadoaze |
| 10/11 | Mise en ligne de la version finale, sauvegarde vérifiée |
| 13/11 17 h | Ouverture |

## 9. Hors périmètre

- La fiche de quête, la liste des quêtes, l'encyclopédie, les stuffs, le builder, les outils, les archimonstres et les avis de recherche : tout est sur Duffus.
- Les points bonus, toujours abandonnés.
