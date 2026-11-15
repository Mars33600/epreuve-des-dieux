"""Recensement des métiers (15/11) : la saisie sur le tableau de bord et la page Métiers."""

import re

from tests.web.outils import ID_BRINDILLE, ID_MARCEAU, SITE, monde


def _declarer(m, c, **niveaux):
    html = c.get("/tableau-de-bord").text
    jeton = re.search(r'name="csrf" value="([^"]*)"', html).group(1)
    data = {"csrf": jeton, **{f"metier_{k}": v for k, v in niveaux.items()}}
    return c.post("/grimpeurs/moi/metiers", data=data, headers={"Origin": SITE})


def test_declarer_ses_metiers_puis_les_retrouver():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    html = c.get("/tableau-de-bord").text
    assert 'id="mesMetiers"' in html and "Mes métiers" in html and 'name="metier_bijoutier"' in html
    r = _declarer(m, c, bijoutier="25", tailleur="", mineur="0")
    assert r.status_code == 303 and r.headers["location"] == "/tableau-de-bord?fait=metiers#mesMetiers"
    html = c.get("/tableau-de-bord?fait=metiers").text
    assert "Métiers enregistrés." in html
    assert 'name="metier_bijoutier" min="0" max="200" inputmode="numeric" value="25"' in html
    assert [(n.metier, n.niveau) for n in m.depot._metiers.values()] == [("bijoutier", 25)]
    # Une nouvelle saisie remplace la précédente : le bijoutier vidé disparaît.
    _declarer(m, c, tailleur="12")
    assert [(n.metier, n.niveau) for n in m.depot._metiers.values()] == [("tailleur", 12)]


def test_niveau_invalide_refuse():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    r = _declarer(m, c, bijoutier="250")
    assert r.headers["location"] == "/tableau-de-bord?erreur=metier#mesMetiers" and not m.depot._metiers
    assert "Un niveau de métier est un nombre de 1 à 200" in c.get("/tableau-de-bord?erreur=metier").text


def test_page_metiers_recherche_par_niveau():
    m = monde()
    _declarer(m, m.connecter(ID_BRINDILLE), bijoutier="25")
    c = m.connecter(ID_MARCEAU)
    html = c.get("/metiers").text
    assert "Métiers de la guilde" in html and 'href="/metiers"' in html
    assert 'Bijoutier <span class="pli-cpt num">(1 · max 25)' in html
    html = c.get("/metiers?metier=bijoutier&min=20").text
    assert "Bijoutier niveau 20 ou plus : 1 grimpeur" in html and "Brindille</a> <b class=\"num\">niv. 25" in html
    assert "Bijoutier niveau 30 ou plus : 0 grimpeur" in c.get("/metiers?metier=bijoutier&min=30").text
    assert "niveau 1 ou plus" in c.get("/metiers?metier=bijoutier&min=abc").text  # minimum illisible : 1
    autre = c.get("/grimpeurs/1").text
    assert "Ses métiers" in autre and "Bijoutier <b class=\"num\">niv. 25</b>" in autre


def test_page_metiers_reservee_aux_grimpeurs():
    assert monde().client().get("/metiers").status_code in (303, 401)
