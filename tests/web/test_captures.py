"""Module E1 sur le site : connexion requise, CSP, pied de page, écritures protégées, entraide."""

from __future__ import annotations

import re

import pytest

from tests.web.outils import AVANT_OUVERTURE, ID_ADMIN_SUP, ID_BRINDILLE, ID_FOURBE, ID_OMBREVIVE, SITE, monde

PAGES = ["/archimonstres", "/archimonstres?tri=zone", "/archimonstres?tri=etape", "/archimonstres?onglet=boss",
         "/archimonstres?onglet=boss&tri=niveau&etat=manquants", "/archimonstres?qui=32",
         "/avis-de-recherche", "/avis-de-recherche?milice=Astrub&emeraude=1&qui=1",
         "/avis-de-recherche/fouduglen-lecureuil"]


@pytest.fixture(scope="module")
def m():
    return monde()


def ecrire(c, csrf, url, corps, origine=SITE):
    return c.post(url, json=corps, headers={"X-CSRF-Token": csrf, "Origin": origine})


@pytest.mark.parametrize("chemin", PAGES)
def test_pages_connectees(m, chemin):
    c = m.connecter(ID_BRINDILLE)
    r = c.get(chemin)
    assert r.status_code == 200
    assert "Merci Duffus" in r.text and "Archis et avis" in r.text
    assert not re.search(r"<script(?![^>]*\bsrc=)", r.text)  # aucun script en ligne
    assert " style=" not in r.text and "duffus.fr/" not in r.text.replace('href="https://duffus.fr"', "")
    assert "supabase" not in r.text  # jamais les images du stockage de Duffus
    assert "default-src 'self'" in r.headers["content-security-policy"]


@pytest.mark.parametrize("chemin", ["/archimonstres", "/avis-de-recherche", "/avis-de-recherche/fouduglen-lecureuil"])
def test_connexion_requise(m, chemin):
    r = m.client().get(chemin)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert m.client().get("/api/archimonstres/archi/32/qui").status_code == 401


def test_teaser_masque_le_module():
    t = monde(mode="teaser", maintenant=AVANT_OUVERTURE)
    c = t.connecter(ID_BRINDILLE)
    assert c.get("/archimonstres").status_code == 303
    assert c.get("/api/avis-de-recherche/1/qui").status_code == 404


def test_exclu_refuse(m):
    c = m.connecter(ID_FOURBE)
    assert c.get("/archimonstres").status_code == 403


def test_compresse(m):
    c = m.connecter(ID_BRINDILLE)
    r = c.get("/archimonstres", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip" and r.text.count('class="cp-carte') == 286


def test_compteur_et_entraide():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    csrf = m.csrf(c, "/archimonstres")
    assert ecrire(c, csrf, "/api/archimonstres/archi/32", {"delta": 1}).json() == {"ok": True, "nombre": 1}
    assert ecrire(c, csrf, "/api/archimonstres/archi/32", {"delta": 1}).json()["nombre"] == 2
    assert ecrire(c, csrf, "/api/archimonstres/boss/2", {"delta": 1}).json()["nombre"] == 1
    qui = c.get("/api/archimonstres/archi/32/qui").json()
    assert [(p["pseudo"], p["nombre"]) for p in qui["ont"]] == [("Brindille", 2)]
    assert "Brindille" not in [p["pseudo"] for p in qui["pas"]] and all("discord" not in str(p) for p in qui["pas"])
    assert "Fourbe" not in str(qui)  # les exclus n'apparaissent pas
    page = c.get("/archimonstres?qui=32").text
    assert "Qui a Blorie" in page and "×2" in page
    # Personnages : 2 → l'archi à 2 exemplaires est complet.
    r = c.post("/archimonstres/personnages", data={"csrf": csrf, "nombre": "2", "retour": "tri=etape"},
               headers={"Origin": SITE})
    assert r.status_code == 303 and r.headers["location"] == "/archimonstres?tri=etape"
    assert re.search(r"data-prog-faits>1<", c.get("/archimonstres").text)
    # Avis : capturé, puis visible pour les autres.
    assert ecrire(c, csrf, "/api/avis-de-recherche/1", {"capture": True}).json() == {"ok": True, "capture": True}
    autre = m.connecter(ID_OMBREVIVE)  # en pause : il suit quand même
    assert [p["pseudo"] for p in autre.get("/api/avis-de-recherche/1/qui").json()["ont"]] == ["Brindille"]
    r = ecrire(autre, m.csrf(autre, "/avis-de-recherche"), "/api/avis-de-recherche/1", {"capture": True})
    assert r.status_code == 200


def test_formulaires_sans_js_et_retour_sur():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    csrf = m.csrf(c, "/archimonstres")
    r = c.post("/archimonstres/archi/32", data={"csrf": csrf, "delta": "1", "retour": "q=blo&x=//evil.com&tri=zone"},
               headers={"Origin": SITE})
    assert r.status_code == 303 and r.headers["location"] == "/archimonstres?q=blo&tri=zone#archi-32"
    r = c.post("/avis-de-recherche/1", data={"csrf": csrf, "capture": "1", "vers": "https://evil.com/x"},
               headers={"Origin": SITE})
    assert r.status_code == 303 and r.headers["location"].startswith("/avis-de-recherche")
    vers = "/avis-de-recherche/fouduglen-lecureuil"
    r = c.post("/avis-de-recherche/1", data={"csrf": csrf, "capture": "0", "vers": vers}, headers={"Origin": SITE})
    assert r.headers["location"] == "/avis-de-recherche/fouduglen-lecureuil"


def test_ecritures_refusees():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    csrf = m.csrf(c, "/archimonstres")
    assert ecrire(c, "faux", "/api/archimonstres/archi/32", {"delta": 1}).status_code == 403
    assert ecrire(c, csrf, "/api/archimonstres/archi/32", {"delta": 1}, origine="https://evil.com").status_code == 403
    assert ecrire(c, csrf, "/api/archimonstres/archi/32", {"delta": 5}).status_code == 422
    assert ecrire(c, csrf, "/api/archimonstres/archi/32", {"delta": True}).status_code == 422
    assert ecrire(c, csrf, "/api/archimonstres/dragon/32", {"delta": 1}).status_code == 422
    assert ecrire(c, csrf, "/api/archimonstres/archi/99999", {"delta": 1}).status_code == 404
    assert ecrire(c, csrf, "/api/avis-de-recherche/1", {"capture": "oui"}).status_code == 422
    assert ecrire(c, csrf, "/api/avis-de-recherche/99999", {"capture": True}).status_code == 404
    assert c.get("/api/archimonstres/archi/99999/qui").status_code == 404
    assert c.get("/avis-de-recherche/inconnu").status_code == 404
    # Un admin sans fiche consulte, mais ne suit rien.
    a = m.connecter(ID_ADMIN_SUP)
    page = a.get("/archimonstres")
    assert page.status_code == 200 and "Tu n'as pas de fiche" in page.text and 'name="delta"' not in page.text
    assert ecrire(a, m.csrf(a, "/archimonstres"), "/api/archimonstres/archi/32", {"delta": 1}).status_code == 409


def test_recherche_sans_js(m):
    c = m.connecter(ID_BRINDILLE)
    html = c.get("/archimonstres?q=BLORIE").text
    visibles = re.findall(r'<li class="cp-carte[^"]*" id="archi-(\d+)"[^>]*data-nombre="\d+"[^>]*?(?<!hidden)>', html)
    assert "32" in visibles and len(visibles) == 1
    assert '<b class="num" data-affiches>1</b>' in html
