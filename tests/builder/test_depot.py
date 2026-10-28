"""Les builds en base : création, lecture, modification et suppression par l'auteur seul, partage dans la guilde."""

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from epreuve.builder.depot import Contenu, DepotBuilds
from tests.fabrique import PENDANT

BUILD = Contenu("Iop Bouftou", "Iop", 50, {"coiffe": 2411}, {"Force": 100}, {"Force": 100}, "note", False)


@pytest.fixture
async def builds(depot, moteur):
    g1 = await depot.creer_grimpeur(1, "a", "Brindille", "Iop", 50, PENDANT, liste_obligatoire=False)
    g2 = await depot.creer_grimpeur(2, "b", "Mirelune", "Crâ", 60, PENDANT, liste_obligatoire=False)
    return DepotBuilds(moteur), g1.id, g2.id


async def test_cycle_de_vie(builds):
    d, g1, g2 = builds
    bid = await d.creer(g1, BUILD, PENDANT)
    lu = await d.lire(bid)
    assert (lu.grimpeur_id, lu.auteur, lu.contenu) == (g1, "Brindille", BUILD)
    plus_tard = PENDANT + timedelta(hours=1)
    nouveau = Contenu("Autre", "Iop", 60, {}, {}, {}, "", True)
    assert not await d.modifier(bid, g2, nouveau, plus_tard)  # pas l'auteur
    assert await d.modifier(bid, g1, nouveau, plus_tard)
    lu = await d.lire(bid)
    assert lu.contenu == nouveau and lu.maj_le == plus_tard
    assert not await d.supprimer(bid, g2)
    assert await d.supprimer(bid, g1)
    assert await d.lire(bid) is None
    assert not await d.modifier(bid, g1, nouveau, plus_tard)


async def test_mes_builds_et_partages(builds):
    d, g1, g2 = builds
    prive = await d.creer(g1, BUILD, PENDANT)
    partage = await d.creer(g1, Contenu("Public", "Iop", 50, {}, {}, {}, "", True), PENDANT + timedelta(minutes=1))
    autre = await d.creer(g2, Contenu("Crâ", "Crâ", 60, {}, {}, {}, "", True), PENDANT + timedelta(minutes=2))
    assert [b.id for b in await d.de_grimpeur(g1)] == [partage, prive]
    assert [b.id for b in await d.partages()] == [autre, partage]
    assert [b.id for b in await d.partages(sauf_grimpeur=g2)] == [partage]


async def test_contraintes(builds):
    d, g1, _ = builds
    with pytest.raises(IntegrityError):
        await d.creer(g1, Contenu("", "Iop", 50, {}, {}, {}), PENDANT)
    with pytest.raises(IntegrityError):
        await d.creer(g1, Contenu("x", "Iop", 201, {}, {}, {}), PENDANT)
