"""Bot sans base : contrôle d'accès, verrou de serveur, autocomplétion, liens de preuve.

On utilise de faux objets Discord (SimpleNamespace et AsyncMock) : aucun réseau.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from epreuve.bot.acces import REPONSE_REFUS, est_admin
from epreuve.bot.client import ArbreVerrouille, BotEpreuve
from epreuve.bot.cmd_validation import date_du_snowflake, lire_preuve, trouver_contenu
from epreuve.bot.commun import Reponse, normaliser, suggestions, tronquer
from tests.fabrique import CONTENUS

GUILD, ROLE_ADMIN = 1000, 2000


def membre(roles=(), gerer=False, id_=7):
    return SimpleNamespace(id=id_, roles=[SimpleNamespace(id=r) for r in roles],
                           guild_permissions=SimpleNamespace(manage_guild=gerer))


def interaction(user, guild_id=GUILD):
    return SimpleNamespace(user=user, guild_id=guild_id, command=SimpleNamespace(qualified_name="test"),
                           response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()))


class DepotInterdit:
    """Un faux dépôt qui échoue à la moindre utilisation : prouve que rien n'est lu ni écrit."""

    def __getattr__(self, nom):
        raise AssertionError(f"le dépôt ne devait pas être utilisé ({nom})")


def test_est_admin():
    assert est_admin(membre(roles=[ROLE_ADMIN]), ROLE_ADMIN)
    assert est_admin(membre(gerer=True), ROLE_ADMIN)
    assert not est_admin(membre(roles=[123]), ROLE_ADMIN)
    assert not est_admin(SimpleNamespace(id=1), ROLE_ADMIN)  # un User hors serveur


def bot():
    return BotEpreuve(DepotInterdit(), GUILD, ROLE_ADMIN, "Europe/Paris")


def commandes(b):
    return {c.name: c for c in b.tree.get_commands(guild=discord.Object(id=GUILD))}


def test_commandes_masquees_par_defaut_et_serialisables():
    b = bot()
    cmds = commandes(b)
    assert set(cmds) == {"grimpeur", "etage", "valider", "annuler", "quetes"}
    for nom, c in cmds.items():
        c.to_dict(b.tree)  # ce que discord.py envoie à Discord lors de la synchronisation
        if nom == "quetes":
            assert c.default_permissions is None  # commande des joueurs : visible de tous
        else:
            assert c.default_permissions is not None and c.default_permissions.manage_guild
    sous = {s.name for s in cmds["grimpeur"].commands}
    assert sous == {"ajouter", "modifier", "inclure", "pause", "reprendre", "exclure", "voir", "liste"}
    assert {s.name for s in cmds["etage"].commands} == {"etat"}
    noms = [p.name for p in cmds["valider"].parameters]
    assert noms[:3] == ["contenu", "grimpeur1", "niveau1"] and noms[-1] == "preuve"
    assert "forcer" not in noms and "motif" not in noms and len(noms) == 18
    assert [p.name for p in cmds["quetes"].parameters] == ["contenu", "preuve", "pour"]


def test_choix_proposes_pour_classe_difficulte_et_statut():
    grimpeur = commandes(bot())["grimpeur"]
    params = {p.name: p for p in grimpeur.get_command("ajouter").parameters}
    assert len(params["classe"].choices) == 19
    assert [c.name for c in params["difficulte"].choices] == ["Aventurier", "Éclaireur", "Collectionneur"]
    assert params["pseudo"].min_value == 2 and params["pseudo"].max_value == 30
    statut = {p.name: p for p in grimpeur.get_command("liste").parameters}["statut"]
    assert [c.value for c in statut.choices] == ["actif", "pause", "exclu", "retardataire"]


async def _appeler(cmd, inter, **kw):
    """Appelle le corps d'une commande comme le ferait discord.py."""
    if cmd.binding is not None:
        await cmd.callback(cmd.binding, inter, **kw)
    else:
        await cmd.callback(inter, **kw)


@pytest.mark.parametrize(("chemin", "args"), [
    (("grimpeur", "ajouter"), {"pseudo": "Brindille", "classe": "Eniripsa", "difficulte": "hard"}),
    (("grimpeur", "modifier"), {"pseudo": "Brindille", "difficulte": "hard"}),
    (("grimpeur", "inclure"), {"pseudo": "Brindille"}),
    (("grimpeur", "pause"), {"pseudo": "Brindille"}),
    (("grimpeur", "reprendre"), {"pseudo": "Brindille"}),
    (("grimpeur", "exclure"), {"pseudo": "Brindille", "motif": "triche"}),
    (("grimpeur", "voir"), {"pseudo": "Brindille"}),
    (("grimpeur", "liste"), {}),
    (("etage", "etat"), {}),
    (("valider",), {"contenu": "1", "grimpeur1": "Brindille", "niveau1": 20}),
    (("annuler",), {"validation": 1, "motif": "x"}),
])  # fmt: skip
async def test_non_admin_recoit_reserve_aux_admins_et_rien_n_est_ecrit(chemin, args):
    cmd = commandes(bot())[chemin[0]]
    if len(chemin) == 2:
        cmd = cmd.get_command(chemin[1])
    inter = interaction(membre(roles=[123]))
    await _appeler(cmd, inter, **args)
    inter.response.send_message.assert_awaited_once_with(REPONSE_REFUS, ephemeral=True)


async def test_quetes_pour_reserve_aux_admins():
    inter = interaction(membre(roles=[123]))
    await _appeler(commandes(bot())["quetes"], inter, contenu="toutes", pour="Brindille")
    assert inter.response.send_message.await_args.args[0].startswith(REPONSE_REFUS)


async def test_verrou_de_serveur():
    arbre = ArbreVerrouille(discord.Client(intents=discord.Intents.none()), GUILD)
    assert await arbre.interaction_check(SimpleNamespace(guild_id=GUILD))
    assert not await arbre.interaction_check(SimpleNamespace(guild_id=999))
    assert not await arbre.interaction_check(SimpleNamespace(guild_id=None))  # message privé


async def test_le_bot_quitte_un_serveur_etranger():
    b = bot()
    etranger, notre = SimpleNamespace(id=999, leave=AsyncMock()), SimpleNamespace(id=GUILD, leave=AsyncMock())
    await b.on_guild_join(etranger)
    await b.on_guild_join(notre)
    etranger.leave.assert_awaited_once()
    notre.leave.assert_not_awaited()
    assert not b.connecte


async def test_valider_grimpeur_sans_niveau_refuse_sans_ecrire():
    inter = interaction(membre(roles=[ROLE_ADMIN]))
    await _appeler(commandes(bot())["valider"], inter, contenu="1", grimpeur1="A", niveau1=20, grimpeur2="B")
    texte = inter.response.send_message.await_args.args[0]
    assert "Rien n'a été enregistré" in texte and "grimpeur2 et niveau2" in texte


def test_autocompletion_ignore_casse_et_accents():
    options = [(p, p) for p in ["Pépin-Lagrume", "Mirelune", "Ombrevive", "Sélénith"]]
    assert suggestions("pep", options) == [("Pépin-Lagrume", "Pépin-Lagrume")]
    assert suggestions("SELE", options)[0][0] == "Sélénith"
    assert [n for n, _ in suggestions("lune", options)] == ["Mirelune"]  # contient, pas seulement commence
    assert len(suggestions("", [(str(i), str(i)) for i in range(40)])) == 25  # limite de Discord
    assert normaliser("  Crâ ") == "cra"


def test_trouver_contenu():
    noms = [(c.nom_court, str(c.id)) for c in CONTENUS]
    assert suggestions("kar", noms)[0] == ("Kardorim vaincu", "1")
    assert trouver_contenu("1", list(CONTENUS)).nom_court == "Kardorim vaincu"
    assert trouver_contenu("kardorim (duo)", list(CONTENUS)).id == 2
    assert trouver_contenu("Crypte de Kardorim", list(CONTENUS)).id == 1
    assert trouver_contenu("99", list(CONTENUS)) is None


def test_date_du_snowflake():
    # Exemple de la documentation Discord : 175928847299117063 → 2016-04-30 11:18:25.796 UTC
    assert date_du_snowflake(175928847299117063) == datetime(2016, 4, 30, 11, 18, 25, 796000, tzinfo=UTC)


def test_lien_de_preuve():
    p = lire_preuve(f"https://discord.com/channels/{GUILD}/22/175928847299117063", GUILD)
    assert (p.guild_id, p.channel_id, p.message_id) == (GUILD, 22, 175928847299117063)
    assert p.poste_le.year == 2016
    assert not isinstance(lire_preuve(f"https://ptb.discord.com/channels/{GUILD}/22/33/", GUILD), str)
    assert lire_preuve("https://discord.com/channels/999/22/33", GUILD) == "la preuve vient d'un autre serveur Discord"
    assert lire_preuve("https://exemple.com/x", GUILD).startswith("lien de preuve invalide")


def test_tronquer_et_reponse():
    assert tronquer("court") == "court"
    long = tronquer("x" * 3000)
    assert len(long) <= 2000 and long.endswith("(liste tronquée)")
    assert Reponse("a").ephemere
