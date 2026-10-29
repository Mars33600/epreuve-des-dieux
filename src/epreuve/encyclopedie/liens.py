"""Les liens vers l'encyclopédie : un nom cité sur le site devient un vrai lien `<a href>` vers sa fiche.

Règle d'or : jamais de lien approximatif. Un nom ne mène à une fiche que si, une fois normalisé (`cle_recherche` :
minuscules, sans accents ni ponctuation), il correspond à UNE SEULE fiche du genre demandé. Deux fiches de même
nom, ou aucune : pas de lien, le nom reste du texte. Quand la source donne un identifiant (DofusDB), on le préfère
au nom, à condition que la fiche existe bien en base.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from epreuve.encyclopedie.textes import cle_recherche

CHEMINS = {"objet": "objets", "monstre": "monstres", "pnj": "pnj", "panoplie": "panoplies", "sort": "sorts"}


@dataclass(frozen=True)
class Liens:
    """Les correspondances déjà résolues pour une page. `par_nom` : (genre, clé de recherche) → identifiant,
    seulement pour les noms sans ambiguïté ; `existants` : (genre, identifiant) des fiches connues."""

    par_nom: Mapping[tuple[str, str], int] = field(default_factory=dict)
    existants: frozenset[tuple[str, int]] = frozenset()

    def url(self, nom: str | None, genres: Iterable[str] | str = ("objet",), ident: int | None = None) -> str | None:
        """L'adresse de la fiche, ou None quand la correspondance n'est pas sûre."""
        for genre in (genres,) if isinstance(genres, str) else genres:
            if ident is not None and (genre, ident) in self.existants:
                return f"/encyclopedie/{CHEMINS[genre]}/{ident}"
            trouve = self.par_nom.get((genre, cle_recherche(nom))) if nom else None
            if trouve is not None:
                return f"/encyclopedie/{CHEMINS[genre]}/{trouve}"
        return None


def decouper_quantite(texte: str) -> tuple[str, str]:
    """« 5 × Queue de Chapardam » → (« 5 × », « Queue de Chapardam »). Sans quantité : ("", texte)."""
    m = re.match(r"^(\d[\d  .]*\s*[×x]\s*)(.+)$", texte.strip())
    return (m.group(1), m.group(2)) if m else ("", texte)


def noms_de_fiche(fiche) -> list[str]:
    """Tous les noms d'une fiche de quête qui peuvent mener à l'encyclopédie (récompenses, besoins, étapes)."""
    noms = [decouper_quantite(r)[1] for r in fiche.recompenses]
    if fiche.pnj_depart:
        noms.append(fiche.pnj_depart)
    noms += [b.nom for b in (*fiche.objets, *fiche.monstres)]
    noms += [ligne.nom for e in fiche.etapes for ligne in e.lignes if ligne.nom]
    return noms
