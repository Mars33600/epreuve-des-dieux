"""Tests adverses du site (lot B) : XSS, CSRF, Origin, identifiants Discord, base vide, étage sans grimpeur.

Critères 35 à 37, et l'esprit des tests adverses de la v3, réécrits pour le nouveau modèle.
"""

from __future__ import annotations

import html as html_mod
import re
from dataclasses import replace
from pathlib import Path

import pytest

from epreuve.web.demo import ID_MARCEAU, DepotDemo
from tests.web.outils import (
    ID_BRINDILLE,
    IDS_DISCORD_FABRIQUE,
    SITE,
    cocher,
    monde,
    routes_declarees,
)

XSS = "<img src=x onerror=alert(1)>"
APP_JS = Path(__file__).resolve().parents[2] / "src/epreuve/web/static/app.js"
PAGES = ["/", "/etages/0", "/etages/0/quetes/101", "/grimpeurs", "/grimpeurs?quoi=quete:101", "/grimpeurs/2",
         "/regles"]


def piege():
    """Un pseudo et un libellé de quête piégés."""
    m = monde()
    m.depot._grimpeurs[2] = replace(m.depot._grimpeurs[2], pseudo=XSS, nom_discord=XSS)
    m.depot._quetes[101] = replace(m.depot._quetes[101], nom=f"Quête {XSS}", jusqu_ou=XSS)
    return m


@pytest.mark.parametrize("profil", [ID_BRINDILLE, ID_MARCEAU])
def test_xss_par_pseudo_et_libelle_affiches_en_texte(profil):
    m = piege()
    c = m.connecter(profil)
    chemins = PAGES + (["/admin/grimpeurs", "/admin/etages/0", "/admin/journal"] if profil == ID_MARCEAU else [])
    for chemin in chemins:
        page = c.get(chemin).text
        assert XSS not in page, chemin
        assert "onerror=alert" not in page.replace(html_mod.escape(XSS), ""), chemin
    assert html_mod.escape(XSS) in c.get("/grimpeurs").text


def test_xss_dans_le_json_reste_une_donnee():
    m = piege()
    c = m.connecter(ID_BRINDILLE)
    d = c.get("/api/etages/0/manque?type=quete&id=105").json()
    assert XSS in [g["pseudo"] for g in d["pas_fait"]]  # la donnée brute, que app.js affiche avec textContent
    assert c.get("/api/etages/0/manque?type=quete&id=105").headers["content-type"].startswith("application/json")


def test_app_js_n_insere_jamais_de_donnee_en_html():
    js = APP_JS.read_text()
    # Le seul innerHTML est celui de la fiche de quête, rendue et échappée par le serveur.
    assert js.count("innerHTML =") == 1 and "t.innerHTML = await r.text()" in js
    assert "insertAdjacentHTML" not in js and "outerHTML" not in js and "document.write" not in js
    assert "eval(" not in js and "new Function" not in js
    assert re.search(r"s\.textContent = g\.pseudo", js)


@pytest.mark.parametrize("profil", [ID_BRINDILLE, ID_MARCEAU])
def test_aucun_identifiant_discord_numerique_cote_grimpeurs(profil):
    """Critère 35 : ni le HTML ni le JSON servis aux grimpeurs ne contiennent un identifiant Discord."""
    m = monde()
    c = m.connecter(profil)
    reponses = [c.get(p).text for p in PAGES + ["/etages/0/quetes/104", "/grimpeurs?quoi=categorie:donjons"]]
    reponses += [c.get(f"/api/etages/0/manque?type={t}&id={i}").text
                 for t, i in (("quete", 101), ("case", 22), ("categorie", "donjons"), ("donjon", 1))]
    if profil == ID_BRINDILLE:
        reponses.append(cocher(c, m.csrf(c), type="quete", id=107, cochee=True).text)
    for texte in reponses:
        for i in IDS_DISCORD_FABRIQUE:
            assert str(i) not in texte


def test_identifiants_discord_seulement_dans_l_admin():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    assert "300000000000000050" in c.get("/admin/grimpeurs").text  # « fiche à créer » : il faut bien l'identifier


def test_post_sans_csrf_ou_d_origine_etrangere_refuse_partout():
    """Critère 37 : chaque POST déclaré refuse un jeton absent ou faux et une origine étrangère (403)."""
    m = monde()
    c = m.connecter(ID_MARCEAU)
    t = m.csrf(c)
    CALCULS_PURS = ("/api/builder/calcul", "/api/builder/sorts")  # sans écriture : pas de CSRF
    posts = [re.sub(r"\{[^}]+\}", "1", r.path) for r in routes_declarees(m.app) if "POST" in getattr(r, "methods", ())
             if r.path not in CALCULS_PURS]
    assert len(posts) >= 14
    journal_avant = len(m.depot._journal)
    for chemin in posts:
        for donnees, entetes in (({}, {"Origin": SITE}), ({"csrf": "faux"}, {"Origin": SITE}),
                                 ({"csrf": t}, {"Origin": "https://pirate.example"})):
            r = c.post(chemin, data=donnees, headers=entetes)
            assert r.status_code == 403, (chemin, donnees, entetes)
    assert len(m.depot._journal) == journal_avant and len(m.depot._sessions) == 1


def test_csrf_d_une_autre_session_refuse():
    m = monde()
    a = m.connecter(ID_BRINDILLE)
    b = m.connecter(ID_MARCEAU)
    assert cocher(a, m.csrf(b), type="quete", id=107, cochee=True).status_code == 403


def test_cookie_de_session_falsifie():
    m = monde()
    c = m.client()
    c.cookies.set("__Host-session", "nimporte-quoi", domain="epreuve.test")
    assert "Se connecter avec Discord" in c.get("/").text
    assert c.get("/admin").status_code == 303


def test_base_sans_etage_ni_grimpeur():
    d = DepotDemo()
    d._etages, d._donjons, d._cases, d._quetes, d._grimpeurs = {}, {}, {}, {}, {}
    d._coches_cases, d._coches_quetes = {}, {}
    m = monde(depot=d)
    c = m.connecter(ID_MARCEAU)
    for chemin in ("/", "/grimpeurs", "/regles", "/admin", "/admin/grimpeurs", "/admin/etages", "/admin/journal"):
        assert c.get(chemin).status_code == 200, chemin
    assert c.get("/etages/0").status_code == 404
    assert cocher(c, m.csrf(c), type="quete", id=101, cochee=True).status_code == 409


def test_etage_ouvert_sans_aucun_actif():
    m = monde()
    for g in list(m.depot._grimpeurs.values()):
        m.depot._grimpeurs[g.id] = replace(g, statut="pause")
    c = m.connecter(ID_MARCEAU)
    html = c.get("/etages/0").text
    assert "Aucun grimpeur actif pour l'instant" in html
    assert ">Un admin pourra ouvrir le prochain étage quand la jauge sera pleine.</p>" in html
    assert "aucun grimpeur actif" in c.get("/admin/etages/0").text
    tour = c.get("/").text.split('class="pyramide"')[1]
    assert "prêt" not in tour


def test_etage_sans_contenu():
    m = monde()
    m.depot._quetes = {k: q for k, q in m.depot._quetes.items() if q.etage_id != 1}
    m.depot._donjons = {k: d for k, d in m.depot._donjons.items() if d.etage_id != 1}
    c = m.connecter(ID_BRINDILLE)
    assert c.get("/etages/0").status_code == 200 and c.get("/grimpeurs").status_code == 200


def test_numero_negatif_ou_enorme():
    c = monde().connecter(ID_BRINDILLE)
    for chemin in ("/etages/-1", "/etages/99999999999999999999", "/etages/0/quetes/-5", "/grimpeurs/0"):
        assert c.get(chemin).status_code in (404, 422), chemin


def test_erreur_interne_sans_trace():
    m = monde()
    c = m.connecter(ID_BRINDILLE)

    async def panne(*_a, **_k):
        raise RuntimeError("secret interne")

    m.depot.contenu_etage = panne
    from fastapi.testclient import TestClient

    r = TestClient(m.app, base_url=SITE, cookies=c.cookies, raise_server_exceptions=False).get("/etages/0")
    assert r.status_code == 500 and "secret interne" not in r.text
    assert r.headers["content-security-policy"].startswith("default-src 'self'")
