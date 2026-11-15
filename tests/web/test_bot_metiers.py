"""Le bot du salon « métiers » : sa réponse, lue dans la même base que le site (sans Discord)."""

import asyncio
from datetime import UTC, datetime

from epreuve.discord.bot import repondre, salon_autorise
from epreuve.web.demo import DepotDemo

SITE = "https://epreuve.test"
T = datetime(2026, 11, 15, tzinfo=UTC)


def _depot():
    d = DepotDemo()
    asyncio.run(d.regler_metiers(1, {"paysan": 30, "bijoutier": 12}, 0, T))  # Brindille
    asyncio.run(d.regler_metiers(2, {"paysan": 15}, 0, T))
    return d


def test_salon_autorise():
    assert salon_autorise("métiers") and salon_autorise("📜-metiers-de-la-guilde") and not salon_autorise("général")


def test_reponse_par_metier_sans_mention():
    d = _depot()
    pseudos = {g.id: g.pseudo for g in asyncio.run(d.grimpeurs())}
    texte = asyncio.run(repondre(d, "<@123456> boulanger lvl15", SITE))
    assert texte.startswith("**Paysan** (niv. 15+) : 2 grimpeurs")
    assert f"• {pseudos[1]} (niv. 30)" in texte and f"• {pseudos[2]} (niv. 15)" in texte and "<@" not in texte
    assert "Personne n'a déclaré **Paysan** (niv. 31+)" in asyncio.run(repondre(d, "<@1> paysan 31", SITE))


def test_reponse_par_joueur_et_aide():
    d = _depot()
    pseudo = next(g.pseudo for g in asyncio.run(d.grimpeurs()) if g.id == 1)
    assert asyncio.run(repondre(d, f"<@1> {pseudo.lower()}", SITE)) == f"**{pseudo}** : Paysan 30 · Bijoutier 12"
    assert "Je ne trouve ni métier ni grimpeur « Personne »" in asyncio.run(repondre(d, "<@1> Personne", SITE))
    assert asyncio.run(repondre(d, "<@1>", SITE)).startswith("Demande-moi un métier")


def test_arret_du_bot_ecrit_au_journal(caplog):
    from epreuve.main import signaler_arret_du_bot

    async def echoue():
        raise RuntimeError("jeton refusé")

    async def scenario():
        t = asyncio.create_task(echoue())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        signaler_arret_du_bot(t)

    asyncio.run(scenario())
    assert "le bot des métiers s'est arrêté" in caplog.text and "jeton refusé" in caplog.text


def test_metier_retire_ignore_par_le_bot():
    d = _depot()
    d._metiers[(1, "parchomage")] = d._metiers[(1, "paysan")].__class__(1, "parchomage", 40, T)
    pseudo = next(g.pseudo for g in asyncio.run(d.grimpeurs()) if g.id == 1)
    assert asyncio.run(repondre(d, f"<@1> {pseudo}", SITE)) == f"**{pseudo}** : Paysan 30 · Bijoutier 12"
