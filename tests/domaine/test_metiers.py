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


# --- Le bot du salon « métiers » ----------------------------------------------------------------------------

from epreuve.domaine.metiers import (  # noqa: E402
    LIMITE_DISCORD,
    Demande,
    interpreter,
    texte_aide,
    texte_artisans,
    texte_joueur,
    trouver_joueur,
    trouver_metier,
)


@pytest.mark.parametrize(("mot", "cle"), [("Bûcheron", "bucheron"), ("PAYSAN", "paysan"), ("boulanger", "paysan"),
                                         ("bijou", "bijoutier"), ("joaillo", "joaillomage"),
                                         ("Façonneur,", "faconneur")])
def test_trouver_metier(mot, cle):
    assert trouver_metier(mot).cle == cle


@pytest.mark.parametrize("mot", ["for", "sculpte", "Billy", ""])  # trop court, ambigu, inconnu, vide
def test_trouver_metier_rien_ou_ambigu(mot):
    assert trouver_metier(mot) is None


def test_interpreter():
    assert interpreter("boulanger lvl15") == Demande(PAR_CLE["paysan"], 15, None)
    assert interpreter("  bijoutier 25 ") == Demande(PAR_CLE["bijoutier"], 25, None)
    assert interpreter("niv. 30 forgeron") == Demande(PAR_CLE["forgeron"], 30, None)
    assert interpreter("tailleur") == Demande(PAR_CLE["tailleur"], 1, None)
    assert interpreter("mineur lvl 999") == Demande(PAR_CLE["mineur"], 200, None)
    assert interpreter("Billy Bananes !") == Demande(None, 1, "Billy Bananes")
    assert interpreter("   ") is None


def test_trouver_joueur():
    pseudos = {1: "BillyBananes", 2: "Mars", 3: "Marshield", 4: "Éloïse"}
    assert trouver_joueur("mars", pseudos) == 2  # exact d'abord
    assert trouver_joueur("billy", pseudos) == 1  # début du pseudo
    assert trouver_joueur("bananes", pseudos) == 1  # contenu
    assert trouver_joueur("eloise", pseudos) == 4  # sans accents
    assert trouver_joueur("mar", pseudos) is None  # Mars et Marshield : ambigu
    assert trouver_joueur("zzz", pseudos) is None and trouver_joueur(" ", pseudos) is None


def test_textes_du_bot():
    site = "https://epreuve.test"
    vide = texte_artisans(PAR_CLE["paysan"], 15, [], site)
    assert "Personne n'a déclaré **Paysan** (niv. 15+)" in vide and f"{site}/tableau-de-bord" in vide
    t = texte_artisans(PAR_CLE["paysan"], 1, [("Billy", 30), ("Mars", 12)], site)
    assert t == "**Paysan** (tous niveaux) : 2 grimpeurs\n• Billy (niv. 30)\n• Mars (niv. 12)"
    un = texte_artisans(PAR_CLE["paysan"], 1, [("Billy", 30)], site)
    assert un.startswith("**Paysan** (tous niveaux) : 1 grimpeur\n")
    assert texte_joueur("Billy", []) == "**Billy** n'a déclaré aucun métier."
    assert texte_joueur("Billy", [("Tailleur", 23), ("Bijoutier", 20)]) == "**Billy** : Tailleur 23 · Bijoutier 20"
    assert f"{site}/metiers" in texte_aide(site)
    long = texte_artisans(PAR_CLE["paysan"], 1, [(f"Joueur{i:03}", 10) for i in range(200)], site)
    assert len(long) <= LIMITE_DISCORD + 2 and long.endswith("\n…")
