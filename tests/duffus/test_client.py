"""Le client Duffus avec un faux transport : politesse (débit, User-Agent), pagination, erreurs."""

import httpx
import pytest

from epreuve.duffus.client import USER_AGENT, AccesRefuse, ClientDuffus, ErreurDuffus, lire_environnement


class Horloge:
    """Un temps simulé : `dormir` avance l'horloge au lieu d'attendre."""

    def __init__(self):
        self.t = 1000.0
        self.attentes: list[float] = []

    def __call__(self):
        return self.t

    async def dormir(self, s):
        self.attentes.append(s)
        self.t += s


def client(repondre, horloge=None):
    h = horloge or Horloge()
    return ClientDuffus("https://exemple.supabase.co", "CLE-TEST", transport=httpx.MockTransport(repondre),
                        horloge=h, dormir=h.dormir), h


async def test_entetes_et_debit_au_plus_une_requete_par_seconde():
    vus = []

    def repondre(req):
        vus.append((h.t, req))
        return httpx.Response(200, json=[{"id": 1}])

    c, h = client(repondre)
    async with c:
        for _ in range(4):
            await c.une_ligne("quest_list")
    instants = [t for t, _ in vus]
    assert all(b - a >= 1.0 for a, b in zip(instants, instants[1:], strict=False))
    req = vus[0][1]
    assert req.headers["User-Agent"] == USER_AGENT and "epreuve-des-dieux.fr" in USER_AGENT
    assert req.headers["apikey"] == "CLE-TEST" and req.headers["Authorization"] == "Bearer CLE-TEST"
    assert req.url.path == "/rest/v1/quest_list" and req.url.params["limit"] == "1"


async def test_pagination_par_range():
    lignes = [{"id": i} for i in range(2500)]
    ranges = []

    def repondre(req):
        debut, fin = map(int, req.headers["Range"].split("-"))
        ranges.append((debut, fin))
        assert req.headers["Range-Unit"] == "items" and req.url.params["order"] == "id.asc"
        return httpx.Response(200, json=lignes[debut:fin + 1])

    c, _ = client(repondre)
    async with c:
        assert await c.lire_table("quest_list", "id", filtres={"range_id": "eq.1"}) == lignes
    assert ranges == [(0, 999), (1000, 1999), (2000, 2999)]


@pytest.mark.parametrize("code", [401, 403, 404, 400])
async def test_arret_immediat(code):
    appels = []

    def repondre(req):
        appels.append(req)
        return httpx.Response(code, text="non")

    c, _ = client(repondre)
    async with c:
        with pytest.raises(AccesRefuse if code in (401, 403) else ErreurDuffus):
            await c.une_ligne("quest_list")
    assert len(appels) == 1  # on n'insiste jamais


@pytest.mark.parametrize(("entete", "attente"), [({"Retry-After": "7"}, 7.0), ({}, 30.0), ({"Retry-After": "x"}, 30.0)])
async def test_retry_after_sur_429_puis_succes(entete, attente):
    codes = iter([429, 503, 200])

    def repondre(req):
        code = next(codes)
        return httpx.Response(code, headers=entete, json=[] if code == 200 else None)

    c, h = client(repondre)
    async with c:
        assert await c.une_ligne("quest_list") == []
    assert h.attentes.count(attente) == 2 and c.nb_requetes == 3


async def test_trois_essais_au_plus():
    appels = []

    def repondre(req):
        appels.append(req)
        return httpx.Response(429, headers={"Retry-After": "1"})

    c, _ = client(repondre)
    async with c:
        with pytest.raises(ErreurDuffus, match="3 essais"):
            await c.une_ligne("quest_list")
    assert len(appels) == 3


async def test_openapi_ouverte_fermee_ou_illisible():
    reponses = iter([httpx.Response(200, json={"definitions": {"t": {}}}), httpx.Response(401),
                     httpx.Response(200, text="pas du json"), httpx.Response(200, json={"paths": {}})])
    c, _ = client(lambda req: next(reponses))
    async with c:
        assert await c.openapi() == {"definitions": {"t": {}}}
        assert await c.openapi() is None
        assert await c.openapi() is None
        assert await c.openapi() is None


def test_lire_environnement(monkeypatch):
    monkeypatch.delenv("DUFFUS_SUPABASE_URL", raising=False)
    monkeypatch.delenv("DUFFUS_SUPABASE_CLE", raising=False)
    with pytest.raises(ErreurDuffus):
        lire_environnement()
    monkeypatch.setenv("DUFFUS_SUPABASE_URL", "https://x.supabase.co/")
    monkeypatch.setenv("DUFFUS_SUPABASE_CLE", "k")
    assert lire_environnement() == ("https://x.supabase.co", "k")
