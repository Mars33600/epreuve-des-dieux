"""repartition_classes() et contrôles des dataclasses du domaine."""

import pytest

from epreuve.domaine.classes import CLASSES, repartition_classes
from epreuve.domaine.modeles import Coches, ContenuEtage, ElementRef, Grimpeur, Session
from tests.fabrique import AVANT, case, donjon, etage, grimpeur, quete


def test_19_classes_dans_l_ordre_du_jeu():
    assert len(CLASSES) == 19
    assert CLASSES[0] == "Féca" and CLASSES[6] == "Eniripsa" and CLASSES[-1] == "Forgelance"


def test_registre_vide_19_zeros():
    r = repartition_classes([])
    assert [x.classe for x in r] == list(CLASSES)
    assert all(x.actifs == 0 and x.en_pause == 0 for x in r)


def test_actifs_pause_exclus_et_sans_classe():
    g = [
        grimpeur(1, classe="Féca"),
        grimpeur(2, classe="Féca", statut="pause"),
        grimpeur(3, classe="Iop"),
        grimpeur(4, classe="Iop"),
        grimpeur(5, classe="Sram", statut="exclu"),
        grimpeur(6, classe=None),  # classe facultative (T-20) : ignoré
    ]
    r = {x.classe: x for x in repartition_classes(g)}
    assert len(r) == 19
    assert (r["Féca"].actifs, r["Féca"].en_pause) == (1, 1)
    assert (r["Iop"].actifs, r["Iop"].en_pause) == (2, 0)
    assert (r["Sram"].actifs, r["Sram"].en_pause) == (0, 0)


@pytest.mark.parametrize(("champ", "valeur"), [("classe", "Paladin"), ("statut", "fantome")])
def test_grimpeur_refuse_les_valeurs_hors_liste(champ, valeur):
    args = {"id": 1, "discord_user_id": 1, "nom_discord": "d", "pseudo": "X", "classe": "Iop",
            "statut": "actif", "niveau_declare": None, "inscrit_le": AVANT}
    args[champ] = valeur
    with pytest.raises(ValueError):
        Grimpeur(**args)


def test_grimpeur_sans_classe_accepte():
    assert grimpeur(1, classe=None).classe is None


def test_session_ne_montre_pas_ses_jetons():
    s = Session(1, "d", False, AVANT, AVANT, jeton_oauth="SECRET-OAUTH", csrf="SECRET-CSRF")
    assert "SECRET" not in repr(s)


def test_contenu_visible_retire_les_masques_et_trie():
    e = etage()
    donjons = [donjon(2, ordre=1), donjon(1, ordre=2), donjon(3, masque=True)]
    cases = [case(2, 1, 2), case(1, 1, 1), case(3, 1, 3, masquee=True), case(4, 3, 1), case(5, 2, 1)]
    quetes = [quete(2, ordre=1), quete(1, ordre=2), quete(3, masquee=True)]
    c = ContenuEtage.visible(e, donjons, cases, quetes)
    assert [d.id for d in c.donjons] == [2, 1]
    assert {x.id for x in c.cases} == {1, 2, 5}  # 3 masquée, 4 dans un donjon masqué
    assert [x.id for x in c.cases_du_donjon(1)] == [1, 2]
    assert [q.id for q in c.quetes] == [2, 1]
    assert ElementRef("case", 4) not in c.elements()
    assert set(c.elements()) == {ElementRef("case", 1), ElementRef("case", 2), ElementRef("case", 5),
                                 ElementRef("quete", 1), ElementRef("quete", 2)}


def test_coches_contient():
    c = Coches(1, frozenset({3}), frozenset({7}))
    assert c.contient(ElementRef("case", 3)) and not c.contient(ElementRef("quete", 3))
    assert c.contient(ElementRef("quete", 7)) and not c.contient(ElementRef("case", 7))
