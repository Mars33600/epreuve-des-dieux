"""Chargement et lectures de l'encyclopédie sur un vrai Postgres (extraits réels réduits, tests/donnees/)."""

from pathlib import Path

import pytest
from sqlalchemy import text

from epreuve.encyclopedie.charger import ExtraitManquant, charger, preparer
from epreuve.encyclopedie.depot import PAR_PAGE, DepotEncyclopedie, Filtres

DONNEES = Path(__file__).resolve().parents[1] / "donnees" / "encyclopedie"
EPEE = 44  # Épée de Boisaille : recette de Forgeron, effets 100 (dommages), 118 (Force), 422


@pytest.fixture
async def ency(moteur) -> DepotEncyclopedie:
    await charger(moteur, DONNEES)
    return DepotEncyclopedie(moteur)


def test_preparer_sans_base():
    lignes = preparer(DONNEES)
    epee = next(o for o in lignes["ency_objet"] if o["id"] == EPEE)
    assert epee["cle_recherche"] == "epee de boisaille" and epee["famille"] == "armes"
    assert next(r for r in lignes["ency_recette"] if r["objet_id"] == EPEE)["ingredient_ids"]
    assert all(1 <= s["niveau"] <= 200 for s in lignes["ency_stuff"])
    assert all(m["niveau_min"] <= m["niveau_max"] for m in lignes["ency_monstre"] if m["niveau_min"])


def test_extrait_manquant(tmp_path):
    with pytest.raises(ExtraitManquant, match="types.jsonl"):
        preparer(tmp_path)


async def test_chargement_tout_ou_rien_et_rejouable(ency, moteur):
    rapport = await charger(moteur, DONNEES)  # deux fois : mêmes comptes, pas de doublon
    async with moteur.connect() as c:
        n = (await c.execute(text("SELECT count(*) FROM epreuve.ency_objet"))).scalar_one()
    assert n == rapport.comptes["ency_objet"] > 40


async def test_recherche_par_debut_de_mots_et_index(ency, moteur):
    page = await ency.chercher_objets(Filtres(q="epee boi"))
    assert [o["nom"] for o in page.lignes] == ["Épée de Boisaille"] and page.total == 1
    assert (await ency.chercher_objets(Filtres(q="ÉPÉE"))).total >= 1
    assert (await ency.chercher_objets(Filtres(q="'); DROP TABLE x; --"))).total == 0
    async with moteur.connect() as c:
        await c.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join((await c.execute(text(
            "EXPLAIN SELECT id FROM epreuve.ency_objet WHERE recherche @@ to_tsquery('simple', 'epee:*')"))).scalars())
    assert "ency_objet_recherche" in plan


async def test_filtres_tri_et_pagination(ency):
    tout = await ency.chercher_objets(Filtres(tri="niveau_asc"))
    assert tout.total > PAR_PAGE and len(tout.lignes) == PAR_PAGE and tout.pages >= 2
    niveaux = [o["niveau"] for o in tout.lignes]
    assert niveaux == sorted(niveaux)
    page2 = await ency.chercher_objets(Filtres(tri="niveau_asc", page=2))
    assert not {o["id"] for o in page2.lignes} & {o["id"] for o in tout.lignes}
    ressources = await ency.chercher_objets(Filtres(famille="ressources"))
    assert ressources.total and all(o["famille"] == "ressources" for o in ressources.lignes)
    bornes = await ency.chercher_objets(Filtres(niveau_min=10, niveau_max=20))
    assert all(10 <= o["niveau"] <= 20 for o in bornes.lignes)
    assert all(o["niveau"] <= 5 for o in (await ency.chercher_objets(Filtres(), plafond=5)).lignes)
    hors = await ency.chercher_objets(Filtres(page=999))
    assert hors.lignes == [] and hors.total == tout.total


async def test_fiche_objet_complete(ency):
    o = await ency.objet(EPEE)
    assert o["nom"] == "Épée de Boisaille" and o["type"] == "Épée" and o["arme"]["pa"] == 3
    assert "7 à 10 Force" in [e.texte for e in o["effets_lus"]]
    assert o["recette"]["metier"] == "Forgeron" and all(i["qte"] for i in o["recette"]["ingredients"])
    assert o["image"].startswith("https://api.dofusdb.fr/")
    ingredient = o["recette"]["ingredients"][0]["id"]
    assert EPEE in [x["id"] for x in (await ency.objet(ingredient))["utilise_dans"]]
    assert await ency.objet(999_999_999) is None
    assert await ency.objet(EPEE, plafond=1) is None  # verrouillage par étage (T-08)


async def test_monstre_butin_et_drop_croise(ency):
    page = await ency.chercher_monstres(Filtres(q="larve bleue"))
    assert page.lignes[0]["nom"] == "Larve Bleue"
    m = await ency.monstre(31)
    assert m["race"] and m["grades"][0]["pv"] and m["butin"]
    objet = m["butin"][0]["id"]
    assert 31 in [x["id"] for x in (await ency.objet(objet))["monstres"]]


async def test_recettes_par_metier(ency):
    page = await ency.chercher_recettes(Filtres(metier=11))
    assert any(r["nom"] == "Épée de Boisaille" for r in page.lignes)
    assert all(r["metier_nom"] == "Forgeron" for r in page.lignes)
    assert (await ency.chercher_recettes(Filtres(q="anneau"))).total >= 1


async def test_stuffs_bornes_par_niveau(ency):
    assert [s["niveau"] for s in await ency.stuffs(40)] == [20]
    assert len(await ency.stuffs(200)) == 3
    effets = await ency.effets_de([EPEE])
    assert effets[EPEE]
