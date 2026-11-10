"""La pré-inscription (décision du 07/11) : du mercredi 11/11 17 h au vendredi 13/11 17 h, un joueur crée sa
fiche derrière le compte à rebours, sur une page seule ; le reste du site reste fermé jusqu'à l'ouverture.
Passé l'ouverture, plus personne ne s'ajoute, sauf un admin. Et la question de Shadoaze (10/11) : dispo
vendredi 16 h-17 h pour rejoindre la guilde, sinon à partir de quand.
"""

import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from epreuve.domaine.modeles import Regles
from tests.web.outils import AVANT_OUVERTURE, ID_BRINDILLE, ID_MARCEAU, ID_NOUVELLE, PENDANT_FICHES, SITE, monde

APRES_OUVERTURE = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


def _csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]*)"', html).group(1)


def _poster(c, **champs):
    return c.post("/inscription", data={"csrf": _csrf(c.get("/inscription").text), **champs},
                  headers={"Origin": SITE})


def test_teaser_sans_bouton_avant_le_11():
    m = monde(mode="auto", maintenant=AVANT_OUVERTURE)
    assert "Créer ma fiche" not in m.client().get("/").text
    assert "Créer ma fiche" not in m.connecter(ID_NOUVELLE).get("/").text


def test_teaser_bouton_creer_ma_fiche_pendant_la_fenetre():
    m = monde(mode="auto", maintenant=PENDANT_FICHES)
    html = m.client().get("/").text
    assert "teaser.js" in html and "Les fiches sont ouvertes" in html
    assert '<a class="enter" href="/connexion">Créer ma fiche' in html  # pas connecté : la connexion d'abord
    c = m.connecter(ID_NOUVELLE)
    assert '<a class="enter" href="/inscription">Créer ma fiche' in c.get("/").text
    html = m.connecter(ID_BRINDILLE).get("/").text  # a déjà sa fiche
    assert "Ta fiche est prête, Brindille" in html and "Créer ma fiche" not in html


def test_retour_discord_mene_a_la_fiche_pendant_la_fenetre():
    m = monde(mode="auto", maintenant=PENDANT_FICHES)
    c = m.client()
    state = parse_qs(urlparse(c.get("/connexion").headers["location"]).query)["state"][0]
    assert c.get(f"/auth/discord/retour?code=code-{ID_NOUVELLE}&state={state}").headers["location"] == "/inscription"


def test_fiche_seule_le_reste_du_site_ferme():
    m = monde(mode="auto", maintenant=PENDANT_FICHES)
    c = m.connecter(ID_NOUVELLE)
    html = c.get("/inscription").text
    assert "<form" in html and "Seras-tu là vendredi 13 novembre entre 16 h et 17 h" in html
    assert "Tableau de bord" not in html and "Grimpeurs" not in html and "duffus" not in html.lower()
    assert 'href="/">← Retour au compte à rebours' in html
    assert c.get("/static/commun.css").status_code == 200
    for chemin in ("/etages/0", "/grimpeurs", "/regles", "/tableau-de-bord", "/admin"):
        assert c.get(chemin).headers["location"] == "/", chemin
    assert c.post("/api/coches", json={}).status_code == 404


def test_dispo_obligatoire_pour_la_pre_inscription():
    m = monde(mode="auto", maintenant=PENDANT_FICHES)
    c = m.connecter(ID_NOUVELLE)
    r = _poster(c, pseudo="Lune", classe="Crâ")
    assert r.status_code == 422 and "Dis-nous si tu es là" in r.text and "Tableau de bord" not in r.text
    r = _poster(c, pseudo="Lune", classe="Crâ", dispo="non", dispo_quand="   ")
    assert r.status_code == 422 and "Dis-nous à partir de quand" in r.text
    assert _poster(c, pseudo="Lune", classe="Crâ", dispo="non", dispo_quand="x" * 101).status_code == 422
    assert len(m.depot._grimpeurs) == 13


def test_pre_inscription_puis_retour_au_compte_a_rebours():
    m = monde(mode="auto", maintenant=PENDANT_FICHES)
    c = m.connecter(ID_NOUVELLE)
    r = _poster(c, pseudo="Lune", classe="Crâ", dispo="non", dispo_quand="  samedi   14 h ")
    assert r.status_code == 303 and r.headers["location"] == "/"
    g = m.depot._grimpeurs[14]
    assert (g.pseudo, g.classe, g.statut, g.dispo_guilde) == ("Lune", "Crâ", "actif", "samedi 14 h")
    assert "Ta fiche est prête, Lune" in c.get("/").text
    assert c.get("/inscription").headers["location"] == "/"  # une seule fiche


def test_dispo_oui_et_affichage_admin():
    m = monde(maintenant=PENDANT_FICHES)
    c = m.connecter(ID_NOUVELLE)
    _poster(c, pseudo="Lune", dispo="oui")
    assert m.depot._grimpeurs[14].dispo_guilde == "oui"
    html = m.connecter(ID_MARCEAU).get("/admin/grimpeurs").text
    assert "Guilde vendredi" in html and "vendredi 16 h-17 h" in html


def test_dispo_facultative_pour_un_admin():
    m = monde(maintenant=PENDANT_FICHES)
    c = m.connecter(ID_MARCEAU)
    assert _poster(c, pseudo="Mars").status_code == 303
    assert m.depot._grimpeurs[14].dispo_guilde is None


def test_fiches_closes_apres_l_ouverture_sauf_pour_un_admin():
    m = monde(mode="auto", maintenant=APRES_OUVERTURE)
    c = m.connecter(ID_NOUVELLE)
    r = c.get("/inscription")
    assert r.status_code == 403 and "Les inscriptions sont closes" in r.text
    assert c.post("/inscription", data={"csrf": "x", "pseudo": "Tard"}, headers={"Origin": SITE}).status_code == 403
    assert len(m.depot._grimpeurs) == 13
    admin = m.connecter(ID_MARCEAU)
    assert _poster(admin, pseudo="Mars").status_code == 303


def test_fermeture_reglable():
    m = monde(mode="auto", maintenant=APRES_OUVERTURE)
    m.app.state.config = m.app.state.config.model_copy(update={"fiches_fermees_le": datetime(2026, 11, 20, tzinfo=UTC)})
    c = m.connecter(ID_NOUVELLE)
    assert c.get("/inscription").status_code == 200


def test_serveur_dans_les_regles_jamais_sur_le_teaser():
    m = monde(regles=Regles(serveur="Mikhal"))
    assert "L'aventure se joue sur le serveur <b>Mikhal</b>" in m.connecter(ID_BRINDILLE).get("/regles").text
    for maintenant in (AVANT_OUVERTURE, PENDANT_FICHES):
        m = monde(mode="auto", maintenant=maintenant, regles=Regles(serveur="Mikhal"))
        html = m.client().get("/").text
        assert "Mikhal" not in html and "Kourial" not in html and "Serveur" not in html


def test_pied_de_page_les_auteurs():
    m = monde(mode="auto", maintenant=PENDANT_FICHES)
    for html in (m.client().get("/").text, m.connecter(ID_NOUVELLE).get("/inscription").text):
        pied = re.search(r"<footer>(.*?)</footer>", html, re.S).group(1)
        assert "Réalisé par Shadoaze et Mars" in pied and "Projet de fans, non officiel" in pied
        assert "code" not in pied


def test_recapitulatif_des_dispos_pour_les_admins():
    m = monde(maintenant=PENDANT_FICHES)
    _poster(m.connecter(ID_NOUVELLE), pseudo="Lune", dispo="non", dispo_quand="samedi 14 h")
    html = m.connecter(ID_MARCEAU).get("/admin/grimpeurs").text
    assert "Guilde, vendredi 16 h-17 h : 0 dispo" in html
    assert "À inviter plus tard (1)" in html and "<li>Lune : samedi 14 h</li>" in html


def test_tableau_de_bord_deux_cartes_distinctes():
    m = monde()
    html = m.connecter(ID_BRINDILLE).get("/tableau-de-bord").text
    assert 'class="card carte-profil"' in html and 'class="initiale" aria-hidden="true">B<' in html
    assert 'class="card carte-etage"' in html and "Étage en cours" in html


def test_stats_par_categorie_sur_le_tableau_de_bord():
    m = monde()
    html = m.connecter(ID_BRINDILLE).get("/tableau-de-bord").text
    assert "Mes points par catégorie" in html and html.count('<li><span>Blocs ') == 2
    autre = m.connecter(ID_MARCEAU).get("/grimpeurs/1").text
    assert "Ses points par catégorie" in autre


def test_profil_de_jeu():
    from types import SimpleNamespace as N

    from epreuve.web.tableau import stats_categories

    def bloc(**acquises):
        cats = {c: N(acquise=acquises.get(c, False), total=1)
                for c in ("donjons", "full_succes", "principales", "secondaires")}
        return N(vue=N(categories=lambda _gid, cats=cats: cats))

    assert stats_categories([bloc()], 1)[1] == ""
    stats, profil = stats_categories([bloc(donjons=True), bloc(donjons=True, principales=True)], 1)
    assert profil == "Plutôt donjons" and [(p, n) for _, p, n in stats] == [(2, 2), (0, 2), (1, 2), (0, 2)]
    assert stats_categories([bloc(donjons=True, secondaires=True)], 1)[1] == "Profil équilibré"


def test_regles_expliquent_duffus_et_le_bloc():
    html = monde().connecter(ID_BRINDILLE).get("/regles").text
    assert "tu y coches les quêtes une à une" in html and "seul le bloc compte pour les points" in html


def test_regles_lien_vers_le_guide_duffus():
    html = monde().connecter(ID_BRINDILLE).get("/regles").text
    assert ('tranche de niveaux du <a href="https://duffus.fr/guide-complet" target="_blank" rel="noopener">'
            'guide Duffus') in html


def test_verdicts_ouverture_automatique():
    from dataclasses import replace

    from epreuve.web.vues import verdicts

    m = monde()
    etage = replace(m.depot._etages[1], date_plancher_suivant=datetime(2026, 11, 13, 16, 0, tzinfo=UTC))
    plein, pas_plein = verdicts(etage, PENDANT_FICHES, Regles(), annonce=True)
    assert plein.startswith("Jauge pleine : le prochain étage s'ouvrira tout seul le vendredi 13 novembre à 17 h")
    assert "Gardien de la Tour" in plein and "pas avant le vendredi 13 novembre" in pas_plein
    plein, _ = verdicts(etage, APRES_OUVERTURE, Regles(delai_grace_secondes=30))
    assert plein == "Jauge pleine : le prochain étage s'ouvre tout seul dans 30 secondes, si elle reste pleine."
    assert "aussitôt" in verdicts(etage, APRES_OUVERTURE, Regles(delai_grace_secondes=0))[0]
    plein, pas_plein = verdicts(etage, PENDANT_FICHES, Regles(ouverture_automatique=False))
    assert "un admin va vérifier" in plein and "Un admin pourra ouvrir" in pas_plein
