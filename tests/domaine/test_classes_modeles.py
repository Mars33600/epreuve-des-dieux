"""repartition_classes(), contrôles des dataclasses et petits textes du domaine."""

import pytest

from epreuve.domaine.classes import CLASSES, repartition_classes
from epreuve.domaine.modeles import Grimpeur, Instantane, liste_francaise, phrase_validation
from tests.fabrique import AVANT, ETAGE0, grimpeur


def test_19_classes_dans_l_ordre_du_jeu():
    assert len(CLASSES) == 19
    assert CLASSES[0] == "Féca" and CLASSES[6] == "Eniripsa" and CLASSES[-1] == "Forgelance"


def test_registre_vide_19_zeros():
    r = repartition_classes([])
    assert [x.classe for x in r] == list(CLASSES)
    assert all(x.actifs == 0 and x.en_pause == 0 for x in r)


def test_actifs_pause_et_exclus():
    g = [
        grimpeur(1, classe="Féca"),
        grimpeur(2, classe="Féca", statut="pause"),
        grimpeur(3, classe="Iop"),
        grimpeur(4, classe="Iop", retard=True),  # un retardataire joue bien sa classe
        grimpeur(5, classe="Sram", statut="exclu"),
    ]
    r = {x.classe: x for x in repartition_classes(g)}
    assert len(r) == 19
    assert (r["Féca"].actifs, r["Féca"].en_pause) == (1, 1)
    assert (r["Iop"].actifs, r["Iop"].en_pause) == (2, 0)
    assert (r["Sram"].actifs, r["Sram"].en_pause) == (0, 0)  # exclu ignoré


@pytest.mark.parametrize(("champ", "valeur"), [("classe", "Paladin"), ("difficulte", "extreme"),
                                               ("statut", "fantome")])
def test_grimpeur_refuse_les_valeurs_hors_liste(champ, valeur):
    args = {"id": 1, "pseudo": "X", "classe": "Iop", "difficulte": "easy", "statut": "actif",
            "niveau_connu": None, "inscrit_le": AVANT, "inclus_le": AVANT}
    args[champ] = valeur
    with pytest.raises(ValueError):
        Grimpeur(**args)


def test_instantane_etage_ouvert():
    assert Instantane((ETAGE0,), (), (), (), (), ()).etage_ouvert == ETAGE0
    assert Instantane((), (), (), (), (), ()).etage_ouvert is None


def test_liste_francaise():
    assert liste_francaise([]) == ""
    assert liste_francaise(["A"]) == "A"
    assert liste_francaise(["A", "B"]) == "A et B"
    assert liste_francaise(["Brindille", "Mirelune", "Sélénith"]) == "Brindille, Mirelune et Sélénith"


def test_phrase_validation_et_declaration():
    assert phrase_validation(1, ["Kardorim (Duo)"], [20]) == "a validé « Kardorim (Duo) » (niv. 20)."
    assert phrase_validation(3, ["Kardorim (Duo)"], [20, 19, 20]) == "ont validé « Kardorim (Duo) » (niv. 19 à 20)."
    assert phrase_validation(1, ["Toutes les quêtes d'Incarnam"], [None]) == \
        "a déclaré avoir terminé « Toutes les quêtes d'Incarnam »."
    assert phrase_validation(2, ["A", "B"], [None, None]) == "ont déclaré avoir terminé « A » et « B »."
