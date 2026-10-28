"""Le Builder (lot E3) : calculateur d'équipement, repris à l'identique de celui de duffus.fr.

- `effets` : les tables de correspondance de Duffus (effet → caractéristique, emplacements, groupes) ;
- `aspirer` : lecture polie des tables de référence `items` et `item_sets` de Duffus, vers `donnees/` ;
- `catalogue` : les objets et panoplies en mémoire, et la recherche par emplacement ;
- `calcul` : les formules (totaux, panoplies, conditions, caractéristiques de base, parchemins, dérivés) ;
- `depot` : les builds des grimpeurs, en base.

Voir docs/lots/E3.md.
"""
