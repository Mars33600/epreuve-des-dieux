"""Les pages, pour chaque profil : critères 3 à 5, 8 à 11 bis, 15, 16, 19 à 21 et 34 du lot B.

Profils : visiteur, membre sans fiche, grimpeur, gelé, exclu (voir test_auth), admin sans fiche.
"""

from __future__ import annotations

import html as html_mod
import re
from dataclasses import replace
from fractions import Fraction

import pytest

from epreuve.domaine.modeles import Regles
from epreuve.web import pages
from epreuve.web.demo import ID_HORS_LISTE, ID_MARCEAU, ID_NOUVELLE, DepotDemo
from tests.web.outils import ID_BRINDILLE, ID_OMBREVIVE, PENDANT_FICHES, SITE, monde, routes_declarees

PAGES_GRIMPEUR = ["/", "/etages/0", "/etages/0/quetes/101", "/etages/0/quetes/104", "/etages/0/quetes/109",
                  "/grimpeurs", "/grimpeurs?quoi=categorie:donjons", "/grimpeurs/2", "/grimpeurs/3", "/regles"]
# Ce que les grimpeurs ne doivent jamais voir : les étages scellés 1 à 3, leur contenu, leurs ids.
SCELLES = ["Les Champs Murmurants", "La Forêt des Abraknydes", "Le Vallon Interdit", "Repaire des Murmures",
           "Le Secret des Champs Murmurants", "/etages/1", "/etages/2", "/etages/3", "quetes/201", "case:41"]


def pages_de(c, chemins=PAGES_GRIMPEUR):
    for chemin in chemins:
        r = c.get(chemin)
        assert r.status_code == 200, (chemin, r.status_code)
        yield chemin, r.text


# ---------------------------------------------------------------- profils


def test_visiteur_voit_l_accueil_et_rien_d_autre():
    c = monde().client()
    assert 'href="/connexion"' in c.get("/").text
    for chemin in PAGES_GRIMPEUR[1:] + ["/admin", "/inscription"]:
        r = c.get(chemin)
        assert r.status_code == 303 and r.headers["location"] == "/", chemin


def test_membre_sans_fiche_renvoye_vers_sa_fiche():
    c = monde().connecter(ID_NOUVELLE)
    for chemin in PAGES_GRIMPEUR:
        r = c.get(chemin)
        assert r.status_code == 303 and r.headers["location"] == "/inscription", chemin


def test_grimpeur_voit_toutes_ses_pages():
    c = monde().connecter(ID_BRINDILLE)
    for chemin, html in pages_de(c):
        assert "Brindille" in html, chemin
        assert 'href="/admin"' not in html


def test_grimpeur_gele_voit_et_peut_cocher():
    c = monde().connecter(ID_OMBREVIVE)
    html = c.get("/etages/0").text
    assert "Tu es en pause" in html
    assert re.search(r'data-ref="bloc:3"(?: checked)?>', html)  # case active (pas disabled)


def test_admin_sans_fiche_consulte_tout_en_lecture_seule():
    c = monde().connecter(ID_MARCEAU)
    for chemin, html in pages_de(c):
        assert 'href="/admin"' in html, chemin
    html = c.get("/etages/0").text
    assert "Lecture seule" in html and 'id="maProgression"' not in html
    assert all("disabled" in m for m in re.findall(r'data-ref="[^"]+"[^>]*>', html))


# ---------------------------------------------------------------- inscription (critères 3, 4, 5)


def inscrire(m, c, **champs):
    return c.post("/inscription", data={"csrf": m.csrf(c, "/inscription"), **champs}, headers={"Origin": SITE})


def test_inscription_cree_la_fiche_au_statut_de_la_liste():
    m = monde(maintenant=PENDANT_FICHES)
    m.depot._liste[ID_NOUVELLE] = "pause"
    c = m.connecter(ID_NOUVELLE)
    r = inscrire(m, c, pseudo="  Nouvelle  Lune ", classe="", niveau="")
    assert r.status_code == 303 and r.headers["location"] == "/"
    g = m.depot._grimpeurs[14]
    assert (g.pseudo, g.classe, g.niveau_declare, g.statut) == ("Nouvelle Lune", None, 1, "pause")
    assert g.nom_discord == "Nouvelle"
    assert c.get("/inscription").headers["location"] == "/"  # déjà inscrite


@pytest.mark.parametrize(("champs", "statut", "message"), [
    ({"pseudo": "brindille"}, 409, "déjà pris"),
    ({"pseudo": "BRINDILLE"}, 409, "déjà pris"),
    ({"pseudo": "X"}, 422, "entre 2 et 30"),
    ({"pseudo": "x" * 31}, 422, "entre 2 et 30"),
    ({"pseudo": "Lune", "classe": "Paladin"}, 422, "Classe inconnue"),
    ({"pseudo": "Lune", "niveau": "201"}, 422, "de 1 à 200"),
    ({"pseudo": "Lune", "niveau": "abc"}, 422, "de 1 à 200"),
])
def test_inscription_refusee(champs, statut, message):
    m = monde(maintenant=PENDANT_FICHES)
    c = m.connecter(ID_NOUVELLE)
    r = inscrire(m, c, **champs)
    assert r.status_code == statut and message in r.text
    assert len(m.depot._grimpeurs) == 13


def test_inscription_avec_classe_et_niveau():
    m = monde(maintenant=PENDANT_FICHES)
    c = m.connecter(ID_NOUVELLE)
    inscrire(m, c, pseudo="Lune", classe="Huppermage", niveau="12")
    assert (m.depot._grimpeurs[14].classe, m.depot._grimpeurs[14].niveau_declare) == ("Huppermage", 12)


def test_inscription_sans_niveau_part_du_niveau_1():
    m = monde(maintenant=PENDANT_FICHES)
    c = m.connecter(ID_NOUVELLE)
    assert 'name="niveau"' not in c.get("/inscription").text
    inscrire(m, c, pseudo="Lune", classe="Huppermage")
    assert m.depot._grimpeurs[14].niveau_declare == 1


def test_classe_obligatoire_si_le_reglage_le_demande():
    m = monde(maintenant=PENDANT_FICHES, regles=Regles(classe_obligatoire=True))
    c = m.connecter(ID_NOUVELLE)
    assert inscrire(m, c, pseudo="Lune").status_code == 422


def test_hors_liste_ne_peut_pas_creer_de_fiche():
    m = monde(maintenant=PENDANT_FICHES, regles=Regles(liste_officielle_obligatoire=True))
    c = m.connecter(ID_HORS_LISTE)
    html = c.get("/inscription").text
    assert "Envoie ta validation en MP à Shadoaze" in html
    r = c.post("/inscription", data={"csrf": m.csrf(c, "/inscription"), "pseudo": "Passant"}, headers={"Origin": SITE})
    assert r.status_code == 403 and len(m.depot._grimpeurs) == 13


def test_modifier_sa_fiche():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    t = m.csrf(c)
    r = c.post("/grimpeurs/moi", data={"csrf": t, "pseudo": "Brindille", "classe": "Iop", "niveau": "21"},
               headers={"Origin": SITE})
    assert r.headers["location"] == "/tableau-de-bord?fait=1"
    assert m.depot._grimpeurs[1].classe == "Iop"
    r = c.post("/grimpeurs/moi", data={"csrf": t, "pseudo": "kaskarot"}, headers={"Origin": SITE})
    assert r.headers["location"] == "/tableau-de-bord?erreur=pris"
    assert "déjà pris" in c.get(r.headers["location"]).text


# ---------------------------------------------------------------- tour et brouillard (critère 8)


def _pyramide(html: str) -> str:
    return html[html.index('<div class="pyr'):].split("</nav>")[0]


def test_tour_seulement_les_etages_ouverts_nommes_et_cliquables():
    html = monde().connecter(ID_BRINDILLE).get("/").text
    tour = _pyramide(html)
    assert "Le Seuil" in tour and 'href="/etages/0"' in tour and tour.count("<a ") == 1
    assert "Étage 0" not in tour and "scell" not in tour and "prêt" not in tour  # aucun numéro, aucun scellé nommé
    menu = html[:html.index('<div class="pyr')].split('aria-label="Navigation principale"')[1]
    assert 'href="/etages/0"' not in menu  # plus d'onglet « Étage 0 » : on choisit dans la pyramide
    # La jauge vient après la pyramide, jamais dedans.
    assert html.index('class="pyr-jauge"') > html.index('class="pyramide"')


def test_tour_html_ne_trahit_pas_le_nombre_d_etages():
    """Le HTML de l'accueil est identique avec 3 ou 8 étages scellés : rien ne compte les étages."""
    def accueil(nb_scelles: int) -> str:
        m = monde()
        base = m.depot._etages[2]
        for i in range(nb_scelles):
            n = 10 + i
            m.depot._etages[n] = replace(base, id=n, numero=n, nom=f"Secret {n}", statut="scelle")
        return m.connecter(ID_BRINDILLE).get("/").text

    a, b = accueil(0), accueil(8)
    zone = lambda h: h[h.index('<div class="pyr'):h.index('<div class="pyr-jauge"')]  # noqa: E731
    assert zone(a) == zone(b)
    assert zone(a).count("<div") == 4  # gradins anonymes : des décors, pas une liste d'étages
    for html in (a, b):
        for trace in ("data-", " hidden", "display:none", "Secret"):  # ni attribut de données, ni liste cachée
            assert trace not in zone(html), trace
        assert not re.search(r"\b(\d+)\s+étages\b", html)
        assert "scellé" not in zone(html)


def test_tour_etage_suivant_pret_sans_numero():
    m = monde()
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=1)
    tour = _pyramide(m.connecter(ID_BRINDILLE).get("/").text)
    assert 'class="pyr prete"' in tour and "Étage 1" not in tour and "Champs Murmurants" not in tour


def test_brouillard_aucune_trace_d_un_scelle():
    c = monde().connecter(ID_BRINDILLE)
    for chemin, html in pages_de(c):
        for trace in SCELLES:
            assert trace not in html, (chemin, trace)
    for chemin in ("/etages/1", "/etages/3", "/etages/1/quetes/201", "/etages/0/quetes/201", "/etages/42"):
        assert c.get(chemin).status_code == 404, chemin
    # Un scellé répond exactement comme un étage qui n'existe pas.
    assert c.get("/etages/1").text == c.get("/etages/42").text


def test_admin_voit_un_etage_scelle():
    c = monde().connecter(ID_MARCEAU)
    html = c.get("/etages/1").text
    assert "Les Champs Murmurants" in html and "scellé (vue admin)" in html


# ---------------------------------------------------------------- l'étage (critères 9 à 11, 15, 16)


def test_etage_donjons_puis_blocs_du_guide_avec_cadres_et_libelles():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0").text
    liste = html.split('id="liste"')[1]
    # Les donjons d'abord, puis les blocs du guide dans l'ordre, avec leur numéro et le titre de Duffus.
    ordre = [liste.index(n) for n in ("Donjons de l'étage</h2>", 'id="donjon-1"', 'id="donjon-2"', 'id="donjon-3"',
                                      "Blocs du guide</h2>", "Bloc 1 · Incarnam", "Bloc 2 · Astrub",
                                      "Bloc 3 · Petits services d&#39;Astrub")]
    assert ordre == sorted(ordre)
    assert liste.count("<details class=\"dj-ligne\"") == 3
    # Plus de fiche de quête dans la page d'étage : les noms des quêtes seulement, dans un menu plié.
    assert "data-qopen" not in html and 'id="qd"' not in html and "/quetes/" not in liste
    assert "Jusqu'où" not in liste
    # Cadre rouge (principal) ou jaune (secondaire) ET libellé écrit, lisible sans la couleur. « Incarnam » est
    # hybride : deux moitiés côte à côte dans une paire, la rouge puis la jaune, même numéro et même titre.
    cartes = re.findall(r'<li class="bloc-carte c-(\w+)( moitie)?"', liste)
    assert cartes == [("principales", " moitie"), ("secondaires", " moitie"), ("principales", ""), ("secondaires", "")]
    assert liste.count('<li class="bloc-paire" data-paire>') == 1 and liste.count("Bloc 1 · Incarnam</h3>") == 2
    paire = liste.split('<li class="bloc-paire" data-paire>')[1].split('id="bloc-2"')[0]
    assert paire.index('data-ref="bloc:1"') < paire.index('data-ref="bloc:5"')
    assert liste.count('<span class="badge princ"><svg') == 2 and liste.count(">Principal</span>") == 2
    assert liste.count('<span class="badge second"><svg') == 2 and liste.count(">Secondaire</span>") == 2
    # Le vrai compte de chaque partie, accordé, dans un menu plié qui liste les quêtes dans l'ordre du guide.
    menus = re.findall(r'<details class="quetes-bloc">\s*<summary>([^<]+)</summary>\s*<ol>(.*?)</ol>', liste)
    assert [m[0] for m in menus] == ["1 principale", "2 secondaires", "3 principales", "3 secondaires"]
    assert menus[1][1] == "<li>Le Bouftou égaré</li><li>Lettres pour Incarnam</li>"
    assert '<details class="quetes-bloc" open' not in liste
    # La case de chaque moitié se nomme pour un lecteur d'écran ; un bloc entier garde « Bloc terminé ».
    assert 'aria-label="Bloc 1, partie principale terminée"' in liste
    assert 'aria-label="Bloc 1, partie secondaire terminée"' in liste
    assert liste.count("<b>Bloc terminé</b>") == 2 and "<b>Partie principale terminée</b>" in liste
    # Plus de bouton Duffus par bloc (ni d'indication de tranche) : seul le lien général de la section reste.
    assert "Ouvrir sur Duffus" not in liste and "puis tranche " not in liste and "chapitre" not in liste
    assert liste.count('href="https://duffus.fr/guide-complet"') == 1
    assert "5 sur 10 l'ont fait" in liste
    assert liste.count("Fait par / Pas encore fait par") == 4 and "Pas encore fait par <small" in liste


def test_donjon_cinq_sous_cases_classique_en_premier():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0").text
    bloc = html.split('data-donjon="2"')[1].split("</details>")[0]
    refs = re.findall(r'data-ref="case:(\d+)"', bloc)
    assert refs == ["21", "22", "23", "24", "25"]
    assert bloc.index("Vaincre le boss") < bloc.index("Duo")
    assert 'data-donjon-tout="2"' in bloc
    assert '<span class="badge donjon on"' in bloc and '<span class="badge succes on"' in bloc


def test_filtre_cumulatif_present_avec_les_4_categories_et_le_reste():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0").text
    filtre = html.split('id="filtre"')[1].split("</fieldset>")[0]
    assert re.findall(r'value="(\w+)" checked', filtre) == ["donjons", "full_succes", "principales", "secondaires"]
    assert "Seulement ce qui me reste" in filtre
    # Chaque ligne porte ses catégories : le filtre (app.js) n'a qu'à les comparer.
    assert html.count('data-cats="donjons full_succes"') == 3
    assert html.count('data-cats="principales"') == 2 and html.count('data-cats="secondaires"') == 2
    assert "Blocs principaux" in filtre and "Blocs secondaires" in filtre


def test_jauge_de_reference_calculee_a_la_main():
    """Critère 15 : 10 actifs, 2 en pause, 4 catégories → palier 20 ; points comptés à la main sur demo.BRUT.

    Donjons (3 cases classiques) : tous sauf Pépin, Fleur et Torvald… non : les 1res cases → 8 actifs ont les 3.
    Full succès : Brindille non (13/15), Mirelune, Sélénith, Nalouette → 3. Principales (4/4) : Brindille, Kaskarot,
    Sélénith, Cliquetis → 4. Secondaires (5/5) : Pépin, Sélénith, Gromolo, Cliquetis → 4. Score 8+3+4+4 = 19.
    """
    html = monde().connecter(ID_BRINDILLE).get("/etages/0").text
    assert "19 / 20 points" in html and "Il manque 1 point" in html
    assert "Palier = 2 × 10 grimpeurs actifs" in html
    assert "Jauge de l'étage</div>" not in html and "Il manque <b" not in html
    assert re.findall(r'data-jcat="(\w+)">(\d+)<', html) == [("donjons", "8"), ("full_succes", "3"),
                                                             ("principales", "4"), ("secondaires", "4")]
    assert 'id="encoches"' not in html
    assert 'Maximum possible : <span class="num" data-pg="maximum">40</span>' in html


def test_formule_du_palier_suit_les_regles():
    """Critère 16 : changer points_par_joueur ou une catégorie vide change le calcul et le texte, sans code."""
    m = monde(regles=Regles(points_par_joueur=Fraction(5, 2)))
    html = m.connecter(ID_BRINDILLE).get("/etages/0").text
    assert "Palier = 5/2 × 10 grimpeurs actifs" in html and "sur un palier de 25" in html
    m = monde()
    for b in (3, 5):  # plus aucune partie secondaire (bloc 3 et moitié jaune d'Incarnam)
        m.depot._blocs[b] = replace(m.depot._blocs[b], masque=True)
    html = m.connecter(ID_BRINDILLE).get("/etages/0").text
    assert "× 3 catégories sur 4, arrondi au-dessus" in html and "sur un palier de 15" in html


def test_palier_manuel_annonce():
    m = monde()
    m.depot._etages[1] = replace(m.depot._etages[1], palier_manuel=7)
    html = m.connecter(ID_BRINDILLE).get("/etages/0").text
    assert "Palier fixé par un admin" in html and "Jauge pleine : un admin va vérifier" in html


def test_verdict_avec_la_date_plancher():
    m = monde(maintenant=pages_horloge_avant_plancher())
    html = m.connecter(ID_BRINDILLE).get("/etages/0").text
    assert "et pas avant le vendredi 13 novembre à 17 h" in html


def pages_horloge_avant_plancher():
    from tests.web.outils import AVANT_OUVERTURE
    return AVANT_OUVERTURE


def test_ma_progression():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0").text
    prog = html.split('id="maProgression"')[1].split("</section>")[0]
    assert '<span data-moi="points">2</span>' in prog
    assert re.findall(r'data-moi-cat="(\w+)">([^<]+)<', prog) == [
        ("donjons", "3/3 ✓"), ("full_succes", "13/15"), ("principales", "2/2 ✓"), ("secondaires", "0/2")]
    assert 'aria-label="Donjons : point obtenu"' in prog and 'aria-label="Full succès : 13 sur 15"' in prog


# ---------------------------------------------------------------- fiche de quête (critère 11 bis)


def test_fiche_de_quete_page_complete_et_fragment():
    c = monde().connecter(ID_BRINDILLE)
    page = c.get("/etages/0/quetes/102").text
    frag = c.get("/etages/0/quetes/102", headers={"Accept": "text/html-fragment"}).text
    assert "<!doctype html>" in page and "Merci Duffus" in page and "<!doctype" not in frag
    for html in (page, frag):
        assert 'id="qdTitle"' in html and "La Graine de Mère Cawotte" in html
        for bloc in ("Jusqu'où la faire", "Prérequis", "Étapes", "Ce dont tu as besoin", "Positions",
                     "Succès lié", "Récompenses", "En bref", "Faite par", "Pas encore faite par"):
            assert bloc in html, bloc
        assert 'href="/etages/0/quetes/101"' in html  # prérequis d'un étage ouvert : un lien vers sa fiche
        assert "[5,-17]" in html and 'data-copier="/travel 5,-17"' in html
        assert 'data-ref="quete:102"' in html  # la même case que la liste
    assert 'href="/etages/0">← Retour' in page


def test_fiche_complete_parite_des_champs():
    """Chaque champ non vide de la FicheQuete apparaît dans la page (parité, sur les fiches de démonstration)."""
    m = monde()
    c = m.connecter(ID_MARCEAU)
    for qid, f in m.depot._fiches.items():
        if m.depot._quetes[qid].etage_id != 1:
            continue
        html = c.get(f"/etages/0/quetes/{qid}", headers={"Accept": "text/html-fragment"}).text
        valeurs = [f.jusqu_ou, f.a_lier, f.succes_lie, *f.recompenses, *(e.titre for e in f.etapes),
                   *(o for e in f.etapes for o in e.objectifs), *(b.nom for b in f.objets + f.monstres),
                   *(p.libelle for p in f.positions), *(p.nom for p in f.prerequis if p.nom)]
        for v in filter(None, valeurs):
            assert v.replace("'", "&#39;").replace("«", "«") in html, (qid, v)


def test_prerequis_scelle_sans_nom_ni_id():
    c = monde().connecter(ID_BRINDILLE)
    for accept in ("text/html", "text/html-fragment"):
        html = c.get("/etages/0/quetes/104", headers={"Accept": accept}).text
        assert "Prérequis d'un étage pas encore ouvert" in html
        assert "Secret des Champs" not in html and "201" not in html


def test_prerequis_hors_guide_en_texte():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0/quetes/101").text
    assert "Tutoriel d&#39;Incarnam" in html and "hors du guide" in html


def test_masquer_prerequis_scelles_appelee_sur_chaque_chemin(monkeypatch):
    appels = []
    vraie = pages.masquer_prerequis_scelles

    def espion(*a, **k):
        appels.append(1)
        return vraie(*a, **k)

    monkeypatch.setattr(pages, "masquer_prerequis_scelles", espion)
    c = monde().connecter(ID_BRINDILLE)
    c.get("/etages/0/quetes/104")
    c.get("/etages/0/quetes/104", headers={"Accept": "text/html-fragment"})
    assert len(appels) == 2


def test_admin_voit_le_nom_du_prerequis_scelle():
    html = monde().connecter(ID_MARCEAU).get("/etages/0/quetes/104").text
    assert "Le Secret des Champs Murmurants" in html


def test_quete_sans_fiche_duffus():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0/quetes/109").text
    assert "Fiche détaillée indisponible" in html and "1 000 XP" in html


def test_fiche_completee_avec_dofusdb_et_icone():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0/quetes/103").text
    assert "Fiche complétée avec DofusDB." in html
    assert '<img src="https://api.dofusdb.fr/img/monsters/31.png"' in html


def test_fiche_sans_duffus_script_style_ni_on():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    for qid in (101, 102, 103, 104, 105, 106, 107, 108, 109):
        frag = c.get(f"/etages/0/quetes/{qid}", headers={"Accept": "text/html-fragment"}).text
        assert "duffus.fr" not in frag and "<script" not in frag and "<style" not in frag
        assert not re.search(r"\son\w+\s*=", frag), qid
        assert not re.search(r'<img[^>]+src="(?!https://api\.dofusdb\.fr/)', frag)
    # Le seul lien vers duffus.fr du site est celui du pied de page.
    page = c.get("/etages/0/quetes/101").text
    assert page.count("duffus.fr") == 1 and '<a href="https://duffus.fr" rel="noopener">Merci Duffus</a>' in page


def test_quete_masquee_ou_d_un_autre_etage_404():
    m = monde()
    m.depot._quetes[107] = replace(m.depot._quetes[107], masquee=True)
    c = m.connecter(ID_BRINDILLE)
    assert c.get("/etages/0/quetes/107").status_code == 404
    assert c.get("/etages/0/quetes/999").status_code == 404


# ---------------------------------------------------------------- grimpeurs et fiches (critères 19 à 21)


def test_liste_des_grimpeurs_jamais_par_score():
    html = monde().connecter(ID_BRINDILLE).get("/grimpeurs").text
    pseudos = re.findall(r'<div class="ptop"><strong>([^<]+)</strong>', html)
    actifs = ["Brindille", "Cliquetis", "Fleur-de-Bwork", "Gromolo", "Kaskarot", "Mirelune", "Nalouette",
              "Pépin-Lagrume", "Sélénith", "Torvald"]
    assert pseudos == actifs + ["Ombrevive", "Vieux-Grain"]
    assert "Fourbe" not in html


def test_admin_voit_les_exclus():
    html = monde().connecter(ID_MARCEAU).get("/grimpeurs").text
    assert "Fourbe" in html and "Exclu" in html


def test_nom_discord_selon_le_reglage():
    assert "brindille#discord" in monde().connecter(ID_BRINDILLE).get("/grimpeurs").text
    m = monde(regles=Regles(afficher_nom_discord=False))
    c = m.connecter(ID_BRINDILLE)
    for chemin in ("/grimpeurs", "/grimpeurs/1"):
        assert "#discord" not in c.get(chemin).text


def test_filtre_par_element_sans_javascript():
    c = monde().connecter(ID_BRINDILLE)
    html = c.get("/grimpeurs?quoi=bloc:1").text  # sans ?etage= : l'étage ouvert, comme les anciens liens
    rep = html.split('id="qui-0-bloc-1"')[1].split("</details>")[0]
    assert ("Qui ne l'a pas fait <small>5 sur 10 actifs · la partie principale du bloc « Bloc 1 · Incarnam »"
            in rep)
    assert "Qui l'a fait (peut accompagner)" in rep
    # Une option par partie : les deux moitiés d'Incarnam se distinguent par leur nature, un bloc entier non.
    assert "Bloc 1 · Incarnam (principale)" in html and "Bloc 1 · Incarnam (secondaire)" in html
    assert "Bloc 2 · Astrub (" not in html and "Bloc 2 · Astrub" in html
    assert html.count("player target") == 5 and len(re.findall(r"class=\"player[^\"]* dim\"", html)) == 5
    rep = c.get("/grimpeurs?quoi=donjon:3").text.split('id="qui-0-donjon-3"')[1]
    assert "vaincre Donjon des Bouftous" in rep
    rep = c.get("/grimpeurs?quoi=categorie:principales").text.split('id="qui-0-categorie-principales"')[1]
    assert "Qui ne l'a pas fait <small>6 sur 10 actifs · le point Quêtes principales" in rep


def test_lien_qui_manque_de_chaque_tuile():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0").text
    for cat in ("donjons", "full_succes", "principales", "secondaires"):
        assert f'href="/grimpeurs?quoi=categorie:{cat}">Qui manque&nbsp;?</a>' in html


def test_fiche_d_un_grimpeur():
    # Son tableau de bord en lecture seule (l'ancienne fiche) : web/tableau.py.
    html = monde().connecter(ID_BRINDILLE).get("/grimpeurs/3").text
    assert "Tableau de bord de Mirelune" in html and "Étage 0 · Le Seuil" in html
    assert "Ses blocs du guide" in html and "Bloc 1 · Incarnam" in html
    assert "16 sur 19 éléments faits (84 %)" in html  # 15 cases + 1 bloc sur 19 (15 cases, 4 parties de bloc)
    assert "/4 points · 16/19" in html
    assert all("disabled" in m for m in re.findall(r'data-ref="[^"]+"[^>]*>', html))  # pas la sienne
    assert html.count('<li class="bloc-paire" data-paire>') == 1  # les deux moitiés d'Incarnam, en lecture seule


def test_fiche_exclu_introuvable_pour_un_grimpeur():
    c = monde().connecter(ID_BRINDILLE)
    assert c.get("/grimpeurs/13").status_code == 404
    assert c.get("/grimpeurs/999").status_code == 404


def test_mode_edition_reserve_a_l_admin():
    m = monde()
    assert "data-cible" not in m.connecter(ID_BRINDILLE).get("/grimpeurs/3?edition=1").text
    html = m.connecter(ID_MARCEAU).get("/grimpeurs/3?edition=1").text
    assert 'data-cible="3"' in html and 'id="motif"' in html
    assert not any("disabled" in x for x in re.findall(r'data-ref="[^"]+"[^>]*>', html))


# ---------------------------------------------------------------- règles


def test_page_des_regles_lit_la_configuration():
    html = monde(regles=Regles(points_par_joueur=Fraction(5, 2))).connecter(ID_BRINDILLE).get("/regles").text
    assert "<b>5/2 × le nombre de grimpeurs actifs</b>" in html
    assert "le cap est le niveau <b class=\"num\">20</b>" in html
    for theme in ("tranche", "4 points au maximum", "sans capture d'écran", "sans power-leveling",
                  "s'ouvre tout seul", "mettre en pause", "réintègre"):
        assert theme in html, theme
    assert "bonus" not in html.lower()
    assert "point est offert" in monde(regles=Regles(categorie_vide="offerte")).connecter(ID_BRINDILLE).get(
        "/regles").text
    # Sans webhook (le monde de test n'en a pas), la page ne promet pas d'annonce du Gardien.
    assert "Gardien de la Tour" not in html and "ne poste rien sur Discord" in html
    # `ouverture.automatique: false` : la règle redevient l'ouverture par un admin.
    manuel = monde(regles=Regles(ouverture_automatique=False)).connecter(ID_BRINDILLE).get("/regles").text
    assert "un admin vérifie et ouvre" in manuel and "s'ouvre tout seul" not in manuel
    # Le délai de grâce : dit en une phrase, en minute s'il vaut 60 s, absent s'il est coupé.
    assert "s'ouvre une minute après que la jauge est pleine (le temps de rattraper une coche par erreur)" in html
    sans = monde(regles=Regles(delai_grace_secondes=0)).connecter(ID_BRINDILLE).get("/regles").text
    assert "rattraper une coche" not in sans
    assert "s'ouvre 90 secondes après" in monde(regles=Regles(delai_grace_secondes=90)).connecter(
        ID_BRINDILLE).get("/regles").text


# ---------------------------------------------------------------- transverse (critère 34)


def _exemple(chemin: str) -> str:
    return (chemin.replace("{numero}", "0").replace("{quete_id}", "101").replace("{grimpeur_id}", "1"))


def test_pied_de_page_sur_chaque_route_get():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    vues = 0
    for route in routes_declarees(m.app):
        if "GET" not in getattr(route, "methods", set()) or route.path.startswith(("/api", "/auth", "/connexion",
                                                                                     "/sante")):
            continue
        r = c.get(_exemple(route.path))
        if r.headers.get("content-type", "").startswith("image/"):
            continue  # /etages/{n}/image : une image, pas une page
        if r.status_code == 303:
            continue  # /inscription pour un admin déjà connecté sans être sur la liste : redirection
        assert "Projet de fans" in r.text and '<a href="https://duffus.fr" rel="noopener">Merci Duffus</a>' in r.text, \
            route.path
        vues += 1
    assert vues >= 12
    for chemin in ("/etages/42", "/inconnue"):  # les pages d'erreur aussi
        assert "Merci Duffus" in c.get(chemin).text


def test_aucun_script_ni_style_en_ligne():
    c = monde().connecter(ID_MARCEAU)
    for chemin in PAGES_GRIMPEUR + ["/admin", "/admin/grimpeurs", "/admin/etages/0", "/admin/journal"]:
        html = c.get(chemin).text
        assert not re.search(r"<script(?![^>]*\bsrc=\"/static/)", html), chemin
        assert "<style" not in html and not re.search(r'\sstyle="', html), chemin
        assert not re.search(r"\son[a-z]+\s*=", html), chemin


def test_base_vide_et_aucun_etage_ouvert():
    d = DepotDemo()
    d._etages = {k: replace(e, statut="scelle") for k, e in d._etages.items()}
    m = monde(depot=d)
    c = m.connecter(ID_MARCEAU)
    assert "La tour se prépare" in c.get("/").text
    assert c.get("/grimpeurs").status_code == 200 and c.get("/regles").status_code == 200
    assert "Aucun étage ouvert" in c.get("/grimpeurs/1").text


# ---------------------------------------------------------------- texte des donjons et filtres de l'étage


def _depot_avec_donjons(n: int) -> DepotDemo:
    """Le Seuil (3 donjons dans la démo) ramené ou porté à n donjons, 5 cases chacun."""
    from epreuve.domaine.modeles import CaseSucces, Donjon
    depot = DepotDemo()
    for id_ in [i for i, d in depot._donjons.items() if d.etage_id == 1 and i > n]:
        depot._donjons.pop(id_)
        for cid in [c for c, cs in depot._cases.items() if cs.donjon_id == id_]:
            depot._cases.pop(cid)
    for id_ in range(4, n + 1):
        nouv = 100 + id_
        depot._donjons[nouv] = Donjon(nouv, 1, f"Donjon neuf {id_}", 20, 40 + id_, None, 900 + id_,
                                    "propose", "duffus", False)
        for k in range(1, 6):
            depot._cases[nouv * 10 + k] = CaseSucces(
                nouv * 10 + k, nouv, k, "Vaincre le boss" if k == 1 else f"Défi {k}", "x", k == 1, False)
    return depot


def test_textes_de_la_regle_des_donjons():
    from epreuve.web.vues import texte_point_donjons, texte_point_full
    assert texte_point_donjons(1) == "Vaincre ce donjon rapporte 1 point (Donjons)"
    assert texte_point_donjons(4) == "Vaincre les 4 donjons de l'étage rapporte 1 point (Donjons)"
    assert texte_point_full(1).endswith("1 point (Full succès)") and "ce donjon" in texte_point_full(1)
    assert "des 4 donjons de l'étage" in texte_point_full(4)


@pytest.mark.parametrize("n", [1, 4])
def test_page_etage_dit_la_regle_pour_n_donjons(n):
    html = monde(depot=_depot_avec_donjons(n)).connecter(ID_BRINDILLE).get("/etages/0").text
    liste = html.split('id="liste"')[1]
    if n == 1:
        assert liste.count("Vaincre ce donjon rapporte 1 point (Donjons)") == 2
        assert " / 1 vaincu<" in liste
    else:
        assert liste.count("Vaincre les 4 donjons de l&#39;étage rapporte 1 point (Donjons)") == 5
        assert re.search(r"/ 4 vaincus<", liste)
        assert "des 4 donjons de l&#39;étage rapporte 1 point (Full succès)" in liste
    assert "si tous les donjons sont vaincus" not in liste


def test_filtre_page_etage_a_tout_afficher_et_etat_lu_dans_l_url():
    c = monde().connecter(ID_BRINDILLE)
    html = c.get("/etages/0?voir=donjons").text
    assert 'id="filtreTout"' in html and "Tout afficher" in html
    app_js = c.get("/static/app.js").text
    assert "URLSearchParams(location.search)" in app_js and "replaceState" in app_js


def test_regle_precise_et_aleatoire_dans_les_cases():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0").text
    assert 'class="alea"' not in html or "alea-note" in html
    from epreuve.domaine.modeles import MARQUE_ALEATOIRE, CaseSucces

    fixe = CaseSucces(1, 1, 2, "Duo", "Finir le donjon à deux personnages au plus.", False)
    assert fixe.regle == fixe.condition and fixe.explication_aleatoire is None
    regle = "Le monstre désigné doit être achevé en premier."
    alea = CaseSucces(2, 1, 3, "Premier", f"{regle}{MARQUE_ALEATOIRE}Il change.", False)
    assert alea.regle == regle and alea.explication_aleatoire == "Il change."


def test_article_du_repere():
    from epreuve.web.vues import avec_article

    assert [avec_article(n) for n in ("Crypte de Kardorim", "Château Ensablé", "Antichambre des Gloursons")] == [
        "la Crypte de Kardorim", "le Château Ensablé", "l'Antichambre des Gloursons"]


def _jauge_rendue(actifs: int) -> str:
    from epreuve.domaine.bareme import EtatJauge
    from epreuve.web.rendu import creer_gabarits

    j = EtatJauge(0, 2 * actifs, False, actifs, 0, 4, {})
    macros = creer_gabarits().env.get_template("_macros.html").module
    jauge = macros.jauge_bloc(j, "plein", "pas plein")
    return macros.barre_progression(j) + jauge


def test_jauge_sans_grimpeur_actif_etat_vide_clair():
    html = _jauge_rendue(0)
    assert 'data-vide="1"' in html and "Aucun grimpeur actif pour l'instant</p>" in html
    assert "0 / 0 points" not in html  # le résumé du bandeau n'affiche pas « 0 / 0 »
    assert 'class="pg-max" data-pg-normal' in html  # masqué tant qu'il n'y a pas d'actif


def test_jauge_avec_actifs_affiche_le_resume_et_pas_l_etat_vide():
    html = _jauge_rendue(12)
    assert 'data-vide="0"' in html and ">0 / 24 points</strong>" in html and "Il manque 24 points" in html


def test_bandeau_etage_sans_depliant_avec_barre_et_faits():
    c = monde().connecter(ID_BRINDILLE)
    html = c.get("/etages/0").text
    bandeau = html.split('id="enteteEtage"')[1].split("</section>")[0]
    assert "<details" not in html.split('id="enteteEtage"')[0][-60:] and "Niveaux 1 à 20" in bandeau
    assert bandeau.count("Étage 0") == 1
    assert '<b class="num">3</b> donjons' in bandeau and '<b class="num">2</b> blocs principaux' in bandeau
    assert '<b class="num">2</b> blocs secondaires' in bandeau  # le bloc 3 et la moitié jaune d'Incarnam
    assert 'role="progressbar"' in bandeau and "pg-palier" in bandeau and ">palier</small>" in bandeau
    assert re.search(r'data-pg="score">\d+ / \d+ points</strong>', bandeau) and "Il manque" in bandeau
    tour = c.get("/").text.split('id="enteteEtage"')[1].split("</section>")[0]
    assert "Étage en cours" in tour and 'role="progressbar"' in tour and "<details" not in tour


def test_bandeau_etage_vide_sans_grimpeur_actif():
    m = monde()
    for g in m.depot._grimpeurs.values():
        m.depot._grimpeurs[g.id] = replace(g, statut="pause")
    html = m.connecter(ID_MARCEAU).get("/etages/0").text
    bandeau = html.split('id="enteteEtage"')[1].split("</section>")[0]
    assert 'data-vide="1"' in bandeau and "Aucun grimpeur actif pour l&#39;instant" in bandeau or \
        "Aucun grimpeur actif pour l'instant" in bandeau
    assert 'aria-valuemax="0"' in bandeau and "q-0" in bandeau
    tour = m.connecter(ID_MARCEAU).get("/").text
    gradin = tour[tour.index("gradin-jauge"):tour.index('<div class="pyr-brume"')]
    assert "sans-actif" in gradin and "ep-palier" not in gradin and "Aucun grimpeur actif pour l'instant" in gradin


def test_gradin_courant_est_une_barre_avec_infobulle_et_pseudos():
    tour = monde().connecter(ID_BRINDILLE).get("/").text
    gradin = tour[tour.index("gradin-jauge"):tour.index('<div class="pyr-brume"')]
    assert 'role="progressbar"' in gradin and 'tabindex="0"' in gradin
    assert 'aria-describedby="infobulle-jauge"' in gradin
    assert re.search(r'aria-valuemin="0" aria-valuemax="(\d+)" aria-valuenow="\d+"', gradin)
    assert "ep-palier" in gradin and ">palier</small>" in gradin and 'role="tooltip" id="infobulle-jauge"' in gradin
    assert re.search(r'<span class="ep-score">\d+ / \d+</span>', gradin)
    for pseudo in ("Brindille", "Sélénith"):
        assert f'<span class="pseudo">{pseudo}</span>' in gradin
    assert "Ombrevive" in gradin and "pseudo pause" in gradin and "Fourbe" not in gradin  # pause à part, exclu absent


def test_phrase_d_accueil():
    tour = monde().connecter(ID_BRINDILLE).get("/").text
    assert ("Un étage s'éveille quand la guilde en est digne. Combien en reste-t-il&nbsp;? "
            "Même les Dieux se taisent.") in tour
    assert "Plus on la gravit" not in tour


def test_page_etage_liste_des_grimpeurs_actifs_et_en_pause():
    html = monde().connecter(ID_BRINDILLE).get("/etages/0").text
    bloc = html.split('id="actifsEtage"')[1].split("</details>")[0]
    assert re.search(r"Grimpeurs actifs \(\d+\)", bloc) and "En pause (2)" in bloc
    assert bloc.index("Brindille") < bloc.index("En pause") < bloc.index("Ombrevive")
    assert re.search(r'Sélénith</span><b class="num">\d / 4</b>', bloc)


def test_photo_de_fond_sur_chaque_page_jamais_un_etage_scelle():
    c = monde().connecter(ID_BRINDILLE)
    for chemin in ("/regles", "/histoire", "/grimpeurs"):
        assert 'data-ambiance="/etages/0/image"' in c.get(chemin).text, chemin
    assert 'data-ambiance="/etages/1/image"' not in c.get("/regles").text


def test_jeu_demo_etage8():
    import asyncio

    from epreuve.domaine.bareme import calculer_jauge
    from epreuve.web.demo import DepotEtage8

    depot = DepotEtage8()
    etages = asyncio.run(depot.etages())
    assert [e.statut for e in etages] == ["termine"] * 8 + ["ouvert", "scelle", "scelle"]
    e8 = next(e for e in etages if e.numero == 8)
    contenu = asyncio.run(depot.contenu_etage(e8.id))
    jauge = calculer_jauge(contenu, asyncio.run(depot.grimpeurs()), asyncio.run(depot.coches_etage(e8.id)), Regles())
    assert (jauge.score, jauge.palier, jauge.actifs, jauge.en_pause, jauge.maximum) == (31, 44, 22, 3, 88)


def test_maquette_etage8_autonome():
    from pathlib import Path

    dossier = Path(__file__).resolve().parents[2] / "docs" / "design"
    html = (dossier / "maquette-etage8.html").read_text()
    assert "<script" not in html and "<link" not in html and 'role="progressbar"' in html
    assert "maquette-etage8/etage-8.webp" in html and "31 / 44" in html
    assert not re.search(r'(?:href|src)="/', html)  # aucun lien absolu cassé
    assert (dossier / "maquette-etage8" / "etage-8.webp").stat().st_size <= 300_000
    pyramide = html[html.index('<nav class="pyramide"'):html.index('<div class="pyr-brume"')]
    assert "Étage 8" not in pyramide and not re.search(r"\d+ étages", html) and "Étage scellé" not in html


# ------------------------------ bloc jaune rétrogradé qui garde des quêtes utiles (consigne du chef de projet)


def _monde_bloc_retrograde():
    m = monde()
    bloc = m.depot._blocs[2]  # « Astrub » : principal par la règle, avec des quêtes principales
    noms = [q.nom for q in m.depot._quetes.values() if q.etage_id == bloc.etage_id and q.bloc == bloc.titre
            and q.nature == "principale"]
    assert noms
    m.depot._blocs[2] = replace(bloc, nature="secondaire", nature_origine="admin", nature_motif="test")
    return m, noms


def test_bloc_jaune_avec_quetes_utiles_affiche_un_avertissement():
    m, noms = _monde_bloc_retrograde()
    html = m.connecter(ID_BRINDILLE).get("/etages/0").text
    liste = html.split('id="liste"')[1]
    s = "s" if len(noms) > 1 else ""
    assert f"⚠ Contient {len(noms)} quête{s} utile{s} pour un Dofus :" in liste
    for nom in noms:
        assert html_mod.escape(nom, quote=True) in liste
    # Un seul avertissement : le bloc secondaire naturel (aucune quête principale) n'en a pas, ni les blocs rouges.
    assert liste.count("avert-utiles") == 1
    # Le vrai compte : le bloc rétrogradé garde « 3 principales », le bloc secondaire naturel « 3 secondaires ».
    assert "<summary>3 principales</summary>" in liste and "<summary>3 secondaires</summary>" in liste
    # Le barème ne change pas : le bloc compte désormais dans les secondaires.
    assert 'data-cats="secondaires"' in liste


def test_pas_d_avertissement_sans_retrogradation():
    liste = monde().connecter(ID_BRINDILLE).get("/etages/0").text.split('id="liste"')[1]
    assert "avert-utiles" not in liste


def test_revue_admin_montre_les_quetes_utiles_du_bloc():
    m, noms = _monde_bloc_retrograde()
    html = m.connecter(ID_MARCEAU).get("/admin/etages/0").text
    assert "⚠ Contient" in html and "pour un Dofus" in html
    assert html_mod.escape(noms[0], quote=True) in html
