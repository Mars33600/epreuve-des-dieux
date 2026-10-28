"""Connexion Discord (OAuth2 seul) et session : critères 1 à 7, 4 bis, 4 ter et 29 du lot B.

Discord est simulé par `httpx.MockTransport` : aucun appel réseau, et chaque adresse appelée est notée.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import SecretStr

from epreuve.config import Config
from epreuve.discord.oauth import ClientOAuth, ErreurDiscord, Identite, PasMembre, est_admin
from epreuve.web.auth import COOKIE_SESSION, MESSAGE_NON_MEMBRE, MESSAGE_SUSPENDU
from epreuve.web.demo import ID_HORS_LISTE, ID_MARCEAU, ID_NON_MEMBRE, ID_NOUVELLE, faux_discord
from tests.web.outils import (
    AVANT_OUVERTURE,
    ID_ADMIN_SUP,
    ID_BRINDILLE,
    ID_FOURBE,
    SITE,
    monde,
)

# ---------------------------------------------------------------- le client OAuth seul


def client_oauth(transport=None) -> ClientOAuth:
    return ClientOAuth("42", SecretStr("s"), f"{SITE}/auth/discord/retour", 1, transport=transport)


def test_url_d_autorisation_deux_portees_seulement():
    url = urlparse(client_oauth().url_autorisation("etat-xyz"))
    q = parse_qs(url.query)
    assert url.netloc == "discord.com" and url.path == "/oauth2/authorize"
    assert q["scope"] == ["identify guilds.members.read"] and "%20" in url.query
    assert q["response_type"] == ["code"] and q["client_id"] == ["42"] and q["state"] == ["etat-xyz"]
    assert q["redirect_uri"] == [f"{SITE}/auth/discord/retour"] and q["prompt"] == ["none"]


async def test_identite_et_roles():
    appels: list[str] = []
    c = client_oauth(faux_discord({7: ("Pseudo", frozenset({5, 6}))}, appels))
    jeton = await c.echanger_code("code-7")
    assert jeton == "jeton-7"
    assert await c.identite(jeton) == Identite(7, "Pseudo", frozenset({5, 6}))
    assert appels == ["POST /api/v10/oauth2/token", "GET /api/v10/users/@me", "GET /api/v10/users/@me/guilds/1/member"]


async def test_non_membre_et_erreurs():
    c = client_oauth(faux_discord({}))
    with pytest.raises(PasMembre):
        await c.identite("jeton-9")
    with pytest.raises(ErreurDiscord):
        await c.identite("jeton-invalide")
    with pytest.raises(ErreurDiscord):
        await c.echanger_code("mauvais")


async def test_reponses_illisibles_refusees():
    def repondre(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"pas_de_jeton": True})
        return httpx.Response(200, text="pas du json")

    c = client_oauth(httpx.MockTransport(repondre))
    with pytest.raises(ErreurDiscord):
        await c.echanger_code("x")
    with pytest.raises(ErreurDiscord):
        await c.identite("x")


async def test_revocation_ignore_les_erreurs(caplog):
    def panne(_req):
        raise httpx.ConnectError("hors ligne")

    await client_oauth(httpx.MockTransport(panne)).revoquer("jeton")
    await client_oauth(httpx.MockTransport(lambda r: httpx.Response(500))).revoquer("jeton")
    assert "jeton" not in caplog.text.replace("révocation du jeton", "")  # jamais le jeton lui-même au journal


def test_est_admin_par_role_ou_liste_de_secours():
    assert est_admin(Identite(1, "a", frozenset({9})), frozenset({9}), frozenset())
    assert est_admin(Identite(2, "b", frozenset()), frozenset({9}), frozenset({2}))
    assert not est_admin(Identite(3, "c", frozenset({8})), frozenset({9}), frozenset({2}))


# ---------------------------------------------------------------- le parcours sur le site


def test_flux_complet_et_cookie_de_session():
    m = monde()
    c = m.client()
    r = c.get("/connexion")
    assert r.status_code == 303 and r.headers["location"].startswith("https://discord.com/oauth2/authorize?")
    etat = r.headers["set-cookie"]
    assert "__Host-oauth_state=" in etat and "Secure" in etat and "HttpOnly" in etat and "samesite=lax" in etat.lower()
    assert "Max-Age=600" in etat and "Path=/" in etat
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = c.get(f"/auth/discord/retour?code=code-{ID_BRINDILLE}&state={state}")
    assert r.status_code == 303 and r.headers["location"] == "/"
    cookie = [v for k, v in r.headers.multi_items() if k == "set-cookie" and v.startswith(COOKIE_SESSION)][0]
    assert "Secure" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower() and "Path=/" in cookie
    assert "Max-Age=604800" in cookie  # 7 jours
    jeton = cookie.split(";")[0].split("=", 1)[1]
    assert len(jeton) >= 43  # 256 bits en base64
    # La base ne garde que l'empreinte du jeton, jamais le jeton lui-même.
    assert all(k != jeton.encode() and len(k) == 32 for k in m.depot._sessions)
    assert "Brindille" in c.get("/").text


@pytest.mark.parametrize("cas", ["absent", "faux", "sans_cookie"])
def test_state_absent_faux_ou_expire_refuse(cas):
    m = monde()
    c = m.client()
    r = c.get("/connexion")
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    if cas == "sans_cookie":  # le cookie de 10 minutes a expiré
        c.cookies.clear()
    q = {"absent": "", "faux": "&state=autre", "sans_cookie": f"&state={state}"}[cas]
    r = c.get(f"/auth/discord/retour?code=code-{ID_BRINDILLE}{q}")
    assert r.status_code == 400 and "Recommence" in r.text
    assert m.depot._sessions == {} and not any(a.endswith("/oauth2/token") for a in m.appels)


def test_non_membre_refuse_sans_session_et_jeton_revoque():
    m = monde()
    c = m.client()
    r = c.get("/connexion")
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = c.get(f"/auth/discord/retour?code=code-{ID_NON_MEMBRE}&state={state}")
    assert r.status_code == 403 and MESSAGE_NON_MEMBRE.replace("'", "&#39;") in r.text
    assert m.depot._sessions == {}
    assert "POST /api/v10/oauth2/token/revoke" in m.appels


def test_annulation_sur_discord():
    m = monde()
    c = m.client()
    state = parse_qs(urlparse(c.get("/connexion").headers["location"]).query)["state"][0]
    assert c.get(f"/auth/discord/retour?error=access_denied&state={state}").status_code == 400


def test_membre_de_la_liste_sans_fiche_va_creer_sa_fiche():
    m = monde()
    c = m.client()
    state = parse_qs(urlparse(c.get("/connexion").headers["location"]).query)["state"][0]
    r = c.get(f"/auth/discord/retour?code=code-{ID_NOUVELLE}&state={state}")
    assert r.headers["location"] == "/inscription"
    assert "Créer ma fiche" in c.get("/inscription").text
    assert c.get("/").headers["location"] == "/inscription"


def test_membre_hors_liste_voit_le_message():
    m = monde()
    c = m.connecter(ID_HORS_LISTE)
    html = c.get("/inscription").text
    assert "Envoie ta validation en MP à Shadoaze" in html and "<form" not in html.split("<main")[0][-1:]


@pytest.mark.parametrize("discord_id", [ID_MARCEAU, ID_ADMIN_SUP])
def test_admin_par_role_ou_par_liste_de_secours(discord_id):
    m = monde()
    c = m.connecter(discord_id)
    assert c.get("/admin").status_code == 200
    # Admin sans fiche : il consulte tout sans compter dans la jauge (critère 4 ter).
    for chemin in ("/", "/etages/0", "/grimpeurs", "/grimpeurs/1", "/etages/0/quetes/101", "/regles"):
        assert c.get(chemin).status_code == 200, chemin


def test_simple_grimpeur_n_est_pas_admin():
    c = monde().connecter(ID_BRINDILLE)
    assert c.get("/admin").status_code == 403


def test_exclu_ne_voit_que_le_message():
    m = monde()
    c = m.connecter(ID_FOURBE)
    for chemin in ("/", "/etages/0", "/grimpeurs", "/grimpeurs/1", "/regles"):
        r = c.get(chemin)
        assert r.status_code == 403 and MESSAGE_SUSPENDU in r.text, chemin


def test_revérification_des_droits_apres_10_minutes():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    m.membres[ID_MARCEAU] = ("Marceau", frozenset())  # rôle retiré sur Discord
    m.avancer(minutes=9)
    assert c.get("/admin").status_code == 200  # pas encore revérifié
    n = len(m.appels)
    m.avancer(minutes=2)
    assert c.get("/admin").status_code == 403
    assert m.appels[n:] == ["GET /api/v10/users/@me", "GET /api/v10/users/@me/guilds/1/member"]
    assert c.get("/admin").status_code == 403  # la session est redevenue non-admin


def test_revérification_garde_l_admin_qui_a_toujours_son_role():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    m.avancer(minutes=30)
    assert c.get("/admin").status_code == 200
    n = len(m.appels)
    assert c.get("/admin").status_code == 200 and len(m.appels) == n  # revérifié il y a moins de 10 minutes


def test_revérification_discord_injoignable_refuse_sans_retirer_le_droit():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    m.avancer(minutes=11)

    def panne(_req):
        raise httpx.ConnectError("hors ligne")

    m.app.state.oauth = client_oauth(httpx.MockTransport(panne))
    assert c.get("/admin").status_code == 503
    assert all(s.est_admin for s in m.depot._sessions.values())


def test_deconnexion_supprime_la_session_et_revoque_le_jeton():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    cookie = c.cookies.get(COOKIE_SESSION)
    jeton_csrf = m.csrf(c)
    r = c.post("/deconnexion", data={"csrf": jeton_csrf}, headers={"Origin": SITE})
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert m.depot._sessions == {}
    assert m.appels[-1] == "POST /api/v10/oauth2/token/revoke"
    # Le vieux cookie ne fonctionne plus.
    autre = m.client()
    autre.cookies.set(COOKIE_SESSION, cookie, domain="epreuve.test")
    assert "Se connecter avec Discord" in autre.get("/").text


def test_deconnexion_sans_csrf_refusee():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    assert c.post("/deconnexion", data={"csrf": "faux"}, headers={"Origin": SITE}).status_code == 403
    assert len(m.depot._sessions) == 1


def test_session_expiree_apres_7_jours():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    m.avancer(days=7, seconds=1)
    assert "Se connecter avec Discord" in c.get("/").text


def test_aucun_bot_seulement_les_quatre_adresses_oauth():
    """Critère 29 : le site n'appelle Discord que pour la connexion, et la configuration ne lit aucun jeton de bot."""
    m = monde()
    c = m.connecter(ID_MARCEAU)
    m.avancer(minutes=11)
    c.get("/admin")
    c.post("/deconnexion", data={"csrf": m.csrf(c)}, headers={"Origin": SITE})
    permis = {"POST /api/v10/oauth2/token", "GET /api/v10/users/@me", "GET /api/v10/users/@me/guilds/1/member",
              "POST /api/v10/oauth2/token/revoke"}
    assert set(m.appels) == permis
    assert not any("token" in nom.lower() and "secret" not in nom.lower() for nom in Config.model_fields)


def test_jeton_de_bot_dans_l_environnement_ignore(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "jeton-de-bot")
    assert "jeton-de-bot" not in repr(Config(_env_file=None).model_dump())


# ---------------------------------------------------------------- avant le 13/11 (critère 4 bis)


def test_mode_teaser_le_joueur_connecte_revoit_le_teaser():
    m = monde(mode="auto", maintenant=AVANT_OUVERTURE)
    c = m.connecter(ID_NOUVELLE)  # sur la liste, sans fiche : aucune fiche ne doit être créée
    assert "teaser.js" in c.get("/").text
    for chemin in ("/inscription", "/etages/0", "/grimpeurs", "/grimpeurs/1", "/regles", "/admin"):
        r = c.get(chemin)
        assert r.status_code == 303 and r.headers["location"] == "/", chemin
    r = c.post("/inscription", data={"csrf": "x", "pseudo": "Nouvelle"}, headers={"Origin": SITE})
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert c.post("/api/coches", json={}).status_code == 404
    assert len(m.depot._grimpeurs) == 13


def test_mode_teaser_retour_oauth_renvoie_le_joueur_au_teaser():
    m = monde(mode="teaser")
    c = m.client()
    state = parse_qs(urlparse(c.get("/connexion").headers["location"]).query)["state"][0]
    r = c.get(f"/auth/discord/retour?code=code-{ID_NOUVELLE}&state={state}")
    assert r.headers["location"] == "/"


def test_mode_teaser_l_admin_voit_tout_avec_le_bandeau():
    m = monde(mode="teaser")
    c = m.connecter(ID_MARCEAU)
    html = c.get("/").text
    assert "teaser.js" not in html and "Mode teaser" in html and "les grimpeurs ne voient pas encore" in html
    for chemin in ("/etages/0", "/grimpeurs", "/admin", "/admin/journal", "/regles"):
        r = c.get(chemin)
        assert r.status_code == 200 and "Mode teaser" in r.text, chemin
    # Même un admin ne crée pas de fiche avant l'ouverture.
    assert c.get("/inscription").headers["location"] == "/"
