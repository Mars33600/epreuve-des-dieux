"""Le builder dans le site : connexion requise, CSP sans script en ligne, pied de page, API de recherche."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from epreuve.config import Config
from epreuve.web.app import creer_app
from epreuve.web.builder import ServicesBuilder, Visiteur, identifier_par_session

APRES = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
MOI = Visiteur(discord_id=11, est_admin=False, csrf="jeton-csrf", grimpeur_id=1, pseudo="Brindille")


def client(visiteur: Visiteur | None = MOI, mode: str = "ouvert", builds=None) -> TestClient:
    app = creer_app(Config(_env_file=None, SITE_MODE=mode), horloge=lambda: APRES)

    async def identifier(_request):
        return visiteur

    app.state.builder = ServicesBuilder(identifier, builds=builds)
    return TestClient(app, follow_redirects=False, raise_server_exceptions=False)


@pytest.mark.parametrize("chemin", ["/builder", "/builder/nouveau"])
def test_pages_sur_connexion_seulement(chemin):
    r = client(None).get(chemin)
    assert r.status_code == 303 and r.headers["location"] == "/"
    r = client().get(chemin)
    assert r.status_code == 200


def test_api_sur_connexion_seulement():
    r = client(None).get("/api/builder/objets", params={"emplacement": "coiffe"})
    assert r.status_code == 401 and r.json()["ok"] is False


def test_ferme_pendant_le_teaser():
    r = client(MOI, mode="teaser").get("/builder")
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert client(MOI, mode="teaser").get("/api/builder/objets?emplacement=coiffe").status_code == 404


def test_page_csp_sans_script_en_ligne_et_merci_duffus():
    r = client().get("/builder/nouveau")
    assert "'unsafe-inline'" not in r.headers["content-security-policy"]
    html = r.text
    for balise in re.findall(r"<script[^>]*>", html):
        assert 'src="/static/builder/builder.js"' in balise or 'type="application/json"' in balise
    assert " on" not in " ".join(re.findall(r"<[^>]+ on[a-z]+=", html))  # aucun gestionnaire en ligne
    assert "style=" not in html
    assert "Merci Duffus" in html and 'href="https://duffus.fr"' in html
    assert '<meta name="color-scheme" content="dark">' in html


def test_statiques_liste_fermee():
    c = client(None)  # les statiques ne contiennent rien de privé
    assert c.get("/static/builder/builder.js").status_code == 200
    assert c.get("/static/builder/builder.css").headers["content-type"].startswith("text/css")
    assert c.get("/static/builder/..%2fapp.py").status_code == 404
    assert c.get("/static/builder/autre.js").status_code == 404


def test_recherche_objets():
    r = client().get("/api/builder/objets", params={"emplacement": "coiffe", "q": "bouftou", "niveau_max": 20})
    assert r.status_code == 200
    d = r.json()
    coiffe = next(o for o in d["objets"] if o["id"] == 2411)
    assert coiffe["nom"] == "Coiffe du Bouftou" and coiffe["niveau"] == 20
    assert coiffe["icone"] == "https://api.dofusdb.fr/img/items/16041.png"
    assert coiffe["caracs"] == [["Force", 20], ["Intelligence", 20]]


def test_recherche_filtres_types_caracs_pagination():
    c = client()
    d = c.get("/api/builder/objets", params=[("emplacement", "arme"), ("type", "7"), ("carac", "Force")]).json()
    assert d["total"] > 0 and all(o["type"] == 7 for o in d["objets"])
    tous = c.get("/api/builder/objets", params={"emplacement": "anneau2"}).json()
    suite = c.get("/api/builder/objets", params={"emplacement": "anneau2", "decalage": 60}).json()
    assert tous["total"] == suite["total"] > 60
    assert not {o["id"] for o in tous["objets"]} & {o["id"] for o in suite["objets"]}


@pytest.mark.parametrize("params", [
    {"emplacement": "chapeau"}, {"emplacement": "coiffe", "carac": "Mana"}, {"emplacement": "coiffe", "decalage": -1},
    {"emplacement": "coiffe", "q": "x" * 101}, {"emplacement": "coiffe", "niveau_min": "abc"},
])  # fmt: skip
def test_recherche_refuse_les_filtres_invalides(params):
    assert client().get("/api/builder/objets", params=params).status_code == 422


# --- Identification par la session du lot B -------------------------------------------------------------------


@dataclass
class FausseSession:
    discord_user_id: int
    est_admin: bool
    csrf: str = "c"


@dataclass
class FauxGrimpeur:
    id: int
    pseudo: str
    statut: str = "actif"


class FauxDepot:
    def __init__(self, sessions, grimpeurs):
        self.sessions, self.grimpeurs = sessions, grimpeurs

    async def session(self, id_hache, maintenant):
        return self.sessions.get(id_hache)

    async def grimpeur_par_discord(self, discord_id):
        return self.grimpeurs.get(discord_id)


class Requete:
    def __init__(self, cookies):
        self.cookies = cookies


def _h(jeton):
    return hashlib.sha256(jeton.encode()).digest()


async def test_identifier_par_session():
    depot = FauxDepot({_h("a"): FausseSession(1, False), _h("b"): FausseSession(2, True),
                       _h("c"): FausseSession(3, False), _h("d"): FausseSession(4, True)},
                      {1: FauxGrimpeur(10, "Mirelune"), 3: FauxGrimpeur(30, "X", "exclu"),
                       4: FauxGrimpeur(40, "Y", "exclu")})
    ident = identifier_par_session(depot, lambda: APRES)
    v = await ident(Requete({"__Host-session": "a"}))
    assert (v.grimpeur_id, v.pseudo, v.est_admin) == (10, "Mirelune", False)
    v = await ident(Requete({"__Host-session": "b"}))
    assert v.grimpeur_id is None and v.est_admin  # admin sans fiche : il entre, sans pouvoir enregistrer
    assert await ident(Requete({"__Host-session": "c"})) is None  # grimpeur exclu
    v = await ident(Requete({"__Host-session": "d"}))
    assert v.est_admin and v.grimpeur_id is None
    assert await ident(Requete({"__Host-session": "inconnu"})) is None
    assert await ident(Requete({})) is None
    assert await identifier_par_session(None)(Requete({"__Host-session": "a"})) is None
