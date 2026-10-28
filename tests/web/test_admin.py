"""L'admin : chaque action, ses validations et sa ligne de journal ; 403 pour un non-admin sur chaque route.

Critères 22 à 28 du lot B.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from epreuve.db.depot import EtatInvalide
from epreuve.web.demo import ID_MARCEAU, _id_discord
from tests.web.outils import ID_BRINDILLE, SITE, monde, routes_declarees


def admin():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    return m, c, m.csrf(c, "/admin")


def poster(c, t, chemin, **champs):
    return c.post(chemin, data={"csrf": t, **champs}, headers={"Origin": SITE})


def dernier(m, type_):
    return next(e for e in reversed(m.depot._journal) if e.type == type_)


def test_non_admin_403_sur_chaque_route_d_admin():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    t = m.csrf(c)
    routes = [r for r in routes_declarees(m.app) if getattr(r, "path", "").startswith("/admin")]
    assert len(routes) >= 16
    for r in routes:
        chemin = re.sub(r"\{[^}]+\}", "1", r.path)
        for methode in r.methods - {"HEAD"}:
            rep = c.request(methode, chemin, data={"csrf": t}, headers={"Origin": SITE}) if methode == "POST" \
                else c.request(methode, chemin)
            assert rep.status_code == 403, (methode, chemin)
    assert len(m.depot._journal) == 0


def test_post_admin_sans_csrf_refuse():
    m, c, t = admin()
    r = c.post("/admin/liste", data={"csrf": "faux", "mentions": "<@123456789012345678>"}, headers={"Origin": SITE})
    assert r.status_code == 403 and len(m.depot._liste) == 14


def test_liste_officielle_par_mentions_sans_doublon():
    m, c, t = admin()
    texte = "<@123456789012345678> <@!234567890123456789> 123456789012345678 <@300000000000000001>"
    r = poster(c, t, "/admin/liste", mentions=texte, statut_initial="pause")
    assert r.headers["location"] == "/admin/grimpeurs?fait=liste&n=2"
    assert m.depot._liste[123456789012345678] == "pause" and m.depot._liste[234567890123456789] == "pause"
    assert m.depot._liste[_id_discord(1)] == "actif"  # déjà présent : inchangé
    assert dernier(m, "liste_officielle").details["ajoutes"] == 2
    assert "2 nouvel(s) identifiant(s)" in c.get(r.headers["location"]).text
    assert poster(c, t, "/admin/liste", mentions="rien").headers["location"].endswith("erreur=ids")
    assert poster(c, t, "/admin/liste", mentions=texte, statut_initial="exclu").headers["location"].endswith(
        "erreur=statut")


def test_page_grimpeurs_annonce_l_effet_et_le_moins_avance():
    m, c, t = admin()
    html = c.get("/admin/grimpeurs").text
    assert "Geler (Palier 20 → 18)" in html and "Réintégrer (Palier 20 → 22)" in html
    assert "Le moins avancé des actifs : <b>Fleur-de-Bwork</b>" in html
    assert "moins avancé des actifs : Fleur-de-Bwork" in html  # sur la ligne d'un grimpeur gelé
    assert "Fiche à créer" in html and "300000000000000050" in html


def test_geler_puis_reintegrer_change_le_palier_tout_de_suite():
    m, c, t = admin()
    assert poster(c, t, "/admin/grimpeurs/2/statut", statut="pause", motif="absent").headers["location"].endswith(
        "fait=statut")
    assert "sur un palier de 18" in c.get("/etages/0").text
    e = dernier(m, "statut")
    assert e.grimpeur_id == 2 and e.details == {"statut": "pause", "motif": "absent"} and e.public is False
    poster(c, t, "/admin/grimpeurs/2/statut", statut="actif")
    assert "sur un palier de 20" in c.get("/etages/0").text


def test_exclure_demande_motif_et_confirmation_et_reste_reversible():
    m, c, t = admin()
    assert poster(c, t, "/admin/grimpeurs/2/statut", statut="exclu", confirmer="oui").headers["location"].endswith(
        "erreur=motif")
    assert poster(c, t, "/admin/grimpeurs/2/statut", statut="exclu", motif="triche").headers["location"].endswith(
        "erreur=confirmer")
    assert m.depot._grimpeurs[2].statut == "actif"
    poster(c, t, "/admin/grimpeurs/2/statut", statut="exclu", motif="triche", confirmer="oui")
    assert m.depot._grimpeurs[2].statut == "exclu" and m.depot._coches_quetes[2]  # coches gardées
    poster(c, t, "/admin/grimpeurs/2/statut", statut="actif")
    assert m.depot._grimpeurs[2].statut == "actif"
    assert poster(c, t, "/admin/grimpeurs/999/statut", statut="actif").headers["location"].endswith(
        "erreur=introuvable")


def test_corriger_pseudo_et_classe():
    m, c, t = admin()
    r = poster(c, t, "/admin/grimpeurs/2", pseudo="Kaskarot", classe="Crâ")
    assert r.headers["location"].endswith("fait=fiche")
    assert m.depot._grimpeurs[2].classe == "Crâ" and dernier(m, "fiche_modifiee").public is False
    assert poster(c, t, "/admin/grimpeurs/2", pseudo="mirelune").headers["location"].endswith("erreur=pris")
    assert poster(c, t, "/admin/grimpeurs/2", pseudo="K", classe="").headers["location"].endswith("erreur=pseudo")
    assert poster(c, t, "/admin/grimpeurs/2", pseudo="Kas", classe="Paladin").headers["location"].endswith(
        "erreur=classe")


def test_palier_manuel():
    m, c, t = admin()
    assert poster(c, t, "/admin/etages/0/palier", palier="12").headers["location"].endswith("erreur=motif")
    assert poster(c, t, "/admin/etages/0/palier", palier="0", motif="x").headers["location"].endswith("erreur=palier")
    assert poster(c, t, "/admin/etages/0/palier", palier="-3", motif="x").headers["location"].endswith("erreur=palier")
    poster(c, t, "/admin/etages/0/palier", palier="12", motif="catégorie vide")
    html = c.get("/etages/0").text
    assert "sur un palier de 12" in html and "Palier fixé par un admin" in html
    assert dernier(m, "palier").details == {"palier": 12, "motif": "catégorie vide"}
    poster(c, t, "/admin/etages/0/palier", palier="", motif="retour à la formule")
    assert "Palier = 2 × 10 grimpeurs actifs" in c.get("/etages/0").text


def test_date_plancher_change_la_raison_du_bouton():
    m, c, t = admin()
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)  # jauge pleine
    html = c.get("/admin/etages/0").text
    assert re.search(r'<button class="btn or" type="submit">Ouvrir le prochain', html)  # actif
    poster(c, t, "/admin/etages/0/date-plancher", date="2026-12-01T18:30")
    assert m.depot._etages[1].date_plancher_suivant.isoformat() == "2026-12-01T18:30:00+01:00"
    html = c.get("/admin/etages/0").text
    assert "pas avant le mardi 1er décembre à 18 h 30" in html and "submit\" disabled>Ouvrir" in html
    assert poster(c, t, "/admin/etages/0/date-plancher", date="demain").headers["location"].endswith("erreur=date")


def test_ouverture_refusee_tant_que_la_jauge_n_est_pas_pleine():
    m, c, t = admin()
    html = c.get("/admin/etages/0").text
    assert "jauge : il manque 1 points" in html and "Détail par grimpeur" in html
    assert poster(c, t, "/admin/etages/1/ouvrir").headers["location"].endswith("erreur=ouverture")
    assert m.depot._etages[2].statut == "scelle"
    assert poster(c, t, "/admin/etages/1/ouvrir", forcer="oui").headers["location"].endswith("erreur=motif")


def test_ouverture_forcee_fige_le_bilan_et_fait_apparaitre_l_etage():
    m, c, t = admin()
    r = poster(c, t, "/admin/etages/1/ouvrir", forcer="oui", motif="voulu par Shadoaze")
    assert r.headers["location"] == "/admin/etages/1?fait=ouvert"
    assert m.depot._etages[1].statut == "termine" and m.depot._etages[2].statut == "ouvert"
    b = m.depot._bilans[1]
    assert (b.score, b.palier, b.actifs, b.force, b.motif) == (19, 20, 10, True, "voulu par Shadoaze")
    assert dernier(m, "ouverture").details["force"] is True
    g = m.connecter(ID_BRINDILLE)
    assert "Les Champs Murmurants" in g.get("/").text and g.get("/etages/1").status_code == 200
    assert "Bilan figé" in g.get("/etages/0").text
    # Deuxième ouverture du même étage : rien en double, message clair.
    assert poster(c, t, "/admin/etages/1/ouvrir", forcer="oui", motif="encore").headers["location"].endswith(
        "erreur=ouverture")


def test_ouverture_normale_quand_tout_est_pret():
    m, c, t = admin()
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)
    r = poster(c, t, "/admin/etages/1/ouvrir")
    assert r.headers["location"].endswith("fait=ouvert") and m.depot._bilans[1].force is False


def test_deux_admins_en_meme_temps_une_seule_ouverture(monkeypatch):
    m, c, t = admin()
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)

    async def deja_ouvert(*_a, **_k):
        raise EtatInvalide("un autre admin vient d'ouvrir")

    monkeypatch.setattr(m.depot, "ouvrir_etage", deja_ouvert)
    r = poster(c, t, "/admin/etages/1/ouvrir")
    assert r.headers["location"].endswith("erreur=concurrence")
    assert "Un autre admin vient d&#39;ouvrir cet étage" in c.get(r.headers["location"]).text


def test_revue_nature_masquage_libelles():
    m, c, t = admin()
    assert poster(c, t, "/admin/quetes/105", etage="0", nature="principale").headers["location"].endswith(
        "erreur=motif")
    poster(c, t, "/admin/quetes/105", etage="0", nature="principale", motif="mène au Dofus")
    q = m.depot._quetes[105]
    assert q.nature == "principale" and q.nature_origine == "admin"
    poster(c, t, "/admin/quetes/106", etage="0", masquee="oui")
    poster(c, t, "/admin/donjons/3", etage="0", masque="oui")
    poster(c, t, "/admin/cases/22", etage="0", nom="Duo de choc", condition="À deux")
    poster(c, t, "/admin/cases/23", etage="0", masquee="oui")
    poster(c, t, "/admin/quetes/101", etage="0", nom="L'Appel")
    g = m.connecter(ID_BRINDILLE).get("/etages/0").text
    assert "Lettres pour Incarnam" not in g and "Donjon des Bouftous" not in g and "Duo de choc" in g
    assert 'data-ref="case:23"' not in g and "L&#39;Appel</b>" in g
    assert {e.type for e in m.depot._journal} >= {"quete", "donjon", "case"}
    poster(c, t, "/admin/donjons/3", etage="0", masque="non")
    assert "Donjon des Bouftous" in m.connecter(ID_BRINDILLE).get("/etages/0").text
    assert poster(c, t, "/admin/quetes/105", etage="0", nature="bonus", motif="x").headers["location"].endswith(
        "erreur=nature")
    assert poster(c, t, "/admin/quetes/999", etage="0", masquee="oui").headers["location"].endswith(
        "erreur=introuvable")


def test_revue_affiche_alertes_sources_et_quetes_sans_fiche():
    m, c, t = admin()
    html = c.get("/admin/etages/0").text
    assert "succès pris chez DofusDB" in html and "1 quête(s) sans fiche Duffus : Le Vieux Puits" in html
    assert "succès : DofusDB" in html and "succès : Duffus" in html
    assert c.get("/admin/etages/1").status_code == 200 and "4 succès seulement" in c.get("/admin/etages/1").text
    assert c.get("/admin/etages/42").status_code == 404


def test_ajouter_un_donjon_aspire():
    m, c, t = admin()
    poster(c, t, "/admin/etages/0/donjons", duffus_id="d-120")
    d = max(m.depot._donjons.values(), key=lambda d: d.id)
    assert d.nom == "Grotte Hesque" and d.origine == "admin" and d.etage_id == 1
    assert "Grotte Hesque" in m.connecter(ID_BRINDILLE).get("/etages/0").text
    assert poster(c, t, "/admin/etages/0/donjons", duffus_id="inconnu").headers["location"].endswith(
        "erreur=introuvable")


def test_reglages_nom_image_cap():
    m, c, t = admin()
    poster(c, t, "/admin/etages/1/reglages", nom="Les Prés", ambiance_url="https://exemple.org/a.webp", level_cap="38")
    e = m.depot._etages[2]
    assert (e.nom, e.ambiance_url, e.level_cap) == ("Les Prés", "https://exemple.org/a.webp", 38)
    assert poster(c, t, "/admin/etages/1/reglages", ambiance_url="javascript:alert(1)").headers["location"].endswith(
        "erreur=url")
    assert poster(c, t, "/admin/etages/1/reglages", level_cap="999").headers["location"].endswith("erreur=cap")


def test_journal_auteur_date_details_et_filtres():
    m, c, t = admin()
    poster(c, t, "/admin/grimpeurs/2/statut", statut="pause", motif="vacances")
    b = m.connecter(ID_BRINDILLE)
    b.post("/api/coches", json={"type": "quete", "id": 107, "cochee": True},
           headers={"X-CSRF-Token": m.csrf(b), "Origin": SITE})
    html = c.get("/admin/journal").text
    assert "vacances" in html and "statut" in html and "coche" in html and str(ID_MARCEAU) in html
    assert "non public" in html
    filtre = c.get("/admin/journal?type=coche").text
    assert "vacances" not in filtre and "quete:107" in filtre
    assert "quete:107" in c.get("/admin/journal?grimpeur=1").text
    assert "quete:107" not in c.get("/admin/journal?grimpeur=2").text
    assert "quete:107" in c.get("/admin/journal?etage=0").text


@pytest.mark.parametrize("chemin", ["/admin", "/admin/grimpeurs", "/admin/etages", "/admin/etages/0",
                                    "/admin/etages/1", "/admin/journal"])
def test_pages_d_admin(chemin):
    m, c, t = admin()
    assert c.get(chemin).status_code == 200
