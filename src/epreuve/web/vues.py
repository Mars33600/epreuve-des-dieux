"""Ce que les pages affichent, calculé une fois par requête à partir du dépôt et du domaine.

Une seule fonction du domaine alimente chaque chiffre (SPEC §5.4) : la jauge vient toujours de
`bareme.calculer_jauge`, les compteurs « 7/12 » de `progression.compteurs`. Les gabarits ne font
que mettre en forme ; ils ne reçoivent jamais un étage scellé (sauf l'admin).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from epreuve.domaine.bareme import (
    EtatCategorie,
    EtatJauge,
    calculer_jauge,
    categories_grimpeur,
    points_grimpeur,
)
from epreuve.domaine.modeles import (
    CATEGORIES,
    NOM_CATEGORIE,
    CaseSucces,
    Categorie,
    Coches,
    ContenuEtage,
    Donjon,
    ElementRef,
    Etage,
    Grimpeur,
    Quete,
    Regles,
)
from epreuve.domaine.progression import avancement, compteurs
from epreuve.domaine.textes import date_paris


@dataclass(frozen=True)
class InfoCategorie:
    cle: Categorie
    nom: str
    court: str
    desc: str
    icone: str


INFOS_CATEGORIES: tuple[InfoCategorie, ...] = (
    InfoCategorie("donjons", NOM_CATEGORIE["donjons"], "Donjons", "Vaincre tous les donjons de l'étage.", "i-donjon"),
    InfoCategorie("full_succes", NOM_CATEGORIE["full_succes"], "Succès",
                  "Cocher les 5 succès de chaque donjon.", "i-succes"),
    InfoCategorie("principales", NOM_CATEGORIE["principales"], "Princ.",
                  "Les quêtes qui mènent à un Dofus, l'œuf légendaire du jeu.", "i-princ"),
    InfoCategorie("secondaires", NOM_CATEGORIE["secondaires"], "Second.",
                  "Toutes les autres quêtes de l'étage.", "i-second"),
)
assert tuple(i.cle for i in INFOS_CATEGORIES) == CATEGORIES


def texte_point_donjons(n: int) -> str:
    """La règle du point Donjons, dite juste : il faut vaincre tous les donjons de l'étage (1 seul, ou N)."""
    if n == 1:
        return "Vaincre ce donjon rapporte 1 point (Donjons)"
    return f"Vaincre les {n} donjons de l'étage rapporte 1 point (Donjons)"


def texte_point_full(n: int) -> str:
    """La règle du point Full succès : les 5 cases de chaque donjon de l'étage."""
    if n == 1:
        return "Cocher les 5 cases de ce donjon rapporte 1 point (Full succès)"
    return f"Cocher les 5 cases des {n} donjons de l'étage rapporte 1 point (Full succès)"


def pct(faits: int, total: int) -> str:
    """Classe CSS « p-45 » (par pas de 5 %) : la CSP interdit style="--p:45%"."""
    if total <= 0:
        return "p-0"
    return f"p-{min(100, max(0, round(faits / total * 20) * 5))}"


def pct1(valeur: int, total: int) -> str:
    """Classe CSS « q-37 » (au pour cent près) : la position d'un remplissage ou du trait de palier."""
    if total <= 0:
        return "q-0"
    return f"q-{min(100, max(0, round(valeur / total * 100)))}"


def cle(ref: ElementRef) -> str:
    return f"{ref.type}:{ref.id}"


@dataclass
class LigneDonjon:
    donjon: Donjon
    cases: tuple[CaseSucces, ...]
    apres: Quete | None = None  # la quête qui précède le donjon dans le guide : « moment conseillé »
    type: str = "donjon"


@dataclass
class LigneQuete:
    quete: Quete
    type: str = "quete"


@dataclass
class Bloc:
    nom: str | None
    lignes: list[LigneDonjon | LigneQuete] = field(default_factory=list)
    donjons: bool = False


NOM_BLOC_DONJONS = "Donjons de l'étage"
_MASCULINS = {"château", "dojo", "laboratoire", "temple", "clos", "repaire", "palais", "antre", "fort", "manoir",
              "donjon", "marais", "bois", "mont", "col", "pic", "port", "jardin", "sanctuaire", "monastère"}


def avec_article(nom: str) -> str:
    """« Crypte de Kardorim » → « la Crypte de Kardorim » ; « Château Ensablé » → « le Château Ensablé »."""
    premier = nom.split(" ", 1)[0].lower().strip("'’")
    if premier and premier[0] in "aeiouyàâéèêîôû":
        return f"l'{nom}"
    return f"le {nom}" if premier in _MASCULINS else f"la {nom}"


def quete_avant(donjon: Donjon, quetes: Iterable[Quete]) -> Quete | None:
    """La dernière quête du même bloc qui précède le donjon dans l'ordre du guide Duffus, s'il y en a une."""
    if donjon.bloc is None:
        return None
    avant = [q for q in quetes if q.bloc == donjon.bloc and q.ordre < donjon.ordre]
    return max(avant, key=lambda q: (q.ordre, q.id), default=None)


def blocs_du_guide(contenu: ContenuEtage) -> list[Bloc]:
    """En tête, tous les donjons de l'étage, chacun dans son dépliant (avec le « moment conseillé » : après quelle
    quête le faire) ; puis le fil du guide, qui ne contient que des quêtes."""
    ordonnes = sorted(contenu.donjons, key=lambda d: (d.ordre, d.id))
    tete = Bloc(NOM_BLOC_DONJONS, [LigneDonjon(d, contenu.cases_du_donjon(d.id), quete_avant(d, contenu.quetes))
                                   for d in ordonnes], donjons=True)
    par_bloc: dict[str, list[tuple[int, LigneQuete]]] = {}
    for q in contenu.quetes:
        par_bloc.setdefault(q.bloc, []).append((q.ordre, LigneQuete(q)))
    classes = sorted(par_bloc.items(), key=lambda kv: min(o for o, _ in kv[1]))
    blocs = [Bloc(nom, [ligne for _, ligne in sorted(lignes, key=lambda t: t[0])]) for nom, lignes in classes]
    return ([tete] if tete.lignes else []) + blocs


@dataclass
class VueEtage:
    etage: Etage
    contenu: ContenuEtage
    grimpeurs: list[Grimpeur]
    coches: dict[int, Coches]
    jauge: EtatJauge
    compteurs: dict[str, int]
    regles: Regles

    def coches_de(self, grimpeur_id: int | None) -> Coches:
        if grimpeur_id is None:
            return Coches(0)
        return self.coches.get(grimpeur_id, Coches(grimpeur_id))

    def categories(self, grimpeur_id: int | None) -> dict[Categorie, EtatCategorie]:
        return categories_grimpeur(self.contenu, self.coches_de(grimpeur_id))

    def points(self, grimpeur_id: int | None) -> int:
        return points_grimpeur(self.contenu, self.coches_de(grimpeur_id), self.regles)

    def avancement(self, grimpeur_id: int | None) -> tuple[int, int]:
        return avancement(self.contenu, self.coches_de(grimpeur_id))

    @property
    def nb_principales(self) -> int:
        return sum(1 for q in self.contenu.quetes if q.nature == "principale")

    @property
    def nb_secondaires(self) -> int:
        return len(self.contenu.quetes) - self.nb_principales

    def grimpeurs_par_statut(self, statut: str) -> list[tuple[Grimpeur, int]]:
        """(grimpeur, points sur cet étage), du plus avancé au moins avancé, puis par pseudo."""
        lignes = [(g, self.points(g.id)) for g in self.grimpeurs if g.statut == statut]
        return sorted(lignes, key=lambda t: (-t[1], t[0].pseudo.lower()))

    def blocs(self) -> list[Bloc]:
        return blocs_du_guide(self.contenu)

    def classique(self, donjon_id: int) -> CaseSucces | None:
        return next((c for c in self.contenu.cases_du_donjon(donjon_id) if c.est_classique), None)


async def charger_vue_etage(depot, etage: Etage, regles: Regles, grimpeurs: list[Grimpeur] | None = None) -> VueEtage:
    contenu = await depot.contenu_etage(etage.id)
    gs = grimpeurs if grimpeurs is not None else await depot.grimpeurs()
    coches = await depot.coches_etage(etage.id)
    return VueEtage(etage, contenu, gs, coches, calculer_jauge(contenu, gs, coches, regles),
                    {cle(r): n for r, n in compteurs(contenu, gs, coches).items()}, regles)


def formule_palier(jauge: EtatJauge, regles: Regles) -> str:
    if jauge.palier_manuel:
        return "Palier fixé par un admin"
    m = regles.points_par_joueur
    m_txt = str(m.numerator) if m.denominator == 1 else f"{m.numerator}/{m.denominator}"
    n = f"{jauge.actifs} grimpeur{'s' if jauge.actifs > 1 else ''} actif{'s' if jauge.actifs > 1 else ''}"
    if jauge.nb_categories == 4:
        return f"Palier = {m_txt} × {n}"
    return f"Palier = {m_txt} × {n} × {jauge.nb_categories} catégories sur 4, arrondi au-dessus"


def titre_etage(etage) -> str:
    """« Étage 3 · Les Pics » ; juste « Étage 3 » quand l'étage n'a pas de nom propre (jamais « Étage 3 · Étage 3 »)."""
    nom = (etage.nom or "").strip()
    if not nom or nom.casefold() == f"étage {etage.numero}":
        return f"Étage {etage.numero}"
    return f"Étage {etage.numero} · {nom}"


def texte_jauge(jauge: EtatJauge) -> str:
    """Toujours présent et lisible sans la couleur (SPEC §4.5)."""
    pause = f", {jauge.en_pause} en pause" if jauge.en_pause else ""
    actifs = f"{jauge.actifs} grimpeur{'s' if jauge.actifs > 1 else ''} actif{'s' if jauge.actifs > 1 else ''}"
    if jauge.pleine:
        debut = f"Score {jauge.score} sur un palier de {jauge.palier} : la jauge est pleine."
    else:
        debut = (f"Score {jauge.score} sur un palier de {jauge.palier}, il en manque {jauge.manquants}.")
    return f"{debut} {actifs}{pause}."


def verdicts(etage: Etage, maintenant: datetime) -> tuple[str, str]:
    """(jauge pleine, jauge pas pleine) : app.js bascule de l'un à l'autre après une coche. Aucun scellé nommé."""
    plein = "Jauge pleine : un admin va vérifier et ouvrir le prochain étage."
    plancher = etage.date_plancher_suivant
    if plancher is not None and maintenant < plancher:
        return plein, (f"Un admin pourra ouvrir le prochain étage quand la jauge sera pleine, "
                       f"et pas avant le {date_paris(plancher)}.")
    return plein, "Un admin pourra ouvrir le prochain étage quand la jauge sera pleine."


def encoches(jauge: EtatJauge) -> list[str]:
    """Une encoche par point requis, remplies dans l'ordre des catégories ; au-delà du palier, « over »."""
    pleines = [c for c in CATEGORIES for _ in range(jauge.points_par_categorie.get(c, 0))]
    n = max(jauge.palier, jauge.score)
    return [(f"c-{pleines[i]}" + (" over" if i >= jauge.palier else "")) if i < len(pleines) else "vide"
            for i in range(n)]


def tri_grimpeurs(grimpeurs: Iterable[Grimpeur], est_admin: bool) -> list[Grimpeur]:
    """Actifs d'abord, puis en pause, par ordre alphabétique. Jamais de tri par score. Exclus : admin seulement."""
    rang = {"actif": 0, "pause": 1, "exclu": 2}
    return sorted((g for g in grimpeurs if est_admin or g.statut != "exclu"),
                  key=lambda g: (rang[g.statut], g.pseudo.casefold()))


def jauge_json(jauge: EtatJauge) -> dict:
    return {"score": jauge.score, "palier": jauge.palier, "actifs": jauge.actifs, "en_pause": jauge.en_pause,
            "pleine": jauge.pleine, "points_par_categorie": dict(jauge.points_par_categorie)}


def categories_json(cats: dict[Categorie, EtatCategorie]) -> dict:
    return {c: {"faits": e.faits, "total": e.total, "acquise": e.acquise} for c, e in cats.items()}
