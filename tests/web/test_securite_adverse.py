"""Revue B2 : tests adverses complémentaires (OAuth, Origin, CSRF, droits, XSS, en-têtes, accessibilité).

Ils complètent `test_auth.py`, `test_api.py` et `tests/qa/test_qa_site.py` sur les angles qui n'y étaient pas :
cookie du `state`, `state` à usage unique, redirections ouvertes, origines trompeuses, jeton CSRF hors de
l'en-tête, fiche de quête piégée en base, nom Discord piégé, en-têtes sur les pages du site, et un contrôle
d'accessibilité de base (langue, titre, étiquettes des champs, noms des boutons et des liens).
"""

from __future__ import annotations

import re
from dataclasses import replace
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

from epreuve.web.demo import ID_MARCEAU, ID_NOUVELLE
from epreuve.web.securite import ENTETES_SECURITE
from tests.web.outils import ID_ADMIN_SUP, ID_BRINDILLE, SITE, cocher, monde

XSS = "<img src=x onerror=alert(1)>"


# ---------------------------------------------------------------- OAuth

def _set_cookies(r) -> list[str]:
    return r.headers.get_list("set-cookie")


def test_cookie_du_state_host_secure_httponly_lax_et_court():
    m = monde()
    r = m.client().get("/connexion")
    cookie = next(c for c in _set_cookies(r) if c.startswith("__Host-oauth_state="))
    attributs = {a.strip().split("=")[0].lower(): a for a in cookie.split(";")[1:]}
    assert {"secure", "httponly", "path", "samesite", "max-age"} <= attributs.keys()
    assert "domain" not in attributs  # un cookie __Host- n'a jamais de Domain
    assert attributs["path"].strip() == "Path=/" and attributs["samesite"].strip().lower() == "samesite=lax"
    assert attributs["max-age"].strip() == "Max-Age=600"
    # Le `state` du cookie est celui envoyé à Discord, et il change à chaque demande.
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    assert cookie.split(";")[0] == f"__Host-oauth_state={state}" and len(state) >= 40
    autre = parse_qs(urlsplit(m.client().get("/connexion").headers["location"]).query)["state"][0]
    assert autre != state


def test_state_a_usage_unique():
    m = monde()
    c = m.client()
    state = parse_qs(urlsplit(c.get("/connexion").headers["location"]).query)["state"][0]
    r = c.get(f"/auth/discord/retour?code=code-{ID_BRINDILLE}&state={state}")
    assert r.status_code == 303
    assert any(s.startswith("__Host-oauth_state=") and "Max-Age=0" in s for s in _set_cookies(r))
    rejoue = m.client()
    rejoue.cookies.set("__Host-oauth_state", "autre-valeur", domain="epreuve.test")
    assert rejoue.get(f"/auth/discord/retour?code=code-{ID_BRINDILLE}&state={state}").status_code == 400
    assert c.get(f"/auth/discord/retour?code=code-{ID_BRINDILLE}&state={state}").status_code == 400


def test_aucune_redirection_ouverte():
    m = monde()
    c = m.client()
    r = c.get("/connexion?redirect_uri=https://evil.test/vol&next=https://evil.test")
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert q["redirect_uri"] == [f"{SITE}/auth/discord/retour"] and q["scope"] == ["identify guilds.members.read"]
    state = q["state"][0]
    r = c.get(f"/auth/discord/retour?code=code-{ID_BRINDILLE}&state={state}&next=https://evil.test"
              "&redirect=//evil.test")
    assert r.headers["location"] in ("/", "/inscription")
    for chemin in ("//evil.test/", "//evil.test/%2e%2e", "/\\evil.test", "/admin/", "/grimpeurs/"):
        loc = c.get(chemin).headers.get("location", "")
        assert "evil.test" not in urlsplit(loc).netloc and not loc.startswith(("//", "/\\")), (chemin, loc)


# ---------------------------------------------------------------- Origin et CSRF

ORIGINES_TROMPEUSES = ["null", "https://epreuve.test.evil.test", "http://epreuve.test", "https://epreuve.test:444",
                       "https://evil.test", "https://EPREUVE.test.evil.test", " https://epreuve.test"]


@pytest.mark.parametrize("origine", ORIGINES_TROMPEUSES)
def test_origine_trompeuse_refusee_sans_ecrire(origine):
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    jeton = m.csrf(c)
    r = c.post("/api/coches", json={"type": "quete", "id": 107, "cochee": True},
               headers={"X-CSRF-Token": jeton, "Origin": origine})
    assert r.status_code == 403
    assert 107 not in m.depot._coches_quetes.get(1, set())
    assert cocher(c, jeton, type="quete", id=107, cochee=True).json()["changement"] is True  # rien n'avait été écrit


@pytest.mark.parametrize("referer", ["https://epreuve.test.evil.test/", "https://epreuve.test@evil.test/",
                                     "https://evil.test/https://epreuve.test/", "http://epreuve.test/"])
def test_referer_trompeur_refuse_sans_origin(referer):
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    r = c.post("/api/coches", json={"type": "quete", "id": 107, "cochee": True},
               headers={"X-CSRF-Token": m.csrf(c), "Referer": referer})
    assert r.status_code == 403


def test_jeton_csrf_vide_dans_l_url_ou_dans_le_corps_json_refuse():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    jeton = m.csrf(c)
    corps = {"type": "quete", "id": 107, "cochee": True}
    assert c.post("/api/coches", json=corps, headers={"X-CSRF-Token": "", "Origin": SITE}).status_code == 403
    assert c.post(f"/api/coches?csrf={jeton}", json=corps, headers={"Origin": SITE}).status_code == 403
    assert c.post("/api/coches", json={**corps, "csrf": jeton}, headers={"Origin": SITE}).status_code == 403
    # Formulaire : le champ « csrf » d'une autre valeur, ou répété, ne passe pas.
    r = c.post("/grimpeurs/moi", data={"csrf": "x" + jeton, "pseudo": "Pirate"}, headers={"Origin": SITE})
    assert r.status_code == 403
    assert m.depot._grimpeurs[1].pseudo != "Pirate"


# ---------------------------------------------------------------- droits

def test_un_joueur_ne_modifie_que_sa_propre_fiche():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    jeton = m.csrf(c)
    avant = m.depot._grimpeurs[2].pseudo
    # Un identifiant glissé dans le formulaire est ignoré : c'est la fiche de la session qui change.
    r = c.post("/grimpeurs/moi", data={"csrf": jeton, "pseudo": "Brindille Bis", "grimpeur_id": "2", "id": "2"},
               headers={"Origin": SITE})
    assert r.status_code == 303 and r.headers["location"].startswith("/grimpeurs/1")
    assert m.depot._grimpeurs[2].pseudo == avant and m.depot._grimpeurs[1].pseudo == "Brindille Bis"
    # Les écritures d'admin restent fermées, même avec un jeton CSRF valide.
    r = c.post("/admin/grimpeurs/2", data={"csrf": jeton, "pseudo": "Pirate"}, headers={"Origin": SITE})
    assert r.status_code == 403 and m.depot._grimpeurs[2].pseudo == avant
    r = c.post("/admin/grimpeurs/2/statut", data={"csrf": jeton, "statut": "exclu", "motif": "x", "confirmer": "1"},
               headers={"Origin": SITE})
    assert r.status_code == 403 and m.depot._grimpeurs[2].statut != "exclu"
    # Cocher pour un autre, même avec un motif : 403.
    assert cocher(c, jeton, type="quete", id=107, cochee=True, grimpeur_id=2, motif="parce que").status_code == 403


def test_teaser_un_joueur_connecte_n_ecrit_rien():
    from tests.web.outils import AVANT_OUVERTURE

    m = monde(mode="auto", maintenant=AVANT_OUVERTURE)
    c = m.connecter(ID_BRINDILLE)
    assert '<meta name="csrf"' not in c.get("/").text  # le teaser, pas le site
    for chemin in ("/etages/0", "/grimpeurs", "/grimpeurs/1", "/regles", "/inscription", "/admin"):
        assert c.get(chemin).status_code == 303, chemin
    r = c.post("/api/coches", json={"type": "quete", "id": 107, "cochee": True}, headers={"Origin": SITE})
    assert r.status_code == 404
    assert c.post("/grimpeurs/moi", data={"pseudo": "Pirate"}, headers={"Origin": SITE}).status_code == 303
    assert m.depot._grimpeurs[1].pseudo != "Pirate"


# ---------------------------------------------------------------- XSS

FICHE_PIEGEE = ('<script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:alert(1)">lien</a>'
                '<a href="https://duffus.fr/quete/x">duffus</a><p onclick="alert(1)">clic</p>'
                '<style>body{}</style><iframe src="https://evil.test"></iframe><b>gras gardé</b>'
                '<a href="//evil.test/x">relatif</a><a href="/etages/0/quetes/102">interne</a>')


def test_fiche_piegee_en_base_neutralisee_au_rendu():
    """Défense en profondeur : même si la base contenait une étape non nettoyée, le rendu la nettoie."""
    m = monde()
    f = m.depot._fiches[101]
    etape = replace(f.etapes[0], texte_html=FICHE_PIEGEE)
    m.depot._fiches[101] = replace(f, etapes=(etape, *f.etapes[1:]))
    c = m.connecter(ID_BRINDILLE)
    for entetes in ({}, {"Accept": "text/html-fragment"}):
        page = c.get("/etages/0/quetes/101", headers=entetes).text
        assert "<script>alert" not in page and "<iframe" not in page and "<style>" not in page
        assert "onerror" not in page and "onclick" not in page and "javascript:" not in page
        assert "duffus.fr/quete" not in page and "evil.test" not in page
        assert "<b>gras gardé</b>" in page and '<a href="/etages/0/quetes/102">interne</a>' in page


def test_nom_discord_piege_affiche_en_texte():
    m = monde()
    m.membres[ID_ADMIN_SUP] = (XSS, frozenset())
    m.membres[ID_NOUVELLE] = (XSS, m.membres[ID_NOUVELLE][1])
    admin = m.connecter(ID_ADMIN_SUP)
    for chemin in ("/", "/etages/0", "/grimpeurs", "/admin", "/admin/grimpeurs", "/admin/journal"):
        assert XSS not in admin.get(chemin).text, chemin
    nouvelle = m.connecter(ID_NOUVELLE)
    assert XSS not in nouvelle.get("/inscription").text


# ---------------------------------------------------------------- en-têtes

PAGES_ADMIN = ["/", "/etages/0", "/etages/0/quetes/101", "/grimpeurs", "/grimpeurs/1", "/regles", "/admin",
               "/admin/grimpeurs", "/admin/etages", "/admin/etages/0", "/admin/journal", "/etages/999",
               "/n-existe-pas"]


def test_entetes_de_securite_sur_chaque_page_du_site():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    for chemin in PAGES_ADMIN:
        r = c.get(chemin)
        for nom, valeur in ENTETES_SECURITE.items():
            assert r.headers.get(nom) == valeur, (chemin, nom)
        assert r.headers.get("cache-control") == "no-store", chemin
    csp = ENTETES_SECURITE["Content-Security-Policy"]
    assert "unsafe" not in csp and "frame-ancestors 'none'" in csp and "base-uri 'none'" in csp
    assert ENTETES_SECURITE.get("Strict-Transport-Security", "").startswith("max-age=")


def test_merci_duffus_sur_les_pages_d_erreur_et_d_admin():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    for chemin in PAGES_ADMIN:
        assert ">Merci Duffus</a>" in c.get(chemin).text, chemin
    visiteur = m.client()
    for chemin in ("/", "/etages/0", "/n-existe-pas"):
        r = visiteur.get(chemin, follow_redirects=True)
        assert ">Merci Duffus</a>" in r.text, chemin


# ---------------------------------------------------------------- accessibilité de base

class _Audit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.h1 = 0
        self.titre = ""
        self._dans_titre = False
        self.labels_for: set[str] = set()
        self.dans_label = 0
        self.champs: list[tuple[str, dict, bool]] = []
        self.images: list[dict] = []
        self._pile: list[tuple[str, dict, list[str]]] = []  # boutons et liens en cours, avec leur texte
        self.sans_nom: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self._dans_titre = True
        elif tag == "label":
            self.dans_label += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        elif tag in ("input", "select", "textarea"):
            if a.get("type") not in ("hidden", "submit", "button"):
                self.champs.append((tag, a, self.dans_label > 0))
        elif tag == "img":
            self.images.append(a)
        if tag in ("button", "a"):
            self._pile.append((tag, a, []))
        elif tag in ("svg", "img") and self._pile and (a.get("aria-label") or a.get("alt")):
            self._pile[-1][2].append(a.get("aria-label") or a.get("alt"))

    def handle_endtag(self, tag):
        if tag == "title":
            self._dans_titre = False
        elif tag == "label":
            self.dans_label -= 1
        elif tag in ("button", "a") and self._pile and self._pile[-1][0] == tag:
            _, a, textes = self._pile.pop()
            if not ("".join(textes).strip() or a.get("aria-label") or a.get("aria-labelledby") or a.get("title")):
                self.sans_nom.append(f"<{tag} {a}>")

    def handle_data(self, data):
        if self._dans_titre:
            self.titre += data
        for _, _, textes in self._pile:
            textes.append(data)


@pytest.mark.parametrize("profil", [ID_BRINDILLE, ID_MARCEAU])
def test_accessibilite_de_base(profil):
    m = monde()
    c = m.connecter(profil)
    chemins = ["/", "/etages/0", "/etages/0/quetes/101", "/grimpeurs", "/grimpeurs?quoi=quete:101", "/grimpeurs/1",
               "/grimpeurs/1?edition=1", "/regles", "/n-existe-pas"]
    if profil == ID_MARCEAU:
        chemins += ["/grimpeurs/2?edition=1", "/admin", "/admin/grimpeurs", "/admin/etages", "/admin/etages/0",
                    "/admin/journal"]
    for chemin in chemins:
        a = _Audit()
        a.feed(c.get(chemin).text)
        assert a.lang == "fr", chemin
        assert a.titre.strip(), chemin
        assert a.h1 == 1, (chemin, a.h1)
        for tag, attrs, enveloppe in a.champs:
            nomme = (enveloppe or attrs.get("id") in a.labels_for or attrs.get("aria-label")
                     or attrs.get("aria-labelledby"))
            assert nomme, (chemin, tag, attrs)
        for img in a.images:
            assert "alt" in img, (chemin, img)
        assert not a.sans_nom, (chemin, a.sans_nom)


def test_inscription_accessible():
    m = monde()
    c = m.connecter(ID_NOUVELLE)
    a = _Audit()
    a.feed(c.get("/inscription").text)
    assert a.lang == "fr" and a.h1 == 1 and a.champs
    for tag, attrs, enveloppe in a.champs:
        assert enveloppe or attrs.get("id") in a.labels_for or attrs.get("aria-label"), (tag, attrs)
    assert re.search(r'maxlength="30"', c.get("/inscription").text)
