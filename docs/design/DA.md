# Direction artistique : L'Épreuve des Dieux

Référence pour le site et le teaser. Les exemples vivants sont `teaser.html` et `maquette-v2.html` (dans ce dossier) : en cas de doute, ces pages font foi.

## Intention

La nuit au pied d'une tour bâtie par les Dieux. La lumière vient **d'en haut** : une lueur dorée au sommet, qui se perd dans les nuées. Tout le reste est sombre, froid et brumeux. L'or est **rare**, il signale le divin et le progrès : l'étage en cours, le seuil, un point obtenu. Le ton est mystérieux et aventureux, jamais gadget.

## Tokens

| Rôle | Token | Valeur | Usage |
|---|---|---|---|
| Nuit | `--night-0/1/2`, `--horizon` | `#05070e` `#0a0e1c` `#141a30` `#2a2240` | Ciel, du zénith à l'horizon violacé |
| Surface | `--surface`, `--surface-2`, `--sunken` | `#0f1426` `#161c33` `#0a0e1b` | Cartes, éléments surélevés, creux (jauge, champs) |
| Traits | `--line`, `--line-soft` | `#283050`, gris à 18 % | Bordures |
| Texte | `--ink`, `--muted`, `--faint` | `#efe8d8` `#aeb3c6` `#959cb3` | Principal, secondaire, mentions |
| Or | `--gold`, `--gold-hi`, `--gold-wash`, `--gold-line` | `#e3b552` `#f6d58a`, or à 12 %, or à 32 % | Accent, chiffres clés, liseré haut des cartes |
| Donjons | `--c-donjon` | `#63c7a0` jade | Catégorie 1 |
| Full succès | `--c-succes` | `#b99af5` améthyste | Catégorie 2 |
| Quêtes principales | `--c-princ` | `#74aef2` azur | Catégorie 3 |
| Quêtes secondaires | `--c-second` | `#ef9a7a` corail | Catégorie 4 |
| Alerte | `--warn` | `#f08a5d` | Hors cap, « pas encore fait » |

Contraste mesuré sur `--surface` : texte 15:1, `--muted` 8,8:1, `--faint` supérieur à 6:1, couleurs de catégorie entre 7,4 et 9:1. Sur la brume la plus claire du décor, tout reste au-dessus de 4,5:1. Le thème est **sombre uniquement** (`color-scheme: dark`).

## Typographie

Via Google Fonts, `display=swap`.
- **Alegreya SC** (700–800) : titres, pseudos, noms d'étage et de donjon. Interlignage 1,1, `text-wrap: balance`.
- **Alegreya Sans** (400/500/700, italique 400) : texte courant, 16 px minimum (18 px sur le teaser).
- **IBM Plex Mono** (500) : chiffres (`tabular-nums`), compte à rebours, sur-titres en capitales espacées (12 px, interlettrage 0,14 em, en or).

## Le décor, en calques

Du fond vers l'avant, dans un conteneur `position: fixed` en `aria-hidden` et `pointer-events: none` :
1. **Ciel** : dégradés CSS (zénith noir, horizon violacé).
2. **Image d'ambiance de l'étage** (option, voir plus bas).
3. **Étoiles** : canvas, plus denses au zénith, dessinées une seule fois ; quelques-unes scintillent sur le teaser.
4. **Lueur divine** : `radial-gradient` doré au sommet de la tour, qui « respire » (opacité, 10 à 12 s). Sur le teaser s'y ajoutent des rayons coniques très pâles et une colonne de lumière.
5. **Crêtes et ruines** : silhouettes SVG presque noires (colonnes brisées, arche).
6. **La tour** (teaser) : SVG généré, avec 14 gradins de pierre, des fenêtres en arche dont certaines sont éclairées, un sceau « ? » par étage, la porte au pied. Les gradins hauts s'effacent sous un masque.
7. **Brume** : 2 ou 3 bandes de `radial-gradient` larges de 200 %, qui dérivent en `translate3d` (90 à 160 s par boucle). On n'anime que `transform` et `opacity`.
8. **Poussières d'or** : canvas, 24 à 46 particules qui montent lentement. Un sprite pré-rendu, 25 à 30 images par seconde.
9. **Voile** : vignette et assombrissement léger, pour la lisibilité.

**Image d'ambiance par étage.** L'URL est réglée par étage (`AMBIANCES[n]` dans la maquette, `AMBIANCE` dans le teaser, et `?ambiance=URL` pour tester). Elle est chargée en JavaScript avec `new Image()`. Elle n'apparaît qu'une fois chargée (fondu de 1,6 s), filtrée (`saturate(.65) brightness(.5)`, opacité de 45 à 55 %). En cas d'échec, rien ne change : le décor généré reste. Format conseillé : paysage, 2400 × 1350, WebP de moins de 400 Ko, sombre, sans texte. **Pas de capture du jeu ni d'artwork d'Ankama** : il faut une création originale ou une image libre de droits.

## Composants

- **Carte** : pierre sombre presque opaque (dégradé de `rgba(22,28,51,.92)` à `rgba(13,17,33,.94)`), rayon de 10 px, liseré or de 1 px en haut (`inset 0 1px 0 var(--gold-line)`). Elle est opaque pour garantir le contraste, quel que soit le décor derrière.
- **Tour (colonne de gauche)** : même principe que la v1. Ce sont des blocs empilés en pyramide : l'étage en cours en bas, en pleine largeur, et 6 étages scellés au-dessus, de plus en plus étroits. Un scellé est un bloc de pierre portant un sceau « ? » cerclé d'or. Les scellés s'effacent vers le haut (masque) sous une brume qui respire. L'étage en cours a une bordure or, un halo et un filet doré en bas, rempli selon la jauge. Le premier scellé devient « Étage 1 · prêt » quand le seuil est atteint. Sur mobile, la tour passe au-dessus du contenu et ne garde que 3 étages scellés.
- **Jauge d'étage** : une seule jauge, **une encoche par point requis** (le seuil vaut 2 × le nombre de grimpeurs actifs). Les encoches se remplissent dans l'ordre des catégories, chacune de sa couleur. Au-dessus : un grand chiffre « 20 / 22 points » et la formule du seuil. Au-dessous : ce qui manque et le maximum possible. Seuil atteint : bordure or. Ensuite viennent **4 tuiles de catégorie** : icône, nom, définition en une phrase, « x / N grimpeurs », mini-barre et lien « Qui manque ? ».
- **Pastille de catégorie** : un disque de 36 px (48 px dans la fiche) avec l'icône de la catégorie. L'**anneau** (`conic-gradient`) montre la progression ; le **disque plein** signifie que le point est obtenu. On lit la forme sans la couleur, et un `aria-label` donne « Donjons : 2 sur 3 ».
- **Icônes** (trait de 1,8, SVG `<symbol>`) : porte en arche pour les donjons, étoile pour le full succès, œuf (le Dofus) pour les quêtes principales, parchemin pour les quêtes secondaires.
- **Case à cocher** : la case native, restylée (`appearance: none`). C'est un carré gravé de 22 px, rayon 5 px, qui se remplit de la couleur de sa catégorie avec une coche sombre. La ligne entière (libellé et explication) est cliquable, sur 44 px de haut minimum. La première case d'un donjon (« Vaincre le boss ») est en jade ; les 4 autres succès sont en améthyste. Une case désactivée signale une fiche en lecture seule.
- **Badge principal / secondaire** : une pilule mono de 12 px. **Principale** : fond azur teinté, bordure pleine, icône œuf. **Secondaire** : contour corail **en pointillés**, icône parchemin. Le trait plein ou pointillé distingue les deux sans la couleur.
- **Filtre « qui n'a pas fait… ? »** : un `select` groupé (catégories, donjons, succès, quêtes). Il affiche deux listes de pastilles : « Pas encore fait » (✗, bordure alerte) et « Déjà fait, ils peuvent accompagner » (✓). Les cartes concernées sont entourées, les autres estompées.
- **Fiche de quête** : on touche le nom d'une quête (un bouton souligné d'or, distinct de sa case de 44 px) pour l'ouvrir. C'est un `<dialog>` ouvert par `showModal()`, avec `aria-modal` et `aria-labelledby`. Sur ordinateur, c'est un panneau latéral à droite (560 px, liseré or à gauche) ; sous 640 px, il passe en plein écran. Le fond est assombri à 66 %. Il se ferme par la croix (44 px), par Échap ou par un clic sur le fond. Le focus va au titre, reste piégé dans le panneau, puis revient au déclencheur. L'en-tête est collant : sur-titre, nom, badge, niveau, zone, PNJ de départ avec sa position en mono or `[x,y]`, et la case « Faite », synchronisée avec la liste et en lecture seule sur la fiche d'un autre grimpeur. Le corps est découpé en sections à sur-titre mono or :
  - **Pourquoi la faire** : pour une principale, la chaîne cliquable jusqu'au Dofus ; pour une secondaire, une phrase.
  - **Prérequis** : des liens qui ouvrent leur fiche, avec « ✓ Faite » ou « ✗ Pas encore faite ».
  - **Étapes** : numérotées dans des pastilles, avec les positions mises en évidence. Encart **Jusqu'où la faire** au contour alerte plein ; les étapes suivantes sont atténuées, numéro en pointillés. Encart **À lier** au contour jade en pointillés. Le titre en clair sépare les deux encarts sans la couleur.
  - **Ce dont tu as besoin** et **Récompenses** : des lignes avec un type en étiquette (Objet, Ressource, Monstre, XP, Kamas, Succès) et une quantité.
  - **Qui ne l'a pas encore faite ?** : les mêmes pastilles que le filtre.

  Aperçu direct : `maquette-v2.html?quete=p2`.
- **Compte à rebours** : il vise le **13/11/2026 à 17:00, heure de Paris**, calculé avec `Intl` et `Europe/Paris`, jamais avec l'heure locale. Teaser : 4 tablettes (jours, heures, minutes, secondes) et, si le fuseau du visiteur diffère, son heure locale. En-tête du site : une ligne en mono, puis « Jour N de l'ascension » après la date.

## Mouvement et performance

- On n'anime que `transform` et `opacity`. Les canvas plafonnent le DPR à 2 et à 30 images par seconde, et se mettent en pause quand l'onglet est caché (`visibilitychange`).
- `prefers-reduced-motion: reduce` fige la brume, la lueur et les particules (dessinées une fois), et retire les transitions. Le compte à rebours continue.
- Ni `backdrop-filter` ni filtre SVG animé : c'est coûteux sur mobile.
- Vérifié à 360 px : aucun défilement horizontal (`overflow-x: clip` sur `html`). Les cibles tactiles font au moins 44 px.

## À ne pas faire

- Utiliser un visuel, un logo, une police ou une capture d'Ankama. Le pied de page « projet de fans, non officiel » reste obligatoire.
- Poser du texte directement sur le décor sans carte, halo ou ombre portée.
- Mettre de l'or partout : il est réservé au divin et au progrès.
- Coder une information par la seule couleur : il faut toujours une icône, une forme ou un texte.
- Utiliser un fond clair ou un thème clair : ce n'est pas prévu.
- Animer plus de 3 calques à la fois, ou animer une propriété qui déclenche un *layout* (`top`, `width`, `filter`).
- Réintroduire les anciennes difficultés (Aventurier, Éclaireur, Collectionneur) ou des paliers dans l'interface.
- Afficher du `innerHTML` sans échappement : les pseudos passent par `esc()`, comme dans la maquette.
