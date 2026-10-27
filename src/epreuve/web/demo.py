"""Démonstration locale du site, sans base ni Discord : des données FICTIVES en mémoire.

    uv run python -m epreuve.web.demo          puis ouvrir http://127.0.0.1:8080

Les 12 grimpeurs de la maquette (docs/maquette-v1.html), dont deux en pause (l'un inscrit après
l'ouverture, en attente qu'un admin le passe actif), plus un exclu (invisible sur le site) et une
validation annulée (absente du fil), pour voir ces règles à l'œuvre.
L'horloge est simulée au dimanche 8 novembre 2026 à 18:00 ;
`?horloge=2026-11-13T17:00` dans l'adresse en simule une autre.

Le calcul de la jauge est le VRAI calcul du domaine : seules les données sont inventées.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import uvicorn

from epreuve.domaine.modeles import Contenu, EntreeJournal, Etage, Grimpeur, Instantane, Palier, Validation
from epreuve.web.app import creer_app

PARIS = ZoneInfo("Europe/Paris")
HORLOGE_DEMO = datetime(2026, 11, 8, 18, 0, tzinfo=PARIS)
OUVERTURE = datetime(2026, 10, 30, 17, 0, tzinfo=PARIS).astimezone(UTC)
INSCRIPTION = OUVERTURE - timedelta(days=3)  # inscrits avant l'ouverture : actifs

ETAGE0 = Etage(
    id=1, numero=0, nom="Le Seuil", level_cap=20, seuil_pourcent=75, statut="ouvert", ouvert_le=OUVERTURE,
    date_plancher_suivant=datetime(2026, 11, 13, 17, 0, tzinfo=PARIS).astimezone(UTC),
    zone_quetes="Incarnam", donjons_affiches=("Kardorim",),
    chapitre_guide="Chapitre 0 (nom à confirmer par Shadoaze)",
)  # fmt: skip

CONTENUS = (
    Contenu(1, 1, "succes", "Crypte de Kardorim", "Kardorim vaincu"),
    Contenu(2, 1, "succes", "Kardorim (Duo)", "Kardorim (Duo)"),
    Contenu(3, 1, "succes", "Kardorim (Zombie)", "Kardorim (Zombie)"),
    Contenu(4, 1, "succes", "Kardorim (Premier)", "Kardorim (Premier)"),
    Contenu(5, 1, "succes", "Kardorim (Spécial)", "Kardorim (Spécial)"),
    Contenu(6, 1, "lot_quetes", "Guide Duffus : Chapitre 0 (nom à confirmer par Shadoaze) à 100 %",
            "Guide Duffus : Chapitre 0 (nom à confirmer par Shadoaze) à 100 %"),
)
PALIERS = (
    Palier(1, 1, 1, "Kardorim vaincu", frozenset({1})),
    Palier(2, 1, 2, "Kardorim full succès", frozenset({1, 2, 3, 4, 5})),
    Palier(3, 1, 3, "Guide Duffus à 100 %", frozenset({6})),
)


def _g(id_, pseudo, classe, diff, statut, niveau, tardif=False):
    inscrit = HORLOGE_DEMO.astimezone(UTC) - timedelta(days=1) if tardif else INSCRIPTION
    return Grimpeur(id_, pseudo, classe, diff, statut, niveau, inscrit)


# Les grimpeurs fictifs de la maquette.
GRIMPEURS = (
    _g(1, "Brindille", "Eniripsa", "hard", "actif", 20),
    _g(2, "Kaskarot", "Iop", "easy", "actif", 20),
    _g(3, "Mirelune", "Crâ", "med", "actif", 19),
    _g(4, "Torvald", "Sacrieur", "med", "actif", 20),
    _g(5, "Pépin-Lagrume", "Enutrof", "easy", "actif", 17),
    _g(6, "Sélénith", "Xélor", "hard", "actif", 20),
    _g(7, "Gromolo", "Pandawa", "easy", "actif", 20),
    _g(8, "Ombrevive", "Sram", "med", "actif", 22),
    _g(9, "Fleur-de-Bwork", "Sadida", "easy", "pause", 14, tardif=True),  # arrivée hier : en pause par défaut
    _g(10, "Cliquetis", "Steamer", "hard", "actif", 20),
    _g(11, "Nalouette", "Osamodas", "easy", "actif", 20),
    _g(12, "Vieux-Grain", "Féca", "med", "pause", 11),
    _g(13, "Fourbenoire", "Roublard", "easy", "exclu", 20),  # exclu : n'apparaît nulle part
)

# Séances : (heures avant l'horloge de démo, contenus, [(grimpeur, niveau ou None)], annulée ?)
# Niveau None = déclaration de quêtes par le joueur.
TOUS_LES_SUCCES = (1, 2, 3, 4, 5)
SEANCES = [
    (190, TOUS_LES_SUCCES, [(1, 20), (6, 20), (3, 19)], False),
    (160, (1,), [(2, 20), (7, 20), (11, 20)], False),
    (150, (2, 3, 4, 5), [(11, 20)], False),
    (120, (1,), [(4, 20), (10, 20)], False),
    (100, (1,), [(13, 20)], False),  # l'exclu : entrée masquée du fil
    (96, (6,), [(1, None)], False),
    (40, (1,), [(5, 17)], True),  # saisie par erreur puis annulée : absente du fil et de la jauge
    (2, (6,), [(10, None)], False),  # guide sans full succès : marque Quêtes, mais 1 point
]


def instantane_demo() -> Instantane:
    validations: list[Validation] = []
    journal: list[EntreeJournal] = []
    for n, (heures, contenus, groupe, annulee) in enumerate(SEANCES, start=1):
        quand = (HORLOGE_DEMO - timedelta(hours=heures)).astimezone(UTC)
        for contenu_id in contenus:
            nom = next(c.nom_court for c in CONTENUS if c.id == contenu_id)
            lignes = []
            for grimpeur_id, niveau in groupe:
                vid = len(validations) + 1
                source = "declaration" if niveau is None else "manuelle"
                validations.append(Validation(vid, grimpeur_id, contenu_id, niveau,
                                              "annulee" if annulee else "acceptee", False, source, quand))
                lignes.append({"id": vid, "grimpeur_id": grimpeur_id, "niveau": niveau, "contenu": nom})
            type_ = "declaration" if groupe[0][1] is None else "validation"
            journal.append(EntreeJournal(n * 10 + contenu_id, quand, type_, True, None, {"validations": lignes}))
    journal.sort(key=lambda e: e.horodatage, reverse=True)
    return Instantane((ETAGE0,), PALIERS, CONTENUS, GRIMPEURS, tuple(validations), tuple(journal))


class SourceDemo:
    """Même interface que le dépôt (`charger_instantane`, `ping`), mais en mémoire."""

    async def charger_instantane(self) -> Instantane:
        return instantane_demo()

    async def ping(self) -> bool:
        return True


def creer_app_demo():
    # discord_connecte → False : il n'y a pas de bot en démo, /sante le dit honnêtement (503).
    return creer_app(SourceDemo(), discord_connecte=lambda: False, horloge=lambda: HORLOGE_DEMO, demo=True)


def main() -> None:  # pragma: no cover — lance un serveur
    parser = argparse.ArgumentParser(description="Site de démonstration, données fictives.")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    print(f"Démo : http://127.0.0.1:{args.port}  (données fictives, Ctrl+C pour arrêter)")
    uvicorn.run(creer_app_demo(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":  # pragma: no cover
    main()
