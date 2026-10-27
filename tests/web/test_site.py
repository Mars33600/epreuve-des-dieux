"""Le site : /api/etat conforme au contrat, sécurité de l'affichage, santé, panne de base.

Sans base : une fausse source fournit l'instantané. Le TestClient de FastAPI appelle l'application
directement, sans serveur réseau. Le JavaScript pur (compte à rebours) tourne dans V8 (mini-racer).
"""

# ruff: noqa: E402
import pytest

# La page v3 (index.html, /api/etat) n'est plus routée depuis le lot A, et creer_app a changé de forme.
# Ces tests seront réécrits au lot B sur le nouveau modèle (docs/LOTS.md, inventaire) ; leurs idées restent ici.
pytest.skip("page v3 retirée au lot A, tests réécrits au lot B", allow_module_level=True)

from datetime import UTC, datetime, timedelta
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient
from py_mini_racer import MiniRacer

from epreuve.domaine.modeles import EntreeJournal, Etage, Instantane
from epreuve.web.app import construire_etat, creer_app
from epreuve.web.demo import creer_app_demo
from tests.fabrique import CONTENUS, ETAGE0, PALIERS, PARIS, PENDANT, faits, grimpeur, validation

APP_JS = Path(__file__).resolve().parents[2] / "src/epreuve/web/static/app.js"
XSS = "<img src=x onerror=alert(1)>"

# --- Le schéma JSON du contrat de /api/etat (docs/LOTS.md, interface 5) -----------------------------
DATE = {"type": "string", "pattern": r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+0[12]:00$"}
DATE_OU_NULL = {"anyOf": [DATE, {"type": "null"}]}
ENTIER = {"type": "integer", "minimum": 0}
SCHEMA = {
    "type": "object",
    "required": ["genere_le", "ouverture_etage0", "tour", "etage_courant", "classes", "grimpeurs", "fil"],
    "properties": {
        "genere_le": DATE,
        "ouverture_etage0": DATE_OU_NULL,
        "tour": {"type": "array", "items": {
            "type": "object", "required": ["numero", "nom", "statut"],
            "properties": {"numero": ENTIER, "nom": {"type": ["string", "null"]},
                           "statut": {"enum": ["scelle", "ouvert", "termine"]}}}},
        "etage_courant": {"anyOf": [{"type": "null"}, {
            "type": "object",
            "required": ["numero", "nom", "level_cap", "seuil_pourcent", "donjons", "zone_quetes", "ouvert_le",
                         "date_plancher_suivant", "n_comptes", "n_pause", "n_retardataires", "jauge",
                         "comptes_par_difficulte", "paliers", "deblocable"],
            "properties": {
                "numero": ENTIER, "nom": {"type": "string"}, "level_cap": ENTIER,
                "seuil_pourcent": {"type": "integer", "minimum": 1, "maximum": 100},
                "donjons": {"type": "array", "items": {"type": "string"}}, "zone_quetes": {"type": "string"},
                "ouvert_le": DATE_OU_NULL, "date_plancher_suivant": DATE_OU_NULL,
                "n_comptes": ENTIER, "n_pause": ENTIER, "n_retardataires": ENTIER,
                "jauge": {"type": "object", "required": ["points", "maximum", "seuil", "pleine"],
                          "properties": {"points": ENTIER, "maximum": ENTIER, "seuil": ENTIER,
                                         "pleine": {"type": "boolean"}}},
                "comptes_par_difficulte": {"type": "object", "required": ["easy", "med", "hard"],
                                           "additionalProperties": ENTIER},
                "paliers": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
                    "type": "object", "required": ["rang", "libelle", "grimpeurs"],
                    "properties": {"rang": {"enum": [1, 2, 3]}, "libelle": {"type": "string"},
                                   "grimpeurs": ENTIER}}},
                "deblocable": {"type": "boolean"}}}]},
        "classes": {"type": "array", "minItems": 19, "maxItems": 19, "items": {
            "type": "object", "required": ["classe", "actifs", "en_pause"],
            "properties": {"classe": {"type": "string"}, "actifs": ENTIER, "en_pause": ENTIER}}},
        "grimpeurs": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "pseudo", "classe", "difficulte", "statut", "retardataire", "niveau",
                         "au_dessus_du_cap", "points", "points_vises", "marques"],
            "properties": {
                "id": ENTIER, "pseudo": {"type": "string"}, "classe": {"type": "string"},
                "difficulte": {"enum": ["easy", "med", "hard"]}, "statut": {"enum": ["actif", "pause"]},
                "retardataire": {"type": "boolean"}, "niveau": {"type": ["integer", "null"]},
                "au_dessus_du_cap": {"type": "boolean"}, "points": {"type": "integer", "minimum": 0, "maximum": 3},
                "points_vises": {"enum": [1, 2, 3]},
                "marques": {"type": "object", "required": ["1", "2", "3"], "additionalProperties": False,
                            "properties": {k: {"type": "boolean"} for k in ("1", "2", "3")}}}}},
        "fil": {"type": "array", "maxItems": 30, "items": {
            "type": "object", "required": ["horodatage", "pseudos", "texte"],
            "properties": {"horodatage": DATE, "pseudos": {"type": "array", "items": {"type": "string"}},
                           "texte": {"type": "string"}}}},
    },
}  # fmt: skip


def entree(id_, quand, lignes, type_="validation"):
    return EntreeJournal(id_, quand, type_, True, None, {"validations": lignes})


def instantane_exemple(pseudo_piege=XSS) -> Instantane:
    grimpeurs = (
        grimpeur(1, pseudo="Mirelune", classe="Crâ", niveau=19, difficulte="med"),
        grimpeur(2, pseudo="Ombrevive", classe="Sram", niveau=21),
        grimpeur(3, pseudo="Torvald", classe="Sacrieur", niveau=20, difficulte="hard"),
        grimpeur(4, pseudo="Vieux-Grain", classe="Féca", statut="pause", niveau=None, difficulte="med"),
        grimpeur(5, pseudo="Fourbenoire", classe="Roublard", statut="exclu"),
        grimpeur(6, pseudo=pseudo_piege, classe="Iop"),
        grimpeur(7, pseudo="Fleur", classe="Sadida", niveau=14, retard=True),
    )
    v1, v2, v3 = validation(1, 1), validation(5, 1), validation(3, 1, statut="annulee")
    v4 = validation(7, 6, niveau=None, source="declaration")
    validations = (v1, v2, v3, v4, *faits(1, (2, 3, 4, 5)), *faits(4))
    journal = (
        entree(4, PENDANT + timedelta(hours=1), [{"id": v4.id, "grimpeur_id": 7, "niveau": None,
                                                  "contenu": "Toutes les quêtes d'Incarnam"}], "declaration"),
        entree(3, PENDANT, [{"id": v3.id, "grimpeur_id": 3, "niveau": 20, "contenu": "Kardorim vaincu"}]),
        entree(2, PENDANT - timedelta(hours=1), [
            {"id": v1.id, "grimpeur_id": 1, "niveau": 20, "contenu": "Kardorim vaincu"},
            {"id": v2.id, "grimpeur_id": 5, "niveau": 20, "contenu": "Kardorim vaincu"},
        ]),
        EntreeJournal(1, PENDANT - timedelta(hours=2), "inscription", True, None, {}),
    )
    etage1 = Etage(2, 1, "Nom secret", 30, 75, "scelle", None, None, "Astrub", ("Bouftou",))
    return Instantane((ETAGE0, etage1), PALIERS, CONTENUS, grimpeurs, validations, journal)


class Source:
    def __init__(self, inst=None, base_ok=True, panne=False):
        self.inst, self.base_ok, self.panne = inst or instantane_exemple(), base_ok, panne

    async def charger_instantane(self):
        if self.panne:
            raise ConnectionError("base injoignable : mot de passe=secret")
        return self.inst

    async def ping(self):
        return self.base_ok


def client(source=None, discord=True, **kw):
    app = creer_app(source or Source(), discord_connecte=lambda: discord, horloge=lambda: PENDANT, **kw)
    return TestClient(app, raise_server_exceptions=False)


def toutes_les_cles(objet):
    if isinstance(objet, dict):
        for k, v in objet.items():
            yield k
            yield from toutes_les_cles(v)
    elif isinstance(objet, list):
        for v in objet:
            yield from toutes_les_cles(v)


# --- /api/etat ---------------------------------------------------------------------------------------


def test_api_etat_conforme_au_schema():
    r = client().get("/api/etat")
    assert r.status_code == 200 and r.headers["cache-control"] == "max-age=30"
    jsonschema.validate(r.json(), SCHEMA)


def test_api_etat_jauge():
    etat = client().get("/api/etat").json()
    assert etat["genere_le"].endswith("+01:00")
    assert etat["ouverture_etage0"] == "2026-10-30T17:00:00+01:00"
    assert etat["tour"] == [{"numero": 0, "nom": "Le Seuil", "statut": "ouvert"},
                            {"numero": 1, "nom": None, "statut": "scelle"}]  # nom d'un étage scellé : caché
    ec = etat["etage_courant"]
    assert ec["date_plancher_suivant"] == "2026-11-13T17:00:00+01:00"
    assert (ec["n_comptes"], ec["n_pause"], ec["n_retardataires"]) == (4, 1, 1)
    # Comptés : Mirelune (2), Ombrevive (1), Torvald (3), le pseudo piège (1) → maximum 7, seuil 6.
    # Points : Mirelune 2 (full succès) ; Fleur (retardataire) a déclaré les quêtes sans le 33 → 0.
    assert ec["jauge"] == {"points": 2, "maximum": 7, "seuil": 6, "pleine": False}
    assert ec["comptes_par_difficulte"] == {"easy": 2, "med": 1, "hard": 1}
    assert ec["paliers"] == [{"rang": 1, "libelle": "Kardorim vaincu", "grimpeurs": 1},
                             {"rang": 2, "libelle": "Kardorim full succès", "grimpeurs": 1},
                             {"rang": 3, "libelle": "Toutes les quêtes d'Incarnam", "grimpeurs": 0}]
    assert [c["classe"] for c in etat["classes"]][:3] == ["Féca", "Osamodas", "Enutrof"]


def test_aucun_exclu_ni_identifiant_discord_ni_activite():
    etat = client().get("/api/etat").json()
    assert "Fourbenoire" not in str(etat)
    cles = [k.lower() for k in toutes_les_cles(etat)]
    assert not [k for k in cles if k.startswith("discord") or "activite" in k]
    roublard = next(c for c in etat["classes"] if c["classe"] == "Roublard")
    assert roublard == {"classe": "Roublard", "actifs": 0, "en_pause": 0}


def test_grimpeurs_tries_actifs_puis_alphabetique():
    g = client().get("/api/etat").json()["grimpeurs"]
    assert [x["pseudo"] for x in g] == [XSS, "Fleur", "Mirelune", "Ombrevive", "Torvald", "Vieux-Grain"]
    par = {x["pseudo"]: x for x in g}
    assert par["Ombrevive"]["au_dessus_du_cap"] and not par["Torvald"]["au_dessus_du_cap"]
    assert par["Mirelune"]["marques"] == {"1": True, "2": True, "3": False}
    assert (par["Mirelune"]["points"], par["Mirelune"]["points_vises"]) == (2, 2)
    assert par["Fleur"]["retardataire"] and par["Fleur"]["marques"]["3"] and par["Fleur"]["points"] == 0
    assert par["Vieux-Grain"]["points"] == 0  # en pause : ne rapporte rien, même avec tout fait


def test_fil_validations_et_declarations_sans_annulees_exclus_ni_registre():
    fil = client().get("/api/etat").json()["fil"]
    assert [(f["pseudos"], f["texte"]) for f in fil] == [
        (["Fleur"], "a déclaré avoir terminé « Toutes les quêtes d'Incarnam »."),
        (["Mirelune"], "a validé « Kardorim vaincu » (niv. 20)."),
    ]


def test_fil_limite_a_30():
    inst = instantane_exemple()
    v = validation(1, 6, niveau=None, source="declaration")
    ligne = [{"id": v.id, "grimpeur_id": 1, "niveau": None, "contenu": "Quêtes"}]
    journal = tuple(entree(i, PENDANT - timedelta(minutes=i), ligne, "declaration") for i in range(40))
    inst = Instantane(inst.etages, inst.paliers, inst.contenus, inst.grimpeurs, (*inst.validations, v), journal)
    assert len(client(Source(inst)).get("/api/etat").json()["fil"]) == 30


def test_sans_etage():
    etat = construire_etat(Instantane((), (), (), (grimpeur(1),), (), ()), PENDANT, PARIS)
    assert etat["etage_courant"] is None and etat["ouverture_etage0"] is None
    assert etat["tour"] == [{"numero": 0, "nom": None, "statut": "scelle"}]
    g = etat["grimpeurs"][0]
    assert g["marques"] == {"1": False, "2": False, "3": False} and g["points"] == 0
    jsonschema.validate(etat, SCHEMA)


def test_etage_termine_garde_son_nom():
    termine = Etage(1, 0, "Le Seuil", 20, 75, "termine", None, None, "", ())
    etat = construire_etat(Instantane((termine,), (), (), (), (), ()), PENDANT, PARIS)
    assert etat["tour"] == [{"numero": 0, "nom": "Le Seuil", "statut": "termine"},
                            {"numero": 1, "nom": None, "statut": "scelle"}]


def test_paliers_manquants_toujours_trois_entrees():
    inst = instantane_exemple()
    inst = Instantane(inst.etages, PALIERS[:2], inst.contenus, inst.grimpeurs, inst.validations, ())
    etat = construire_etat(inst, PENDANT, PARIS)
    assert [p["libelle"] for p in etat["etage_courant"]["paliers"]][2] == "Palier 3"
    jsonschema.validate(etat, SCHEMA)


# --- Sécurité de l'affichage ----------------------------------------------------------------------


def test_pseudo_piege_jamais_interprete_par_le_gabarit():
    r = client().get("/")
    assert r.status_code == 200
    assert XSS not in r.text  # pas tel quel dans la page…
    assert "\\u003cimg src=x onerror=alert(1)\\u003e" in r.text  # …mais échappé dans le JSON initial


def test_app_js_n_insere_jamais_de_html():
    source = APP_JS.read_text(encoding="utf-8")
    for interdit in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert interdit not in source, interdit


# --- Santé et pannes ------------------------------------------------------------------------------


@pytest.mark.parametrize(("discord", "base", "code"), [(True, True, 200), (True, False, 503), (False, True, 503)])
def test_sante(discord, base, code):
    r = client(Source(base_ok=base), discord=discord).get("/sante")
    assert r.status_code == code
    assert r.json() == {"discord": "ok" if discord else "ko", "base": "ok" if base else "ko"}


def test_base_injoignable_message_clair_sans_trace():
    c = client(Source(panne=True))
    r = c.get("/api/etat")
    assert r.status_code == 503
    assert r.json() == {"erreur": "Les données sont momentanément indisponibles. Réessaie dans une minute."}
    page = c.get("/")
    assert page.status_code == 200 and "momentanément indisponibles" in page.text
    for texte in (r.text, page.text):
        assert "Traceback" not in texte and "secret" not in texte


def test_base_injoignable_sert_le_dernier_etat_connu():
    source = Source()
    c = client(source)
    premier = c.get("/api/etat").json()
    source.panne = True
    r = c.get("/api/etat")
    assert r.status_code == 200 and r.headers["x-etat-perime"] == "1" and r.json() == premier


def test_erreur_imprevue_sans_trace():
    class Cassee(Source):
        async def ping(self):
            raise RuntimeError("détail interne")

    r = client(Cassee()).get("/sante")
    assert r.status_code == 500 and "détail interne" not in r.text and "Traceback" not in r.text


def test_site_en_lecture_seule():
    c = client()
    assert c.post("/api/etat").status_code == 405
    assert c.get("/docs").status_code == 404  # pas de documentation automatique exposée


# --- Démo locale ----------------------------------------------------------------------------------


def test_demo_clairement_marquee_et_horloge_simulee():
    c = TestClient(creer_app_demo())
    page = c.get("/")
    assert "Démonstration locale" in page.text and "fictifs" in page.text and "(démo)" in page.text
    assert 'data-horloge="2026-11-08T18:00:00+01:00"' in page.text
    etat = c.get("/api/etat").json()
    jsonschema.validate(etat, SCHEMA)
    assert etat["etage_courant"]["jauge"] == {"points": 13, "maximum": 19, "seuil": 15, "pleine": False}
    assert "Fourbenoire" not in str(etat) and "Pépin-Lagrume" in str(etat)
    assert all("Pépin-Lagrume" not in f["pseudos"] for f in etat["fil"])  # validation annulée
    assert c.get("/api/etat?horloge=2026-11-13T17:00").json()["genere_le"] == "2026-11-13T17:00:00+01:00"
    assert c.get("/api/etat?horloge=nimporte").json()["genere_le"] == "2026-11-08T18:00:00+01:00"
    assert c.get("/api/etat?horloge=2026-11-16T10:00:00%2B00:00").json()["genere_le"] == "2026-11-16T11:00:00+01:00"


def test_horloge_ignoree_hors_demo():
    assert client().get("/api/etat?horloge=2030-01-01T00:00").json()["genere_le"] == "2026-11-02T17:00:00+01:00"


def test_horloge_par_defaut_est_l_heure_reelle():
    genere = TestClient(creer_app(Source(), discord_connecte=lambda: True)).get("/api/etat").json()["genere_le"]
    assert abs(datetime.fromisoformat(genere) - datetime.now(UTC)) < timedelta(minutes=1)


# --- Le compte à rebours de app.js (exécuté dans V8, sans navigateur) -----------------------------


@pytest.fixture(scope="module")
def js():
    ctx = MiniRacer()
    ctx.eval(APP_JS.read_text(encoding="utf-8"))
    return ctx


def compte(js, quand: str, pleine: bool = False):
    etat = ('{"ouverture_etage0": "2026-10-30T17:00:00+01:00", "etage_courant": {"numero": 0, '
            f'"date_plancher_suivant": "2026-11-13T17:00:00+01:00", "jauge": {{"pleine": {str(pleine).lower()}}}}}}}')
    return js.eval(f"JSON.stringify(Epreuve.compteARebours(new Date('{quand}'), {etat}))")


def test_compte_a_rebours_avant_pendant_apres(js):
    assert compte(js, "2026-10-30T16:59:00+01:00") == \
        '{"libelle":"Ouverture de l\'étage 0","cible":"2026-10-30T16:00:00.000Z"}'
    assert compte(js, "2026-10-30T17:00:00+01:00") == \
        '{"libelle":"Étage 1 déblocable au plus tôt","cible":"2026-11-13T16:00:00.000Z"}'
    assert compte(js, "2026-11-13T17:00:00+01:00") == "null"  # jauge pas pleine : il disparaît
    assert compte(js, "2026-11-13T17:00:00+01:00", pleine=True) == \
        '{"libelle":"Étage 1","texte":"Étage 1 déblocable"}'


def test_fonctions_js_pures(js):
    assert js.eval("Epreuve.duree(3*864e5 + 4*36e5 + 7*6e4)") == "3 j 04 h 07"
    now = "new Date('2026-11-08T18:00:00Z')"
    assert js.eval(f"Epreuve.ilYA(new Date('2026-11-08T17:59:50Z'), {now})") == "à l'instant"
    assert js.eval(f"Epreuve.ilYA(new Date('2026-11-08T17:30:00Z'), {now})") == "il y a 30 min"
    assert js.eval(f"Epreuve.ilYA(new Date('2026-11-08T16:00:00Z'), {now})") == "il y a 2 h"
    assert js.eval(f"Epreuve.ilYA(new Date('2026-11-07T12:00:00Z'), {now})") == "hier"
    assert js.eval(f"Epreuve.ilYA(new Date('2026-11-05T12:00:00Z'), {now})") == "il y a 3 j"
    tri = js.eval("JSON.stringify(Epreuve.trierGrimpeurs([{pseudo:'b',statut:'pause'},{pseudo:'Z',statut:'actif'},"
                  "{pseudo:'a',statut:'actif'}]).map(g => g.pseudo))")
    assert tri == '["a","Z","b"]'
