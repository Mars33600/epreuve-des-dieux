"""Construction des étages 0 et 1 depuis l'aspiration réelle (donnees/duffus/), puis écriture en base."""

import dataclasses
import json
import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from epreuve.contenu import construire as k
from epreuve.contenu.__main__ import main
from epreuve.contenu.ecrire import EcritureRefusee, ecrire_etage
from epreuve.contenu.fiche_duffus import arbre, lire_fiche, nettoyer_fiche
from epreuve.db import tables as t
from epreuve.domaine.modeles import ElementRef, Regles

ASPI = k.Aspiration.lire(k.derniere_aspiration())
CFG = k.lire_config_etages()
DOFUS = k.lire_dofus_retenus()
MAINTENANT = datetime(2026, 10, 29, 12, tzinfo=UTC)


def etage(n, **kw):
    return k.construire(n, ASPI, CFG, DOFUS, **kw)


ETAGES = {n: etage(n) for n in (0, 1)}


# --- L'étage 0 complet ----------------------------------------------------------------------------------------


def test_etage_0_complet():
    e = ETAGES[0]
    assert (e.tranche, e.niveau_min, e.niveau_max, e.level_cap) == ("1-20", 1, 20, 20)
    assert e.ouvert_le == datetime(2026, 10, 30, 16, tzinfo=UTC)
    assert e.date_plancher_suivant == datetime(2026, 11, 13, 16, tzinfo=UTC)
    assert [d.nom for d in e.donjons] == ["Crypte de Kardorim"]
    assert [c.nom for c in e.donjons[0].cases] == ["Crypte de Kardorim", "Kardorim (Duo)", "Kardorim (Zombie)",
                                                   "Kardorim (Premier)", "Kardorim (Spécial)"]
    assert [c.est_classique for c in e.donjons[0].cases] == [True, False, False, False, False]
    assert len(e.quetes) == 27 and e.sans_fiche == [] and e.quetes[0].nom == "L'anneau de tous les dangers"
    assert [q.ordre for q in e.quetes] == list(range(1, 28))
    assert {q.bloc for q in e.quetes} == {"Quêtes du tutoriel", "Quêtes d'Incarnam"}


def test_niveau_reel_de_la_quete_et_non_le_palier_de_quest_list():
    """Régression : quest_list.level est un palier arrondi (« 10 » pour tout le tutoriel) ; le vrai niveau est
    meta.level de la page Duffus (quête 1 : niveau 1, « Ça sent le gaz » : niveau 20 au lieu de 25)."""
    e = ETAGES[0]
    assert ASPI.quetes[1]["level"] == "10" and e.quetes[0].niveau == 1
    assert [q.niveau for q in e.quetes if q.nom == "Sous le regard des dieux"] == [2]
    assert len({q.niveau for q in e.quetes}) > 3
    assert k.niveau_quete({"level": "25"}, {"meta": {"level": 0}}) == 25  # repli si la page n'a pas de niveau
    assert k.niveau_quete({"level": "25"}, None) == 25


def test_etage_1_donjons_rappels_et_quete_sans_fiche():
    e = ETAGES[1]
    assert [d.nom for d in e.donjons] == ["Grange du Tournesol Affamé", "Château Ensablé", "Cour du Bouftou Royal",
                                          "Cache de Kankreblath"]
    assert all(len(d.cases) == 5 and d.succes_source == "duffus" for d in e.donjons)
    assert len(e.quetes) == 43 and len(e.rappels) == 6 and e.sans_fiche == ["Quête de classe"]
    assert any("sans fiche : Quête de classe" in a for a in e.alertes)


def test_classique_en_premier_puis_duo():
    for e in ETAGES.values():
        for d in e.donjons:
            assert d.cases[0].est_classique and d.cases[0].nom == d.nom
            assert d.cases[1].nom.endswith("(Duo)") and "[challenge," not in d.cases[1].condition
            assert all(c.defi_id for c in d.cases[1:]) and not d.cases[0].defi_id


def test_nature_par_les_guides_par_dofus():
    guides = k.guides_par_dofus(ASPI)
    assert len(guides["Dofus Argenté"]) == 64 and "Dofus Cacao" in guides and "Dofus Kaliptus" not in guides
    nb = {n: sum(1 for q in e.quetes if q.nature == "principale") for n, e in ETAGES.items()}
    assert nb == {0: 26, 1: 37}
    assert all(q.nature_origine == "duffus" for e in ETAGES.values() for q in e.quetes)
    assert all(q.dofus for e in ETAGES.values() for q in e.quetes if q.nature == "principale")
    assert any("sans guide Duffus : Dofus Kaliptus" in a for a in ETAGES[0].alertes)
    forcee = etage(0, forcees={ETAGES[0].quetes[0].duffus_id: "secondaire"})
    assert (forcee.quetes[0].nature, forcee.quetes[0].nature_origine) == ("secondaire", "admin")


def test_nature_par_le_repli_pour_un_dofus_sans_guide():
    q = next(x for x in ETAGES[0].quetes if x.nature == "secondaire")
    e = etage(0, guides_repli={"Dofus Kaliptus": frozenset({int(q.duffus_id)})})
    r = next(x for x in e.quetes if x.duffus_id == q.duffus_id)
    assert (r.nature, r.nature_origine, r.dofus) == ("principale", "dofusdb", ("Dofus Kaliptus",))


@pytest.mark.parametrize(("note", "jusqu", "lier"), [
    ("Avancez jusqu'à l'étape du donjon et liez la quête d'en dessous.",
     "Avancez jusqu'à l'étape du donjon et liez la quête d'en dessous.",
     "Avancez jusqu'à l'étape du donjon et liez la quête d'en dessous."),
    ("N'oubliez pas le rocher. Vous pouvez faire X en simultanée.", None, "Vous pouvez faire X en simultanée."),
    ("Collier de perles.", None, None),
])
def test_jusqu_ou_et_a_lier_lus_dans_les_notes(note, jusqu, lier):
    assert k.jusqu_ou_et_a_lier({"note": note, "note2": note}) == (jusqu, lier)


def test_json_liste_tolerant():
    assert k._json_liste("pas du json") == [] and k._json_liste('{"a": 1}') == [] and k._json_liste('[1, {"a": 2}]') \
        == [{"a": 2}]


def test_donjons_disponibles_pour_l_admin():
    noms = {d.nom for d in ETAGES[0].disponibles}
    assert len(ETAGES[0].disponibles) > 100 and "Château Ensablé" in noms
    assert all(d.cases for d in ETAGES[0].disponibles)


def test_rapport():
    r = ETAGES[1].rapport()
    assert "tranche 20-40" in r and "4 donjons, 20 cases, 43 quêtes" in r


# --- Parité des fiches (critère 11 bis) ---------------------------------------------------------------------


def _slug_vers_entree():
    return {k.slug_quete(q): q for q in ASPI.quetes.values() if k.slug_quete(q)}


@pytest.mark.parametrize("n", [0, 1])
def test_parite_des_fiches(n):
    """Chaque champ non vide côté Duffus se retrouve dans la fiche structurée."""
    entrees = _slug_vers_entree()
    for q in ETAGES[n].quetes:
        if q.fiche is None:
            continue
        entree = ASPI.quetes[int(q.duffus_id)]
        page = ASPI.pages[k.slug_quete(entree)]
        f = q.fiche
        html = page["content_html"] or ""
        assert f.etapes, q.nom
        if "qpos" in html or (page["meta"].get("startCoords") or "").strip():
            assert f.positions, q.nom
        if "recipe-item" in html or page["manual_resources"]:
            assert f.objets, q.nom
        if "combat-line" in html or "mob-stats-name" in html:
            assert f.monstres, q.nom
        liens = json.loads(page["prereq_quests"] or "[]")
        assert len(f.prerequis) == len(liens) + sum(1 for p in page["prereqs"] or [] if (p.get("text") or "").strip())
        for lien, p in zip(liens, f.prerequis, strict=False):
            assert p.nom == lien["title"]
            cible = entrees.get(lien["link"].removeprefix("/quete/"))
            assert p.duffus_id == (str(cible["id"]) if cible else None)
        r = page["rewards"] or {}
        for cle in ("xp", "kamas"):
            if r.get(cle):
                chiffres = re.sub(r"\D", "", str(r[cle]))
                assert any(re.sub(r"\D", "", x) == chiffres for x in f.recompenses), q.nom
        assert len(f.recompenses) >= len(r.get("items") or [])
        if entree.get("succes"):
            assert all(s in f.succes_lie for s in entree["succes"])
        if entree.get("note"):
            assert f.etapes[0].titre == "Note du guide"


def test_nettoyer_toutes_les_fiches_reelles():
    for page in ASPI.pages.values():
        propre = nettoyer_fiche(page["content_html"], {"reponses-a-tout": "/etages/0/quetes/3"})
        assert not re.search(r"<(script|style|img|svg|iframe|button|input)\b", propre, re.I)
        assert not re.search(r"\son\w+\s*=", propre, re.I)
        assert "duffus" not in propre.lower() and "supabase" not in propre.lower()
        assert not re.search(r'href="(?!/etages/)', propre)
    for q in ETAGES[0].quetes + ETAGES[1].quetes:
        for e in q.fiche.etapes if q.fiche else ():
            assert "<img" not in e.texte_html and "supabase" not in e.texte_html


def test_nettoyer_fiche_cas_adverses():
    sale = ('<p onclick="x()">A<script>alert(1)</script><img src=x onerror=alert(1)>'
            '<a href="https://duffus.fr/quete/a">B</a><a href="/quete/a">C</a><a href="/quete/z">D</a>'
            '<a href="javascript:alert(1)">E</a><style>p{}</style></p>')
    propre = nettoyer_fiche(sale, {"a": "/etages/0/quetes/7"})
    assert propre == '<p>AB<a href="/etages/0/quetes/7">C</a>DE</p>'
    assert nettoyer_fiche("", {}) == ""


def test_arbre_tolere_le_html_casse():
    racine = arbre("<div class='qstep move'><p>texte <b>gras</div></span><br>fin")
    assert racine.texte() == "texte gras fin"
    assert '<br>' in racine.html() and racine.par_classe("qstep")[0].classes == ["qstep", "move"]


def test_lire_fiche_cas_limites():
    page = {"content_html": '<div class="qstep combat"><div class="cell-right"><div class="combat-line">Vaincre '
                            '3 x <a href="/monstre/1">Bouftou</a> et 2 x <a href="/monstre/2">Tofu</a></div></div>'
                            '</div><div class="qstep dialogue"><ul></ul></div>'
                            '<li class="recipe-item"><span class="recipe-name">Blé</span></li>',
            "meta": {"startCoords": "pas de coordonnées"}, "prereq_quests": "pas du json",
            "prereqs": [{"text": "  "}, {"text": "Niveau 20"}], "manual_resources": [{"qty": 2, "label": "Blé"},
                                                                                     {"qty": 1, "label": "Lin"}],
            "rewards": {"items": ["Brut"], "others": [{"label": "Émote"}, "Titre"]}}
    f = lire_fiche(page, {"note": "N", "note2": "N", "lancement": "Parlez à X"}, {}, {}, [{"name": "Orge", "qty": 4}])
    assert [m.nom for m in f.monstres] == ["Bouftou", "Tofu"] and [m.quantite for m in f.monstres] == [3, 2]
    assert [(o.nom, o.quantite) for o in f.objets] == [("Blé", 1), ("Lin", 1), ("Orge", 4)]
    assert [p.nom for p in f.prerequis] == ["Niveau 20"] and f.positions == []
    assert f.recompenses == ["Brut", "Émote", "Titre"] and f.etapes[0].texte_html == "N" and f.succes_lie is None
    assert [e.titre for e in f.etapes] == ["Note du guide", "Pour la lancer", "Combat"]
    assert [e.ordre for e in f.etapes] == [1, 2, 3]


# --- Configuration et seuils ---------------------------------------------------------------------------------


def test_seuil_de_5_pourcent_sans_fiche():
    sans_pages = dataclasses.replace(ASPI, pages={})
    with pytest.raises(k.ConstructionArretee, match="décision de Marceau"):
        k.construire(0, sans_pages, CFG, DOFUS)
    e = k.construire(0, sans_pages, CFG, DOFUS, forcer=True)
    assert len(e.sans_fiche) == 27 and any("plus de 5 %" in a for a in e.alertes)


def test_tranche_par_config_et_hors_guide(tmp_path):
    f = tmp_path / "etages.yaml"
    f.write_text("etages:\n  5:\n    tranche: '1-20'\n    nom: Le Seuil\n    level_cap: 21\n", encoding="utf-8")
    e = k.construire(5, ASPI, k.lire_config_etages(f), DOFUS)
    assert (e.tranche, e.nom, e.level_cap) == ("1-20", "Le Seuil", 21)
    with pytest.raises(k.ConfigInvalide, match="24 tranches"):
        k.construire(24, ASPI, CFG, DOFUS)
    f.write_text("etages:\n  0:\n    tranche: '999-1000'\n", encoding="utf-8")
    with pytest.raises(k.ConfigInvalide, match="absente"):
        k.construire(0, ASPI, k.lire_config_etages(f), DOFUS)


@pytest.mark.parametrize("contenu", ["etages:\n  0:\n    inconnu: 1\n",
                                     "etages:\n  0:\n    ouvert_le: 2026-10-30T17:00:00\n",
                                     "etages:\n  0:\n    ambiance_url: https://duffus.fr/a.png\n", "etages: [\n",
                                     "etages:\n  0:\n    ambiance_url: /etages/1/image\n",
                                     "etages:\n  0:\n    ambiance_url: /static/etage-0.webp\n"])
def test_config_etages_invalide(tmp_path, contenu):
    f = tmp_path / "etages.yaml"
    f.write_text(contenu, encoding="utf-8")
    with pytest.raises(k.ConfigInvalide):
        k.lire_config_etages(f)


def test_config_absente_et_dofus(tmp_path):
    assert k.lire_config_etages(tmp_path / "absent.yaml") == {}
    assert "Dofus Émeraude" in DOFUS and len(DOFUS) == 26
    f = tmp_path / "dofus.yaml"
    for contenu in ("dofus: Émeraude\n", "- x\n", "dofus: [\n"):
        f.write_text(contenu, encoding="utf-8")
        with pytest.raises(k.ConfigInvalide):
            k.lire_dofus_retenus(f)
    with pytest.raises(k.ConfigInvalide):
        k.lire_dofus_retenus(tmp_path / "absent.yaml")


def test_aspiration_absente_ou_incomplete(tmp_path):
    with pytest.raises(k.ConfigInvalide, match="aucune aspiration"):
        k.derniere_aspiration(tmp_path)
    (tmp_path / "2026-10-28").mkdir()
    with pytest.raises(k.ConfigInvalide, match="incomplète"):
        k.Aspiration.lire(tmp_path / "2026-10-28")


def test_bornes_et_alertes_de_donjon():
    assert k.bornes("1-20") == (1, 20) and k.bornes("200-3") == (200, 200) and k.bornes("50") == (50, 50)
    page = {"slug": "x", "meta": {"title": "Inconnu", "level": "?"}}
    d, alertes = k.donjon_prepare(page, ASPI, 1, None)
    assert d.cases == () and d.niveau is None and "repli DofusDB" in alertes[0]
    sept = next(p for p in ASPI.donjons.values() if len(k.succes_duffus(p, ASPI.succes)) == 6)
    assert "6 succès au lieu de 5" in k.donjon_prepare(sept, ASPI, 1, None)[1][0]


def test_entrees_et_donjons_manquants():
    r = ASPI.ranges
    faux = [dict(x) for x in r]
    premier = min((x for x in faux if x["is_active"]), key=lambda x: x["order_index"])
    premier["categories"] = [{"title": "B", "items": [{"type": "quest", "id": 999999}, {"type": "quest", "id": 29}]}]
    sans_crypte = {s: p for s, p in ASPI.donjons.items() if s != "crypte-de-kardorim"}
    e = k.construire(0, dataclasses.replace(ASPI, ranges=faux, donjons=sans_crypte), CFG, DOFUS)
    assert any("999999" in a for a in e.alertes) and any("sans page Duffus" in a for a in e.alertes)
    premier["categories"] = []
    e = k.construire(0, dataclasses.replace(ASPI, ranges=faux), CFG, DOFUS)
    assert e.quetes == [] and any("Duffus en annonce 1" in a for a in e.alertes)


# --- Écriture en base -----------------------------------------------------------------------------------------


async def test_ecrire_etages_0_et_1(depot, moteur):
    r0 = await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    r1 = await ecrire_etage(moteur, ETAGES[1], MAINTENANT)
    assert r0.cree and r1.cree and r0.ajoutes == 1 + 5 + 27
    e0, e1 = await depot.etages()
    assert (e0.statut, e0.ouvert_le, e1.statut, e1.ouvert_le) == ("ouvert", ETAGES[0].ouvert_le, "scelle", None)
    c = await depot.contenu_etage(e0.id)
    assert len(c.donjons) == 1 and len(c.cases) == 5 and len(c.quetes) == 27 and all(q.a_une_fiche for q in c.quetes)
    assert [q.nom for q in await depot.quetes_sans_fiche(e1.id)] == ["Quête de classe"]
    assert any("sans guide Duffus" in a for a in await depot.alertes_etage(e0.id))
    fiche = await depot.fiche_quete(c.quetes[3].id)
    assert fiche.etapes and fiche.source == "duffus" and fiche.prerequis
    assert len(await depot.donjons_disponibles()) == len(ETAGES[0].disponibles)
    assert [j.type for j in await depot.journal()] == ["contenu_cree", "contenu_cree"]


async def test_reconstruction_idempotente_et_choix_admin_conserves(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    c = await depot.contenu_etage(e0.id)
    q1, q2 = c.quetes[0], c.quetes[1]
    await depot.modifier_quete(q1.id, 1, MAINTENANT, nature="principale", motif="Dofus", nom="Renommée")
    await depot.modifier_quete(q2.id, 1, MAINTENANT, masquee=True)
    await depot.ajouter_donjon(e0.id, "chateau-ensable", 1, MAINTENANT)
    await depot.regler_etage(e0.id, 1, MAINTENANT, nom="Le Seuil")
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT + timedelta(hours=1))
    assert (r.cree, r.ajoutes, r.masques, r.demasques) == (False, 0, 0, 0) and r.changements == []
    etage, donjons, _, quetes = await depot.contenu_brut(e0.id)
    q1b = next(q for q in quetes if q.id == q1.id)
    assert (q1b.nature, q1b.nature_origine, q1b.nom) == ("principale", "admin", "Renommée")
    assert next(q for q in quetes if q.id == q2.id).masquee
    assert {d.nom for d in donjons} == {"Crypte de Kardorim", "Château Ensablé"} and etage.nom == "Le Seuil"
    assert len(quetes) == 27  # aucun doublon
    assert (await depot.journal(type_="contenu_maj"))[0].details["ajoutes"] == 0


async def test_reconstruction_masque_ce_qui_disparait_et_garde_fou(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    g = (await depot.ajouter_liste([7], "actif", 7, MAINTENANT), await depot.creer_grimpeur(7, "d", "Gr", None,
                                                                                            None, MAINTENANT))[1]
    quete = (await depot.contenu_etage(e0.id)).quetes[0]
    await depot.cocher(g.id, ElementRef("quete", quete.id), True, 7, MAINTENANT, Regles())
    moins = dataclasses.replace(ETAGES[0], quetes=ETAGES[0].quetes[1:], donjons=[])  # 1 quête + 1 donjon disparus
    with pytest.raises(EcritureRefusee, match="plus de 10 %"):
        await ecrire_etage(moteur, moins, MAINTENANT)
    peu = dataclasses.replace(ETAGES[0], quetes=ETAGES[0].quetes[1:])
    r = await ecrire_etage(moteur, peu, MAINTENANT)
    assert r.masques == 1 and "disparu" in r.changements[0]
    _, _, _, quetes = await depot.contenu_brut(e0.id)
    assert next(q for q in quetes if q.id == quete.id).masquee  # masquée, pas supprimée : la coche reste
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    assert r.demasques == 1
    r = await ecrire_etage(moteur, moins, MAINTENANT, forcer=True)
    assert r.masques == 2  # la quête et le donjon (ses 5 cases disparaissent avec lui) : 6 éléments sur 32
    async with moteur.connect() as c:
        assert (await c.execute(text("SELECT count(*) FROM epreuve.coche_quete"))).scalar() == 1


async def test_reconstruction_met_a_jour_les_libelles(depot, moteur):
    await ecrire_etage(moteur, ETAGES[1], MAINTENANT)
    q0 = ETAGES[1].quetes[0]
    d0 = ETAGES[1].donjons[0]
    cases = (dataclasses.replace(d0.cases[1], ordre=1, est_classique=True),
             dataclasses.replace(d0.cases[0], ordre=2, est_classique=False), *d0.cases[2:4])
    autre = dataclasses.replace(ETAGES[1], quetes=[dataclasses.replace(q0, nom="Nouveau nom", nature="principale",
                                                                       nature_origine="duffus"),
                                                   *ETAGES[1].quetes[1:]],
                                donjons=[dataclasses.replace(d0, cases=cases), *ETAGES[1].donjons[1:]])
    r = await ecrire_etage(moteur, autre, MAINTENANT)  # étage scellé : pas de garde-fou
    assert any("Nouveau nom" in c for c in r.changements) and r.masques == 1
    async with moteur.connect() as c:
        rows = (await c.execute(select(t.case_succes.c.nom, t.case_succes.c.est_classique, t.case_succes.c.masquee)
                                .join(t.donjon).where(t.donjon.c.duffus_id == d0.duffus_id)
                                .order_by(t.case_succes.c.ordre))).all()
    assert rows[0].nom.endswith("(Duo)") and rows[0].est_classique and rows[-1].masquee


# --- Ligne de commande ---------------------------------------------------------------------------------------


def test_commande_a_blanc(capsys, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["construire", "--etage", "1", "--a-blanc", "--sans-reseau"]) == 0
    sortie = capsys.readouterr().out
    assert "tranche 20-40" in sortie and "Rien n'a été écrit" in sortie


def test_commande_sans_base_ou_hors_guide(capsys, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["construire", "--etage", "0", "--sans-reseau"]) == 1
    assert main(["construire", "--etage", "40", "--a-blanc", "--sans-reseau"]) == 1
    assert "Arrêt" in capsys.readouterr().err


async def test_commande_ecrit_en_base(depot, moteur, monkeypatch, url_base, capsys):
    import asyncio

    monkeypatch.setenv("DATABASE_URL", url_base)
    commande = ["construire", "--etage", "0", "--aspiration", "2026-10-28", "--sans-reseau"]
    resultat = await asyncio.to_thread(main, commande)
    assert resultat == 0 and "Étage créé" in capsys.readouterr().out
    assert len(await depot.etages()) == 1


def test_regle_du_special_prise_chez_duffus_et_les_autres_attendent_dofusdb():
    cases = ETAGES[0].donjons[0].cases
    assert cases[4].condition.startswith("Kardorim ne doit jamais finir son tour")
    assert [c.condition for c in cases[1:4]] == ["", "", ""] and [c.defi_id for c in cases[1:4]] == [102, 115, 117]


async def test_completer_regles_depuis_le_cache_dofusdb():
    from epreuve.dofusdb.repli import ClientEnCache

    e = await k.completer_regles(etage(0), ClientEnCache(None, k.RACINE / "donnees" / "dofusdb"))
    regles = {c.nom: c.condition for c in e.donjons[0].cases}
    assert regles["Kardorim (Duo)"] == "Finir le donjon à deux personnages au plus."
    assert regles["Kardorim (Zombie)"].startswith("Les combattants alliés doivent utiliser exactement un point")
    assert "Aléatoire :" in regles["Kardorim (Premier)"] and all(regles.values())
    e1 = await k.completer_regles(etage(1), ClientEnCache(None, k.RACINE / "donnees" / "dofusdb"))
    assert not any("introuvable" in a for a in e1.alertes)
    assert all(c.condition and "{" not in c.condition for d in e1.donjons for c in d.cases)
