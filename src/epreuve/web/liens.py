"""Les liens d'encyclopédie d'une page : on collecte les noms cités, une requête par genre les résout.

Sans base (teaser, tests sans Postgres) ou sans encyclopédie branchée : `Liens` vide, aucun lien, aucune erreur.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import Request

from epreuve.domaine.visibilite import etages_visibles
from epreuve.encyclopedie.liens import Liens


async def liens_pour(request: Request, noms: Iterable[str] = (), est_admin: bool = False,
                     **ids: Iterable[int]) -> Liens:
    s = request.app.state
    ency = getattr(s, "ency", None)
    if ency is None or s.depot is None:
        return Liens()
    plafond = None
    if s.regles.verrouiller_modules_par_etage and not est_admin:
        visibles = etages_visibles(await s.depot.etages(), False)
        plafond = max((e.level_cap for e in visibles), default=0)
    return await ency.liens(noms, plafond, **ids)
