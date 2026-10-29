"""Les noms cités deviennent de vrais liens vers l'encyclopédie, sur une vraie fiche de quête en base.

Objet (« Œil de Larve bleue », n° 2269) et monstre (« Larve Bleue », n° 31) viennent des données d'encyclopédie
de test ; un nom inconnu ou ambigu ne donne jamais de lien.
"""

import re

from sqlalchemy import insert, select

from epreuve.db import tables as t
from epreuve.db.depot import contenu_fiche_json
from epreuve.domaine.fiche import Besoin, EtapeFiche, LigneEtape, Position
from epreuve.encyclopedie.liens import Liens, decouper_quantite
from tests.web.test_encyclopedie import client, site  # noqa: F401 — `site` est une fixture


def test_decouper_quantite():
    assert decouper_quantite("5 × Queue de Chapardam") == ("5 × ", "Queue de Chapardam")
    assert decouper_quantite("1 200 XP") == ("", "1 200 XP")
    assert decouper_quantite("Émote Salut") == ("", "Émote Salut")


def test_liens_nom_normalise_et_ambiguite():
    liens = Liens({("objet", "oeil de larve bleue"): 2269}, frozenset({("monstre", 31)}))
    assert liens.url("Œil de Larve BLEUE") == "/encyclopedie/objets/2269"
    assert liens.url("Larve Bleue", "monstre") is None  # pas de nom retenu, et pas d'identifiant donné
    assert liens.url("Autre", "monstre", ident=31) == "/encyclopedie/monstres/31"  # l'identifiant prime
    assert liens.url("Inconnu") is None


async def test_fiche_de_quete_lie_objets_monstres_et_pnj(site, depot, moteur):  # noqa: F811
    async with moteur.begin() as c:
        etage_id = (await c.execute(select(t.etage.c.id).where(t.etage.c.numero == 0))).scalar_one()
        await c.execute(insert(t.quete).values(
            id=7001, etage_id=etage_id, nom="Chasse aux larves", niveau=5, bloc="Incarnam", ordre=1,
            nature="secondaire", nature_origine="duffus", dofus=[], masquee=False))
        contenu = {
            "etapes": [EtapeFiche(1, "Chasser", "<p>Va</p>", lignes=(
                LigneEtape("monstre", nom="Larve Bleue", quantite=2),
                LigneEtape("objet", nom="Plume Chimérique", quantite=1)))],
            "objets": [Besoin("Œil de Larve bleue", 3)], "monstres": [Besoin("Larve Bleue", 2)],
            "positions": [Position("Départ : Haraquiri", 1, 2, "Incarnam")],
            "recompenses": ["2 × Ortie", "1 200 XP", "5 × Queue de Chapardam"],
        }
        await c.execute(insert(t.fiche_quete).values(
            quete_id=7001, source="duffus", contenu=contenu_fiche_json(_contenu(contenu))))
    async with client(site) as c:
        html = (await c.get("/etages/0/quetes/7001")).text
    liens = {nom: href for href, nom in re.findall(r'<a class="enc" href="([^"]+)">([^<]+)</a>', html)}
    assert liens["Œil de Larve bleue"] == "/encyclopedie/objets/2269"  # objet d'un besoin
    assert liens["Larve Bleue"] == "/encyclopedie/monstres/31"  # monstre d'une étape et des besoins
    assert liens["Plume Chimérique"] == "/encyclopedie/objets/16512"  # objet d'une étape
    assert liens["Ortie"] == "/encyclopedie/objets/421"  # récompense « 2 × Ortie » : la quantité reste du texte
    assert html.count('href="/encyclopedie/monstres/31"') == 2  # ligne d'étape et « ce dont tu as besoin »
    assert liens["Haraquiri"] == "/encyclopedie/pnj/740"  # PNJ de départ
    assert "Queue de Chapardam</a>" not in html and "5 × Queue de Chapardam" in html  # inconnu : pas de lien
    assert "1 200 XP</a>" not in html


def _contenu(d):
    from epreuve.db.depot import ContenuFiche

    return ContenuFiche(**d)
