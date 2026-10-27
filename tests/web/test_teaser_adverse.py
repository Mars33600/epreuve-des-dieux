"""Tests adverses du lot A : ce qu'un visiteur curieux (ou un oubli du lot B) pourrait tenter pendant le teaser.

Méthodes inhabituelles, chemins encodés ou « remontants », websockets, injection dans le gabarit,
configuration bancale, image Docker et secrets. Les chemins avec `..` sont envoyés directement à
l'application ASGI : le client HTTP de test les normaliserait avant l'envoi, un vrai visiteur non.
"""

import asyncio
import re
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from epreuve.config import OUVERTURE_PAR_DEFAUT, Config
from epreuve.web.app import creer_app
from epreuve.web.securite import CSP, chemin_permis

RACINE = Path(__file__).resolve().parents[2]
AVANT = datetime(2026, 11, 3, 20, 0, tzinfo=UTC)
APRES = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)
FUITE = "contenu-qui-ne-doit-pas-sortir"


def config(**reglages) -> Config:
    return Config(_env_file=None, **reglages)


def app_piegee(maintenant: datetime = AVANT, **reglages):
    """L'application, plus des routes « oubliées » comme le lot B pourrait en déclarer."""
    app = creer_app(config(**reglages), horloge=lambda: maintenant)

    @app.api_route("/admin", methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def admin():
        return {"x": FUITE}

    @app.get("/api/etat")
    async def etat():
        return {"x": FUITE}

    @app.get("/{reste:path}/fuite")
    async def attrape_tout(reste: str):
        return {"x": FUITE}

    @app.websocket("/ws")
    async def ws(w: WebSocket):
        await w.accept()
        await w.send_text(FUITE)
        await w.close()

    return app


def appel_brut(app, methode: str, chemin: str) -> tuple[int, bytes]:
    """Envoie la requête telle quelle à l'application ASGI, sans normalisation du chemin.

    Comme uvicorn, on décode les %xx dans `path` et on garde l'original dans `raw_path`.
    """
    messages: list[dict] = []
    recu = False

    async def receive():
        nonlocal recu
        if not recu:
            recu = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.sleep(1)
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": methode,
             "scheme": "https", "path": unquote(chemin), "raw_path": chemin.encode(), "query_string": b"",
             "headers": [(b"host", b"epreuve.test")], "root_path": "", "server": ("epreuve.test", 443),
             "client": ("203.0.113.1", 1234)}
    asyncio.run(app(scope, receive, send))
    statut = next(m["status"] for m in messages if m["type"] == "http.response.start")
    corps = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return statut, corps


# --- Aucune fuite pendant le teaser --------------------------------------------------------------------


@pytest.mark.parametrize("methode", ["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@pytest.mark.parametrize("chemin", ["/admin", "/admin/", "//admin", "/ADMIN", "/%61dmin", "/admin%2F", "/x/fuite",
                                    "/sante/fuite", "/api/etat", "/api/etat/", "/api", "/API/etat"])
def test_aucune_methode_ni_variante_de_chemin_ne_fuit(methode, chemin):
    statut, corps = appel_brut(app_piegee(), methode, chemin)
    assert statut in (303, 404, 405), (methode, chemin, statut)
    assert FUITE.encode() not in corps


@pytest.mark.parametrize("chemin", [
    "/static/../admin", "/static/teaser/../../admin", "/static/../x/fuite", "/static/./../api/etat",
    "/static/teaser/../../app.py", "/static/teaser/../../../config.py", "/static/fonts/../../templates/teaser.html",
    "/static/teaser/..%2f..%2fapp.py", "/static/teaser/%2e%2e/%2e%2e/app.py", "/static//etc/passwd",
])
def test_remonter_depuis_static_ne_sert_rien(chemin):
    statut, corps = appel_brut(app_piegee(), "GET", chemin)
    assert statut in (303, 404), (chemin, statut)
    assert FUITE.encode() not in corps and b"def " not in corps and b"{%" not in corps and b"root:" not in corps


@pytest.mark.parametrize("chemin", ["/static/../admin", "/static//x", "/static/./x", "/static/teaser/..",
                                    "/static/a/../b"])
def test_chemin_permis_refuse_les_segments_points_ou_vides(chemin):
    assert not chemin_permis(chemin)


def test_route_a_parametre_en_tete_ne_repond_pas_sous_static():
    statut, corps = appel_brut(app_piegee(), "GET", "/static/fuite")
    assert FUITE.encode() not in corps, statut


def test_les_dossiers_statiques_ne_se_listent_pas():
    c = TestClient(app_piegee(), follow_redirects=False)
    for chemin in ("/static/", "/static/teaser/", "/static/fonts/"):
        assert c.get(chemin).status_code in (303, 404)


def test_websocket_refuse_pendant_le_teaser():
    with pytest.raises(WebSocketDisconnect) as refus, TestClient(app_piegee()).websocket_connect("/ws") as w:
        w.receive_text()
    assert refus.value.code == 1008


def test_websocket_accepte_une_fois_ouvert():
    with TestClient(app_piegee(APRES)).websocket_connect("/ws") as w:
        assert w.receive_text() == FUITE


def test_teaser_force_ferme_aussi_les_methodes_d_ecriture_apres_la_date():
    c = TestClient(app_piegee(APRES, SITE_MODE="teaser"), follow_redirects=False)
    for methode in ("POST", "PUT", "DELETE"):
        r = c.request(methode, "/admin")
        assert r.status_code == 303 and FUITE not in r.text


# --- CSP et gabarit ------------------------------------------------------------------------------------


def _directives(csp: str) -> dict[str, list[str]]:
    return {d.split()[0]: d.split()[1:] for d in (x.strip() for x in csp.split(";")) if d}


def test_csp_scripts_sans_unsafe_et_sans_source_tierce():
    d = _directives(CSP)
    scripts = d.get("script-src", d["default-src"])  # sans script-src, les scripts suivent default-src
    assert scripts == ["'self'"]
    assert d.get("style-src", d["default-src"]) == ["'self'"]
    assert "unsafe" not in CSP and "*" not in CSP
    assert d["frame-ancestors"] == ["'none'"] and d["base-uri"] == ["'none'"]


def test_page_compatible_avec_la_csp():
    html = TestClient(app_piegee()).get("/").text
    # Aucun script en ligne : chaque <script> a un src local, et aucun attribut on*= ni style=.
    for balise in re.findall(r"<script\b[^>]*>", html):
        assert re.search(r'src="/static/', balise), balise
    assert not re.search(r"<script\b[^>]*>\s*\S", html.replace('<script src="/static/teaser/teaser.js"></script>', ""))
    assert not re.search(r"\son[a-z]+\s*=", html)
    assert " style=" not in html and "<style" not in html
    assert "javascript:" not in html


def test_lien_du_bouton_echappe_dans_l_attribut():
    lien = 'https://x.test/"><script>alert(1)</script>'
    html = TestClient(creer_app(config(TEASER_LIEN_ENTRER=lien), horloge=lambda: AVANT)).get("/").text
    assert "<script>alert(1)" not in html
    assert 'data-lien-site="https://x.test/&#34;&gt;&lt;script&gt;' in html


# --- La date d'ouverture -------------------------------------------------------------------------------


def test_ouverture_le_13_novembre_a_17h_paris_soit_16h_utc():
    assert OUVERTURE_PAR_DEFAUT == datetime(2026, 11, 13, 16, 0, tzinfo=UTC)
    paris = OUVERTURE_PAR_DEFAUT.astimezone(ZoneInfo("Europe/Paris"))
    assert (paris.day, paris.month, paris.hour, paris.minute, paris.weekday()) == (13, 11, 17, 0, 4)  # vendredi
    assert paris.utcoffset() == timedelta(hours=1)  # heure d'hiver : le passage a eu lieu le 25/10


@pytest.mark.parametrize("fichier", ["fly.toml", ".env.example"])
def test_fichiers_de_deploiement_alignes_sur_la_date(fichier):
    texte = (RACINE / fichier).read_text(encoding="utf-8")
    valeur = re.search(r'SITE_OUVERT_LE\s*=\s*"?([^"\s#]+)', texte).group(1)
    assert datetime.fromisoformat(valeur) == OUVERTURE_PAR_DEFAUT


def test_bascule_de_bout_en_bout_avec_la_configuration_par_defaut():
    juste_avant = OUVERTURE_PAR_DEFAUT - timedelta(seconds=1)
    assert TestClient(app_piegee(juste_avant), follow_redirects=False).get("/admin").status_code == 303
    assert TestClient(app_piegee(OUVERTURE_PAR_DEFAUT)).get("/admin").json() == {"x": FUITE}


# --- Configuration bancale -----------------------------------------------------------------------------


@pytest.mark.parametrize("variable", ["SITE_MODE", "SITE_OUVERT_LE", "TEASER_LIEN_ENTRER", "SITE_URL", "FUSEAU",
                                      "SITE_PORT", "JOURNAL_NIVEAU", "DATABASE_URL"])
def test_variable_vide_vaut_absente(monkeypatch, variable):
    monkeypatch.setenv(variable, "")
    c, defaut = config(), Config.model_construct()
    attribut = variable.lower()  # les champs portent le nom de leur variable, en minuscules
    assert getattr(c, attribut) == getattr(defaut, attribut)


@pytest.mark.parametrize("valeur", ["2026-11-13", "2026-11-13 17:00", "13/11/2026 17:00", "demain",
                                    "2026-11-13T17:00:00"])
def test_date_sans_fuseau_ou_illisible_refusee(monkeypatch, valeur):
    monkeypatch.setenv("SITE_OUVERT_LE", valeur)
    with pytest.raises(ValidationError, match="SITE_OUVERT_LE"):
        config()


@pytest.mark.parametrize("valeur", ["2026-11-13T16:00:00Z", "2026-11-13T16:00:00+00:00", "2026-11-13T11:00:00-05:00"])
def test_date_dans_un_autre_fuseau_meme_instant(monkeypatch, valeur):
    monkeypatch.setenv("SITE_OUVERT_LE", valeur)
    assert config().site_ouvert_le == OUVERTURE_PAR_DEFAUT


@pytest.mark.parametrize("valeur", ["Europe/Pariss", "Paris", "../../etc/passwd", "UTC+1"])
def test_fuseau_inconnu_refuse_au_demarrage(monkeypatch, valeur):
    monkeypatch.setenv("FUSEAU", valeur)
    with pytest.raises(ValidationError, match="FUSEAU"):
        config()


@pytest.mark.parametrize("valeur", ["TEASER", "Ouvert", " teaser", "ferme", "1"])
def test_mode_mal_ecrit_refuse(monkeypatch, valeur):
    monkeypatch.setenv("SITE_MODE", valeur)
    with pytest.raises(ValidationError, match="SITE_MODE"):
        config()


# --- Image Docker et secrets ---------------------------------------------------------------------------


def test_dockerfile_tourne_sans_privilege():
    texte = (RACINE / "Dockerfile").read_text()
    lignes = [x.strip() for x in texte.splitlines() if x.strip() and not x.startswith("#")]
    users = [i for i, x in enumerate(lignes) if x.startswith("USER ")]
    assert users, "aucune instruction USER : le programme tournerait en root"
    dernier = users[-1]
    assert lignes[dernier].split()[1] not in ("root", "0")
    # Rien ne s'exécute en root après la bascule, et le programme est lancé après.
    assert not any(x.startswith("RUN ") for x in lignes[dernier:])
    assert any(x.startswith("CMD ") for x in lignes[dernier:])


def _fichiers_suivis() -> list[str]:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git indisponible")
    try:
        sortie = subprocess.run([git, "ls-files"], cwd=RACINE, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git indisponible")
    return sortie.stdout.splitlines()


def test_aucun_fichier_de_secrets_suivi():
    suivis = _fichiers_suivis()
    assert ".env" not in suivis
    assert not [f for f in suivis if re.search(r"(^|/)\.env\.(?!example$)|\.(pem|key|p12)$", f)]


def test_aucun_secret_en_clair_dans_le_depot():
    motifs = [
        re.compile(r"[MN][A-Za-z\d_-]{23,25}\.[A-Za-z\d_-]{6}\.[A-Za-z\d_-]{27,}"),  # jeton de bot Discord
        re.compile(r"postgres(?:ql)?(?:\+asyncpg)?://[^:\s/]+:(?!test@|motdepasse@|…)[^@\s]{6,}@(?!localhost|hote)"),
        re.compile(r"(?i)(client_secret|DISCORD_TOKEN|DISCORD_CLIENT_SECRET|SESSION_SECRET)\s*=\s*['\"]?[A-Za-z\d_-]{16,}"),
        re.compile(r"sk-ant-[A-Za-z\d_-]{10,}"),
    ]
    fautifs = []
    for nom in _fichiers_suivis():
        chemin = RACINE / nom
        if chemin.suffix in (".woff2", ".png", ".jpg", ".ico", ".lock") or not chemin.is_file():
            continue
        texte = chemin.read_text(encoding="utf-8", errors="ignore")
        fautifs += [(nom, m.pattern[:30]) for m in motifs if m.search(texte)]
    assert not fautifs
