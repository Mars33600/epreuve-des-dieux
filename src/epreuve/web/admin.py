"""L'admin (SPEC §4.7 à §4.9, ARCHITECTURE §9) : toutes les routes exigent un admin revérifié.

    GET  /admin, /admin/grimpeurs, /admin/etages, /admin/etages/{n}, /admin/journal
    POST /admin/liste                          ajouter des identifiants ou des mentions <@…> à la liste officielle
    POST /admin/grimpeurs/{id}/statut          geler, réintégrer, exclure (motif + confirmation)
    POST /admin/grimpeurs/{id}                 corriger le pseudo ou la classe
    POST /admin/etages/{n}/palier              palier manuel (≥ 1, motif) ou vide = la formule
    POST /admin/etages/{n}/date-plancher       date plancher de l'étage suivant (heure de Paris)
    POST /admin/etages/{n}/ouvrir              ouvrir l'étage n (forçable avec un motif)
    POST /admin/etages/{n}/reglages            nom, image d'ambiance, level cap
    POST /admin/etages/{n}/donjons             ajouter un donjon aspiré (T-03)
    POST /admin/quetes/{id}, /admin/donjons/{id}, /admin/cases/{id}   revue du contenu

Chaque écriture passe par le dépôt, qui l'inscrit au journal. Après un POST, on revient sur la page avec
un code (`?fait=palier`) traduit en message fixe : aucun texte de l'utilisateur n'est renvoyé tel quel.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from epreuve.db.depot import EtatInvalide, Introuvable, PseudoDejaPris
from epreuve.domaine.bareme import detail_par_grimpeur, palier
from epreuve.domaine.classes import CLASSES
from epreuve.domaine.fiche import extraire_ids_discord
from epreuve.domaine.modeles import Etage
from epreuve.domaine.ouverture import bilan_etage, peut_ouvrir
from epreuve.domaine.progression import moins_avance
from epreuve.web.auth import Refus, Visiteur, exiger_admin, verifier_ecriture
from epreuve.web.pages import lire_fiche
from epreuve.web.rendu import rendre
from epreuve.web.vues import charger_vue_etage

routeur = APIRouter(prefix="/admin", dependencies=[Depends(exiger_admin)])
PARIS = ZoneInfo("Europe/Paris")

MESSAGES = {
    "liste": "Liste officielle mise à jour.", "statut": "Statut changé.", "fiche": "Fiche corrigée.",
    "palier": "Palier enregistré.", "plancher": "Date plancher enregistrée.", "ouvert": "Étage ouvert.",
    "reglages": "Réglages de l'étage enregistrés.", "donjon": "Donjon ajouté.", "contenu": "Contenu modifié.",
}
ERREURS = {
    "motif": "Un motif est obligatoire.", "confirmer": "Coche « Je confirme » pour exclure.",
    "palier": "Le palier manuel est un entier supérieur ou égal à 1.", "date": "Date illisible.",
    "cap": "Le level cap est un entier de 1 à 200.", "pseudo": "Le pseudo doit faire entre 2 et 30 caractères.",
    "pris": "Ce pseudo est déjà pris.", "classe": "Classe inconnue.", "niveau": "Le niveau va de 1 à 200.",
    "ouverture": "Ouverture refusée : voir les raisons ci-dessous.", "concurrence":
        "Un autre admin vient d'ouvrir cet étage : rien n'a été fait en double.",
    "introuvable": "Élément introuvable.", "statut": "Statut inconnu.", "ids": "Aucun identifiant Discord reconnu.",
    "nature": "Nature inconnue.", "url": "L'adresse de l'image doit commencer par https://.",
}


def _s(request: Request):
    return request.app.state


def retour(chemin: str, *, fait: str = "", erreur: str = "", extra: str = "") -> RedirectResponse:
    q = f"fait={fait}" if fait else f"erreur={erreur}"
    return RedirectResponse(f"{chemin}?{q}{extra}", status_code=303)


def messages(fait: str, erreur: str) -> dict:
    return {"message": MESSAGES.get(fait, ""), "erreur": ERREURS.get(erreur, "")}


async def _etage(request: Request, numero: int) -> Etage:
    e = await _s(request).depot.etage_par_numero(numero)
    if e is None:
        raise Refus(404, "Étage introuvable.")
    return e


async def _ecrire(request: Request) -> tuple[Visiteur, dict]:
    v = await verifier_ecriture(request)
    return v, dict(await request.form())


@routeur.get("")
async def accueil_admin(request: Request):
    s = _s(request)
    etages = await s.depot.etages()
    return await rendre(request, "admin/index.html", {
        "etages": etages, "ouvert": next((e for e in etages if e.statut == "ouvert"), None),
        "nb_grimpeurs": len(await s.depot.grimpeurs()), "nb_liste": len(await s.depot.liste_officielle())})


# ---------------------------------------------------------------- grimpeurs

@routeur.get("/grimpeurs")
async def admin_grimpeurs(request: Request, fait: str = "", erreur: str = "", n: int = 0):
    s = _s(request)
    grimpeurs = await s.depot.grimpeurs()
    liste = await s.depot.liste_officielle()
    activites = await s.depot.dernieres_activites()
    ouvert = next((e for e in await s.depot.etages() if e.statut == "ouvert"), None)
    vue = await charger_vue_etage(s.depot, ouvert, s.regles, grimpeurs) if ouvert else None
    effets: dict[str, str] = {}
    moins = None
    if vue is not None:
        j, k, manuel = vue.jauge, vue.jauge.nb_categories, vue.etage.palier_manuel
        avec = palier(j.actifs + 1, k, s.regles, manuel)
        sans = palier(max(0, j.actifs - 1), k, s.regles, manuel)
        effets = {"geler": f"Palier {j.palier} → {sans}", "reintegrer": f"Palier {j.palier} → {avec}"}
        moins = moins_avance(vue.contenu, grimpeurs, vue.coches, s.regles)
    par_discord = {g.discord_user_id: g for g in grimpeurs}
    a_creer = [(did, st) for did, st in liste.items() if did not in par_discord]
    rang = {"actif": 0, "pause": 1, "exclu": 2}
    return await rendre(request, "admin/grimpeurs.html", {
        "grimpeurs": sorted(grimpeurs, key=lambda g: (rang[g.statut], g.pseudo.casefold())), "a_creer": a_creer,
        "activites": activites, "vue": vue, "effets": effets, "moins": moins, "classes": CLASSES,
        "ajoutes": n, **messages(fait, erreur)})


@routeur.post("/liste")
async def admin_liste(request: Request):
    v, form = await _ecrire(request)
    ids = extraire_ids_discord(str(form.get("mentions", "")))
    statut = form.get("statut_initial", "actif")
    if statut not in ("actif", "pause"):
        return retour("/admin/grimpeurs", erreur="statut")
    if not ids:
        return retour("/admin/grimpeurs", erreur="ids")
    s = _s(request)
    ajoutes = await s.depot.ajouter_liste(ids, statut, v.discord_id, s.horloge())
    return retour("/admin/grimpeurs", fait="liste", extra=f"&n={len(ajoutes)}")


@routeur.post("/grimpeurs/{grimpeur_id}/statut")
async def admin_statut(request: Request, grimpeur_id: int):
    v, form = await _ecrire(request)
    statut = form.get("statut")
    motif = str(form.get("motif", "")).strip() or None
    if statut not in ("actif", "pause", "exclu"):
        return retour("/admin/grimpeurs", erreur="statut")
    if statut == "exclu" and motif is None:
        return retour("/admin/grimpeurs", erreur="motif")
    if statut == "exclu" and form.get("confirmer") != "oui":
        return retour("/admin/grimpeurs", erreur="confirmer")
    s = _s(request)
    try:
        await s.depot.changer_statut(grimpeur_id, statut, motif, v.discord_id, s.horloge())
    except Introuvable:
        return retour("/admin/grimpeurs", erreur="introuvable")
    return retour("/admin/grimpeurs", fait="statut")


@routeur.post("/grimpeurs/{grimpeur_id}")
async def admin_corriger(request: Request, grimpeur_id: int):
    v, form = await _ecrire(request)
    s = _s(request)
    g = await s.depot.grimpeur(grimpeur_id)
    if g is None:
        return retour("/admin/grimpeurs", erreur="introuvable")
    try:
        pseudo, classe, niveau = lire_fiche({"pseudo": form.get("pseudo", g.pseudo), "classe": form.get("classe", ""),
                                             "niveau": form.get("niveau", "")}, s.regles)
        await s.depot.modifier_grimpeur(grimpeur_id, v.discord_id, s.horloge(), pseudo=pseudo, classe=classe,
                                        niveau_declare=niveau)
    except ValueError as e:
        return retour("/admin/grimpeurs", erreur=e.args[0])
    except PseudoDejaPris:
        return retour("/admin/grimpeurs", erreur="pris")
    return retour("/admin/grimpeurs", fait="fiche")


# ---------------------------------------------------------------- étages

@routeur.get("/etages")
async def admin_etages(request: Request):
    return await rendre(request, "admin/etages.html", {"etages": await _s(request).depot.etages()})


@routeur.get("/etages/{numero}")
async def admin_etage(request: Request, numero: int, fait: str = "", erreur: str = ""):
    s = _s(request)
    etage = await _etage(request, numero)
    _, donjons, cases, quetes = await s.depot.contenu_brut(etage.id)
    grimpeurs = await s.depot.grimpeurs()
    vue = await charger_vue_etage(s.depot, etage, s.regles, grimpeurs)
    ctx = {"etage": etage, "donjons": donjons, "quetes": quetes, "vue": vue,
           "cases": {d.id: [c for c in cases if c.donjon_id == d.id] for d in donjons},
           "alertes": await s.depot.alertes_etage(etage.id), "sans_fiche": await s.depot.quetes_sans_fiche(etage.id),
           "disponibles": await s.depot.donjons_disponibles(), "bilan": await s.depot.bilan(etage.id),
           "plancher_local": etage.date_plancher_suivant.astimezone(PARIS).strftime("%Y-%m-%dT%H:%M")
           if etage.date_plancher_suivant else "", **messages(fait, erreur)}
    if etage.statut == "ouvert":
        prochain = await s.depot.etage_par_numero(numero + 1)
        ctx["decision"] = peut_ouvrir(vue.jauge, etage, prochain, s.horloge())
        ctx["prochain"] = prochain
        ctx["detail"] = detail_par_grimpeur(vue.contenu, [g for g in grimpeurs if g.statut != "exclu"],
                                            vue.coches, s.regles)
        ctx["activites"] = await s.depot.dernieres_activites()
    return await rendre(request, "admin/etage.html", ctx)


@routeur.post("/etages/{numero}/palier")
async def admin_palier(request: Request, numero: int):
    v, form = await _ecrire(request)
    s = _s(request)
    etage = await _etage(request, numero)
    brut, motif = str(form.get("palier", "")).strip(), str(form.get("motif", "")).strip()
    chemin = f"/admin/etages/{numero}"
    if brut and (not brut.isdigit() or int(brut) < 1):
        return retour(chemin, erreur="palier")
    if not motif:
        return retour(chemin, erreur="motif")
    await s.depot.regler_palier(etage.id, int(brut) if brut else None, motif, v.discord_id, s.horloge())
    return retour(chemin, fait="palier")


@routeur.post("/etages/{numero}/date-plancher")
async def admin_plancher(request: Request, numero: int):
    v, form = await _ecrire(request)
    s = _s(request)
    etage = await _etage(request, numero)
    brut = str(form.get("date", "")).strip()
    try:
        date = datetime.fromisoformat(brut).replace(tzinfo=PARIS) if brut else None
    except ValueError:
        return retour(f"/admin/etages/{numero}", erreur="date")
    await s.depot.regler_date_plancher(etage.id, date, v.discord_id, s.horloge())
    return retour(f"/admin/etages/{numero}", fait="plancher")


@routeur.post("/etages/{numero}/ouvrir")
async def admin_ouvrir(request: Request, numero: int):
    """Ouvrir l'étage `numero` : l'étage en cours doit être `numero - 1`, et `peut_ouvrir` vrai, sauf force."""
    v, form = await _ecrire(request)
    s = _s(request)
    prochain = await _etage(request, numero)
    en_cours = await s.depot.etage_par_numero(numero - 1)
    if en_cours is None or en_cours.statut != "ouvert":
        return retour(f"/admin/etages/{numero}", erreur="ouverture")
    chemin = f"/admin/etages/{en_cours.numero}"
    force = form.get("forcer") == "oui"
    motif = str(form.get("motif", "")).strip() or None
    vue = await charger_vue_etage(s.depot, en_cours, s.regles)
    maintenant = s.horloge()
    decision = peut_ouvrir(vue.jauge, en_cours, prochain, maintenant)
    if not decision.ok and not force:
        return retour(chemin, erreur="ouverture")
    if force and motif is None:
        return retour(chemin, erreur="motif")
    try:
        await s.depot.ouvrir_etage(numero, bilan_etage(vue.jauge, maintenant, force, motif), v.discord_id,
                                   maintenant)
    except EtatInvalide:
        return retour(chemin, erreur="concurrence")
    return retour(f"/admin/etages/{numero}", fait="ouvert")


@routeur.post("/etages/{numero}/reglages")
async def admin_reglages(request: Request, numero: int):
    v, form = await _ecrire(request)
    s = _s(request)
    etage = await _etage(request, numero)
    chemin = f"/admin/etages/{numero}"
    nom = str(form.get("nom", "")).strip() or None
    url = str(form.get("ambiance_url", "")).strip() or None
    cap = str(form.get("level_cap", "")).strip()
    if url is not None and not url.startswith("https://"):
        return retour(chemin, erreur="url")
    if cap and (not cap.isdigit() or not 1 <= int(cap) <= 200):
        return retour(chemin, erreur="cap")
    await s.depot.regler_etage(etage.id, v.discord_id, s.horloge(), nom=nom, ambiance_url=url,
                               level_cap=int(cap) if cap else None)
    return retour(chemin, fait="reglages")


@routeur.post("/etages/{numero}/donjons")
async def admin_ajouter_donjon(request: Request, numero: int):
    v, form = await _ecrire(request)
    s = _s(request)
    etage = await _etage(request, numero)
    try:
        await s.depot.ajouter_donjon(etage.id, str(form.get("duffus_id", "")), v.discord_id, s.horloge())
    except Introuvable:
        return retour(f"/admin/etages/{numero}", erreur="introuvable")
    return retour(f"/admin/etages/{numero}", fait="donjon")


def _retour_etage(form) -> str:
    n = str(form.get("etage", ""))
    return f"/admin/etages/{n}" if n.isdigit() else "/admin/etages"


def _bool(form, nom: str) -> bool | None:
    val = form.get(nom)
    return None if val is None else val == "oui"


@routeur.post("/quetes/{quete_id}")
async def admin_quete(request: Request, quete_id: int):
    v, form = await _ecrire(request)
    s = _s(request)
    chemin = _retour_etage(form)
    nature = form.get("nature") or None
    motif = str(form.get("motif", "")).strip() or None
    if nature is not None and nature not in ("principale", "secondaire"):
        return retour(chemin, erreur="nature")
    if nature is not None and motif is None:
        return retour(chemin, erreur="motif")
    try:
        await s.depot.modifier_quete(quete_id, v.discord_id, s.horloge(), nature=nature, motif=motif,
                                     masquee=_bool(form, "masquee"), nom=str(form.get("nom", "")).strip() or None)
    except Introuvable:
        return retour(chemin, erreur="introuvable")
    return retour(chemin, fait="contenu")


@routeur.post("/donjons/{donjon_id}")
async def admin_donjon(request: Request, donjon_id: int):
    v, form = await _ecrire(request)
    s = _s(request)
    chemin = _retour_etage(form)
    try:
        await s.depot.modifier_donjon(donjon_id, v.discord_id, s.horloge(), masque=_bool(form, "masque"),
                                      nom=str(form.get("nom", "")).strip() or None)
    except Introuvable:
        return retour(chemin, erreur="introuvable")
    return retour(chemin, fait="contenu")


@routeur.post("/cases/{case_id}")
async def admin_case(request: Request, case_id: int):
    v, form = await _ecrire(request)
    s = _s(request)
    chemin = _retour_etage(form)
    try:
        await s.depot.modifier_case(case_id, v.discord_id, s.horloge(), masquee=_bool(form, "masquee"),
                                    nom=str(form.get("nom", "")).strip() or None,
                                    condition=str(form.get("condition", "")).strip() or None)
    except Introuvable:
        return retour(chemin, erreur="introuvable")
    return retour(chemin, fait="contenu")


# ---------------------------------------------------------------- journal

@routeur.get("/journal")
async def admin_journal(request: Request, grimpeur: str = "", type: str = "", etage: str = ""):  # noqa: A002
    s = _s(request)
    etages = await s.depot.etages()
    etage_id = next((e.id for e in etages if str(e.numero) == etage), None)
    lignes = await s.depot.journal(200, grimpeur_id=int(grimpeur) if grimpeur.isdigit() else None,
                                   etage_id=etage_id, type_=type or None)
    grimpeurs = {g.id: g for g in await s.depot.grimpeurs()}
    return await rendre(request, "admin/journal.html", {
        "lignes": lignes, "grimpeurs": grimpeurs, "etages": etages, "etages_par_id": {e.id: e for e in etages},
        "filtre": {"grimpeur": grimpeur, "type": type, "etage": etage}})
