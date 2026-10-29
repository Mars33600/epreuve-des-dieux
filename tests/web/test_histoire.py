"""L'histoire de Shadoaze : le prologue de la première connexion, puis la page « L'histoire » du menu."""

from __future__ import annotations

from epreuve.web.demo import ID_NOUVELLE
from epreuve.web.histoire import paragraphes
from tests.web.outils import ID_BRINDILLE, SITE, monde

TEXTE_CLE = ["Il existe, quelque part dans le Monde des Douze", "Tous… sauf un.", "Goultard.",
             "Oserez-vous franchir le seuil ?"]


def test_le_fichier_de_contenu_garde_le_texte_de_shadoaze():
    textes = [t for _, t in paragraphes()]
    for extrait in TEXTE_CLE:
        assert any(extrait in t for t in textes), extrait
    assert paragraphes()[0][0] == "lead" and paragraphes()[-1][0] == "final"


def test_page_histoire_dans_le_menu():
    c = monde().connecter(ID_BRINDILLE)
    html = c.get("/").text
    assert 'href="/histoire"' in html
    page = c.get("/histoire").text
    assert "Oserez-vous franchir le seuil ?" in page and 'aria-current="page"' in page
    assert "Merci Duffus" in page


def test_prologue_a_la_premiere_connexion_puis_plus_jamais():
    m = monde()
    m.depot._liste[ID_NOUVELLE] = "actif"
    c = m.connecter(ID_NOUVELLE)
    r = c.post("/inscription", data={"csrf": m.csrf(c, "/inscription"), "pseudo": "Lune"}, headers={"Origin": SITE})
    assert r.status_code == 303
    html = c.get("/").text
    assert 'class="prologue"' in html and "Entrer dans la tour" in html and "Oserez-vous" in html
    assert 'class="pyramide"' not in html  # le prologue passe avant la tour
    r = c.post("/histoire/vu", data={"csrf": m.csrf(c, "/histoire")}, headers={"Origin": SITE})
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert m.depot._grimpeurs[14].prologue_vu is True
    html = c.get("/").text
    assert 'class="prologue"' not in html and 'class="pyramide"' in html


def test_prologue_vu_refuse_sans_jeton_csrf():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    assert c.post("/histoire/vu", data={}, headers={"Origin": SITE}).status_code in (400, 403)
