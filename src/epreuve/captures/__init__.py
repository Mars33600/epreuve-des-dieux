"""Module E1 : le suivi des archimonstres (et des boss du Dofus Ocre) et des avis de recherche.

- `schema.py`    les colonnes retenues des tables Duffus (relevé du 28/10/2026) ;
- `aspirer.py`   l'aspiration polie de ces tables vers donnees/duffus/AAAA-MM-JJ/ ;
- `catalogue.py` la construction du catalogue (niveaux, aires, icônes, résumés nettoyés), sans réseau ;
- `domaine.py`   les calculs purs : recherche, filtres, regroupements, compteurs, pierres d'âme ;
- `depot.py`     le catalogue et les captures en base (Postgres) ou en mémoire (démo, tests).

Le détail est dans docs/lots/E1.md.
"""
