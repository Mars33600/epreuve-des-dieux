"""Pages du lot E2 sur un vrai Postgres : accès, brouillard des étages, recherche, fiches, sécurité.

L'application tourne dans la boucle des tests (httpx.ASGITransport) : le pool asyncpg du dépôt y est lié.
"""

import hashlib
import re
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import insert

from epreuve.config import Config
from epreuve.db import tables as t
from epreuve.encyclopedie.charger import charger
from epreuve.web.app import creer_app
from epreuve.web.securite import CSP
from tests.fabrique import OUVERTURE, PENDANT, PLANCHER

DONNEES = Path(__file__).resolve().parents[1] / "donnees" / "encyclopedie"
GRIMPEUR, ADMIN, SANS_FICHE, EXCLU = 101, 900, 102, 103
STUFF_20, STUFF_42 = "Pandawa Terre PVM 20", "Enutrof Eau PVM 40"
# Étage 0 ouvert (1-20) ; étages 1 et 2 scellés : leurs noms ne doivent jamais sortir.
ETAGES = [(0, "Incarnam", 1, 20, "ouvert"), (1, "Brume-Secrète", 20, 40, "scelle"),
          (2, "Cime-Interdite", 40, 60, "scelle")]


def jeton(n: int) -> str:
    return f"jeton-de-test-{n}"


@pytest.fixture
async def site(depot, moteur):
    await charger(moteur, DONNEES)
    async with moteur.begin() as c:
        for numero, nom, bas, haut, statut in ETAGES:
            await c.execute(insert(t.etage).values(
                numero=numero, nom=nom, niveau_min=bas, niveau_max=haut, level_cap=haut, statut=statut,
                ouvert_le=OUVERTURE if statut == "ouvert" else None, date_plancher_suivant=PLANCHER,
                maj_le=OUVERTURE))  # fmt: skip
    await depot.ajouter_liste([GRIMPEUR, EXCLU], "actif", ADMIN, OUVERTURE)
    await depot.creer_grimpeur(GRIMPEUR, "brindille", "Brindille", "Iop", 20, OUVERTURE)
    exclu = await depot.creer_grimpeur(EXCLU, "ombre", "Ombre", "Iop", 20, OUVERTURE)
    await depot.changer_statut(exclu.id, "exclu", "triche", ADMIN, OUVERTURE)
    for n, admin in ((GRIMPEUR, False), (ADMIN, True), (SANS_FICHE, False), (EXCLU, False)):
        await depot.creer_session(hashlib.sha256(jeton(n).encode()).digest(), n, f"d{n}", admin, "oauth", "csrf",
                                  OUVERTURE, timedelta(days=7))
    app = creer_app(Config(_env_file=None, SITE_MODE="ouvert"), horloge=lambda: PENDANT, source=depot)
    return app


def client(app, qui: int | None = GRIMPEUR) -> httpx.AsyncClient:
    entetes = {"Cookie": f"__Host-session={jeton(qui)}"} if qui is not None else {}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=entetes,
                             follow_redirects=False)


PAGES = ["/encyclopedie", "/encyclopedie?q=larve", "/encyclopedie/objets", "/encyclopedie/ressources",
         "/encyclopedie/objets/44", "/encyclopedie/monstres", "/encyclopedie/monstres/31", "/encyclopedie/recettes",
         "/stuffs"]


async def test_connexion_requise_sur_chaque_page(site):
    async with client(site, None) as c:
        for p in PAGES:
            r = await c.get(p)
            assert (r.status_code, r.headers["location"]) == (303, "/connexion"), p
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=site), base_url="http://test",
                                 headers={"Cookie": "__Host-session=inconnu"}) as c:
        assert (await c.get("/stuffs")).headers["location"] == "/connexion"


async def test_sans_fiche_exclu_admin(site):
    async with client(site, SANS_FICHE) as c:
        r = await c.get("/encyclopedie")
        assert (r.status_code, r.headers["location"]) == (303, "/inscription")
    async with client(site, EXCLU) as c:
        assert (await c.get("/encyclopedie/objets")).status_code == 403
    async with client(site, ADMIN) as c:
        assert (await c.get("/encyclopedie/objets")).status_code == 200


async def test_chaque_page_securite_pied_de_page_et_menu(site):
    async with client(site) as c:
        for p in PAGES:
            r = await c.get(p)
            assert r.status_code == 200, p
            assert r.headers["content-security-policy"] == CSP
            html = r.text
            assert "Merci Duffus" in html and 'href="https://duffus.fr"' in html
            assert html.count("https://duffus.fr") == 1  # aucun autre lien vers duffus.fr (EX-70)
            assert not re.search(r"<script(?![^>]*\bsrc=)", html), p  # aucun script en ligne
            assert " style=" not in html and "onclick" not in html, p
            assert 'href="/encyclopedie"' in html and 'href="/stuffs"' in html


async def test_recherche_filtres_et_pagination(site):
    async with client(site) as c:
        r = await c.get("/encyclopedie/objets", params={"q": "epee boi"})
        assert "Épée de Boisaille" in r.text and "1 résultat" in r.text
        r = await c.get("/encyclopedie/objets", params={"tri": "niveau_asc"})
        assert "page=2" in r.text and 'aria-current="page">1<' in r.text
        r = await c.get("/encyclopedie/objets", params={"nmin": "abc", "page": "-3", "tri": "zzz", "type": "x"})
        assert r.status_code == 200
        r = await c.get("/encyclopedie/ressources")
        assert "Épée de Boisaille" not in r.text
        r = await c.get("/encyclopedie", params={"q": "larve"})
        assert "Larve Bleue" in r.text


async def test_fiches_et_404(site):
    async with client(site) as c:
        r = await c.get("/encyclopedie/objets/44")
        assert "Forgeron" in r.text and "7 à 10 Force" in r.text and "api.dofusdb.fr/img/items/" in r.text
        assert (await c.get("/encyclopedie/objets/999999")).status_code == 404
        assert (await c.get("/encyclopedie/objets/abc")).status_code == 422
        r = await c.get("/encyclopedie/monstres/31")
        assert "Larve Bleue" in r.text and "Butin" in r.text
        assert (await c.get("/encyclopedie/monstres/999999")).status_code == 404


async def test_saisie_echappee(site):
    async with client(site) as c:
        r = await c.get("/encyclopedie/objets", params={"q": "<script>alert(1)</script>"})
        assert "<script>alert(1)" not in r.text and "&lt;script&gt;" in r.text


async def test_stuffs_brouillard_des_etages_scelles(site):
    async with client(site) as c:
        r = await c.get("/stuffs")
        assert STUFF_20 in r.text and "Étage 0" in r.text
        for secret in (STUFF_42, "Brume-Secrète", "Cime-Interdite", "Étage 1", "Étage 2", "Niv. 40–60"):
            assert secret not in r.text, secret
        r2 = await c.get("/stuffs", params={"etage": "2"})  # étage scellé demandé : on reste sur l'étage 0
        assert STUFF_42 not in r2.text and "Cime-Interdite" not in r2.text and STUFF_20 in r2.text
        ids = dict(re.findall(r'href="/stuffs/([0-9a-f-]+)">([^<]+)<', r.text))
        id_20 = next(k for k, v in ids.items() if v == STUFF_20)
        assert (await c.get(f"/stuffs/{id_20}")).status_code == 200
    async with client(site, ADMIN) as c:
        r = await c.get("/stuffs", params={"etage": "2"})
        assert STUFF_42 in r.text and "Étage 2" in r.text  # l'admin voit les étages scellés
        id_42 = re.search(r'href="/stuffs/([0-9a-f-]+)">' + STUFF_42, r.text).group(1)
    async with client(site) as c:
        assert (await c.get(f"/stuffs/{id_42}")).status_code == 404  # même réponse qu'un stuff inconnu
        assert (await c.get("/stuffs/inconnu")).status_code == 404


async def test_stuffs_filtres_et_fiche(site):
    async with client(site) as c:
        r = await c.get("/stuffs", params={"classe": "Iop"})
        assert STUFF_20 not in r.text and "Aucun stuff" in r.text
        r = await c.get("/stuffs", params={"element": "Terre"})  # élément inconnu : ignoré
        assert r.status_code == 200
        id_20 = re.search(r'href="/stuffs/([0-9a-f-]+)">' + STUFF_20, r.text).group(1)
        r = await c.get(f"/stuffs/{id_20}")
        assert "Équipement" in r.text and "/encyclopedie/objets/" in r.text


async def test_sans_etage_ouvert_aucun_stuff(site, moteur):
    async with moteur.begin() as c:
        await c.execute(t.etage.update().values(statut="scelle", ouvert_le=None))
    async with client(site) as c:
        r = await c.get("/stuffs")
        assert "Aucun étage n'est encore ouvert" in r.text and STUFF_20 not in r.text and "Incarnam" not in r.text


async def test_mode_teaser_redirige(depot):
    app = creer_app(Config(_env_file=None, SITE_MODE="teaser"), horloge=lambda: PENDANT, source=depot)
    async with client(app) as c:
        for p in ("/encyclopedie", "/stuffs", "/static/encyclopedie/encyclopedie.css"):
            r = await c.get(p)
            assert (r.status_code, r.headers["location"]) == (303, "/"), p


async def test_statiques_servis(site):
    async with client(site) as c:
        for f in ("encyclopedie.css", "encyclopedie.js"):
            assert (await c.get(f"/static/encyclopedie/{f}")).status_code == 200
