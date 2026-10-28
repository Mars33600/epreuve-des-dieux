"""Lecture d'une fiche Duffus (`quest_pages`) → contenu structuré de `FicheQuete` (SPEC §4.4 bis).

Le HTML de Duffus est structuré par des classes CSS stables (relevé B0, addendum de LOTS.md) :
`div.qstep <type>` pour chaque étape, `.qpos` pour une position, `.recipe-item` + `.prevoir-qty` pour un objet
à prévoir, `.combat-line` et `.mob-stats-name` pour les monstres, `.qk-card` pour l'objectif.
On découpe avec le parseur HTML de la bibliothèque standard, puis chaque texte passe par `nettoyer_fiche`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser

import nh3

from epreuve.db.depot import ContenuFiche, PrerequisBrut
from epreuve.domaine.fiche import Besoin, EtapeFiche, Position

# --- Nettoyage ----------------------------------------------------------------------------------------------

BALISES = {"p", "br", "b", "strong", "i", "em", "u", "ul", "ol", "li", "h3", "h4", "h5", "div", "span", "a",
           "table", "thead", "tbody", "tr", "td", "th"}
_LIEN_QUETE = re.compile(r"^/quete/([^/?#]+)/?$")


def nettoyer_fiche(html: str, quetes_ouvertes: Mapping[str, str]) -> str:
    """Liste blanche de balises de mise en forme, sans image, script, style, attribut d'événement ni lien
    vers duffus.fr. Un lien `/quete/<slug>` vers une quête d'un étage ouvert est réécrit vers notre fiche
    (`quetes_ouvertes` : slug Duffus → notre adresse) ; tout autre lien perd son adresse (le texte reste)."""

    def filtre(balise: str, attribut: str, valeur: str) -> str | None:
        if balise == "a" and attribut == "href":
            m = _LIEN_QUETE.match(valeur.strip())
            return quetes_ouvertes.get(m.group(1)) if m else None
        return None

    propre = nh3.clean(html or "", tags=BALISES, clean_content_tags={"script", "style", "svg", "button"},
                       attributes={"a": {"href"}}, attribute_filter=filtre, link_rel=None, url_schemes=set())
    return re.sub(r"<a>(.*?)</a>", r"\1", propre, flags=re.S).strip()


# --- Un petit arbre HTML ------------------------------------------------------------------------------------

_VIDES = {"br", "img", "input", "hr", "meta", "link", "source", "wbr"}


@dataclass
class Noeud:
    balise: str
    attrs: dict[str, str]
    enfants: list[Noeud | str] = field(default_factory=list)

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def texte(self) -> str:
        return " ".join("".join(e if isinstance(e, str) else " " + e.texte() + " " for e in self.enfants).split())

    def html(self) -> str:
        dedans = "".join(escape(e, quote=False) if isinstance(e, str) else e.html_complet() for e in self.enfants)
        return dedans

    def html_complet(self) -> str:
        attrs = "".join(f' {k}="{escape(v or "")}"' for k, v in self.attrs.items())
        if self.balise in _VIDES:
            return f"<{self.balise}{attrs}>"
        return f"<{self.balise}{attrs}>{self.html()}</{self.balise}>"

    def tous(self):
        for e in self.enfants:
            if isinstance(e, Noeud):
                yield e
                yield from e.tous()

    def par_classe(self, classe: str) -> list[Noeud]:
        return [n for n in self.tous() if classe in n.classes]


class _Arbre(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.racine = Noeud("racine", {})
        self.pile = [self.racine]

    def handle_starttag(self, tag, attrs):
        n = Noeud(tag, {k: v or "" for k, v in attrs})
        self.pile[-1].enfants.append(n)
        if tag not in _VIDES:
            self.pile.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.pile) - 1, 0, -1):
            if self.pile[i].balise == tag:
                del self.pile[i:]
                return

    def handle_data(self, data):
        self.pile[-1].enfants.append(data)


def arbre(html: str) -> Noeud:
    p = _Arbre()
    p.feed(html or "")
    p.close()
    return p.racine


# --- Lecture d'une fiche --------------------------------------------------------------------------------------

TITRES_ETAPES = {"dialogue": "Dialogue", "move": "Déplacement", "marche": "Déplacement à pied",
                 "clique": "Action", "combat": "Combat", "craft": "Fabrication", "text": "À savoir",
                 "mob-stats-card": "Monstre"}
_COORD = re.compile(r"\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]")
_QTE = re.compile(r"(\d[\d\s \xa0]*)")
_VAINCRE = re.compile(r"(\d+)\s*x\s*$")


def _entier(texte: str, defaut: int = 1) -> int:
    m = _QTE.search(texte or "")
    return int(re.sub(r"\D", "", m.group(1))) if m else defaut


def _coord(texte: str) -> tuple[int, int] | None:
    m = _COORD.search(texte or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _etapes(racine: Noeud, ouvertes: Mapping[str, str]) -> tuple[list[EtapeFiche], list[Position]]:
    etapes: list[EtapeFiche] = []
    positions: list[Position] = []
    for carte in racine.par_classe("qk-card"):
        texte = nettoyer_fiche(carte.html(), ouvertes)
        if arbre(texte).texte():
            etapes.append(EtapeFiche(len(etapes) + 1, "Objectif", texte))
    for bloc in racine.par_classe("qstep"):
        if bloc.balise != "div":
            continue
        genre = next((c for c in bloc.classes if c in TITRES_ETAPES), None)
        droite = next((n for n in bloc.par_classe("cell-right")), None) or bloc
        texte = nettoyer_fiche(droite.html(), ouvertes)
        for p in bloc.par_classe("qpos"):
            xy = _coord(p.texte())
            if xy:
                positions.append(Position(droite.texte()[:120] or "Position", xy[0], xy[1], None))
        if genre == "mob-stats-card":
            continue  # la fiche de monstre est reprise dans « monstres »
        if arbre(texte).texte():  # une étape sans aucun texte (« <ul></ul> ») n'apporte rien
            etapes.append(EtapeFiche(len(etapes) + 1, TITRES_ETAPES.get(genre or "", "Étape"), texte))
    return etapes, positions


def _objets(racine: Noeud, manuels: list[dict]) -> list[Besoin]:
    objets: dict[str, int] = {}
    for item in racine.par_classe("recipe-item"):
        nom = next((n.texte() for n in item.par_classe("recipe-name")), "")
        qte = next((_entier(n.texte()) for n in item.par_classe("prevoir-qty")), 1)
        if nom:
            objets[nom] = objets.get(nom, 0) + qte
    for m in manuels or []:
        if m.get("label"):
            objets.setdefault(str(m["label"]), int(m.get("qty") or 1))
    return [Besoin(n, q) for n, q in objets.items()]


def _monstres(racine: Noeud) -> list[Besoin]:
    monstres: dict[str, int] = {}
    for ligne in racine.par_classe("combat-line"):
        avant = ""
        for e in ligne.enfants:
            if isinstance(e, str):
                avant += e
            elif e.balise == "a":
                m = _VAINCRE.search(avant)
                nom = e.texte()
                if nom:
                    monstres[nom] = monstres.get(nom, 0) + (int(m.group(1)) if m else 1)
                avant = ""
            else:
                avant += e.texte()
    for n in racine.par_classe("mob-stats-name"):
        monstres.setdefault(n.texte(), 1)
    return [Besoin(n, q) for n, q in monstres.items() if n]


def _recompenses(r: Mapping | None) -> list[str]:
    r = r or {}
    sortie = [str(r[k]) for k in ("xp", "kamas") if r.get(k)]
    for item in r.get("items") or []:
        sortie.append(f"{item.get('qty', 1)} × {item.get('label', '?')}" if isinstance(item, dict) else str(item))
    for autre in r.get("others") or []:
        sortie.append(autre.get("label") or autre.get("text") or json.dumps(autre, ensure_ascii=False)
                      if isinstance(autre, dict) else str(autre))
    return sortie


def prerequis_de(page: Mapping, slug_vers_id: Mapping[str, str]) -> list[PrerequisBrut]:
    sortie: list[PrerequisBrut] = []
    try:
        liens = json.loads(page.get("prereq_quests") or "[]")
    except ValueError:
        liens = []
    for lien in liens:
        m = _LIEN_QUETE.match((lien.get("link") or "").strip())
        sortie.append(PrerequisBrut(duffus_id=slug_vers_id.get(m.group(1)) if m else None,
                                    nom=lien.get("title") or "Quête"))
    for p in page.get("prereqs") or []:
        if (p.get("text") or "").strip():
            sortie.append(PrerequisBrut(nom=p["text"].strip()))
    return sortie


def lire_fiche(page: Mapping, entree: Mapping, slug_vers_id: Mapping[str, str],
               ouvertes: Mapping[str, str], ressources: list[dict] | None = None) -> ContenuFiche:
    """La fiche Duffus d'une entrée du guide (`quest_list`), de sa page (`quest_pages`) et de ses ressources
    à prévoir (`quest_resources`)."""
    racine = arbre(page.get("content_html") or "")
    etapes, positions = _etapes(racine, ouvertes)
    if (entree.get("lancement") or "").strip():
        etapes.insert(0, EtapeFiche(0, "Pour la lancer", nettoyer_fiche(escape(entree["lancement"]), ouvertes)))
    note = " ".join(dict.fromkeys(x.strip() for x in (entree.get("note"), entree.get("note2")) if x and x.strip()))
    if note:
        etapes.insert(0, EtapeFiche(0, "Note du guide", nettoyer_fiche(escape(note), ouvertes)))
    etapes = [EtapeFiche(i, e.titre, e.texte_html, e.objectifs) for i, e in enumerate(etapes, 1)]
    meta = page.get("meta") or {}
    depart = _coord(meta.get("startCoords") or "")
    if depart:
        positions.insert(0, Position(f"Départ : {meta.get('startNpc') or 'PNJ'}", depart[0], depart[1],
                                     meta.get("zone")))
    vues = set()
    positions = [p for p in positions if (p.x, p.y, p.libelle) not in vues and not vues.add((p.x, p.y, p.libelle))]
    succes = entree.get("succes") or []
    return ContenuFiche(
        prerequis=prerequis_de(page, slug_vers_id), etapes=etapes,
        objets=_objets(racine, [*(page.get("manual_resources") or []),
                                *({"label": r["name"], "qty": r["qty"]} for r in ressources or [])]),
        monstres=_monstres(racine), positions=positions, succes_lie=", ".join(succes) or None,
        recompenses=_recompenses(page.get("rewards")),
    )  # fmt: skip
