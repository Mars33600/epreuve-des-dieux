"""config/regles.yaml → Regles, et l'effet de chaque réglage (EX-109, T-11, T-13, T-16)."""

from fractions import Fraction

import pytest

from epreuve.domaine.bareme import cascade_coche, categories_comptees, points_grimpeur
from epreuve.domaine.modeles import ElementRef, Regles
from epreuve.regles import CHEMIN_PAR_DEFAUT, ReglesInvalides, lire_regles, regles_depuis
from tests.fabrique import CONTENU_REF, coches


def ecrire(tmp_path, texte):
    f = tmp_path / "regles.yaml"
    f.write_text(texte, encoding="utf-8")
    return f


def test_fichier_absent_donne_les_defauts(tmp_path):
    assert lire_regles(tmp_path / "absent.yaml") == Regles()


def test_fichier_du_depot_vaut_les_defauts():
    assert lire_regles(CHEMIN_PAR_DEFAUT) == Regles()


def test_fichier_vide_donne_les_defauts(tmp_path):
    assert lire_regles(ecrire(tmp_path, "")) == Regles()


@pytest.mark.parametrize(("valeur", "attendu"), [("5/2", Fraction(5, 2)), ("2.5", Fraction(5, 2)), ("3", 3)])
def test_points_par_joueur_exact(tmp_path, valeur, attendu):
    r = lire_regles(ecrire(tmp_path, f"palier:\n  points_par_joueur: {valeur}\n"))
    assert r.points_par_joueur == attendu and isinstance(r.points_par_joueur, Fraction)


def test_tous_les_reglages_sont_lus():
    r = regles_depuis({
        "palier": {"points_par_joueur": "1", "categorie_vide": "offerte"},
        "coches": {"succes_coche_vaincu": False, "pause_peut_cocher": False},
        "inscription": {"liste_officielle_obligatoire": False},
        "fiche": {"classe_obligatoire": True, "afficher_nom_discord": False},
        "modules": {"verrouiller_par_etage": True},
    })
    assert r == Regles(Fraction(1), "offerte", False, False, True, False, False, True)


@pytest.mark.parametrize("texte", [
    "palier:\n  categorie_vide: perdue\n",  # valeur inconnue
    "palier:\n  points_par_joueur: 0\n",
    "palier:\n  points_par_joueur: -2\n",
    "palier:\n  points_par_joueur: deux\n",
    "palier:\n  points_par_joueur: 1/0\n",
    "palier:\n  points_par_joueur: true\n",
    "palier:\n  points_par_joueur: [2]\n",
    "palier:\n  inconnu: 1\n",  # clé inconnue : une faute de frappe ne passe pas en silence
    "bonus: {}\n",
    "coches:\n  pause_peut_cocher: peut-etre\n",
    "- une liste\n",
])
def test_valeur_invalide_erreur_claire(tmp_path, texte):
    with pytest.raises(ReglesInvalides, match="regles.yaml"):
        lire_regles(ecrire(tmp_path, texte))


def test_yaml_illisible(tmp_path):
    with pytest.raises(ReglesInvalides, match="YAML"):
        lire_regles(ecrire(tmp_path, "palier: [\n"))


# --- Chaque réglage change le comportement attendu -----------------------------------------------------


def test_categorie_vide_change_k_et_les_points():
    from epreuve.domaine.modeles import ContenuEtage
    from tests.fabrique import ETAGE_REF
    vide = ContenuEtage.visible(ETAGE_REF, (), (), ())
    assert categories_comptees(vide, Regles()) == 0
    assert categories_comptees(vide, Regles(categorie_vide="offerte")) == 4
    assert points_grimpeur(vide, coches(1), Regles(categorie_vide="offerte")) == 4


def test_cascade_succes_coche_la_classique():
    assert cascade_coche(CONTENU_REF, ElementRef("case", 3), True, Regles()) == (ElementRef("case", 1),)


def test_cascade_decoche_classique_decoche_les_quatre():
    assert cascade_coche(CONTENU_REF, ElementRef("case", 6), False, Regles()) == tuple(
        ElementRef("case", i) for i in (7, 8, 9, 10))


@pytest.mark.parametrize(("ref", "cochee"), [
    (ElementRef("case", 1), True),  # cocher la classique : rien d'autre
    (ElementRef("case", 3), False),  # décocher un succès : rien d'autre
    (ElementRef("quete", 1), True),
    (ElementRef("case", 999), True),  # inconnue ou masquée
])
def test_cascade_sans_effet(ref, cochee):
    assert cascade_coche(CONTENU_REF, ref, cochee, Regles()) == ()


def test_cascade_coupee_par_le_reglage():
    off = Regles(succes_coche_vaincu=False)
    assert cascade_coche(CONTENU_REF, ElementRef("case", 3), True, off) == ()
    assert cascade_coche(CONTENU_REF, ElementRef("case", 1), False, off) == ()


def test_pause_peut_cocher_est_lu():
    # L'effet (CocheRefusee) est testé dans tests/db/test_depot.py ; ici, la lecture du réglage.
    assert regles_depuis({"coches": {"pause_peut_cocher": False}}).pause_peut_cocher is False
