"""Le rendu des gabarits : un contexte commun à toutes les pages (visiteur, mode, jeton CSRF…).

Jinja échappe tout par défaut. Le seul HTML inséré tel quel est le texte des étapes d'une fiche
de quête, déjà nettoyé par liste blanche à la construction de l'étage (`nettoyer_fiche`, B1).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.templating import Jinja2Templates

from epreuve.domaine.textes import date_paris
from epreuve.web.vues import INFOS_CATEGORIES, cle, pct

ICI = Path(__file__).parent
PARIS = ZoneInfo("Europe/Paris")


def heure_paris(d: datetime | None) -> str:
    return d.astimezone(PARIS).strftime("%d/%m/%Y %H:%M") if d else "—"


def creer_gabarits() -> Jinja2Templates:
    g = Jinja2Templates(directory=ICI / "templates")
    g.env.filters.update(pct=pct, cle=cle, date_paris=date_paris, heure_paris=heure_paris)
    g.env.globals.update(CATS=INFOS_CATEGORIES)
    return g


async def rendre(request: Request, gabarit: str, contexte: dict | None = None, statut: int = 200):
    from epreuve.web.auth import mode, visiteur

    s = request.app.state
    v = await visiteur(request)
    numero_ouvert = None
    if v.connecte and s.depot is not None:
        numero_ouvert = next((e.numero for e in await s.depot.etages() if e.statut == "ouvert"), None)
    base = {"v": v, "mode": mode(request), "regles": s.regles, "ouverture_iso": s.config.site_ouvert_le.isoformat(),
            "chemin": request.url.path, "numero_ouvert": numero_ouvert}
    base.update(contexte or {})
    return s.gabarits.TemplateResponse(request, gabarit, base, status_code=statut,
                                       headers={"Cache-Control": "no-store"})
