"""Recette manuelle du builder (lot E3) dans Chromium sans tête, hors pytest (Playwright n'est pas une dépendance).

    uv run --with playwright python tests/qa/recette_builder.py <dossier des captures>

À 360 et 1440 px : compose un build (Coiffe du Bouftou, Cape Bouffante, Marteau du Bouftou, 100 Force de base,
parchemins à 100), vérifie le total de Force (20 + 10 de panoplie 3/8 + 100 + 100 = 230) et les dégâts d'arme,
l'enregistre, puis contrôle l'absence de défilement horizontal et d'erreur JavaScript.
Sans base : un faux visiteur et un faux dépôt de builds.
"""

import asyncio
import sys
import threading
import time
from pathlib import Path

import uvicorn
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from epreuve.config import Config  # noqa: E402
from epreuve.web.app import creer_app  # noqa: E402
from epreuve.web.builder import ServicesBuilder, Visiteur  # noqa: E402
from tests.builder.test_web import FauxBuilds  # noqa: E402

ADRESSE = "http://127.0.0.1:8765"
LARGEUR_PAGE = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"


def lancer_serveur() -> uvicorn.Server:
    app = creer_app(Config(_env_file=None, SITE_MODE="ouvert"))

    async def identifier(_requete):
        return Visiteur(11, False, "jeton", 1, "Brindille")

    app.state.builder = ServicesBuilder(identifier, builds=FauxBuilds())
    serveur = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning"))
    threading.Thread(target=serveur.run, daemon=True).start()
    time.sleep(1.5)
    return serveur


async def choisir(page, emplacement: int, texte: str, nom: str, niveau_max: str | None = None) -> None:
    await page.click(f".b-emplacement:nth-child({emplacement}) .b-case")
    if niveau_max:
        await page.fill("#f-max", niveau_max)
    await page.fill("#f-texte", texte)
    await page.click(f".b-objet >> text='{nom}'")


async def recette_a(navigateur, largeur: int, sortie: Path) -> list[str]:
    problemes: list[str] = []
    page = await navigateur.new_page(viewport={"width": largeur, "height": 900})
    page.on("pageerror", lambda e: problemes.append(f"{largeur} px : {e}"))
    page.on("console", lambda m: m.type == "error" and problemes.append(f"{largeur} px : {m.text}"))
    await page.goto(f"{ADRESSE}/builder/nouveau")
    await page.wait_for_selector(".b-bulle")
    await page.fill("#b-niveau", "50")
    await page.press("#b-niveau", "Tab")
    await page.click(".b-emplacement:nth-child(1) .b-case")
    if await page.is_visible("#b-retirer"):
        problemes.append(f"{largeur} px : « Retirer l'objet » visible sur un emplacement vide")
    await page.fill("#f-texte", "bouftou")
    await page.wait_for_selector(".b-objet >> text='Coiffe du Bouftou'")
    await page.screenshot(path=str(sortie / f"choix-{largeur}.png"))
    await page.click(".b-objet >> text='Coiffe du Bouftou'")
    await choisir(page, 2, "bouffante", "Cape Bouffante", niveau_max="20")
    await page.wait_for_selector(".b-panoplie")
    await choisir(page, 9, "bouftou", "Marteau du Bouftou", niveau_max="20")
    await page.wait_for_selector("#b-arme table")
    await page.click("[data-buff='base']")
    await page.select_option("#b-classe", "Iop")
    await page.click("#b-sorts-zone summary")
    await page.wait_for_selector(".b-sort")
    champ = "#b-base tbody tr:nth-child(3) td:nth-child(4) input"
    await page.fill(champ, "100")
    await page.press(champ, "Tab")
    await page.click("#b-parcho-tout")
    await page.wait_for_timeout(600)
    force = await page.text_content("#b-base tbody tr:nth-child(3) td:nth-child(2)")
    if force != "230":
        problemes.append(f"{largeur} px : Force {force} au lieu de 230")
    await page.fill("#b-nom", "Recette")
    await page.click("#b-enregistrer")
    await page.wait_for_url(lambda u: u.rstrip("/").split("/")[-1].isdigit())
    pages = {"liste": "/builder", "comparaison": "/builder/comparer?a=1&b=1"}
    for nom in ("éditeur", "liste", "comparaison"):
        if nom in pages:
            await page.goto(ADRESSE + pages[nom])
        defile, visible = await page.evaluate(LARGEUR_PAGE)
        if defile > visible:
            problemes.append(f"{largeur} px : défilement horizontal sur la page {nom}")
        await page.screenshot(path=str(sortie / f"{nom}-{largeur}.png"), full_page=True)
    return problemes


async def principal(sortie: Path) -> int:
    async with async_playwright() as p:
        navigateur = await p.chromium.launch()
        problemes = [x for largeur in (360, 1440) for x in await recette_a(navigateur, largeur, sortie)]
        await navigateur.close()
    print("\n".join(problemes) or "Recette : aucun problème (360 et 1440 px).")
    return 1 if problemes else 0


if __name__ == "__main__":
    serveur = lancer_serveur()
    code = asyncio.run(principal(Path(sys.argv[1])))
    serveur.should_exit = True
    sys.exit(code)
