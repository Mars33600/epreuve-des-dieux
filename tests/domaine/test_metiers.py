"""Le recensement des métiers : la liste, la lecture du formulaire et la recherche par niveau."""

from datetime import UTC, datetime

import pytest

from epreuve.domaine.metiers import FAMILLES, METIERS, PAR_CLE, NiveauMetier, artisans, lire_niveaux

T = datetime(2026, 11, 15, tzinfo=UTC)


def test_liste_des_metiers():
    assert len(METIERS) == len(PAR_CLE) == 22
    assert {m.famille for m in METIERS} == {f for f, _ in FAMILLES}
    assert PAR_CLE["bijoutier"].nom == "Bijoutier" and PAR_CLE["pecheur"].nom == "Pêcheur"


def test_lire_niveaux():
    assert lire_niveaux({"bijoutier": " 25 ", "tailleur": "", "mineur": "0", "paysan": "200"}) == {
        "bijoutier": 25, "paysan": 200}


@pytest.mark.parametrize("saisie", [{"bijoutier": "201"}, {"bijoutier": "-3"}, {"bijoutier": "abc"},
                                    {"boulanger": "10"}])
def test_lire_niveaux_refuse(saisie):
    with pytest.raises(ValueError):
        lire_niveaux(saisie)


def test_artisans_du_plus_haut_au_plus_bas_a_partir_du_minimum():
    niveaux = [NiveauMetier(1, "bijoutier", 20, T), NiveauMetier(2, "bijoutier", 45, T),
               NiveauMetier(3, "bijoutier", 25, T), NiveauMetier(4, "tailleur", 90, T)]
    assert [n.grimpeur_id for n in artisans(niveaux, "bijoutier")] == [2, 3, 1]
    assert [n.grimpeur_id for n in artisans(niveaux, "bijoutier", 25)] == [2, 3]
    assert artisans(niveaux, "forgeron") == []
