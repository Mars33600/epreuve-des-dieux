"""Le builder dans le site : connexion requise, CSP sans script en ligne, pied de page, API de recherche."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from py_mini_racer import MiniRacer

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


# --- Calcul ---------------------------------------------------------------------------------------------------


def test_script_valide_pour_v8():
    source = (Path(__file__).resolve().parents[2] / "src/epreuve/web/static/builder/builder.js").read_text()
    MiniRacer().eval("new Function(" + json.dumps(source) + "); 1")  # analyse sans exécuter


def test_calcul_panoplie_du_bouftou():
    corps = {"niveau": 50, "objets": {"coiffe": 2411, "cape": 2414, "amulette": 2425, "ceinture": 2428,
                                      "bottes": 2422, "anneau1": 2419, "bouclier": 18666, "arme": 2416},
             "caracs_base": {"Force": 100, "Vitalité": 45, "Sagesse": 30},
             "caracs_parcho": {"Force": 100, "Intelligence": 50, "Vitalité": 100, "Agilité": 25}}
    d = client().post("/api/builder/calcul", json=corps).json()
    assert d["ok"] and d["totaux"]["Force"] == 300 and d["affichage"]["Vitalité"] == 640
    assert d["points"] == {"total": 245, "depenses": 235, "restants": 10}
    assert d["panoplies"][0]["nb"] == 8 and d["objets"]["coiffe"]["nom"] == "Coiffe du Bouftou"
    assert d["puissance"]["Force"] == 325 and d["alertes"] == {}


def test_calcul_refus():
    assert client(None).post("/api/builder/calcul", json={}).status_code == 401
    c = client()
    assert c.post("/api/builder/calcul", content=b"pas du json").status_code == 422
    assert c.post("/api/builder/calcul", json={"niveau": "x"}).status_code == 422
    assert c.post("/api/builder/calcul", json={"objets": {str(i): 1 for i in range(40)}}).status_code == 422
    assert c.post("/api/builder/calcul", json={}).json()["affichage"]["PA"] == 7  # build vierge, niveau 200


# --- Enregistrement et partage --------------------------------------------------------------------------------


class FauxBuilds:
    """Le dépôt des builds en mémoire (le vrai est testé contre Postgres dans test_depot.py)."""

    def __init__(self):
        from epreuve.builder.depot import BuildEnregistre

        self.Build = BuildEnregistre
        self.lignes: dict[int, object] = {}

    async def creer(self, grimpeur_id, contenu, maintenant):
        bid = len(self.lignes) + 1
        self.lignes[bid] = self.Build(bid, grimpeur_id, f"G{grimpeur_id}", contenu, maintenant)
        return bid

    async def modifier(self, bid, grimpeur_id, contenu, maintenant):
        b = self.lignes.get(bid)
        if b is None or b.grimpeur_id != grimpeur_id:
            return False
        self.lignes[bid] = self.Build(bid, grimpeur_id, b.auteur, contenu, maintenant)
        return True

    async def supprimer(self, bid, grimpeur_id):
        b = self.lignes.get(bid)
        if b is None or b.grimpeur_id != grimpeur_id:
            return False
        del self.lignes[bid]
        return True

    async def lire(self, bid):
        return self.lignes.get(bid)

    async def de_grimpeur(self, grimpeur_id):
        return [b for b in self.lignes.values() if b.grimpeur_id == grimpeur_id]

    async def sorts_de_classe(self, classe):
        from tests.builder.test_sorts import PRESSION

        return [PRESSION] if classe == "Iop" else []

    async def partages(self, sauf_grimpeur=None, limite=200):
        return [b for b in self.lignes.values() if b.contenu.partage and b.grimpeur_id != sauf_grimpeur]


AUTRE = Visiteur(discord_id=22, est_admin=False, csrf="autre-csrf", grimpeur_id=2, pseudo="Mirelune")
CORPS = {"nom": "Iop <b>terre</b>", "classe": "Iop", "niveau": 250, "objets": {"coiffe": 2411, "chapeau": 1},
         "caracs_base": {"Force": 100}, "caracs_parcho": {"Force": 300}, "note": "n", "partage": False}
CSRF = {"X-CSRF-Token": "jeton-csrf"}


def test_enregistrer_modifier_partager_supprimer():
    builds = FauxBuilds()
    moi, autre = client(MOI, builds=builds), client(AUTRE, builds=builds)
    r = moi.post("/api/builder/builds", json=CORPS, headers=CSRF)
    assert r.status_code == 201
    bid = r.json()["id"]
    c = builds.lignes[bid].contenu
    assert (c.nom, c.niveau, c.objets, c.caracs_parcho) == ("Iop <b>terre</b>", 200, {"coiffe": 2411}, {"Force": 100})
    page = moi.get(f"/builder/{bid}")
    assert page.status_code == 200 and "<b>terre</b>" not in page.text  # échappé, y compris dans le JSON
    assert autre.get(f"/builder/{bid}").status_code == 404  # privé
    assert "Iop &lt;b&gt;terre&lt;/b&gt;" in moi.get("/builder").text
    r = moi.put(f"/api/builder/builds/{bid}", json={**CORPS, "partage": True}, headers=CSRF)
    assert r.status_code == 200
    page = autre.get(f"/builder/{bid}")
    assert page.status_code == 200 and "lecture seule" in page.text and 'id="b-enregistrer"' not in page.text
    assert "G1" in autre.get("/builder").text  # dans « Partagés dans la guilde »
    assert autre.put(f"/api/builder/builds/{bid}", json=CORPS,
                     headers={"X-CSRF-Token": "autre-csrf"}).status_code == 404
    assert autre.delete(f"/api/builder/builds/{bid}", headers={"X-CSRF-Token": "autre-csrf"}).status_code == 404
    assert moi.delete(f"/api/builder/builds/{bid}", headers=CSRF).status_code == 200
    assert moi.get(f"/builder/{bid}").status_code == 404


def test_enregistrement_refus():
    builds = FauxBuilds()
    c = client(MOI, builds=builds)
    assert client(None, builds=builds).post("/api/builder/builds", json=CORPS, headers=CSRF).status_code == 401
    assert c.post("/api/builder/builds", json=CORPS).status_code == 403  # sans jeton
    assert c.post("/api/builder/builds", json=CORPS, headers={"X-CSRF-Token": "faux"}).status_code == 403
    assert c.post("/api/builder/builds", json=CORPS,
                  headers={**CSRF, "Origin": "https://ailleurs.example"}).status_code == 403
    assert c.post("/api/builder/builds", json={**CORPS, "classe": "Druide"}, headers=CSRF).status_code == 422
    assert c.post("/api/builder/builds", json={**CORPS, "nom": "  "}, headers=CSRF).status_code == 422
    assert c.post("/api/builder/builds", json={**CORPS, "note": "x" * 2001}, headers=CSRF).status_code == 422
    admin = Visiteur(discord_id=9, est_admin=True, csrf="a")
    assert client(admin, builds=builds).post("/api/builder/builds", json=CORPS,
                                             headers={"X-CSRF-Token": "a"}).status_code == 409  # pas de fiche
    assert c.put("/api/builder/builds/99", json=CORPS, headers=CSRF).status_code == 404
    assert client(MOI).post("/api/builder/builds", json=CORPS, headers=CSRF).status_code == 409  # sans base
    assert builds.lignes == {}


def test_page_liste_sans_base_et_build_introuvable():
    assert "Mes builds" not in client().get("/builder").text
    assert client().get("/builder/3").status_code == 404


# --- Duplication et comparaison -------------------------------------------------------------------------------


def test_dupliquer_un_build_partage_ou_a_soi():
    builds = FauxBuilds()
    moi, autre = client(MOI, builds=builds), client(AUTRE, builds=builds)
    bid = moi.post("/api/builder/builds", json=CORPS, headers=CSRF).json()["id"]
    ecrit = {"X-CSRF-Token": "autre-csrf"}
    assert autre.post(f"/api/builder/builds/{bid}/dupliquer", headers=ecrit).status_code == 404  # privé
    assert moi.post(f"/api/builder/builds/{bid}/dupliquer").status_code == 403  # sans jeton
    moi.put(f"/api/builder/builds/{bid}", json={**CORPS, "partage": True}, headers=CSRF)
    r = autre.post(f"/api/builder/builds/{bid}/dupliquer", headers=ecrit)
    assert r.status_code == 201
    copie = builds.lignes[r.json()["id"]]
    assert copie.grimpeur_id == 2 and copie.contenu.nom == "Copie de Iop <b>terre</b>"
    assert copie.contenu.partage is False and copie.contenu.objets == {"coiffe": 2411}
    assert 'id="b-dupliquer"' in autre.get(f"/builder/{bid}").text
    long = moi.post("/api/builder/builds", json={**CORPS, "nom": "x" * 80}, headers=CSRF).json()["id"]
    r = moi.post(f"/api/builder/builds/{long}/dupliquer", headers=CSRF)
    assert len(builds.lignes[r.json()["id"]].contenu.nom) == 80


def test_comparer_deux_builds():
    builds = FauxBuilds()
    moi = client(MOI, builds=builds)
    a = moi.post("/api/builder/builds", json={**CORPS, "nom": "Seul", "niveau": 50}, headers=CSRF).json()["id"]
    b = moi.post("/api/builder/builds", json={**CORPS, "nom": "Deux", "niveau": 50,
                                               "objets": {"coiffe": 2411, "cape": 2414}}, headers=CSRF).json()["id"]
    page = moi.get("/builder/comparer", params={"a": a, "b": b})
    assert page.status_code == 200
    html = page.text
    # Force : A = 20 + 100 + 100 = 220 ; B = 225 avec le bonus 2/8 du Bouftou. Vitalité : 300 (A), puis + 40 + 5.
    assert "<th scope=\"row\">Force</th><td>220</td><td>225</td>" in html and "▲ +5" in html
    assert "<th scope=\"row\">Vitalité</th><td>300</td><td>345</td>" in html
    assert "Panoplie du Bouftou" in html
    assert "<th scope=\"row\">Dommages</th>" not in html  # nulle des deux côtés : masquée
    autre = client(AUTRE, builds=builds).get("/builder/comparer", params={"a": a, "b": b})
    assert autre.status_code == 200 and "pas partagé" in autre.text and "Écarts" not in autre.text
    assert client(None, builds=builds).get("/builder/comparer").status_code == 303
    assert "Choisir un build" in moi.get("/builder/comparer").text


def test_calcul_arme_dans_l_api():
    corps = {"niveau": 50, "objets": {"arme": 2416}, "caracs_base": {"Intelligence": 50}, "mode_arme": "distance",
             "buff_arme": "base"}
    d = client().post("/api/builder/calcul", json=corps).json()
    feu = d["arme"]["lignes"][0]
    assert feu["libelle"] == "dommages Feu" and feu["normal"] == [18, 36]  # (300 + 50 + 100) / 100 × 4 et × 8
    assert client().post("/api/builder/calcul", json={"objets": {}}).json()["arme"] is None
    assert client().post("/api/builder/calcul", json={"mode_arme": "lancer"}).status_code == 422


def test_sorts_de_la_classe():
    corps = {"niveau": 200, "classe": "Iop", "caracs_base": {"Force": 100}}
    d = client(builds=FauxBuilds()).post("/api/builder/sorts", json=corps).json()
    [pression] = d["sorts"]
    assert pression["nom"] == "Pression" and pression["grade"] == 3
    assert pression["icone"] == "https://api.dofusdb.fr/img/spells/11830.png"
    assert pression["normal"][0]["jet"] == [52, 60]  # (100 + 100) / 100 × 26 et × 30
    feca = client(builds=FauxBuilds()).post("/api/builder/sorts", json={**corps, "classe": "Féca"}).json()
    assert feca["sorts"] == []
    assert client().post("/api/builder/sorts", json=corps).json()["sorts"] == []  # sans base
    assert client(builds=FauxBuilds()).post("/api/builder/sorts", json={"classe": "Druide"}).status_code == 422
    assert client(None).post("/api/builder/sorts", json=corps).status_code == 401
