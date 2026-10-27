"""Le site du lot A : le teaser, le filtre du mode, les en-têtes de sécurité, /sante, la configuration.

Le TestClient de FastAPI appelle l'application directement, sans serveur réseau. L'horloge est
injectée : on simule la veille, l'instant et le lendemain de l'ouverture sans attendre le 13/11.
La configuration est construite sans lire `.env` (`_env_file=None`) : les tests ne dépendent pas
de la machine.
"""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from epreuve.config import Config
from epreuve.web.app import creer_app, jour_en_clair
from epreuve.web.securite import ENTETES_SECURITE, chemin_permis

STATIQUES = Path(__file__).resolve().parents[2] / "src/epreuve/web/static"
OUVERTURE = datetime(2026, 11, 13, 16, 0, tzinfo=UTC)  # 17:00 à Paris (heure d'hiver)
AVANT = datetime(2026, 11, 3, 20, 0, tzinfo=UTC)
APRES = OUVERTURE + timedelta(days=1)
# Les adresses du critère 6, plus quelques chemins que le lot B déclarera.
ADRESSES_FERMEES = ["/etages/0", "/grimpeurs", "/admin", "/api/etat", "/une-adresse-inventee", "/inscription",
                    "/grimpeurs/1", "/admin/journal", "/api/coches", "/static", "/sante/", "/index.html"]


def config(**reglages) -> Config:
    return Config(_env_file=None, **reglages)


def client(maintenant: datetime = AVANT, source=None, **reglages) -> TestClient:
    app = creer_app(config(**reglages), horloge=lambda: maintenant, source=source)
    return TestClient(app, follow_redirects=False, raise_server_exceptions=False)


class Source:
    def __init__(self, reponse):
        self.reponse = reponse

    async def ping(self) -> bool:
        if isinstance(self.reponse, Exception):
            raise self.reponse
        return self.reponse


# --- La page ------------------------------------------------------------------------------------------


def test_teaser_contrat_du_gabarit():
    r = client().get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    html = r.text
    assert 'data-ouverture="2026-11-13T17:00:00+01:00"' in html
    assert 'data-lien-site=""' in html  # vide par défaut : le bouton reste masqué
    # La date est écrite en clair dans le HTML : lisible sans JavaScript (critère 3).
    assert "<strong>Vendredi 13 novembre 2026 · 17 h 00</strong>, heure de Paris" in html
    assert '<script src="/static/teaser/teaser.js"></script>' in html
    assert '<link rel="stylesheet" href="/static/teaser/teaser.css">' in html
    assert 'id="opened" hidden' in html  # l'état « portes ouvertes » attend la fin du compte à rebours


def test_pied_de_page_mention_de_fans_et_merci_duffus():
    html = client().get("/").text
    pied = re.search(r"<footer>(.*?)</footer>", html, re.S).group(1)
    assert "Projet de fans, non officiel et sans lien avec Ankama" in pied
    assert '<a href="https://duffus.fr" rel="noopener">Merci Duffus</a>' in pied
    assert html.count("duffus.fr") == 1  # aucun autre lien vers Duffus (T-09)


@pytest.mark.parametrize("lien", ["https://epreuve.example/tour", 'https://x.example/"><script>alert(1)</script>'])
def test_lien_du_bouton_vient_de_la_configuration(lien):
    html = client(TEASER_LIEN_ENTRER=lien).get("/").text
    attendu = lien.replace('"', "&#34;").replace("<", "&lt;").replace(">", "&gt;")
    assert f'data-lien-site="{attendu}"' in html
    assert "<script>alert" not in html  # échappé par Jinja


def test_date_et_metas_suivent_site_ouvert_le():
    html = client(SITE_OUVERT_LE="2026-12-01T20:30:00+01:00").get("/").text
    assert 'data-ouverture="2026-12-01T20:30:00+01:00"' in html
    assert "<strong>Mardi 1er décembre 2026 · 20 h 30</strong>" in html
    assert "le mardi 1er décembre 2026 à 20 h 30, heure de Paris" in html


def test_date_en_clair_a_l_heure_de_paris_meme_ecrite_en_utc():
    html = client(SITE_OUVERT_LE="2026-11-13T16:00:00Z").get("/").text
    assert "<strong>Vendredi 13 novembre 2026 · 17 h 00</strong>" in html
    assert 'data-ouverture="2026-11-13T16:00:00+00:00"' in html  # le même instant pour le script


@pytest.mark.parametrize(("d", "attendu"), [
    (datetime(2026, 11, 13), "vendredi 13 novembre 2026"),
    (datetime(2026, 2, 1), "dimanche 1er février 2026"),
    (datetime(2026, 8, 31), "lundi 31 août 2026"),
])
def test_jour_en_clair(d, attendu):
    assert jour_en_clair(d) == attendu


def test_theme_sombre_uniquement_et_aucun_visuel_externe():
    html = client().get("/").text
    css = (STATIQUES / "teaser/teaser.css").read_text(encoding="utf-8")
    assert '<meta name="color-scheme" content="dark">' in html and "color-scheme:dark" in css
    assert "prefers-color-scheme" not in css  # aucune feuille claire
    assert "<img" not in html  # le décor est généré (dégradés, canvas, SVG)


def test_mouvement_reduit_prevu():
    css = (STATIQUES / "teaser/teaser.css").read_text(encoding="utf-8")
    bloc = css.split("@media (prefers-reduced-motion:reduce){", 1)[1]
    assert ".fog,.glow,.beam,.rays,.crown{animation:none!important}" in bloc
    js = (STATIQUES / "teaser/teaser.js").read_text(encoding="utf-8")
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in js and "if (!reduit)" in js


# --- Aucune requête vers un domaine tiers (critère 8) ------------------------------------------------


def test_page_ne_charge_rien_hors_de_chez_nous():
    html = client().get("/").text
    for attribut, valeur in re.findall(r'\b(src|href)="([^"]*)"', html):
        if valeur == "https://duffus.fr":
            continue  # un lien qu'on suit en cliquant, pas une ressource chargée
        assert valeur.startswith(("/", "#", "data:")), (attribut, valeur)
    assert "googleapis" not in html and "gstatic" not in html


def test_polices_auto_hebergees():
    css = (STATIQUES / "teaser/teaser.css").read_text(encoding="utf-8")
    urls = re.findall(r'url\("?([^")]+)"?\)', css)
    polices = [u for u in urls if u.endswith(".woff2")]
    assert len(polices) == 6
    for u in urls:
        assert not u.startswith(("http:", "https:", "//")), u
    for u in polices:
        assert (STATIQUES / "teaser" / u).resolve().is_file(), u
    assert sorted(p.name for p in (STATIQUES / "fonts").glob("*.woff2")) == sorted(Path(u).name for u in polices)
    assert "SIL OPEN FONT LICENSE" in (STATIQUES / "fonts/LICENCE-OFL.txt").read_text(encoding="utf-8")


def test_polices_servies_par_le_site():
    c = client()
    r = c.get("/static/fonts/alegreya-sc-800.woff2")
    assert r.status_code == 200 and r.headers["content-type"] == "font/woff2"
    assert c.get("/static/fonts/LICENCE-OFL.txt").status_code == 200


def test_script_sans_adresse_externe():
    js = (STATIQUES / "teaser/teaser.js").read_text(encoding="utf-8")
    assert not re.search(r"https?://", js.replace("http://www.w3.org/2000/svg", ""))
    assert "document.body.dataset.ouverture" in js and "document.body.dataset.lienSite" in js
    assert 'style="' not in js  # pas d'attribut style en ligne : la CSP le refuserait


# --- Le filtre du mode (critère 6) ----------------------------------------------------------------------


def _chemins_declares(app) -> set[str]:
    """Toutes les routes et montages de l'application, avec un exemple concret pour les paramètres."""
    return {re.sub(r"\{[^}]+\}", "1", route.path) for route in app.routes}


def test_toutes_les_routes_declarees_sont_fermees_pendant_le_teaser():
    app = creer_app(config(), horloge=lambda: AVANT)

    # Une route ajoutée « sans y penser » : elle doit être filtrée d'office, comme celles du lot B.
    @app.get("/admin/secret")
    async def secret():
        return {"secret": "ne doit jamais sortir"}

    @app.post("/api/etages/{numero}/coches")
    async def cocher(numero: int):
        return {"numero": numero}

    c = TestClient(app, follow_redirects=False)
    chemins = _chemins_declares(app)
    assert {"/", "/sante", "/admin/secret", "/api/etages/1/coches"} <= chemins
    for chemin in sorted(chemins):
        if chemin_permis(chemin) or chemin.startswith("/static/"):
            continue
        for methode in ("GET", "POST"):
            r = c.request(methode, chemin)
            attendu = 404 if chemin.startswith("/api/") else 303
            assert r.status_code == attendu, (methode, chemin)
            assert "secret" not in r.text


@pytest.mark.parametrize("chemin", ADRESSES_FERMEES)
def test_adresses_fermees_pendant_le_teaser(chemin):
    r = client().get(chemin)
    if chemin.startswith("/api/"):
        assert r.status_code == 404
    else:
        assert r.status_code == 303 and r.headers["location"] == "/"


def test_statiques_permis_mais_seulement_ceux_du_teaser():
    c = client()
    assert c.get("/static/teaser/teaser.css").status_code == 200
    assert c.get("/static/teaser/teaser.js").status_code == 200
    # L'ancienne page v3 reste dans le dépôt jusqu'au lot B, mais n'est pas servie (hors des préfixes permis).
    assert c.get("/static/app.js").status_code in (303, 404)
    assert c.get("/static/style.css").status_code in (303, 404)


# --- La bascule (critère 7) -------------------------------------------------------------------------------


@pytest.mark.parametrize(("maintenant", "mode"), [
    (OUVERTURE - timedelta(seconds=1), "teaser"),
    (OUVERTURE, "ouvert"),
    (APRES, "ouvert"),
])
def test_auto_bascule_a_site_ouvert_le(maintenant, mode):
    c = client(maintenant)
    assert c.get("/sante").json()["mode"] == mode
    # Pendant le teaser, une page inconnue renvoie vers /. Ensuite, elle n'existe tout simplement pas.
    assert c.get("/grimpeurs").status_code == (303 if mode == "teaser" else 404)


def test_teaser_force_apres_la_date():
    c = client(APRES, SITE_MODE="teaser")
    assert c.get("/sante").json()["mode"] == "teaser"
    assert c.get("/etages/0").status_code == 303
    assert 'id="opened" hidden' in c.get("/").text


def test_ouvert_force_avant_la_date():
    c = client(AVANT, SITE_MODE="ouvert")
    assert c.get("/sante").json()["mode"] == "ouvert"
    assert c.get("/etages/0").status_code == 404


def test_page_provisoire_en_mode_ouvert():
    html = client(APRES).get("/").text
    assert "<title>Les portes sont ouvertes · L'Épreuve des Dieux</title>" in html
    assert 'id="countdown" aria-labelledby="cdLabel" hidden' in html
    assert '<section class="opened" id="opened" aria-live="polite">' in html
    assert 'class="is-open"' in html and "Merci Duffus" in html


# --- En-têtes de sécurité (critère 9) ------------------------------------------------------------------


def _verifier_entetes(r):
    for nom, valeur in ENTETES_SECURITE.items():
        assert r.headers.get(nom) == valeur, (r.url, nom)
    csp = r.headers["content-security-policy"]
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert "default-src 'self'" in csp and "script-src" not in csp  # les scripts suivent default-src 'self'
    assert r.headers["x-robots-tag"].startswith("noindex")


@pytest.mark.parametrize("chemin", ["/", "/sante", "/static/teaser/teaser.css", "/static/fonts/ibm-plex-mono-500.woff2",
                                    "/static/teaser/absent.js", "/api/etat", "/admin"])
def test_entetes_sur_toutes_les_reponses(chemin):
    _verifier_entetes(client().get(chemin))


@pytest.mark.parametrize("chemin", ["/", "/sante"])
def test_head_repond_avec_les_entetes(chemin):
    r = client().head(chemin)
    assert r.status_code == 200 and r.content == b""
    _verifier_entetes(r)


def test_entetes_sur_une_404_en_mode_ouvert_et_une_erreur_500():
    _verifier_entetes(client(APRES).get("/une-adresse-inventee"))
    r = client(source=Source(RuntimeError("panne"))).get("/sante")  # erreur rattrapée : pas une 500
    assert r.status_code == 200
    app = creer_app(config(), horloge=lambda: APRES)  # mode ouvert : le filtre laisse passer la route

    @app.get("/boum")
    async def boum():
        raise RuntimeError("trace interne")

    r = TestClient(app, raise_server_exceptions=False).get("/boum")
    assert r.status_code == 500 and "trace interne" not in r.text
    _verifier_entetes(r)


# --- /sante (critère 12) ----------------------------------------------------------------------------


def test_sante_sans_base():
    r = client().get("/sante")
    assert r.status_code == 200
    assert r.json() == {"statut": "ok", "base": "absente", "mode": "teaser"}
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(("reponse", "base"), [(True, "ok"), (False, "erreur"), (OSError("injoignable"), "erreur")])
def test_sante_avec_base(reponse, base):
    r = client(source=Source(reponse)).get("/sante")
    assert r.status_code == 200  # le teaser ne dépend pas de la base
    assert r.json() == {"statut": "ok", "base": base, "mode": "teaser"}


# --- La configuration ----------------------------------------------------------------------------------


def test_configuration_par_defaut():
    c = config()
    assert c.site_mode == "auto" and c.site_ouvert_le == OUVERTURE
    assert c.teaser_lien_entrer == "" and c.site_url is None and c.database_url is None
    assert c.fuseau == "Europe/Paris"


def test_configuration_lue_dans_l_environnement(monkeypatch):
    monkeypatch.setenv("SITE_MODE", "teaser")
    monkeypatch.setenv("SITE_OUVERT_LE", "2026-11-13T18:00:00+01:00")
    monkeypatch.setenv("TEASER_LIEN_ENTRER", "https://epreuve.example/")
    monkeypatch.setenv("SITE_URL", "")  # vide = absente (env_ignore_empty)
    c = config()
    assert c.site_mode == "teaser" and c.site_ouvert_le == OUVERTURE + timedelta(hours=1)
    assert c.teaser_lien_entrer == "https://epreuve.example/" and c.site_url is None


@pytest.mark.parametrize(("variable", "valeur"), [
    ("SITE_OUVERT_LE", "2026-11-13T17:00:00"),  # sans fuseau : refusée
    ("SITE_MODE", "ferme"),
    ("DATABASE_URL", "postgresql://hote/base"),  # sans le pilote asyncpg
])
def test_configuration_refuse_les_valeurs_invalides(variable, valeur):
    with pytest.raises(ValidationError, match=variable):
        config(**{variable: valeur})


def test_url_de_base_masquee():
    c = config(DATABASE_URL="postgresql+asyncpg://moi:motdepasse@hote/base")
    assert "motdepasse" not in repr(c) and "motdepasse" not in str(c)
