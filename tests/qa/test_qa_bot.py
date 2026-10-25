"""QA, commandes du bot : permissions avec Discord simulé, entrées absurdes, concurrence.

Les tests qui prennent la fixture `etage0` tournent contre le Postgres de test (marqueur db).
Attendus tirés de docs/SPEC.md (§5.4, §6, §7) et de docs/LOTS.md (critères du jalon bêta).
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import discord
import pytest

from epreuve.bot.acces import REPONSE_REFUS
from epreuve.bot.client import BotEpreuve
from epreuve.bot.cmd_grimpeur import grimpeur_ajouter, grimpeur_inclure, grimpeur_modifier, grimpeur_reprendre
from epreuve.bot.cmd_joueur import declarer_quetes
from epreuve.bot.cmd_validation import AConfirmer, ConfirmationDepassement, DemandeValidation, annuler, valider
from epreuve.bot.commun import Contexte
from epreuve.web.app import construire_etat
from tests.fabrique import AVANT, PENDANT

GUILD, ROLE_ADMIN, ADMIN, JOUEUR = 1000, 2000, 111, 555
PARIS = ZoneInfo("Europe/Paris")


# --- Discord simulé ------------------------------------------------------------------------------


class DepotInterdit:
    def __getattr__(self, nom):
        raise AssertionError(f"le dépôt ne devait pas être utilisé ({nom})")


def membre(roles=(), gerer=False, id_=7):
    return SimpleNamespace(
        id=id_, roles=[SimpleNamespace(id=r) for r in roles], guild_permissions=SimpleNamespace(manage_guild=gerer)
    )


def interaction(user):
    return SimpleNamespace(
        user=user,
        guild_id=GUILD,
        command=SimpleNamespace(qualified_name="qa"),
        namespace=SimpleNamespace(),
        response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()),
    )


def commandes(depot=None):
    b = BotEpreuve(depot or DepotInterdit(), GUILD, ROLE_ADMIN, "Europe/Paris")
    return {c.name: c for c in b.tree.get_commands(guild=discord.Object(id=GUILD))}


async def appeler(cmd, inter, **kw):
    if cmd.binding is not None:
        await cmd.callback(cmd.binding, inter, **kw)
    else:
        await cmd.callback(inter, **kw)


async def test_utilisateur_hors_serveur_ne_peut_pas_valider():
    """Un discord.User (sans rôles ni permissions) est refusé, rien n'est lu."""
    inter = interaction(SimpleNamespace(id=7))
    await appeler(commandes()["valider"], inter, contenu="1", grimpeur1="X", niveau1=20)
    inter.response.send_message.assert_awaited_once_with(REPONSE_REFUS, ephemeral=True)


async def test_bouton_accepter_par_un_admin_qui_a_perdu_le_role():
    """Le bouton « Accepter malgré le dépassement » revérifie l'accès (rien n'est écrit)."""
    outil = SimpleNamespace(admin_role_id=ROLE_ADMIN, depot=DepotInterdit(), guild_id=GUILD, fuseau="Europe/Paris")
    vue = ConfirmationDepassement(outil, 7, DemandeValidation("1", [("X", 21)]))
    inter = interaction(membre(roles=[123], id_=7))
    await vue.accepter.callback(inter)
    inter.response.send_message.assert_awaited_once_with(REPONSE_REFUS, ephemeral=True)


async def test_bouton_par_un_autre_admin_refuse():
    outil = SimpleNamespace(admin_role_id=ROLE_ADMIN)
    vue = ConfirmationDepassement(outil, 7, DemandeValidation("1", [("X", 21)]))
    inter = interaction(membre(roles=[ROLE_ADMIN], id_=8))
    assert not await vue.interaction_check(inter)


async def test_valider_niveau_zero_au_niveau_discord_est_signale():
    """niveau1=0 (si la borne Discord sautait) : message clair, rien n'est lu."""
    inter = interaction(membre(roles=[ROLE_ADMIN]))
    await appeler(commandes()["valider"], inter, contenu="1", grimpeur1="X", niveau1=0)
    assert "Rien n'a été enregistré" in inter.response.send_message.await_args.args[0]


# --- Avec la base ---------------------------------------------------------------------------------


def ctx(depot, quand=PENDANT, acteur=ADMIN):
    return Contexte(depot, acteur, quand, GUILD, PARIS)


async def inscrire(depot, *pseudos, difficulte="easy", quand=AVANT, membre_id=None):
    for p in pseudos:
        rep = await grimpeur_ajouter(ctx(depot, quand), p, "Iop", difficulte, membre_id)
        assert "est inscrit" in rep.texte, rep.texte


async def g(depot, pseudo):
    return await depot.grimpeur_par_pseudo(pseudo)


async def etat_site(depot, quand=PENDANT):
    return construire_etat(await depot.charger_instantane(), quand, PARIS)


async def test_entrees_absurdes_de_valider(etage0):
    await inscrire(etage0, "Brindille")
    cas = {
        "pseudo inconnu": (DemandeValidation("1", [("Personne", 20)]), "grimpeur inconnu"),
        "niveau négatif": (DemandeValidation("1", [("Brindille", -3)]), "impossible"),
        "niveau 999": (DemandeValidation("1", [("Brindille", 999)]), "impossible"),
        "niveau 0": (DemandeValidation("1", [("Brindille", 0)]), "impossible"),
        "contenu inconnu": (DemandeValidation("Bouftou royal", [("Brindille", 20)]), "inconnu"),
        "contenu id absent": (DemandeValidation("424242", [("Brindille", 20)]), "inconnu"),
        "deux fois le même, casse différente": (
            DemandeValidation("1", [("Brindille", 20), ("BRINDILLE", 20)]),
            "deux fois",
        ),
        "aucun grimpeur": (DemandeValidation("1", []), "au moins un grimpeur"),
        "lien de preuve bidon": (DemandeValidation("1", [("Brindille", 20)], "https://evil.example/x"), "invalide"),
    }
    for nom, (demande, attendu) in cas.items():
        rep = await valider(ctx(etage0), demande)
        assert not isinstance(rep, AConfirmer), nom
        assert rep.texte.startswith("Rien n'a été enregistré") and attendu in rep.texte, (nom, rep.texte)
    assert await etage0.validations() == []


async def test_double_validation_puis_annulation_inexistante(etage0):
    await inscrire(etage0, "Brindille")
    assert (await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)]))).texte.startswith("✅")
    rep = await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)]))
    assert "déjà validé le" in rep.texte
    for vid in (0, -1, 999):
        assert (await annuler(ctx(etage0), vid, "erreur")).texte.startswith("Rien n'a été annulé")
    assert (await annuler(ctx(etage0), 1, "   ")).texte.startswith("Rien n'a été annulé")
    assert (await annuler(ctx(etage0), 1, "erreur")).texte.startswith("Validation n° 1 annulée")
    assert (await annuler(ctx(etage0), 1, "encore")).texte.startswith("Rien n'a été annulé")


@pytest.mark.xfail(
    strict=True,
    raises=Exception,
    reason=(
        "Bug : /annuler avec un numéro hors de l'entier Postgres (option Discord `int` jusqu'à 2^53) "
        "fait planter la commande (DataError asyncpg) au lieu de répondre « Rien n'a été annulé »."
    ),
)
async def test_annuler_numero_enorme(etage0):
    rep = await annuler(ctx(etage0), 10**12, "erreur")
    assert rep.texte.startswith("Rien n'a été annulé")


async def test_modifier_niveau_absurde(etage0):
    await inscrire(etage0, "Brindille")
    for n in (0, -5, 201, 999):
        assert "entre 1 et 200" in (await grimpeur_modifier(ctx(etage0), "Brindille", niveau=n)).texte
    assert (await g(etage0, "Brindille")).niveau_connu is None
    assert "Aucun grimpeur" in (await grimpeur_modifier(ctx(etage0), "Personne", niveau=10)).texte


async def test_pseudo_que_des_espaces_refuse(etage0):
    rep = await grimpeur_ajouter(ctx(etage0, AVANT), "     ", "Iop", "easy")
    assert rep.texte.startswith("Rien n'a été enregistré")


async def test_inclure_un_compte_ou_un_inconnu(etage0):
    await inscrire(etage0, "Brindille")
    assert "n'est pas retardataire" in (await grimpeur_inclure(ctx(etage0), "Brindille")).texte
    assert "Aucun grimpeur" in (await grimpeur_inclure(ctx(etage0), "Fantome")).texte


async def test_quetes_par_un_joueur_exclu_ou_en_pause(etage0):
    await inscrire(etage0, "Brindille", membre_id=JOUEUR)
    from epreuve.bot.cmd_grimpeur import grimpeur_pause

    await grimpeur_pause(ctx(etage0), "Brindille")
    rep = await declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes")
    assert rep.texte.startswith("Rien n'a été enregistré") and "pause" in rep.texte


# --- Retardataires et niveau plancher (§5.4) -----------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bug : l'inclusion automatique n'est réévaluée que quand le niveau DU retardataire change. "
        "Quand le plancher BAISSE (premier niveau connu d'un compté, inclusion forcée d'un bas niveau), "
        "un retardataire qui a déjà rattrapé reste hors de la jauge. SPEC §5.4 : « il devient compté dès que »."
    ),
)
async def test_retardataire_inclus_quand_le_plancher_baisse(etage0):
    await inscrire(etage0, "Ancien")  # compté, niveau inconnu → plancher = cap 20
    await inscrire(etage0, "Tardif", quand=PENDANT)  # retardataire
    await grimpeur_modifier(ctx(etage0), "Tardif", niveau=15)
    assert (await g(etage0, "Tardif")).inclus_le is None  # 15 < 20 : normal
    # Le compté valide le donjon au niveau 12 : le moins avancé du groupe est maintenant à 12.
    await valider(ctx(etage0), DemandeValidation("1", [("Ancien", 12)]))
    assert (await g(etage0, "Tardif")).inclus_le is not None  # 15 ≥ 12 : il a rattrapé


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bug : dans un même /valider, l'inclusion d'un retardataire dépend de l'ordre des grimpeurs "
        "(depot.creer_validations, boucle de mise à jour des niveaux)."
    ),
)
async def test_inclusion_independante_de_l_ordre_dans_valider(etage0):
    await inscrire(etage0, "Ancien")
    await inscrire(etage0, "Tardif", quand=PENDANT)
    # Tardif cité en premier : quand son niveau est mis à jour, Ancien n'a pas encore de niveau (plancher 20).
    rep = await valider(ctx(etage0), DemandeValidation("1", [("Tardif", 15), ("Ancien", 12)]))
    assert rep.texte.startswith("✅")
    assert (await g(etage0, "Tardif")).inclus_le is not None


async def test_meme_scenario_dans_l_autre_ordre_inclut(etage0):
    """Témoin du test précédent : dans l'autre ordre, le retardataire est bien inclus."""
    await inscrire(etage0, "Ancien")
    await inscrire(etage0, "Tardif", quand=PENDANT)
    await valider(ctx(etage0), DemandeValidation("1", [("Ancien", 12), ("Tardif", 15)]))
    assert (await g(etage0, "Tardif")).inclus_le is not None


async def test_reprise_apres_pause_retardataire_puis_rattrapage(etage0):
    await inscrire(etage0, "Aa", "Bb")
    await grimpeur_modifier(ctx(etage0), "Aa", niveau=18)
    await grimpeur_modifier(ctx(etage0), "Bb", niveau=10)
    from epreuve.bot.cmd_grimpeur import grimpeur_pause

    await grimpeur_pause(ctx(etage0), "Bb")
    rep = await grimpeur_reprendre(ctx(etage0), "Bb")  # 10 < plancher 18
    assert "retardataire" in rep.texte and (await g(etage0, "Bb")).inclus_le is None
    j = (await etat_site(etage0))["etage_courant"]
    assert (j["jauge"]["maximum"], j["n_retardataires"]) == (1, 1)
    await grimpeur_modifier(ctx(etage0), "Bb", niveau=18)
    assert (await g(etage0, "Bb")).inclus_le is not None


async def test_reprise_d_un_exclu_redevient_retardataire(etage0):
    await inscrire(etage0, "Aa", "Bb")
    await grimpeur_modifier(ctx(etage0), "Aa", niveau=20)
    from epreuve.bot.cmd_grimpeur import grimpeur_exclure

    await grimpeur_exclure(ctx(etage0), "Bb", "test")
    await grimpeur_reprendre(ctx(etage0), "Bb")
    assert (await g(etage0, "Bb")).inclus_le is None


async def test_inclusion_forcee_fait_monter_le_maximum(etage0):
    await inscrire(etage0, "Aa")
    await inscrire(etage0, "Tt", difficulte="hard", quand=PENDANT)
    rep = await grimpeur_inclure(ctx(etage0), "Tt", "ami de Shadoaze")
    assert "Maximum 1 → 4" in rep.texte
    t = await g(etage0, "Tt")
    assert t.inclus_le is not None and t.inclusion_forcee


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bug : /annuler ne recalcule pas le niveau connu. SPEC §6 : le niveau connu vaut le plus haut "
        "niveau parmi les validations ACCEPTÉES. Après annulation d'une validation à 21 (forcée par erreur), "
        "la carte reste « Dépasse le cap »."
    ),
)
async def test_annulation_recalcule_le_niveau_connu(etage0):
    await inscrire(etage0, "Brindille")
    await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 18)]))
    await valider(ctx(etage0), DemandeValidation("2", [("Brindille", 21)]), accepter_depassement=True)
    v21 = next(v for v in await etage0.validations() if v.niveau == 21)
    await annuler(ctx(etage0), v21.id, "saisie erronée")
    assert (await g(etage0, "Brindille")).niveau_connu == 18
    carte = next(x for x in (await etat_site(etage0))["grimpeurs"] if x["pseudo"] == "Brindille")
    assert carte["au_dessus_du_cap"] is False


# --- Concurrence ----------------------------------------------------------------------------------


async def test_deux_quetes_toutes_simultanees(etage0):
    await inscrire(etage0, "Brindille", membre_id=JOUEUR)
    r1, r2 = await asyncio.gather(
        declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes"), declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes")
    )
    assert sum(r.texte.startswith("✅") for r in (r1, r2)) == 1
    assert sum(v.statut == "acceptee" for v in await etage0.validations()) == 1


async def test_deux_annulations_simultanees(etage0):
    await inscrire(etage0, "Brindille")
    await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)]))
    r1, r2 = await asyncio.gather(annuler(ctx(etage0), 1, "a"), annuler(ctx(etage0, acteur=222), 1, "b"))
    assert sorted(r.texte.startswith("Validation") for r in (r1, r2)) == [False, True]
    annulations = [e for e in await etage0.journal() if e.type == "annulation"]
    assert len(annulations) == 1


async def test_deux_inscriptions_simultanees_meme_pseudo(etage0):
    r1, r2 = await asyncio.gather(
        grimpeur_ajouter(ctx(etage0, AVANT), "Brindille", "Iop", "easy"),
        grimpeur_ajouter(ctx(etage0, AVANT, 222), "brindille", "Crâ", "hard"),
    )
    assert sum("est inscrit" in r.texte for r in (r1, r2)) == 1
    assert len(await etage0.grimpeurs()) == 1


async def test_validation_simultanee_de_groupes_qui_se_recoupent(etage0):
    await inscrire(etage0, "Aa", "Bb", "Cc")
    d1 = DemandeValidation("1", [("Aa", 20), ("Bb", 20)])
    d2 = DemandeValidation("1", [("Bb", 20), ("Cc", 20)])
    r1, r2 = await asyncio.gather(valider(ctx(etage0), d1), valider(ctx(etage0, acteur=222), d2))
    acceptees = [v for v in await etage0.validations() if v.statut == "acceptee"]
    id_b = (await g(etage0, "Bb")).id
    # Tout ou rien : un seul des deux groupes passe, B n'a qu'une validation.
    assert sum(v.grimpeur_id == id_b for v in acceptees) == 1
    assert len(acceptees) == 2
    assert sum(r.texte.startswith("✅") for r in (r1, r2)) == 1
