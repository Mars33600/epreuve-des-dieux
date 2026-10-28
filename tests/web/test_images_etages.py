"""Images d'ambiance des étages : WebP de 300 Ko au plus, servies seulement pour un étage visible."""

from pathlib import Path

from tests.web.outils import ID_BRINDILLE, ID_MARCEAU, monde

IMAGES = Path(__file__).resolve().parents[2] / "donnees" / "images" / "etages"


def test_images_webp_de_300_ko_au_plus():
    fichiers = sorted(IMAGES.glob("*.webp"))
    assert [f.name for f in fichiers] == sorted(f"etage-{n}.webp" for n in range(11))
    for f in fichiers:
        assert f.stat().st_size <= 300 * 1024, f.name
        assert f.read_bytes()[8:12] == b"WEBP"


def test_image_d_un_etage_ouvert_servie_au_grimpeur():
    m = monde()
    r = m.connecter(ID_BRINDILLE).get("/etages/0/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert r.headers["cache-control"].startswith("private")


def test_image_d_un_etage_scelle_jamais_servie_a_un_joueur():
    m = monde()
    c = m.connecter(ID_BRINDILLE)
    for n in (1, 2, 3, 4, 10, 99):  # scellés ou inexistants : même réponse
        assert c.get(f"/etages/{n}/image").status_code == 404, n
    assert m.client().get("/etages/0/image").status_code in (303, 401)  # visiteur non connecté


def test_admin_voit_l_image_d_un_etage_scelle():
    m = monde()
    c = m.connecter(ID_MARCEAU)
    assert c.get("/etages/1/image").status_code == 200
    assert c.get("/etages/3/image").status_code == 200
    assert c.get("/etages/../image").status_code == 404
    assert c.get("/etages/4/image").status_code == 404  # pas d'étage 4 dans la démo


def test_aucune_image_sous_static():
    statiques = Path(__file__).resolve().parents[2] / "src" / "epreuve" / "web" / "static"
    assert not list(statiques.rglob("etage-*"))
