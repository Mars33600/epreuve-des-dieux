"""Le tableau de bord, seule présentation d'un grimpeur (retour de recette v4 : « Ma fiche » faisait doublon).

Trois regards sur le même gabarit (`web/tableau.py`) : soi (cochable, profil, blocs à faire ensuite), un autre
grimpeur (lecture seule), un admin (cochable pour ce grimpeur, motif obligatoire). Les anciennes adresses
(`/grimpeurs/{id}`, `/grimpeurs/moi`) restent valables.
"""

from __future__ import annotations

import re

from epreuve.web.demo import ID_MARCEAU
from tests.web.outils import AVANT_OUVERTURE, ID_BRINDILLE, ID_FOURBE, ID_OMBREVIVE, SITE, monde


def cases(html: str) -> list[str]:
    """Les balises `<input data-ref=…>` de la page (cases de donjon et blocs du guide)."""
    return re.findall(r'<input type="checkbox" data-ref="[^"]+"[^>]*>', html)


# ---------------------------------------------------------------- soi


def test_mon_tableau_cochable_avec_le_profil():
    c = monde().connecter(ID_BRINDILLE)
    html = c.get("/tableau-de-bord").text
    assert '<form method="post" action="/grimpeurs/moi"' in html and 'id="niveau"' in html  # niveau : comme la fiche
    assert "Modifier mon pseudo, ma classe ou mon niveau" in html and "Blocs à faire ensuite" in html
    assert "data-cible" not in html and 'id="motif"' not in html and "Ses blocs du guide" not in html
    succes = c.get("/tableau-de-bord?onglet=succes").text
    assert cases(succes) and not any("disabled" in x for x in cases(succes))
    assert 'href="/tableau-de-bord?onglet=succes&amp;reste=1">Seulement ce qui me reste' in succes


def test_profil_enregistre_revient_sur_le_tableau():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    r = c.post("/grimpeurs/moi", data={"csrf": m.csrf(c), "pseudo": "Brindille", "classe": "Iop", "niveau": "30"},
               headers={"Origin": SITE})
    assert r.headers["location"] == "/tableau-de-bord?fait=1"
    html = c.get(r.headers["location"]).text
    assert "Fiche enregistrée." in html and "niveau 30" in html
    r = c.post("/grimpeurs/moi", data={"csrf": m.csrf(c), "pseudo": "B"}, headers={"Origin": SITE})
    assert r.headers["location"] == "/tableau-de-bord?erreur=pseudo"
    assert "entre 2 et 30 caractères" in c.get(r.headers["location"]).text


def test_mon_id_redirige_vers_mon_tableau_avec_l_onglet():
    c = monde().connecter(ID_BRINDILLE)
    assert c.get("/grimpeurs/1").headers["location"] == "/tableau-de-bord"
    assert c.get("/grimpeurs/1?onglet=succes").headers["location"] == "/tableau-de-bord?onglet=succes"
    assert c.get("/grimpeurs/1?onglet=succes&reste=1").headers["location"] == "/tableau-de-bord?onglet=succes&reste=1"
    r = c.get("/grimpeurs/moi")  # ancienne adresse de « Ma fiche »
    assert r.status_code == 303 and r.headers["location"] == "/tableau-de-bord"


def test_en_pause_la_note_n_apparait_que_sur_son_tableau():
    m = monde()
    assert "Tu es en pause" in m.connecter(ID_OMBREVIVE).get("/tableau-de-bord").text
    autre = m.connecter(ID_BRINDILLE).get("/grimpeurs/8").text
    assert "Tu es en pause" not in autre and "En pause" in autre


# ---------------------------------------------------------------- un autre grimpeur


def test_autre_grimpeur_en_lecture_seule():
    c = monde().connecter(ID_BRINDILLE)
    for chemin in ("/grimpeurs/3", "/grimpeurs/3?onglet=succes", "/grimpeurs/3?edition=1"):
        html = c.get(chemin).text
        assert "<title>Tableau de bord de Mirelune · L'Épreuve des Dieux</title>" in html, chemin
        assert "Lecture seule" in html and "Tableau de bord de Mirelune</h2>" in html, chemin
        assert cases(html) and all("disabled" in x for x in cases(html)), chemin
        assert "data-cible" not in html and 'id="motif"' not in html and "data-donjon-tout" not in html, chemin
        assert 'action="/grimpeurs/moi"' not in html and "Blocs à faire ensuite" not in html, chemin


def test_onglets_par_query_string_sur_la_vue_d_un_autre():
    c = monde().connecter(ID_BRINDILLE)
    html = c.get("/grimpeurs/3").text
    assert '<a href="/grimpeurs/3" aria-current="page">Progression</a>' in html
    assert '<a href="/grimpeurs/3?onglet=succes">Succès de donjon</a>' in html
    reste = c.get("/grimpeurs/3?onglet=succes&reste=1").text
    assert '<a href="/grimpeurs/3?onglet=succes" aria-current="page">Succès de donjon</a>' in reste
    assert 'href="/grimpeurs/3?onglet=succes">Tout afficher</a>' in reste
    assert "Seulement ce qui lui reste" in c.get("/grimpeurs/3?onglet=succes").text


def test_exclu_introuvable_sauf_pour_l_admin():
    m = monde()
    assert m.connecter(ID_BRINDILLE).get("/grimpeurs/13").status_code == 404
    assert m.connecter(ID_BRINDILLE).get("/grimpeurs/abc").status_code in (404, 422)
    assert m.connecter(ID_MARCEAU).get("/grimpeurs/13").status_code == 200
    assert m.connecter(ID_FOURBE).get("/grimpeurs/3").status_code == 403  # un exclu ne voit plus le site


# ---------------------------------------------------------------- admin


def test_admin_coche_pour_le_grimpeur_avec_motif():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    for chemin in ("/grimpeurs/3", "/grimpeurs/3?onglet=succes", "/grimpeurs/3?edition=1"):
        html = c.get(chemin).text
        assert '<main class="outil" data-cible="3">' in html and 'id="motif"' in html, chemin
        assert "Mode édition (admin)" in html and "Tableau de bord de Mirelune" in html, chemin
        assert cases(html) and not any("disabled" in x for x in cases(html)), chemin
        assert 'action="/grimpeurs/moi"' not in html, chemin
    assert "data-donjon-tout" in c.get("/grimpeurs/3?onglet=succes").text
    # L'API reste le garde-fou : sans motif, refusé ; avec, enregistré et journalisé (non public).
    corps = {"type": "bloc", "id": 2, "cochee": True, "grimpeur_id": 3}
    entetes = {"X-CSRF-Token": m.csrf(c), "Origin": SITE}
    assert c.post("/api/coches", json=corps, headers=entetes).status_code == 422
    r = c.post("/api/coches", json={**corps, "motif": "rattrapage"}, headers=entetes)
    assert r.status_code == 200 and m.depot._journal[-1].details["motif"] == "rattrapage"


def test_admin_sans_fiche_n_a_pas_de_tableau_a_lui():
    c = monde().connecter(ID_MARCEAU)
    assert c.get("/tableau-de-bord").status_code == 409


# ---------------------------------------------------------------- menu et accès


def test_menu_sans_ma_fiche():
    c = monde().connecter(ID_BRINDILLE)
    for chemin in ("/", "/tableau-de-bord", "/grimpeurs/3"):
        html = c.get(chemin).text
        assert "Ma fiche" not in html and "ma-fiche" not in html, chemin
        assert '<a href="/tableau-de-bord"' in html and "<b>Brindille</b>" in html, chemin
    assert 'href="/tableau-de-bord" aria-current="page">Tableau de bord' in c.get("/tableau-de-bord").text


def test_teaser_reserve_aux_admins():
    m = monde(mode="teaser", maintenant=AVANT_OUVERTURE)
    assert m.connecter(ID_BRINDILLE).get("/grimpeurs/3").status_code == 303  # le teaser, rien d'autre
    assert m.connecter(ID_BRINDILLE).get("/grimpeurs/moi").status_code == 303
    r = m.connecter(ID_MARCEAU).get("/grimpeurs/3")
    assert r.status_code == 200 and "Mode teaser" in r.text and 'data-cible="3"' in r.text
