"""La recherche globale du site (barre de l'en-tête sur toutes les pages, page « voir tout »).

    GET /api/recherche?q=…[&limite=5][&type=monstres]   suggestions groupées par type, en JSON
    GET /recherche?q=…[&type=monstres]                   la page complète (avec « voir tout » pour un type)

Réservé aux grimpeurs (comme l'encyclopédie). Le brouillard de guerre est appliqué dans la requête SQL
(`epreuve.recherche`) : aucun quête ni donjon d'un étage scellé pour un non-admin.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request

from epreuve.domaine.visibilite import etages_visibles
from epreuve.recherche import LIBELLES, DepotRecherche, mots_de
from epreuve.web.auth import Refus, Visiteur, exiger_grimpeur
from epreuve.web.outils import OUTILS
from epreuve.web.rendu import rendre

routeur = APIRouter()
LIMITE_PAGE = 12
LIMITE_UN_TYPE = 100


def _depot_recherche(request: Request) -> DepotRecherche:
    s = request.app.state
    if getattr(s, "depot_recherche", None) is None:
        if s.depot is None:
            raise Refus(503, "La base n'est pas disponible.")
        s.depot_recherche = DepotRecherche(s.depot.moteur, tuple((o.chemin, o.nom, o.resume) for o in OUTILS))
    return s.depot_recherche


async def _plafond(request: Request, v: Visiteur) -> int | None:
    """Même règle que l'encyclopédie : avec le verrouillage par étage, rien au-dessus du dernier étage visible."""
    s = request.app.state
    if not s.regles.verrouiller_modules_par_etage or v.est_admin:
        return None
    visibles = etages_visibles(await s.depot.etages(), False)
    return max((e.level_cap for e in visibles), default=0)


def _voir_tout(q: str, type_: str) -> str:
    return f"/recherche?q={quote(q)}&type={type_}"


@routeur.get("/api/recherche")
async def api_recherche(request: Request, q: str = "", limite: int = 5, type: str = ""):  # noqa: A002
    v = await exiger_grimpeur(request)
    types = (type,) if type in LIBELLES else None
    groupes = await _depot_recherche(request).chercher(
        q, est_admin=v.est_admin, plafond=await _plafond(request, v), limite=max(1, min(limite, 50)), types=types)
    return {"q": q, "groupes": [
        {"type": g.type, "libelle": g.libelle, "plus": g.plus, "voir_tout": _voir_tout(q, g.type),
         "resultats": [{"nom": r.nom, "lien": r.lien, "detail": r.detail} for r in g.resultats]}
        for g in groupes]}


@routeur.get("/recherche")
async def page_recherche(request: Request, q: str = "", type: str = ""):  # noqa: A002
    v = await exiger_grimpeur(request)
    unique = type if type in LIBELLES else None
    groupes = []
    if mots_de(q):
        groupes = await _depot_recherche(request).chercher(
            q, est_admin=v.est_admin, plafond=await _plafond(request, v),
            limite=LIMITE_UN_TYPE if unique else LIMITE_PAGE, types=(unique,) if unique else None)
    return await rendre(request, "recherche.html", {
        "q": q, "groupes": groupes, "unique": unique, "libelle_unique": LIBELLES.get(unique or ""),
        "voir_tout": lambda t: _voir_tout(q, t)})
