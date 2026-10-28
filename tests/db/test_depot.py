"""Le dépôt sur un vrai Postgres : contraintes, coches, concurrence, journal, admin, fiches, sessions."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError

from epreuve.db import tables as t
from epreuve.db.depot import (
    CocheRefusee,
    ContenuFiche,
    DejaInscrit,
    EtatInvalide,
    Introuvable,
    PasSurLaListe,
    PrerequisBrut,
    PseudoDejaPris,
    contenu_fiche_json,
)
from epreuve.domaine.fiche import Besoin, EtapeFiche, Position, Prerequis
from epreuve.domaine.modeles import ElementRef, Regles
from epreuve.domaine.ouverture import Bilan
from tests.fabrique import OUVERTURE, PENDANT, PLANCHER

R = Regles()
ADMIN = 1
BILAN = Bilan(PENDANT, 3, 6, 7, {"donjons": 2, "full_succes": 1, "principales": 2, "secondaires": 2}, False, None)


async def remplir(moteur):
    """Étage 0 ouvert (1 donjon de 5 cases, 2 quêtes, 1 quête masquée), étage 1 scellé (1 quête)."""
    async with moteur.begin() as c:
        for numero, statut in ((0, "ouvert"), (1, "scelle")):
            await c.execute(insert(t.etage).values(
                numero=numero, nom=f"Étage {numero}", niveau_min=1, niveau_max=20, level_cap=20, statut=statut,
                ouvert_le=OUVERTURE if statut == "ouvert" else None, date_plancher_suivant=PLANCHER,
                maj_le=OUVERTURE, alertes=["donjon X : 4 succès"] if numero == 0 else []))
        await c.execute(insert(t.donjon).values(etage_id=1, nom="Crypte", niveau=10, ordre=1, duffus_id="crypte",
                                                origine="propose", succes_source="duffus", masque=False))
        for o in range(1, 6):
            await c.execute(insert(t.case_succes).values(donjon_id=1, ordre=o, nom=f"S{o}", condition="",
                                                         est_classique=o == 1, duffus_id=str(o), masquee=False))
        for i, (etage, masquee) in enumerate(((1, False), (1, False), (1, True), (2, False)), 1):
            await c.execute(insert(t.quete).values(
                etage_id=etage, nom=f"Q{i}", niveau=10, bloc="Incarnam", ordre=i, nature="secondaire",
                nature_origine="duffus", dofus=[], duffus_id=f"q{i}", masquee=masquee))
        await c.execute(insert(t.donjon_disponible).values(
            duffus_id="grange", nom="Grange", niveau=20, succes_source="duffus", maj_le=OUVERTURE,
            succes=[{"id": "40", "nom": "Grange", "condition": "c", "est_classique": True},
                    {"id": "488", "nom": "Duo", "condition": "", "est_classique": False}]))


async def inscrire(depot, *ids, statut="actif"):
    await depot.ajouter_liste(list(ids), statut, ADMIN, OUVERTURE)
    return [await depot.creer_grimpeur(i, f"d{i}", f"Pseudo{i}", "Iop", None, OUVERTURE) for i in ids]


@pytest.fixture
async def base(depot, moteur):
    await remplir(moteur)
    return depot


# --- Lecture -----------------------------------------------------------------------------------------------


async def test_lecture_etages_et_contenu(base):
    assert base and await base.ping()
    assert [e.numero for e in await base.etages()] == [0, 1]
    assert (await base.etage_par_numero(1)).statut == "scelle" and await base.etage_par_numero(9) is None
    c = await base.contenu_etage(1)
    assert len(c.donjons) == 1 and len(c.cases) == 5 and [q.nom for q in c.quetes] == ["Q1", "Q2"]
    _, _, _, quetes = await base.contenu_brut(1)
    assert len(quetes) == 3
    assert await base.alertes_etage(1) == ["donjon X : 4 succès"]
    with pytest.raises(Introuvable):
        await base.contenu_brut(99)
    with pytest.raises(Introuvable):
        await base.alertes_etage(99)


# --- Contraintes ------------------------------------------------------------------------------------------


async def test_contraintes_de_la_base(base, moteur):
    async with moteur.connect() as c:
        for sql in (
            "INSERT INTO epreuve.case_succes (donjon_id, ordre, nom, est_classique) VALUES (1, 9, 'x', true)",
            "UPDATE epreuve.etage SET statut = 'ouvert' WHERE numero = 1",
            "UPDATE epreuve.etage SET palier_manuel = 0",
            "INSERT INTO epreuve.grimpeur (discord_user_id, nom_discord, pseudo_ig, classe, inscrit_le) "
            "VALUES (5, 'd', 'Xy', 'Paladin', now())",
        ):
            with pytest.raises(IntegrityError):
                async with c.begin():
                    await c.execute(text(sql))


async def test_on_delete_restrict_sur_un_element_coche(base, moteur):
    (g,) = await inscrire(base, 10)
    await base.cocher(g.id, ElementRef("quete", 1), True, 10, PENDANT, R)
    with pytest.raises(IntegrityError):
        async with moteur.begin() as c:
            await c.execute(text("DELETE FROM epreuve.quete WHERE id = 1"))


# --- Inscription ------------------------------------------------------------------------------------------


async def test_creer_grimpeur(base):
    with pytest.raises(PasSurLaListe, match="Shadoaze"):
        await base.creer_grimpeur(10, "d", "Brindille", None, None, OUVERTURE)
    await base.ajouter_liste([10, 11, 12], "pause", ADMIN, OUVERTURE)
    g = await base.creer_grimpeur(10, "d10", "  Brindille ", None, 15, OUVERTURE)
    assert (g.pseudo, g.statut, g.classe, g.niveau_declare) == ("Brindille", "pause", None, 15)
    with pytest.raises(DejaInscrit):
        await base.creer_grimpeur(10, "d10", "Autre", None, None, OUVERTURE)
    with pytest.raises(PseudoDejaPris):
        await base.creer_grimpeur(11, "d11", "brindille", None, None, OUVERTURE)  # sans tenir compte de la casse
    with pytest.raises(ValueError):
        await base.creer_grimpeur(11, "d11", "Ok", "Paladin", None, OUVERTURE)
    hors = await base.creer_grimpeur(99, "d99", "Libre", None, None, OUVERTURE, liste_obligatoire=False)
    assert hors.statut == "actif"
    assert (await base.grimpeur_par_discord(10)).id == g.id and await base.grimpeur_par_discord(5) is None
    assert (await base.grimpeur(g.id)).pseudo == "Brindille" and await base.grimpeur(999) is None
    assert await base.liste_officielle() == {10: "pause", 11: "pause", 12: "pause"}
    await base.maj_nom_discord(10, "nouveau")
    assert (await base.grimpeur(g.id)).nom_discord == "nouveau"


async def test_ajouter_liste_sans_doublon(base):
    assert await base.ajouter_liste([3, 4, 3], "actif", ADMIN, OUVERTURE) == [3, 4]
    assert await base.ajouter_liste([4, 5], "actif", ADMIN, OUVERTURE) == [5]
    assert await base.ajouter_liste([], "actif", ADMIN, OUVERTURE) == []
    with pytest.raises(ValueError):
        await base.ajouter_liste([6], "exclu", ADMIN, OUVERTURE)


async def test_modifier_grimpeur(base):
    a, b = await inscrire(base, 10, 11)
    g = await base.modifier_grimpeur(a.id, 10, PENDANT, pseudo="Mirelune", classe="Féca", niveau_declare=30)
    assert (g.pseudo, g.classe, g.niveau_declare) == ("Mirelune", "Féca", 30)
    assert await base.modifier_grimpeur(a.id, 10, PENDANT) == g
    with pytest.raises(PseudoDejaPris):
        await base.modifier_grimpeur(b.id, 11, PENDANT, pseudo="MIRELUNE")
    for kw in ({"niveau_declare": 0}, {"classe": "Paladin"}, {"pseudo": "x"}):
        with pytest.raises(ValueError):
            await base.modifier_grimpeur(a.id, 10, PENDANT, **kw)
    with pytest.raises(Introuvable):
        await base.modifier_grimpeur(999, 10, PENDANT, pseudo="Zzz")
    j = (await base.journal(type_="fiche_modifiee"))[0]
    assert j.details["pseudo_ig"] == {"avant": "Pseudo10", "apres": "Mirelune"} and j.public


# --- Coches -----------------------------------------------------------------------------------------------


async def test_cocher_idempotent_avec_cascade_et_journal(base):
    (g,) = await inscrire(base, 10)
    assert await base.cocher(g.id, ElementRef("case", 3), True, 10, PENDANT, R) == (ElementRef("case", 3),
                                                                                    ElementRef("case", 1))
    assert await base.cocher(g.id, ElementRef("case", 3), True, 10, PENDANT, R) == ()  # idempotent
    assert await base.cocher(g.id, ElementRef("case", 1), False, 10, PENDANT, R) == (ElementRef("case", 1),
                                                                                     ElementRef("case", 3))
    assert await base.cocher(g.id, ElementRef("quete", 2), True, 10, PENDANT, R) == (ElementRef("quete", 2),)
    assert (await base.coches_etage(1))[g.id].quetes == {2}
    assert len(await base.journal(type_="coche")) == 3
    assert (await base.dernieres_activites()) == {g.id: PENDANT}


async def test_cocher_sans_cascade(base):
    (g,) = await inscrire(base, 10)
    assert await base.cocher(g.id, ElementRef("case", 3), True, 10, PENDANT, Regles(succes_coche_vaincu=False)) \
        == (ElementRef("case", 3),)


@pytest.mark.parametrize("ref", [ElementRef("quete", 3), ElementRef("quete", 4), ElementRef("case", 99),
                                 ElementRef("quete", 99)])
async def test_cocher_introuvable_masque_ou_scelle(base, ref):
    (g,) = await inscrire(base, 10)
    with pytest.raises(Introuvable):
        await base.cocher(g.id, ref, True, 10, PENDANT, R)


async def test_cocher_statuts(base):
    a, b = await inscrire(base, 10, 11)
    await base.changer_statut(a.id, "pause", None, ADMIN, PENDANT)
    assert await base.cocher(a.id, ElementRef("quete", 1), True, 10, PENDANT, R)
    with pytest.raises(CocheRefusee):
        await base.cocher(a.id, ElementRef("quete", 2), True, 10, PENDANT, Regles(pause_peut_cocher=False))
    await base.changer_statut(b.id, "exclu", "triche", ADMIN, PENDANT)
    with pytest.raises(CocheRefusee):
        await base.cocher(b.id, ElementRef("quete", 1), True, 11, PENDANT, R)
    with pytest.raises(Introuvable):
        await base.cocher(999, ElementRef("quete", 1), True, 11, PENDANT, R)


async def test_coche_d_un_admin_sur_un_autre(base):
    (g,) = await inscrire(base, 10)
    await base.cocher(g.id, ElementRef("quete", 1), True, 10, PENDANT, R)
    with pytest.raises(ValueError, match="motif"):
        await base.cocher(g.id, ElementRef("quete", 1), False, ADMIN, PENDANT, R, motif="  ")
    assert await base.cocher(g.id, ElementRef("quete", 1), False, ADMIN, PENDANT, R, motif="erreur")
    j = (await base.journal(grimpeur_id=g.id, type_="coche"))[0]
    assert j.details["motif"] == "erreur" and not j.public and j.acteur_discord_id == ADMIN


async def test_cocher_donjon(base):
    (g,) = await inscrire(base, 10)
    await base.cocher(g.id, ElementRef("case", 2), True, 10, PENDANT, R)  # coche aussi la 1
    assert await base.cocher_donjon(g.id, 1, 10, PENDANT, R) == 3
    assert await base.cocher_donjon(g.id, 1, 10, PENDANT, R) == 0
    assert (await base.coches_etage(1))[g.id].cases == {1, 2, 3, 4, 5}
    assert await base.cocher_donjon(g.id, 1, ADMIN, PENDANT, R, motif="aide") == 0
    with pytest.raises(Introuvable):
        await base.cocher_donjon(g.id, 99, 10, PENDANT, R)


async def test_cocher_donjon_motif_journalise(base):
    (g,) = await inscrire(base, 10)
    assert await base.cocher_donjon(g.id, 1, ADMIN, PENDANT, R, motif="aide") == 5
    assert (await base.journal(type_="coche_donjon"))[0].details["motif"] == "aide"


async def test_concurrence_vingt_coches_simultanees(base, moteur):
    (g,) = await inscrire(base, 10)
    resultats = await asyncio.gather(*(base.cocher(g.id, ElementRef("quete", 1), True, 10, PENDANT, R)
                                       for _ in range(20)))
    assert sum(1 for r in resultats if r) == 1
    async with moteur.connect() as c:
        assert (await c.execute(text("SELECT count(*) FROM epreuve.coche_quete"))).scalar() == 1


# --- Admin : statuts, étages, ouverture ------------------------------------------------------------------


async def test_changer_statut(base):
    (g,) = await inscrire(base, 10)
    with pytest.raises(ValueError):
        await base.changer_statut(g.id, "exclu", "", ADMIN, PENDANT)
    with pytest.raises(ValueError):
        await base.changer_statut(g.id, "fantome", "x", ADMIN, PENDANT)
    assert (await base.changer_statut(g.id, "exclu", "triche", ADMIN, PENDANT)).statut == "exclu"
    assert (await base.changer_statut(g.id, "actif", None, ADMIN, PENDANT)).statut == "actif"
    j = await base.journal(type_="statut")
    assert [x.details["apres"] for x in j] == ["actif", "exclu"] and not j[0].public


async def test_palier_date_et_reglages_d_etage(base):
    assert (await base.regler_palier(1, 7, "absents", ADMIN, PENDANT)).palier_manuel == 7
    assert (await base.regler_palier(1, None, "", ADMIN, PENDANT)).palier_manuel is None
    for p, m in ((0, "x"), (5, " ")):
        with pytest.raises(ValueError):
            await base.regler_palier(1, p, m, ADMIN, PENDANT)
    with pytest.raises(Introuvable):
        await base.regler_palier(99, 3, "x", ADMIN, PENDANT)
    assert (await base.regler_date_plancher(1, None, ADMIN, PENDANT)).date_plancher_suivant is None
    assert (await base.regler_date_plancher(1, PLANCHER, ADMIN, PENDANT)).date_plancher_suivant == PLANCHER
    with pytest.raises(ValueError):
        await base.regler_date_plancher(1, PLANCHER.replace(tzinfo=None), ADMIN, PENDANT)
    e = await base.regler_etage(1, ADMIN, PENDANT, nom=" Le Seuil ", ambiance_url="https://cdn.discordapp.com/a.png",
                                level_cap=21)
    assert (e.nom, e.ambiance_url, e.level_cap) == ("Le Seuil", "https://cdn.discordapp.com/a.png", 21)
    assert (await base.regler_etage(1, ADMIN, PENDANT, ambiance_url="")).ambiance_url is None
    assert (await base.regler_etage(1, ADMIN, PENDANT, ambiance_url="/etages/0/image")).ambiance_url == \
        "/etages/0/image"
    for kw in ({}, {"nom": " "}, {"ambiance_url": "https://duffus.fr/x.png"}, {"ambiance_url": "http://x"},
               {"ambiance_url": "/etages/0/image/../x"},
               {"level_cap": 0}):
        with pytest.raises(ValueError):
            await base.regler_etage(1, ADMIN, PENDANT, **kw)


async def test_ouvrir_etage_et_bilan(base):
    e = await base.ouvrir_etage(1, BILAN, ADMIN, PENDANT)
    assert (e.numero, e.statut, e.ouvert_le) == (1, "ouvert", PENDANT)
    assert (await base.etage_par_numero(0)).statut == "termine"
    assert await base.bilan(1) == BILAN and await base.bilan(2) is None
    with pytest.raises(EtatInvalide):
        await base.ouvrir_etage(1, BILAN, ADMIN, PENDANT)
    with pytest.raises(Introuvable):
        await base.ouvrir_etage(7, BILAN, ADMIN, PENDANT)
    assert (await base.journal(type_="ouverture"))[0].public


async def test_deux_ouvertures_simultanees_une_seule_passe(base):
    r = await asyncio.gather(*(base.ouvrir_etage(1, BILAN, a, PENDANT) for a in (1, 2)), return_exceptions=True)
    assert sum(1 for x in r if isinstance(x, EtatInvalide)) == 1
    assert len(await base.journal(type_="ouverture")) == 1


# --- Admin : revue du contenu ----------------------------------------------------------------------------


async def test_revue_quete_donjon_case(base, moteur):
    with pytest.raises(ValueError):
        await base.modifier_quete(1, ADMIN, PENDANT, nature="principale")
    q = await base.modifier_quete(1, ADMIN, PENDANT, nature="principale", motif="Dofus Argenté", nom=" Q un ")
    assert (q.nature, q.nature_origine, q.nom) == ("principale", "admin", "Q un")
    assert (await base.modifier_quete(1, ADMIN, PENDANT, masquee=True)).masquee
    assert not (await base.modifier_quete(1, ADMIN, PENDANT, masquee=False)).masquee
    d = await base.modifier_donjon(1, ADMIN, PENDANT, masque=True, nom="Crypte de K.")
    assert d.masque and d.nom == "Crypte de K."
    c = await base.modifier_case(2, ADMIN, PENDANT, nom="Duo", condition="")
    assert (c.nom, c.condition) == ("Duo", "")
    assert (await base.modifier_case(2, ADMIN, PENDANT, masquee=True)).masquee
    for appel in (base.modifier_case(2, ADMIN, PENDANT), base.modifier_donjon(1, ADMIN, PENDANT, nom=" ")):
        with pytest.raises(ValueError):
            await appel
    with pytest.raises(Introuvable):
        await base.modifier_donjon(99, ADMIN, PENDANT, masque=True)
    async with moteur.connect() as cx:
        r = (await cx.execute(select(t.case_succes).where(t.case_succes.c.id == 2))).one()
    assert r.nom == "S2" and r.corrections == {"nom": "Duo", "condition": ""} and r.masque_par == "admin"
    j = await base.journal(type_="contenu_admin")
    assert not j[0].public and j[0].etage_id == 1


async def test_ajouter_donjon(base):
    assert await base.donjons_disponibles() == [("grange", "Grange", 20)]
    d = await base.ajouter_donjon(1, "grange", ADMIN, PENDANT)
    assert (d.origine, d.ordre, d.nom) == ("admin", 2, "Grange")
    c = await base.contenu_etage(1)
    assert [(x.nom, x.est_classique) for x in c.cases_du_donjon(d.id)] == [("Grange", True), ("Duo", False)]
    with pytest.raises(EtatInvalide):
        await base.ajouter_donjon(1, "grange", ADMIN, PENDANT)
    await base.modifier_donjon(d.id, ADMIN, PENDANT, masque=True)
    assert not (await base.ajouter_donjon(1, "grange", ADMIN, PENDANT)).masque
    with pytest.raises(Introuvable):
        await base.ajouter_donjon(1, "absent", ADMIN, PENDANT)
    with pytest.raises(Introuvable):
        await base.ajouter_donjon(99, "grange", ADMIN, PENDANT)


# --- Fiches de quête --------------------------------------------------------------------------------------


async def test_fiche_quete_et_quetes_sans_fiche(base, moteur):
    contenu = ContenuFiche(
        prerequis=[PrerequisBrut(duffus_id="q4", nom="Q4"), PrerequisBrut(nom="Hors guide")],
        etapes=[EtapeFiche(1, "Dialogue", "<p>Parler</p>")], objets=[Besoin("Blé", 3)],
        monstres=[Besoin("Bouftou", 2)], positions=[Position("PNJ", 4, -19, "Astrub")], succes_lie="S",
        recompenses=["10 xp"])
    async with moteur.begin() as c:
        await c.execute(insert(t.fiche_quete).values(quete_id=1, source="duffus", contenu=contenu_fiche_json(contenu)))
        await c.execute(insert(t.fiche_quete).values(quete_id=2, source="dofusdb", contenu={}))
    f = await base.fiche_quete(1)
    assert (f.nom, f.etage_numero, f.source, f.complete) == ("Q1", 0, "duffus", True)
    assert f.prerequis == (Prerequis(4, "Q4", "visible"), Prerequis(None, "Hors guide", "hors_guide"))
    assert f.etapes[0].texte_html == "<p>Parler</p>" and f.positions[0].zone == "Astrub"
    assert not (await base.fiche_quete(2)).complete and await base.fiche_quete(3) is None
    assert [q.id for q in await base.quetes_sans_fiche(1)] == [2]
    assert (await base.contenu_etage(1)).quetes[0].a_une_fiche
    assert await base.etage_des_quetes() == {1: 0, 2: 0, 3: 0, 4: 1}


async def test_fiche_sans_prerequis_connu(base, moteur):
    async with moteur.begin() as c:
        await c.execute(insert(t.fiche_quete).values(quete_id=1, source="duffus", contenu={}))
    assert (await base.fiche_quete(1)).prerequis == ()


# --- Sessions ---------------------------------------------------------------------------------------------


async def test_sessions(base):
    await base.creer_session(b"h1", 10, "d", False, "jeton", "csrf", PENDANT, timedelta(days=7))
    s = await base.session(b"h1", PENDANT)
    assert (s.discord_user_id, s.est_admin, s.expire_le) == (10, False, PENDANT + timedelta(days=7))
    await base.maj_roles_session(b"h1", True, PENDANT + timedelta(hours=1))
    s = await base.session(b"h1", PENDANT + timedelta(hours=1))
    assert s.est_admin and s.roles_verifies_le == PENDANT + timedelta(hours=1)
    assert await base.session(b"h1", PENDANT + timedelta(days=7)) is None  # expirée
    await base.creer_session(b"h2", 11, "d", False, "j2", "c", PENDANT - timedelta(days=30), timedelta(days=7))
    assert await base.purger_sessions(PENDANT) == 1
    assert await base.supprimer_session(b"h1") == "jeton" and await base.supprimer_session(b"h1") is None


async def test_ping_base_injoignable():
    from epreuve.db.depot import Depot
    from epreuve.db.session import creer_moteur
    m = creer_moteur("postgresql+asyncpg://x:y@127.0.0.1:1/z")
    assert not await Depot(m).ping()
    await m.dispose()


async def test_journal_filtres(base):
    (g,) = await inscrire(base, 10)
    assert {j.type for j in await base.journal()} == {"liste_ajout", "inscription"}
    assert [j.type for j in await base.journal(grimpeur_id=g.id)] == ["inscription"]
    assert await base.journal(etage_id=1) == [] and len(await base.journal(limite=1)) == 1
