"""L'API JSON (LOTS, lot B, « API JSON ») : forme exacte, tous les codes d'erreur, cascade, coche d'admin.

Critères 11 à 14, 18, 28 bis et 37.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from epreuve.domaine.modeles import Regles
from epreuve.web.demo import ID_MARCEAU, ID_NOUVELLE, _id_discord
from tests.web.outils import ID_BRINDILLE, ID_FOURBE, ID_OMBREVIVE, SITE, cocher, monde


def connecte(discord_id, **kw):
    m = monde(**kw)
    c = m.connecter(discord_id)
    return m, c, m.csrf(c)


def test_forme_exacte_de_la_reponse():
    m, c, t = connecte(_id_discord(5))  # Pépin-Lagrume : 1 case sur le Donjon des Champs
    r = cocher(c, t, type="quete", id=101, cochee=True)
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"ok", "changement", "moi", "jauge", "compteurs"} and d["ok"] is True and d["changement"] is True
    assert set(d["moi"]) == {"points", "categories"}
    assert set(d["moi"]["categories"]) == {"donjons", "full_succes", "principales", "secondaires"}
    assert set(d["moi"]["categories"]["principales"]) == {"faits", "total", "acquise"}
    assert d["moi"]["categories"]["principales"] == {"faits": 1, "total": 4, "acquise": False}
    assert set(d["jauge"]) == {"score", "palier", "actifs", "en_pause", "pleine", "points_par_categorie"}
    assert set(d["jauge"]["points_par_categorie"]) == {"donjons", "full_succes", "principales", "secondaires"}
    assert d["compteurs"] == {"quete:101": 6}  # 5 actifs l'avaient, Pépin en plus
    assert r.headers["cache-control"] == "no-store"


def test_idempotent_double_toucher():
    m, c, t = connecte(ID_BRINDILLE)
    assert cocher(c, t, type="quete", id=107, cochee=True).json()["changement"] is True
    d = cocher(c, t, type="quete", id=107, cochee=True).json()
    assert d["changement"] is False and d["compteurs"] == {}
    assert sum(1 for e in m.depot._journal if e.type == "coche") == 1


def test_cascade_succes_coche_vaincre_le_boss():
    m, c, t = connecte(_id_discord(5))  # Pépin : rien sur la Crypte (cases 21 à 25)
    d = cocher(c, t, type="case", id=23, cochee=True).json()
    assert set(d["compteurs"]) == {"case:23", "case:21"}
    assert {21, 23} <= m.depot._coches_cases[5]


def test_cascade_decocher_la_classique_decoche_les_autres():
    m, c, t = connecte(ID_BRINDILLE)  # Brindille : les 5 cases de la Crypte
    d = cocher(c, t, type="case", id=21, cochee=False).json()
    assert set(d["compteurs"]) == {"case:21", "case:22", "case:23", "case:24", "case:25"}
    assert not {21, 22, 23, 24, 25} & m.depot._coches_cases[1]


def test_sans_cascade_si_le_reglage_est_coupe():
    m, c, t = connecte(_id_discord(5), regles=Regles(succes_coche_vaincu=False))
    d = cocher(c, t, type="case", id=23, cochee=True).json()
    assert set(d["compteurs"]) == {"case:23"}


def test_tout_le_donjon_coche_les_5():
    m, c, t = connecte(_id_discord(5))
    d = cocher(c, t, type="donjon", id=2, cochee=True).json()
    assert set(d["compteurs"]) == {f"case:{i}" for i in range(21, 26)}
    assert cocher(c, t, type="donjon", id=2, cochee=False).status_code == 422


def test_jauge_et_points_mis_a_jour():
    m, c, t = connecte(_id_discord(5))  # Pépin : secondaires 5/5 (1 point)
    avant = cocher(c, t, type="quete", id=101, cochee=False).json()
    assert avant["moi"]["points"] == 1
    for q in (101, 102, 103, 104):
        d = cocher(c, t, type="quete", id=q, cochee=True).json()
    assert d["moi"]["points"] == 2 and d["moi"]["categories"]["principales"]["acquise"] is True
    assert d["jauge"]["score"] == avant["jauge"]["score"] + 1
    ppc, ppc_avant = d["jauge"]["points_par_categorie"], avant["jauge"]["points_par_categorie"]
    assert ppc["principales"] == ppc_avant["principales"] + 1


def test_grimpeur_en_pause_coche_sans_compter():
    m, c, t = connecte(ID_OMBREVIVE)
    avant = cocher(c, t, type="quete", id=105, cochee=False).json()["jauge"]["score"]
    d = cocher(c, t, type="donjon", id=1, cochee=True).json()
    assert d["ok"] and d["jauge"]["score"] == avant  # ses points ne comptent pas tant qu'il est gelé


def test_gele_refuse_si_le_reglage_l_interdit():
    m, c, t = connecte(ID_OMBREVIVE, regles=Regles(pause_peut_cocher=False))
    r = cocher(c, t, type="quete", id=105, cochee=True)
    assert r.status_code == 403 and r.json()["ok"] is False


def test_exclu_403():
    m, c, t = connecte(ID_FOURBE)
    assert cocher(c, t, type="quete", id=105, cochee=True).status_code == 403


def test_401_sans_session():
    m = monde()
    r = m.client().post("/api/coches", json={"type": "quete", "id": 101, "cochee": True}, headers={"Origin": SITE})
    assert r.status_code == 401 and r.json() == {"ok": False, "message": "Ta session a expiré : reconnecte-toi."}


@pytest.mark.parametrize("entetes", [{"X-CSRF-Token": "faux", "Origin": SITE}, {"Origin": SITE},
                                     {"X-CSRF-Token": "", "Origin": SITE}])
def test_403_csrf(entetes):
    m, c, t = connecte(ID_BRINDILLE)
    r = c.post("/api/coches", json={"type": "quete", "id": 107, "cochee": True}, headers=entetes)
    assert r.status_code == 403 and r.json()["ok"] is False
    assert 107 not in m.depot._coches_quetes[1]


@pytest.mark.parametrize("entetes", [{"Origin": "https://pirate.example"}, {"Origin": "null"},
                                     {"Referer": "https://pirate.example/page"}, {"Origin": SITE + ".pirate.example"}])
def test_403_origine_etrangere(entetes):
    m, c, t = connecte(ID_BRINDILLE)
    r = c.post("/api/coches", json={"type": "quete", "id": 107, "cochee": True}, headers={"X-CSRF-Token": t, **entetes})
    assert r.status_code == 403


def test_403_cocher_pour_un_autre_sans_etre_admin():
    m, c, t = connecte(ID_BRINDILLE)
    r = cocher(c, t, type="quete", id=107, cochee=True, grimpeur_id=2, motif="je l'ai vu faire")
    assert r.status_code == 403 and 107 not in m.depot._coches_quetes[2]


@pytest.mark.parametrize(("type_", "id_"), [("quete", 999), ("case", 999), ("quete", 201), ("case", 41),
                                            ("donjon", 4), ("donjon", 999)])
def test_404_inconnu_ou_scelle(type_, id_):
    m, c, t = connecte(ID_BRINDILLE)
    r = cocher(c, t, type=type_, id=id_, cochee=True)
    assert r.status_code == 404 and r.json()["ok"] is False


def test_404_element_masque():
    m, c, t = connecte(ID_BRINDILLE)
    m.depot._quetes[107] = replace(m.depot._quetes[107], masquee=True)
    m.depot._donjons[3] = replace(m.depot._donjons[3], masque=True)
    assert cocher(c, t, type="quete", id=107, cochee=True).status_code == 404
    assert cocher(c, t, type="case", id=32, cochee=True).status_code == 404


def test_409_sans_fiche():
    m = monde()
    c = m.connecter(ID_MARCEAU)  # admin sans fiche
    assert cocher(c, m.csrf(c), type="quete", id=101, cochee=True).status_code == 409


def test_409_membre_sans_fiche():
    m = monde()
    c = m.connecter(ID_NOUVELLE)
    r = c.post("/api/coches", json={"type": "quete", "id": 101, "cochee": True}, headers={"Origin": SITE})
    # Pas de page servie avant la fiche, donc pas de jeton CSRF : la requête est refusée avant tout.
    assert r.status_code in (403, 409)


@pytest.mark.parametrize("corps", [
    {}, {"type": "quete"}, {"type": "autre", "id": 1, "cochee": True}, {"type": "quete", "id": "101", "cochee": True},
    {"type": "quete", "id": 101, "cochee": "oui"}, {"type": "quete", "id": 101, "cochee": 1},
    {"type": "quete", "id": True, "cochee": True}, {"type": "quete", "id": 101, "cochee": True, "grimpeur_id": "2"},
    {"type": "quete", "id": 101, "cochee": True, "motif": 3}, [1, 2],
])
def test_422_corps_invalide(corps):
    m, c, t = connecte(ID_BRINDILLE)
    r = c.post("/api/coches", json=corps, headers={"X-CSRF-Token": t, "Origin": SITE})
    assert r.status_code == 422 and r.json()["ok"] is False


def test_422_corps_qui_n_est_pas_du_json():
    m, c, t = connecte(ID_BRINDILLE)
    r = c.post("/api/coches", content=b"{pas du json", headers={"X-CSRF-Token": t, "Origin": SITE,
                                                                "Content-Type": "application/json"})
    assert r.status_code == 422


def test_admin_coche_pour_un_autre_avec_motif():
    m, c, t = connecte(ID_MARCEAU)
    assert cocher(c, t, type="quete", id=104, cochee=False, grimpeur_id=1).status_code == 422
    assert cocher(c, t, type="quete", id=104, cochee=False, grimpeur_id=1, motif="  ").status_code == 422
    r = cocher(c, t, type="quete", id=104, cochee=False, grimpeur_id=1, motif="validation contraire aux règles")
    d = r.json()
    assert r.status_code == 200 and d["changement"] is True
    assert d["moi"]["categories"]["principales"] == {"faits": 3, "total": 4, "acquise": False}  # « moi » = la cible
    entree = m.depot._journal[-1]
    assert entree.public is False and entree.details["motif"] == "validation contraire aux règles"
    assert entree.acteur_discord_id == ID_MARCEAU and entree.grimpeur_id == 1
    # La fiche du grimpeur ne montre ni le motif ni l'auteur (critère 28 bis).
    b = m.connecter(ID_BRINDILLE)
    html = b.get("/grimpeurs/1").text
    assert "validation contraire" not in html and "Marceau" not in html


def test_admin_cible_inconnue_404():
    m, c, t = connecte(ID_MARCEAU)
    assert cocher(c, t, type="quete", id=104, cochee=True, grimpeur_id=999, motif="x").status_code == 404


def test_admin_dont_le_role_a_ete_retire_ne_coche_plus_pour_un_autre():
    m, c, t = connecte(ID_MARCEAU)
    m.membres[ID_MARCEAU] = ("Marceau", frozenset())
    m.avancer(minutes=11)
    assert cocher(c, t, type="quete", id=104, cochee=False, grimpeur_id=1, motif="x").status_code == 403


def test_etage_termine_reste_cochable():
    m, c, t = connecte(ID_BRINDILLE)
    e = m.depot._etages[1]
    m.depot._etages[1] = replace(e, statut="termine")
    assert cocher(c, t, type="quete", id=107, cochee=True).status_code == 200


# ---------------------------------------------------------------- « qui ne l'a pas fait ? »


def test_manque_forme_et_actifs_seulement():
    m, c, t = connecte(ID_BRINDILLE)
    d = c.get("/api/etages/0/manque?type=quete&id=101").json()
    assert set(d) == {"pas_fait", "fait"}
    assert set(d["fait"][0]) == {"id", "pseudo", "classe"}
    ids = {g["id"] for g in d["pas_fait"] + d["fait"]}
    assert 8 not in ids and 12 not in ids and 13 not in ids  # en pause et exclu : jamais
    assert len(ids) == 10
    pseudos = [g["pseudo"] for g in d["pas_fait"]]
    assert pseudos == sorted(pseudos, key=str.casefold)


@pytest.mark.parametrize(("type_", "id_"), [("categorie", "donjons"), ("categorie", "full_succes"),
                                            ("categorie", "principales"), ("categorie", "secondaires"),
                                            ("case", "22"), ("quete", "105"), ("donjon", "3")])
def test_manque_coherent_avec_les_compteurs(type_, id_):
    """Critère 18 : compteur + nombre de « pas fait » = nombre d'actifs, pour chaque élément."""
    m, c, t = connecte(ID_BRINDILLE)
    d = c.get(f"/api/etages/0/manque?type={type_}&id={id_}").json()
    assert len(d["pas_fait"]) + len(d["fait"]) == 10
    if type_ in ("case", "quete"):
        html = c.get("/etages/0").text
        assert f'data-compteur="{type_}:{id_}"' in html
        assert f">{len(d['fait'])}/10</a>" in html.split(f'data-compteur="{type_}:{id_}"')[1][:400]


def test_manque_donjon_egal_vaincre_le_boss():
    m, c, t = connecte(ID_BRINDILLE)
    assert c.get("/api/etages/0/manque?type=donjon&id=3").json() == c.get("/api/etages/0/manque?type=case&id=31").json()


@pytest.mark.parametrize("q", ["type=quete&id=999", "type=categorie&id=bonus", "type=case&id=abc", "type=quete&id=201"])
def test_manque_inconnu_404(q):
    m, c, t = connecte(ID_BRINDILLE)
    assert c.get(f"/api/etages/0/manque?{q}").status_code == 404


def test_manque_requete_invalide_et_etage_scelle():
    m, c, t = connecte(ID_BRINDILLE)
    assert c.get("/api/etages/0/manque?type=autre&id=1").status_code == 422
    assert c.get("/api/etages/1/manque?type=categorie&id=donjons").status_code == 404
    assert c.get("/api/etages/99/manque?type=categorie&id=donjons").status_code == 404
