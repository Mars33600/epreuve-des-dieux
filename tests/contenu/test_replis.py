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
    (dossier / "dungeon-index.json").write_text(json.dumps([{"id": 90, "name": {"fr": "Crypte de Kardorim"}}]))
    return dossier


def test_guides_repli_vers_duffus_par_le_nom():
    g = k.guides_repli_vers_duffus({"Dofus Kaliptus": {1: "  l'anneau DE TOUS les dangers ", 2: "Inconnue"}}, ASPI)
    assert g == {"Dofus Kaliptus": frozenset({1})}


async def test_completer_par_dofusdb(tmp_path):
    client = ClientEnCache(None, cache_kardorim(tmp_path))
    e = k.construire(0, ASPI, k.lire_config_etages(), k.lire_dofus_retenus())
    vide = k.DonjonPrepare("crypte", "Crypte de Kardorim", 10, 1, None, None, "duffus", ())
    perdu = k.DonjonPrepare("perdu", "Donjon perdu", 10, 2, None, None, "duffus", (), "Boss Perdu")
    e.donjons = [vide, perdu, e.donjons[0]]
    e.alertes.append("donjon « Crypte de Kardorim » : succès introuvables chez Duffus, repli DofusDB à faire")
    e = await k.completer_par_dofusdb(e, client)
    d = e.donjons[0]
    assert (d.succes_source, d.dofusdb_id, len(d.cases), d.cases[0].est_classique) == ("dofusdb", 90, 5, True)
    assert [c.ordre for c in d.cases] == [1, 2, 3, 4, 5] and d.cases[0].duffus_id == "dofusdb:33"
    assert e.donjons[2].succes_source == "duffus"
    # Introuvable partout : la case classique seule, pour que le donjon compte au point Donjons.
    (seule,) = e.donjons[1].cases
    assert (seule.duffus_id, seule.nom, seule.condition, seule.est_classique) == (
        "classique:perdu", "Donjon perdu", "Vaincre Boss Perdu dans son donjon.", True)
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


# --- Les donjons incomplets chez Duffus, sur l'aspiration et le cache DofusDB réels (sans réseau) -----------

CACHE_REEL = Path(__file__).resolve().parents[2] / "donnees" / "dofusdb"
_ETAGES: dict[int, k.EtagePrepare] = {}


async def etage_reel(numero: int) -> k.EtagePrepare:
    """L'étage construit comme `python -m epreuve.contenu construire --sans-reseau` (une fois par étage)."""
    if numero not in _ETAGES:
        client = ClientEnCache(None, CACHE_REEL)
        e = k.construire(numero, ASPI, k.lire_config_etages(), k.lire_dofus_retenus(), forcer=True)
        _ETAGES[numero] = await k.completer_regles(await k.completer_par_dofusdb(e, client), client)
    return _ETAGES[numero]


# (étage, slug Duffus, ids des cases, suffixes des défis). Duffus trouvait la classique (ou rien) : son nom de page
# ou de boss diffère du jeu (« Chafer Ronin »/« Rōnin », « Chouque »/« Le Chouque », « Nagate »/« Nagate la Dame
# des eaux », « Maitre »/« Maître », « Chaloeil »/« Chalœil », « Cavernes Givrefoux » pour la Tanière…).
INCOMPLETS_CHEZ_DUFFUS = [
    (2, "donjon-des-squelettes", ["49", "dofusdb:494", "dofusdb:666", "dofusdb:667", "dofusdb:6154"],
     ["Duo", "Nomade", "Premier", "Spécial"]),
    (6, "bateau-du-chouque", ["1398", "dofusdb:1399", "dofusdb:1402", "dofusdb:1403", "dofusdb:6174"],
     ["Duo", "Dernier", "Nomade", "Spécial"]),
    (8, "bibliotheque-du-maitre-corbac", ["dofusdb:25", "dofusdb:515", "dofusdb:708", "dofusdb:709", "dofusdb:6188"],
     ["Duo", "Collant", "Premier", "Spécial"]),
    (10, "vallee-de-la-dame-des-eaux", ["3020", "dofusdb:3023", "dofusdb:3021", "dofusdb:3022", "dofusdb:6201"],
     ["Duo", "Nomade", "Prudent", "Spécial"]),
    (14, "taniere-givrefoux", ["dofusdb:31", "dofusdb:538", "dofusdb:748", "dofusdb:749", "dofusdb:6218"],
     ["Duo", "Premier", "Statue", "Spécial"]),
    # Le Chalœil, le Vénérable et la Déchireuse n'ont pas de Duo en jeu : un « Trio » à la place.
    (18, "defi-du-chaloeil", ["1437", "dofusdb:1438", "dofusdb:1439", "dofusdb:1440", "dofusdb:6244"],
     ["Liberté", "Prudent", "Trio", "Spécial"]),
    (23, "breuil-du-venerable", ["8849", "dofusdb:8850", "dofusdb:8851", "dofusdb:8852", "dofusdb:8853"],
     ["Premier", "Hardi", "Trio", "Spécial"]),
    (23, "autel-de-la-dechireuse", ["8833", "dofusdb:8834", "dofusdb:8835", "dofusdb:8836", "dofusdb:8837"],
     ["Nomade", "Trio", "En ligne de mire", "Spécial"]),
]


@pytest.mark.parametrize(("numero", "slug", "ids", "defis"), INCOMPLETS_CHEZ_DUFFUS)
async def test_donjon_incomplet_chez_duffus_complete_par_dofusdb(numero, slug, ids, defis):
    e = await etage_reel(numero)
    d = next(d for d in e.donjons if d.duffus_id == slug)
    assert [c.duffus_id for c in d.cases] == ids and d.succes_source == "dofusdb"
    assert [c.nom.rsplit("(", 1)[-1].rstrip(")") for c in d.cases[1:]] == defis
    assert [c.est_classique for c in d.cases] == [True, False, False, False, False]
    assert [c.ordre for c in d.cases] == [1, 2, 3, 4, 5] and all(c.condition for c in d.cases)
    assert not any(f"« {d.nom} » : 1 succès" in a or f"« {d.nom} » : succès introuvables" in a for a in e.alertes)


@pytest.mark.parametrize(("numero", "slug", "boss"), [(22, "caverne-de-cire-momore", "Cire Momore"),
                                                     (23, "temple-de-gargandyas", "Gargandyas")])
async def test_donjon_sans_succes_nulle_part_garde_sa_classique(numero, slug, boss):
    """Ni Duffus (aucun succès) ni DofusDB (aucun donjon de ce nom) : seule la case « vaincre le boss »."""
    e = await etage_reel(numero)
    d = next(d for d in e.donjons if d.duffus_id == slug)
    (c,) = d.cases
    assert (c.duffus_id, c.est_classique, c.condition) == (f"classique:{slug}", True,
                                                           f"Vaincre {boss} dans son donjon.")
    assert any(f"« {d.nom} » : introuvable chez DofusDB" in a for a in e.alertes)


async def test_tous_les_donjons_des_etages_0_a_23():
    """Après correction, seuls les deux donjons sans succès en jeu n'ont pas 5 cases."""
    a_part = {(d.duffus_id, len(d.cases)) for n in range(24) for d in (await etage_reel(n)).donjons
              if len(d.cases) != 5}
    assert a_part == {("caverne-de-cire-momore", 1), ("temple-de-gargandyas", 1)}


def _case(i: str, ordre: int, classique: bool = False) -> k.CasePreparee:
    return k.CasePreparee(i, ordre, f"S{i}", "règle", classique)


def test_fusion_garde_les_cases_duffus_et_dedoublonne():
    duffus = (_case("1", 1, True),)
    dofusdb = (_case("dofusdb:1", 1, True), _case("dofusdb:2", 2), _case("dofusdb:2", 3), _case("dofusdb:3", 4))
    assert [(c.duffus_id, c.ordre) for c in k.fusionner_cases(duffus, dofusdb)] == [
        ("1", 1), ("dofusdb:2", 2), ("dofusdb:3", 3)]
    # Un succès Duffus absent chez DofusDB : les sources se contredisent, pas de mélange.
    assert k.fusionner_cases((_case("9", 1, True),), dofusdb) is None


async def test_dofusdb_n_apporte_rien_les_cases_duffus_restent(tmp_path):
    cache = cache_kardorim(tmp_path)
    (cache / "dungeon-90.json").write_text(json.dumps({"id": 90, "achievements": [33]}))
    duffus = (_case("33", 1, True), _case("487", 2))
    e = k.EtagePrepare(0, "É", "1-20", 1, 20, 20, None, None, None,
                       alertes=["donjon « Crypte » : 2 succès au lieu de 5"],
                       donjons=[k.DonjonPrepare("c", "Crypte", 10, 1, None, 90, "duffus", duffus)])
    e = await k.completer_par_dofusdb(e, ClientEnCache(None, cache))
    assert e.donjons[0].cases == duffus and e.donjons[0].succes_source == "duffus"
    assert e.alertes == ["donjon « Crypte » : 2 succès au lieu de 5"]  # l'alerte de la construction reste


async def test_completer_remplace_l_alerte_de_construction(tmp_path):
    e = k.EtagePrepare(0, "É", "1-20", 1, 20, 20, None, None, None,
                       alertes=["donjon « Crypte » : 1 succès au lieu de 5"],
                       donjons=[k.DonjonPrepare("c", "Crypte", 10, 1, None, 90, "duffus", (_case("33", 1, True),))])
    e = await k.completer_par_dofusdb(e, ClientEnCache(None, cache_kardorim(tmp_path)))
    assert e.donjons[0].cases[0].duffus_id == "33" and len(e.donjons[0].cases) == 5
    assert e.alertes == ["donjon « Crypte » : succès pris chez DofusDB (repli)"]


async def test_donjon_sans_succes_chez_dofusdb_garde_sa_classique(tmp_path):
    cache = cache_kardorim(tmp_path)
    (cache / "dungeon-90.json").write_text(json.dumps({"id": 90, "achievements": []}))
    e = k.EtagePrepare(0, "É", "1-20", 1, 20, 20, None, None, None,
                       donjons=[k.DonjonPrepare("c", "Crypte", 10, 1, None, 90, "duffus", ())])
    e = await k.completer_par_dofusdb(e, ClientEnCache(None, cache))
    (c,) = e.donjons[0].cases
    assert (c.duffus_id, c.condition, c.est_classique) == ("classique:c", "Vaincre le boss du donjon.", True)
    assert e.donjons[0].dofusdb_id == 90 and "aucun succès chez DofusDB" in e.alertes[0]


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
    (cache / "dungeon-90.json").write_text(json.dumps({"id": 90, "achievements": []}))
    e = await construire_manuel(lire_etage_manuel(f), ClientEnCache(None, cache), set())
    assert [(c.duffus_id, c.est_classique) for c in e.donjons[0].cases] == [("classique:dofusdb:90", True)]
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
