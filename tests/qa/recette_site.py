# ruff: noqa: E501, UP031, S310, B904, S110
"""Recette automatisée du site v5 dans Chromium sans tête, hors pytest (Playwright n'est pas une dépendance).

    uv run --with playwright python tests/qa/recette_site.py [--mode demo|base|les-deux] [--captures DOSSIER]
                                                              [--largeurs 360,768,1440] [--limite 60]

À chaque largeur (360, 768 et 1440 px) et pour chaque profil (grimpeur, admin) :
- vérifie le menu réduit (La Tour, L'histoire, Règles, Tableau de bord, Grimpeurs, Admin : plus de « Monde des Douze »),
  parcourt chaque entrée, puis chaque lien interne en profondeur 2 (échantillon borné par modèle d'adresse), en cliquant
  le lien depuis la page précédente et en vérifiant le retour arrière ;
- contrôle chaque page : statut 200, aucune erreur JS ni CSP ni requête en échec, aucun défilement horizontal,
  aucun lien ou bouton recouvert (`elementFromPoint` au centre), images cassées, texte coupé ;
- clique les boutons, onglets, filtres, listes déroulantes de la page, puis recontrôle ;
- attend 404 (jamais 500) sur les modules désactivés : encyclopédie, stuffs, builder, outils, archimonstres, avis de
  recherche, fiche de quête, et leurs API ;
- parcours v5 en grimpeur : structure des blocs (titre Duffus, cadre et libellé, case « Bloc terminé », nombre de
  quêtes, lien « Ouvrir sur Duffus » en nouvel onglet), cocher et décocher un bloc (jauge, compteurs, volet « Fait par »,
  persistance), point « Quêtes principales » et catégorie secondaire vide, donjons et succès, filtres dans l'URL et
  retour arrière, refus de cocher la fiche d'un autre, fiche, tableau de bord, filtre « qui a fait » sur un bloc ;
- en admin : correction de la nature d'un bloc (motif obligatoire, journal, effet, retour à la règle) ;
- un membre du Discord sans fiche et hors liste crée sa fiche (« Créer ma fiche ») ;
- la recherche globale (saisie progressive, grimpeurs, blocs, donjons, jamais de quête).

`demo` : données fictives en mémoire. `base` : TEST_DATABASE_URL (ou DATABASE_URL, jamais `.env`) remplie par
`python -m epreuve.contenu construire --etage 0` puis `--etage 1` (base migrée par `alembic upgrade head`) ; le
serveur de recette ouvre l'étage 1, ce qui termine le 0, et efface les fiches « Novice<largeur> » créées par la
recette précédente. Les coches de Brindille sont remises comme avant par chaque scénario.
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
HORS_V5 = ("/encyclopedie", "/stuffs", "/builder", "/outils", "/archimonstres", "/avis-de-recherche")
MENU = ["La Tour", "L'histoire", "Règles", "Tableau de bord", "Grimpeurs"]
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
    if (e.closest('.table-wrap') && (r.left > innerWidth || r.right < 0)) continue;  // tableau d'admin : défilement horizontal voulu
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
                                      where e.statut = 'scelle' and e.numero > 1 order by q.id limit 4""")
            lignes += await c.fetch("""select d.nom from epreuve.donjon d join epreuve.etage e on e.id = d.etage_id
                                       where e.statut = 'scelle' and e.numero > 1 order by d.id limit 3""")
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
        # SPEC-V5 §2 : les modules du « Monde des Douze » et la fiche de quête répondent 404.
        if chemin.startswith(HORS_V5) or re.match(r"/etages/\d+/quetes/", chemin):
            return 404
        if self.mode == "demo" and chemin.startswith("/recherche"):
            return 404  # la démo n'a pas de base de recherche
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
    selecteur = ("main button:not([type=submit]):not([data-ref]):not([data-donjon-tout]), main summary, main [role=tab], "
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


def parcours_menu(ctx: Contexte, a_fiche: bool, admin: bool) -> None:
    """Le menu réduit de la v5, puis chaque entrée : clic, 200, retour arrière."""
    p = ctx.page
    ctx.aller("/")
    attendu = [m for m in MENU if a_fiche or m != "Tableau de bord"] + (["Admin"] if admin else [])
    menu = p.eval_on_selector_all(".bar .nav a", "els => els.map(e => e.textContent.trim())")
    if menu != attendu:
        ctx.defaut(f"menu {menu} au lieu de {attendu}")
    if p.locator(".bar .deroulant-bouton, .bar .deroulant-liste").count():
        ctx.defaut("le menu déroulant « Monde des Douze » est encore dans la barre")
    if "Monde des Douze" in p.inner_text(".bar") or p.locator("a[href^='/encyclopedie'], a[href^='/outils'], a[href^='/builder']").count():
        ctx.defaut("une trace du Monde des Douze reste sur l'accueil")
    creer = p.locator(".bar .who a", has_text="Créer ma fiche").count()
    if bool(creer) == a_fiche:
        ctx.defaut(f"« Créer ma fiche » {'présent' if creer else 'absent'} alors que le profil {'a' if a_fiche else 'n a pas'} de fiche")
    liens = p.eval_on_selector_all(".bar .nav a[href], .bar .who a[href]", "els => els.map(e => e.getAttribute('href'))")
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


def lire_etat(p: Page) -> dict:
    """Ce que la page d'un étage affiche de ma progression et de la jauge, pour comparer avant / après une coche."""
    return p.evaluate("""() => ({
      cats: Object.fromEntries([...document.querySelectorAll('[data-moi-cat]')].map(e => [e.dataset.moiCat, e.textContent.trim()])),
      points: (document.querySelector('[data-moi=points]') || {}).textContent,
      jauge: Object.fromEntries([...document.querySelectorAll('[data-jcat]')].map(e => [e.dataset.jcat, e.textContent.trim()])),
    })""")


def entier(texte: str) -> int:
    m = re.search(r"\d+", texte or "")
    return int(m.group()) if m else -1


def structure_blocs(ctx: Contexte, numero: int) -> int:
    """Chaque carte de bloc : titre « Bloc N · … » dans l'ordre du guide, libellé et cadre, case, quêtes, lien Duffus."""
    p = ctx.page
    cartes = p.locator("li.bloc-carte")
    n = cartes.count()
    numeros = []
    for i in range(n):
        c = cartes.nth(i)
        titre = c.locator("h3").inner_text().strip()
        m = re.match(r"^Bloc (\d+) · \S.+", titre)
        if not m:
            ctx.defaut(f"bloc {i + 1} de l'étage {numero} : titre « {titre} » sans le numéro de Duffus")
        else:
            numeros.append(int(m.group(1)))
        classe = c.get_attribute("class") or ""
        lib = c.locator(".badge").first.inner_text().strip()
        if "c-principales" in classe and lib != "Principal":
            ctx.defaut(f"« {titre} » : cadre rouge mais libellé « {lib} » au lieu de « Principal »")
        if "c-secondaires" in classe and lib != "Secondaire":
            ctx.defaut(f"« {titre} » : cadre jaune mais libellé « {lib} » au lieu de « Secondaire »")
        couleur = c.evaluate("e => getComputedStyle(e).borderTopColor")
        rgb = [int(x) for x in re.findall(r"\d+", couleur)[:3]]
        rouge = rgb[0] > 200 and rgb[1] < 160 and rgb[2] < 160
        jaune = rgb[0] > 200 and rgb[1] > 200 and rgb[2] < 120
        if ("c-principales" in classe and not rouge) or ("c-secondaires" in classe and not jaune):
            ctx.defaut(f"« {titre} » : couleur du cadre {couleur} inattendue pour {classe}")
        if c.locator("label.bloc-termine", has_text="Bloc terminé").count() != 1:
            ctx.defaut(f"« {titre} » : pas de case « Bloc terminé »")
        if not re.search(r"\d+ quêtes?", c.locator(".bloc-meta").inner_text()):
            ctx.defaut(f"« {titre} » : nombre de quêtes absent ({c.locator('.bloc-meta').inner_text()!r})")
        lien = c.locator("a.lien-duffus")
        if lien.count() != 1:
            ctx.defaut(f"« {titre} » : pas de lien « Ouvrir sur Duffus »")
        else:
            href = lien.get_attribute("href") or ""
            if not href.startswith("https://duffus.fr"):
                ctx.defaut(f"« {titre} » : le lien Duffus mène à {href!r}")
            if lien.get_attribute("target") != "_blank" or "noopener" not in (lien.get_attribute("rel") or ""):
                ctx.defaut(f"« {titre} » : le lien Duffus ne s'ouvre pas dans un nouvel onglet (target/rel)")
        if c.locator("details.qui-bloc summary", has_text="Fait par / Pas encore fait par").count() != 1:
            ctx.defaut(f"« {titre} » : pas de volet « Fait par / Pas encore fait par »")
        if not re.search(r"\d+ sur \d+ l'ont fait", c.locator("a.compteur").inner_text()):
            ctx.defaut(f"« {titre} » : compteur « x sur N l'ont fait » absent")
    if numeros != sorted(numeros):
        ctx.defaut(f"étage {numero} : blocs dans le désordre {numeros} (ordre du guide attendu)")
    return n


def lien_duffus(ctx: Contexte) -> None:
    """« Ouvrir sur Duffus » : un nouvel onglet vers duffus.fr, la page de l'étage reste ouverte."""
    p = ctx.page
    lien = p.locator("li.bloc-carte a.lien-duffus").first
    if lien.count() == 0:
        return
    avant = ctx.chemin
    try:
        with p.context.expect_page(timeout=5000) as nouvelle:
            lien.scroll_into_view_if_needed()
            lien.click()
        onglet = nouvelle.value
        onglet.wait_for_load_state("domcontentloaded")
        if "duffus.fr" not in onglet.url:
            ctx.defaut(f"« Ouvrir sur Duffus » ouvre {onglet.url}")
        if onglet.evaluate("window.opener") is not None:
            ctx.defaut("« Ouvrir sur Duffus » : le nouvel onglet garde window.opener (noopener manquant)")
        onglet.close()
        ctx.r.clics += 1
    except Exception as e:  # noqa: BLE001
        ctx.defaut(f"« Ouvrir sur Duffus » n'ouvre pas de nouvel onglet ({str(e).splitlines()[0][:100]})")
    if ctx.chemin != avant:
        ctx.defaut(f"« Ouvrir sur Duffus » a changé la page courante : {ctx.chemin}")


def cocher_un_bloc(ctx: Contexte, numero: int, pseudo: str) -> None:
    """Cocher puis décocher un bloc : case, carte, compteur, volet « fait par », progression, persistance."""
    p = ctx.page
    ctx.aller(f"/etages/{numero}")
    boite = p.locator("li.bloc-carte input[data-ref^='bloc:']:not(:checked)").first
    if boite.count() == 0:
        ctx.defaut(f"étage {numero} : aucun bloc à cocher")
        return
    ref = boite.get_attribute("data-ref")
    carte = p.locator(f"li.bloc-carte:has(input[data-ref='{ref}'])")
    cat = "principales" if "c-principales" in (carte.get_attribute("class") or "") else "secondaires"
    compteur = p.locator(f"[data-compteur='{ref}']")
    avant = lire_etat(p)
    n0 = entier(compteur.inner_text())
    actifs = entier(compteur.get_attribute("data-actifs"))
    boite.check(force=True)
    ctx.r.clics += 1
    p.wait_for_timeout(700)
    apres = lire_etat(p)
    if carte.get_attribute("data-fait") != "1":
        ctx.defaut(f"{ref} : la carte n'est pas marquée faite après la coche")
    if entier(compteur.inner_text()) != n0 + 1:
        ctx.defaut(f"{ref} : compteur {compteur.inner_text()!r} au lieu de {n0 + 1}")
    f0, f1 = (entier(x["cats"][cat].split("/")[0]) for x in (avant, apres))
    if f1 != f0 + 1:
        ctx.defaut(f"« Ma progression » {cat} : {avant['cats'][cat]} → {apres['cats'][cat]} (+1 attendu)")
    if p.locator("#messageCoche:visible").count():
        ctx.defaut(f"message d'échec après la coche : {p.inner_text('#messageCoche')}")
    # le volet « fait par »
    carte.locator("details.qui-bloc summary").click()
    p.wait_for_timeout(600)
    fait = [t.strip() for t in carte.locator("[data-qui=fait] .person").all_inner_texts()]
    pas = carte.locator("[data-qui=pas] .person").count()
    if not any(pseudo in t for t in fait):
        ctx.defaut(f"{ref} : {pseudo} absent de « Fait par » {fait[:5]}")
    if len(fait) != n0 + 1 or len(fait) + pas != actifs:
        ctx.defaut(f"{ref} : volet incohérent ({len(fait)} ont fait, {pas} pas encore, {actifs} actifs, compteur {n0 + 1})")
    if entier(carte.locator("[data-qui-n=fait]").inner_text()) != len(fait):
        ctx.defaut(f"{ref} : le petit nombre du volet « Fait par » ne suit pas la liste")
    ctx.controler(f"après la coche de {ref}")
    ctx.photo("bloc-coche")
    # persistance
    p.reload()
    p.wait_for_load_state("load")
    if not p.locator(f"input[data-ref='{ref}']").first.is_checked():
        ctx.defaut(f"la coche de {ref} n'a pas survécu au rechargement")
    if entier(p.locator(f"[data-compteur='{ref}']").inner_text()) != n0 + 1:
        ctx.defaut(f"{ref} : compteur faux après rechargement")
    if lire_etat(p)["cats"][cat] != apres["cats"][cat]:
        ctx.defaut(f"« Ma progression » {cat} change au rechargement : {apres['cats'][cat]} → {lire_etat(p)['cats'][cat]}")
    # décocher
    p.locator(f"input[data-ref='{ref}']").first.uncheck(force=True)
    p.wait_for_timeout(700)
    retour = lire_etat(p)
    if retour != avant:
        ctx.defaut(f"{ref} : décochée, la progression/jauge ne revient pas à l'état d'avant ({avant} → {retour})")
    if entier(p.locator(f"[data-compteur='{ref}']").inner_text()) != n0:
        ctx.defaut(f"{ref} : compteur non revenu à {n0} après la décoche")
    p.reload()
    p.wait_for_load_state("load")
    if p.locator(f"input[data-ref='{ref}']").first.is_checked():
        ctx.defaut(f"la décoche de {ref} n'a pas persisté")


def point_principales(ctx: Contexte, numero: int) -> None:
    """Tous les blocs principaux cochés : le point « Quêtes principales » tombe ; catégorie secondaire vide ou non."""
    p = ctx.page
    ctx.aller(f"/etages/{numero}")
    refs = p.eval_on_selector_all("li.bloc-carte.c-principales input[data-ref]", "els => els.map(e => [e.dataset.ref, e.checked])")
    if not refs:
        ctx.defaut(f"étage {numero} : aucun bloc principal pour tester le point")
        return
    secondaires = p.locator("li.bloc-carte.c-secondaires").count()
    avant = lire_etat(p)
    a_cocher = [r for r, c in refs if not c]
    for i, r in enumerate(a_cocher):
        p.locator(f"input[data-ref='{r}']").first.check(force=True)
        p.wait_for_timeout(500)
        etat = lire_etat(p)
        derniere = i == len(a_cocher) - 1
        got = "✓" in etat["cats"]["principales"]
        if derniere and not got:
            ctx.defaut(f"étage {numero} : tous les blocs principaux cochés mais pas de point ({etat['cats']['principales']})")
        if not derniere and got:
            ctx.defaut(f"étage {numero} : point « principales » accordé avant le dernier bloc principal ({etat['cats']['principales']})")
    if a_cocher:
        fin = lire_etat(p)
        if entier(fin["points"]) != entier(avant["points"]) + 1:
            ctx.defaut(f"étage {numero} : points {avant['points']} → {fin['points']} (+1 attendu)")
        if entier(fin["jauge"]["principales"]) != entier(avant["jauge"]["principales"]) + 1:
            ctx.defaut(f"étage {numero} : jauge principales {avant['jauge']['principales']} → {fin['jauge']['principales']}")
        ctx.photo("point-principales")
        ctx.controler(f"point principales de l'étage {numero}")
    sec = lire_etat(p)["cats"]["secondaires"]
    if secondaires == 0 and (sec.startswith("0/0") is False or "✓" in sec):
        ctx.defaut(f"étage {numero} : catégorie secondaire vide mais affichée « {sec} » (« 0/0 » sans point attendu)")
    if p.locator("body").inner_text().count("NaN") or "undefined" in p.inner_text("body"):
        ctx.defaut(f"étage {numero} : NaN ou undefined avec une catégorie vide")
    # on remet tout dans l'état d'avant
    for r in a_cocher:
        p.locator(f"input[data-ref='{r}']").first.uncheck(force=True)
        p.wait_for_timeout(400)
    p.reload()
    p.wait_for_load_state("load")
    if lire_etat(p) != avant:
        ctx.defaut(f"étage {numero} : l'état ne revient pas après décoche de tous les blocs ({avant} → {lire_etat(p)})")


def donjons_et_succes(ctx: Contexte, numero: int) -> None:
    """Un donjon : ses cases, « Tout le donjon », le compteur x/5, la persistance ; on remet à zéro."""
    p = ctx.page
    ctx.aller(f"/etages/{numero}")
    li = p.locator("li[data-donjon]").first
    if li.count() == 0:
        ctx.defaut(f"étage {numero} : aucun donjon")
        return
    li.locator("summary").first.click()
    boites = li.locator("input[data-ref]")
    total = boites.count()
    if total != 5:
        ctx.defaut(f"étage {numero} : le premier donjon a {total} cases au lieu de 5")
    etat0 = lire_etat(p)
    compte = li.locator("[data-djcompte]")
    avant = entier(compte.inner_text())
    cible = boites.nth(0)
    if cible.is_checked():
        ctx.defaut("donjon : la première case est cochée sur une base de recette neuve")
    cible.check(force=True)  # le boss du donjon (la case « Donjon »)
    p.wait_for_timeout(600)
    if entier(compte.inner_text()) != avant + 1:
        ctx.defaut(f"donjon : compteur {compte.inner_text()} après une case (attendu {avant + 1})")
    cible.uncheck(force=True)
    p.wait_for_timeout(600)
    tout = li.locator("[data-donjon-tout]")
    if tout.is_visible():
        tout.click()
        ctx.r.clics += 1
        p.wait_for_timeout(800)
        if compte.inner_text() != "5":
            ctx.defaut(f"« Tout le donjon » : compte {compte.inner_text()} au lieu de 5")
        ctx.photo("donjon-complet")
        p.reload()
        p.wait_for_load_state("load")
        li = p.locator("li[data-donjon]").first
        li.locator("summary").first.click()
        if li.locator("[data-djcompte]").inner_text() != "5":
            ctx.defaut("« Tout le donjon » n'a pas persisté après rechargement")
        for i in range(5):
            li.locator("input[data-ref]").nth(i).uncheck(force=True)
            p.wait_for_timeout(350)
    p.reload()
    p.wait_for_load_state("load")
    if lire_etat(p) != etat0:
        ctx.defaut(f"donjon : l'état ne revient pas après remise à zéro ({etat0} → {lire_etat(p)})")


def filtres_url(ctx: Contexte, numero: int) -> None:
    """Les filtres vivent dans l'URL, survivent au rechargement et au retour arrière depuis une autre page."""
    p = ctx.page
    ctx.aller(f"/etages/{numero}")
    p.locator("#filtre input[value=donjons]").uncheck()
    p.locator("#filtre input[value=full_succes]").uncheck()
    p.wait_for_timeout(150)
    if "voir=" not in p.url:
        ctx.defaut(f"filtre : l'URL ne porte pas l'état ({p.url})")
    if p.locator("li[data-donjon]:not([hidden])").count():
        ctx.defaut("filtre : les donjons restent visibles malgré Donjons et Full succès décochés")
    visibles = p.locator("#liste li[data-cats]:not([hidden])").count()
    if p.locator("li.bloc-carte:not([hidden])").count() != p.locator("li.bloc-carte").count():
        ctx.defaut("filtre : des blocs sont masqués alors que leurs filtres sont cochés")
    url = ctx.chemin
    p.reload()
    p.wait_for_load_state("load")
    if p.locator("#filtre input[value=donjons]").is_checked() or p.locator("#liste li[data-cats]:not([hidden])").count() != visibles:
        ctx.defaut("filtre : état non retrouvé après rechargement")
    # aller ailleurs puis revenir
    lien = p.locator("a.compteur-bloc").first
    if lien.count():
        lien.click()
        p.wait_for_load_state("load")
        if "/grimpeurs?quoi=bloc:" not in p.url:
            ctx.defaut(f"le compteur d'un bloc mène à {p.url}")
        p.go_back()
        p.wait_for_load_state("load")
        p.wait_for_timeout(250)
        if ctx.chemin != url:
            ctx.defaut(f"retour arrière : {ctx.chemin} au lieu de {url}")
        if p.locator("#filtre input[value=donjons]").is_checked() or p.locator("li[data-donjon]:not([hidden])").count():
            ctx.defaut("retour arrière : le filtre n'est pas retrouvé")
    # blocs principaux seulement, puis « ce qui me reste »
    p.click("#filtreTout")
    if "voir=" in p.url or "reste=" in p.url:
        ctx.defaut(f"« Tout afficher » laisse des filtres dans l'URL ({p.url})")
    p.locator("#filtre input[value=secondaires]").uncheck()
    p.wait_for_timeout(100)
    if p.locator("li.bloc-carte.c-secondaires:not([hidden])").count():
        ctx.defaut("filtre : des blocs secondaires restent visibles, Blocs secondaires étant décoché")
    p.click("#filtreTout")
    ctx.aller(f"/etages/{numero}?voir=principales&reste=1")
    if p.locator("#filtre input[value=principales]").is_checked() is False or p.locator("#filtre input[value=reste]").is_checked() is False:
        ctx.defaut("filtre : l'URL ?voir=principales&reste=1 n'est pas relue")
    if p.locator("#filtre input[value=donjons]").is_checked():
        ctx.defaut("filtre : ?voir=principales laisse Donjons coché")
    # tout décoché : message
    ctx.aller(f"/etages/{numero}")
    p.locator("#filtre input").evaluate_all("els => els.forEach(e => { if (e.value !== 'reste') e.checked = false })")
    p.locator("#filtre input[value=reste]").check()
    p.wait_for_timeout(100)
    if not p.locator("#filtreVide").is_visible():
        ctx.defaut("tout décoché : pas de message « Rien à afficher »")
    p.click("#filtreTout")
    ctx.aller(f"/etages/{numero}?voir=n-importe-quoi")  # une valeur inconnue ne casse rien
    ctx.controler("filtre d'URL invalide")


def refus_autre_fiche(ctx: Contexte, autre_id: str | None, numero: int) -> None:
    """On ne coche pas la fiche d'un autre : cases désactivées, et l'API refuse (403)."""
    p = ctx.page
    if not autre_id:
        return
    ctx.aller(f"/grimpeurs/{autre_id}")
    ctx.photo("fiche-autre")
    activees = p.locator("input[data-ref]:not([disabled])").count()
    if activees:
        ctx.defaut(f"fiche de l'autre grimpeur : {activees} cases modifiables (lecture seule attendue)")
    ctx.controler("fiche d'un autre grimpeur")
    ctx.aller(f"/etages/{numero}?grimpeur={autre_id}")
    if p.locator("li.bloc-carte input[data-ref]:not([disabled])").count() and p.locator("li.bloc-carte input[data-ref]:disabled").count():
        ctx.defaut("?grimpeur=autre : des cases de blocs sont actives")
    # l'API : un grimpeur ne peut pas cocher pour un autre
    ref = p.locator("li.bloc-carte input[data-ref^='bloc:']").first.get_attribute("data-ref")
    csrf = p.evaluate("(document.querySelector('meta[name=csrf]') || {}).content || ''")
    rep = p.request.post(ctx.base + "/api/coches", data=json.dumps(
        {"type": "bloc", "id": int(ref.split(":")[1]), "cochee": True, "grimpeur_id": int(autre_id), "motif": "test"}),
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf, "Origin": ctx.base})
    if rep.status not in (403, 400):
        ctx.defaut(f"cocher le bloc d'un autre grimpeur par l'API : statut {rep.status} (403 attendu)")
    p.reload()
    if p.locator(f"input[data-ref='{ref}']").first.is_checked():
        ctx.defaut("le bloc d'un autre grimpeur est devenu coché")


def fiche_et_tableau(ctx: Contexte, numero: int) -> None:
    """Ma fiche, le tableau de bord et la page Grimpeurs avec le filtre « qui a fait » sur un bloc."""
    p = ctx.page
    ctx.aller(f"/etages/{numero}")
    ref = p.locator("li.bloc-carte input[data-ref^='bloc:']").first.get_attribute("data-ref")
    p.locator(f"input[data-ref='{ref}']").first.check(force=True)
    p.wait_for_timeout(600)
    titre = p.locator(f"li.bloc-carte:has(input[data-ref='{ref}']) h3").inner_text().strip()
    ma = p.locator(".bar .ma-fiche").get_attribute("href")
    pseudo = p.locator(".bar .ma-fiche").text_content().split("(")[-1].strip(" )")
    ctx.aller(ma)
    ctx.photo("fiche-moi")
    corps = p.inner_text("body")
    if "Blocs du guide" not in corps:
        ctx.defaut("fiche : pas de section « Blocs du guide »")
    ligne = p.locator("ul.etat-liste li", has_text=titre).first
    if ligne.count() == 0 or "Fait" not in ligne.inner_text() or "À faire" in ligne.inner_text():
        ctx.defaut(f"fiche : le bloc « {titre} » n'apparaît pas comme fait")
    if p.locator("input[data-ref]:not([disabled])").count() == 0:
        ctx.defaut("ma fiche : aucune case modifiable")
    nb_f = entier(p.locator("h3.section-title", has_text="Blocs du guide").first.inner_text())
    if nb_f < 1:
        ctx.defaut("fiche : le compteur de blocs ne compte pas le bloc coché")
    ctx.controler("ma fiche")
    # tableau de bord
    ctx.aller("/tableau-de-bord")
    ctx.photo("tableau")
    dt = p.locator("dl.resume-etage").first
    if "Blocs du guide" not in dt.inner_text():
        ctx.defaut("tableau de bord : « Blocs du guide » absent du résumé d'étage")
    ctx.controler("tableau de bord")
    ctx.aller("/tableau-de-bord?onglet=succes")
    ctx.controler("tableau de bord, succès de donjon")
    ctx.aller("/tableau-de-bord?onglet=succes&reste=1")
    ctx.controler("tableau de bord, succès restants")
    # page Grimpeurs : le filtre porte sur les blocs
    ctx.aller("/grimpeurs")
    options = p.locator("#askSel option[value^='bloc:']")
    if options.count() == 0:
        ctx.defaut("page Grimpeurs : aucun bloc dans le filtre « qui a fait »")
    else:
        p.select_option("#askSel", ref)  # le bouton « Voir » est masqué par le script : le choix suffit
        p.wait_for_selector("#answer h3", timeout=4000)
        p.wait_for_timeout(300)
        if f"quoi={ref}".replace(":", "%3A") not in p.url and f"quoi={ref}" not in p.url:
            ctx.defaut(f"filtre « qui a fait » : URL {p.url}")
        reponse = p.inner_text("#answer")
        if "Qui l'a fait" not in reponse or pseudo not in " ".join(p.locator("#answer .person.done").all_inner_texts()):
            ctx.defaut(f"filtre « qui a fait » sur {ref} : {pseudo} absent de la liste « fait » ({reponse[:120]!r})")
        if p.locator("#roster .player.target").count() + p.locator("#roster .player.dim").count() == 0:
            ctx.defaut("filtre « qui a fait » : aucune carte mise en avant ou estompée")
        ctx.photo("grimpeurs-qui")
        ctx.controler("page Grimpeurs avec filtre")
        p.click("#askClear")
        p.wait_for_load_state("load")
        if "quoi=" in p.url:
            ctx.defaut("« Effacer » laisse le filtre dans l'URL")
    # remise à zéro
    ctx.aller(f"/etages/{numero}")
    p.locator(f"input[data-ref='{ref}']").first.uncheck(force=True)
    p.wait_for_timeout(600)


def sans_trace_de_quete(ctx: Contexte) -> None:
    """Aucune quête unitaire, aucune fiche de quête, aucune fenêtre : sur les pages principales."""
    p = ctx.page
    for chemin in ("/", "/etages/0", "/etages/1", "/grimpeurs", "/tableau-de-bord", "/regles"):
        if chemin == "/etages/1" and ctx.mode == "demo":
            continue  # scellé dans la démo
        if chemin == "/tableau-de-bord" and p.locator(".bar .ma-fiche").count() == 0:
            continue
        ctx.aller(chemin)
        traces = p.evaluate("""() => [...document.querySelectorAll(
          "a[data-qopen], dialog#qd, [data-etape], [data-qui]:not([data-qui='fait']):not([data-qui='pas']), input[data-ref^='quete:'], a[href*='/quetes/'], a[href^='/encyclopedie'], a[href^='/outils'], a[href^='/builder'], a[href^='/archimonstres'], a[href^='/avis-de-recherche'], a[href^='/stuffs']"
        )].map(e => e.outerHTML.slice(0, 90))""")
        if traces:
            ctx.defaut(f"{chemin} : traces de quête unitaire ou de module désactivé {traces[:3]}")
        texte = p.evaluate("""() => { const c = document.body.cloneNode(true); c.querySelectorAll('footer, script').forEach(e => e.remove());
                                      return c.innerText; }""")  # le pied de page et l'histoire citent le Monde des Douze (jeu)
        for motif in (r"[Ff]iche de quête", r"Encyclop", r"Builder", r"Archimonstre", r"Avis de recherche", r"Quête faite", r"Étape\b"):
            if re.search(motif, texte):
                ctx.defaut(f"{chemin} : texte « {motif} » encore présent")


def desactives(ctx: Contexte) -> None:
    """Les modules désactivés répondent 404 (page d'erreur propre, jamais 500) ; l'API aussi."""
    p = ctx.page
    for chemin in ("/encyclopedie", "/encyclopedie/quetes", "/encyclopedie/monstres", "/encyclopedie/objets", "/stuffs",
                   "/builder", "/outils", "/outils/craft", "/outils/almanax", "/archimonstres", "/avis-de-recherche",
                   "/etages/0/quetes/101", "/etages/1/quetes/1"):
        ctx.aller(chemin, attendu=404)
        if p.locator("text=Traceback").count():
            ctx.defaut(f"{chemin} : trace d'erreur dans la 404")
    ctx.controler("une 404", recouvrements=False)
    for chemin in ("/api/builder/objets", "/api/archimonstres/monstre/1/qui", "/outils/donnees/almanax.json"):
        rep = p.request.get(ctx.base + chemin)
        if rep.status != 404:
            ctx.defaut(f"{chemin} : statut {rep.status} au lieu de 404")
    # le suivi par étape (SPEC-V5 §2) : l'API ne répond plus, même à un POST bien formé
    ctx.aller("/etages/0" if ctx.mode == "demo" else "/etages/1")
    csrf = p.evaluate("(document.querySelector('meta[name=csrf]') || {}).content || ''")
    rep = p.request.post(ctx.base + "/api/etapes", data=json.dumps({"quete_id": 101, "ordre": 1, "faite": True}),
                         headers={"Content-Type": "application/json", "X-CSRF-Token": csrf, "Origin": ctx.base})
    if rep.status != 404:
        ctx.defaut(f"POST /api/etapes : statut {rep.status} au lieu de 404 (suivi par étape désactivé)")
    rep = p.request.post(ctx.base + "/api/coches", data=json.dumps({"type": "quete", "id": 101, "cochee": True}),
                         headers={"Content-Type": "application/json", "X-CSRF-Token": csrf, "Origin": ctx.base})
    if rep.status not in (400, 404, 422):
        ctx.defaut(f"POST /api/coches sur une quête : statut {rep.status} (la coche de quête n'existe plus)")


def recherche_v5(ctx: Contexte, admin: bool) -> None:
    """La recherche ne sort que des grimpeurs, blocs, donjons et étages : jamais une quête, jamais un objet."""
    p = ctx.page
    ctx.aller("/")
    permis = {"grimpeurs", "blocs", "donjons", "etages"}
    for q, attendu in (("cryptologie", None), ("incarnam", "blocs"), ("tutoriel", "blocs"), ("brin", "grimpeurs"),
                       ("bouftou", "donjons"), ("étage", None), ("bloc 2", "blocs"), ("épée", None)):
        rep = p.request.get(ctx.base + f"/api/recherche?q={q}&limite=20")
        if rep.status != 200:
            ctx.defaut(f"recherche « {q} » : statut {rep.status}")
            continue
        groupes = rep.json()["groupes"]
        types = {g["type"] for g in groupes}
        if not types <= permis:
            ctx.defaut(f"recherche « {q} » : types inattendus {types - permis}")
        if attendu and attendu not in types:
            ctx.defaut(f"recherche « {q} » : aucun résultat de type {attendu} (types {types})")
        for g in groupes:
            for r in g["resultats"]:
                if "/quetes/" in r["lien"] or r["lien"].startswith(("/encyclopedie", "/outils", "/builder")):
                    ctx.defaut(f"recherche « {q} » : lien vers un module désactivé {r['lien']}")
    rep = p.request.get(ctx.base + "/api/recherche?q=cryptologie")
    if rep.ok and any(g["resultats"] for g in rep.json()["groupes"]):
        ctx.defaut("recherche « cryptologie » (nom d'une quête) renvoie quand même des résultats : " + str(rep.json()["groupes"])[:150])


def correction_admin(ctx: Contexte, numero: int) -> None:
    """Un admin corrige la nature d'un bloc : motif obligatoire, journal, effet sur la page d'étage, retour à la règle."""
    p = ctx.page
    ctx.aller(f"/admin/etages/{numero}")
    ctx.photo("admin-etage")
    ctx.controler("revue d'étage (admin)")
    lignes = p.locator("tr.bloc-revue")
    if lignes.count() == 0:
        ctx.defaut(f"admin étage {numero} : aucun bloc dans la revue")
        return
    if not re.search(r"\d+\s+sur\s+\d+", lignes.first.locator("td.num").inner_text()):
        ctx.defaut("revue : « principales sur total » absent")
    ligne = lignes.last
    titre = ligne.locator("td").first.inner_text().split("\n")[0].strip()
    nature0 = ligne.locator("select[name=nature]").input_value()
    nouvelle = "secondaire" if nature0 == "principale" else "principale"
    motif = f"recette v5 {int(time.time())}"
    # sans motif : refusé (le champ est « required » : on contourne pour viser le serveur)
    ligne.locator("input[name=motif]").evaluate("e => e.removeAttribute('required')")
    ligne.locator("select[name=nature]").select_option(nouvelle)
    ligne.locator("button[type=submit]").click()
    p.wait_for_load_state("load")
    if p.locator("tr.bloc-revue").last.locator("select[name=nature]").input_value() != nature0:
        ctx.defaut("correction de bloc acceptée sans motif")
    ctx.controler("correction refusée sans motif", recouvrements=False)
    # avec motif
    ligne = p.locator("tr.bloc-revue").last
    ligne.locator("select[name=nature]").select_option(nouvelle)
    ligne.locator("input[name=motif]").fill(motif)
    ligne.locator("button[type=submit]").click()
    p.wait_for_load_state("load")
    ligne = p.locator("tr.bloc-revue").last
    if ligne.locator("select[name=nature]").input_value() != nouvelle:
        ctx.defaut(f"correction de nature : {nouvelle} non retenue")
    if motif not in ligne.inner_text():
        ctx.defaut("correction de nature : le motif n'est pas rappelé dans la revue")
    ctx.photo("admin-bloc-corrige")
    ctx.aller("/admin/journal")
    if motif not in p.inner_text("body"):
        ctx.defaut("correction de nature : absente du journal admin")
    ctx.controler("journal admin", recouvrements=False)
    ctx.aller(f"/etages/{numero}")
    carte = p.locator("li.bloc-carte").last
    attendu_lib = "Principal" if nouvelle == "principale" else "Secondaire"
    if carte.locator(".badge").first.inner_text().strip() != attendu_lib or f"c-{'principales' if nouvelle == 'principale' else 'secondaires'}" not in (carte.get_attribute("class") or ""):
        ctx.defaut(f"« {titre} » : la page d'étage n'affiche pas la correction ({attendu_lib})")
    if nouvelle == "secondaire" and p.locator("[data-moi-cat=secondaires]").count() and "0/0" in p.inner_text("[data-moi-cat=secondaires]"):
        ctx.defaut("une catégorie secondaire non vide s'affiche 0/0 après correction")
    ctx.photo("etage-bloc-secondaire" if nouvelle == "secondaire" else "etage-bloc-principal")
    # retour à la règle
    ctx.aller(f"/admin/etages/{numero}")
    ligne = p.locator("tr.bloc-revue").last
    if ligne.locator("select[name=nature] option[value=auto]").count() == 0:
        ctx.defaut("pas d'option « Revenir à la règle » sur un bloc corrigé")
        return
    ligne.locator("select[name=nature]").select_option("auto")
    ligne.locator("input[name=motif]").fill("retour à la règle (recette)")
    ligne.locator("button[type=submit]").click()
    p.wait_for_load_state("load")
    if p.locator("tr.bloc-revue").last.locator("select[name=nature]").input_value() != nature0:
        ctx.defaut(f"retour à la règle : nature {p.locator('tr.bloc-revue').last.locator('select[name=nature]').input_value()} au lieu de {nature0}")


def creer_fiche(ctx: Contexte, nom: str, ouvert: int) -> None:
    """Un membre du Discord sans fiche : « Créer ma fiche » dans l'en-tête, formulaire, pseudo déjà pris, première coche."""
    p = ctx.page
    ctx.aller("/")
    lien = p.locator(".bar a", has_text="Créer ma fiche")
    if p.locator("#burger:visible").count() and lien.count() and not lien.first.is_visible():
        p.click("#burger")
    if lien.count() == 0:
        ctx.defaut(f"{nom} : pas de lien « Créer ma fiche » dans l'en-tête")
        ctx.aller("/inscription")
    else:
        if not lien.first.is_visible():
            ctx.defaut("« Créer ma fiche » est présent mais invisible")
        lien.first.click()
        p.wait_for_load_state("load")
    if "/inscription" not in p.url:
        ctx.defaut(f"« Créer ma fiche » mène à {p.url}")
    if "pas encore inscrit" in p.inner_text("body") or "liste des grimpeurs" in p.inner_text("body"):
        ctx.defaut("la liste officielle est exigée alors qu'elle ne l'est plus (message « pas inscrit »)")
        return
    ctx.photo("inscription")
    ctx.controler("formulaire de fiche")
    p.fill("#pseudo", "Brindille")  # déjà pris
    p.click("button:has-text('Créer ma fiche')")
    p.wait_for_load_state("load")
    if not p.locator("[role=alert]").count():
        ctx.defaut("pseudo déjà pris : aucun message d'erreur")
    pseudo = f"Neuf{ctx.largeur}"
    p.fill("#pseudo", pseudo)
    p.select_option("#classe", "Iop")
    p.click("button:has-text('Créer ma fiche')")
    p.wait_for_load_state("load")
    if "/inscription" in p.url:
        ctx.defaut(f"la fiche n'est pas créée ({p.inner_text('main')[:150]!r})")
        return
    if p.locator(".bar a", has_text="Créer ma fiche").count():
        ctx.defaut("« Créer ma fiche » reste affiché après la création")
    if p.locator(".bar .ma-fiche").count() == 0:
        ctx.defaut("pas de lien « Ma fiche » après la création")
    ctx.aller(f"/etages/{ouvert}")
    cases = p.locator("li.bloc-carte input[data-ref]:not([disabled])")
    if cases.count() == 0:
        ctx.defaut("la nouvelle fiche ne peut pas cocher de bloc")
    else:
        cases.first.check(force=True)
        p.wait_for_timeout(600)
        p.reload()
        if not p.locator("li.bloc-carte input[data-ref]").first.is_checked():
            ctx.defaut("la première coche de la nouvelle fiche n'est pas conservée")
        p.locator("li.bloc-carte input[data-ref]").first.uncheck(force=True)
        p.wait_for_timeout(500)
    ctx.aller("/grimpeurs")
    if pseudo not in p.inner_text("#roster"):
        ctx.defaut(f"{pseudo} absent de la page Grimpeurs")


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
    # Le serveur de recette `base` ouvre l'étage 1 (le 0 est terminé) ; la démo garde le 0 seul ouvert.
    ouvert = 0 if mode == "demo" else 1
    nouveau = f"Novice{largeur}" if mode == "base" else {360: "Passant", 768: "Nouvelle"}.get(largeur)
    profils = [("Brindille", False), ("Marceau", True)] + ([(nouveau, False)] if nouveau else [])
    for profil, est_admin in profils:
        novice = profil == nouveau
        etiquette = f"{mode}-{'admin' if est_admin else ('nouveau' if novice else 'grimpeur')}"
        print(f"== {etiquette} à {largeur} px")
        contexte = navigateur.new_context(viewport={"width": largeur, "height": HAUTEUR[largeur]}, locale="fr-FR",
                                          has_touch=largeur < 768, is_mobile=largeur < 768,
                                          reduced_motion="reduce")  # le décor animé ne sert à rien ici
        contexte.route(re.compile(r"https://(www\.)?duffus\.fr/.*"), lambda r: r.fulfill(
            status=200, content_type="text/html", body="<title>Duffus (simulé)</title><p>guide</p>"))
        page = contexte.new_page()
        page.set_default_timeout(15000)
        ctx = Contexte(page, rapport, etiquette, serveur.adresse, captures, largeur)
        ctx.mode = mode
        page.add_init_script("document.addEventListener('securitypolicyviolation', e => "
                             "console.error('Content Security Policy : ' + e.violatedDirective + ' ' + e.blockedURI))")
        connecter(ctx, profil)
        try:
            if novice:
                creer_fiche(ctx, profil, ouvert)
                continue
            ctx.aller("/")
            ctx.photo("accueil")
            parcours_menu(ctx, a_fiche=not est_admin, admin=est_admin)
            crawler(ctx, limite)
            desactives(ctx)
            sans_trace_de_quete(ctx)
            if mode == "base":
                requetes = [("kar", "kar"), ("bouf", "bouf"), ("incarnam", "incarnam"), ("tour", None),
                            ("brin" if not est_admin else "karam", None), ("eleonore", "éléonore")]
                recherche(ctx, requetes, scelles, est_admin)
                recherche_v5(ctx, est_admin)
            if not est_admin:
                # un étage scellé : introuvable pour un grimpeur
                for n in (ouvert + 1, 25, 9999):
                    ctx.aller(f"/etages/{n}", attendu=404)
            autre = None
            ctx.aller("/grimpeurs")
            moi = page.locator(".bar .ma-fiche").get_attribute("href") if page.locator(".bar .ma-fiche").count() else ""
            for h in liens_internes(page, serveur.adresse):
                if re.fullmatch(r"/grimpeurs/\d+", h) and h != moi:
                    autre = h.rsplit("/", 1)[1]
                    break
            if est_admin:
                if mode == "base":
                    correction_admin(ctx, ouvert)
            else:
                pseudo = page.locator(".bar .ma-fiche").text_content().split("(")[-1].strip(" )") if moi else profil
                ctx.aller(f"/etages/{ouvert}")
                if structure_blocs(ctx, ouvert) == 0:
                    ctx.defaut(f"étage {ouvert} sans bloc")
                ctx.controler(f"étage {ouvert}")
                lien_duffus(ctx)
                cocher_un_bloc(ctx, ouvert, pseudo)
                point_principales(ctx, ouvert)
                donjons_et_succes(ctx, ouvert)
                filtres_url(ctx, ouvert)
                refus_autre_fiche(ctx, autre, ouvert)
                fiche_et_tableau(ctx, ouvert)
                if mode == "base":  # l'étage 0 est terminé : on peut encore y compléter sa fiche
                    ctx.aller("/etages/0")
                    structure_blocs(ctx, 0)
                    ctx.controler("étage 0 (terminé)")
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
