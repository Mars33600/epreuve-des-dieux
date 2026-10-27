"""QA, le site : cohérence des chiffres de /api/etat, échappement d'un pseudo piégé, base vide.

La cohérence est vérifiée en recalculant P, S, M à la main à partir des CARTES renvoyées par l'API
(et non avec les fonctions du domaine), sur des registres tirés au hasard.
"""

# ruff: noqa: E402
import pytest

# La page v3 (index.html, /api/etat) n'est plus routée depuis le lot A, et creer_app a changé de forme.
# Ces tests seront réécrits au lot B sur le nouveau modèle (docs/LOTS.md, inventaire) ; leurs idées restent ici.
pytest.skip("page v3 retirée au lot A, tests réécrits au lot B", allow_module_level=True)

from datetime import timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from epreuve.domaine.modeles import EntreeJournal, Grimpeur, Instantane
from epreuve.web.app import construire_etat, creer_app
from epreuve.web.demo import creer_app_demo
from tests.fabrique import AVANT, CONTENUS, ETAGE0, PALIERS, PENDANT, validation

PARIS = ZoneInfo("Europe/Paris")
XSS = "<img src=x onerror=alert(1)>"
XSS2 = "</script><script>alert(2)</script>"


class Source:
    def __init__(self, inst):
        self.inst = inst

    async def charger_instantane(self):
        return self.inst

    async def ping(self):
        return True


def inst(grimpeurs, validations=(), journal=(), etages=(ETAGE0,)):
    return Instantane(tuple(etages), PALIERS, CONTENUS, tuple(grimpeurs), tuple(validations), tuple(journal))


def gr(id_, pseudo, statut="actif", diff="easy", retard=False, niveau=20):
    return Grimpeur(id_, pseudo, "Iop", diff, statut, niveau, PENDANT if retard else AVANT, None if retard else AVANT)


# --- Démo : les chiffres attendus, calculés à la main depuis demo.py -----------------------------


def test_demo_chiffres_calcules_a_la_main():
    """10 comptés (4 Aventuriers, 3 Éclaireurs, 3 Collectionneurs) → M = 4 + 6 + 9 = 19, S = ⌈14,25⌉ = 15.
    Points : Brindille 3, Sélénith 2, Mirelune 2, Nalouette 2 (Aventurier au-dessus), Kaskarot, Gromolo,
    Torvald 1, Cliquetis 1 (quêtes sans full succès), Pépin 0 (annulée), Ombrevive 0 → P = 13."""
    d = TestClient(creer_app_demo()).get("/api/etat").json()
    ec = d["etage_courant"]
    assert ec["jauge"] == {"points": 13, "maximum": 19, "seuil": 15, "pleine": False}
    assert ec["comptes_par_difficulte"] == {"easy": 4, "med": 3, "hard": 3}
    assert (ec["n_comptes"], ec["n_pause"], ec["n_retardataires"]) == (10, 1, 1)
    assert [p["grimpeurs"] for p in ec["paliers"]] == [8, 4, 1]
    pseudos = {g["pseudo"] for g in d["grimpeurs"]}
    assert "Fourbenoire" not in pseudos and len(pseudos) == 12
    assert all("Fourbenoire" not in e["pseudos"] for e in d["fil"])
    fleur = next(g for g in d["grimpeurs"] if g["pseudo"] == "Fleur-de-Bwork")
    assert fleur["retardataire"] is True


# --- Cohérence sur des registres au hasard -------------------------------------------------------

STATUTS = st.sampled_from(["actif", "actif", "actif", "pause", "exclu"])
DIFFS = st.sampled_from(["easy", "med", "hard"])


@st.composite
def registres(draw):
    n = draw(st.integers(0, 14))
    grimpeurs, validations = [], []
    for i in range(1, n + 1):
        grimpeurs.append(
            gr(
                i,
                f"G{i}",
                draw(STATUTS),
                draw(DIFFS),
                draw(st.booleans()),
                draw(st.one_of(st.none(), st.integers(1, 30))),
            )
        )
        for c in draw(st.sets(st.integers(1, 6))):
            statut = draw(st.sampled_from(["acceptee", "acceptee", "annulee", "refusee"]))
            niveau = None if c == 6 else draw(st.integers(10, 23))
            validations.append(
                validation(
                    i,
                    c,
                    niveau=niveau,
                    statut=statut,
                    forcee=draw(st.booleans()),
                    source="declaration" if c == 6 else "manuelle",
                )
            )
    return grimpeurs, validations


@settings(max_examples=150, deadline=None)
@given(registres())
def test_coherence_api(reg):
    grimpeurs, validations = reg
    d = construire_etat(inst(grimpeurs, validations), PENDANT, PARIS)
    ec = d["etage_courant"]
    cartes = d["grimpeurs"]
    comptes = [c for c in cartes if c["statut"] == "actif" and not c["retardataire"]]
    M = sum(c["points_vises"] for c in comptes)
    P = sum(c["points"] for c in comptes)
    S = -(-M * 75 // 100)
    assert ec["jauge"] == {"points": P, "maximum": M, "seuil": S, "pleine": M > 0 and P >= S}
    assert ec["n_comptes"] == len(comptes) == sum(ec["comptes_par_difficulte"].values())
    assert ec["n_pause"] == sum(c["statut"] == "pause" for c in cartes)
    assert ec["n_retardataires"] == sum(c["retardataire"] for c in cartes)
    assert [p["grimpeurs"] for p in ec["paliers"]] == [sum(c["points"] >= k for c in comptes) for k in (1, 2, 3)]
    assert all(c["statut"] != "exclu" for c in cartes)
    assert len(cartes) == sum(g.statut != "exclu" for g in grimpeurs)
    for c in cartes:
        k = c["points"]
        assert all(c["marques"][str(r)] for r in range(1, k + 1))  # points ≥ k ⇒ marques 1..k
        assert c["au_dessus_du_cap"] == (c["niveau"] is not None and c["niveau"] > 20)
        if c["statut"] == "pause":
            assert c["points"] == 0
    classes = {x["classe"]: x for x in d["classes"]}
    assert len(d["classes"]) == 19
    assert classes["Iop"]["actifs"] == sum(c["statut"] == "actif" for c in cartes)
    assert classes["Iop"]["en_pause"] == ec["n_pause"]


# --- Échappement HTML -----------------------------------------------------------------------------


def test_pseudo_piege_jamais_interprete():
    g1, g2 = gr(1, XSS), gr(2, XSS2)
    vs = [validation(1, 1), validation(2, 1)]
    j = [
        EntreeJournal(
            1,
            PENDANT,
            "validation",
            True,
            None,
            {
                "validations": [
                    {"id": vs[0].id, "grimpeur_id": 1, "niveau": 20, "contenu": XSS},
                    {"id": vs[1].id, "grimpeur_id": 2, "niveau": 20, "contenu": "x"},
                ]
            },
        )
    ]
    client = TestClient(creer_app(Source(inst([g1, g2], vs, j)), lambda: True, horloge=lambda: PENDANT))
    html = client.get("/").text
    assert "<img src=x" not in html and "<script>alert(2)" not in html
    assert html.count("</script>") == html.count("<script")  # aucune balise script fermée en avance
    api = client.get("/api/etat").json()
    assert {g["pseudo"] for g in api["grimpeurs"]} == {XSS, XSS2}  # le texte est rendu tel quel
    assert api["fil"][0]["pseudos"] == [XSS, XSS2]


def test_horloge_piegee_en_demo():
    html = TestClient(creer_app_demo()).get('/?horloge="><script>alert(3)</script>').text
    assert "alert(3)" not in html


# --- Base vide ------------------------------------------------------------------------------------


def test_aucun_etage_aucun_grimpeur():
    client = TestClient(creer_app(Source(inst([], etages=())), lambda: True, horloge=lambda: PENDANT))
    r = client.get("/api/etat")
    assert r.status_code == 200
    d = r.json()
    assert d["etage_courant"] is None and d["grimpeurs"] == [] and d["fil"] == []
    assert d["tour"] == [{"numero": 0, "nom": None, "statut": "scelle"}]
    assert d["ouverture_etage0"] is None and len(d["classes"]) == 19
    assert client.get("/").status_code == 200


def test_etage_ouvert_sans_grimpeur_apres_la_date_plancher():
    apres = ETAGE0.date_plancher_suivant + timedelta(days=1)
    d = construire_etat(inst([]), apres, PARIS)
    ec = d["etage_courant"]
    assert ec["jauge"] == {"points": 0, "maximum": 0, "seuil": 0, "pleine": False}
    assert ec["deblocable"] is False


def client_async(source):
    """Même boucle d'événements que le moteur Postgres (TestClient en ouvrirait une autre)."""
    app = creer_app(source, lambda: True, horloge=lambda: PENDANT)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_base_postgres_vide(depot):
    async with client_async(depot) as client:
        r = await client.get("/api/etat")
        assert r.status_code == 200 and r.json()["etage_courant"] is None
        assert r.json()["grimpeurs"] == [] and len(r.json()["classes"]) == 19
        assert (await client.get("/")).status_code == 200
        assert (await client.get("/sante")).json() == {"discord": "ok", "base": "ok"}


async def test_base_postgres_etage_importe_sans_grimpeur(etage0):
    async with client_async(etage0) as client:
        d = (await client.get("/api/etat")).json()
    assert d["etage_courant"]["jauge"] == {"points": 0, "maximum": 0, "seuil": 0, "pleine": False}
    assert d["etage_courant"]["ouvert_le"] == "2026-10-30T17:00:00+01:00"
    assert d["etage_courant"]["date_plancher_suivant"] == "2026-11-13T17:00:00+01:00"
