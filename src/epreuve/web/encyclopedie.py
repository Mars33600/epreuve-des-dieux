"""Les pages du lot E2 : l'encyclopédie (objets, ressources, monstres, recettes) et les stuffs recommandés.

Toutes demandent une connexion (cookie `__Host-session`, ARCHITECTURE §8) et une fiche de grimpeur non
exclue, ou d'être admin (le sens de « grimpeur » d'ARCHITECTURE §9). Sans session : 303 vers `/connexion` ;
sans fiche : 303 vers `/inscription` ; exclu : 403.

Le brouillard (EX-111) : les stuffs sont rangés par étage, et seuls les étages visibles (`etages_visibles`)
entrent dans la page. La base ne renvoie aucun stuff au-dessus de la tranche du dernier étage visible, et un
stuff d'un étage scellé répond 404. L'encyclopédie, elle, est ouverte (données du jeu, T-08), sauf si
`modules.verrouiller_par_etage` est vrai : elle s'arrête alors au cap du dernier étage visible.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from epreuve.domaine.visibilite import etages_visibles
from epreuve.encyclopedie.depot import DepotEncyclopedie, Filtres
from epreuve.encyclopedie.textes import (
    EMPLACEMENTS,
    FAMILLES,
    METIERS,
    TRIS,
    TrancheVisible,
    etage_du_niveau,
)
from epreuve.regles import Regles, lire_regles

ICI = Path(__file__).parent
COOKIE_SESSION = "__Host-session"
ELEMENTS = ("Force", "Intelligence", "Chance", "Agilité")


class _Redirection(Exception):
    def __init__(self, cible: str) -> None:
        self.cible = cible


class Visiteur:
    """Ce que les pages savent de la personne connectée (jamais la session elle-même)."""

    def __init__(self, est_admin: bool, pseudo: str | None) -> None:
        self.est_admin, self.pseudo = est_admin, pseudo


def _entier(v: str | None, bas: int | None = None, haut: int | None = None) -> int | None:
    """Un paramètre d'URL en entier borné ; vide ou invalide → None (jamais d'erreur 422 sur une page)."""
    try:
        n = int((v or "").strip())
    except ValueError:
        return None
    if bas is not None:
        n = max(bas, n)
    if haut is not None:
        n = min(haut, n)
    return n


def _filtres(request: Request, **fixes) -> Filtres:
    p = request.query_params
    tri = p.get("tri", "recents")
    valeurs = {
        "q": (p.get("q") or "").strip()[:80] or None,
        "famille": p.get("famille") if p.get("famille") in FAMILLES else None,
        "type_id": _entier(p.get("type")), "race_id": _entier(p.get("race")), "metier": _entier(p.get("metier")),
        "classe_id": _entier(p.get("classe")),
        "niveau_min": _entier(p.get("nmin"), 1, 200), "niveau_max": _entier(p.get("nmax"), 1, 200),
        "tri": tri if tri in TRIS else "recents", "page": _entier(p.get("page"), 1, 10_000) or 1,
    }  # fmt: skip
    valeurs.update(fixes)
    return Filtres(**valeurs)


def _lien_page(request: Request, page: int) -> str:
    """Le même chemin et les mêmes filtres, à une autre page (lien relatif, sans hôte)."""
    u = request.url.include_query_params(page=page)
    return f"{u.path}?{u.query}"


def routeur_encyclopedie(depot, ency: DepotEncyclopedie, gabarits: Jinja2Templates,
                         horloge: Callable[[], datetime], regles: Regles) -> APIRouter:
    r = APIRouter()

    async def visiteur(request: Request) -> Visiteur:
        jeton = request.cookies.get(COOKIE_SESSION)
        if not jeton:
            raise _Redirection("/connexion")
        session = await depot.session(hashlib.sha256(jeton.encode()).digest(), horloge())
        if session is None:
            raise _Redirection("/connexion")
        grimpeur = await depot.grimpeur_par_discord(session.discord_user_id)
        if not session.est_admin:
            if grimpeur is None:
                raise _Redirection("/inscription")
            if grimpeur.statut == "exclu":
                raise HTTPException(403)
        return Visiteur(session.est_admin, grimpeur.pseudo if grimpeur else session.nom_discord)

    async def tranches(v: Visiteur) -> tuple[list[TrancheVisible], TrancheVisible | None]:
        """Les étages visibles, et l'étage en cours (sinon le plus haut visible)."""
        visibles = etages_visibles(await depot.etages(), v.est_admin)
        liste = [TrancheVisible(e.numero, e.nom, e.niveau_min, e.niveau_max) for e in visibles]
        ouvert = next((TrancheVisible(e.numero, e.nom, e.niveau_min, e.niveau_max)
                       for e in visibles if e.statut == "ouvert"), None)
        return liste, ouvert or (liste[-1] if liste else None)

    async def plafond(v: Visiteur) -> int | None:
        if not regles.verrouiller_modules_par_etage or v.est_admin:
            return None
        visibles = etages_visibles(await depot.etages(), False)
        return max((e.level_cap for e in visibles), default=0)

    def rendre(request: Request, gabarit: str, v: Visiteur, rubrique: str, **ctx) -> HTMLResponse:
        return gabarits.TemplateResponse(request, f"encyclopedie/{gabarit}", {
            "visiteur": v, "rubrique": rubrique, "familles": FAMILLES, "tris": TRIS, "metiers": METIERS, **ctx})

    @r.get("/encyclopedie", response_class=HTMLResponse)
    async def accueil(request: Request):
        v = await visiteur(request)
        f = _filtres(request)
        objets = monstres = None
        if f.q:
            p = await plafond(v)
            objets = await ency.chercher_objets(Filtres(q=f.q, tri="niveau_asc"), p)
            monstres = await ency.chercher_monstres(Filtres(q=f.q, tri="niveau_asc"), p)
        return rendre(request, "accueil.html", v, "accueil", f=f, objets=objets, monstres=monstres)

    async def liste_objets(request: Request, rubrique: str, **fixes):
        v = await visiteur(request)
        f = _filtres(request, **fixes)
        page = await ency.chercher_objets(f, await plafond(v))
        return rendre(request, "objets.html", v, rubrique, f=f, page=page, types=await ency.types_par_famille(),
                      lien_page=lambda n: _lien_page(request, n))

    @r.get("/encyclopedie/objets", response_class=HTMLResponse)
    async def objets(request: Request):
        return await liste_objets(request, "objets")

    @r.get("/encyclopedie/ressources", response_class=HTMLResponse)
    async def ressources(request: Request):
        return await liste_objets(request, "ressources", famille="ressources")

    @r.get("/encyclopedie/objets/{ident}", response_class=HTMLResponse)
    async def objet(request: Request, ident: int):
        v = await visiteur(request)
        fiche = await ency.objet(ident, await plafond(v))
        if fiche is None:
            raise HTTPException(404)
        rubrique = "ressources" if fiche["famille"] == "ressources" else "objets"
        return rendre(request, "objet.html", v, rubrique, o=fiche)

    @r.get("/encyclopedie/monstres", response_class=HTMLResponse)
    async def monstres(request: Request):
        v = await visiteur(request)
        f = _filtres(request)
        page = await ency.chercher_monstres(f, await plafond(v))
        return rendre(request, "monstres.html", v, "monstres", f=f, page=page, races=await ency.races(),
                      lien_page=lambda n: _lien_page(request, n))

    @r.get("/encyclopedie/monstres/{ident}", response_class=HTMLResponse)
    async def monstre(request: Request, ident: int):
        v = await visiteur(request)
        fiche = await ency.monstre(ident, await plafond(v))
        if fiche is None:
            raise HTTPException(404)
        return rendre(request, "monstre.html", v, "monstres", m=fiche)

    @r.get("/encyclopedie/recettes", response_class=HTMLResponse)
    async def recettes(request: Request):
        v = await visiteur(request)
        f = _filtres(request)
        page = await ency.chercher_recettes(f, await plafond(v))
        return rendre(request, "recettes.html", v, "recettes", f=f, page=page,
                      lien_page=lambda n: _lien_page(request, n))

    # --- Sorts, panoplies, PNJ, quêtes ---------------------------------------------------------------------

    @r.get("/encyclopedie/sorts", response_class=HTMLResponse)
    async def sorts(request: Request):
        v = await visiteur(request)
        f = _filtres(request)
        page = await ency.chercher_sorts(f, await plafond(v))
        return rendre(request, "sorts.html", v, "sorts", f=f, page=page, classes=await ency.classes(),
                      lien_page=lambda n: _lien_page(request, n))

    @r.get("/encyclopedie/sorts/{ident}", response_class=HTMLResponse)
    async def sort(request: Request, ident: int):
        v = await visiteur(request)
        fiche = await ency.sort(ident, await plafond(v))
        if fiche is None:
            raise HTTPException(404)
        return rendre(request, "sort.html", v, "sorts", s=fiche)

    @r.get("/encyclopedie/panoplies", response_class=HTMLResponse)
    async def panoplies(request: Request):
        v = await visiteur(request)
        f = _filtres(request)
        page = await ency.chercher_panoplies(f, await plafond(v))
        return rendre(request, "panoplies.html", v, "panoplies", f=f, page=page,
                      lien_page=lambda n: _lien_page(request, n))

    @r.get("/encyclopedie/panoplies/{ident}", response_class=HTMLResponse)
    async def panoplie(request: Request, ident: int):
        v = await visiteur(request)
        fiche = await ency.panoplie(ident, await plafond(v))
        if fiche is None:
            raise HTTPException(404)
        return rendre(request, "panoplie.html", v, "panoplies", p=fiche)

    @r.get("/encyclopedie/pnj", response_class=HTMLResponse)
    async def liste_pnj(request: Request):
        v = await visiteur(request)
        f = _filtres(request)
        page = await ency.chercher_pnj(f)
        return rendre(request, "pnj_liste.html", v, "pnj", f=f, page=page,
                      lien_page=lambda n: _lien_page(request, n))

    @r.get("/encyclopedie/pnj/{ident}", response_class=HTMLResponse)
    async def pnj(request: Request, ident: int):
        v = await visiteur(request)
        fiche = await ency.pnj(ident, await plafond(v))
        if fiche is None:
            raise HTTPException(404)
        return rendre(request, "pnj.html", v, "pnj", n=fiche)

    @r.get("/encyclopedie/quetes", response_class=HTMLResponse)
    async def quetes(request: Request):
        v = await visiteur(request)
        f = _filtres(request)
        page = await ency.chercher_quetes(f, await plafond(v))
        return rendre(request, "quetes.html", v, "quetes", f=f, page=page,
                      lien_page=lambda n: _lien_page(request, n))

    @r.get("/encyclopedie/quetes/{ident}", response_class=HTMLResponse)
    async def quete(request: Request, ident: int):
        v = await visiteur(request)
        fiche = await ency.quete(ident, await plafond(v))
        if fiche is None:
            raise HTTPException(404)
        return rendre(request, "quete.html", v, "quetes", q=fiche)

    # --- Stuffs recommandés, par étage --------------------------------------------------------------------

    async def stuffs_visibles(v: Visiteur) -> tuple[list[TrancheVisible], TrancheVisible | None, list[dict]]:
        liste, courant = await tranches(v)
        if not liste:
            return liste, None, []
        tous = await ency.stuffs(max(t.niveau_max for t in liste))
        for s in tous:
            s["etage"] = etage_du_niveau(s["niveau"], liste)
        return liste, courant, [s for s in tous if s["etage"] is not None]

    @r.get("/stuffs", response_class=HTMLResponse)
    async def stuffs(request: Request):
        v = await visiteur(request)
        liste, courant, tous = await stuffs_visibles(v)
        numero = _entier(request.query_params.get("etage"))
        choisi = next((t for t in liste if t.numero == numero), courant)
        classe = request.query_params.get("classe") or None
        element = request.query_params.get("element") or None
        de_l_etage = [s for s in tous if choisi and s["etage"] == choisi]
        classes = sorted({s["classe"] for s in de_l_etage if s["classe"]})
        retenus = [s for s in de_l_etage if (not classe or s["classe"] == classe)
                   and (element not in ELEMENTS or element in (s["tags"] or []))]
        objets = await ency.objets_de_stuffs(retenus)
        return rendre(request, "stuffs.html", v, "stuffs", tranches=liste, choisi=choisi, stuffs=retenus,
                      classes=classes, classe=classe, element=element if element in ELEMENTS else None,
                      elements=ELEMENTS, objets=objets, emplacements=EMPLACEMENTS)

    @r.get("/stuffs/{ident}", response_class=HTMLResponse)
    async def stuff(request: Request, ident: str):
        v = await visiteur(request)
        _liste, _courant, tous = await stuffs_visibles(v)
        s = next((x for x in tous if x["id"] == ident), None)
        if s is None:
            raise HTTPException(404)  # inconnu, ou d'un étage scellé : même réponse
        objets = await ency.objets_de_stuffs([s])
        return rendre(request, "stuff.html", v, "stuffs", s=s, objets=objets, emplacements=EMPLACEMENTS,
                      effets=await ency.effets_de(list(s["objets"].values())))

    return r


def brancher(app: FastAPI, source: object, gabarits: Jinja2Templates, horloge: Callable[[], datetime],
             regles: Regles | None = None) -> None:
    """Ajoute les statiques et, s'il y a une base, les pages du lot E2. Appelé par `creer_app`."""
    app.mount("/static/encyclopedie", StaticFiles(directory=ICI / "static" / "encyclopedie"), name="encyclopedie")
    from epreuve.db.depot import Depot

    if not isinstance(source, Depot):
        return
    regles = regles or lire_regles()
    ency = DepotEncyclopedie(source.moteur)
    app.include_router(routeur_encyclopedie(source, ency, gabarits, horloge, regles))

    @app.exception_handler(_Redirection)
    async def _rediriger(_request: Request, exc: _Redirection) -> RedirectResponse:
        return RedirectResponse(exc.cible, status_code=303)
