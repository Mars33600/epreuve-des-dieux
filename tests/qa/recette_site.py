# ruff: noqa: E501, UP031, S310, B904, S110
"""Recette automatisée du site entier dans Chromium sans tête, hors pytest (Playwright n'est pas une dépendance).

    uv run --with playwright python tests/qa/recette_site.py [--mode demo|base|les-deux] [--captures DOSSIER]
                                                              [--largeurs 360,768,1440] [--limite 60]

À chaque largeur (360, 768 et 1440 px) et pour chaque profil (grimpeur, admin) :
- parcourt le menu, le menu déroulant « Monde des Douze », puis chaque lien interne en profondeur 2 (échantillon
  borné par modèle d'adresse), en cliquant le lien depuis la page précédente et en vérifiant le retour arrière ;
- contrôle chaque page : statut 200, aucune erreur JS ni CSP ni requête en échec, aucun défilement horizontal,
  aucun lien ou bouton recouvert (`elementFromPoint` au centre), images cassées ;
- clique les boutons, onglets, filtres, listes déroulantes et fiches de la page, puis recontrôle ;
- teste la recherche globale (saisie progressive, sans Entrée, moins d'une seconde, étage scellé invisible), les
  cases à cocher (jauge, compteurs, persistance, lecture seule chez l'autre) et les fenêtres modales.

`demo` : données fictives en mémoire. `base` : TEST_DATABASE_URL (ou DATABASE_URL, jamais `.env`) remplie par
`python -m epreuve.contenu construire --etage 0|1`, `epreuve.encyclopedie charger` et `epreuve.captures charger`.
Code de sortie 1 s'il reste un défaut ; le détail est écrit dans <captures>/rapport.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

RACINE = Path(__file__).resolve().parents[2]
CAPTURES_DEFAUT = Path("/private/tmp/claude-501/-Users-marceau-home-ai/d7955bda-5c02-4859-a185-89f95d886ccc/"
                       "scratchpad/captures-t1")
HAUTEUR = {360: 740, 768: 1024, 1440: 900}
IGNORES = ("/deconnexion", "/static/", "/api/", "/donnees/", "/auth/", "/demo/", "/connexion", "/etages/0/image",
           "/image", "mailto:", "https://", "http://")  # liens sortants (Duffus) : pas notre site
CLIQUABLES = "a[href], button, input:not([type=hidden]), select, textarea, summary, [role=tab], [role=option]"
DANGEREUX = re.compile(r"déconnecter|supprimer|exclure|geler|réintégrer|ouvrir l'étage|forcer|reset|vider", re.I)

JS_DEBORDEMENT = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
JS_RECOUVERTS = """
(max) => {
  const sortie = [];
  const dansFerme = e => { for (let d = e.parentElement && e.parentElement.closest('details'); d;
    d = d.parentElement && d.parentElement.closest('details')) {
      if (!d.open && !(e.tagName === 'SUMMARY' && e.parentElement === d)) return true; } return false; };
  const els = [...document.querySelectorAll(%r)].filter(e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && !e.disabled
      && !e.closest('[hidden]') && !dansFerme(e)
      && (!document.querySelector('dialog[open]') || e.closest('dialog[open]')) && s.pointerEvents !== 'none' && !e.closest('.sr-only')
      && !(e.type === 'checkbox' || e.type === 'radio') && !e.classList.contains('sr-only');
  }).slice(0, max);
  const estSticky = e => { for (let n = e; n && n !== document.body; n = n.parentElement) {
    const p = getComputedStyle(n).position; if (p === 'fixed' || p === 'sticky') return true; } return false; };
  for (const e of els) {
    e.scrollIntoView({block: estSticky(e) ? 'nearest' : 'center', inline: 'nearest'});
    const r = e.getBoundingClientRect();
    const x = Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2));
    const y = Math.min(innerHeight - 1, Math.max(0, r.top + r.height / 2));
    if (r.right < 0 || r.left > innerWidth || r.bottom < 0 || r.top > innerHeight) {
      sortie.push('hors écran : ' + decrire(e)); continue; }
    const h = document.elementFromPoint(x, y);
    if (h && !(e.contains(h) || h.contains(e) || (e.labels && [...e.labels].some(l => l.contains(h))))) {
      sortie.push(decrire(e) + ' recouvert par ' + decrire(h)); }
  }
  function decrire(n) { return n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') +
    (n.className && typeof n.className === 'string' ? '.' + n.className.trim().split(/\\s+/).slice(0, 2).join('.') : '') +
    ' « ' + (n.textContent || n.value || n.getAttribute('aria-label') || '').trim().slice(0, 30) + ' »'; }
  window.scrollTo(0, 0);
  return sortie;
}
""" % CLIQUABLES
JS_IMAGES = "[...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.src && !i.classList.contains('img-absente')).map(i => i.src)"
JS_TEXTE_COUPE = """
() => [...document.querySelectorAll('main *, .bar *')].filter(e => {
  const s = getComputedStyle(e);
  return e.children.length === 0 && e.textContent.trim().length > 3 && s.display !== 'none'
    && s.visibility !== 'hidden' && !e.closest('[hidden], .sr-only') && s.overflowX === 'hidden'
    && s.textOverflow !== 'ellipsis' && e.scrollWidth > e.clientWidth + 2 && e.clientWidth > 0;
}).slice(0, 5).map(e => e.tagName + '.' + e.className + ' « ' + e.textContent.trim().slice(0, 30) + ' »')
"""


class Rapport:
    def __init__(self) -> None:
        self.defauts: dict[tuple, int] = {}
        self.pages: set[tuple] = set()
        self.clics = 0
        self.verifs = 0
        self.captures = 0

    def defaut(self, ctx: str, page: str, message: str) -> None:
        cle = (ctx, page, message[:300])
        self.defauts[cle] = self.defauts.get(cle, 0) + 1
        print(f"  DÉFAUT [{ctx}] {page} : {message[:300]}")

    def ecrire(self, dossier: Path) -> None:
        sortie = [{"contexte": c, "page": p, "message": m, "occurrences": n} for (c, p, m), n in self.defauts.items()]
        (dossier / "rapport.json").write_text(json.dumps(
            {"pages_testees": len(self.pages), "clics": self.clics, "controles": self.verifs,
             "defauts": sortie}, ensure_ascii=False, indent=1))


def port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Serveur:
    def __init__(self, mode: str) -> None:
        self.port = port_libre()
        self.adresse = f"http://127.0.0.1:{self.port}"
        env = dict(os.environ)
        env.pop("VIRTUAL_ENV", None)
        self.proc = subprocess.Popen([sys.executable, str(RACINE / "tests/qa/serveur_qa.py"), mode, str(self.port)],
                                     cwd=RACINE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(120):
            try:
                urllib.request.urlopen(self.adresse + "/sante", timeout=1).read()
                return
            except Exception:  # noqa: BLE001
                if self.proc.poll() is not None:
                    raise SystemExit(f"serveur arrêté : {self.proc.stderr.read().decode()[-800:]}")
                time.sleep(0.5)
        raise SystemExit("serveur injoignable")

    def arreter(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def noms_scelles(mode: str) -> list[str]:
    """Des noms de quêtes et de donjons d'étages scellés, qu'un grimpeur ne doit jamais voir."""
    if mode == "demo":
        from epreuve.web.demo import DepotDemo

        d = DepotDemo()
        scelles = {e.id for e in d._etages.values() if e.statut == "scelle"}
        return [q.nom for q in d._quetes.values() if q.etage_id in scelles][:4]
    import asyncio

    import asyncpg

    url = (os.environ.get("TEST_DATABASE_URL") or os.environ["DATABASE_URL"]).replace("+asyncpg", "")

    async def lire():
        c = await asyncpg.connect(url)
        try:
            lignes = await c.fetch("""select q.nom from epreuve.quete q join epreuve.etage e on e.id = q.etage_id
                                      where e.statut = 'scelle' order by q.id limit 4""")
            lignes += await c.fetch("""select d.nom from epreuve.donjon d join epreuve.etage e on e.id = d.etage_id
                                       where e.statut = 'scelle' order by d.id limit 3""")
            return [r["nom"] for r in lignes]
        finally:
            await c.close()

    return asyncio.run(lire())


# ---------------------------------------------------------------------------------------------- une page


class Contexte:
    """Un onglet, ses erreurs collectées, et le rapport."""

    def __init__(self, page: Page, rapport: Rapport, etiquette: str, base: str, captures: Path, largeur: int) -> None:
        self.page, self.r, self.etiquette, self.base = page, rapport, etiquette, base
        self.captures, self.largeur = captures, largeur
        self.erreurs: list[str] = []
        self.statuts: list[tuple[str, int]] = []
        page.on("console", self._console)
        page.on("pageerror", lambda e: self.erreurs.append(f"JS : {e}"))
        page.on("requestfailed", self._echec)
        page.on("response", self._reponse)
        page.on("dialog", lambda d: d.dismiss())

    def _console(self, m) -> None:
        if m.type == "error" or "Content Security Policy" in m.text or "Refused to" in m.text:
            if "Failed to load resource" in m.text:
                return  # les statuts sont jugés par `_reponse`, avec l'adresse
            self.erreurs.append(f"console : {m.text[:200]}")

    def _echec(self, req) -> None:
        if "net::ERR_ABORTED" in (req.failure or ""):
            return
        if "api.dofusdb.fr/img/" in req.url:
            return  # image absente chez DofusDB : le site la masque (classe img-absente), voir JS_IMAGES
        self.erreurs.append(f"requête en échec : {req.url} ({req.failure})")

    def _reponse(self, rep) -> None:
        if rep.url.startswith(self.base):
            self.statuts.append((rep.url[len(self.base):], rep.status))

    @property
    def chemin(self) -> str:
        u = urlparse(self.page.url)
        return u.path + (f"?{u.query}" if u.query else "")

    def defaut(self, message: str) -> None:
        self.r.defaut(self.etiquette, self.chemin, message)

    def vider_erreurs(self, ou: str) -> None:
        for e in dict.fromkeys(self.erreurs):
            self.defaut(f"{ou} : {e}")
        self.erreurs.clear()
        # 4xx/5xx sur une ressource (pas la page : jugée à part)
        for url, st in self.statuts:
            if st >= 400 and (url.startswith("/static") or url.startswith("/api")) and st != 404:
                self.defaut(f"{ou} : {url} → {st}")
        self.statuts.clear()

    def controler(self, ou: str, recouvrements: bool = True) -> None:
        """Les contrôles passifs de la page courante."""
        p = self.page
        self.r.verifs += 1
        self.vider_erreurs(ou)
        sw, cw = p.evaluate(JS_DEBORDEMENT)
        if sw > cw:
            self.defaut(f"{ou} : défilement horizontal ({sw} > {cw})")
        if recouvrements:
            for m in p.evaluate(JS_RECOUVERTS, 120):
                self.defaut(f"{ou} : {m}")
        for src in p.evaluate(JS_IMAGES):
            self.defaut(f"{ou} : image cassée {src[:100]}")
        for t in p.evaluate(JS_TEXTE_COUPE):
            self.defaut(f"{ou} : texte coupé {t}")
        if not p.title().strip():
            self.defaut(f"{ou} : titre de page vide")
        if p.locator("h1").count() == 0 and p.locator("h2").count() == 0 and "/static" not in self.chemin:
            self.defaut(f"{ou} : aucun titre h1 ou h2")
        corps = p.inner_text("body")
        for motif in (r"Traceback", r"Internal Server Error", r"\bundefined\b", r"\bNaN\b", r"\{\{", r"\bNone\b"):
            if re.search(motif, corps):
                self.defaut(f"{ou} : texte parasite « {motif.replace(chr(92), '')} » dans la page")

    def photo(self, nom: str) -> None:
        if self.largeur == 768 and not nom.startswith("n1-"):
            return
        fichier = self.captures / f"{self.etiquette}__{self.largeur}__{nom}.jpg"
        try:
            self.page.screenshot(path=str(fichier), full_page=True, type="jpeg", quality=55)
            self.r.captures += 1
        except Exception:  # noqa: BLE001 — une capture ratée ne doit pas arrêter la recette
            pass

    mode = ""

    def attendu(self, chemin: str, defaut: int = 200) -> int:
        # La démo n'a ni encyclopédie ni stuffs (pas de base) : 404 voulu.
        if self.mode == "demo" and chemin.startswith(("/encyclopedie", "/stuffs", "/recherche")):
            return 404
        return defaut

    def aller(self, chemin: str, attendu: int = 200) -> int:
        attendu = self.attendu(chemin, attendu)
        rep = self.page.goto(self.base + chemin, wait_until="load")
        st = rep.status if rep else 0
        if st != attendu:
            self.defaut(f"statut {st} au lieu de {attendu} ({chemin})")
        self.page.wait_for_timeout(120)
        self.r.pages.add((self.etiquette, self.largeur, urlparse(chemin).path))
        return st


def slug(chemin: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", chemin.lower()).strip("-")[:70] or "accueil"


def connecter(ctx: Contexte, profil: str) -> None:
    ctx.page.goto(ctx.base + "/connexion")
    ctx.page.get_by_role("link", name=re.compile(rf"^{profil}")).first.click()
    ctx.page.wait_for_load_state("load")
    ctx.erreurs.clear()
    ctx.statuts.clear()
    if "/histoire" in ctx.page.url or ctx.page.locator("#prologue, .prologue").count():
        ctx.page.goto(ctx.base + "/")  # le prologue ne bloque pas l'accès : on passe à l'accueil


def liens_internes(page: Page, base: str) -> list[str]:
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    sortie = []
    for h in hrefs:
        if not h or h.startswith("#") or h.startswith("javascript:"):
            continue
        absolu = urldefrag(urljoin(page.url, h))[0]
        if not absolu.startswith(base):
            continue
        rel = absolu[len(base):] or "/"
        if any(rel.startswith(i) for i in IGNORES if i.startswith("/")):
            continue
        if rel not in sortie:
            sortie.append(rel)
    return sortie


def modele(chemin: str) -> str:
    """Le modèle d'adresse : les nombres deviennent « * », et les paramètres gardent leur nom seulement."""
    u = urlparse(chemin)
    segs = ["*" if re.search(r"\d", s) else s for s in u.path.strip("/").split("/")]
    params = sorted({kv.split("=")[0] for kv in u.query.split("&") if kv})
    return "/" + "/".join(segs) + ("?" + "&".join(params) if params else "")


def cliquer_vers(ctx: Contexte, href: str) -> bool:
    """Clique le lien visible vers `href` (en ouvrant le burger et le déroulant au besoin) ; sinon False."""
    p = ctx.page
    sel = f'a[href="{href}"]'
    cible = p.locator(sel + ":visible")
    if cible.count() == 0:
        burger = p.locator("#burger:visible")
        if burger.count() and burger.get_attribute("aria-expanded") != "true":
            burger.click()
            p.wait_for_timeout(120)
        bouton = p.locator(".deroulant-bouton:visible")
        if p.locator(sel).count() and p.locator(sel + ":visible").count() == 0 and bouton.count():
            bouton.click()
            p.wait_for_timeout(120)
        cible = p.locator(sel + ":visible")
    if cible.count() == 0:
        return False
    cible.first.scroll_into_view_if_needed()
    cible.first.click()
    ctx.r.clics += 1
    return True


def visiter_en_cliquant(ctx: Contexte, depart: str, href: str) -> bool:
    """Va sur `depart`, clique vers `href`, contrôle, puis teste le retour arrière. Renvoie False si injoignable."""
    if depart == href:
        depart = "/histoire"  # cliquer sur le lien de la page où l'on est ne crée pas d'entrée d'historique
    ctx.aller(depart)
    p = ctx.page
    avant = ctx.chemin
    ctx.statuts.clear()
    if not cliquer_vers(ctx, href):
        ctx.aller(href)
        return True
    p.wait_for_load_state("load")
    p.wait_for_timeout(150)
    docs = [(u, s) for u, s in ctx.statuts if not u.startswith(("/static", "/api"))]
    cible_statut = next((s for u, s in docs if u.split("#")[0] == href.split("#")[0]), None)
    if cible_statut is not None and cible_statut != ctx.attendu(href):
        ctx.defaut(f"clic sur {href} (depuis {avant}) : statut {cible_statut}")
    ctx.r.pages.add((ctx.etiquette, ctx.largeur, urlparse(href).path))
    ctx.controler(f"après clic vers {href}")
    ctx.photo(slug(href))
    p.go_back()
    p.wait_for_load_state("load")
    p.wait_for_timeout(150)
    if ctx.chemin != avant:
        ctx.defaut(f"retour arrière depuis {href} : on arrive sur {ctx.chemin} au lieu de {avant}")
    ctx.vider_erreurs("après retour arrière")
    return True


def interactions(ctx: Contexte, maximum: int = 14) -> None:
    """Clique les boutons, onglets, filtres, listes et résumés de la page, hors cases cochées (testées à part)."""
    p = ctx.page
    url = ctx.chemin
    selecteur = ("main button:not([type=submit]):not([data-ref]), main summary, main [role=tab], "
                 "main input[type=checkbox]:not([data-ref]):not([data-etape]), main input[type=radio], main select, "
                 ".bar .deroulant-bouton, #burger")
    total = p.locator(selecteur).count()
    for i in range(min(total, maximum)):
        el = p.locator(selecteur).nth(i)
        try:
            if not el.is_visible() or not el.is_enabled():
                continue
            texte = (el.inner_text() or el.get_attribute("aria-label") or "")[:40]
            if DANGEREUX.search(texte):
                continue
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            if tag == "select":
                n = el.locator("option").count()
                if n > 1:
                    el.select_option(index=1)
                    p.wait_for_timeout(350)
            else:
                el.scroll_into_view_if_needed(timeout=2000)
                el.click(timeout=2500)
                p.wait_for_timeout(200)
            ctx.r.clics += 1
        except Exception as e:  # noqa: BLE001
            ctx.defaut(f"clic impossible sur l'élément n°{i} ({str(e).splitlines()[0][:120]})")
            continue
        sw, cw = p.evaluate(JS_DEBORDEMENT)
        if sw > cw:
            ctx.defaut(f"défilement horizontal après le clic n°{i} « {texte.strip()} » ({sw} > {cw})")
        ctx.vider_erreurs(f"après le clic n°{i} « {texte.strip()} »")
        if ctx.chemin.split("#")[0] != url.split("#")[0] and not ctx.chemin.startswith(url.split("?")[0]):
            p.go_back()
            p.wait_for_load_state("load")
        ctx.controler(f"état après le clic n°{i} « {texte.strip()} »", recouvrements=False)
        # on repart d'un état propre
        ctx.aller(url)


# ---------------------------------------------------------------------------------------------- scénarios


def parcours_menu(ctx: Contexte) -> None:
    """Chaque entrée du menu et du menu déroulant : clic, 200, retour arrière."""
    p = ctx.page
    ctx.aller("/")
    liens = p.eval_on_selector_all(".bar .nav a[href], .bar .deroulant-liste a[href], .bar .who a[href]",
                                   "els => els.map(e => e.getAttribute('href'))")
    for h in dict.fromkeys(liens):
        visiter_en_cliquant(ctx, "/", h)


def recherche(ctx: Contexte, requetes: list[tuple[str, str | None]], scelles: list[str], admin: bool) -> None:
    """Saisie progressive : les suggestions apparaissent sans Entrée, en moins d'une seconde, et mènent au bon endroit."""
    p = ctx.page
    for saisie, attendu in requetes:
        ctx.aller("/")
        if p.locator("#burger:visible").count():
            p.click("#burger")
        champ = p.locator(".bar input[data-suggest=global]")
        champ.click()
        debut = 0.0
        for lettre in saisie:
            champ.press_sequentially(lettre, delay=45)
            debut = time.monotonic()
        try:
            p.wait_for_selector(".rech-panneau:not([hidden]) .rech-item, .rech-panneau:not([hidden]) .rech-vide", timeout=1500)
        except Exception:  # noqa: BLE001
            ctx.defaut(f"recherche « {saisie} » : aucune suggestion visible sans Entrée")
            continue
        delai = time.monotonic() - debut
        if delai > 1.0:
            ctx.defaut(f"recherche « {saisie} » : suggestions après {delai:.2f} s (> 1 s)")
        items = p.locator(".rech-panneau:not([hidden]) a.rech-item")
        if items.count() == 0:
            ctx.defaut(f"recherche « {saisie} » : aucun résultat")
            continue
        ctx.r.verifs += 1
        recouvert = p.evaluate("""() => { const a = document.querySelector('.rech-panneau:not([hidden]) a.rech-item');
          const r = a.getBoundingClientRect(); const h = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
          return !(a.contains(h) || h.contains(a)); }""")
        if recouvert:
            ctx.defaut(f"recherche « {saisie} » : la première suggestion est recouverte")
        sw, cw = p.evaluate(JS_DEBORDEMENT)
        if sw > cw:
            ctx.defaut(f"recherche « {saisie} » : défilement horizontal avec le panneau ouvert")
        ctx.photo(f"recherche-{slug(saisie)}")
        textes = [t.lower() for t in p.locator(".rech-panneau .rech-nom").all_inner_texts()]
        if attendu and not any(attendu.lower() in t for t in textes):
            ctx.defaut(f"recherche « {saisie} » : « {attendu} » absent des suggestions {textes[:6]}")
        if not admin:
            for nom in scelles:
                if nom.lower() in " ".join(textes):
                    ctx.defaut(f"recherche « {saisie} » : le nom scellé « {nom} » est visible par un grimpeur")
        premier = items.first.get_attribute("href")
        items.first.click()
        ctx.r.clics += 1
        p.wait_for_load_state("load")
        ctx.statuts.clear()
        if premier and urlparse(premier).path not in p.url:
            ctx.defaut(f"recherche « {saisie} » : le clic mène à {p.url} au lieu de {premier}")
        ctx.controler(f"page atteinte par la recherche « {saisie} »", recouvrements=False)
        p.go_back()
        p.wait_for_load_state("load")
        if ctx.chemin != "/":
            ctx.defaut(f"recherche « {saisie} » : retour arrière sur {ctx.chemin} au lieu de /")
    # Entrée avec une flèche, Échap, et la page « voir tout »
    ctx.aller("/")
    if p.locator("#burger:visible").count():
        p.click("#burger")
    champ = p.locator(".bar input[data-suggest=global]")
    champ.press_sequentially("bouf", delay=40)
    p.wait_for_selector(".rech-panneau:not([hidden]) .rech-item", timeout=1500)
    champ.press("Escape")
    if not p.locator(".rech-panneau").first.is_hidden():
        ctx.defaut("recherche : Échap ne referme pas le panneau")
    champ.press("Enter")
    p.wait_for_load_state("load")
    if "/recherche" not in p.url:
        ctx.defaut(f"recherche : Entrée mène à {p.url} au lieu de /recherche")
    else:
        ctx.controler("page /recherche", recouvrements=False)
        ctx.photo("recherche-page")
        champ2 = p.locator("#rechPage")
        champ2.fill("")
        champ2.press_sequentially("tour", delay=40)
        p.wait_for_timeout(600)
    # Un mot sans résultat : message clair
    ctx.aller("/")
    if p.locator("#burger:visible").count():
        p.click("#burger")
    champ = p.locator(".bar input[data-suggest=global]")
    champ.press_sequentially("zzzzqx", delay=30)
    try:
        p.wait_for_selector(".rech-panneau:not([hidden]) .rech-vide", timeout=1500)
    except Exception:  # noqa: BLE001
        ctx.defaut("recherche « zzzzqx » : pas de message « aucun résultat »")


def cases(ctx: Contexte, autre_id: str | None) -> None:
    """Cocher : jauge et compteurs, persistance, lecture seule chez un autre grimpeur."""
    p = ctx.page
    ctx.aller("/etages/0")
    boite = p.locator("#liste li[data-cats]:not([data-donjon]) input[data-ref^='quete:']:not(:checked)").first
    if boite.count() == 0:
        ctx.defaut("aucune quête à cocher sur /etages/0")
        return
    ref = boite.get_attribute("data-ref")
    etat0 = p.eval_on_selector_all("#liste input[data-ref]", "els => els.map(e => [e.dataset.ref, e.checked])")
    avant_cats = {c: p.inner_text(f"[data-moi-cat='{c}']") for c in ("principales", "secondaires")}
    compteur = p.locator(f"[data-compteur='{ref}']").first
    avant_compteur = compteur.inner_text()
    avant_score = p.inner_text("[data-j='score']")
    p.locator(f"input[data-ref='{ref}']").first.check(force=True)
    ctx.r.clics += 1
    p.wait_for_timeout(700)
    if not p.locator(f"input[data-ref='{ref}']").first.is_checked():
        ctx.defaut(f"la case {ref} s'est décochée toute seule")
    if compteur.inner_text() == avant_compteur:
        ctx.defaut(f"compteur de {ref} inchangé après la coche ({avant_compteur})")
    apres_cats = {c: p.inner_text(f"[data-moi-cat='{c}']") for c in avant_cats}
    if apres_cats == avant_cats:
        ctx.defaut(f"« Ma progression » inchangée après la coche de {ref}")
    if p.locator("#messageCoche:visible").count():
        ctx.defaut(f"message d'échec après la coche : {p.inner_text('#messageCoche')}")
    ctx.controler("après une coche")
    ctx.photo("coche-faite")
    p.reload()
    p.wait_for_load_state("load")
    if not p.locator(f"input[data-ref='{ref}']").first.is_checked():
        ctx.defaut(f"la coche de {ref} n'a pas survécu au rechargement")
    if p.inner_text(f"[data-compteur='{ref}']") == avant_compteur:
        ctx.defaut("le compteur est revenu à sa valeur d'avant après rechargement")
    # le donjon : « Tout le donjon »
    d = p.locator("li[data-donjon] summary").first
    if d.count():
        d.click()
        tout = p.locator("[data-donjon-tout]").first
        avant_dj = p.inner_text("li[data-donjon] [data-djcompte]")
        if tout.is_visible():
            tout.click()
            ctx.r.clics += 1
            p.wait_for_timeout(700)
            if p.inner_text("li[data-donjon] [data-djcompte]") != "5" and avant_dj != "5":
                ctx.defaut(f"« Tout le donjon » : compte {p.inner_text('li[data-donjon] [data-djcompte]')} au lieu de 5")
            p.reload()
            p.wait_for_load_state("load")
            if p.inner_text("li[data-donjon] [data-djcompte]") != "5":
                ctx.defaut("« Tout le donjon » n'a pas persisté après rechargement")
            # retour à l'état initial (case par case, depuis le premier donjon)
            p.locator("li[data-donjon] summary").first.click()
            restantes = p.locator("li[data-donjon]").first.locator("input[data-ref]:checked")
            for _ in range(5):
                if restantes.count() == 0:
                    break
                restantes.first.uncheck(force=True)
                p.wait_for_timeout(300)
    # on remet toutes les cases dans leur état d'origine (la cascade peut en toucher plusieurs)
    for _ in range(3):
        p.reload()
        p.wait_for_load_state("load")
        courant = dict(p.eval_on_selector_all("#liste input[data-ref]", "els => els.map(e => [e.dataset.ref, e.checked])"))
        ecart = [(r, v) for r, v in etat0 if courant.get(r) != v]
        if not ecart:
            break
        for r, v in ecart:
            p.locator("li[data-donjon] summary").evaluate_all("els => els.forEach(e => e.parentElement.open = true)")
            (p.locator(f"input[data-ref='{r}']").first.check if v else p.locator(f"input[data-ref='{r}']").first.uncheck)(force=True)
            p.wait_for_timeout(300)
    p.reload()
    if p.locator(f"input[data-ref='{ref}']").first.is_checked():
        ctx.defaut(f"la décoche de {ref} n'a pas persisté")
    if p.inner_text("[data-j='score']") != avant_score:
        ctx.defaut("le score de la jauge ne revient pas à sa valeur d'origine")
    # filtre : état dans l'URL, conservé au rechargement
    p.locator("#filtre input[value=principales]").uncheck()
    p.wait_for_timeout(150)
    visibles = p.locator("#liste li[data-cats]:not([hidden])").count()
    p.reload()
    if p.locator("#filtre input[value=principales]").is_checked():
        ctx.defaut("le filtre décoché n'est pas retrouvé après rechargement")
    if p.locator("#liste li[data-cats]:not([hidden])").count() != visibles:
        ctx.defaut("le filtre ne masque pas les mêmes lignes après rechargement")
    p.locator("#filtre input").evaluate_all("els => els.forEach(e => { if (e.value !== 'reste') e.checked = false })")
    p.locator("#filtre input[value=reste]").check()
    p.wait_for_timeout(100)
    if not p.locator("#filtreVide").is_visible() and p.locator("#liste li[data-cats]:not([hidden])").count():
        ctx.defaut("tout décoché : ni liste vide ni message « Rien à afficher »")
    p.click("#filtreTout")
    # la fiche d'un autre grimpeur : lecture seule
    if autre_id:
        ctx.aller(f"/grimpeurs/{autre_id}")
        ctx.photo("fiche-autre")
        activees = p.locator("input[data-ref]:not([disabled])").count()
        if activees:
            ctx.defaut(f"fiche de l'autre grimpeur : {activees} cases modifiables (lecture seule attendue)")
        ctx.controler("fiche d'un autre grimpeur")
        ctx.aller(f"/etages/0?grimpeur={autre_id}")


def modales(ctx: Contexte) -> None:
    """Fenêtre de fiche de quête : Échap, clic sur le fond, retour arrière, croix, focus."""
    p = ctx.page
    ctx.aller("/etages/0")
    lien = p.locator("#liste a[data-qopen]").first
    if lien.count() == 0:
        ctx.defaut("aucune quête à ouvrir en fenêtre sur /etages/0")
        return
    liste_url = ctx.chemin
    qhref = lien.get_attribute("href")

    def ouvrir():
        lien.scroll_into_view_if_needed()
        lien.click()
        ctx.r.clics += 1
        p.wait_for_selector("dialog#qd[open] .qd-in", timeout=3000)
        p.wait_for_timeout(150)

    def ferme(contexte: str) -> None:
        p.wait_for_timeout(300)
        if p.locator("dialog#qd[open]").count():
            ctx.defaut(f"fenêtre : toujours ouverte après {contexte}")
        if ctx.chemin != liste_url:
            ctx.defaut(f"fenêtre : après {contexte} l'adresse est {ctx.chemin} au lieu de {liste_url}")

    ouvrir()
    if urlparse(p.url).path != qhref:
        ctx.defaut(f"fenêtre : adresse {ctx.chemin} au lieu de {qhref}")
    foc = p.evaluate("document.activeElement && (document.activeElement.closest('dialog#qd') ? 'dans' : document.activeElement.tagName)")
    if foc != "dans":
        ctx.defaut(f"fenêtre : le focus n'est pas dans la fenêtre à l'ouverture ({foc})")
    ctx.controler("fiche de quête ouverte")
    ctx.photo("modale-quete")
    # onglet / qui l'a faite
    qui = p.locator("dialog#qd [data-qui]")
    if qui.count():
        qui.click()
        ctx.r.clics += 1
        if p.locator("#quiPanneau").is_hidden():
            ctx.defaut("« Qui l'a faite » n'ouvre pas le volet")
        ctx.photo("modale-quete-qui")
        qui.click()
    # tab reste piégé dans la fenêtre
    for _ in range(40):
        p.keyboard.press("Tab")
    if p.evaluate("(() => { const a = document.activeElement; return a !== document.body && !a.closest('dialog#qd'); })()"):
        ctx.defaut("fenêtre : Tab fait sortir le focus de la fenêtre modale")
    p.keyboard.press("Escape")
    ferme("Échap")
    if p.evaluate("document.activeElement && document.activeElement.dataset && document.activeElement.dataset.qopen") != qhref.split("/")[-1]:
        ctx.defaut("fenêtre : le focus ne revient pas sur la quête ouverte après Échap")
    ouvrir()
    plein_ecran = p.evaluate("(() => { const r = document.getElementById('qd').getBoundingClientRect(); return r.left < 4 && r.top < 4; })()")
    if plein_ecran:  # sur téléphone la fiche occupe tout l'écran : il n'y a pas de fond à toucher, on utilise la croix
        p.click("dialog#qd [data-qclose]")
    else:
        p.mouse.click(2, 2)
    ferme("clic sur le fond")
    ouvrir()
    p.go_back()
    ferme("retour arrière")
    p.go_forward()
    p.wait_for_timeout(500)
    if not p.locator("dialog#qd[open]").count():
        ctx.defaut("fenêtre : « page suivante » ne rouvre pas la fiche")
    else:
        p.keyboard.press("Escape")
        ferme("Échap après page suivante")
    ouvrir()
    p.click("dialog#qd [data-qclose]")
    ferme("la croix")
    # prérequis cliquable dans la fiche : remplace la fiche sans empiler une fenêtre
    for i in range(min(12, p.locator("#liste a[data-qopen]").count())):
        p.locator("#liste a[data-qopen]").nth(i).click()
        p.wait_for_selector("dialog#qd[open] .qd-in", timeout=3000)
        pre = p.locator("dialog#qd .recap-list a.qlink")
        if pre.count():
            pre.first.click()
            ctx.r.clics += 1
            p.wait_for_timeout(500)
            if p.locator("dialog#qd[open]").count() != 1:
                ctx.defaut("fenêtre : le prérequis cliqué a fermé la fiche")
            ctx.photo("modale-prerequis")
            p.keyboard.press("Escape")
            p.wait_for_timeout(300)
            if ctx.chemin != liste_url:
                ctx.defaut(f"fenêtre : après prérequis puis Échap l'adresse est {ctx.chemin}")
            break
        p.keyboard.press("Escape")
        p.wait_for_timeout(300)
    # page complète sans JS : /etages/0/quetes/N
    ctx.aller(qhref)
    ctx.controler("fiche de quête en page complète")


def filtres_instantanes(ctx: Contexte) -> None:
    """Barres de recherche des listes : le filtre agit à la frappe, sans bouton, et affiche l'état vide."""
    p = ctx.page
    for chemin, mot in (("/encyclopedie/monstres", "bouf"), ("/encyclopedie/objets", "bouf"),
                        ("/encyclopedie/panoplies", "bouf"), ("/encyclopedie/sorts", "feu"),
                        ("/encyclopedie/quetes", "bouf"), ("/encyclopedie/pnj", "mer"),
                        ("/encyclopedie/recettes", "bouf"), ("/archimonstres", "kar"),
                        ("/avis-de-recherche", "ar"), ("/outils/craft", "bouf")):
        st = ctx.aller(chemin, attendu=200)
        if st != 200:
            continue
        champ = p.locator("main input[type=search]:visible").first
        if champ.count() == 0:
            ctx.defaut(f"{chemin} : pas de champ de recherche visible")
            continue
        avant = p.inner_text("main")
        champ.click()
        champ.press_sequentially(mot, delay=60)
        p.wait_for_timeout(900)
        p.wait_for_load_state("load")  # la liste se recharge parfois par navigation
        apres = p.inner_text("main")
        ctx.r.verifs += 1
        if avant == apres:
            ctx.defaut(f"{chemin} : la saisie « {mot} » ne change rien sans validation")
        ctx.controler(f"filtre {chemin} « {mot} »")
        ctx.photo(f"filtre-{slug(chemin)}")
        champ.fill("")
        champ.press_sequentially("zzzzqx", delay=40)
        p.wait_for_timeout(900)
        p.wait_for_load_state("load")
        corps = p.inner_text("main").lower()
        if not any(m in corps for m in ("aucun", "rien", "pas de résultat", "0 résultat", "introuvable")) and "0" not in corps:
            ctx.defaut(f"{chemin} : aucun message d'état vide pour un mot introuvable")
        ctx.photo(f"filtre-vide-{slug(chemin)}")


def crawler(ctx: Contexte, limite: int) -> None:
    """Profondeur 2 depuis l'accueil, échantillon borné par modèle d'adresse, clics, retour arrière."""
    vus_modeles: Counter = Counter()
    vus: set[str] = set()
    file: list[tuple[str, str, int]] = []
    ctx.aller("/")
    ctx.controler("accueil")
    ctx.photo("n0-accueil")
    for h in liens_internes(ctx.page, ctx.base):
        file.append(("/", h, 1))
    n = 0
    while file and n < limite:
        parent, href, prof = file.pop(0)
        m = modele(href)
        if href in vus or urlparse(href).path == urlparse(parent).path and href == parent or vus_modeles[m] >= (2 if prof > 1 else 3):
            continue
        vus.add(href)
        vus_modeles[m] += 1
        n += 1
        visiter_en_cliquant(ctx, parent, href)
        ctx.aller(href)
        ctx.photo(("n1-" if prof == 1 else "n2-") + slug(href))
        interactions(ctx)
        if prof < 2:
            for h in liens_internes(ctx.page, ctx.base):
                if h not in vus:
                    file.append((href, h, prof + 1))


def scenario(playwright, serveur: Serveur, mode: str, largeur: int, captures: Path, rapport: Rapport,
             limite: int, scelles: list[str]) -> None:
    navigateur = playwright.chromium.launch()
    grimpeur, admin = ("Brindille", "Marceau")
    for profil, est_admin in ((grimpeur, False), (admin, True)):
        etiquette = f"{mode}-{'admin' if est_admin else 'grimpeur'}"
        print(f"== {etiquette} à {largeur} px")
        contexte = navigateur.new_context(viewport={"width": largeur, "height": HAUTEUR[largeur]}, locale="fr-FR",
                                          has_touch=largeur < 768, is_mobile=largeur < 768,
                                          reduced_motion="reduce")  # le décor animé ne sert à rien ici
        page = contexte.new_page()
        page.set_default_timeout(15000)
        ctx = Contexte(page, rapport, etiquette, serveur.adresse, captures, largeur)
        ctx.mode = mode
        page.add_init_script("document.addEventListener('securitypolicyviolation', e => "
                             "console.error('Content Security Policy : ' + e.violatedDirective + ' ' + e.blockedURI))")
        connecter(ctx, profil)
        try:
            ctx.aller("/")
            ctx.photo("accueil")
            parcours_menu(ctx)
            crawler(ctx, limite)
            requetes = [("kar", "kar"), ("bouf", "bouf"), ("tour", None), ("dofus", None),
                        ("brin" if not est_admin else "karam", None), ("eleonore", "éléonore"),
                        ("brindil", None)]
            if mode == "base":
                recherche(ctx, requetes, scelles, est_admin)
            if not est_admin:
                # un étage scellé : introuvable pour un grimpeur
                ctx.aller("/etages/1", attendu=404)
                ctx.aller("/etages/25", attendu=404)
                ctx.aller("/etages/9999", attendu=404)
            autre = None
            ctx.aller("/grimpeurs")
            for h in liens_internes(page, serveur.adresse):
                if re.fullmatch(r"/grimpeurs/\d+", h):
                    autre = h.rsplit("/", 1)[1]
                    if profil == "Brindille":
                        moi = page.locator(".bar .ma-fiche").get_attribute("href") if page.locator(".bar .ma-fiche").count() else ""
                        if h == moi:
                            continue
                    break
            if not est_admin:
                cases(ctx, autre)
            modales(ctx)
            if mode == "base":
                filtres_instantanes(ctx)
        except Exception as e:  # noqa: BLE001 — un scénario qui plante est lui-même un défaut
            ctx.defaut(f"le scénario a planté (ligne {e.__traceback__.tb_next.tb_lineno if e.__traceback__.tb_next else '?'}) : "
                       f"{type(e).__name__} {' | '.join(str(e).splitlines()[:6])[:500]}")
            ctx.photo("plantage")
        finally:
            contexte.close()
    navigateur.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="les-deux", choices=["demo", "base", "les-deux"])
    ap.add_argument("--captures", type=Path, default=CAPTURES_DEFAUT)
    ap.add_argument("--largeurs", default="360,768,1440")
    ap.add_argument("--limite", type=int, default=60)
    args = ap.parse_args()
    args.captures.mkdir(parents=True, exist_ok=True)
    rapport = Rapport()
    modes = ["demo", "base"] if args.mode == "les-deux" else [args.mode]
    scelles = {m: noms_scelles(m) for m in modes}  # avant Playwright : sa boucle d'événements gêne asyncio.run
    with sync_playwright() as pw:
        for mode in modes:
            serveur = Serveur(mode)
            try:
                for largeur in (int(x) for x in args.largeurs.split(",")):
                    scenario(pw, serveur, mode, largeur, args.captures, rapport, args.limite, scelles[mode])
            finally:
                serveur.arreter()
    rapport.ecrire(args.captures)
    print(f"\n{len({(m, p) for (m, _, p) in rapport.pages})} pages distinctes "
          f"({len(rapport.pages)} avec les largeurs), {rapport.clics} clics, {rapport.verifs} contrôles, "
          f"{rapport.captures} captures, {len(rapport.defauts)} défauts distincts.")
    return 1 if rapport.defauts else 0


if __name__ == "__main__":
    sys.exit(main())
