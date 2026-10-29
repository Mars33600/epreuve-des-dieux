"""Recherche globale : API JSON groupée, sans accents ni casse, mot partiel, et le brouillard de guerre.

Les quêtes et donjons d'un étage scellé ne doivent JAMAIS sortir pour un non-admin (même par un mot partiel).
"""

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import insert, select

from epreuve.db import tables as t
from tests.fabrique import PENDANT
from tests.web.test_encyclopedie import GRIMPEUR, SANS_FICHE, client, jeton, site  # noqa: F401 — fixture `site`

DONJON = {"origine": "propose", "succes_source": "duffus"}
QUETE = {"nature": "principale", "nature_origine": "duffus"}
ADMIN = 950  # session d'admin vérifiée à l'instant (sinon le site redemande à Discord, absent des tests)


@pytest.fixture
async def monde(site, moteur, depot):  # noqa: F811
    """Un donjon et une quête dans l'étage ouvert (0) et dans l'étage scellé (1) ; un autre masqué."""
    async with moteur.begin() as c:
        ids = {n: i for i, n in (await c.execute(select(t.etage.c.id, t.etage.c.numero))).all()}
        for etage, nom in ((0, "Gelaxième Dimension"), (1, "Gelaxème Scellée")):
            await c.execute(insert(t.donjon).values(
                etage_id=ids[etage], nom=nom, niveau=10, ordre=1, **DONJON, masque=False))
        await c.execute(insert(t.donjon).values(
            etage_id=ids[0], nom="Gelaxie masquée", niveau=10, ordre=2, **DONJON, masque=True))
        for etage, nom in ((0, "Éclaireur de la Tour"), (1, "Éclat secret du sommet")):
            await c.execute(insert(t.quete).values(
                etage_id=ids[etage], nom=nom, bloc="b", ordre=1, **QUETE, dofus=[],
                masquee=False))
    await depot.creer_session(hashlib.sha256(jeton(ADMIN).encode()).digest(), ADMIN, "admin", True, "oauth", "csrf",
                              PENDANT, timedelta(days=7))
    return site


async def chercher(app, q, qui=GRIMPEUR, **params):
    async with client(app, qui) as c:
        r = await c.get("/api/recherche", params={"q": q, **params})
    return r


def noms(r) -> dict[str, list[str]]:
    return {g["type"]: [x["nom"] for x in g["resultats"]] for g in r.json()["groupes"]}


async def test_sans_accent_sans_casse_et_mot_partiel(monde):
    r = await chercher(monde, "ECLAIR")
    assert r.status_code == 200
    assert noms(r)["quetes"] == ["Éclaireur de la Tour"]
    assert noms(await chercher(monde, "gelax"))["donjons"] == ["Gelaxième Dimension"]
    assert "Gelaxième Dimension" in noms(await chercher(monde, "dimens"))["donjons"]  # milieu de nom


async def test_groupes_limites_et_voir_tout(monde):
    r = await chercher(monde, "brindille")
    assert r.json()["groupes"][0]["type"] == "grimpeurs"
    assert r.json()["groupes"][0]["resultats"][0]["lien"].startswith("/grimpeurs/")
    gros = await chercher(monde, "a", limite=2)  # tous les types, 2 par groupe au plus
    assert all(len(g["resultats"]) <= 2 for g in gros.json()["groupes"])
    assert any(g["plus"] and g["voir_tout"].startswith("/recherche?q=a&type=") for g in gros.json()["groupes"])


async def test_outils_et_recherche_vide(monde):
    assert noms(await chercher(monde, "alman"))["outils"] == ["Almanax"]
    assert (await chercher(monde, "   ")).json()["groupes"] == []


async def test_etage_scelle_jamais_visible_pour_un_grimpeur(monde):
    for q in ("gelax", "scellee", "eclat", "secret", "sommet", "gelaxie"):
        r = await chercher(monde, q)
        texte = r.text
        assert "Scellée" not in texte and "Éclat secret" not in texte, q
        assert "masquée" not in texte, q  # donjon masqué de l'étage ouvert
        for g in r.json()["groupes"]:
            assert all("/etages/1" not in x["lien"] for x in g["resultats"]), q
    page = await client_get(monde, "/recherche?q=eclat%20secret")
    assert "Éclat secret" not in page and "Scellée" not in page


async def test_admin_voit_les_etages_scelles(monde):
    r = await chercher(monde, "gelax", ADMIN)
    assert set(noms(r)["donjons"]) == {"Gelaxième Dimension", "Gelaxème Scellée", "Gelaxie masquée"}
    assert noms(await chercher(monde, "eclat", ADMIN))["quetes"] == ["Éclat secret du sommet"]


async def client_get(app, chemin, qui=GRIMPEUR):
    async with client(app, qui) as c:
        return (await c.get(chemin)).text


async def test_acces_reserve_aux_grimpeurs(monde):
    assert (await chercher(monde, "x", None)).status_code in (303, 401, 403)
    r = await chercher(monde, "x", SANS_FICHE)
    assert r.status_code == 409 and r.json()["ok"] is False


async def test_page_voir_tout_et_en_tete_sur_toutes_les_pages(monde):
    html = await client_get(monde, "/recherche?q=gelax&type=donjons")
    assert "Gelaxième Dimension" in html
    for chemin in ("/", "/encyclopedie", "/builder", "/outils", "/regles"):
        page = await client_get(monde, chemin)
        assert 'data-suggest="global"' in page and "Monde des Douze" in page, chemin
