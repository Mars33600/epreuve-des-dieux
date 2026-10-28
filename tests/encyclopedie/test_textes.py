"""Fonctions pures du lot E2 : effets en clair (comme Duffus), recherche, familles, étage d'un stuff."""

import pytest

from epreuve.encyclopedie.textes import (
    TrancheVisible,
    cle_recherche,
    effets_en_clair,
    etage_du_niveau,
    famille_du_super_type,
    formater_effet,
    icone_objet,
    image_monstre,
    requete_plein_texte,
)


@pytest.mark.parametrize(("modele", "de_min", "de_max", "valeur", "attendu"), [
    ("#1{{~1~2 à }}#2 Force", 7, 10, 0, "7 à 10 Force"),
    ("#1{{~1~2 à }}#2 Force", 7, 0, 0, "7 Force"),
    ("#1{{~1~2 à }}#2 Force", 5, 5, 0, "5 Force"),
    ("-#1{{~1~2 à -}}#2 Sagesse", -3, -8, 0, "-3 à -8 Sagesse"),
    ("Repousse de #1 case{{~ps}}", 1, 0, 0, "Repousse de 1 case"),
    ("Repousse de #1 case{{~ps}}", 3, 0, 0, "Repousse de 3 cases"),
    ("#3 Combat{{~ps}} restant{{~ps}}", 0, 0, 12, "12 Combats restants"),
    ("#1{{~1~2 à }}#2 (dommages Neutre)", 8, 10, 0, "8 à 10 (dommages Neutre)"),
    (None, 1, 2, 0, ""),
])  # fmt: skip
def test_formater_effet(modele, de_min, de_max, valeur, attendu):
    assert formater_effet(modele, de_min, de_max, valeur) == attendu


def test_effets_en_clair_par_priorite_et_sans_texte_omis():
    modeles = {118: ("#1{{~1~2 à }}#2 Force", 5300), 125: ("#1{{~1~2 à }}#2 Vitalité", 5000),
               157: ("-#1{{~1~2 à -}}#2 Force", 5301), 999: (None, 1)}
    lus = effets_en_clair([[118, 7, 10, 0], [999, 1, 1, 0], [125, 20, 30, 0], [157, 5, 0, 0]], modeles)
    assert [e.texte for e in lus] == ["20 à 30 Vitalité", "7 à 10 Force", "-5 Force"]
    assert [e.negatif for e in lus] == [False, False, True]


def test_cle_et_requete_plein_texte():
    assert cle_recherche("Épée de Boisaille") == "epee de boisaille"
    assert cle_recherche("Œil de Larve bleue") == "oeil de larve bleue"
    assert requete_plein_texte("  Épée   BOI ") == "epee:* & boi:*"
    assert requete_plein_texte("") is None and requete_plein_texte("!!!") is None
    # Aucun opérateur tsquery ne passe : la saisie est réduite à [0-9a-z].
    assert requete_plein_texte("a' | !b & (c:*)") == "a:* & b:* & c:*"
    assert requete_plein_texte(" ".join(["x"] * 20)).count("&") == 7  # 8 mots au plus


def test_familles_des_super_types():
    assert famille_du_super_type(9) == "ressources"
    assert famille_du_super_type(2) == "armes"
    assert famille_du_super_type(10) == "equipements"
    assert famille_du_super_type(None) == famille_du_super_type(424242) == "autres"


def test_etage_d_un_niveau_premier_etage_qui_le_contient():
    tranches = [TrancheVisible(1, "Astrub", 20, 40), TrancheVisible(0, "Incarnam", 1, 20)]
    assert etage_du_niveau(20, tranches).numero == 0  # borne commune : l'étage le plus bas
    assert etage_du_niveau(21, tranches).numero == 1
    assert etage_du_niveau(41, tranches) is None  # au-delà des étages visibles : rien


def test_images_chez_dofusdb_jamais_chez_duffus():
    assert icone_objet(6007) == "https://api.dofusdb.fr/img/items/6007.png"
    assert image_monstre(31) == "https://api.dofusdb.fr/img/monsters/31.png"
    assert icone_objet(None) is None
