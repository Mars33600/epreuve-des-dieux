"""Les blocs du guide Duffus (SPEC v5 §3 et §5) : construction, écriture, correction d'un admin, blocs hybrides
coupés en deux moitiés (décision du 06/11) et leur migration."""

import dataclasses

import pytest
from sqlalchemy import text, update

from epreuve.contenu import construire as k
from epreuve.contenu.ecrire import ecrire_etage
from epreuve.db import tables as t
from epreuve.domaine.modeles import ElementRef, Regles
from tests.conftest import alembic
from tests.contenu.test_construire import ETAGES, MAINTENANT, etage

INCARNAM, TUTORIEL = "Quêtes d'Incarnam", "Quêtes du tutoriel"
SECONDAIRE_INCARNAM = "15"  # « La fin du règne », seule quête secondaire du bloc Incarnam (étage 0)


def avec_natures(e: k.EtagePrepare, natures: dict[str, str]) -> k.EtagePrepare:
    """L'étage avec certaines quêtes changées de nature (duffus_id → nature), ses blocs recalculés comme le ferait la
    construction (mêmes numéros, même ordre des titres)."""
    quetes = [dataclasses.replace(q, nature=natures.get(q.duffus_id, q.nature)) for q in e.quetes]
    numeros = {b.titre: b.numero for b in e.blocs}
    return dataclasses.replace(e, quetes=quetes, blocs=k.blocs_depuis_quetes(quetes, numeros, list(numeros)))


async def grimpeur(depot):
    await depot.ajouter_liste([7], "actif", 7, MAINTENANT)
    return await depot.creer_grimpeur(7, "d", "Gr", None, None, MAINTENANT)


# --- Construction ----------------------------------------------------------------------------------------------


def test_blocs_des_etages_0_et_1():
    b0, b1 = ETAGES[0].blocs, ETAGES[1].blocs
    # Incarnam (étage 0) et le bloc 3 (étage 1) mêlent principales et secondaires : coupés en deux moitiés, même
    # numéro et même ordre, la principale d'abord.
    assert [(b.numero, b.ordre, b.titre, b.nature, b.nb_quetes, b.moitie) for b in b0] == [
        (1, 1, TUTORIEL, "principale", 3, False),
        (2, 2, INCARNAM, "principale", 23, True), (2, 2, INCARNAM, "secondaire", 1, True)]
    assert [(b.numero, b.nature, b.nb_quetes, b.moitie) for b in b1] == [
        (3, "principale", 33, True), (3, "secondaire", 6, True), (4, "principale", 4, False)]
    assert sum(b.nb_quetes for b in b0) == 27 and sum(b.nb_quetes for b in b1) == 43
    assert all(b.duffus_url == k.URL_GUIDE_DUFFUS and b.duffus_ancre is None for b in (*b0, *b1))
    # Une partie ne porte que des quêtes de sa nature.
    assert [b.nb_principales for b in b0] == [3, 23, 0]
    assert "2 blocs, dont 1 hybride(s) coupé(s) en deux (2 parties principales, 1 secondaires)" in ETAGES[0].rapport()
    assert f"bloc 2 · {INCARNAM} (moitié) : secondaire, 1 quête(s)" in ETAGES[0].rapport()


def test_bloc_entier_reste_en_un_seul_morceau():
    qs = [dataclasses.replace(q, nature="secondaire") for q in ETAGES[0].quetes if q.bloc == TUTORIEL]
    (b,) = k.blocs_depuis_quetes(qs)
    assert (b.nature, b.nb_principales, b.nb_quetes, b.moitie) == ("secondaire", 0, 3, False)
    tout_rouge = avec_natures(ETAGES[0], {SECONDAIRE_INCARNAM: "principale"})
    assert [(b.titre, b.nature, b.nb_quetes, b.moitie) for b in tout_rouge.blocs] == [
        (TUTORIEL, "principale", 3, False), (INCARNAM, "principale", 24, False)]


# --- Écriture et reconstruction ---------------------------------------------------------------------------------


async def test_ecriture_d_un_hybride_chaque_quete_dans_sa_moitie(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    blocs = await depot.blocs_brut(e0.id)
    assert [(b.titre, b.nature, b.partie, b.nb_principales, b.nb_quetes, b.moitie) for b in blocs] == [
        (TUTORIEL, "principale", "principale", 3, 3, False),
        (INCARNAM, "principale", "principale", 23, 23, True), (INCARNAM, "secondaire", "secondaire", 0, 1, True)]
    c = await depot.contenu_etage(e0.id)
    jaune = blocs[2]
    assert [q.nom for q in c.quetes_du_bloc(jaune)] == ["La fin du règne"]
    assert len(c.quetes_du_bloc(blocs[1])) == 23 and c.quetes_utiles_du_bloc(jaune) == ()
    assert [[b.id for b in g] for g in c.groupes_blocs()] == [[blocs[0].id], [blocs[1].id, jaune.id]]


async def test_reconstruction_stable_sans_doublon_et_coches_conservees(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    avant = await depot.blocs_brut(e0.id)
    g = await grimpeur(depot)
    for b in avant[1:]:
        await depot.cocher(g.id, ElementRef("bloc", b.id), True, 7, MAINTENANT, Regles())
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    assert (r.ajoutes, r.masques, r.demasques, r.changements) == (0, 0, 0, [])
    assert [(b.id, b.partie) for b in await depot.blocs_brut(e0.id)] == [(b.id, b.partie) for b in avant]
    assert (await depot.coches_etage(e0.id))[g.id].blocs == {avant[1].id, avant[2].id}


async def test_un_bloc_entier_qui_devient_hybride_puis_entier_garde_sa_ligne(depot, moteur):
    tout_rouge = avec_natures(ETAGES[0], {SECONDAIRE_INCARNAM: "principale"})
    await ecrire_etage(moteur, tout_rouge, MAINTENANT)
    e0 = (await depot.etages())[0]
    rouge = (await depot.blocs_brut(e0.id))[1]
    g = await grimpeur(depot)
    await depot.cocher(g.id, ElementRef("bloc", rouge.id), True, 7, MAINTENANT, Regles())
    # Une quête devient secondaire : la ligne rouge reste (avec sa coche), la moitié jaune s'ajoute.
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    assert r.ajoutes == 1 and r.changements[0] == f"bloc « {INCARNAM} » (moitié secondaire) ajouté (secondaire)"
    blocs = await depot.blocs_brut(e0.id)
    assert blocs[1].id == rouge.id and blocs[1].moitie and blocs[2].partie == "secondaire"
    assert rouge.id in (await depot.coches_etage(e0.id))[g.id].blocs
    # Elle redevient principale : la moitié jaune, vide, est masquée (pas supprimée) ; démasquée si elle revient.
    r = await ecrire_etage(moteur, tout_rouge, MAINTENANT, forcer=True)  # 1 élément sur 8 : garde-fou des 10 %
    assert r.masques == 1 and r.changements[0] == f"bloc « {INCARNAM} » : plus de quête secondaire, moitié masquée"
    assert [b.masque for b in await depot.blocs_brut(e0.id)] == [False, False, True]
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    assert (r.ajoutes, r.demasques) == (0, 1)
    # Tout le bloc devient secondaire : la ligne de cette partie (déjà là) reprend, la rouge est masquée.
    tout_jaune = avec_natures(ETAGES[0], {q.duffus_id: "secondaire" for q in ETAGES[0].quetes if q.bloc == INCARNAM})
    await ecrire_etage(moteur, tout_jaune, MAINTENANT, forcer=True)
    assert [(b.partie, b.masque, b.moitie) for b in (await depot.blocs_brut(e0.id))[1:]] == [
        ("principale", True, False), ("secondaire", False, False)]


async def test_un_bloc_entier_qui_change_de_nature_garde_sa_ligne_et_ses_coches(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    tuto = (await depot.blocs_brut(e0.id))[0]
    g = await grimpeur(depot)
    await depot.cocher(g.id, ElementRef("bloc", tuto.id), True, 7, MAINTENANT, Regles())
    jaune = avec_natures(ETAGES[0], {q.duffus_id: "secondaire" for q in ETAGES[0].quetes if q.bloc == TUTORIEL})
    r = await ecrire_etage(moteur, jaune, MAINTENANT, forcer=True)
    assert r.ajoutes == 0 and f"bloc « {TUTORIEL} » : nature « principale » → « secondaire »" in r.changements
    b = (await depot.blocs_brut(e0.id))[0]
    assert (b.id, b.nature, b.partie) == (tuto.id, "secondaire", "secondaire")
    assert tuto.id in (await depot.coches_etage(e0.id))[g.id].blocs


async def test_bloc_retitre_par_duffus_reconnu_a_sa_position(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    avant = await depot.blocs_brut(e0.id)
    nouveau = "Incarnam, nouveau titre"
    quetes = [dataclasses.replace(q, bloc=nouveau) if q.bloc == INCARNAM else q for q in ETAGES[0].quetes]
    retitre = dataclasses.replace(ETAGES[0], quetes=quetes, blocs=k.blocs_depuis_quetes(quetes, {TUTORIEL: 1}))
    r = await ecrire_etage(moteur, retitre, MAINTENANT)
    assert r.ajoutes == 0 and r.changements.count(f"bloc « {INCARNAM} » retitré : « {nouveau} »") == 2
    assert [b.id for b in await depot.blocs_brut(e0.id)] == [b.id for b in avant]


# --- Corrections d'admin ----------------------------------------------------------------------------------------


async def test_correction_admin_d_un_bloc_entier(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    tuto = (await depot.blocs_brut(e0.id))[0]
    # Correction d'admin : motif obligatoire, journalisée, et elle survit à la reconstruction.
    with pytest.raises(ValueError):
        await depot.modifier_bloc(tuto.id, 1, MAINTENANT, nature="secondaire")
    b = await depot.modifier_bloc(tuto.id, 1, MAINTENANT, nature="secondaire", motif="pas utile")
    assert (b.nature, b.nature_origine, b.nature_motif, b.partie) == ("secondaire", "admin", "pas utile", "principale")
    assert (await depot.journal(type_="contenu_admin"))[0].details["motif"] == "pas utile"
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    assert r.changements == []
    assert (await depot.blocs_brut(e0.id))[0].nature == "secondaire"
    b = await depot.modifier_bloc(tuto.id, 1, MAINTENANT, nature="auto", motif="retour")
    assert (b.nature, b.nature_origine) == ("principale", "construction")
    # Coche d'un bloc : idempotente, et elle alimente le barème.
    g = await grimpeur(depot)
    ref = ElementRef("bloc", tuto.id)
    assert await depot.cocher(g.id, ref, True, 7, MAINTENANT, Regles()) == (ref,)
    assert await depot.cocher(g.id, ref, True, 7, MAINTENANT, Regles()) == ()
    assert (await depot.coches_etage(e0.id))[g.id].blocs == frozenset({tuto.id})
    assert (await depot.contenu_etage(e0.id)).blocs[0].id == tuto.id


async def test_la_nature_d_une_moitie_ne_se_regle_pas(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    _, rouge, jaune = await depot.blocs_brut(e0.id)
    with pytest.raises(ValueError, match="coupé en deux"):
        await depot.modifier_bloc(rouge.id, 1, MAINTENANT, nature="secondaire", motif="non")
    # Masquer une moitié reste possible : l'autre redevient un bloc entier, réglable.
    await depot.modifier_bloc(jaune.id, 1, MAINTENANT, masque=True)
    b = await depot.modifier_bloc(rouge.id, 1, MAINTENANT, nature="secondaire", motif="seul")
    assert (b.nature, b.moitie) == ("secondaire", False)


async def test_correction_d_un_bloc_entier_devenu_hybride_ne_s_applique_plus(depot, moteur):
    tout_rouge = avec_natures(ETAGES[0], {SECONDAIRE_INCARNAM: "principale"})
    await ecrire_etage(moteur, tout_rouge, MAINTENANT)
    e0 = (await depot.etages())[0]
    incarnam = (await depot.blocs_brut(e0.id))[1]
    await depot.modifier_bloc(incarnam.id, 1, MAINTENANT, nature="secondaire", motif="trop long")
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT, forcer=True)
    assert (f"bloc « {INCARNAM} » (moitié principale) : bloc coupé en deux, la correction d'admin « trop long » ne "
            "s'applique plus (corriger la nature des quêtes)") in r.changements
    rouge = (await depot.blocs_brut(e0.id))[1]
    assert (rouge.id, rouge.nature, rouge.nature_origine, rouge.nature_motif) == (
        incarnam.id, "principale", "construction", None)


async def test_changer_la_nature_d_une_quete_la_fait_changer_de_moitie_aussitot(depot, moteur):
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    tuto, rouge, jaune = await depot.blocs_brut(e0.id)
    c = await depot.contenu_etage(e0.id)
    fin = next(q for q in c.quetes if q.nom == "La fin du règne")
    # La seule quête secondaire d'Incarnam devient principale : elle rejoint la moitié rouge, la jaune (vide) est
    # masquée, Incarnam redevient un bloc entier.
    await depot.modifier_quete(fin.id, 1, MAINTENANT, nature="principale", motif="utile au Dofus")
    assert (await depot.journal(type_="contenu_admin"))[0].details["partie"] == "principale"
    blocs = await depot.blocs_brut(e0.id)
    assert [(b.id, b.masque, b.moitie, b.nb_quetes) for b in blocs[1:]] == [
        (rouge.id, False, False, 24), (jaune.id, True, False, 0)]
    # La reconstruction (qui reçoit les natures forcées par l'admin) retrouve exactement les mêmes lignes.
    r = await ecrire_etage(moteur, etage(0, forcees={SECONDAIRE_INCARNAM: "principale"}), MAINTENANT)
    assert (r.ajoutes, r.masques, r.demasques, r.changements) == (0, 0, 0, [])
    # Une quête du tutoriel devient secondaire : une moitié jaune est créée pour le tutoriel, qui devient hybride,
    # et la correction d'admin posée sur le tutoriel entier ne s'applique plus.
    await depot.modifier_bloc(tuto.id, 1, MAINTENANT, nature="secondaire", motif="bof")
    premiere = next(q for q in c.quetes if q.bloc == TUTORIEL)
    await depot.modifier_quete(premiere.id, 1, MAINTENANT, nature="secondaire", motif="facultative")
    blocs = await depot.blocs_brut(e0.id)
    nouveau = next(b for b in blocs if b.titre == TUTORIEL and b.partie == "secondaire")
    assert (nouveau.numero, nouveau.ordre, nouveau.moitie, nouveau.nb_quetes) == (1, 1, True, 1)
    assert (blocs[0].nature, blocs[0].nature_origine, blocs[0].moitie) == ("principale", "construction", True)
    # La quête revient (la moitié jaune du tutoriel, vide, est masquée), puis repart (elle est démasquée).
    await depot.modifier_quete(premiere.id, 1, MAINTENANT, nature="principale", motif="non")
    assert next(b for b in await depot.blocs_brut(e0.id) if b.id == nouveau.id).masque
    await depot.modifier_quete(premiere.id, 1, MAINTENANT, nature="secondaire", motif="si")
    assert not next(b for b in await depot.blocs_brut(e0.id) if b.id == nouveau.id).masque
    # Une quête déjà dans la partie de sa nature, ou seulement renommée, ne bouge pas.
    await depot.modifier_quete(premiere.id, 1, MAINTENANT, nature="secondaire", motif="même")
    await depot.modifier_quete(premiere.id, 1, MAINTENANT, nom="Renommée")
    assert len(await depot.blocs_brut(e0.id)) == 4


async def test_quete_sans_bloc_changee_de_nature(depot, moteur):
    """Une quête sans rattachement (données d'avant les blocs) change de nature sans rien déplacer."""
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    q = (await depot.contenu_etage(e0.id)).quetes[0]
    async with moteur.begin() as c:
        await c.execute(update(t.quete).where(t.quete.c.id == q.id).values(bloc_id=None))
    assert (await depot.modifier_quete(q.id, 1, MAINTENANT, nature="secondaire", motif="x")).bloc_id is None
    assert len(await depot.blocs_brut(e0.id)) == 3


# --- Migration h1 -----------------------------------------------------------------------------------------------


async def test_migration_coupe_les_hybrides_et_se_defait(depot, moteur):
    """Retour à g3 (moitiés recollées), puis h1 : les hybrides déjà en base sont coupés, les coches restent, et une
    correction d'admin posée sur un hybride est levée."""
    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    tuto, rouge, _ = await depot.blocs_brut(e0.id)
    g = await grimpeur(depot)
    await depot.cocher(g.id, ElementRef("bloc", rouge.id), True, 7, MAINTENANT, Regles())
    await moteur.dispose()  # aucune connexion du pool ne garde un plan préparé sur l'ancien schéma
    try:
        assert alembic("downgrade", "g3_annonce_lancement").returncode == 0
        async with moteur.begin() as c:
            lignes = (await c.execute(text("SELECT id, titre, nature FROM epreuve.bloc ORDER BY id"))).all()
            assert [tuple(x) for x in lignes] == [(tuto.id, TUTORIEL, "principale"),
                                                  (rouge.id, INCARNAM, "principale")]
            assert (await c.execute(text("SELECT count(*) FROM epreuve.quete WHERE bloc_id = :b"),
                                    {"b": rouge.id})).scalar() == 24
            await c.execute(text("UPDATE epreuve.bloc SET nature = 'secondaire', nature_origine = 'admin', "
                                 "nature_motif = 'trop long' WHERE id = :b"), {"b": rouge.id})
    finally:
        await moteur.dispose()
        assert alembic("upgrade", "head").returncode == 0
    blocs = await depot.blocs_brut(e0.id)
    assert [(b.id, b.titre, b.partie, b.nature, b.nature_origine, b.nb_quetes) for b in blocs[:2]] == [
        (tuto.id, TUTORIEL, "principale", "principale", "construction", 3),
        (rouge.id, INCARNAM, "principale", "principale", "construction", 23)]
    assert (blocs[2].titre, blocs[2].partie, blocs[2].nb_quetes, blocs[2].moitie) == (INCARNAM, "secondaire", 1, True)
    assert (await depot.coches_etage(e0.id))[g.id].blocs == {rouge.id}
    # La reconstruction retrouve les lignes de la migration.
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    assert (r.ajoutes, r.masques, r.changements) == (0, 0, [])
