"""Le titre d'un étage sans nom propre s'affiche une seule fois."""
from epreuve.web.vues import titre_etage
from tests.fabrique import etage


def test_etage_sans_nom_propre_une_seule_fois():
    assert titre_etage(etage(numero=0)) == "Étage 0"
    assert titre_etage(etage(numero=3, nom="ÉTAGE 3")) == "Étage 3"


def test_etage_nomme_garde_son_nom():
    assert titre_etage(etage(numero=2, nom="Les Pics")) == "Étage 2 · Les Pics"
