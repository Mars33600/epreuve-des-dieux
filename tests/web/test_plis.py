"""Retour de recette v4 : tout ce qui grossit avec les étages est plié par défaut.

L'étage en cours reste au premier niveau ; les étages précédents passent dans « Étages précédents », un
`<details>` par étage. Sur /grimpeurs, le « qui a fait… ? » est rangé par étage, et chaque réponse arrive à
l'ouverture (morceau de page, `Accept: text/html-fragment`) avec les mêmes contrôles d'accès que la page.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from epreuve.web.demo import ID_MARCEAU
from epreuve.web.vues import separer_courant
from tests.web.outils import ID_BRINDILLE, SITE, monde

FRAGMENT = {"Accept": "text/html-fragment"}
APP_JS = Path(__file__).resolve().parents[2] / "src" / "epreuve" / "web" / "static" / "app.js"


def deux_etages(**kw):
    """L'étage 0 terminé, l'étage 1 ouvert : un étage en cours et un étage précédent."""
    m = monde(**kw)
    m.depot._etages[1] = replace(m.depot._etages[1], statut="termine")
    m.depot._etages[2] = replace(m.depot._etages[2], statut="ouvert")
    return m


def balise(html: str, ident: str) -> str:
    """La balise ouvrante de l'élément `id="…"`."""
    return re.search(rf'<[a-z][a-z0-9]* [^>]*id="{ident}"[^>]*>', html).group(0)


def apres(html: str, ident: str) -> str:
    return html[html.index(f'id="{ident}"'):]


# ---------------------------------------------------------------- l'étage en cours


def test_separer_courant():
    class E:
        def __init__(self, statut):
            self.statut = statut

    termine, ouvert = E("termine"), E("ouvert")
    assert separer_courant([], lambda e: e) == (None, [])
    assert separer_courant([ouvert, termine], lambda e: e) == (ouvert, [termine])
    # Plus d'étage ouvert (fin de l'épreuve) : le plus récent reste au premier niveau.
    autre = E("termine")
    assert separer_courant([termine, autre], lambda e: e) == (termine, [autre])


# ---------------------------------------------------------------- tableau de bord


def test_progression_etage_en_cours_visible_et_precedents_plies():
    html = deux_etages().connecter(ID_BRINDILLE).get("/tableau-de-bord").text
    assert balise(html, "tb1").startswith("<h3")  # l'étage en cours : sa carte, comme avant
    bloc = balise(html, "precedents")
    assert bloc.startswith('<details class="card pli"') and " open" not in bloc
    assert "Étages précédents (1)" in html
    # L'étage 0 est dans le bloc replié, lui-même plié, avec l'essentiel sur une ligne.
    assert html.index('id="precedents"') < html.index('id="tb0"')
    assert balise(html, "tb0") == '<details class="pli" id="tb0">'
    resume = apres(html, "tb0").split("</summary>")[0]
    assert "Étage 0 · Le Seuil" in resume and re.search(r"\d/4 points · \d+/\d+", resume)
    assert "Blocs à faire ensuite" in html  # au plus 6 blocs de l'étage en cours : pas plié


def test_progression_sans_etage_precedent_pas_de_bloc():
    html = monde().connecter(ID_BRINDILLE).get("/tableau-de-bord").text
    assert "Étages précédents" not in html and balise(html, "tb0").startswith("<h3")


def test_succes_donjons_plies_et_etages_precedents_replies():
    html = deux_etages().connecter(ID_BRINDILLE).get("/tableau-de-bord?onglet=succes").text
    assert html.count('<details class="dj-ligne">') == 4 and "dj-ligne\" open" not in html
    assert balise(html, "etage1").startswith("<section")  # l'étage en cours : visible
    assert " open" not in balise(html, "precedents")
    assert balise(html, "etage0") == '<details class="pli" id="etage0">'
    assert "donjons en full succès" in apres(html, "etage0").split("</summary>")[0]
    assert html.index('id="precedents"') < html.index('id="etage0"')


def test_lien_donjons_a_completer_vise_l_ancre_que_le_script_deplie():
    c = deux_etages().connecter(ID_BRINDILLE)
    assert "/tableau-de-bord?onglet=succes&amp;reste=1#etage0" in c.get("/tableau-de-bord").text
    assert 'id="etage0"' in c.get("/tableau-de-bord?onglet=succes&reste=1").text
    # Sans navigateur, on vérifie le contrat du script : l'ancre déplie la cible et ses ancêtres.
    js = APP_JS.read_text(encoding="utf-8")
    assert 'addEventListener("hashchange", ouvrirAncre)' in js and "ouvrirAncre();" in js
    assert 'cible.closest("details")' in js and "d.open = true" in js


# ---------------------------------------------------------------- grimpeurs : « qui a fait… ? »


def test_qui_a_fait_un_depliant_par_etage_le_plus_recent_d_abord():
    html = deux_etages().connecter(ID_BRINDILLE).get("/grimpeurs").text
    assert html.index('id="qui-e1"') < html.index('id="qui-e0"') and 'id="qui-e2"' not in html
    assert " open" in balise(html, "qui-e1")  # l'étage en cours, déroulé
    e0 = balise(html, "qui-e0")
    assert " open" not in e0 and 'data-qui-url="/grimpeurs?etage=0"' in e0
    assert 'href="/grimpeurs?etage=0#qui-e0"' in html  # repli sans script
    assert 'id="qui-0-points"' not in html  # le corps de l'étage 0 n'est pas dans la page
    # Les rubriques et les objectifs de l'étage en cours sont pliés, sans réponse écrite.
    for ident in ("qui-1-points", "qui-1-vaincus", "qui-1-succes", "qui-1-dj-4"):
        assert " open" not in balise(html, ident), ident
    assert " open" not in balise(html, "qui-1-categorie-donjons") and "Qui ne l'a pas fait" not in html
    assert 'href="/grimpeurs?etage=1&amp;quoi=donjon%3A4#qui-1-donjon-4"' in html
    assert re.search(r'class="player [^"]*"', html) and "player target" not in html


def test_fragment_d_un_etage_precedent_et_de_sa_reponse():
    c = deux_etages().connecter(ID_BRINDILLE)
    r = c.get("/grimpeurs?etage=0", headers=FRAGMENT)
    assert r.status_code == 200 and "<html" not in r.text and "<footer" not in r.text
    for ident in ("qui-0-points", "qui-0-vaincus", "qui-0-succes", "qui-0-principaux"):
        assert ident in r.text and " open" not in balise(r.text, ident)
    r = c.get("/grimpeurs?etage=0&quoi=bloc:1", headers=FRAGMENT)
    assert r.status_code == 200 and "<html" not in r.text
    assert "Qui ne l'a pas fait <small>5 sur 10 actifs · le bloc « Bloc 1 · Incarnam »" in r.text
    assert "Qui l'a fait (peut accompagner)" in r.text and 'class="person miss"' in r.text
    assert re.search(r'data-manque="[\d ]+" data-fait="[\d ]+"', r.text)
    # Le même nombre d'actifs que la page d'étage (la même vue)
    assert "sur 10 actifs" in c.get("/grimpeurs?etage=0&quoi=categorie:donjons", headers=FRAGMENT).text


def test_fragment_requetes_invalides():
    c = deux_etages().connecter(ID_BRINDILLE)
    assert c.get("/grimpeurs", headers=FRAGMENT).status_code == 422
    assert c.get("/grimpeurs?etage=0&quoi=bloc:999", headers=FRAGMENT).status_code == 404
    assert c.get("/grimpeurs?etage=0&quoi=n-importe-quoi", headers=FRAGMENT).status_code == 404
    assert c.get("/grimpeurs?etage=0&quoi=categorie:inconnue", headers=FRAGMENT).status_code == 404
    assert c.get("/grimpeurs?etage=99", headers=FRAGMENT).status_code == 404


def test_fragment_d_un_etage_scelle_jamais_montre():
    m = deux_etages()
    for ident in (ID_BRINDILLE, ID_MARCEAU):  # même l'admin : la page ne liste pas les étages scellés
        r = m.connecter(ident).get("/grimpeurs?etage=2&quoi=categorie:donjons", headers=FRAGMENT)
        assert r.status_code == 404 and "Forêt" not in r.text
    html = m.connecter(ID_BRINDILLE).get("/grimpeurs?etage=2&quoi=categorie:donjons").text
    assert "qui-e2" not in html and "Forêt" not in html


def test_fragment_refuse_au_visiteur_et_pendant_le_teaser():
    m = deux_etages()
    r = m.client().get("/grimpeurs?etage=0&quoi=bloc:1", headers=FRAGMENT)
    assert r.status_code == 303 and "Qui ne l'a pas fait" not in r.text
    m = deux_etages(mode="teaser", maintenant=datetime(2026, 11, 1, tzinfo=UTC))
    r = m.connecter(ID_BRINDILLE).get("/grimpeurs?etage=0&quoi=bloc:1", headers=FRAGMENT)
    assert r.status_code == 303 and r.headers["location"] == "/" and "Qui ne l'a pas fait" not in r.text
    r = m.connecter(ID_MARCEAU).get("/grimpeurs?etage=0&quoi=bloc:1", headers=FRAGMENT)
    assert r.status_code == 200 and "Qui ne l'a pas fait" in r.text  # l'admin voit le site pendant le teaser


def test_repli_sans_javascript_deplie_l_objectif_d_un_etage_precedent():
    html = deux_etages().connecter(ID_BRINDILLE).get("/grimpeurs?etage=0&quoi=bloc:1").text
    assert " open" in balise(html, "qui-e0") and " open" in balise(html, "qui-e1")
    assert " open" in balise(html, "qui-0-principaux") and " open" not in balise(html, "qui-0-secondaires")
    assert " open" not in balise(html, "qui-0-points")
    objectif = balise(html, "qui-0-bloc-1")
    assert " open" in objectif and 'data-charge="1"' in objectif
    assert "5 sur 10 actifs" in apres(html, "qui-0-bloc-1").split("</details>")[0]
    assert html.count("player target") == 5  # les fiches suivent la réponse, comme avant
    # Un succès : sa rubrique et le dépliant de son donjon s'ouvrent.
    html = deux_etages().connecter(ID_BRINDILLE).get("/grimpeurs?etage=0&quoi=case:12").text
    assert " open" in balise(html, "qui-0-succes") and " open" in balise(html, "qui-0-dj-1")
    assert " open" not in balise(html, "qui-0-dj-2") and " open" in balise(html, "qui-0-case-12")


def test_repli_etage_seul_deroule_son_corps():
    html = deux_etages().connecter(ID_BRINDILLE).get("/grimpeurs?etage=0&quoi=bloc:999").text
    assert " open" in balise(html, "qui-e0") and 'id="qui-0-points"' in html
    assert "Qui ne l'a pas fait" not in html


def test_qui_a_fait_page_et_fragments_sans_script_en_ligne():
    c = deux_etages().connecter(ID_BRINDILLE)
    for chemin, entetes in (("/grimpeurs", {}), ("/grimpeurs?etage=0", FRAGMENT),
                            ("/grimpeurs?etage=0&quoi=bloc:1", FRAGMENT)):
        r = c.get(chemin, headers=entetes)
        assert "<script>" not in r.text and " style=" not in r.text and "onclick" not in r.text, chemin


# ---------------------------------------------------------------- fiche d'un grimpeur, admin


def test_fiche_etages_precedents_plies():
    c = deux_etages().connecter(ID_BRINDILLE)
    html = c.get("/grimpeurs/1").text
    assert balise(html, "etage1").startswith("<h2")
    assert " open" not in balise(html, "precedents") and balise(html, "etage0") == '<details class="pli" id="etage0">'
    assert "Étages précédents (1)" in html
    # Dans l'étage en cours, les longues listes sont pliées ; « Le détail à cocher » reste ouvert sur sa fiche.
    courant = html[html.index('id="etage1"'):html.index('id="precedents"')]
    assert '<details class="pli">' in courant and "<details class=\"pli\" open" not in courant
    assert "<details open>" in courant
    assert "<details open>" not in html[html.index('id="precedents"'):]


def test_admin_quetes_pliees_et_retour_sur_l_ancre():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    html = c.get("/admin/etages/0").text
    assert balise(html, "quetes") == '<details class="card pli" id="quetes">'
    t = m.csrf(c)
    r = c.post("/admin/quetes/101", data={"csrf": t, "etage": "0", "nom": "L'Appel"}, headers={"Origin": SITE})
    assert r.status_code == 303 and r.headers["location"].endswith("#quetes")
