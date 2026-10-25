"""Les contrôles d'une validation : statut du grimpeur, doublon, date, cap de niveau.

Deux fonctions, deux moments :
- `controler_validation` : AVANT d'écrire. Elle sépare les motifs **bloquants** (rien n'est écrit)
  des **avertissements** que l'admin tranche : le dépassement de cap (Shadoaze, Q9 : pas de marge,
  mais une tolérance au cas par cas pour un dépassement involontaire) ;
- `validation_compte` : APRÈS, pour savoir si une validation enregistrée rapporte des points.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from epreuve.domaine.modeles import TYPES_QUETES, Contenu, Etage, Grimpeur, Validation

NIVEAU_MIN, NIVEAU_MAX = 1, 200

# Les motifs sont des constantes : le bot et les tests les comparent tels quels.
MOTIF_PAUSE = "grimpeur en pause"
MOTIF_EXCLU = "grimpeur exclu"
MOTIF_HORS_ETAGE = "contenu hors de l'étage en cours"
MOTIF_ETAGE_FERME = "l'étage n'est pas ouvert"
MOTIF_AVANT_OUVERTURE = "réalisée avant l'ouverture de l'étage"
MOTIF_DEJA_VALIDE = "déjà validé"
MOTIF_NIVEAU_MANQUANT = "niveau manquant"
MOTIF_NON_INSCRIT = "membre non inscrit"  # utilisé par l'IA au jalon lancement


def motif_cap(niveau: int, etage: Etage) -> str:
    """« niveau 21 au-dessus du cap 20 »."""
    return f"niveau {niveau} au-dessus du cap {etage.level_cap}"


def motif_niveau_impossible(niveau: int) -> str:
    return f"niveau {niveau} impossible (entre {NIVEAU_MIN} et {NIVEAU_MAX})"


@dataclass(frozen=True)
class Controle:
    ok: bool  # vrai s'il n'y a aucun motif bloquant
    bloquants: tuple[str, ...]
    avertissements: tuple[str, ...]


def controler_validation(
    grimpeur: Grimpeur,
    contenu: Contenu,
    niveau: int | None,
    realisee_le: datetime,
    etage: Etage,
    deja_acceptee: bool,
) -> Controle:
    """Vérifie qu'une validation peut être enregistrée. Renvoie TOUS les motifs à la fois.

    `niveau=None` n'est permis que pour une quête ou un lot de quêtes (déclaration du joueur).
    """
    bloquants: list[str] = []
    avertissements: list[str] = []

    if grimpeur.statut == "pause":
        bloquants.append(MOTIF_PAUSE)
    elif grimpeur.statut == "exclu":
        bloquants.append(MOTIF_EXCLU)

    if contenu.etage_id != etage.id:
        bloquants.append(MOTIF_HORS_ETAGE)

    if etage.statut != "ouvert":
        bloquants.append(MOTIF_ETAGE_FERME)

    if etage.ouvert_le is None or realisee_le < etage.ouvert_le:
        bloquants.append(MOTIF_AVANT_OUVERTURE)

    if niveau is None:
        if contenu.type not in TYPES_QUETES:
            bloquants.append(MOTIF_NIVEAU_MANQUANT)
    elif not NIVEAU_MIN <= niveau <= NIVEAU_MAX:
        bloquants.append(motif_niveau_impossible(niveau))
    elif niveau > etage.level_cap:
        avertissements.append(motif_cap(niveau, etage))

    if deja_acceptee:
        bloquants.append(MOTIF_DEJA_VALIDE)

    return Controle(ok=not bloquants, bloquants=tuple(bloquants), avertissements=tuple(avertissements))


def validation_compte(v: Validation, etage: Etage) -> bool:
    """Vrai si la validation rapporte des points sur l'étage.

    Acceptée, réalisée après l'ouverture, et : sans niveau (déclaration), ou au plus au cap,
    ou acceptée malgré le dépassement par un admin (`forcee`).
    """
    if v.statut != "acceptee" or etage.ouvert_le is None:
        return False
    if v.realisee_le < etage.ouvert_le:
        return False
    return v.niveau is None or v.niveau <= etage.level_cap or v.forcee
