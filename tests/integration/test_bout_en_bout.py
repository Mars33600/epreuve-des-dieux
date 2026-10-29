"""Le lot B de bout en bout : le vrai dépôt Postgres, les étages 0 et 1 construits depuis l'aspiration réelle de
Duffus, le site complet, et un faux Discord. Même boucle d'événements que la base (client httpx asynchrone)."""

import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text

from epreuve.config import Config
from epreuve.contenu import construire as k
from epreuve.contenu.ecrire import ecrire_etage
from epreuve.discord.oauth import ClientOAuth
from epreuve.domaine.bareme import EtatJauge
from epreuve.domaine.modeles import Regles
from epreuve.domaine.ouverture import bilan_etage
from epreuve.web.app import creer_app
from epreuve.web.demo import faux_discord

SITE = "https://epreuve.test"
ROLE_ADMIN = 4242
ADMIN, BRINDILLE, MIRELUNE, INTRUS = 100000000000000001, 100000000000000002, 100000000000000003, 100000000000000004
MEMBRES = {ADMIN: ("Shadoaze", frozenset({ROLE_ADMIN})), BRINDILLE: ("brindille#1", frozenset()),
           MIRELUNE: ("mire", frozenset()), INTRUS: ("intrus", frozenset())}
APRES_OUVERTURE = datetime(2026, 11, 14, 10, tzinfo=UTC)

ASPI = k.Aspiration.lire(k.derniere_aspiration())


class Site:
    def __init__(self, depot):
        self.maintenant = APRES_OUVERTURE
        self.appels: list[str] = []
        config = Config(SITE_MODE="auto", SITE_URL=SITE, DISCORD_GUILD_ID=1, DISCORD_ADMIN_ROLE_IDS=str(ROLE_ADMIN),
                        DISCORD_CLIENT_SECRET="secret-de-test", _env_file=None)
        oauth = ClientOAuth(config.discord_client_id, SecretStr("secret-de-test"), config.redirect_uri, 1,
                            transport=faux_discord(MEMBRES, self.appels))
        self.app = creer_app(config, horloge=lambda: self.maintenant, source=depot, oauth=oauth, regles=Regles())

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=SITE, follow_redirects=False)

    async def connecter(self, discord_id: int) -> httpx.AsyncClient:
        c = self.client()
        r = await c.get("/connexion")
        state = re.search(r"state=([^&]+)", r.headers["location"]).group(1)
        r = await c.get(f"/auth/discord/retour?code=code-{discord_id}&state={state}")
        assert r.status_code == 303, r.text
        return c

    @staticmethod
    async def csrf(c: httpx.AsyncClient, chemin: str = "/") -> str:
        return re.search(r'<meta name="csrf" content="([^"]*)"', (await c.get(chemin)).text).group(1)


@pytest.fixture
async def site(depot, moteur):
    cfg, retenus = k.lire_config_etages(), k.lire_dofus_retenus()
    for n in (0, 1):
        await ecrire_etage(moteur, k.construire(n, ASPI, cfg, retenus), datetime(2026, 10, 29, tzinfo=UTC))
    return Site(depot)


async def test_parcours_complet_du_lot_b(site, depot, moteur):
    # Sans base ou sans fiche : la santé dit « ok » avec la vraie base.
    async with site.client() as visiteur:
        assert (await visiteur.get("/sante")).json()["base"] == "ok"

    # L'admin colle les mentions de la liste officielle.
    admin = await site.connecter(ADMIN)
    t = await site.csrf(admin, "/admin/grimpeurs")
    r = await admin.post("/admin/liste", data={"csrf": t, "mentions": f"<@{BRINDILLE}> <@!{MIRELUNE}>",
                                                 "statut_initial": "actif"}, headers={"Origin": SITE})
    assert r.status_code == 303 and await depot.liste_officielle() == {BRINDILLE: "actif", MIRELUNE: "actif"}

    # Un grimpeur se connecte pour la première fois et crée sa fiche.
    brindille = await site.connecter(BRINDILLE)
    assert (await brindille.get("/")).headers.get("location") == "/inscription"
    t = await site.csrf(brindille, "/inscription")
    r = await brindille.post("/inscription", data={"csrf": t, "pseudo": "Brindille", "classe": "Féca", "niveau": ""},
                             headers={"Origin": SITE})
    assert r.status_code == 303
    g = await depot.grimpeur_par_discord(BRINDILLE)
    assert (g.pseudo, g.statut) == ("Brindille", "actif")

    # Un membre hors liste ne crée rien.
    intrus = await site.connecter(INTRUS)
    assert "Shadoaze" in (await intrus.get("/inscription")).text

    # La tour et l'étage 0 réels ; l'étage 1 est scellé.
    assert 'class="prologue"' in (await brindille.get("/")).text  # première connexion : le prologue d'abord
    t = await site.csrf(brindille, "/histoire")
    r = await brindille.post("/histoire/vu", data={"csrf": t}, headers={"Origin": SITE})
    assert r.status_code == 303
    tour = (await brindille.get("/")).text
    assert "L'anneau de tous les dangers" not in tour and 'href="/etages/0"' in tour
    etage0 = await brindille.get("/etages/0")
    assert etage0.status_code == 200 and "L&#39;anneau de tous les dangers" in etage0.text
    assert "Crypte de Kardorim" in etage0.text
    assert (await brindille.get("/etages/1")).status_code == 404
    assert "Grange du Tournesol" not in etage0.text  # rien de l'étage scellé

    # Cocher une sous-case : la cascade coche la classique, la jauge suit.
    e0 = await depot.etage_par_numero(0)
    contenu = await depot.contenu_etage(e0.id)
    donjon = contenu.donjons[0]
    zombie = next(c for c in contenu.cases_du_donjon(donjon.id) if "Zombie" in c.nom)
    t = await site.csrf(brindille, "/etages/0")
    r = await brindille.post("/api/coches", json={"type": "case", "id": zombie.id, "cochee": True},
                             headers={"X-CSRF-Token": t, "Origin": SITE})
    corps = r.json()
    assert r.status_code == 200 and corps["ok"] and corps["moi"]["categories"]["donjons"]["faits"] == 1
    assert corps["moi"]["points"] == 1 and corps["jauge"]["score"] == 1 and corps["jauge"]["palier"] == 2
    assert set(corps["compteurs"]) == {f"case:{zombie.id}", f"case:{contenu.cases_du_donjon(donjon.id)[0].id}"}
    principale = next(q for q in contenu.quetes if q.nature == "principale")
    r = await brindille.post("/api/coches", json={"type": "quete", "id": principale.id, "cochee": True},
                             headers={"X-CSRF-Token": t, "Origin": SITE})
    assert r.json()["compteurs"] == {f"quete:{principale.id}": 1}

    # La fiche de quête réelle, en page complète : parité, aucun lien vers duffus.fr hors pied de page.
    avec_prerequis = None
    for q in contenu.quetes:
        if (await depot.fiche_quete(q.id)).prerequis:
            avec_prerequis = q
            break
    fiche = await brindille.get(f"/etages/0/quetes/{avec_prerequis.id}")
    assert fiche.status_code == 200 and avec_prerequis.nom.replace("'", "&#39;") in fiche.text
    corps_fiche = fiche.text.split("<footer")[0]
    assert "duffus" not in corps_fiche.lower() and "supabase" not in corps_fiche.lower()
    assert "<script>" not in corps_fiche

    # Qui ne l'a pas fait ? (actifs seulement)
    m = await brindille.get(f"/api/etages/0/manque?type=quete&id={principale.id}")
    assert [x["pseudo"] for x in m.json()["fait"]] == ["Brindille"]

    # L'admin ouvre l'étage 1 en forçant (jauge non pleine), avec un motif.
    t = await site.csrf(admin, "/admin/etages/0")
    r = await admin.post("/admin/etages/1/ouvrir", data={"csrf": t, "forcer": "oui", "motif": "recette"},
                         headers={"Origin": SITE})
    assert r.status_code == 303 and "fait=ouvert" in r.headers["location"]
    assert (await depot.etage_par_numero(0)).statut == "termine" and (await depot.bilan(e0.id)).force
    etage1 = await brindille.get("/etages/1")
    assert etage1.status_code == 200 and "Grange du Tournesol Affamé" in etage1.text
    assert {e.type for e in await depot.journal()} >= {"liste_ajout", "inscription", "coche", "ouverture"}

    # Déconnexion : la session disparaît de la base et le jeton est révoqué chez Discord.
    t = await site.csrf(brindille, "/")
    await brindille.post("/deconnexion", data={"csrf": t}, headers={"Origin": SITE})
    assert (await brindille.get("/etages/0")).status_code in (303, 401)
    assert any("revoke" in a for a in site.appels)
    async with moteur.connect() as c:
        assert (await c.execute(text("SELECT count(*) FROM epreuve.session"))).scalar() == 2  # admin, intrus
    for c in (admin, brindille, intrus):
        await c.aclose()


async def test_teaser_avant_le_13_un_joueur_ne_voit_que_le_teaser(site, depot):
    site.maintenant = datetime(2026, 11, 10, 12, tzinfo=UTC)
    await depot.ajouter_liste([BRINDILLE], "actif", ADMIN, site.maintenant)
    brindille = await site.connecter(BRINDILLE)
    assert (await brindille.get("/inscription")).headers["location"] == "/"
    assert "teaser" in (await brindille.get("/")).text.lower()
    admin = await site.connecter(ADMIN)
    assert (await admin.get("/etages/0")).status_code == 200
    assert await depot.grimpeur_par_discord(BRINDILLE) is None
    await brindille.aclose()
    await admin.aclose()


async def test_sessions_purgees_chaque_jour(depot):
    from epreuve.main import purger_chaque_jour

    await depot.creer_session(b"x", 1, "d", False, "j", "c", APRES_OUVERTURE - timedelta(days=30), timedelta(days=7))
    attentes = []

    async def attendre(s):
        attentes.append(s)
        raise RuntimeError("fin du test")

    with pytest.raises(RuntimeError):
        await purger_chaque_jour(depot, lambda: APRES_OUVERTURE, attendre)
    assert attentes == [86400] and await depot.session(b"x", APRES_OUVERTURE - timedelta(days=29)) is None


async def test_image_d_ambiance_suit_l_ouverture(site, depot):
    e0, e1 = await depot.etage_par_numero(0), await depot.etage_par_numero(1)
    assert (e0.ambiance_url, e1.ambiance_url) == ("/etages/0/image", "/etages/1/image")
    await depot.ajouter_liste([BRINDILLE], "actif", ADMIN, APRES_OUVERTURE)
    await depot.creer_grimpeur(BRINDILLE, "b", "Brindille", None, None, APRES_OUVERTURE)
    brindille = await site.connecter(BRINDILLE)
    assert 'data-ambiance="/etages/0/image"' in (await brindille.get("/etages/0")).text
    assert (await brindille.get("/etages/0/image")).status_code == 200
    assert (await brindille.get("/etages/1/image")).status_code == 404
    jauge = EtatJauge(0, 0, False, 1, 0, 4, {})
    await depot.ouvrir_etage(1, bilan_etage(jauge, APRES_OUVERTURE, True, "test"), ADMIN, APRES_OUVERTURE)
    assert (await brindille.get("/etages/1/image")).status_code == 200
    await brindille.aclose()
