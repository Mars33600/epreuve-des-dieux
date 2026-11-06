"""Ce que les pages affichent, calculé une fois par requête à partir du dépôt et du domaine.

Une seule fonction du domaine alimente chaque chiffre (SPEC §5.4) : la jauge vient toujours de
`bareme.calculer_jauge`, les compteurs « 7/12 » de `progression.compteurs`. Les gabarits ne font
que mettre en forme ; ils ne reçoivent jamais un étage scellé (sauf l'admin).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
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
    ElementRef,
    Etage,
    Grimpeur,
    Regles,
)
from epreuve.domaine.progression import avancement, compteurs, qui
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
                  "Terminer toutes les parties rouges du guide : blocs et moitiés principales.", "i-princ"),
    InfoCategorie("secondaires", NOM_CATEGORIE["secondaires"], "Second.",
                  "Terminer toutes les parties jaunes du guide : blocs et moitiés secondaires.", "i-second"),
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


def texte_quetes_bloc(bloc) -> str:
    """Le vrai compte des quêtes d'un bloc ou d'une moitié, accordé : « 1 principale », « 7 principales »,
    « 12 secondaires ». Une partie ne porte que des quêtes de sa nature ; un mélange (bloc pas encore reconstruit)
    s'écrit « 24 quêtes, dont 23 principales »."""
    n, p = bloc.nb_quetes, bloc.nb_principales
    if n == 0:
        return "aucune quête"
    if p in (0, n):
        return f"{n} {'principale' if p else 'secondaire'}{'s' if n > 1 else ''}"
    return f"{n} quêtes, dont {p} principale{'s' if p > 1 else ''}"


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


_MASCULINS = {"château", "dojo", "laboratoire", "temple", "clos", "repaire", "palais", "antre", "fort", "manoir",
              "donjon", "marais", "bois", "mont", "col", "pic", "port", "jardin", "sanctuaire", "monastère"}


def avec_article(nom: str) -> str:
    """« Crypte de Kardorim » → « la Crypte de Kardorim » ; « Château Ensablé » → « le Château Ensablé »."""
    premier = nom.split(" ", 1)[0].lower().strip("'’")
    if premier and premier[0] in "aeiouyàâéèêîôû":
        return f"l'{nom}"
    return f"le {nom}" if premier in _MASCULINS else f"la {nom}"


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

    @property
    def points_max(self) -> int:
        """Points qu'un grimpeur peut rapporter sur cet étage : une par catégorie non vide (4 au plus)."""
        return self.jauge.nb_categories

    def avancement(self, grimpeur_id: int | None) -> tuple[int, int]:
        return avancement(self.contenu, self.coches_de(grimpeur_id))

    @property
    def nb_principales(self) -> int:
        """Les blocs principaux de l'étage (le point « Quêtes principales » les demande tous)."""
        return len(self.contenu.blocs_de_nature("principale"))

    @property
    def nb_secondaires(self) -> int:
        return len(self.contenu.blocs_de_nature("secondaire"))

    def qui_bloc(self, bloc_id: int, fait: bool) -> list[Grimpeur]:
        """Les actifs qui ont (fait=True) ou n'ont pas (fait=False) terminé le bloc, par pseudo."""
        return qui(ElementRef("bloc", bloc_id), self.grimpeurs, self.coches, fait)

    def grimpeurs_par_statut(self, statut: str) -> list[tuple[Grimpeur, int]]:
        """(grimpeur, points sur cet étage), du plus avancé au moins avancé, puis par pseudo."""
        lignes = [(g, self.points(g.id)) for g in self.grimpeurs if g.statut == statut]
        return sorted(lignes, key=lambda t: (-t[1], t[0].pseudo.lower()))

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


def separer_courant[T](elements: list[T], etage_de) -> tuple[T | None, list[T]]:
    """(l'élément de l'étage en cours, les autres) sur une liste du plus récent au plus ancien.

    L'étage en cours est l'étage ouvert ; s'il n'y en a plus (fin de l'épreuve), le plus récent, comme
    `tableau.a_faire`. Les pages l'affichent au premier niveau et plient les autres : la liste grossit
    d'un étage par semaine, la page ne doit pas grossir avec elle (retour de recette v4).
    """
    if not elements:
        return None, []
    courant = next((x for x in elements if etage_de(x).statut == "ouvert"), elements[0])
    return courant, [x for x in elements if x is not courant]


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
