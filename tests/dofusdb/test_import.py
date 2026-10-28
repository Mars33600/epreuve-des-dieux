"""Import de l'étage 0 depuis les réponses DofusDB enregistrées (aucun accès réseau)."""

import copy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from sqlalchemy import func, select

from epreuve.db import tables as t
from epreuve.dofusdb.client import ClientDofusDB
from epreuve.dofusdb.import_etage import ConfigInvalide, developper_etage, ecrire_etage, importer
from tests.conftest import RACINE, transport_dofusdb

YAML0 = RACINE / "config/etages/etage-0.yaml"
TEMPORIS = ("/achievements/2316", "/achievements/2676", "/achievements/2783")
PARIS = ZoneInfo("Europe/Paris")


def config0():
    return yaml.safe_load(YAML0.read_text(encoding="utf-8"))


async def _preparer(appels=None, config=None):
    async with ClientDofusDB(transport=transport_dofusdb(appels)) as client:
        return await developper_etage(config or config0(), client)


async def test_etage0_produit_6_contenus_et_les_bons_paliers():
    appels: list[str] = []
    e = await _preparer(appels)
    assert len(e.contenus) == 6
    assert set(e.contenus) == {("achievement", i) for i in (33, 487, 571, 574, 6148)} | {("guide_duffus", 0)}
    paliers = {p.rang: set(p.contenus) for p in e.paliers}
    assert paliers[1] == {("achievement", 33)} and len(paliers[2]) == 5 and paliers[3] == {("guide_duffus", 0)}
    assert e.seuil_pourcent == 75 and e.level_cap == 20
    assert e.ouvert_le == datetime(2026, 10, 30, 17, 0, tzinfo=PARIS)
    assert e.date_plancher_suivant == datetime(2026, 11, 13, 17, 0, tzinfo=PARIS)

    assert e.contenus[("achievement", 33)].nom_court == "Kardorim vaincu"
    assert e.contenus[("achievement", 33)].nom == "Crypte de Kardorim"
    assert e.contenus[("achievement", 487)].nom_court == "Kardorim (Duo)"
    guide = e.contenus[("guide_duffus", 0)]
    assert guide.type == "lot_quetes" and guide.dofusdb_ids_couverts is None
    assert guide.nom == "Guide Duffus : Chapitre 0 (nom à confirmer par Shadoaze) à 100 %"
    assert e.chapitre_guide == "Chapitre 0 (nom à confirmer par Shadoaze)"
    assert not set(TEMPORIS) & set(appels)  # les succès Temporis ne sont jamais demandés
    assert not [a for a in appels if "quest" in a]  # plus aucune quête lue dans DofusDB


@pytest.mark.parametrize("casser", [
    lambda c: c["paliers"].pop(),  # pas de rang 3
    lambda c: c["paliers"][2].update(contenus=[]),  # palier vide
    lambda c: c["paliers"][2].update(rang=4),
    lambda c: c.pop("paliers"),
])
async def test_paliers_invalides_refuses(casser):
    config = copy.deepcopy(config0())
    casser(config)
    with pytest.raises(ConfigInvalide, match="palier"):
        await _preparer(config=config)


@pytest.mark.parametrize("pourcent", [0, 101])
async def test_seuil_hors_bornes_refuse(pourcent):
    config = config0()
    config["seuil_pourcent"] = pourcent
    with pytest.raises(ConfigInvalide, match="seuil_pourcent"):
        await _preparer(config=config)


async def test_guide_duffus_sans_chapitre_refuse():
    config = config0()
    config.pop("chapitre_guide")
    with pytest.raises(ConfigInvalide, match="chapitre_guide"):
        await _preparer(config=config)


async def test_raccourci_inconnu_et_date_sans_fuseau_refuses():
    config = config0()
    config["paliers"][0]["contenus"] = [{"dofusdb_inconnu": 1}]
    with pytest.raises(ConfigInvalide, match="raccourci"):
        await _preparer(config=config)
    config = config0()
    config["ouvert_le"] = "2026-10-30T17:00:00"
    with pytest.raises(ConfigInvalide, match="fuseau"):
        await _preparer(config=config)


async def test_a_blanc_n_ecrit_rien_et_ne_demande_pas_de_base():
    rapport = await importer(Path(YAML0), a_blanc=True, database_url=None,
                             client=ClientDofusDB(transport=transport_dofusdb()))
    assert "rien n'a été écrit" in rapport
    assert "seuil 75 %" in rapport and "palier 3" in rapport and "guide Duffus" in rapport


async def test_ecriture_rejouable_sans_doublon(depot, moteur):
    premier = await ecrire_etage(moteur, await _preparer())
    second = await ecrire_etage(moteur, await _preparer())
    assert premier == second
    async with moteur.connect() as c:
        compte = {nom: (await c.execute(select(func.count()).select_from(table))).scalar()
                  for nom, table in [("etage", t.etage), ("contenu", t.contenu), ("palier", t.palier),
                                     ("liens", t.palier_contenu)]}
    assert compte == {"etage": 1, "contenu": 6, "palier": 3, "liens": 1 + 5 + 1}
    etage = await depot.etage_ouvert()
    assert etage.numero == 0 and etage.statut == "ouvert" and etage.seuil_pourcent == 75
    paliers = await depot.paliers(etage.id)
    assert [p.rang for p in paliers] == [1, 2, 3] and len(paliers[1].contenu_ids) == 5


async def test_reimport_ne_change_pas_le_statut_mais_met_a_jour_le_reste(depot, moteur):
    e = await _preparer()
    await ecrire_etage(moteur, e)
    async with moteur.begin() as c:
        await c.execute(t.etage.update().values(statut="termine"))
    assert not await depot.journal()  # une création n'est pas une modification
    e.seuil_pourcent = 70
    await ecrire_etage(moteur, e)
    etage = (await depot.etages())[0]
    assert etage.statut == "termine" and etage.seuil_pourcent == 70
    (entree,) = await depot.journal()
    assert entree.type == "import_etage" and entree.details["changements"] == {"seuil_pourcent": [75, 70]}
    await ecrire_etage(moteur, e)  # rejoué sans changement : rien de plus au journal
    assert len(await depot.journal()) == 1


async def test_etage_suivant_cree_scelle(depot, moteur):
    e = await _preparer()
    e.numero = 1
    await ecrire_etage(moteur, e)
    assert (await depot.etages())[0].statut == "scelle"


async def test_importer_ecrit_en_base(depot, url_base):
    rapport = await importer(Path(YAML0), a_blanc=False, database_url=url_base,
                             client=ClientDofusDB(transport=transport_dofusdb()))
    assert "Écrit en base" in rapport
    assert len(await depot.contenus((await depot.etage_ouvert()).id)) == 6


async def test_importer_sans_base_s_arrete(capsys):
    with pytest.raises(SystemExit):
        await importer(Path(YAML0), a_blanc=False, database_url=None,
                       client=ClientDofusDB(transport=transport_dofusdb()))
