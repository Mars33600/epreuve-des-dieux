"""L'annonce Discord d'une ouverture d'étage : le corps exact posté sur le webhook (demande de Shadoaze)."""

from datetime import timedelta
from pathlib import Path

import pytest

from epreuve.domaine.annonce import (
    COULEUR_OR,
    FENETRE_LANCEMENT,
    NOM_GARDIEN,
    annonce_lancement,
    annonce_ouverture,
    delai_avant_regard,
    doit_annoncer_lancement,
    image_publique,
    lien_connexion,
    lien_etage,
)
from tests.fabrique import PENDANT, PLANCHER, etage

HISTOIRE = (Path(__file__).parents[2] / "src/epreuve/web/contenu/histoire.md").read_text(encoding="utf-8")

CHAMPS = etage(2, 1, "ouvert", nom="Les Champs Murmurants", niveau_min=21, niveau_max=40, level_cap=40,
               ouvert_le=PENDANT)


def test_annonce_complete():
    a = annonce_ouverture(CHAMPS, "https://epreuve.test/")
    assert a["username"] == NOM_GARDIEN == "Gardien de la Tour"
    # Le @everyone en tête, et autorisé explicitement : sans allowed_mentions, Discord ne notifie personne.
    assert a["content"].startswith("@everyone ")
    assert a["allowed_mentions"] == {"parse": ["everyone"]}
    assert "niveaux 21 à 40" in a["content"] and a["content"].endswith("\nhttps://epreuve.test/etages/1")
    (e,) = a["embeds"]
    assert e["title"] == "L'étage 1 s'éveille" and e["color"] == COULEUR_OR == 0xD4A84B
    assert e["url"] == "https://epreuve.test/etages/1"  # pas de double « / » malgré le SITE_URL terminé par /
    assert "**Les Champs Murmurants**" in e["description"] and "Même les Dieux se taisent" in e["description"]
    assert e["fields"][0] == {"name": "Niveaux", "value": "21 à 40", "inline": True}
    assert e["fields"][1]["value"] == "niveau 40"
    assert e["timestamp"] == PENDANT.isoformat()
    assert "image" not in e  # pas d'image d'ambiance publique


def test_sans_site_url_ni_date_aucun_lien():
    a = annonce_ouverture(etage(2, 1, "scelle"), None)
    assert "url" not in a["embeds"][0] and "timestamp" not in a["embeds"][0]
    assert "http" not in a["content"]
    assert lien_etage("", 3) is None and lien_etage("https://x.fr", 3) == "https://x.fr/etages/3"


def test_image_seulement_si_publique():
    # /etages/N/image exige une connexion : Discord ne pourrait pas la lire, on ne l'envoie pas.
    assert image_publique(etage(ambiance_url="/etages/1/image")) is None
    assert image_publique(etage(ambiance_url=None)) is None
    externe = etage(2, 1, ambiance_url="https://images.example/champs.webp")
    assert image_publique(externe) == "https://images.example/champs.webp"
    assert annonce_ouverture(externe, None)["embeds"][0]["image"] == {"url": "https://images.example/champs.webp"}


# ---------------------------------------------------------------- le lancement du site (13/11, 17 h)

LANCEMENT = PLANCHER  # le 13/11 à 17 h, heure de Paris


def test_annonce_lancement_complete():
    a = annonce_lancement("https://epreuve.test/")
    assert a["username"] == NOM_GARDIEN
    assert a["content"] == "@everyone L’Épreuve des Dieux commence.\nhttps://epreuve.test/connexion"
    assert a["allowed_mentions"] == {"parse": ["everyone"]}
    (e,) = a["embeds"]
    assert e["title"] == "La tour s’éveille" and e["color"] == 0xD4A84B
    assert e["url"] == "https://epreuve.test/connexion"
    # Les phrases de Shadoaze, telles quelles ; pas celles déjà dites par le teaser vidéo.
    for phrase in ("Ses portes s’entrouvrent à nouveau.",
                   "Gravissez les étages. Surmontez les épreuves. Prouvez votre valeur.",
                   "Cette fois, nul ne pourra triompher seul."):
        assert phrase in e["description"] and phrase in HISTOIRE
    assert "premier étage vous attend" not in e["description"] and "seuil" not in e["description"]


def test_annonce_lancement_sans_site_url():
    a = annonce_lancement(None)
    assert "url" not in a["embeds"][0] and "http" not in a["content"]
    assert lien_connexion("") is None


@pytest.mark.parametrize(("decalage", "deja", "attendu"), [
    (-timedelta(seconds=1), False, False),          # avant l'heure
    (timedelta(0), False, True),                     # pile à l'heure
    (timedelta(hours=5, minutes=59), False, True),   # dans la fenêtre (serveur relancé dans l'après-midi)
    (FENETRE_LANCEMENT, False, False),               # fenêtre close : pas d'annonce en retard
    (timedelta(days=2), False, False),
    (timedelta(minutes=1), True, False),             # déjà annoncé
])
def test_doit_annoncer_lancement(decalage, deja, attendu):
    assert doit_annoncer_lancement(LANCEMENT + decalage, LANCEMENT, deja) is attendu


def test_fenetre_reglable():
    assert doit_annoncer_lancement(LANCEMENT + timedelta(hours=1), LANCEMENT, False, timedelta(minutes=30)) is False


@pytest.mark.parametrize(("decalage", "attendu"), [
    (timedelta(seconds=-20), 20.0),   # l'ouverture tombe avant la fin de la période : réveil pile à l'heure
    (timedelta(minutes=-5), 60.0),    # loin avant : une période normale
    (timedelta(0), 60.0),             # à l'heure ou après : une période normale
    (timedelta(hours=1), 60.0),
])
def test_delai_avant_regard(decalage, attendu):
    assert delai_avant_regard(LANCEMENT + decalage, LANCEMENT, 60.0) == attendu
