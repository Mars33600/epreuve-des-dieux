# Direction artistique : L'Épreuve des Dieux

Référence pour le site et le teaser. Les exemples vivants sont `teaser.html` et `maquette-v2.html` (dans ce dossier) : en cas de doute, ces pages font foi.

## Intention

**Nuit du teaser** (variante A de `maquettes-da.html`, DECISIONS-V4 §13) : une nuit bleue profonde et de l'or. La lumière vient d'en haut (lueur dorée au sommet de la tour), la brume dérive au pied. L'image de l'étage est le fond de toute la page, assombrie par un voile ; le texte se lit sur des cartes **quasi opaques**. L'or signale le divin et le progrès. Le ton reste mystérieux, jamais gadget. Le « crépuscule » violet clair du 28/10 est abandonné : il était trop clair et les phrases ne se lisaient pas. Thème sombre uniquement.

## Tokens

| Rôle | Token | Valeur | Usage |
|---|---|---|---|
| Nuit | `--night-0/1/2`, `--horizon` | `#05070e` `#0a0e1c` `#141a30` `#2a2240` | Du zénith à l'horizon |
| Surface | `--card`, `--surface`, `--surface-2`, `--sunken` | `rgba(10,14,28,.96)` `#151b33` `#1b2340` `#0c1020` | Carte quasi opaque, élément surélevé, creux (jauge, champs) |
| Traits | `--line`, `--line-soft` | or à 40 %, or à 20 % | Bordures |
| Texte | `--ink`, `--muted`, `--faint` | `#f1ead9` `#bdb7a7` `#a9a595` | Principal, secondaire, mentions |
| Or | `--gold`, `--gold-hi`, `--gold-deep`, `--gold-wash`, `--gold-line` | `#e3b552` `#f6d58a` `#a8781f`, or à 12 %, or à 32 % | Accent, chiffres clés, liseré haut des cartes, focus |
| Décor | `--veil`, `--fog`, `--glow` | `5,8,22` `150,160,200` `255,221,150` | Voile, brume, lueur (triplets RVB pour `rgba()`) |
| Donjons | `--c-donjon` | `#72e0b6` jade | Catégorie 1 |
| Full succès | `--c-succes` | `#cdb0ff` améthyste | Catégorie 2 |
| Quêtes principales | `--c-princ` | `#86beff` azur | Catégorie 3 |
| Quêtes secondaires | `--c-second` | `#ffa684` corail | Catégorie 4 |
| Alerte | `--warn` | `#ff9d68` | Hors cap, « pas encore fait » |

**Échelle typographique** : `--t-xs` 12, `--t-sm` 14, `--t-base` 16 (corps), `--t-h3` 18, `--t-h2` 21 à 26, `--t-h1` 22 à 30 px. **Espacements** `--s1` à `--s6` : 4, 8, 12, 16, 24, 32 px. **Rayons** 8 px (`--r`) et 12 px ; une seule ombre douce (`--ombre`).

Contraste mesuré sur une carte (`#0a0e1c`) : texte courant `--ink` environ 15:1, `--muted` environ 9:1 (au-dessus de 7:1, AAA), `--faint` environ 7:1, or et couleurs de catégorie au-dessus de 7:1. Le **focus** est un contour de 3 px en `--gold-hi`, décalé de 3 px, sur tous les éléments. Les cibles tactiles font au moins 44 px.

## Le décor de la page

Dans un conteneur `position: fixed`, `aria-hidden`, `pointer-events: none`, du fond vers l'avant : ciel en dégradé, **image de l'étage** (`.ambiance`, plein cadre, `saturate(.85) brightness(.8)`), étoiles (canvas), lueur dorée qui respire, brume qui dérive, crêtes, poussières d'or (canvas), **voile** (`rgba(var(--veil))`, de 80 % en haut à 58 % au milieu) et vignette. L'image vient de l'étage ouvert (`/etages/N/image`), chargée en JavaScript ; en cas d'échec, le décor généré reste. Pas de capture du jeu ni d'artwork d'Ankama non libre de droits.

## En-tête

Une barre **compacte et collante** (`.bar`, 52 px) : la marque, le menu (une seule ligne sur grand écran), l'horloge compacte et le compte. Sous 1180 px, le menu se replie derrière un bouton « burger » (case à cocher CSS, aucun script). Aucun défilement horizontal, nulle part.

## Accueil : la pyramide en grand

Les étages ouverts ou terminés sont des blocs de pierre nommés et cliquables (survol lumineux, focus net), empilés du plus large (le plus ancien) au plus étroit. **Aucun chiffre ni nombre d'étages** : pas de numéro, pas de compteur. Au-dessus, des **gradins anonymes** dessinés par une seule règle CSS (`.pyr-haut` : dégradés répétés, découpe en escalier irrégulier, masque qui les efface) se perdent dans la lueur et la brume : on ne peut pas les compter, et le HTML ne contient ni attribut ni liste cachée qui trahisse le total (test `test_tour_html_ne_trahit_pas_le_nombre_d_etages`). La **jauge de l'étage en cours est placée sous la pyramide**, jamais superposée.

## L'histoire de Shadoaze

Le texte vit dans `src/epreuve/web/contenu/histoire.md`. Prologue **plein écran à la première connexion** d'un grimpeur (passable par « Entrer dans la tour », mémorisé en base dans `grimpeur.prologue_vu_le`), puis page « L'histoire » dans le menu. Mise en page de récit : colonne de 660 px, chapeau en italique, mots isolés en capitales dorées (« Une tour. », « Goultard. »), citations avec filet d'or, question finale centrée.

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

**Image d'ambiance par étage.** L'URL est réglée par étage (`AMBIANCES[n]` dans la maquette, `AMBIANCE` dans le teaser, et `?ambiance=URL` pour tester). Elle est chargée en JavaScript avec `new Image()`. Elle n'apparaît qu'une fois chargée (fondu de 1,6 s), à peine filtrée (`saturate(1.05) brightness(.9)`, opacité de 85 %) : on doit la voir. La lisibilité vient de **voiles locaux** derrière le texte posé sur le décor (titre, horloge, menu, pied de page), jamais d'un voile global. La page « La Tour » porte l'image de l'étage ouvert. En cas d'échec, rien ne change : le décor généré reste. Format conseillé : paysage, 2400 × 1350, WebP de moins de 400 Ko, sombre, sans texte. **Pas de capture du jeu ni d'artwork d'Ankama** : il faut une création originale ou une image libre de droits.

## Composants

- **Carte** : pierre sombre presque opaque (dégradé de `rgba(22,28,51,.92)` à `rgba(13,17,33,.94)`), rayon de 10 px, liseré or de 1 px en haut (`inset 0 1px 0 var(--gold-line)`). Elle est opaque pour garantir le contraste, quel que soit le décor derrière.
- **Pyramide d'accueil** : voir plus haut.
- **Jauge d'étage** : une seule jauge, **une encoche par point requis** (le seuil vaut 2 × le nombre de grimpeurs actifs). Les encoches se remplissent dans l'ordre des catégories, chacune de sa couleur. Au-dessus : un grand chiffre « 20 / 22 points » et la formule du seuil. Au-dessous : ce qui manque et le maximum possible. Seuil atteint : bordure or. Ensuite viennent **4 tuiles de catégorie** : icône, nom, définition en une phrase, « x / N grimpeurs », mini-barre et lien « Qui manque ? ».
- **Pastille de catégorie** : un disque de 36 px (48 px dans la fiche) avec l'icône de la catégorie. L'**anneau** (`conic-gradient`) montre la progression ; le **disque plein** signifie que le point est obtenu. On lit la forme sans la couleur, et un `aria-label` donne « Donjons : 2 sur 3 ».
- **Icônes** (trait de 1,8, SVG `<symbol>`) : porte en arche pour les donjons, étoile pour le full succès, œuf (le Dofus) pour les quêtes principales, parchemin pour les quêtes secondaires.
- **Case à cocher** : la case native, restylée (`appearance: none`). C'est un carré gravé de 22 px, rayon 5 px, qui se remplit de la couleur de sa catégorie avec une coche sombre. La ligne entière (libellé et explication) est cliquable, sur 44 px de haut minimum. La première case d'un donjon (« Vaincre le boss ») est en jade, **mise en surbrillance** (liseré épais, fond jade, mention « 1 point Donjons »), avec une légende au-dessus de la liste : cocher le boss de tous les donjons de l'étage rapporte déjà le point Donjons ; les 4 autres succès sont en améthyste. Une case désactivée signale une fiche en lecture seule.
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
- **Aucun défilement horizontal, nulle part** (360, 768, 1440 px) : les bandes d'onglets et d'étages passent à la ligne (`flex-wrap`), les grilles utilisent `minmax(0,1fr)`, `overflow-x: clip` sur `html`. Les cibles tactiles font au moins 44 px.

## À ne pas faire

- Utiliser un visuel, un logo, une police ou une capture d'Ankama. Le pied de page « projet de fans, non officiel » reste obligatoire.
- Poser du texte directement sur le décor sans carte, halo ou ombre portée.
- Mettre de l'or partout : il est réservé au divin et au progrès.
- Coder une information par la seule couleur : il faut toujours une icône, une forme ou un texte.
- Utiliser un fond clair ou un thème clair : ce n'est pas prévu.
- Animer plus de 3 calques à la fois, ou animer une propriété qui déclenche un *layout* (`top`, `width`, `filter`).
- Réintroduire les anciennes difficultés (Aventurier, Éclaireur, Collectionneur) ou des paliers dans l'interface.
- Afficher du `innerHTML` sans échappement : les pseudos passent par `esc()`, comme dans la maquette.
