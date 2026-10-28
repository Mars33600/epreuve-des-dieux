"""E4 : le tableau de bord et les outils (pages, accès, CSP, cases du lot B réutilisées)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pytest

from epreuve.outils import aspirer, lecture
from epreuve.web.demo import ID_MARCEAU, ID_NOUVELLE
from tests.web.outils import ID_BRINDILLE, ID_OMBREVIVE, cocher, monde

OUTILS = ["/outils", "/outils/almanax", "/outils/calculateur-drop", "/outils/xp-metiers", "/outils/craft",
          "/outils/elevage", "/outils/classes", "/outils/classes/2"]


def test_visiteur_et_membre_sans_fiche_ne_voient_ni_tableau_ni_outils():
    c = monde().client()
    for chemin in ["/tableau-de-bord", *OUTILS, "/outils/donnees/craft.json"]:
        assert c.get(chemin).status_code == 303, chemin
    c = monde().connecter(ID_NOUVELLE)
    for chemin in ["/tableau-de-bord", *OUTILS]:
        r = c.get(chemin)
        assert r.status_code == 303 and r.headers["location"] == "/inscription", chemin


def test_pas_d_outil_pendant_le_teaser():
    m = monde(mode="teaser", maintenant=datetime(2026, 11, 1, tzinfo=UTC))
    c = m.client()
    assert c.get("/outils").headers["location"] == "/"
    assert c.get("/tableau-de-bord").headers["location"] == "/"


def test_pages_sans_script_ni_style_en_ligne_et_merci_duffus():
    c = monde().connecter(ID_BRINDILLE)
    for chemin in ["/tableau-de-bord", "/tableau-de-bord?onglet=succes", *OUTILS]:
        r = c.get(chemin)
        assert r.status_code == 200, chemin
        assert "Merci Duffus" in r.text and "duffus.fr" in r.text
        assert not re.search(r"<script(?![^>]*\bsrc=)", r.text), chemin
        assert " style=" not in r.text and "onclick=" not in r.text, chemin
        assert 'href="/outils"' in r.text and 'href="/tableau-de-bord"' in r.text
        assert "unsafe-inline" not in r.headers["content-security-policy"]


def test_tableau_progression_reprend_les_chiffres_de_l_etage():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    html = c.get("/tableau-de-bord").text
    # le même calcul que la page d'étage : le tableau ne recompte rien
    assert "/4 points" in html and 'href="/etages/0"' in html
    etage = c.get("/etages/0").text
    point = re.search(r'data-moi="points">(\d)', etage).group(1)
    assert re.search(rf'<span class="total[^"]*">{point}<small>/4 points', html)
    assert "À faire ensuite" in html


def test_onglet_succes_liste_les_5_cases_de_chaque_donjon_et_se_coche_par_l_api():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    html = c.get("/tableau-de-bord?onglet=succes").text
    cases = re.findall(r'data-ref="case:(\d+)"', html)
    donjons = re.findall(r'data-donjon="(\d+)"', html)
    assert donjons and len(cases) == 5 * len(donjons)
    assert 'data-donjon-tout="' in html
    # Les mêmes cases que le lot B : la coche passe par /api/coches, puis le tableau la montre cochée.
    r = cocher(c, m.csrf(c), type="case", id=int(cases[0]), cochee=True)
    assert r.status_code == 200 and r.json()["ok"]
    apres = c.get("/tableau-de-bord?onglet=succes").text
    assert re.search(rf'data-ref="case:{cases[0]}" checked', apres)


def test_onglet_succes_seulement_ce_qui_reste():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    tout = c.get("/tableau-de-bord?onglet=succes").text
    donjon = re.search(r'data-donjon-tout="(\d+)"', tout).group(1)
    assert cocher(c, m.csrf(c), type="donjon", id=int(donjon), cochee=True).status_code == 200
    reste = c.get("/tableau-de-bord?onglet=succes&reste=1").text
    assert f'data-donjon="{donjon}"' not in reste
    assert f'data-donjon="{donjon}"' in c.get("/tableau-de-bord?onglet=succes").text


def test_grimpeur_en_pause_voit_ses_cases_cochables_et_l_admin_sans_fiche_un_message():
    c = monde().connecter(ID_OMBREVIVE)
    assert "Tu es en pause" in c.get("/tableau-de-bord").text
    r = monde().connecter(ID_MARCEAU).get("/tableau-de-bord")
    assert r.status_code in (200, 409)


def test_aucun_etage_scelle_dans_le_tableau():
    html = monde().connecter(ID_BRINDILLE).get("/tableau-de-bord?onglet=succes").text
    for interdit in ["Les Champs Murmurants", "Repaire des Murmures", "/etages/1", "case:41"]:
        assert interdit not in html


def test_almanax_aujourd_hui_et_hors_dates():
    m = monde(maintenant=datetime(2026, 11, 13, 12, 0, tzinfo=UTC))
    c = m.connecter(ID_BRINDILLE)
    html = c.get("/outils/almanax").text
    assert "13/11/2026" in html and "aujourd'hui" in html and "Les jours suivants" in html
    assert "Pas d'offrande connue" in c.get("/outils/almanax?jour=2030-01-01").text
    assert c.get("/outils/almanax?jour=n-importe-quoi").status_code == 404


def test_classes_et_donnees():
    c = monde().connecter(ID_BRINDILLE)
    assert c.get("/outils/classes/999999").status_code == 404
    assert "Flèche de Recul" in c.get(f"/outils/classes/{_id('Crâ')}").text
    r = c.get("/outils/donnees/craft.json")
    assert r.status_code == 200 and json.loads(r.text)["recettes"]
    assert c.get("/outils/donnees/classes.json").status_code == 404
    assert c.get("/outils/donnees/..%2Fx.json").status_code == 404


def _id(nom: str) -> int:
    return next(c["id"] for c in lecture.classes() if c["nom"] == nom)


# ---------------------------------------------------------------- données (JSON versionné)


def test_donnees_coherentes():
    craft = lecture.charger("craft")
    assert len(craft["recettes"]) > 4000 and set(craft["metiers"]) >= {"11", "15", "27"}
    for resultat, metier, _niveau, ingredients in craft["recettes"]:
        assert str(metier) in craft["metiers"] and ingredients
        assert str(resultat) in craft["objets"] and all(str(i) in craft["objets"] for i, _ in ingredients)
    classes = lecture.classes()
    assert len(classes) == 19 and all(c["sorts"] for c in classes)
    montures = lecture.charger("montures")
    assert set(montures) == {"dragodinde", "muldo", "volkorne"} and all(montures.values())
    premier, dernier = lecture.bornes_almanax()
    assert (dernier - premier).days + 1 == len(lecture.charger("almanax"))  # un jour par date, sans trou


def test_aucune_donnee_d_utilisateur_duffus_dans_les_fichiers():
    for nom in ("craft", "montures", "classes", "almanax"):
        texte = lecture.fichier(nom).read_text(encoding="utf-8")
        assert "user_id" not in texte and "profile_id" not in texte
    assert not {"builder", "user_mounts", "user_quest", "profiles"} & set(aspirer.__dict__)


@pytest.mark.parametrize(("objet", "attendu"), [
    ({"craftxpratio": 80, "typeid": 1}, 80), ({"craftxpratio": -1, "typeid": 1}, 50),
    ({"craftxpratio": None, "typeid": 2}, 100), ({"craftxpratio": -1, "typeid": 3}, 0),
])
def test_ratio_xp_de_craft(objet, attendu):
    assert aspirer.ratio_xp(objet, {1: 50, 2: -1}) == attendu


def test_montures_rangees_par_nom():
    items = [{"id": 2, "name": "B", "typeid": 331}, {"id": 1, "name": "A", "typeid": 331},
             {"id": 3, "name": "C", "typeid": 999}]
    assert aspirer.montures_de(items)["dragodinde"] == [[1, "A"], [2, "B"]]
    assert aspirer.montures_de(items)["muldo"] == []

