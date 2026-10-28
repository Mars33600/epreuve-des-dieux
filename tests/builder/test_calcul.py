"""Formules du builder, vérifiées par des builds chiffrés à la main d'après le code de Duffus (docs/lots/E3.md §3)."""

import pytest

from epreuve.builder.calcul import (
    Build,
    affichage,
    calculer,
    conditions_remplies,
    cout_points,
    nettoyer,
    panoplies_actives,
    points_disponibles,
    puissance_par_element,
)
from epreuve.builder.catalogue import Catalogue, catalogue_par_defaut

BOUFTOU = {"coiffe": 2411, "cape": 2414, "amulette": 2425, "ceinture": 2428, "bottes": 2422, "anneau1": 2419,
           "bouclier": 18666, "arme": 2416}


def test_panoplie_du_bouftou_complete_niveau_50():
    """Le cas de référence. Objets (jet max) : Force 20+15+15, Intelligence 20+15+15, Vitalité 40+15+20+30+20+20,
    Initiative 200+100, Pods 500, Puissance 15+10, Invocation 1. Bonus 8/8 : Force 50, Intelligence 50,
    Vitalité 50, PA 1, dommages Neutre, Terre, Feu 5."""
    b = Build(niveau=50, objets=BOUFTOU,
              caracs_base={"Force": 100, "Vitalité": 45, "Sagesse": 30},
              caracs_parcho={"Force": 100, "Intelligence": 50, "Vitalité": 100, "Agilité": 25})
    r = calculer(b, catalogue_par_defaut())
    t = r.totaux
    assert (t["Force"], t["Intelligence"], t["Vitalité"], t["Sagesse"], t["Agilité"], t["Chance"]) == \
        (300, 150, 340, 30, 25, 0)
    assert (t["PA"], t["PM"], t["Puissance"], t["Initiative"], t["Pods"], t["Invocations"]) == (1, 0, 25, 300, 500, 1)
    assert (t["Do Neutre"], t["Do Terre"], t["Do Feu"], t["Do Eau"]) == (5, 5, 5, 0)
    [p] = r.panoplies
    assert (p.id, p.nom, p.nb, p.max_nb) == (1, "Panoplie du Bouftou", 8, 8)
    assert dict(p.caracs) == {"Do Neutre": 5, "Do Terre": 5, "Force": 50, "Intelligence": 50, "Do Feu": 5, "PA": 1,
                              "Vitalité": 50}
    a = r.affichage
    assert (a["PA"], a["PM"], a["Vitalité"]) == (7, 3, 640)  # 6 + 1 ; 3 ; 340 + 55 + 5 × 49
    assert a["Pods"] == 3000  # 500 + 1000 + 5 × 300
    assert a["Initiative"] == 775  # 300 + 300 + 150 + 25 + 0
    assert (a["Fuite"], a["Tacle"]) == (2, 2)  # ⌊25 / 10⌋
    assert (a["Esquive PA"], a["Esquive PM"], a["Retrait PA"], a["Retrait PM"]) == (3, 3, 3, 3)
    assert (a["Prospection"], a["Invocations"]) == (100, 2)
    assert (r.points_total, r.points_depenses) == (245, 235)  # 100 + 45 + 3 × 30
    assert r.alertes == {}
    assert puissance_par_element(t) == {"Force": 325, "Intelligence": 175, "Chance": 25, "Agilité": 50}
    assert r.detail["Force"] == {"objets": [["Coiffe du Bouftou", 20], ["Amulette du Bouftou", 15],
                                            ["Ceinture du Bouftou", 15]],
                                 "panoplies": [["Panoplie du Bouftou (8)", 50]], "base": 100, "parchemin": 100}


def test_paliers_de_panoplie():
    cat = catalogue_par_defaut()
    deux = calculer(Build(50, {"coiffe": 2411, "cape": 2414}), cat)
    assert dict(deux.panoplies[0].caracs) == {"Force": 5, "Intelligence": 5, "Vitalité": 5}
    seul = calculer(Build(50, {"coiffe": 2411}), cat)
    assert seul.panoplies == [] and seul.totaux["Force"] == 20


def test_anneaux_en_double_comptent_deux_fois_et_sont_signales():
    """8 objets + le même anneau deux fois = 9 objets d'une panoplie de 8 : pas de palier 9, donc aucun bonus."""
    r = calculer(Build(50, {**BOUFTOU, "anneau2": 2419}), catalogue_par_defaut())
    assert r.panoplies == []
    assert r.alertes == {"anneau1": ["Anneau en double (même panoplie)"],
                         "anneau2": ["Anneau en double (même panoplie)"]}
    assert r.totaux["Vitalité"] == 145 + 30  # les deux anneaux, sans bonus de panoplie


def test_niveau_insuffisant_et_dofus_en_double():
    cat = catalogue_par_defaut()
    dofus = next(o for o in cat.objets.values() if o.type == 23)
    r = calculer(Build(10, {"coiffe": 2411, "dofus1": dofus.id, "dofus4": dofus.id}), cat)
    assert "Niveau insuffisant" in r.alertes["coiffe"]
    assert "Objet en double" in r.alertes["dofus1"] and "Objet en double" in r.alertes["dofus4"]


def test_objet_inconnu_ou_emplacement_inconnu_ignore():
    r = calculer(Build(200, {"coiffe": 999999999, "chapeau": 2411}), catalogue_par_defaut())
    assert r.totaux["Force"] == 0 and r.alertes == {}


@pytest.mark.parametrize(("carac", "valeur", "cout"), [
    ("Vitalité", 7, 7), ("Sagesse", 10, 30), ("Force", 100, 100), ("Force", 101, 102), ("Force", 200, 300),
    ("Agilité", 250, 450), ("Chance", 350, 800), ("Intelligence", -5, 0), ("Force", 0, 0),
])  # fmt: skip
def test_cout_des_points(carac, valeur, cout):
    assert cout_points(carac, valeur) == cout


def test_points_disponibles_et_bornes():
    assert (points_disponibles(1), points_disponibles(200)) == (0, 995)
    b = nettoyer(Build(250, {"coiffe": 1, "chapeau": 2}, {"Force": 10, "Puissance": 5}, {"Force": 150, "Agilité": -3}))
    assert (b.niveau, b.objets, b.caracs_base, b.caracs_parcho) == (200, {"coiffe": 1}, {"Force": 10}, {"Force": 100})
    assert nettoyer(Build(0)).niveau == 1


def test_affichage_derives_et_dommages():
    a = affichage({"Dommages": 10, "Do Feu": 3, "Agilité": -15, "Sagesse": 99, "Chance": 105, "Force": 0}, 100)
    assert (a["Do Feu"], a["Do Neutre"], a["Do Air"]) == (13, 10, 10)
    assert (a["PA"], a["PM"], a["Vitalité"]) == (7, 3, 550)
    assert (a["Fuite"], a["Tacle"]) == (-2, -2)  # arrondi vers le bas, comme Math.floor
    assert a["Esquive PA"] == 9 and a["Prospection"] == 110 and a["Pods"] == 1000 and a["Initiative"] == 90
    assert affichage({}, 99)["PA"] == 6


# --- Conditions -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("conditions", "totaux", "niveau", "attendu"), [
    ("CS>140", {"Force": 140}, 200, False),  # strict, comme Duffus
    ("CS>140", {"Force": 141}, 200, True),
    ("CS>=140", {"Force": 140}, 200, False),  # Duffus traite >= comme >
    ("CS<10", {"Force": 10}, 200, False),
    ("CS=10", {"Force": 10}, 200, True),
    ("CP<12|CM<6", {"PA": 5, "PM": 3}, 200, False),  # 12 PA, 6 PM : ni l'un ni l'autre
    ("CP<12|CM<6", {"PA": 5, "PM": 2}, 200, True),
    ("CP<12", {"PA": 5}, 99, True),  # 6 + 5 = 11 sous le niveau 100
    ("CS>299&CC>299", {"Force": 300, "Chance": 299}, 200, False),
    ("(CS>10&CI>10)|CA>5", {"Agilité": 6}, 200, True),
    ("CS>10&(CI>10|CA>5)", {"Force": 11, "Agilité": 6}, 200, True),
    ("PL>50", {}, 50, True), ("PL<50", {}, 51, False),
    ("OS=505", {}, 1, True), ("PO!10119", {}, 1, True), ("PN~Silaisie&BI=1", {}, 1, True),
    ("cs>10", {}, 1, True),  # clé en minuscules : inconnue, donc remplie
    ("CV>3949", {"Vitalité": 3950}, 200, True),
    ("", {}, 1, True), (None, {}, 1, True), ("CS>", {}, 1, True), ("&|(", {}, 1, True),
])  # fmt: skip
def test_conditions(conditions, totaux, niveau, attendu):
    assert conditions_remplies(conditions, totaux, niveau, []) is attendu


def test_condition_pk_compte_les_panoplies_actives():
    cat = Catalogue.depuis_json(
        [{"id": i, "nom": f"O{i}", "niveau": 1, "type": t, "panoplie": p, "effets": []}
         for i, t, p in ((1, 16, 1), (2, 17, 1), (3, 1, 2), (4, 10, 2), (5, 11, 3))],
        [{"id": n, "nom": f"P{n}", "objets": [], "bonus": {"2": [[118, 1, 0]]}} for n in (1, 2, 3)])
    actives = panoplies_actives([cat.objet(i) for i in (1, 2, 3, 4, 5)], cat.panoplies)
    assert [a.id for a in actives] == [1, 2]
    assert conditions_remplies("pk<2", {}, 1, actives) is False
    assert conditions_remplies("PK<3", {}, 1, actives) is True
    assert conditions_remplies("PK=2", {}, 1, actives) is True


def test_conditions_comptent_base_parchemins_et_panoplie():
    cat = Catalogue.depuis_json(
        [{"id": 1, "nom": "Exigeant", "niveau": 1, "type": 16, "conditions": "CS>140", "effets": []},
         {"id": 2, "nom": "Familier", "niveau": 1, "type": 18, "conditions": "CS>140", "effets": []}], [])
    r = calculer(Build(200, {"coiffe": 1, "familier": 2}, {"Force": 40}, {"Force": 100}), cat)
    assert r.alertes == {"coiffe": ["Conditions non remplies"]}  # 140 : pas assez ; le familier n'est pas contrôlé
    r = calculer(Build(200, {"coiffe": 1}, {"Force": 41}, {"Force": 100}), cat)
    assert r.alertes == {}
