"""Replis DofusDB de la construction (succès d'un donjon, nature) et étage saisi à la main (plan de repli)."""

import json
import shutil
from pathlib import Path

import pytest

from epreuve.contenu import __main__ as cli
from epreuve.contenu import construire as k
from epreuve.contenu.manuel import construire_manuel, lire_etage_manuel
from epreuve.dofusdb.repli import ClientEnCache

DONNEES_TESTS = Path(__file__).resolve().parents[1] / "donnees" / "dofusdb"
ASPI = k.Aspiration.lire(k.derniere_aspiration())


def cache_kardorim(dossier: Path) -> Path:
    """Les réponses enregistrées du donjon 90 (Crypte de Kardorim), plus une recherche par nom."""
    dossier.mkdir(parents=True, exist_ok=True)
    for f in DONNEES_TESTS.glob("*.json"):
        shutil.copy(f, dossier / f.name)
    (dossier / "dungeon-recherche-crypte-de-kardorim.json").write_text(json.dumps([{"id": 90}]))
    (dossier / "dungeon-recherche-donjon-perdu.json").write_text("[]")
    return dossier


def test_guides_repli_vers_duffus_par_le_nom():
    g = k.guides_repli_vers_duffus({"Dofus Kaliptus": {1: "  l'anneau DE TOUS les dangers ", 2: "Inconnue"}}, ASPI)
    assert g == {"Dofus Kaliptus": frozenset({1})}


async def test_completer_par_dofusdb(tmp_path):
    client = ClientEnCache(None, cache_kardorim(tmp_path))
    e = k.construire(0, ASPI, k.lire_config_etages(), k.lire_dofus_retenus())
    vide = k.DonjonPrepare("crypte", "Crypte de Kardorim", 10, 1, None, None, "duffus", ())
    perdu = k.DonjonPrepare("perdu", "Donjon perdu", 10, 2, None, None, "duffus", ())
    e.donjons = [vide, perdu, e.donjons[0]]
    e.alertes.append("donjon « Crypte de Kardorim » : succès introuvables chez Duffus, repli DofusDB à faire")
    e = await k.completer_par_dofusdb(e, client)
    d = e.donjons[0]
    assert (d.succes_source, d.dofusdb_id, len(d.cases), d.cases[0].est_classique) == ("dofusdb", 90, 5, True)
    assert [c.ordre for c in d.cases] == [1, 2, 3, 4, 5] and d.cases[0].duffus_id == "dofusdb:33"
    assert e.donjons[1].cases == () and e.donjons[2].succes_source == "duffus"
    assert any("succès pris chez DofusDB" in a for a in e.alertes)
    assert any("Donjon perdu" in a and "introuvable chez DofusDB" in a for a in e.alertes)
    assert not any("repli DofusDB à faire" in a for a in e.alertes)


async def test_completer_alerte_si_pas_5_succes(tmp_path):
    cache = cache_kardorim(tmp_path)
    (cache / "dungeon-90.json").write_text(json.dumps({"id": 90, "achievements": [33, 487]}))
    e = k.EtagePrepare(0, "É", "1-20", 1, 20, 20, None, None, None,
                       donjons=[k.DonjonPrepare("c", "Crypte", 10, 1, None, 90, "duffus", ())])
    e = await k.completer_par_dofusdb(e, ClientEnCache(None, cache))
    assert "2 succès au lieu de 5" in e.alertes[0]


MANUEL = """
etage: 0
niveau_min: 1
niveau_max: 20
level_cap: 20
ouvert_le: "2026-10-30T17:00:00+01:00"
donjons: [90]
blocs:
  - nom: "Incarnam"
    quetes:
      - {dofusdb_id: 1462, jusqu_ou: "jusqu'au donjon"}
      - {dofusdb_id: 1463}
"""


def cache_manuel(dossier: Path) -> Path:
    cache_kardorim(dossier)
    (dossier / "quest-1462.json").write_text(json.dumps({"id": 1462, "name": {"fr": "Racine"}, "levelMin": 10,
                                                        "startCriterion": "Qf=1463"}))
    (dossier / "quest-1463.json").write_text(json.dumps({"id": 1463, "name": {"fr": "Autre"}, "levelMin": 12}))
    (dossier / "item-type-23.json").write_text(json.dumps([{"id": 1, "name": {"fr": "Dofus Test"},
                                                            "questsThatReward": [1462]}]))
    return dossier


async def test_construire_manuel(tmp_path):
    f = tmp_path / "etage-0.yaml"
    f.write_text(MANUEL, encoding="utf-8")
    client = ClientEnCache(None, cache_manuel(tmp_path / "cache"))
    e = await construire_manuel(lire_etage_manuel(f), client, {"Dofus Test"}, {"dofusdb:1463": "secondaire"})
    assert [d.nom for d in e.donjons] == ["Crypte de Kardorim"] and len(e.donjons[0].cases) == 5
    q1, q2 = e.quetes
    assert (q1.nom, q1.niveau, q1.nature, q1.nature_origine, q1.dofus, q1.jusqu_ou, q1.fiche) == (
        "Racine", 10, "principale", "dofusdb", ("Dofus Test",), "jusqu'au donjon", None)
    assert (q2.nature, q2.nature_origine) == ("secondaire", "admin")
    assert e.sans_fiche == ["Racine", "Autre"] and any("saisi à la main" in a for a in e.alertes)


async def test_manuel_donjon_incomplet_et_fichier_invalide(tmp_path):
    cache = cache_manuel(tmp_path / "cache")
    (cache / "dungeon-90.json").write_text(json.dumps({"id": 90, "achievements": [33]}))
    f = tmp_path / "etage-0.yaml"
    f.write_text(MANUEL, encoding="utf-8")
    e = await construire_manuel(lire_etage_manuel(f), ClientEnCache(None, cache), set())
    assert "1 succès au lieu de 5" in e.alertes[0] and all(q.nature == "secondaire" for q in e.quetes)
    f.write_text("etage: 0\nblocs: oui\n", encoding="utf-8")
    with pytest.raises(k.ConfigInvalide):
        lire_etage_manuel(f)


def test_commande_manuel_a_blanc(tmp_path, monkeypatch, capsys):
    racine = tmp_path
    (racine / "config" / "etages-manuels").mkdir(parents=True)
    (racine / "config" / "etages-manuels" / "etage-0.yaml").write_text(MANUEL, encoding="utf-8")
    cache_manuel(racine / "donnees" / "dofusdb")
    monkeypatch.setattr(cli, "RACINE", racine)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert cli.main(["construire", "--etage", "0", "--manuel", "--a-blanc", "--sans-reseau"]) == 0
    assert "saisie manuelle" in capsys.readouterr().out


def test_commande_cache_manquant_sans_reseau(tmp_path, monkeypatch, capsys):
    (tmp_path / "config" / "etages-manuels").mkdir(parents=True)
    (tmp_path / "config" / "etages-manuels" / "etage-0.yaml").write_text(MANUEL, encoding="utf-8")
    monkeypatch.setattr(cli, "RACINE", tmp_path)
    assert cli.main(["construire", "--etage", "0", "--manuel", "--a-blanc", "--sans-reseau"]) == 1
    assert "absent du cache" in capsys.readouterr().err
