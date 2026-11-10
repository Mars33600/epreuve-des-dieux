"""Les pages des grimpeurs (SPEC §4.2 à §4.6, ARCHITECTURE §9).

    GET  /etages/{n}                 l'onglet d'un étage : ma progression, la jauge, les donjons, les blocs du guide
    GET  /etages/{n}/quetes/{id}     la fiche de quête (plus liée depuis le site v5 : le guide, c'est Duffus)
    GET  /histoire                   l'histoire de Shadoaze ; POST /histoire/vu retient le prologue passé
    GET  /grimpeurs                  toutes les fiches + « qui a fait, qui n'a pas fait… ? » par étage
                                     (?etage=N&quoi=… ; morceaux de page avec Accept: text/html-fragment)
    POST /grimpeurs/moi              modifier son pseudo, sa classe, son niveau (le formulaire est sur le
                                     tableau de bord ; GET /grimpeurs/{id} est dans `tableau.py`)
    GET/POST /inscription            créer sa fiche (du 11/11 17 h à l'ouverture, page seule derrière le teaser)

Brouillard de guerre : un étage scellé répond 404 comme un étage inexistant (sauf admin), et les
prérequis d'un étage scellé sont masqués par `masquer_prerequis_scelles` sur tous les chemins.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from epreuve.db.depot import DejaInscrit, Introuvable, PasSurLaListe, PseudoDejaPris
from epreuve.domaine.bareme import palier
from epreuve.domaine.classes import CLASSES, repartition_classes
from epreuve.domaine.fiche import FicheQuete, masquer_prerequis_scelles
from epreuve.domaine.mode_site import fiches_ouvertes
from epreuve.domaine.modeles import CATEGORIES, NOM_CATEGORIE, ElementRef, Etage, Grimpeur
from epreuve.domaine.progression import qui, qui_categorie
from epreuve.domaine.textes import valider_pseudo
from epreuve.domaine.visibilite import etage_cochable, etages_visibles
from epreuve.encyclopedie.liens import noms_de_fiche
from epreuve.web.auth import Refus, Visiteur, exiger_connecte, exiger_grimpeur, mode, verifier_ecriture
from epreuve.web.histoire import paragraphes
from epreuve.web.liens import liens_pour
from epreuve.web.rendu import rendre
from epreuve.web.vues import (
    VueEtage,
    charger_vue_etage,
    encoches,
    formule_palier,
    separer_courant,
    texte_jauge,
    tri_grimpeurs,
    verdicts,
)

routeur = APIRouter()
IMAGES_ETAGES = Path(__file__).resolve().parents[3] / "donnees" / "images" / "etages"
INTROUVABLE = "Introuvable."
MESSAGES_FICHE = {"pseudo": "Le pseudo doit faire entre 2 et 30 caractères.",
                  "pris": "Ce pseudo est déjà pris (sans tenir compte des majuscules).",
                  "classe": "Classe inconnue.", "niveau": "Le niveau va de 1 à 200.",
                  "dispo": "Dis-nous si tu es là vendredi entre 16 h et 17 h pour rejoindre la guilde.",
                  "quand": "Dis-nous à partir de quand tu seras là pour être invité (100 caractères au plus)."}
DISPO_OUI = "oui"  # dispo vendredi 13/11 entre 16 h et 17 h ; sinon, le texte libre « à partir de quand »


def lire_dispo(form, obligatoire: bool) -> str | None:
    """La question de Shadoaze (10/11) : « dispo vendredi 16 h-17 h pour la guilde ? Sinon, à partir de quand ? »

    Renvoie « oui », le texte libre (1 à 100 caractères) ou None si la question est facultative et sans réponse.
    """
    reponse = str(form.get("dispo", "")).strip()
    if reponse == DISPO_OUI:
        return DISPO_OUI
    if reponse == "non":
        quand = " ".join(str(form.get("dispo_quand", "")).split())
        if not 1 <= len(quand) <= 100:
            raise ValueError("quand")
        return quand
    if obligatoire:
        raise ValueError("dispo")
    return None


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
    actifs_points = vue.grimpeurs_par_statut("actif")
    pauses_points = vue.grimpeurs_par_statut("pause")
    return {"vue": vue, "jauge": vue.jauge, "encoches": encoches(vue.jauge),
            "formule": formule_palier(vue.jauge, s.regles), "texte_jauge": texte_jauge(vue.jauge),
            "verdict_plein": plein, "verdict_pas_plein": pas_plein,
            "actifs_points": actifs_points, "pauses_points": pauses_points,
            "actifs_liste": [g for g, _ in actifs_points], "pauses_liste": [g for g, _ in pauses_points]}


async def tour(request: Request, v: Visiteur):
    """L'accueil connecté : la tour, la jauge de l'étage ouvert, la répartition des classes."""
    s = _s(request)
    if v.grimpeur is not None and not v.grimpeur.prologue_vu:
        return await rendre(request, "prologue.html", {"histoire": paragraphes()})
    etages = etages_visibles(await s.depot.etages(), est_admin=False)  # la tour ne montre jamais un scellé
    ouvert = next((e for e in etages if e.statut == "ouvert"), None)
    grimpeurs = await s.depot.grimpeurs()
    ctx: dict = {"etages": etages, "ouvert": ouvert, "vue": None,
                "ambiance": ouvert.ambiance_url if ouvert else None}
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


@routeur.get("/ambiance")
async def ambiance_ouverte(request: Request):
    """L'image de l'étage ouvert, pour le décor des modules (CSS seul, sans script) : jamais un étage scellé."""
    await exiger_grimpeur(request)
    ouvert = next((e for e in await _s(request).depot.etages() if e.statut == "ouvert"), None)
    fichier = IMAGES_ETAGES / f"etage-{ouvert.numero}.webp" if ouvert else None
    if fichier is None or not fichier.is_file():
        raise Refus(404, "Image introuvable.")
    return FileResponse(fichier, media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"})


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
    if not s.regles.monde_des_douze:  # SPEC-V5 §2 : la fiche de quête relève de duffus.fr
        raise Refus(404, INTROUVABLE)
    etage = await etage_visible(request, numero, v)
    vue = await charger_vue_etage(s.depot, etage, s.regles)
    quete = next((q for q in vue.contenu.quetes if q.id == quete_id), None)
    if quete is None:
        raise Refus(404, INTROUVABLE)
    fiche, carte = await fiche_pour(request, v, etage, quete_id)
    ref = ElementRef("quete", quete.id)
    cochable = peut_cocher_soi(v, etage, s.regles)
    # Le suivi des étapes est personnel : seulement pour le grimpeur connecté sur sa propre fiche.
    suivies = await s.depot.etapes_suivies(v.grimpeur.id, quete_id) if cochable and v.grimpeur else None
    liens = await liens_pour(request, noms_de_fiche(fiche), v.est_admin) if fiche else None
    ctx = {"etage": etage, "quete": quete, "fiche": fiche, "carte": carte, "vue": vue, "liens": liens,
           "cible": v.grimpeur, "cochable": False,  # la quête ne se coche plus : on coche le bloc (SPEC v5)
           "etapes_suivies": suivies,
           "pas_fait": qui(ref, vue.grimpeurs, vue.coches, fait=False),
           "fait": qui(ref, vue.grimpeurs, vue.coches, fait=True)}
    if "text/html-fragment" in request.headers.get("accept", ""):
        return await rendre(request, "_quete.html", ctx)
    return await rendre(request, "quete.html", ctx)


@routeur.get("/histoire")
async def page_histoire(request: Request):
    """L'histoire de Shadoaze (DECISIONS-V4 §13), relisible à tout moment depuis le menu."""
    await exiger_grimpeur(request)
    return await rendre(request, "histoire.html", {"histoire": paragraphes()})


@routeur.post("/histoire/vu")
async def prologue_vu(request: Request):
    """« Entrer dans la tour » : retient en base que le prologue a été passé, puis retour à l'accueil."""
    v = await verifier_ecriture(request)
    if v.grimpeur is not None:
        await _s(request).depot.marquer_prologue_vu(v.grimpeur.id, _s(request).horloge())
    return RedirectResponse("/", status_code=303)


@routeur.get("/regles")
async def page_regles(request: Request):
    """Les règles en clair (DECISIONS-V4 §12). Les valeurs viennent de la configuration, jamais écrites en dur."""
    await exiger_grimpeur(request)
    s = _s(request)
    m = s.regles.points_par_joueur
    ouvert = next((e for e in await s.depot.etages() if e.statut == "ouvert"), None)
    return await rendre(request, "regles.html", {
        "m": str(m.numerator) if m.denominator == 1 else f"{m.numerator}/{m.denominator}",
        # Les exemples chiffrés viennent de la même fonction que la vraie jauge : jamais de nombre écrit en dur.
        "palier_12": palier(12, 4, s.regles), "palier_12_trois": palier(12, 3, s.regles),
        "ouvert": ouvert, "plancher": ouvert.date_plancher_suivant if ouvert else None,
        "annonce_discord": s.config.discord_webhook_annonces is not None})


# ---------------------------------------------------------------- « qui n'a pas fait… ? »

def resoudre_quoi(vue: VueEtage, type_: str, ident: str) -> tuple[str, list[Grimpeur], list[Grimpeur]] | None:
    """(libellé, pas fait, fait) pour une case, un bloc, un donjon (sa case classique) ou une catégorie."""
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
    elif type_ == "bloc":
        b = next((x for x in c.blocs if x.id == n), None)
        if b is None:
            return None
        libelle = (f"la partie {b.nature} du bloc « {b.titre_complet} »" if b.moitie
                   else f"le bloc « {b.titre_complet} »")
    else:
        return None
    ref = ElementRef(type_, n)  # type: ignore[arg-type]
    return libelle, qui(ref, vue.grimpeurs, vue.coches, False), qui(ref, vue.grimpeurs, vue.coches, True)


def _fragment(request: Request) -> bool:
    """Le script demande un morceau de page (`Accept: text/html-fragment`), comme pour la fiche de quête."""
    return "text/html-fragment" in request.headers.get("accept", "")


async def etage_qui(request: Request, v: Visiteur, numero: int) -> Etage:
    """L'étage d'un « qui a fait… ? » : visible pour ce visiteur et ouvert ou terminé, sinon 404 (un étage scellé
    n'a rien à montrer, même à un admin : la page ne le liste pas)."""
    etage = await etage_visible(request, numero, v)
    if not etage_cochable(etage):
        raise Refus(404, INTROUVABLE)
    return etage


@routeur.get("/grimpeurs")
async def page_grimpeurs(request: Request, quoi: str = "", etage: int | None = None):
    """Les fiches et « qui a fait, qui n'a pas fait… ? », rangé par étage (retour de recette v4).

    La page ne déroule que l'étage en cours (rubriques et objectifs pliés) et l'étage demandé par `?etage=` ;
    les autres étages et chaque réponse arrivent à l'ouverture de leur dépliant : `app.js` redemande cette
    même adresse avec `Accept: text/html-fragment` et n'en reçoit que le morceau (`_qui_etage.html` sans
    `quoi`, `_qui_reponse.html` avec). Sans script, chaque dépliant porte un lien `?etage=N&quoi=…` qui rend
    la page entière avec la réponse en place et ses dépliants ouverts. Même contrôle d'accès partout :
    grimpeur connecté (ou admin), site ouvert (le teaser est filtré avant, par `securite.FiltreMode`).
    """
    v = await exiger_grimpeur(request)
    s = _s(request)
    if _fragment(request):
        if etage is None:
            raise Refus(422, "Requête invalide.")
        vue = await charger_vue_etage(s.depot, await etage_qui(request, v, etage), s.regles)
        if not quoi:
            return await rendre(request, "_qui_etage.html", {"vue": vue, "sel": None, "courant": False})
        reponse = resoudre_quoi(vue, *quoi.split(":", 1)) if ":" in quoi else None
        if reponse is None:
            raise Refus(404, INTROUVABLE)
        return await rendre(request, "_qui_reponse.html", {"vue": vue, "reponse": reponse})
    grimpeurs = await s.depot.grimpeurs()
    tous = await s.depot.etages()
    ouvert = next((e for e in tous if e.statut == "ouvert"), None)
    listes = sorted((e for e in tous if etage_cochable(e)), key=lambda e: -e.numero)
    courant, _ = separer_courant(listes, lambda e: e)
    # Sans `etage`, un ancien lien `?quoi=` (tuiles de la page d'étage) vise l'étage ouvert, comme avant.
    choisi = next((e for e in listes if e.numero == etage), None) if etage is not None else ouvert
    vues = {}  # numéro → vue, chargée une seule fois : l'étage en cours, l'étage demandé, l'étage ouvert (fiches)
    for e in (courant, choisi, ouvert):
        if e is not None and e.numero not in vues:
            vues[e.numero] = await charger_vue_etage(s.depot, e, s.regles, grimpeurs)
    vue_ouvert = vues[ouvert.numero] if ouvert else None
    reponse = sel = None
    if choisi is not None and ":" in quoi:
        reponse = resoudre_quoi(vues[choisi.numero], *quoi.split(":", 1))
    if reponse is not None or (choisi is not None and etage is not None):
        sel = {"etage": choisi.numero, "quoi": quoi if reponse else "", "reponse": reponse}
    cibles = {g.id for g in reponse[1]} if reponse else set()
    liste = tri_grimpeurs(grimpeurs, v.est_admin)
    return await rendre(request, "grimpeurs.html", {
        "grimpeurs": liste, "vue": vue_ouvert, "ouvert": ouvert, "etages_qui": listes, "vues_qui": vues,
        "courant": courant, "sel": sel, "reponse": reponse, "cibles": cibles,
        "actifs": sum(g.statut == "actif" for g in liste), "en_pause": sum(g.statut == "pause" for g in liste)})


@routeur.post("/grimpeurs/moi")
async def modifier_moi(request: Request):
    v = await verifier_ecriture(request)
    if v.grimpeur is None or v.grimpeur.statut == "exclu":
        raise Refus(403, "Tu n'as pas de fiche à modifier.")
    s = _s(request)
    form = await request.form()
    gid = v.grimpeur.id
    # Retour sur le tableau de bord, qui porte le formulaire depuis que « Ma fiche » n'existe plus.
    try:
        pseudo, classe, niveau = lire_fiche(form, s.regles)
    except ValueError as e:
        return RedirectResponse(f"/tableau-de-bord?erreur={e.args[0]}", status_code=303)
    try:
        await s.depot.modifier_grimpeur(gid, v.discord_id, s.horloge(), pseudo=pseudo, classe=classe,
                                        niveau_declare=niveau)
    except PseudoDejaPris:
        return RedirectResponse("/tableau-de-bord?erreur=pris", status_code=303)
    return RedirectResponse("/tableau-de-bord?fait=1", status_code=303)


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

MESSAGE_FICHES_CLOSES = ("Les inscriptions sont closes depuis l'ouverture de la tour. "
                         "Si tu devais en être, écris à Shadoaze ou à Mars sur le Discord.")


async def _inscription_permise(request: Request) -> Visiteur:
    """Pré-inscription (décision du 07/11) : un joueur crée sa fiche de FICHES_OUVERTES_LE à la fin des fiches
    (l'ouverture du site), sur une page seule derrière le compte à rebours. Un admin le peut toujours."""
    v = await exiger_connecte(request)
    if v.grimpeur is not None:
        raise Refus(303, "", vers="/")
    if not v.est_admin:
        config, maintenant = _s(request).config, _s(request).horloge()
        if maintenant >= config.fin_des_fiches:
            raise Refus(403, MESSAGE_FICHES_CLOSES)
        if mode(request) == "teaser" and not fiches_ouvertes(config.fiches_ouvertes_le, config.fin_des_fiches,
                                                             maintenant):
            raise Refus(303, "", vers="/")  # trop tôt : le compte à rebours
    return v


def _cadre_fiche(request: Request, v: Visiteur) -> dict:
    """Pendant le teaser, un joueur voit la fiche seule (`fiche_seule.html`), sans la navigation du site."""
    seule = mode(request) == "teaser" and not v.est_admin
    return {"cadre": "fiche_seule.html" if seule else "site.html", "seule": seule}


@routeur.get("/inscription")
async def inscription(request: Request):
    v = await _inscription_permise(request)
    s = _s(request)
    cadre = _cadre_fiche(request, v)
    if s.regles.liste_officielle_obligatoire and v.discord_id not in await s.depot.liste_officielle():
        return await rendre(request, "inscription.html", {"hors_liste": True, **cadre})
    return await rendre(request, "inscription.html", {"hors_liste": False, "classes": CLASSES, "valeurs": {}, **cadre})


@routeur.post("/inscription")
async def inscrire(request: Request):
    await verifier_ecriture(request)
    v = await _inscription_permise(request)
    s = _s(request)
    cadre = _cadre_fiche(request, v)
    form = await request.form()
    valeurs = {k: str(form.get(k, "")) for k in ("pseudo", "classe", "niveau", "dispo", "dispo_quand")}
    try:
        pseudo, classe, niveau = lire_fiche(form, s.regles)
        niveau = niveau or 1  # le formulaire ne demande plus le niveau : tout le monde part du niveau 1
        dispo = lire_dispo(form, obligatoire=cadre["seule"])  # obligatoire pour la pré-inscription des joueurs
        await s.depot.creer_grimpeur(v.discord_id, v.session.nom_discord, pseudo, classe, niveau, s.horloge(),
                                     liste_obligatoire=s.regles.liste_officielle_obligatoire, dispo_guilde=dispo)
    except ValueError as e:
        return await rendre(request, "inscription.html", {"hors_liste": False, "classes": CLASSES, **cadre,
                                                          "valeurs": valeurs, "erreur": MESSAGES_FICHE[e.args[0]]}, 422)
    except PseudoDejaPris:
        return await rendre(request, "inscription.html", {"hors_liste": False, "classes": CLASSES, **cadre,
                                                          "valeurs": valeurs, "erreur": MESSAGES_FICHE["pris"]}, 409)
    except PasSurLaListe:
        return await rendre(request, "inscription.html", {"hors_liste": True, **cadre}, 403)
    except (DejaInscrit, Introuvable):
        pass
    return RedirectResponse("/", status_code=303)
