"""L'ouverture automatique de l'étage suivant et l'annonce du Gardien de la Tour (demande de Shadoaze).

Le monde de démonstration : étage 0 ouvert, jauge 19/20, date plancher (13/11) passée à l'horloge de la démo
(15/11). Pépin-Lagrume (grimpeur 5) a le bloc secondaire mais pas les principaux (blocs 1 et 2) : cocher les
deux lui apporte le point qui remplit la jauge. Discord est simulé par `httpx.MockTransport` : aucun appel réseau.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import replace
from datetime import timedelta

import httpx
import pytest
from pydantic import SecretStr

from epreuve.db.depot import EtatInvalide
from epreuve.discord.webhook import poster_webhook
from epreuve.domaine.modeles import Regles
from epreuve.web import ouverture_auto
from epreuve.web.demo import _id_discord
from epreuve.web.ouverture_auto import annoncer, annoncer_lancement, ouvrir_si_pret, veiller
from epreuve.web.vues import charger_vue_etage
from tests.web.outils import SITE, cocher, monde
from tests.web.test_admin import admin, poster

ID_PEPIN = _id_discord(5)
WEBHOOK = "https://discord.test/api/webhooks/1/secret-du-webhook"


def avec_webhook(m, statut: int = 204, erreur: Exception | None = None) -> list[httpx.Request]:
    """Règle le webhook et un faux Discord sur l'application ; renvoie la liste des requêtes reçues."""
    recues: list[httpx.Request] = []

    def repondre(req: httpx.Request) -> httpx.Response:
        recues.append(req)
        if erreur is not None:
            raise erreur
        return httpx.Response(statut)

    s = m.app.state
    s.config = s.config.model_copy(update={"discord_webhook_annonces": SecretStr(WEBHOOK)})
    s.transport_webhook = httpx.MockTransport(repondre)
    return recues


def pepin(**kw):
    """Pépin connecté, le bloc principal 1 déjà coché : il ne lui manque que le bloc 2 pour le point."""
    m = monde(**kw)
    c = m.connecter(ID_PEPIN)
    t = m.csrf(c)
    assert cocher(c, t, type="bloc", id=1, cochee=True).json()["jauge"]["score"] == 19
    assert statuts(m)[1] == "scelle"
    return m, c, t


def sans_delai(m):
    """Délai de grâce à 0 : l'ancienne ouverture immédiate, pour les tests de l'annonce et des routes admin."""
    m.app.state.regles = replace(m.app.state.regles, delai_grace_secondes=0)
    return m


def plus_tard(m, secondes: float) -> None:
    m.maintenant[0] += timedelta(seconds=secondes)  # l'horloge injectée avance, sans sommeil réel


def regarder(m):
    return asyncio.run(ouvrir_si_pret(m.app.state))


def statuts(m) -> dict[int, str]:
    return {e.numero: e.statut for e in m.depot._etages.values()}


def ouvertures(m) -> list:
    return [x for x in m.depot._journal if x.type == "ouverture"]


# ---------------------------------------------------------------- l'ouverture


def test_la_coche_qui_remplit_la_jauge_ouvre_l_etage_suivant_une_minute_apres():
    m, c, t = pepin()
    r = cocher(c, t, type="bloc", id=2, cochee=True)
    assert r.status_code == 200 and r.json()["ok"] and r.json()["jauge"]["score"] == 20
    assert statuts(m)[1] == "scelle"  # pas tout de suite : le temps de rattraper une coche par erreur
    plus_tard(m, 59)
    assert regarder(m) is None and statuts(m)[1] == "scelle"
    plus_tard(m, 1)
    assert regarder(m).numero == 1  # pleine depuis 60 s d'affilée
    assert statuts(m) == {0: "termine", 1: "ouvert", 2: "scelle", 3: "scelle"}  # un seul étage, le suivant
    b = m.depot._bilans[1]
    assert (b.score, b.palier, b.force, b.motif) == (20, 20, False, None)  # bilan non forcé
    (o,) = ouvertures(m)
    assert o.acteur_discord_id is None and o.etage_id == 2  # acteur système : NULL au journal
    assert m.app.state.pleine_depuis == {}  # la note de l'étage 0 ne compte pas pour l'étage 1
    # Une seconde coche ne rouvre rien : l'étage 1 vient d'ouvrir, sa jauge est vide.
    cocher(c, t, type="bloc", id=1, cochee=False)
    plus_tard(m, 3600)
    assert regarder(m) is None and len(ouvertures(m)) == 1 and statuts(m)[2] == "scelle"


def test_decocher_avant_la_minute_n_ouvre_rien_et_le_compte_repart_de_zero():
    m, c, t = pepin()
    cocher(c, t, type="bloc", id=2, cochee=True)  # la coche par erreur qui remplit la jauge
    plus_tard(m, 30)
    assert cocher(c, t, type="bloc", id=2, cochee=False).json()["jauge"]["score"] == 19  # rattrapée
    assert m.app.state.pleine_depuis == {}
    plus_tard(m, 30)
    assert regarder(m) is None and statuts(m)[1] == "scelle" and not ouvertures(m)
    # Recochée : une nouvelle minute pleine, comptée depuis cette coche-ci, pas depuis la première.
    cocher(c, t, type="bloc", id=2, cochee=True)
    plus_tard(m, 59)
    assert regarder(m) is None
    plus_tard(m, 1)
    assert regarder(m).numero == 1 and len(ouvertures(m)) == 1


def test_apres_un_redemarrage_le_compte_repart_de_zero():
    m, c, t = pepin()
    cocher(c, t, type="bloc", id=2, cochee=True)
    plus_tard(m, 59)
    m.app.state.pleine_depuis = {}  # redémarrage : la note vivait en mémoire
    plus_tard(m, 1)
    assert regarder(m) is None  # premier regard après le redémarrage : il note, il n'ouvre pas
    plus_tard(m, 60)
    assert regarder(m).numero == 1  # une minute de retard au pire


def test_la_veille_se_reveille_pile_a_la_fin_du_delai():
    m, c, t = pepin()
    cocher(c, t, type="bloc", id=2, cochee=True)
    rempli_le = m.horloge()
    plus_tard(m, 25)  # la veille dormait pendant la coche : elle la voit à son regard suivant
    attentes: list[float] = []

    async def attendre(duree):
        attentes.append(duree)
        plus_tard(m, duree)
        if len(attentes) == 2:
            raise Arret

    with pytest.raises(Arret):
        asyncio.run(veiller(m.app.state, attendre=attendre, periode=60))
    assert attentes == [35, 60]  # 25 + 35 : ouverte 60 s après la coche, pas 119 s
    (o,) = ouvertures(m)
    assert o.horodatage == rempli_le + timedelta(seconds=60) and statuts(m)[1] == "ouvert"


def test_pas_d_ouverture_avant_la_date_plancher_puis_la_veille_ouvre_a_l_heure():
    m, c, t = pepin()
    plancher = m.horloge() + timedelta(days=1)
    m.depot._etages[1] = replace(m.depot._etages[1], date_plancher_suivant=plancher)
    cocher(c, t, type="bloc", id=2, cochee=True)  # jauge pleine, mais trop tôt
    assert statuts(m)[1] == "scelle"
    # Le lendemain, plus personne ne coche : c'est la veille de fond qui ouvre.
    m.maintenant[0] = plancher
    ouvert = asyncio.run(ouvrir_si_pret(m.app.state))
    assert ouvert is not None and ouvert.numero == 1 and statuts(m)[1] == "ouvert"


def test_pas_d_ouverture_sans_etage_scelle():
    m, c, t = pepin()
    for i in (2, 3, 4):
        del m.depot._etages[i]  # aucun étage préparé
    assert cocher(c, t, type="bloc", id=2, cochee=True).status_code == 200
    assert statuts(m) == {0: "ouvert"} and not ouvertures(m)


def test_pas_d_ouverture_si_le_reglage_est_coupe():
    m, c, t = pepin(regles=Regles(monde_des_douze=True, ouverture_automatique=False))
    recues = avec_webhook(m)
    cocher(c, t, type="bloc", id=2, cochee=True)
    plus_tard(m, 3600)  # même pleine depuis une heure
    assert regarder(m) is None
    assert statuts(m)[1] == "scelle" and not ouvertures(m) and not recues


def test_ouverture_auto_teaser_attend_aussi_la_minute():
    # La recette des admins pendant le teaser (OUVERTURE_AUTO_TEASER) suit le même délai, sans annonce.
    m = monde(mode="teaser")
    m.app.state.config = m.app.state.config.model_copy(update={"ouverture_auto_teaser": True})
    recues = avec_webhook(m)
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)  # jauge pleine
    assert regarder(m) is None
    plus_tard(m, 60)
    ouvert = regarder(m)
    assert ouvert.numero == 1 and statuts(m)[1] == "ouvert"
    assert asyncio.run(annoncer(m.app.state, ouvert)) is False and not recues


def test_rien_pendant_le_teaser():
    m = monde(mode="teaser")
    recues = avec_webhook(m)
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)  # jauge pleine
    assert asyncio.run(ouvrir_si_pret(m.app.state)) is None
    plus_tard(m, 3600)
    assert asyncio.run(ouvrir_si_pret(m.app.state)) is None
    assert statuts(m)[1] == "scelle"
    # Une ouverture de recette par un admin pendant le teaser ne prévient pas tout le serveur.
    assert asyncio.run(annoncer(m.app.state, m.depot._etages[2])) is False and not recues


def test_deux_coches_simultanees_une_seule_ouverture(monkeypatch):
    m = monde()
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)
    assert regarder(m) is None  # la jauge pleine est notée…
    plus_tard(m, 60)  # … et le délai de grâce est écoulé pour les deux tentatives
    vrai = m.depot.ouvrir_etage

    async def lent(*a, **k):  # les deux tentatives lisent l'état avant que l'une n'écrive
        await asyncio.sleep(0)
        return await vrai(*a, **k)

    monkeypatch.setattr(m.depot, "ouvrir_etage", lent)

    async def deux():
        return await asyncio.gather(ouvrir_si_pret(m.app.state), ouvrir_si_pret(m.app.state))

    r = asyncio.run(deux())
    assert sum(x is not None for x in r) == 1
    assert len(ouvertures(m)) == 1 and statuts(m) == {0: "termine", 1: "ouvert", 2: "scelle", 3: "scelle"}


def test_sans_base_ou_sans_etage_ouvert_rien_a_faire():
    m = monde()
    m.app.state.depot = None
    assert asyncio.run(ouvrir_si_pret(m.app.state)) is None
    m = monde()
    m.depot._etages[1] = replace(m.depot._etages[1], statut="termine")
    assert asyncio.run(ouvrir_si_pret(m.app.state)) is None


def test_une_erreur_de_l_ouverture_auto_ne_casse_pas_la_coche(monkeypatch, caplog):
    m, c, t = pepin()

    async def panne(_s):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(ouverture_auto, "ouvrir_si_pret", panne)
    with caplog.at_level(logging.ERROR, logger="epreuve.ouverture"):
        r = cocher(c, t, type="bloc", id=2, cochee=True)
    assert r.status_code == 200 and r.json()["changement"] is True
    assert "ouverture automatique impossible" in caplog.text


# ---------------------------------------------------------------- l'admin


def test_un_palier_baisse_par_l_admin_ouvre_et_le_dit():
    m, c, t = admin()
    sans_delai(m)
    recues = avec_webhook(m)
    r = poster(c, t, "/admin/etages/0/palier", palier="12", motif="catégorie vide")
    assert r.headers["location"] == "/admin/etages/0?fait=auto"
    assert "l&#39;étage suivant s&#39;est ouvert automatiquement" in c.get(r.headers["location"]).text
    assert statuts(m)[1] == "ouvert" and len(recues) == 1
    assert "système" in c.get("/admin/journal").text  # l'auteur de l'ouverture, au journal admin


def test_geler_un_grimpeur_peut_ouvrir():
    m, c, t = admin()
    sans_delai(m)
    # Jauge 19/20 avec 10 actifs : geler l'actif qui a le moins de points (au plus 1) baisse le palier de 2.
    vue = asyncio.run(charger_vue_etage(m.depot, m.depot._etages[1], m.app.state.regles))
    g = min((g for g in vue.grimpeurs if g.statut == "actif"), key=lambda g: vue.points(g.id))
    assert vue.points(g.id) <= 1
    r = poster(c, t, f"/admin/grimpeurs/{g.id}/statut", statut="pause")
    assert r.headers["location"] == "/admin/grimpeurs?fait=auto" and statuts(m)[1] == "ouvert"


def test_l_ouverture_manuelle_est_annoncee_aussi():
    m, c, t = admin()
    recues = avec_webhook(m)
    r = poster(c, t, "/admin/etages/1/ouvrir", forcer="oui", motif="voulu par Shadoaze")
    assert r.headers["location"].endswith("fait=ouvert") and len(recues) == 1
    assert json.loads(recues[0].content)["embeds"][0]["title"] == "L'étage 1 s'éveille"


# ---------------------------------------------------------------- l'annonce


def test_l_ouverture_est_annoncee_avec_everyone():
    m, c, t = pepin()
    sans_delai(m)
    recues = avec_webhook(m)
    cocher(c, t, type="bloc", id=2, cochee=True)
    (req,) = recues
    assert req.method == "POST" and str(req.url) == WEBHOOK
    corps = json.loads(req.content)
    assert corps["username"] == "Gardien de la Tour" and corps["content"].startswith("@everyone")
    assert corps["allowed_mentions"] == {"parse": ["everyone"]}
    assert corps["embeds"][0]["url"] == f"{SITE}/etages/1" and corps["embeds"][0]["color"] == 0xD4A84B


@pytest.mark.parametrize("panne", [{"statut": 500}, {"erreur": httpx.ConnectTimeout("délai dépassé")}])
def test_un_webhook_en_panne_n_empeche_pas_l_ouverture(panne, caplog):
    m, c, t = pepin()
    sans_delai(m)
    recues = avec_webhook(m, **panne)
    with caplog.at_level(logging.WARNING, logger="epreuve.discord.webhook"):
        r = cocher(c, t, type="bloc", id=2, cochee=True)
    assert r.status_code == 200 and statuts(m)[1] == "ouvert" and len(recues) == 1
    assert "annonce Discord" in caplog.text and "secret-du-webhook" not in caplog.text  # jamais l'adresse


def test_sans_webhook_aucun_appel():
    m, c, t = pepin()
    sans_delai(m)
    recues = avec_webhook(m)
    m.app.state.config = m.app.state.config.model_copy(update={"discord_webhook_annonces": None})
    cocher(c, t, type="bloc", id=2, cochee=True)
    assert statuts(m)[1] == "ouvert" and not recues


def test_poster_webhook_reponses():
    def transport(statut):
        return httpx.MockTransport(lambda _r: httpx.Response(statut))

    assert asyncio.run(poster_webhook(WEBHOOK, {}, transport=transport(204))) is True
    assert asyncio.run(poster_webhook(WEBHOOK, {}, transport=transport(429))) is False


def test_poster_webhook_adresse_mal_formee_ne_leve_pas(caplog):
    with caplog.at_level(logging.WARNING, logger="epreuve.discord.webhook"):
        assert asyncio.run(poster_webhook("pas une adresse", {})) is False
    assert "non envoyée" in caplog.text


# ---------------------------------------------------------------- la veille de fond


class Arret(Exception):
    pass


def test_la_veille_regarde_au_demarrage_puis_a_chaque_periode():
    m = monde()
    recues = avec_webhook(m)
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)
    attentes: list[float] = []

    async def attendre(duree):
        attentes.append(duree)
        plus_tard(m, duree)
        if len(attentes) == 3:
            raise Arret

    with pytest.raises(Arret):
        asyncio.run(veiller(m.app.state, attendre=attendre, periode=60))
    # 1er regard : la jauge pleine est notée ; 2e, une minute plus tard : ouverture ; 3e : rien en double.
    assert attentes == [60, 60, 60] and statuts(m)[1] == "ouvert" and len(recues) == 1


def test_la_veille_survit_a_une_panne(monkeypatch, caplog):
    m = monde()

    async def panne():
        raise EtatInvalide("base en vrac")

    monkeypatch.setattr(m.depot, "etages", panne)

    async def attendre(_duree):
        raise Arret

    with caplog.at_level(logging.ERROR, logger="epreuve.ouverture"), pytest.raises(Arret):
        asyncio.run(veiller(m.app.state, attendre=attendre))
    assert "ouverture automatique impossible" in caplog.text


# ---------------------------------------------------------------- le lancement du site (13/11, 17 h)


def lancement(**kw):
    """Le site en mode auto, l'horloge pile à l'heure du lancement (SITE_OUVERT_LE par défaut)."""
    m = monde(mode="auto")
    m.maintenant[0] = m.app.state.config.site_ouvert_le + kw.get("decalage", timedelta(0))
    return m


def annonces_lancement(m) -> list:
    return [x for x in m.depot._journal if x.type == "annonce_lancement"]


def test_le_lancement_est_annonce_une_seule_fois():
    m = lancement()
    recues = avec_webhook(m)
    assert asyncio.run(annoncer_lancement(m.app.state)) is True
    assert asyncio.run(annoncer_lancement(m.app.state)) is False  # deuxième regard : déjà inscrit
    (req,) = recues
    corps = json.loads(req.content)
    assert corps["content"].startswith("@everyone") and corps["allowed_mentions"] == {"parse": ["everyone"]}
    assert corps["embeds"][0]["url"] == f"{SITE}/connexion"
    (ligne,) = annonces_lancement(m)
    assert ligne.acteur_discord_id is None and ligne.public is False


def test_deux_veilles_simultanees_un_seul_envoi():
    m = lancement()
    recues = avec_webhook(m)

    async def deux():
        return await asyncio.gather(annoncer_lancement(m.app.state), annoncer_lancement(m.app.state))

    assert sorted(asyncio.run(deux())) == [False, True] and len(recues) == 1


def test_la_reservation_perdue_n_envoie_rien(monkeypatch):
    # Une autre machine a réservé entre notre lecture du journal et notre écriture.
    m = lancement()
    recues = avec_webhook(m)

    async def deja_prise(_maintenant):
        return False

    monkeypatch.setattr(m.depot, "reserver_annonce_lancement", deja_prise)
    assert asyncio.run(annoncer_lancement(m.app.state)) is False and not recues


@pytest.mark.parametrize("decalage", [-timedelta(seconds=1), timedelta(hours=6)])
def test_pas_d_annonce_hors_de_la_fenetre(decalage):
    m = lancement(decalage=decalage)
    recues = avec_webhook(m)
    assert asyncio.run(annoncer_lancement(m.app.state)) is False
    assert not recues and not annonces_lancement(m)


def test_lancement_sans_webhook_ni_reservation():
    m = lancement()
    assert asyncio.run(annoncer_lancement(m.app.state)) is False
    assert not annonces_lancement(m)  # configuré plus tard dans la fenêtre, il annoncera encore
    m.app.state.depot = None
    avec_webhook(m)
    assert asyncio.run(annoncer_lancement(m.app.state)) is False


def test_lancement_tenu_en_teaser_force():
    m = lancement()
    m.app.state.config = m.app.state.config.model_copy(update={"site_mode": "teaser"})
    recues = avec_webhook(m)
    assert asyncio.run(annoncer_lancement(m.app.state)) is False and not recues


@pytest.mark.parametrize("panne", [{"statut": 500}, {"erreur": httpx.ConnectTimeout("délai dépassé")}])
def test_lancement_discord_en_panne_journalise_sans_nouvel_essai(panne, caplog):
    m = lancement()
    recues = avec_webhook(m, **panne)
    with caplog.at_level(logging.WARNING):
        assert asyncio.run(annoncer_lancement(m.app.state)) is False
        assert asyncio.run(annoncer_lancement(m.app.state)) is False
    assert len(recues) == 1 and len(annonces_lancement(m)) == 1  # la ligne reste prise : pas de second @everyone
    assert "annonce du lancement non envoyée" in caplog.text and "secret-du-webhook" not in caplog.text


def test_la_veille_se_reveille_pile_a_l_heure_du_lancement():
    m = lancement(decalage=-timedelta(seconds=20))
    recues = avec_webhook(m)
    attentes: list[float] = []

    async def attendre(duree):
        attentes.append(duree)
        m.maintenant[0] += timedelta(seconds=duree)  # l'horloge avance de l'attente, sans sommeil réel
        if len(attentes) == 3:
            raise Arret

    with pytest.raises(Arret):
        asyncio.run(veiller(m.app.state, attendre=attendre, periode=60))
    assert attentes == [20, 60, 60] and len(recues) == 1  # envoyé au deuxième regard, à 17 h 00 pile
    assert annonces_lancement(m)[0].horodatage == m.app.state.config.site_ouvert_le


def test_une_panne_du_lancement_n_arrete_pas_la_veille(monkeypatch, caplog):
    m = monde()

    async def panne(_s):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(ouverture_auto, "annoncer_lancement", panne)
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)
    sans_delai(m)

    async def attendre(_duree):
        raise Arret

    with caplog.at_level(logging.ERROR, logger="epreuve.ouverture"), pytest.raises(Arret):
        asyncio.run(veiller(m.app.state, attendre=attendre))
    assert "annonce du lancement impossible" in caplog.text and statuts(m)[1] == "ouvert"
