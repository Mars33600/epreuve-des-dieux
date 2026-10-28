"""Les pages des grimpeurs (SPEC §4.2 à §4.6, ARCHITECTURE §9).

    GET  /etages/{n}                 l'onglet d'un étage : ma progression, la jauge, le filtre, la liste unique
    GET  /etages/{n}/quetes/{id}     la fiche de quête : fragment (Accept: text/html-fragment) ou page complète
    GET  /grimpeurs                  toutes les fiches + le filtre « qui n'a pas fait… ? » (?quoi=…)
    GET  /grimpeurs/{id}             la fiche d'un grimpeur (?edition=1 : mode édition de l'admin)
    POST /grimpeurs/moi              modifier son pseudo, sa classe, son niveau
    GET/POST /inscription            créer sa fiche (membre de la liste officielle, après l'ouverture)

Brouillard de guerre : un étage scellé répond 404 comme un étage inexistant (sauf admin), et les
prérequis d'un étage scellé sont masqués par `masquer_prerequis_scelles` sur tous les chemins.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from epreuve.db.depot import DejaInscrit, Introuvable, PasSurLaListe, PseudoDejaPris
from epreuve.domaine.classes import CLASSES, repartition_classes
from epreuve.domaine.fiche import FicheQuete, masquer_prerequis_scelles
from epreuve.domaine.modeles import CATEGORIES, NOM_CATEGORIE, ElementRef, Etage, Grimpeur
from epreuve.domaine.progression import qui, qui_categorie
from epreuve.domaine.textes import valider_pseudo
from epreuve.domaine.visibilite import NB_SCELLES_DECORATIFS, etage_cochable, etages_visibles
from epreuve.web.auth import Refus, Visiteur, exiger_connecte, exiger_grimpeur, mode, verifier_ecriture
from epreuve.web.rendu import rendre
from epreuve.web.vues import (
    VueEtage,
    charger_vue_etage,
    encoches,
    formule_palier,
    texte_jauge,
    tri_grimpeurs,
    verdicts,
)

routeur = APIRouter()
IMAGES_ETAGES = Path(__file__).resolve().parents[3] / "donnees" / "images" / "etages"
INTROUVABLE = "Introuvable."
MESSAGES_FICHE = {"pseudo": "Le pseudo doit faire entre 2 et 30 caractères.",
                  "pris": "Ce pseudo est déjà pris (sans tenir compte des majuscules).",
                  "classe": "Classe inconnue.", "niveau": "Le niveau va de 1 à 200."}


def _s(request: Request):
    return request.app.state


async def etage_visible(request: Request, numero: int, v: Visiteur) -> Etage:
    """L'étage s'il est visible pour ce visiteur ; sinon 404, exactement comme un étage qui n'existe pas."""
    etage = await _s(request).depot.etage_par_numero(numero)
    if etage is None or (etage.statut == "scelle" and not v.est_admin):
        raise Refus(404, INTROUVABLE)
    return etage


def peut_cocher_soi(v: Visiteur, etage: Etage, regles) -> bool:
    g = v.grimpeur
    return (g is not None and etage_cochable(etage) and g.statut != "exclu"
            and (g.statut != "pause" or regles.pause_peut_cocher))


def contexte_etage(request: Request, vue: VueEtage) -> dict:
    s = _s(request)
    plein, pas_plein = verdicts(vue.etage, s.horloge())
    return {"vue": vue, "jauge": vue.jauge, "encoches": encoches(vue.jauge),
            "formule": formule_palier(vue.jauge, s.regles), "texte_jauge": texte_jauge(vue.jauge),
            "verdict_plein": plein, "verdict_pas_plein": pas_plein}


async def tour(request: Request, v: Visiteur):
    """L'accueil connecté : la tour, la jauge de l'étage ouvert, la répartition des classes."""
    s = _s(request)
    etages = etages_visibles(await s.depot.etages(), est_admin=False)  # la tour ne montre jamais un scellé
    ouvert = next((e for e in etages if e.statut == "ouvert"), None)
    grimpeurs = await s.depot.grimpeurs()
    ctx: dict = {"etages": etages, "ouvert": ouvert, "nb_scelles": NB_SCELLES_DECORATIFS, "vue": None}
    if ouvert is not None:
        vue = await charger_vue_etage(s.depot, ouvert, s.regles, grimpeurs)
        ctx.update(contexte_etage(request, vue))
    avec_classe = [g for g in grimpeurs if g.classe is not None]
    repartition = sorted(repartition_classes(avec_classe), key=lambda r: (-r.actifs, r.classe))
    ctx["classes"] = repartition
    ctx["classes_max"] = max([1, *(r.actifs for r in repartition)])
    ctx["classes_absentes"] = sum(1 for r in repartition if r.actifs == 0)
    return await rendre(request, "tour.html", ctx)


@routeur.get("/etages/{numero}")
async def page_etage(request: Request, numero: int):
    v = await exiger_grimpeur(request)
    s = _s(request)
    etage = await etage_visible(request, numero, v)
    vue = await charger_vue_etage(s.depot, etage, s.regles)
    tranches = etages_visibles(await s.depot.etages(), est_admin=False)
    bilan = await s.depot.bilan(etage.id) if etage.statut == "termine" else None
    ctx = contexte_etage(request, vue) | {
        "etage": etage, "tranches": tranches, "bilan": bilan, "cible": v.grimpeur, "ambiance": etage.ambiance_url,
        "cochable": peut_cocher_soi(v, etage, s.regles), "motif_requis": False,
    }
    return await rendre(request, "etage.html", ctx)


@routeur.get("/etages/{numero}/image")
async def image_etage(request: Request, numero: int):
    """L'image d'ambiance d'un étage, servie seulement si l'étage est visible (ouvert, terminé, ou admin).

    Les images ne sont pas sous /static : une adresse devinée ne montre rien d'un étage scellé (404).
    """
    v = await exiger_grimpeur(request)
    await etage_visible(request, numero, v)
    fichier = IMAGES_ETAGES / f"etage-{numero}.webp"
    if not fichier.is_file():
        raise Refus(404, "Image introuvable.")
    return FileResponse(fichier, media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"})


async def etage_de_quete(depot) -> dict[int, int]:
    """Quête → numéro de son étage, pour savoir si un prérequis est scellé (une seule requête en base)."""
    return await depot.etage_des_quetes()


async def fiche_pour(request: Request, v: Visiteur, etage: Etage, quete_id: int) -> tuple[FicheQuete | None, dict]:
    s = _s(request)
    carte = await etage_de_quete(s.depot)
    fiche = await s.depot.fiche_quete(quete_id)
    if fiche is not None and not v.est_admin:
        visibles = {e.numero for e in etages_visibles(await s.depot.etages(), est_admin=False)}
        fiche = masquer_prerequis_scelles(fiche, visibles, carte)
    return fiche, carte


@routeur.get("/etages/{numero}/quetes/{quete_id}")
async def page_quete(request: Request, numero: int, quete_id: int):
    v = await exiger_grimpeur(request)
    s = _s(request)
    etage = await etage_visible(request, numero, v)
    vue = await charger_vue_etage(s.depot, etage, s.regles)
    quete = next((q for q in vue.contenu.quetes if q.id == quete_id), None)
    if quete is None:
        raise Refus(404, INTROUVABLE)
    fiche, carte = await fiche_pour(request, v, etage, quete_id)
    ref = ElementRef("quete", quete.id)
    ctx = {"etage": etage, "quete": quete, "fiche": fiche, "carte": carte, "vue": vue,
           "cible": v.grimpeur, "cochable": peut_cocher_soi(v, etage, s.regles),
           "pas_fait": qui(ref, vue.grimpeurs, vue.coches, fait=False),
           "fait": qui(ref, vue.grimpeurs, vue.coches, fait=True)}
    if "text/html-fragment" in request.headers.get("accept", ""):
        return await rendre(request, "_quete.html", ctx)
    return await rendre(request, "quete.html", ctx)


@routeur.get("/regles")
async def page_regles(request: Request):
    """Les règles en clair (DECISIONS-V4 §12). Les valeurs viennent de la configuration, jamais écrites en dur."""
    await exiger_grimpeur(request)
    s = _s(request)
    m = s.regles.points_par_joueur
    ouvert = next((e for e in await s.depot.etages() if e.statut == "ouvert"), None)
    return await rendre(request, "regles.html", {
        "m": str(m.numerator) if m.denominator == 1 else f"{m.numerator}/{m.denominator}",
        "ouvert": ouvert, "plancher": ouvert.date_plancher_suivant if ouvert else None})


# ---------------------------------------------------------------- « qui n'a pas fait… ? »

def resoudre_quoi(vue: VueEtage, type_: str, ident: str) -> tuple[str, list[Grimpeur], list[Grimpeur]] | None:
    """(libellé, pas fait, fait) pour une case, une quête, un donjon (sa case classique) ou une catégorie."""
    c = vue.contenu
    if type_ == "categorie":
        if ident not in CATEGORIES:
            return None
        return (f"le point {NOM_CATEGORIE[ident]}",
                qui_categorie(c, ident, vue.grimpeurs, vue.coches, fait=False),
                qui_categorie(c, ident, vue.grimpeurs, vue.coches, fait=True))
    if not ident.isdigit():
        return None
    n = int(ident)
    if type_ == "donjon":
        d = next((d for d in c.donjons if d.id == n), None)
        classique = vue.classique(n) if d else None
        if classique is None:
            return None
        type_, n, libelle = "case", classique.id, f"vaincre {d.nom}"
    elif type_ == "case":
        case = next((x for x in c.cases if x.id == n), None)
        if case is None:
            return None
        d = next(d for d in c.donjons if d.id == case.donjon_id)
        libelle = f"vaincre {d.nom}" if case.est_classique else f"le succès « {case.nom} » ({d.nom})"
    elif type_ == "quete":
        q = next((x for x in c.quetes if x.id == n), None)
        if q is None:
            return None
        libelle = f"la quête « {q.nom} »"
    else:
        return None
    ref = ElementRef(type_, n)  # type: ignore[arg-type]
    return libelle, qui(ref, vue.grimpeurs, vue.coches, False), qui(ref, vue.grimpeurs, vue.coches, True)


@routeur.get("/grimpeurs")
async def page_grimpeurs(request: Request, quoi: str = ""):
    v = await exiger_grimpeur(request)
    s = _s(request)
    grimpeurs = await s.depot.grimpeurs()
    ouvert = next((e for e in await s.depot.etages() if e.statut == "ouvert"), None)
    vue = await charger_vue_etage(s.depot, ouvert, s.regles, grimpeurs) if ouvert else None
    reponse = None
    if vue is not None and ":" in quoi:
        reponse = resoudre_quoi(vue, *quoi.split(":", 1))
    cibles = {g.id for g in reponse[1]} if reponse else set()
    faits = {g.id for g in reponse[2]} if reponse else set()
    liste = tri_grimpeurs(grimpeurs, v.est_admin)
    return await rendre(request, "grimpeurs.html", {
        "grimpeurs": liste, "vue": vue, "ouvert": ouvert, "quoi": quoi, "reponse": reponse,
        "cibles": cibles, "faits": faits, "actifs": sum(g.statut == "actif" for g in liste),
        "en_pause": sum(g.statut == "pause" for g in liste)})


@routeur.get("/grimpeurs/{grimpeur_id}")
async def page_fiche(request: Request, grimpeur_id: int, edition: int = 0, fait: str = "", erreur: str = ""):
    v = await exiger_grimpeur(request)
    s = _s(request)
    g = await s.depot.grimpeur(grimpeur_id)
    if g is None or (g.statut == "exclu" and not v.est_admin):
        raise Refus(404, INTROUVABLE)
    edition_admin = bool(edition) and v.est_admin and v.grimpeur_id != g.id
    soi = v.grimpeur_id == g.id
    grimpeurs = await s.depot.grimpeurs()
    etages = sorted((e for e in await s.depot.etages() if etage_cochable(e)), key=lambda e: -e.numero)
    vues = [await charger_vue_etage(s.depot, e, s.regles, grimpeurs) for e in etages]
    faits = sum(vu.avancement(g.id)[0] for vu in vues)
    total = sum(vu.avancement(g.id)[1] for vu in vues)
    cochable = (soi and peut_cocher_soi(v, etages[0], s.regles)) if etages else False
    return await rendre(request, "fiche.html", {
        "g": g, "vues": vues, "soi": soi, "edition": edition_admin, "global": (faits, total),
        "cochable": cochable or edition_admin, "classes": CLASSES,
        "message": "Fiche enregistrée." if fait else "", "erreur": MESSAGES_FICHE.get(erreur, "")})


@routeur.post("/grimpeurs/moi")
async def modifier_moi(request: Request):
    v = await verifier_ecriture(request)
    if v.grimpeur is None or v.grimpeur.statut == "exclu":
        raise Refus(403, "Tu n'as pas de fiche à modifier.")
    s = _s(request)
    form = await request.form()
    gid = v.grimpeur.id
    try:
        pseudo, classe, niveau = lire_fiche(form, s.regles)
    except ValueError as e:
        return RedirectResponse(f"/grimpeurs/{gid}?erreur={e.args[0]}", status_code=303)
    try:
        await s.depot.modifier_grimpeur(gid, v.discord_id, s.horloge(), pseudo=pseudo, classe=classe,
                                        niveau_declare=niveau)
    except PseudoDejaPris:
        return RedirectResponse(f"/grimpeurs/{gid}?erreur=pris", status_code=303)
    return RedirectResponse(f"/grimpeurs/{gid}?fait=1", status_code=303)


def lire_fiche(form, regles) -> tuple[str, str | None, int | None]:
    """Pseudo (2 à 30 caractères), classe (facultative, une des 19), niveau (facultatif, 1 à 200)."""
    try:
        pseudo = valider_pseudo(str(form.get("pseudo", "")))
    except ValueError as e:
        raise ValueError("pseudo") from e
    classe = str(form.get("classe", "")).strip() or None
    if (classe is None and regles.classe_obligatoire) or (classe is not None and classe not in CLASSES):
        raise ValueError("classe")
    brut = str(form.get("niveau", "")).strip()
    if brut and (not brut.isdigit() or not 1 <= int(brut) <= 200):
        raise ValueError("niveau")
    return pseudo, classe, int(brut) if brut else None


# ---------------------------------------------------------------- inscription

async def _inscription_permise(request: Request) -> Visiteur:
    v = await exiger_connecte(request)
    if mode(request) == "teaser":
        raise Refus(303, "", vers="/")  # aucune fiche avant l'ouverture, même pour un admin
    if v.grimpeur is not None:
        raise Refus(303, "", vers="/")
    return v


@routeur.get("/inscription")
async def inscription(request: Request):
    v = await _inscription_permise(request)
    s = _s(request)
    if s.regles.liste_officielle_obligatoire and v.discord_id not in await s.depot.liste_officielle():
        return await rendre(request, "inscription.html", {"hors_liste": True})
    return await rendre(request, "inscription.html", {"hors_liste": False, "classes": CLASSES, "valeurs": {}})


@routeur.post("/inscription")
async def inscrire(request: Request):
    await verifier_ecriture(request)
    v = await _inscription_permise(request)
    s = _s(request)
    form = await request.form()
    valeurs = {k: str(form.get(k, "")) for k in ("pseudo", "classe", "niveau")}
    try:
        pseudo, classe, niveau = lire_fiche(form, s.regles)
        await s.depot.creer_grimpeur(v.discord_id, v.session.nom_discord, pseudo, classe, niveau, s.horloge(),
                                     liste_obligatoire=s.regles.liste_officielle_obligatoire)
    except ValueError as e:
        return await rendre(request, "inscription.html", {"hors_liste": False, "classes": CLASSES,
                                                          "valeurs": valeurs, "erreur": MESSAGES_FICHE[e.args[0]]}, 422)
    except PseudoDejaPris:
        return await rendre(request, "inscription.html", {"hors_liste": False, "classes": CLASSES,
                                                          "valeurs": valeurs, "erreur": MESSAGES_FICHE["pris"]}, 409)
    except PasSurLaListe:
        return await rendre(request, "inscription.html", {"hors_liste": True}, 403)
    except (DejaInscrit, Introuvable):
        pass
    return RedirectResponse("/", status_code=303)
