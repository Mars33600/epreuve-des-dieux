"""Le site public : une page, une API JSON en lecture seule, une sonde de santé.

    GET /           la page (gabarit Jinja + style.css + app.js tirés de la maquette)
    GET /api/etat   tout l'état affiché, en JSON (contrat figé dans docs/LOTS.md)
    GET /sante      {"discord": "ok"|"ko", "base": "ok"|"ko"}, code 200 ou 503

Le site ne sait pas d'où viennent les données : il reçoit une « source » qui sait
`charger_instantane()` et `ping()`. En production c'est le dépôt (Postgres) ; pour la démo
locale, un jeu de données en mémoire (voir `demo.py`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from epreuve.domaine.classes import repartition_classes
from epreuve.domaine.inclusion import est_retardataire
from epreuve.domaine.jauges import calculer_etat_etage, marques_grimpeur, points_grimpeur
from epreuve.domaine.modeles import Instantane, phrase_validation
from epreuve.domaine.seuil import POINTS_VISES

journal = logging.getLogger("epreuve.web")
ICI = Path(__file__).parent
TAILLE_FIL = 30
RANGS = (1, 2, 3)
MESSAGE_INDISPONIBLE = "Les données sont momentanément indisponibles. Réessaie dans une minute."


class SourceEtat(Protocol):
    async def charger_instantane(self) -> Instantane: ...
    async def ping(self) -> bool: ...


def _iso(d: datetime | None, fuseau: ZoneInfo) -> str | None:
    """ISO 8601 avec le décalage de Paris : « 2026-10-31T00:00:00+01:00 »."""
    return d.astimezone(fuseau).replace(microsecond=0).isoformat() if d else None


def construire_etat(inst: Instantane, maintenant: datetime, fuseau: ZoneInfo) -> dict:
    """Transforme l'instantané en JSON de `/api/etat`. Fonction pure : facile à tester.

    Garanties : aucun exclu, aucun identifiant Discord, aucune date d'activité, aucun nom
    d'étage scellé.
    """
    visibles = [g for g in inst.grimpeurs if g.statut != "exclu"]
    pseudos = {g.id: g.pseudo for g in visibles}
    etage = inst.etage_ouvert

    # --- La tour : les étages connus, plus un étage scellé au-dessus du dernier.
    tour = [{"numero": e.numero, "nom": None if e.statut == "scelle" else e.nom, "statut": e.statut}
            for e in inst.etages]
    if not tour or tour[-1]["statut"] != "scelle":
        tour.append({"numero": (tour[-1]["numero"] + 1) if tour else 0, "nom": None, "statut": "scelle"})
    etage0 = next((e for e in inst.etages if e.numero == 0), None)

    # --- L'étage en cours et sa jauge, calculées par le domaine.
    courant = None
    if etage:
        etat = calculer_etat_etage(etage, inst.paliers, inst.grimpeurs, inst.validations, maintenant)
        libelles = {p.rang: p.libelle for p in inst.paliers}
        j = etat.jauge
        courant = {
            "numero": etage.numero, "nom": etage.nom, "level_cap": etage.level_cap,
            "seuil_pourcent": etage.seuil_pourcent, "donjons": list(etage.donjons_affiches),
            "zone_quetes": etage.zone_quetes, "ouvert_le": _iso(etage.ouvert_le, fuseau),
            "date_plancher_suivant": _iso(etage.date_plancher_suivant, fuseau),
            "n_comptes": etat.n_comptes, "n_pause": etat.n_pause, "n_retardataires": etat.n_retardataires,
            "jauge": {"points": j.points, "maximum": j.maximum, "seuil": j.seuil, "pleine": j.pleine},
            "comptes_par_difficulte": dict(etat.comptes_par_difficulte),
            "paliers": [{"rang": rang, "libelle": libelles.get(rang, f"Palier {rang}"), "grimpeurs": n}
                        for rang, n in zip(RANGS, etat.grimpeurs_par_palier, strict=True)],
            "deblocable": etat.deblocable,
        }  # fmt: skip

    # --- Les grimpeurs : actifs d'abord, puis ordre alphabétique. Pas de tri par score.
    def cle_tri(g):
        return (g.statut != "actif", g.pseudo.casefold())

    grimpeurs = []
    for g in sorted(visibles, key=cle_tri):
        au_dessus = bool(etage and g.niveau_connu is not None and g.niveau_connu > etage.level_cap)
        marques = marques_grimpeur(g, inst.paliers, inst.validations, etage) if etage else {}
        points = points_grimpeur(g, inst.paliers, inst.validations, etage) if etage and g.statut == "actif" else 0
        grimpeurs.append({
            "id": g.id, "pseudo": g.pseudo, "classe": g.classe, "difficulte": g.difficulte,
            "statut": g.statut, "retardataire": est_retardataire(g), "niveau": g.niveau_connu,
            "au_dessus_du_cap": au_dessus, "points": points, "points_vises": POINTS_VISES[g.difficulte],
            "marques": {str(rang): bool(marques.get(rang)) for rang in RANGS},
        })  # fmt: skip

    return {
        "genere_le": _iso(maintenant, fuseau),
        "ouverture_etage0": _iso(etage0.ouvert_le if etage0 else None, fuseau),
        "tour": tour,
        "etage_courant": courant,
        "classes": [{"classe": r.classe, "actifs": r.actifs, "en_pause": r.en_pause}
                    for r in repartition_classes(inst.grimpeurs)],
        "grimpeurs": grimpeurs,
        "fil": construire_fil(inst, pseudos, fuseau),
    }


def construire_fil(inst: Instantane, pseudos: dict[int, str], fuseau: ZoneInfo) -> list[dict]:
    """Les 30 dernières validations et déclarations publiques. Jamais de refus.

    Une entrée ne montre que les grimpeurs dont la validation est TOUJOURS acceptée et qui ne sont
    pas exclus : une annulation ou une exclusion se reflète dans le fil, sans rien effacer du
    journal. Les pseudos sont ceux d'aujourd'hui (un changement de pseudo suit).
    """
    statuts = {v.id: v.statut for v in inst.validations}
    fil = []
    for entree in inst.journal_public:
        if entree.type not in ("validation", "declaration"):
            continue
        restants = [v for v in entree.details.get("validations", [])
                    if statuts.get(v["id"]) == "acceptee" and v["grimpeur_id"] in pseudos]
        if not restants:
            continue
        noms_grimpeurs = list(dict.fromkeys(pseudos[v["grimpeur_id"]] for v in restants))
        contenus = list(dict.fromkeys(v["contenu"] for v in restants))
        fil.append({
            "horodatage": _iso(entree.horodatage, fuseau),
            "pseudos": noms_grimpeurs,
            "texte": phrase_validation(len(noms_grimpeurs), contenus, [v["niveau"] for v in restants]),
        })  # fmt: skip
        if len(fil) == TAILLE_FIL:
            break
    return fil


def creer_app(source: SourceEtat, discord_connecte: Callable[[], bool], fuseau: str = "Europe/Paris",
              horloge: Callable[[], datetime] = lambda: datetime.now(UTC), demo: bool = False) -> FastAPI:
    """Fabrique l'application. `horloge` est injectable : la démo et les tests simulent la date."""
    zone = ZoneInfo(fuseau)
    app = FastAPI(title="L'Épreuve des Dieux", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=ICI / "static"), name="static")
    gabarits = Jinja2Templates(directory=ICI / "templates")
    dernier_etat: dict = {}  # le dernier état calculé avec succès, servi si la base tombe

    def maintenant(request: Request) -> datetime:
        # En démo seulement, `?horloge=2026-11-16T00:00` simule une autre date (critère 10).
        if demo and (h := request.query_params.get("horloge")):
            try:
                d = datetime.fromisoformat(h)
                return d if d.tzinfo else d.replace(tzinfo=zone)
            except ValueError:
                pass
        return horloge()

    async def etat_courant(request: Request) -> tuple[dict | None, bool]:
        """(état, périmé ?). Si la base est injoignable, on ressert le dernier état connu."""
        try:
            etat = construire_etat(await source.charger_instantane(), maintenant(request), zone)
        except Exception:
            journal.exception("lecture de l'état impossible")
            return (dernier_etat.get("etat"), True)
        dernier_etat["etat"] = etat
        return etat, False

    @app.exception_handler(Exception)
    async def _erreur(_request: Request, exc: Exception) -> JSONResponse:
        # Jamais de trace de pile vers le visiteur : elle part dans les journaux du serveur.
        journal.error("erreur non prévue : %r", exc)
        return JSONResponse({"erreur": MESSAGE_INDISPONIBLE}, status_code=500)

    @app.get("/", response_class=HTMLResponse)
    async def page(request: Request):
        etat, perime = await etat_courant(request)
        return gabarits.TemplateResponse(request, "index.html", {
            "etat": etat, "perime": perime, "demo": demo,
            "horloge": _iso(maintenant(request), zone) if demo else None,
        })  # fmt: skip

    @app.get("/api/etat")
    async def api_etat(request: Request):
        etat, perime = await etat_courant(request)
        if etat is None:
            return JSONResponse({"erreur": MESSAGE_INDISPONIBLE}, status_code=503,
                                headers={"Cache-Control": "no-store"})
        entetes = {"Cache-Control": "max-age=30"}
        if perime:
            entetes["X-Etat-Perime"] = "1"  # le navigateur affiche « dernier état connu »
        return JSONResponse(etat, headers=entetes)

    @app.get("/sante")
    async def sante():
        corps = {"discord": "ok" if discord_connecte() else "ko", "base": "ok" if await source.ping() else "ko"}
        code = 200 if corps == {"discord": "ok", "base": "ok"} else 503
        return JSONResponse(corps, status_code=code, headers={"Cache-Control": "no-store"})

    return app
