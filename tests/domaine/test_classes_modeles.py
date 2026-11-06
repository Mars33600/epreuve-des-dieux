"""repartition_classes() et contrôles des dataclasses du domaine."""

import pytest

from epreuve.domaine.classes import CLASSES, repartition_classes
from epreuve.domaine.modeles import Bloc, Coches, ContenuEtage, ElementRef, Grimpeur, Session
from tests.fabrique import AVANT, bloc, case, donjon, etage, grimpeur, quete


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
    blocs = [bloc(2, ordre=1), bloc(1, ordre=2), bloc(3, masque=True)]
    c = ContenuEtage.visible(e, donjons, cases, quetes, blocs)
    assert [d.id for d in c.donjons] == [2, 1]
    assert {x.id for x in c.cases} == {1, 2, 5}  # 3 masquée, 4 dans un donjon masqué
    assert [x.id for x in c.cases_du_donjon(1)] == [1, 2]
    assert [q.id for q in c.quetes] == [2, 1]
    assert ElementRef("case", 4) not in c.elements()
    assert set(c.elements()) == {ElementRef("case", 1), ElementRef("case", 2), ElementRef("case", 5),
                                 ElementRef("bloc", 1), ElementRef("bloc", 2)}


def test_coches_contient():
    c = Coches(1, frozenset({3}), frozenset({7}))
    assert c.contient(ElementRef("case", 3)) and not c.contient(ElementRef("quete", 3))
    assert c.contient(ElementRef("quete", 7)) and not c.contient(ElementRef("case", 7))


def test_bloc_lien_duffus():
    b = Bloc(1, 1, "Quêtes d'Incarnam", 2, 1, "principale", "construction", 24, 23)
    assert b.lien_duffus is None  # pas d'adresse Duffus connue : pas de lien
    avec = Bloc(1, 1, "Quêtes d'Incarnam", 2, 1, "principale", "construction", 24, 23,
                duffus_url="https://duffus.fr/guide-complet")
    assert avec.lien_duffus == "https://duffus.fr/guide-complet"
    ancre = Bloc(1, 1, "Quêtes d'Incarnam", 2, 1, "principale", "construction", 24, 23,
                 duffus_url="https://duffus.fr/guide-complet", duffus_ancre="bloc-2")
    assert ancre.lien_duffus == "https://duffus.fr/guide-complet#bloc-2"


def test_bloc_hybride_moities_titres_et_libelles():
    from epreuve.domaine.modeles import marquer_moities

    rouge = bloc(1, "principale", titre="Incarnam", numero=2, ordre=1, partie="principale")
    jaune = bloc(2, "secondaire", titre="Incarnam", numero=2, ordre=1, partie="secondaire")
    entier = bloc(3, "principale", titre="Astrub", numero=None, ordre=2, partie="principale")
    autre_etage = bloc(4, "secondaire", titre="Incarnam", etage_id=2, partie="secondaire")
    masque = bloc(5, "secondaire", titre="Astrub", ordre=2, partie="secondaire", masque=True)
    r, j, e, a, m = marquer_moities([rouge, jaune, entier, autre_etage, masque])
    assert (r.moitie, j.moitie, e.moitie, a.moitie, m.moitie) == (True, True, False, False, False)
    assert (r.titre_partie, j.titre_partie, e.titre_partie) == (
        "Bloc 2 · Incarnam (principale)", "Bloc 2 · Incarnam (secondaire)", "Astrub")
    assert (r.libelle_coche, e.libelle_coche) == ("Bloc 2, partie principale", "Bloc « Astrub »")
    # La partie fixe la nature par défaut ; sans partie (données anciennes), elle se déduit des quêtes.
    corrige = bloc(6, "secondaire", partie="principale", nature_origine="admin", nb_principales=0)
    assert corrige.nature_par_defaut == "principale"
    assert bloc(7, "secondaire", nb_principales=2).nature_par_defaut == "principale"


def test_contenu_regroupe_les_moities_rouge_puis_jaune():
    # La moitié jaune a l'id le plus petit : elle passe quand même après la rouge.
    jaune = bloc(1, "secondaire", titre="Incarnam", ordre=1, partie="secondaire")
    rouge = bloc(2, "principale", titre="Incarnam", ordre=1, partie="principale")
    astrub = bloc(3, "principale", titre="Astrub", ordre=2, partie="principale")
    masquee = bloc(4, "secondaire", titre="Astrub", ordre=2, partie="secondaire", masque=True)
    qs = [quete(10, "principale", bloc_id=2), quete(11, "secondaire", bloc_id=1), quete(12, "principale", bloc_id=2),
          quete(13, "principale", bloc="Astrub")]  # sans bloc_id : rattachée par le titre
    c = ContenuEtage.visible(etage(), [], [], qs, [jaune, rouge, astrub, masquee])
    assert [[b.id for b in g] for g in c.groupes_blocs()] == [[2, 1], [3]]
    assert [q.id for q in c.quetes_du_bloc(c.blocs[0])] == [10, 12]
    assert [q.id for q in c.quetes_du_bloc(c.blocs[1])] == [11]
    assert c.quetes_utiles_du_bloc(c.blocs[2]) == ("Quête 13",)
    # Deux blocs entiers voisins ne se regroupent pas.
    deux = ContenuEtage.visible(etage(), [], [], [], [bloc(1, titre="A", ordre=1), bloc(2, titre="B", ordre=2)])
    assert [len(g) for g in deux.groupes_blocs()] == [1, 1]
