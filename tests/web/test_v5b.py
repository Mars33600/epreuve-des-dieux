"""SPEC-V5 §2 et §7 : Monde des Douze désactivé, recherche réduite, comptes ouverts à tout le Discord."""

from __future__ import annotations

from epreuve.config import Config
from epreuve.domaine.modeles import Regles
from epreuve.regles import regles_depuis
from tests.web.outils import (
    ID_BRINDILLE,
    ID_HORS_LISTE,
    ID_NOUVELLE,
    SITE,
    monde,
)

MODULES = ["/encyclopedie", "/encyclopedie/objets", "/stuffs", "/builder", "/outils", "/outils/almanax",
           "/archimonstres", "/avis-de-recherche", "/api/builder/objets"]


def test_reglages_par_defaut():
    r = regles_depuis({})
    assert r.monde_des_douze is False and r.liste_officielle_obligatoire is False
    assert regles_depuis({"modules": {"monde_des_douze": True}}).monde_des_douze is True


def test_monde_des_douze_desactive_repond_404():
    m = monde(regles=Regles())  # valeur par défaut : désactivé
    c = m.connecter(ID_BRINDILLE)
    for chemin in MODULES:
        assert c.get(chemin).status_code == 404, chemin
    assert c.get("/etages/0/quetes/1").status_code == 404  # fiche de quête, aussi


def test_suivi_par_etape_desactive_repond_404():
    m = monde(regles=Regles())
    c = m.connecter(ID_BRINDILLE)
    r = c.post("/api/etapes", json={"quete_id": 102, "ordre": 1, "faite": True},
               headers={"X-CSRF-Token": m.csrf(c), "Origin": SITE})
    assert r.status_code == 404


def test_monde_des_douze_active_rallume_les_routes():
    c = monde(regles=Regles(monde_des_douze=True)).connecter(ID_BRINDILLE)
    assert c.get("/outils").status_code == 200 and c.get("/archimonstres").status_code == 200


def test_menu_sans_deroulant_dans_l_ordre():
    html = monde().connecter(ID_BRINDILLE).get("/regles").text
    nav = html.split('aria-label="Navigation principale"')[1].split("</nav>")[0]
    assert "deroulant" not in nav and "Monde des Douze" not in nav
    ordre = ["La Tour", "L'histoire", "Règles", "Tableau de bord", "Grimpeurs"]
    positions = [nav.index(f">{n}</a>") for n in ordre]
    assert positions == sorted(positions)


def test_tout_membre_du_discord_cree_sa_fiche_sans_liste():
    m = monde()  # liste_officielle_obligatoire: false par défaut
    c = m.connecter(ID_HORS_LISTE)
    assert "<form" in c.get("/inscription").text
    r = c.post("/inscription", data={"csrf": m.csrf(c, "/inscription"), "pseudo": "Passant"}, headers={"Origin": SITE})
    assert r.status_code == 303


def test_lien_creer_ma_fiche_dans_l_en_tete():
    m = monde()
    assert 'class="creer-fiche"' in m.connecter(ID_NOUVELLE).get("/inscription").text
    assert 'class="creer-fiche"' not in m.connecter(ID_BRINDILLE).get("/regles").text


def test_proprietaire_du_serveur_admin_d_office():
    assert ID_HORS_LISTE in Config(DISCORD_OWNER_ID=ID_HORS_LISTE, _env_file=None).admins_supplementaires
    assert not Config(_env_file=None).admins_supplementaires
    m = monde(owner_id=ID_HORS_LISTE)
    assert m.connecter(ID_HORS_LISTE).get("/admin").status_code == 200
    assert monde().connecter(ID_HORS_LISTE).get("/admin").status_code != 200


def test_admin_sans_fiche_voit_le_message_et_le_lien():
    m = monde(owner_id=ID_HORS_LISTE)
    html = m.connecter(ID_HORS_LISTE).get("/etages/0").text
    assert "Tu n'as pas encore de fiche" in html and 'class="creer-fiche"' in html
