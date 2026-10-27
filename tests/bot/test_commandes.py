"""Les commandes, couche métier, contre un vrai Postgres (marqueur db).

Le contexte simule un admin (ou un joueur) et une horloge : on rejoue les critères d'acceptation
du jalon bêta (docs/LOTS.md).
"""

import asyncio
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

from epreuve.bot.cmd_etage import etage_etat
from epreuve.bot.cmd_grimpeur import (
    grimpeur_ajouter,
    grimpeur_exclure,
    grimpeur_liste,
    grimpeur_modifier,
    grimpeur_pause,
    grimpeur_reprendre,
    grimpeur_voir,
)
from epreuve.bot.cmd_joueur import declarer_quetes
from epreuve.bot.cmd_validation import AConfirmer, DemandeValidation, annuler, valider
from epreuve.bot.commun import Contexte
from epreuve.web.app import construire_etat
from tests.fabrique import AVANT, OUVERTURE, PENDANT

GUILD, ADMIN, JOUEUR = 1000, 111, 555
PARIS = ZoneInfo("Europe/Paris")
GUIDE = "Guide Duffus : Chapitre 0 (nom à confirmer par Shadoaze) à 100 %"
# Des identifiants de messages Discord fabriqués à une date donnée (millisecondes depuis 2015, décalées de 22 bits).
MSG_PENDANT = ((1793534400000 - 1420070400000) << 22) + 1  # 01/11/2026 12:00 UTC (13:00 à Paris)
MSG_AVANT = ((1793361600000 - 1420070400000) << 22) + 1  # 30/10/2026 13:00 à Paris : avant l'ouverture de 17:00


def ctx(depot, quand=PENDANT, acteur=ADMIN):
    return Contexte(depot, acteur, quand, GUILD, PARIS)


async def inscrire(depot, *pseudos, classe="Iop", difficulte="easy", quand=AVANT, membre=None):
    for p in pseudos:
        rep = await grimpeur_ajouter(ctx(depot, quand), p, classe, difficulte, membre)
        assert "est inscrit" in rep.texte, rep.texte


async def etat_site(depot, quand=PENDANT):
    return construire_etat(await depot.charger_instantane(), quand, PARIS)


async def jauge(depot):
    return (await etat_site(depot))["etage_courant"]["jauge"]


async def nb_validations(depot, statut="acceptee"):
    return sum(v.statut == statut for v in await depot.validations())


async def shadoaze(depot):
    """L'exemple de Shadoaze : 4 Collectionneurs, 4 Éclaireurs, 4 Aventuriers, inscrits avant l'ouverture."""
    for diff, prefixe in (("hard", "Coll"), ("med", "Ecl"), ("easy", "Av")):
        await inscrire(depot, *[f"{prefixe}{i}" for i in range(1, 5)], difficulte=diff)


# --- Critère 1 : inscrire 12 grimpeurs ------------------------------------------------------------


async def test_inscrire_douze_grimpeurs(etage0):
    await shadoaze(etage0)
    rep = await grimpeur_liste(ctx(etage0))
    assert rep.texte.startswith("**12 grimpeurs**") and rep.ephemere and "activité : aucune" in rep.texte
    assert (await jauge(etage0)) == {"points": 0, "maximum": 24, "seuil": 18, "pleine": False}


async def test_ajouter_refuse_les_entrees_invalides(etage0):
    assert "entre 2 et 30" in (await grimpeur_ajouter(ctx(etage0), "X", "Iop", "easy")).texte
    assert "classe inconnue" in (await grimpeur_ajouter(ctx(etage0), "Xavier", "Paladin", "easy")).texte
    assert "difficulté inconnue" in (await grimpeur_ajouter(ctx(etage0), "Xavier", "Iop", "x")).texte
    await inscrire(etage0, "Xavier")
    assert "déjà inscrit" in (await grimpeur_ajouter(ctx(etage0), "xavier", "Iop", "easy")).texte
    assert len(await etage0.grimpeurs()) == 1


# --- Critère 3 : /valider pour 3 grimpeurs ----------------------------------------------------------


async def test_valider_trois_grimpeurs_une_entree_au_fil(etage0):
    await inscrire(etage0, "Brindille", "Mirelune", "Sélénith")
    rep = await valider(ctx(etage0), DemandeValidation(
        "Kardorim vaincu", [("Brindille", 20), ("mirelune", 20), ("Sélénith", 20)]))
    assert rep.texte.startswith("✅ Brindille, Mirelune et Sélénith ont validé « Kardorim vaincu » (niv. 20).")
    assert rep.ephemere and "Jauge : 3 points sur 3 requis." in rep.texte
    assert await nb_validations(etage0) == 3
    (entree,) = await etage0.journal(public=True)
    assert entree.type == "validation"
    assert (await jauge(etage0))["points"] == 3
    fil = (await etat_site(etage0))["fil"]
    assert [(f["pseudos"], f["texte"]) for f in fil] == [
        (["Brindille", "Mirelune", "Sélénith"], "ont validé « Kardorim vaincu » (niv. 20).")]


async def test_valider_avec_un_bloquant_rien_n_est_ecrit(etage0):
    await inscrire(etage0, "Brindille", "Mirelune")
    rep = await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20), ("Inconnu", 20), ("Mirelune", 25)]))
    assert rep.texte.startswith("Rien n'a été enregistré") and "« Inconnu » : grimpeur inconnu" in rep.texte
    assert await nb_validations(etage0) == 0 and not await etage0.journal(public=True)


# --- Critère 4 : cap sans tolérance, avertissement et boutons -------------------------------------


async def test_niveaux_20_et_15_sans_avertissement(etage0):
    await inscrire(etage0, "Brindille", "Petit")
    rep = await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20), ("Petit", 15)]))
    assert rep.texte.startswith("✅") and not any(v.forcee for v in await etage0.validations())


async def test_niveau_21_avertissement_puis_accepter_ou_annuler(etage0):
    await inscrire(etage0, "Brindille", "Ombrevive")
    demande = DemandeValidation("Kardorim vaincu", [("Brindille", 20), ("Ombrevive", 21)])
    rep = await valider(ctx(etage0), demande)
    assert isinstance(rep, AConfirmer) and "Ombrevive : niveau 21 au-dessus du cap 20" in rep.texte
    assert await nb_validations(etage0) == 0  # rien avant le clic (« Annuler la saisie » n'écrit rien)

    rep = await valider(ctx(etage0), demande, accepter_depassement=True)
    assert rep.texte.startswith("✅") and "malgré le dépassement de cap pour Ombrevive" in rep.texte
    forcees = {v.grimpeur_id: v.forcee for v in await etage0.validations()}
    ombrevive = await etage0.grimpeur_par_pseudo("Ombrevive")
    assert forcees[ombrevive.id] and sum(forcees.values()) == 1
    (entree,) = [e for e in await etage0.journal() if e.type == "depassement_accepte"]
    async with etage0._moteur.connect() as c:
        requete = text("SELECT acteur_discord_id FROM epreuve.journal WHERE id = :id")
        acteur = (await c.execute(requete, {"id": entree.id})).scalar()
    assert acteur == ADMIN
    assert (await jauge(etage0))["points"] == 2  # la validation forcée compte


async def test_accepter_refait_les_controles(etage0):
    await inscrire(etage0, "Ombrevive")
    demande = DemandeValidation("1", [("Ombrevive", 21)])
    assert isinstance(await valider(ctx(etage0), demande), AConfirmer)
    await grimpeur_pause(ctx(etage0), "Ombrevive")  # entre-temps, il passe en pause
    rep = await valider(ctx(etage0), demande, accepter_depassement=True)
    assert "grimpeur en pause" in rep.texte and await nb_validations(etage0) == 0


async def test_valider_refuse_les_quetes(etage0):
    await inscrire(etage0, "Brindille")
    guide = "Guide Duffus : Chapitre 0 (nom à confirmer par Shadoaze) à 100 %"
    rep = await valider(ctx(etage0), DemandeValidation(guide, [("Brindille", 20)]))
    assert "inconnu" in rep.texte and "/quetes" in rep.texte


# --- Critère 5 : doublon et annulation --------------------------------------------------------------


async def test_doublon_puis_annulation(etage0):
    await inscrire(etage0, "Brindille")
    await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)]))
    rep = await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)]))
    assert "Brindille : déjà validé le 02/11 à " in rep.texte and "(n° 1)" in rep.texte
    assert "indique un motif" in (await annuler(ctx(etage0), 1, " ")).texte
    assert "annulée" in (await annuler(ctx(etage0), 1, "mauvais grimpeur")).texte
    assert (await jauge(etage0))["points"] == 0
    voir = await grimpeur_voir(ctx(etage0), "Brindille")
    assert "n° 1 Kardorim vaincu (niv. 20)" in voir.texte and "annulée · motif : mauvais grimpeur" in voir.texte
    assert "pas de validation acceptée n° 1" in (await annuler(ctx(etage0), 1, "encore")).texte
    assert (await etat_site(etage0))["fil"] == []  # le fil ne montre plus la validation annulée


# --- Critère 6 : paliers ----------------------------------------------------------------------------


async def _faire(depot, pseudo, contenus):
    for c in contenus:
        rep = await valider(ctx(depot), DemandeValidation(c, [(pseudo, 20)]))
        assert rep.texte.startswith("✅"), rep.texte


DEFIS = ["Kardorim (Duo)", "Kardorim (Zombie)", "Kardorim (Premier)", "Kardorim (Spécial)"]


async def test_paliers_avec_l_exemple_de_shadoaze(etage0):
    await shadoaze(etage0)
    await inscrire(etage0, "Brindille", membre=JOUEUR)  # un 13e, Aventurier : maximum 25
    await _faire(etage0, "Coll1", DEFIS)  # 4 défis sans le succès 33 : 0 point
    await _faire(etage0, "Coll2", ["Kardorim vaincu", *DEFIS])  # les 5 succès : 2 points
    await _faire(etage0, "Coll3", ["Kardorim vaincu", *DEFIS])
    await declarer_quetes(ctx(etage0), "toutes", pour="Coll3", appelant_admin=True)  # 5 succès + quêtes : 3
    await _faire(etage0, "Ecl1", ["Kardorim vaincu"])
    await declarer_quetes(ctx(etage0), "toutes", pour="Ecl1", appelant_admin=True)  # 33 + quêtes : 1 point
    await _faire(etage0, "Brindille", ["Kardorim vaincu", *DEFIS])  # Aventurier au full succès : 2 points

    site = await etat_site(etage0)
    points = {g["pseudo"]: (g["points"], g["marques"]) for g in site["grimpeurs"]}
    assert points["Coll1"][0] == 0 and points["Coll2"][0] == 2 and points["Coll3"][0] == 3
    assert points["Ecl1"] == (1, {"1": True, "2": False, "3": True})  # marque Quêtes allumée
    assert points["Brindille"][0] == 2
    assert site["etage_courant"]["jauge"] == {"points": 8, "maximum": 25, "seuil": 19, "pleine": False}
    assert [p["grimpeurs"] for p in site["etage_courant"]["paliers"]] == [4, 3, 1]


# --- Critère 7 : changement de difficulté -------------------------------------------------------------


async def test_changement_de_difficulte_24_vers_25(etage0):
    await shadoaze(etage0)
    rep = await grimpeur_modifier(ctx(etage0), "Ecl1", difficulte="hard")
    assert "difficulté : Éclaireur → Collectionneur" in rep.texte and "Maximum 24 → 25, seuil 18 → 19." in rep.texte
    assert any(e.type == "difficulte" for e in await etage0.journal())
    assert (await jauge(etage0))["maximum"] == 25


# --- Critère 8 : pause et exclusion ------------------------------------------------------------------


async def test_pause_puis_reprise(etage0):
    await shadoaze(etage0)
    await _faire(etage0, "Coll1", ["Kardorim vaincu"])
    rep = await grimpeur_pause(ctx(etage0), "Coll1", "vacances")
    assert "Maximum 24 → 21, seuil 18 → 16." in rep.texte
    assert (await jauge(etage0))["points"] == 0
    site = await etat_site(etage0)
    assert site["grimpeurs"][-1]["pseudo"] == "Coll1" and site["grimpeurs"][-1]["statut"] == "pause"
    iop = next(c for c in site["classes"] if c["classe"] == "Iop")
    assert (iop["actifs"], iop["en_pause"]) == (11, 1)
    assert "déjà en pause" in (await grimpeur_pause(ctx(etage0), "Coll1")).texte
    assert "Maximum 21 → 24" in (await grimpeur_reprendre(ctx(etage0), "Coll1")).texte
    assert "déjà actif" in (await grimpeur_reprendre(ctx(etage0), "Coll1")).texte
    assert (await etage0.grimpeur_par_pseudo("Coll1")).statut == "actif"


async def test_exclusion_disparait_du_site(etage0):
    await inscrire(etage0, "Fourbe", "Honnete")
    await valider(ctx(etage0), DemandeValidation("1", [("Fourbe", 20), ("Honnete", 20)]))
    assert "est exclu" in (await grimpeur_exclure(ctx(etage0), "Fourbe", "triche")).texte
    site = await etat_site(etage0)
    assert "Fourbe" not in str(site)
    assert site["fil"][0]["pseudos"] == ["Honnete"] and site["fil"][0]["texte"].startswith("a validé")
    assert "déjà exclu" in (await grimpeur_exclure(ctx(etage0), "Fourbe", "x")).texte
    assert "demande un motif" in (await grimpeur_exclure(ctx(etage0), "Honnete", " ")).texte
    assert "est exclu" in (await grimpeur_pause(ctx(etage0), "Fourbe")).texte
    assert "grimpeur exclu" in (await valider(ctx(etage0), DemandeValidation("2", [("Fourbe", 20)]))).texte


# --- Critère 9 : inscription après l'ouverture, réintégration à la main ------------------------------


async def test_inscrit_apres_l_ouverture_en_pause_puis_repris_par_un_admin(etage0):
    await inscrire(etage0, "Ancien")
    rep = await grimpeur_ajouter(ctx(etage0), "Fleur", "Sadida", "easy")  # après l'ouverture
    assert "**en pause**" in rep.texte and "/grimpeur reprendre pseudo:Fleur" in rep.texte and "Maximum" not in rep.texte
    site = await etat_site(etage0)
    fleur = next(g for g in site["grimpeurs"] if g["pseudo"] == "Fleur")
    assert fleur["statut"] == "pause" and "retardataire" not in fleur
    assert site["etage_courant"]["jauge"]["maximum"] == 1 and site["etage_courant"]["n_pause"] == 1
    assert "n_retardataires" not in site["etage_courant"]
    await grimpeur_modifier(ctx(etage0), "Fleur", niveau=20)  # monter de niveau ne change rien seul
    assert (await etage0.grimpeur_par_pseudo("Fleur")).statut == "pause"
    rep = await grimpeur_reprendre(ctx(etage0), "Fleur")
    assert "reprend l'ascension" in rep.texte and "Maximum 1 → 2" in rep.texte


# --- Critère 10 : /quetes --------------------------------------------------------------------------


async def test_quetes_par_un_grimpeur_relie(etage0):
    await inscrire(etage0, "Brindille", membre=JOUEUR)
    lien = f"https://discord.com/channels/{GUILD}/5/{MSG_PENDANT}"
    rep = await declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes", preuve=lien)
    assert rep.texte.startswith(f"✅ **Brindille** a déclaré avoir terminé « {GUIDE} »")
    assert "https://duffus.fr/guide-complet" in rep.texte
    (v,) = await etage0.validations()
    assert v.source == "declaration" and v.niveau is None and v.realisee_le == PENDANT
    fil = (await etat_site(etage0))["fil"]
    assert fil[0]["texte"] == f"a déclaré avoir terminé « {GUIDE} »."
    voir = await grimpeur_voir(ctx(etage0), "Brindille")
    assert "(déclaré)" in voir.texte and f"preuve : {lien}" in voir.texte
    assert "déjà déclaré toutes" in (await declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes")).texte
    rep = await declarer_quetes(ctx(etage0, acteur=JOUEUR), GUIDE)
    assert "déjà validé" in rep.texte
    assert "annulée" in (await annuler(ctx(etage0), v.id, "déclaration erronée")).texte  # un admin annule


async def test_quetes_non_relie_ou_pour(etage0):
    await inscrire(etage0, "Brindille")
    rep = await declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes")
    assert "Demande à un admin de relier ton compte" in rep.texte and await nb_validations(etage0) == 0
    rep = await declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes", pour="Brindille", appelant_admin=False)
    assert rep.texte.startswith("Réservé aux admins") and await nb_validations(etage0) == 0
    rep = await declarer_quetes(ctx(etage0), "toutes", pour="Brindille", appelant_admin=True)
    assert rep.texte.startswith("✅ **Brindille**")
    assert "Aucun grimpeur nommé" in (await declarer_quetes(ctx(etage0), "x", pour="Rien", appelant_admin=True)).texte


async def test_quetes_refus(etage0):
    await inscrire(etage0, "Brindille", membre=JOUEUR)
    rep = await declarer_quetes(ctx(etage0, acteur=JOUEUR), "Kardorim vaincu")
    assert "inconnu" in rep.texte and GUIDE in rep.texte and "duffus.fr" in rep.texte
    rep = await declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes", preuve="https://discord.com/channels/42/5/6")
    assert "autre serveur" in rep.texte
    rep = await declarer_quetes(ctx(etage0, quand=OUVERTURE - timedelta(hours=1), acteur=JOUEUR), "toutes")
    assert "réalisée avant l'ouverture" in rep.texte
    await grimpeur_pause(ctx(etage0), "Brindille")
    assert "grimpeur en pause" in (await declarer_quetes(ctx(etage0, acteur=JOUEUR), "toutes")).texte
    assert await nb_validations(etage0) == 0


# --- Critère 11 : premier Eniripsa ---------------------------------------------------------------


async def test_premier_eniripsa(etage0):
    def eniripsa(site):
        return next(c for c in site["classes"] if c["classe"] == "Eniripsa")

    site = await etat_site(etage0)
    assert len(site["classes"]) == 19 and eniripsa(site)["actifs"] == 0
    await inscrire(etage0, "Soigneuse", classe="Eniripsa")
    assert eniripsa(await etat_site(etage0))["actifs"] == 1


# --- Critères 14 et 15 : maximum nul, preuve ------------------------------------------------------


async def test_maximum_nul_verdict(etage0):
    rep = await etage_etat(ctx(etage0))
    assert "Aucun grimpeur actif" in rep.texte and "0 points sur 0 requis" in rep.texte


async def test_preuve_fixe_la_date_de_realisation(etage0):
    await inscrire(etage0, "Brindille")
    lien = f"https://discord.com/channels/{GUILD}/5/{MSG_PENDANT}"
    plus_tard = ctx(etage0, quand=PENDANT + timedelta(days=2))
    rep = await valider(plus_tard, DemandeValidation("1", [("Brindille", 20)], lien))
    assert rep.texte.startswith("✅") and "réalisée le 01/11 à 13:00" in rep.texte


async def test_preuve_avant_ouverture_ou_autre_serveur_refusee(etage0):
    await inscrire(etage0, "Brindille")
    avant = f"https://discord.com/channels/{GUILD}/5/{MSG_AVANT}"
    rep = await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)], avant))
    assert "Brindille : réalisée avant l'ouverture de l'étage" in rep.texte
    ailleurs = f"https://discord.com/channels/42/5/{MSG_PENDANT}"
    rep = await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)], ailleurs))
    assert "la preuve vient d'un autre serveur Discord" in rep.texte
    assert await nb_validations(etage0) == 0


# --- Critère 16 : journal ----------------------------------------------------------------------


async def test_journal_complet_et_fil_public_limite(etage0):
    await inscrire(etage0, "Brindille", "Torvald", membre=None)
    await grimpeur_ajouter(ctx(etage0), "Tard", "Iop", "easy")  # arrive en pause
    await grimpeur_reprendre(ctx(etage0), "Tard")
    await grimpeur_modifier(ctx(etage0), "Brindille", difficulte="hard")
    await grimpeur_pause(ctx(etage0), "Torvald")
    await grimpeur_reprendre(ctx(etage0), "Torvald")
    await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)]))
    await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20)]))  # refus : pas d'écriture
    await valider(ctx(etage0), DemandeValidation("2", [("Torvald", 22)]), accepter_depassement=True)
    await declarer_quetes(ctx(etage0), "toutes", pour="Brindille", appelant_admin=True)
    await annuler(ctx(etage0), 1, "erreur")
    await grimpeur_exclure(ctx(etage0), "Torvald", "abandon")
    journal = await etage0.journal()
    assert sorted(e.type for e in journal) == sorted([
        "inscription", "inscription", "inscription", "reprise", "difficulte", "pause", "reprise", "validation",
        "validation", "depassement_accepte", "declaration", "annulation", "exclusion"])
    assert {e.type for e in journal if e.public} == {"validation", "declaration"}
    async with etage0._moteur.connect() as c:
        sans_acteur = (await c.execute(text("SELECT count(*) FROM epreuve.journal WHERE acteur_discord_id IS NULL")))
        assert sans_acteur.scalar() == 0
    voir = await grimpeur_voir(ctx(etage0), "Brindille")
    assert "Dernière activité : 02/11 à " in voir.texte
    assert "activité : 02/11" in (await grimpeur_liste(ctx(etage0))).texte


# --- Critère 19 : deux /valider simultanés -----------------------------------------------------------


async def test_deux_valider_simultanes(etage0):
    await inscrire(etage0, "Brindille")
    demande = DemandeValidation("1", [("Brindille", 20)])
    r1, r2 = await asyncio.gather(valider(ctx(etage0), demande), valider(ctx(etage0, acteur=222), demande))
    textes = [r1.texte, r2.texte]
    assert sum(t.startswith("✅") for t in textes) == 1
    assert sum("déjà validé" in t for t in textes) == 1
    assert await nb_validations(etage0) == 1


# --- Divers ------------------------------------------------------------------------------------


async def test_modifier_et_voir(etage0):
    await inscrire(etage0, "Brindille")
    rep = await grimpeur_modifier(ctx(etage0), "Brindille", nouveau_pseudo="Brindille-II", classe="Sram",
                                  difficulte="med", niveau=18, membre_id=JOUEUR)
    assert "difficulté : Aventurier → Éclaireur" in rep.texte and "niveau : — → 18" in rep.texte
    voir = await grimpeur_voir(ctx(etage0), "brindille-ii")
    assert "Sram, Éclaireur, actif" in voir.texte and f"<@{JOUEUR}>" in voir.texte and "Aucune validation" in voir.texte
    assert "Rien à changer" in (await grimpeur_modifier(ctx(etage0), "Brindille-II", classe="Sram")).texte
    assert "Aucun grimpeur nommé" in (await grimpeur_modifier(ctx(etage0), "Personne")).texte
    assert "entre 2 et 30" in (await grimpeur_modifier(ctx(etage0), "Brindille-II", nouveau_pseudo="x")).texte
    assert "classe inconnue" in (await grimpeur_modifier(ctx(etage0), "Brindille-II", classe="Paladin")).texte
    assert "difficulté inconnue" in (await grimpeur_modifier(ctx(etage0), "Brindille-II", difficulte="x")).texte
    assert "entre 1 et 200" in (await grimpeur_modifier(ctx(etage0), "Brindille-II", niveau=0)).texte
    await inscrire(etage0, "Autre")
    assert "déjà inscrit" in (await grimpeur_modifier(ctx(etage0), "Autre", nouveau_pseudo="BRINDILLE-II")).texte


async def test_etage_etat_public(etage0):
    await shadoaze(etage0)
    await grimpeur_ajouter(ctx(etage0), "Tard", "Iop", "easy")
    await grimpeur_pause(ctx(etage0), "Av4")
    rep = await etage_etat(ctx(etage0), public=True)
    assert not rep.ephemere
    assert "Jauge : **0 points sur 18 requis** — il en manque 18" in rep.texte
    assert "Maximum 23 = 4 Collectionneurs × 3 + 4 Éclaireurs × 2 + 3 Aventuriers × 1. Seuil 75 % → 18." in rep.texte
    assert "Palier 1 · Kardorim vaincu : 0 grimpeur" in rep.texte
    assert "pas avant le vendredi 13 novembre à 17 h" in rep.texte
    assert "11 grimpeurs actifs, 2 en pause." in rep.texte


async def test_etage_etat_seuil_atteint(etage0):
    await inscrire(etage0, "Seul")
    await valider(ctx(etage0), DemandeValidation("1", [("Seul", 20)]))
    assert "pourra s'ouvrir le vendredi 13 novembre à 17 h, pas avant" in (await etage_etat(ctx(etage0))).texte
    tard = ctx(etage0, quand=PENDANT + timedelta(days=30))
    assert "un admin peut ouvrir l'étage 1" in (await etage_etat(tard)).texte


async def test_listes_et_cas_vides(etage0):
    assert (await grimpeur_liste(ctx(etage0))).texte == "Aucun grimpeur."
    assert (await grimpeur_liste(ctx(etage0), "pause")).texte == "Aucun grimpeur en pause."
    assert "Aucun grimpeur nommé" in (await grimpeur_voir(ctx(etage0), "Fantome")).texte
    assert "contenu « Donjon imaginaire » inconnu" in (
        await valider(ctx(etage0), DemandeValidation("Donjon imaginaire", [("A", 20)]))).texte
    assert "au moins un grimpeur" in (await valider(ctx(etage0), DemandeValidation("1", []))).texte
    await inscrire(etage0, "Brindille")
    rep = await valider(ctx(etage0), DemandeValidation("1", [("Brindille", 20), ("brindille", 20)]))
    assert "indiqué deux fois" in rep.texte


async def test_sans_etage_ouvert(depot):
    assert "Aucun étage n'est ouvert" in (await etage_etat(ctx(depot))).texte
    assert "aucun étage n'est ouvert" in (await valider(ctx(depot), DemandeValidation("1", [("A", 20)]))).texte
    await inscrire(depot, "Brindille", membre=JOUEUR)
    assert "aucun étage n'est ouvert" in (await declarer_quetes(ctx(depot, acteur=JOUEUR), "toutes")).texte
    assert (await depot.grimpeur_par_pseudo("Brindille")).statut == "actif"  # pas d'étage : actif
