"""L'annonce Discord d'une ouverture d'étage : le corps exact posté sur le webhook (demande de Shadoaze)."""

from epreuve.domaine.annonce import COULEUR_OR, NOM_GARDIEN, annonce_ouverture, image_publique, lien_etage
from tests.fabrique import PENDANT, etage

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
