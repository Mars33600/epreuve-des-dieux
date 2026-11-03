"""Les blocs du guide Duffus (SPEC v5 §3 et §5) : construction, écriture, correction d'un admin."""

import dataclasses

import pytest

from epreuve.contenu import construire as k
from epreuve.contenu.ecrire import ecrire_etage
from tests.contenu.test_construire import ETAGES, MAINTENANT


def test_blocs_des_etages_0_et_1():
    b0, b1 = ETAGES[0].blocs, ETAGES[1].blocs
    assert [(b.numero, b.ordre, b.titre) for b in b0] == [(1, 1, "Quêtes du tutoriel"), (2, 2, "Quêtes d'Incarnam")]
    assert [b.numero for b in b1] == [3, 4]  # le rang compte les blocs des tranches précédentes
    assert sum(b.nb_quetes for b in b0) == 27 and sum(b.nb_quetes for b in b1) == 43
    assert all(b.nature == "principale" and b.duffus_url == k.URL_GUIDE_DUFFUS and b.duffus_ancre is None
               for b in (*b0, *b1))
    assert [b.nb_principales for b in b0] == [3, 23]


def test_nature_du_bloc_secondaire_sans_quete_principale():
    qs = [dataclasses.replace(q, nature="secondaire") for q in ETAGES[0].quetes if q.bloc == "Quêtes du tutoriel"]
    (b,) = k.blocs_depuis_quetes(qs)
    assert (b.nature, b.nb_principales, b.nb_quetes) == ("secondaire", 0, 3)


async def test_ecriture_des_blocs_correction_admin_et_coche(depot, moteur):
    from epreuve.domaine.modeles import ElementRef, Regles

    await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    e0 = (await depot.etages())[0]
    blocs = await depot.blocs_brut(e0.id)
    assert [(b.titre, b.nature, b.nb_principales, b.nb_quetes) for b in blocs] == [
        ("Quêtes du tutoriel", "principale", 3, 3), ("Quêtes d'Incarnam", "principale", 23, 24)]
    # Correction d'admin : motif obligatoire, journalisée, et elle survit à la reconstruction.
    with pytest.raises(ValueError):
        await depot.modifier_bloc(blocs[1].id, 1, MAINTENANT, nature="secondaire")
    b = await depot.modifier_bloc(blocs[1].id, 1, MAINTENANT, nature="secondaire", motif="pas utile")
    assert (b.nature, b.nature_origine, b.nature_motif) == ("secondaire", "admin", "pas utile")
    assert (await depot.journal(type_="contenu_admin"))[0].details["motif"] == "pas utile"
    r = await ecrire_etage(moteur, ETAGES[0], MAINTENANT)
    assert r.changements == []
    assert (await depot.blocs_brut(e0.id))[1].nature == "secondaire"
    b = await depot.modifier_bloc(blocs[1].id, 1, MAINTENANT, nature="auto", motif="retour")
    assert (b.nature, b.nature_origine) == ("principale", "construction")
    # Coche d'un bloc : idempotente, et elle alimente le barème.
    await depot.ajouter_liste([7], "actif", 7, MAINTENANT)
    g = await depot.creer_grimpeur(7, "d", "Gr", None, None, MAINTENANT)
    ref = ElementRef("bloc", blocs[0].id)
    assert await depot.cocher(g.id, ref, True, 7, MAINTENANT, Regles()) == (ref,)
    assert await depot.cocher(g.id, ref, True, 7, MAINTENANT, Regles()) == ()
    assert (await depot.coches_etage(e0.id))[g.id].blocs == frozenset({blocs[0].id})
    assert (await depot.contenu_etage(e0.id)).blocs[0].id == blocs[0].id
