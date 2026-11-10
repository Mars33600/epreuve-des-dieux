# Suivi des obligations

Ce qui a été demandé ou validé avec Shadoaze (la conversation fait foi), coché quand c'est fait **et vérifié**.
Détails : `DECISIONS-V4.md`.

## Calendrier

- [x] Rien d'accessible aux joueurs avant le 13/11 : seulement le compte à rebours
- [x] Page compte à rebours en ligne : https://epreuve-des-dieux.fr
- [ ] Reveal de la page vers le 6/11 (lien donné sur le Discord par Shadoaze et Marceau)
- [ ] Trailer (option, géré par Marceau)
- [x] 10/11 : remise à zéro faite (sauvegarde avant) : étage 0 ouvert, date plancher 13/11 17 h, étages 1 à 23 scellés, 0 fiche, 0 coche, 0 bilan, journal des tests purgé, corrections de blocs gardées, `OUVERTURE_AUTO_TEASER` retiré
- [x] 10/11 : pré-inscription du 11/11 17 h au 13/11 17 h (bouton sur le compte à rebours, page seule, reste du site fermé, fiches closes à l'ouverture sauf admin), question de dispo pour la guilde (migration i1), serveur Mikhal dans les règles, pied de page « Réalisé par Shadoaze et Mars »
- [x] 10/11 : tableau de bord, carte profil dorée (initiale) et carte « Étage en cours » sombre à bandeau ; récapitulatif des dispos guilde dans /admin/grimpeurs
- [x] 10/11 : tableau de bord, catégories en clair, lien « N blocs du guide à cocher », points par catégorie et profil de jeu (« Plutôt donjons ») ; règles, Duffus pour les quêtes une à une, le site pour le bloc entier
- [x] 10/11 : « Il te reste à cocher » liste aussi les donjons pas complets ; encadré « Mode teaser » compact ; « guide Duffus » en lien dans les règles
- [ ] Avant le 13/11 17 h : vérifier que les coches d'admins faites pendant la recette sont voulues (sinon les retirer)
- [ ] Ouverture du site le vendredi 13/11 à 17 h, tout prêt « nickel au démarrage »

## Règles du jeu

- [x] Plus de difficultés (Aventurier, Éclaireur, Collectionneur supprimés)
- [x] 4 catégories, 1 point chacune quand elle est complète sur l'étage, 4 points max par joueur
- [x] Full succès : 5 cases par donjon (vaincre le boss + 4 succès), point quand tout l'étage est coché
- [x] Palier pour ouvrir un étage = 2 × joueurs actifs
- [x] Seuls les donjons et quêtes de la tranche de l'étage comptent
- [x] Ouverture d'étage manuelle par un admin, après vérification
- [x] Étages non ouverts cachés (tour et guide)
- [x] Pause d'un joueur par un admin : il ne compte plus dans le palier
- [x] Réintégration des retardataires et des joueurs en pause, à la main par un admin
- [x] Page « Règles » sur le site
- [x] Pas de points bonus

## Contenu (Duffus, source unique)

- [x] Étages = tranches du guide Duffus (24 étages, 0 à 23), cap = haut de la tranche
- [x] Étages 0 et 1 importés (quêtes, fiches, donjons et leurs succès)
- [x] Étages 2 à 23 importés (base de production remplie le 28/10). Fiches absentes chez Duffus prises sur DofusDB : il ne manque que 2 fiches sur 1 010 quêtes
- [x] Quêtes principales et secondaires classées d'après les guides par Dofus (sans supposition)
- [x] Images des étages récupérées sur le Discord (étages 0 à 10)
- [x] Images affichées sur le site, chacune seulement une fois son étage ouvert

## Site

- [ ] Un compte par joueur (connexion Discord) : codé et testé, reste l'essai avec le vrai Discord
- [x] Les joueurs cochent eux-mêmes, en confiance, sans screen
- [x] Fiches joueurs visibles par tous
- [x] Filtre « qui n'a pas fait… ? » par quête ou succès
- [x] Un seul guide avec code couleur et filtre principales / secondaires
- [x] Fiche de quête complète comme sur Duffus : départ (zone, position, PNJ), étapes détaillées avec suivi étape par étape, besoins, prérequis, gains (kamas compris), succès lié, qui l'a faite ou non
- [x] Onglet de validation des succès de donjon, dans la progression du tableau de bord
- [x] Ambiance « Nuit du teaser » sur tout le site, accueil = pyramide en grand sans aucun chiffre (mystère), jauge dessous
- [x] Histoire de Shadoaze : prologue à la première connexion + page « L'histoire »
- [x] Accès réservé aux participants

- [x] Menu logique avec « Monde des Douze », recherche globale en direct (grimpeurs, quêtes, monstres, objets…), fiche de quête en fenêtre centrée, page Grimpeurs avec fiche par joueur
- [x] Recette complète par le testeur : 61 pages, 783 clics, 0 défaut restant à 360 px

- [x] Jauge dans la pyramide (remplissage, trait du palier, infobulle avec les grimpeurs actifs) et bandeau d'étage sans dépliant
- [x] Donjons dans leur propre section, règle précise de chaque challenge (« aléatoire » quand le jeu choisit la cible)
- [x] Liens vers l'encyclopédie (objets, monstres, PNJ) ouvrables dans un nouvel onglet ; police plus grande ; page Règles lisible
- [x] Sauvegarde chiffrée chaque nuit sur GitHub, restauration vérifiée ; retour à la version précédente possible

- [x] Ouverture automatique de l'étage suivant (jauge pleine + date plancher) et annonce @everyone du « Gardien de la Tour » (04/11, retour Shadoaze)
- [x] Annonce du lancement du site par le Gardien, une seule fois, le 13/11 à 17 h 00 (05/11)
- [ ] Webhook Discord des annonces : Shadoaze le crée, Marceau fait `fly secrets set DISCORD_WEBHOOK_ANNONCES=…`
- [x] Les 100 quêtes d'alignement comptent pour le Dofus Ivoire ; Règles §1 : Donjon en mousse et Tour du monde en fil rouge (04/11)
- [x] Quêtes d'alignement en secondaire en ligne : corrigé, déployé (v22) et étages reconstruits (04/11)
- [x] Créer sa fiche : plus de niveau (départ niveau 1), classe obligatoire (04/11)

- [x] 06/11 : blocs mixtes coupés en deux moitiés (rouge / jaune, cochables séparément, menu « n principales / n secondaires »), plus de lien Duffus par bloc ; dépliants à 3 niveaux, comptes entre parenthèses ; « Il te reste à cocher » ; fiche fusionnée dans le tableau de bord ; délai de grâce d'1 min avant l'ouverture auto ; 144/146 donjons à 5 cases (Cire Momore, Gargandyas : aucun succès en jeu)

## Modules de Duffus « à l'identique »

- [x] Guide (cases, fiches, progression)
- [x] Tableau de bord
- [x] Archimonstres (sans la bourse aux échanges)
- [x] Avis de recherche
- [x] Encyclopédie (objets, monstres, recettes, panoplies, sorts, PNJ, quêtes) ; manquent les cartes et les variantes de sorts
- [ ] Outils (sans les tutoriels) : 6 sur 7 faits (Almanax, drop, classes et sorts, élevage, craft, XP des métiers) ; manque la carte interactive
- [x] Stuffs (builds PvM de Duffus)
- [x] Builder : objets, panoplies (et navigateur), conditions, totaux, forgemagie, variantes, dégâts d'arme et de sorts, comparaison, builds partagés. Non repris faute de demande : simulation Poutch, skins, forgemagie élémentaire de l'arme, dossiers
- [x] Rien ne renvoie à Duffus (en-têtes, Twitch, Discord, soutien), sauf « Merci Duffus »

## Crédit

- [x] Teaser : plus aucun lien vers Duffus (demande de Shadoaze, 04/11)
- [x] « Merci Duffus » sur toutes les pages du site
