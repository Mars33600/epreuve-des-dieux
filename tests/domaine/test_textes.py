"""Textes du domaine : listes, dates en heure de Paris, pseudos, mentions Discord, fiche de quête."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from epreuve.domaine.fiche import (
    Besoin,
    EtapeFiche,
    FicheQuete,
    Position,
    Prerequis,
    extraire_ids_discord,
    masquer_prerequis_scelles,
)
from epreuve.domaine.textes import date_paris, liste_francaise, valider_pseudo


def test_liste_francaise():
    assert liste_francaise([]) == ""
    assert liste_francaise(["A"]) == "A"
    assert liste_francaise(["A", "B"]) == "A et B"
    assert liste_francaise(["Brindille", "Mirelune", "Sélénith"]) == "Brindille, Mirelune et Sélénith"


def test_date_paris_heure_d_hiver():
    assert date_paris(datetime(2026, 11, 13, 16, 0, tzinfo=UTC)) == "vendredi 13 novembre à 17 h"
    assert date_paris(datetime(2026, 12, 1, 8, 5, tzinfo=UTC)) == "mardi 1 décembre à 9 h 05"


def test_date_paris_heure_d_ete_et_autre_fuseau():
    assert date_paris(datetime(2026, 10, 24, 15, 0, tzinfo=UTC)) == "samedi 24 octobre à 17 h"
    assert date_paris(datetime(2026, 10, 30, 12, 0, tzinfo=timezone(timedelta(hours=-4)))) == \
        "vendredi 30 octobre à 17 h"


def test_date_paris_sans_fuseau():
    with pytest.raises(ValueError):
        date_paris(datetime(2026, 11, 13, 17, 0))  # noqa: DTZ001


@pytest.mark.parametrize(("brut", "propre"), [("  Brindille ", "Brindille"), ("Le   Sage", "Le Sage"),
                                              ("ab", "ab"), ("x" * 30, "x" * 30), ("Sélénith", "Sélénith")])
def test_valider_pseudo(brut, propre):
    assert valider_pseudo(brut) == propre


@pytest.mark.parametrize("brut", ["a", "   ", "", "x" * 31, "ab​", "a\x00b"])
def test_pseudo_refuse(brut):
    with pytest.raises(ValueError):
        valider_pseudo(brut)


def test_extraire_ids_discord():
    assert extraire_ids_discord("<@123> <@!456> 789") == [123, 456, 789]
    assert extraire_ids_discord("<@123>, <@123>\n<@!123>") == [123]
    assert extraire_ids_discord("aucune mention") == []


def fiche(*prerequis, source="duffus"):
    return FicheQuete(10, 1, "Quête", 12, "Astrub", "secondaire", (), "jusqu'à l'étape 2", None, prerequis,
                      (EtapeFiche(1, "Parler", "<p>Va voir</p>", ("Parler à X",)),), (Besoin("Blé", 5),),
                      (Besoin("Bouftou", 3, "https://api.dofusdb.fr/img/1.png"),), (Position("PNJ", 4, -19),),
                      None, ("1 200 XP",), source)


def test_fiche_complete_selon_la_source():
    assert fiche().complete and fiche(source="duffus+dofusdb").complete
    assert not fiche(source="dofusdb").complete


def test_masquer_prerequis_scelles():
    f = fiche(Prerequis(1, "Ouverte", "visible"), Prerequis(2, "Secrète", "visible"),
              Prerequis(None, "Hors guide", "hors_guide"), Prerequis(3, "Inconnue", "visible"),
              Prerequis(4, "Déjà marquée", "scelle"))
    m = masquer_prerequis_scelles(f, {0, 1}, {1: 0, 2: 2, 4: 1})
    assert m.prerequis == (Prerequis(1, "Ouverte", "visible"), Prerequis(None, None, "scelle"),
                           Prerequis(None, "Hors guide", "hors_guide"), Prerequis(None, None, "scelle"),
                           Prerequis(None, None, "scelle"))
    assert m.etapes == f.etapes and f.prerequis[1].nom == "Secrète"  # l'original n'est pas modifié
