"""Le rendu des gabarits : un contexte commun à toutes les pages (visiteur, mode, jeton CSRF…).

Jinja échappe tout par défaut. Le seul HTML inséré tel quel est le texte des étapes d'une fiche
de quête, déjà nettoyé par liste blanche à la construction de l'étage (`nettoyer_fiche`, B1). Le filtre
`fiche_propre` le renettoie au rendu avec la même liste blanche (défense en profondeur : une ligne
écrite en base par un autre chemin ne devient jamais du script), en ne gardant que nos liens de fiche.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import nh3
from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from epreuve.contenu.fiche_duffus import BALISES
from epreuve.domaine.textes import date_paris
from epreuve.encyclopedie.liens import Liens, decouper_quantite
from epreuve.web.vues import (
    INFOS_CATEGORIES,
    avec_article,
    cle,
    pct,
    pct1,
    texte_point_donjons,
    texte_point_full,
    titre_etage,
)

ICI = Path(__file__).parent
PARIS = ZoneInfo("Europe/Paris")
_LIEN_FICHE = re.compile(r"^/etages/\d+/quetes/\d+$")


def _lien_interne(balise: str, attribut: str, valeur: str) -> str | None:
    if balise == "a" and attribut == "href":
        return valeur if _LIEN_FICHE.match(valeur) else None
    return None


def fiche_propre(html: str | None) -> Markup:
    """Le texte d'une étape, renettoyé : liste blanche de `nettoyer_fiche`, liens limités à nos fiches."""
    return Markup(nh3.clean(html or "", tags=BALISES, clean_content_tags={"script", "style", "svg", "button"},  # noqa: S704
                            attributes={"a": {"href"}}, attribute_filter=_lien_interne, link_rel=None,
                            url_schemes=set()))


def heure_paris(d: datetime | None) -> str:
    return d.astimezone(PARIS).strftime("%d/%m/%Y %H:%M") if d else "—"


def creer_gabarits() -> Jinja2Templates:
    g = Jinja2Templates(directory=ICI / "templates")
    g.env.filters.update(pct=pct, pct1=pct1, cle=cle, date_paris=date_paris, heure_paris=heure_paris,
                         fiche_propre=fiche_propre)
    g.env.globals.update(CATS=INFOS_CATEGORIES, texte_donjons=texte_point_donjons, texte_full=texte_point_full,
                         titre_etage=titre_etage, avec_article=avec_article, decouper_quantite=decouper_quantite, LIENS_VIDES=Liens())
    return g


async def rendre(request: Request, gabarit: str, contexte: dict | None = None, statut: int = 200):
    from epreuve.web.auth import mode, visiteur

    s = request.app.state
    v = await visiteur(request)
    numero_ouvert = ambiance = None
    if v.connecte and s.depot is not None:
        ouvert = next((e for e in await s.depot.etages() if e.statut == "ouvert"), None)
        # Photo de fond de chaque page : l'étage en cours, jamais un étage scellé. Une page d'étage peut
        # imposer la sienne (`ambiance` dans son contexte, après contrôle de visibilité).
        numero_ouvert, ambiance = (ouvert.numero, ouvert.ambiance_url) if ouvert else (None, None)
    base = {"v": v, "mode": mode(request), "regles": s.regles, "ouverture_iso": s.config.site_ouvert_le.isoformat(),
            "chemin": request.url.path, "numero_ouvert": numero_ouvert, "ambiance": ambiance}
    base.update(contexte or {})
    return s.gabarits.TemplateResponse(request, gabarit, base, status_code=statut,
                                       headers={"Cache-Control": "no-store"})
