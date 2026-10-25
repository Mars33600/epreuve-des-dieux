"""Migration, contraintes et dépôt, contre un vrai Postgres (marqueur db)."""

import asyncio
import os
import subprocess
import sys
from datetime import timedelta

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError

from epreuve.db import tables as t
from epreuve.db.depot import (
    DejaValide,
    ErreurDepot,
    Introuvable,
    MembreDejaRelie,
    PreuveDiscord,
    PseudoDejaPris,
)
from epreuve.db.session import creer_moteur
from epreuve.domaine.modeles import Grimpeur, Validation
from tests.conftest import RACINE
from tests.fabrique import AVANT, OUVERTURE, PENDANT

ADMIN = 111


async def test_migration_appliquee_puis_defaite_sur_base_vide(url_base):
    admin = creer_moteur(url_base)
    async with admin.connect() as c:
        await c.execution_options(isolation_level="AUTOCOMMIT")
        await c.execute(text("DROP DATABASE IF EXISTS epreuve_migration"))
        await c.execute(text("CREATE DATABASE epreuve_migration"))
    url = url_base.rsplit("/", 1)[0] + "/epreuve_migration"
    env = {**os.environ, "DATABASE_URL": url}

    def alembic(*args):
        r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=RACINE, env=env,
                           capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stderr

    async def tables():
        m = creer_moteur(url)
        async with m.connect() as c:
            res = await c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'epreuve'"))
            noms = {r[0] for r in res}
        await m.dispose()
        return noms

    alembic("upgrade", "head")
    assert await tables() == {"etage", "palier", "contenu", "palier_contenu", "grimpeur", "preuve", "validation",
                              "journal", "alembic_version"}
    alembic("downgrade", "base")
    assert await tables() == {"alembic_version"}
    alembic("upgrade", "head")  # et elle se réapplique
    async with admin.connect() as c:
        await c.execution_options(isolation_level="AUTOCOMMIT")
        await c.execute(text("DROP DATABASE epreuve_migration WITH (FORCE)"))
    await admin.dispose()


async def test_rls_activee(moteur):
    async with moteur.connect() as c:
        res = await c.execute(text(
            "SELECT relname FROM pg_class WHERE relnamespace = 'epreuve'::regnamespace "
            "AND relkind = 'r' AND relrowsecurity"))
        assert {"grimpeur", "validation", "journal", "palier"} <= {r[0] for r in res}


async def _refuse(moteur, table, **valeurs):
    with pytest.raises(IntegrityError):
        async with moteur.begin() as c:
            await c.execute(insert(table).values(**valeurs))


async def test_contraintes_check(etage0, moteur):
    await _refuse(moteur, t.grimpeur, pseudo_ig="Paladine", classe="Paladin", difficulte="easy", inscrit_le=PENDANT)
    await _refuse(moteur, t.palier, etage_id=1, rang=4, libelle="Quatrième")
    await _refuse(moteur, t.etage, numero=5, nom="X", level_cap=50, seuil_pourcent=0)
    g = await etage0.ajouter_grimpeur("Brindille", "Eniripsa", "hard", None, ADMIN, AVANT)
    commun = dict(grimpeur_id=g.id, contenu_id=1, statut="acceptee", decidee_par=ADMIN, decidee_le=PENDANT,
                  realisee_le=PENDANT)
    await _refuse(moteur, t.validation, niveau=None, source="manuelle", **commun)  # niveau vide hors déclaration
    async with moteur.begin() as c:  # une déclaration sans niveau passe
        await c.execute(insert(t.validation).values(niveau=None, source="declaration", **commun))


async def test_pseudo_unique_sans_la_casse_et_membre_unique(depot):
    await depot.ajouter_grimpeur("Mirelune", "Crâ", "med", 42, ADMIN, AVANT)
    with pytest.raises(PseudoDejaPris):
        await depot.ajouter_grimpeur("MIRELUNE", "Iop", "easy", None, ADMIN, AVANT)
    with pytest.raises(MembreDejaRelie):
        await depot.ajouter_grimpeur("Autre", "Iop", "easy", 42, ADMIN, AVANT)
    assert (await depot.grimpeur_par_discord(42)).pseudo == "Mirelune"
    assert await depot.grimpeur_par_discord(43) is None


async def test_le_depot_renvoie_des_objets_du_domaine(etage0):
    g = await etage0.ajouter_grimpeur("Brindille", "Eniripsa", "hard", None, ADMIN, AVANT)
    assert isinstance(g, Grimpeur) and g.statut == "actif" and g.inclus_le == AVANT
    etage = await etage0.etage_ouvert()
    k = (await etage0.contenus(etage.id))[0]
    await etage0.creer_validations(etage, k, [(g, 20, False)], PENDANT, None, ADMIN, PENDANT)
    (v,) = await etage0.validations()
    assert isinstance(v, Validation) and v.statut == "acceptee" and v.source == "manuelle"
    assert v.realisee_le == PENDANT and v.realisee_le.tzinfo is not None
    inst = await etage0.charger_instantane()
    assert inst.etage_ouvert == etage and len(inst.paliers) == 3 and len(inst.contenus) == 6
    assert (await etage0.grimpeur_par_pseudo("brindille")).niveau_connu == 20


async def test_inscription_apres_l_ouverture_retardataire(etage0):
    avant = await etage0.ajouter_grimpeur("Tot", "Iop", "easy", None, ADMIN, OUVERTURE - timedelta(seconds=1))
    apres = await etage0.ajouter_grimpeur("Tard", "Iop", "easy", None, ADMIN, OUVERTURE)
    assert avant.inclus_le is not None and apres.inclus_le is None
    assert [g.pseudo for g in await etage0.grimpeurs("retardataire")] == ["Tard"]


async def test_inclusion_automatique_sur_mise_a_jour_de_niveau(etage0):
    g = await etage0.ajouter_grimpeur("Tard", "Iop", "easy", None, ADMIN, PENDANT)
    _, changements = await etage0.modifier_grimpeur(g.id, ADMIN, PENDANT, niveau=19)
    assert "inclus" not in changements
    nouveau, changements = await etage0.modifier_grimpeur(g.id, ADMIN, PENDANT, niveau=20)
    assert changements["inclus"] == [False, True] and nouveau.inclus_le == PENDANT
    inclusion = [e for e in await etage0.journal() if e.type == "inclusion"]
    assert len(inclusion) == 1 and inclusion[0].details["raison"] == "rattrapage"
    assert inclusion[0].details["niveau_plancher"] == 20  # aucun compté n'a de niveau : le cap


async def test_inclusion_au_niveau_du_moins_avance(etage0):
    await etage0.ajouter_grimpeur("Ancien", "Iop", "easy", None, ADMIN, AVANT)
    ancien = await etage0.grimpeur_par_pseudo("Ancien")
    await etage0.modifier_grimpeur(ancien.id, ADMIN, AVANT, niveau=14)
    g = await etage0.ajouter_grimpeur("Tard", "Iop", "easy", None, ADMIN, PENDANT)
    _, changements = await etage0.modifier_grimpeur(g.id, ADMIN, PENDANT, niveau=14)
    assert changements["inclus"] == [False, True]


async def test_retour_de_pause_retardataire(etage0):
    await etage0.ajouter_grimpeur("Ancien", "Iop", "easy", None, ADMIN, AVANT)
    await etage0.ajouter_grimpeur("Dormeur", "Iop", "easy", None, ADMIN, AVANT)
    ancien, dormeur = await etage0.grimpeur_par_pseudo("Ancien"), await etage0.grimpeur_par_pseudo("Dormeur")
    await etage0.modifier_grimpeur(ancien.id, ADMIN, AVANT, niveau=18)
    await etage0.changer_statut(dormeur.id, "pause", None, "pause", ADMIN, PENDANT)
    repris = await etage0.changer_statut(dormeur.id, "actif", None, "reprise", ADMIN, PENDANT)
    assert repris.inclus_le is None  # niveau inconnu : il redevient retardataire
    await etage0.modifier_grimpeur(dormeur.id, ADMIN, PENDANT, niveau=18)
    assert (await etage0.grimpeur_par_pseudo("Dormeur")).inclus_le is not None
    # Déjà au niveau du groupe : la reprise le réinclut tout de suite.
    await etage0.changer_statut(dormeur.id, "pause", None, "pause", ADMIN, PENDANT)
    repris = await etage0.changer_statut(dormeur.id, "actif", None, "reprise", ADMIN, PENDANT)
    assert repris.inclus_le == PENDANT


async def test_inclusion_automatique_par_une_validation(etage0):
    g = await etage0.ajouter_grimpeur("Tard", "Iop", "easy", None, ADMIN, PENDANT)
    etage = await etage0.etage_ouvert()
    k = (await etage0.contenus(etage.id))[0]
    await etage0.creer_validations(etage, k, [(g, 20, False)], PENDANT, None, ADMIN, PENDANT)
    assert (await etage0.grimpeur_par_pseudo("Tard")).inclus_le is not None


async def test_inclure_a_la_main(etage0):
    g = await etage0.ajouter_grimpeur("Tard", "Iop", "easy", None, ADMIN, PENDANT)
    inclus = await etage0.inclure(g.id, "il joue avec nous depuis le début", ADMIN, PENDANT)
    assert inclus.inclus_le == PENDANT and inclus.inclusion_forcee
    with pytest.raises(ErreurDepot, match="pas retardataire"):
        await etage0.inclure(g.id, None, ADMIN, PENDANT)
    with pytest.raises(Introuvable):
        await etage0.inclure(999, None, ADMIN, PENDANT)


async def _deux_grimpeurs(depot):
    g1 = await depot.ajouter_grimpeur("Kaskarot", "Iop", "easy", None, ADMIN, AVANT)
    g2 = await depot.ajouter_grimpeur("Gromolo", "Pandawa", "easy", None, ADMIN, AVANT)
    etage = await depot.etage_ouvert()
    kardorim = (await depot.contenus(etage.id))[0]
    return g1, g2, etage, kardorim


async def test_index_bloque_une_deuxieme_validation_acceptee(etage0, moteur):
    g1, _, etage, k = await _deux_grimpeurs(etage0)
    await etage0.creer_validations(etage, k, [(g1, 20, False)], PENDANT, None, ADMIN, PENDANT)
    await _refuse(moteur, t.validation, grimpeur_id=g1.id, contenu_id=k.id, niveau=20, statut="acceptee",
                  decidee_par=ADMIN, decidee_le=PENDANT, realisee_le=PENDANT)


async def test_tout_ou_rien_en_base(etage0):
    g1, g2, etage, k = await _deux_grimpeurs(etage0)
    await etage0.creer_validations(etage, k, [(g2, 20, False)], PENDANT, None, ADMIN, PENDANT)
    with pytest.raises(DejaValide):
        await etage0.creer_validations(etage, k, [(g1, 20, False), (g2, 20, False)], PENDANT, None, ADMIN, PENDANT)
    assert len(await etage0.validations()) == 1
    assert len(await etage0.journal(public=True)) == 1


async def test_annulee_puis_reacceptee(etage0):
    g1, _, etage, k = await _deux_grimpeurs(etage0)
    (vid,) = await etage0.creer_validations(etage, k, [(g1, 20, False)], PENDANT, None, ADMIN, PENDANT)
    await etage0.annuler_validation(vid, "erreur de saisie", ADMIN, PENDANT)
    with pytest.raises(Introuvable):
        await etage0.annuler_validation(vid, "deux fois", ADMIN, PENDANT)
    await etage0.creer_validations(etage, k, [(g1, 20, False)], PENDANT, None, ADMIN, PENDANT)
    assert sorted(v.statut for v in await etage0.validations()) == ["acceptee", "annulee"]


async def test_deux_ecritures_simultanees_une_seule_acceptee(etage0):
    g1, _, etage, k = await _deux_grimpeurs(etage0)

    async def ecrire():
        return await etage0.creer_validations(etage, k, [(g1, 20, False)], PENDANT, None, ADMIN, PENDANT)

    resultats = await asyncio.gather(ecrire(), ecrire(), return_exceptions=True)
    assert sum(isinstance(r, list) for r in resultats) == 1
    assert sum(isinstance(r, DejaValide) for r in resultats) == 1
    assert len(await etage0.validations()) == 1


async def test_depassement_accepte_au_journal(etage0):
    g1, _, etage, k = await _deux_grimpeurs(etage0)
    await etage0.creer_validations(etage, k, [(g1, 21, True)], PENDANT, None, ADMIN, PENDANT)
    (v,) = await etage0.validations()
    assert v.forcee and v.niveau == 21
    (entree,) = [e for e in await etage0.journal() if e.type == "depassement_accepte"]
    assert not entree.public and entree.details["cap"] == 20


async def test_declarer_et_doublon(etage0):
    g1, _, etage, _ = await _deux_grimpeurs(etage0)
    lot = (await etage0.contenus(etage.id))[5]
    (vid,) = await etage0.declarer(etage, [lot], g1, None, g1.id, PENDANT)
    (v,) = await etage0.validations()
    assert (v.id, v.niveau, v.source, v.realisee_le) == (vid, None, "declaration", PENDANT)
    with pytest.raises(DejaValide):
        await etage0.declarer(etage, [lot], g1, None, g1.id, PENDANT)
    (entree,) = await etage0.journal(public=True)
    assert entree.type == "declaration"
    assert entree.details["validations"][0]["contenu"] == "Toutes les quêtes d'Incarnam"


async def test_modifier_et_journal(etage0):
    g, _, _, _ = await _deux_grimpeurs(etage0)
    nouveau, changements = await etage0.modifier_grimpeur(g.id, ADMIN, PENDANT, difficulte="hard", niveau=18,
                                                          discord_user_id=99, classe="Sram")
    assert nouveau.difficulte == "hard" and nouveau.niveau_connu == 18
    assert changements["difficulte"] == ["easy", "hard"]
    assert changements["discord_user_id"] == ["…", "relié"]  # jamais l'id en clair au journal
    assert await etage0.modifier_grimpeur(g.id, ADMIN, PENDANT, difficulte="hard") == (nouveau, {})
    assert {"difficulte", "niveau", "modification"} <= {e.type for e in await etage0.journal()}
    with pytest.raises(Introuvable):
        await etage0.modifier_grimpeur(999, ADMIN, PENDANT, classe="Iop")
    with pytest.raises(Introuvable):
        await etage0.changer_statut(999, "pause", None, "pause", ADMIN, PENDANT)


async def test_derniere_activite(etage0):
    g1, g2, etage, k = await _deux_grimpeurs(etage0)
    assert await etage0.derniere_activite(g1.id) is None
    await etage0.creer_validations(etage, k, [(g1, 20, False), (g2, 20, False)], PENDANT, None, ADMIN, PENDANT)
    plus_tard = PENDANT + timedelta(days=1)
    await etage0.modifier_grimpeur(g2.id, ADMIN, plus_tard, niveau=21)
    await etage0.changer_statut(g1.id, "pause", None, "pause", ADMIN, plus_tard)  # pas une activité
    assert await etage0.dernieres_activites() == {g1.id: PENDANT, g2.id: plus_tard}


async def test_ping(depot):
    assert await depot.ping()
    hors_service = type(depot)(creer_moteur("postgresql+asyncpg://x:y@127.0.0.1:1/rien"))
    assert not await hors_service.ping()


async def test_preuve_reutilisee_et_visible(etage0):
    g1, _, etage, k = await _deux_grimpeurs(etage0)
    p = PreuveDiscord(1, 2, 3, "https://discord.com/channels/1/2/3", OUVERTURE + timedelta(hours=1))
    contenus = await etage0.contenus(etage.id)
    await etage0.creer_validations(etage, k, [(g1, 20, False)], p.poste_le, p, ADMIN, PENDANT)
    await etage0.creer_validations(etage, contenus[1], [(g1, 20, False)], p.poste_le, p, ADMIN, PENDANT)
    async with etage0._moteur.connect() as c:
        assert (await c.execute(text("SELECT count(*) FROM epreuve.preuve"))).scalar() == 1
    lignes = await etage0.validations_du_grimpeur(g1.id)
    assert [lv.preuve for lv in lignes] == [p.lien, p.lien]
