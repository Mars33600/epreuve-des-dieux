"""Écrire un `EtagePrepare` en base, dans UNE transaction (ARCHITECTURE §6.5, étape 6).

- un étage nouveau est créé `scelle`, sauf l'étage 0, créé `ouvert` ;
- un étage existant est mis à jour **par identifiant Duffus** : on ajoute le nouveau, on met à jour les
  libellés de la source, et on **masque** ce qui a disparu au lieu de le supprimer (nos coches pointent vers
  nos identifiants, jamais vers ceux de Duffus) ;
- les blocs du guide (SPEC v5) sont rapprochés par (titre, partie), puis par titre seul (un bloc entier qui change de
  nature), puis par position si Duffus a retitré un bloc ; un bloc hybride a deux lignes, une par partie ; leur
  nature calculée est recalculée, sauf correction d'un admin sur un bloc entier (`nature_origine = 'admin'`) ;
- les choix d'un admin survivent : nature forcée (d'une quête ou d'un bloc), masquage (`masque_par = 'admin'`),
  libellés corrigés (`corrections`), donjon ajouté (`origine = 'admin'`), nom, cap et image d'étage réglés ;
- garde-fou : sur un étage ouvert, si plus de 10 % des éléments disparaîtraient ou changeraient de nature,
  l'écriture est refusée sans `forcer` ;
- chaque reconstruction d'un étage existant passe au journal (`contenu_maj`), avec le détail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as insert_pg
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from epreuve.contenu.construire import BlocPrepare, DonjonPrepare, EtagePrepare
from epreuve.db import tables as t
from epreuve.db.depot import contenu_fiche_json

GARDE_FOU = 0.10


class EcritureRefusee(RuntimeError):
    pass


@dataclass
class Resultat:
    etage_id: int
    cree: bool
    ajoutes: int = 0
    masques: int = 0
    demasques: int = 0
    changements: list[str] = field(default_factory=list)  # lisibles, pour le rapport et le journal

    def texte(self) -> str:
        quoi = "créé" if self.cree else "mis à jour"
        lignes = [f"Étage {quoi} (id {self.etage_id}) : {self.ajoutes} ajouts, {self.masques} masqués, "
                  f"{self.demasques} démasqués, {len(self.changements)} changements"]
        lignes += [f"  {c}" for c in self.changements[:50]]
        return "\n".join(lignes)


def _visible(r, champ: str) -> bool:
    return not getattr(r, champ)


def _lisible(quoi: str, nom: str, avant: dict, apres: dict) -> str | None:
    """« quête « X » : nom « A » → « B » », ou None si rien n'a changé."""
    ecarts = [f"{k} « {avant[k]} » → « {apres[k]} »" for k in apres if avant.get(k) != apres[k]]
    return f"{quoi} « {nom} » : " + ", ".join(ecarts) if ecarts else None


async def _synchroniser(c: AsyncConnection, table, existants: dict, voulus: dict[str, dict], champ_masque: str,
                        quoi: str, res: Resultat, fixes: dict, garder=lambda r: False) -> dict[str, int]:
    """Ajoute, met à jour et masque les lignes d'une table de contenu ; renvoie duffus_id → id."""
    ids: dict[str, int] = {}
    for cle, valeurs in voulus.items():
        r = existants.get(cle)
        if r is None:
            ids[cle] = (await c.execute(insert(table).values(**fixes, **valeurs, duffus_id=cle, **{champ_masque: False})
                                        .returning(table.c.id))).scalar_one()
            res.ajoutes += 1
            res.changements.append(f"{quoi} ajouté(e) : « {valeurs['nom']} »")
            continue
        ids[cle] = r.id
        maj = dict(valeurs)
        if getattr(r, champ_masque) and r.masque_par == "construction":
            maj |= {champ_masque: False, "masque_par": None}
            res.demasques += 1
        ligne = _lisible(quoi, valeurs["nom"], r._mapping,
                         {k: v for k, v in valeurs.items() if k not in ("ordre", "bloc_id")})
        if ligne:
            res.changements.append(ligne)
        await c.execute(update(table).where(table.c.id == r.id).values(**maj))
    for cle, r in existants.items():
        if cle not in voulus and not getattr(r, champ_masque) and not garder(r):
            await c.execute(update(table).where(table.c.id == r.id).values(**{champ_masque: True},
                                                                          masque_par="construction"))
            res.masques += 1
            res.changements.append(f"{quoi} disparu(e) de Duffus, masqué(e) : « {r.nom} »")
    return ids


def _rapprocher_blocs(existants: list, voulus: list[BlocPrepare]) -> dict[int, object]:
    """Indice du bloc voulu → ligne existante qui le porte (absent : ligne à créer). Par ordre de préférence :

    1. même titre, même partie, ligne visible ; 2. même titre, ligne visible (un bloc entier qui change de nature garde
    sa ligne et ses coches), si aucune ligne de ce titre ne porte déjà cette partie (la clé (étage, titre, partie) est
    unique) ; 3. et 4. les mêmes, ligne masquée comprise ; 5. et 6. même position et titre disparu de la tranche (Duffus
    a retitré le bloc), même partie d'abord. Chaque ligne ne sert qu'une fois."""
    titres_voulus = {b.titre for b in voulus}
    cles = {(x.titre, x.partie) for x in existants}

    def meme_partie(b, x):
        return x.titre == b.titre and x.partie == b.nature

    def meme_titre(b, x):
        return x.titre == b.titre and (b.titre, b.nature) not in cles

    def retitre(b, x):
        return x.ordre == b.ordre and x.titre not in titres_voulus and (b.titre, b.nature) not in cles

    etapes = [(meme_partie, True), (meme_titre, True), (meme_partie, False), (meme_titre, False),
              (lambda b, x: retitre(b, x) and x.partie == b.nature, False), (retitre, False)]
    pris: dict[int, object] = {}
    utilises: set[int] = set()
    for critere, visibles_seulement in etapes:
        for i, b in enumerate(voulus):
            if i in pris:
                continue
            r = next((x for x in existants if x.id not in utilises and not (visibles_seulement and x.masque)
                      and critere(b, x)), None)
            if r is not None:
                pris[i] = r
                utilises.add(r.id)
    return pris


async def _synchroniser_blocs(c: AsyncConnection, etage_id: int, voulus: list[BlocPrepare],
                              res: Resultat) -> tuple[dict[tuple[str, str], int], int]:
    """Ajoute, met à jour et masque les blocs du guide ; renvoie (titre, partie) → id et le nombre de blocs dont la
    nature change (pour le garde-fou). Une correction d'admin sur un bloc entier n'est jamais écrasée ; sur un bloc
    devenu hybride, elle ne s'applique plus : chaque moitié prend la nature de ses quêtes (règle du 06/11)."""
    existants = list(await c.execute(select(t.bloc).where(t.bloc.c.etage_id == etage_id)))
    hybrides = {b.titre for b in voulus if b.moitie}
    pris = _rapprocher_blocs(existants, voulus)
    ids: dict[tuple[str, str], int] = {}
    changent = 0
    for i, b in enumerate(voulus):
        r = pris.get(i)
        nom = f"bloc « {b.titre} »" + (f" (moitié {b.nature})" if b.moitie else "")
        valeurs = dict(titre=b.titre, numero=b.numero, ordre=b.ordre, partie=b.nature, duffus_url=b.duffus_url,
                       duffus_ancre=b.duffus_ancre)
        if r is None:
            ids[(b.titre, b.nature)] = (await c.execute(insert(t.bloc).values(
                etage_id=etage_id, nature=b.nature, nature_origine="construction", masque=False, **valeurs)
                .returning(t.bloc.c.id))).scalar_one()
            res.ajoutes += 1
            res.changements.append(f"{nom} ajouté ({b.nature})")
            continue
        ids[(b.titre, b.nature)] = r.id
        if r.titre != b.titre:
            res.changements.append(f"bloc « {r.titre} » retitré : « {b.titre} »")
        maj = dict(valeurs)
        if r.nature_origine == "admin" and b.titre in hybrides:
            maj |= {"nature_origine": "construction", "nature_motif": None}
            res.changements.append(f"{nom} : bloc coupé en deux, la correction d'admin « {r.nature_motif} » "
                                   "ne s'applique plus (corriger la nature des quêtes)")
        if r.nature_origine != "admin" or b.titre in hybrides:
            maj["nature"] = b.nature
            if r.nature != b.nature and not r.masque:
                changent += 1
                res.changements.append(f"{nom} : nature « {r.nature} » → « {b.nature} »")
        if r.masque and r.masque_par == "construction":
            maj |= {"masque": False, "masque_par": None}
            res.demasques += 1
        await c.execute(update(t.bloc).where(t.bloc.c.id == r.id).values(**maj))
    gardes = {r.id for r in pris.values()}
    titres = {b.titre for b in voulus}
    for r in existants:
        if r.id not in gardes and not r.masque:
            await c.execute(update(t.bloc).where(t.bloc.c.id == r.id).values(masque=True, masque_par="construction"))
            res.masques += 1
            res.changements.append(f"bloc « {r.titre} » : plus de quête {r.partie}, moitié masquée" if r.titre in titres
                                   else f"bloc disparu de Duffus, masqué : « {r.titre} »")
    return ids, changent


async def _elements_visibles(c: AsyncConnection, etage_id: int) -> set[tuple[str, int]]:
    """Les cases (de donjons visibles) et les blocs visibles : ce que les grimpeurs cochent."""
    cases = await c.execute(select(t.case_succes.c.id).select_from(t.case_succes.join(t.donjon)).where(
        t.donjon.c.etage_id == etage_id, t.donjon.c.masque.is_(False), t.case_succes.c.masquee.is_(False)))
    blocs = await c.execute(select(t.bloc.c.id).where(t.bloc.c.etage_id == etage_id, t.bloc.c.masque.is_(False)))
    return {("case", r.id) for r in cases} | {("bloc", r.id) for r in blocs}


async def _disponibles(c: AsyncConnection, donjons: list[DonjonPrepare], maintenant: datetime) -> None:
    for d in donjons:
        valeurs = dict(nom=d.nom, niveau=d.niveau, dofusdb_id=d.dofusdb_id, succes_source=d.succes_source,
                       succes=[{"id": x.duffus_id, "nom": x.nom, "condition": x.condition,
                                "est_classique": x.est_classique} for x in d.cases], maj_le=maintenant)
        await c.execute(insert_pg(t.donjon_disponible).values(duffus_id=d.duffus_id, **valeurs)
                        .on_conflict_do_update(index_elements=["duffus_id"], set_=valeurs))


async def ecrire_etage(moteur: AsyncEngine, e: EtagePrepare, maintenant: datetime, acteur: int | None = None,
                       forcer: bool = False) -> Resultat:
    async with moteur.begin() as c:
        etage = (await c.execute(select(t.etage).where(t.etage.c.numero == e.numero).with_for_update())).one_or_none()
        if etage is None:
            ouvert = e.numero == 0
            etage_id = (await c.execute(insert(t.etage).values(
                numero=e.numero, nom=e.nom, niveau_min=e.niveau_min, niveau_max=e.niveau_max, level_cap=e.level_cap,
                statut="ouvert" if ouvert else "scelle", ouvert_le=e.ouvert_le if ouvert else None,
                date_plancher_suivant=e.date_plancher_suivant, duffus_tranche_id=e.tranche,
                ambiance_url=e.ambiance_url, alertes=e.alertes, maj_le=maintenant,
            ).returning(t.etage.c.id))).scalar_one()  # fmt: skip
            res = Resultat(etage_id, True)
        else:
            res = Resultat(etage.id, False)
            avant = await _elements_visibles(c, etage.id)
            regle = etage.corrections
            valeurs = dict(niveau_min=e.niveau_min, niveau_max=e.niveau_max, duffus_tranche_id=e.tranche,
                           alertes=e.alertes, maj_le=maintenant)
            for champ in ("nom", "level_cap", "ambiance_url"):
                if champ not in regle and getattr(e, champ) is not None:
                    valeurs[champ] = getattr(e, champ)
            await c.execute(update(t.etage).where(t.etage.c.id == etage.id).values(**valeurs))
        etage_id = res.etage_id

        # Donjons, puis leurs cases.
        existants = {r.duffus_id: r for r in await c.execute(select(t.donjon).where(t.donjon.c.etage_id == etage_id))}
        voulus = {d.duffus_id: dict(nom=d.nom, niveau=d.niveau, ordre=d.ordre, bloc=d.bloc, dofusdb_id=d.dofusdb_id,
                                    succes_source=d.succes_source) for d in e.donjons}
        ids_donjons = await _synchroniser(c, t.donjon, existants, voulus, "masque", "donjon", res,
                                          {"etage_id": etage_id, "origine": "propose"},
                                          garder=lambda r: r.origine == "admin")
        for d in e.donjons:
            did = ids_donjons[d.duffus_id]
            q_cases = select(t.case_succes).where(t.case_succes.c.donjon_id == did)
            cases = {r.duffus_id: r for r in await c.execute(q_cases)}
            await c.execute(update(t.case_succes).where(t.case_succes.c.donjon_id == did).values(est_classique=False))
            voulues = {x.duffus_id: dict(nom=x.nom, condition=x.condition, ordre=x.ordre, est_classique=x.est_classique)
                       for x in d.cases}
            # Les ordres des cases masquées partent au-delà, pour laisser la place (contrainte différée).
            await c.execute(update(t.case_succes).where(t.case_succes.c.donjon_id == did,
                                                        t.case_succes.c.duffus_id.not_in(voulues))
                            .values(ordre=t.case_succes.c.ordre + 100))
            await _synchroniser(c, t.case_succes, cases, voulues, "masquee", "case", res, {"donjon_id": did})

        # Blocs du guide, puis quêtes (chacune rattachée à son bloc).
        e_blocs = e.blocs or []
        ids_blocs, blocs_changes = await _synchroniser_blocs(c, etage_id, e_blocs, res)

        # Quêtes : la nature d'origine « admin » n'est jamais écrasée.
        existantes = {r.duffus_id: r for r in await c.execute(select(t.quete).where(t.quete.c.etage_id == etage_id))}
        changent_de_nature = blocs_changes
        voulues_q: dict[str, dict] = {}
        for q in e.quetes:
            ancienne = existantes.get(q.duffus_id)
            admin = ancienne is not None and ancienne.nature_origine == "admin"
            # La quête va dans la partie de sa nature (celle de l'admin s'il l'a corrigée) ; à défaut, dans la
            # partie de la nature calculée, qui existe toujours.
            nature = ancienne.nature if admin else q.nature
            v = dict(nom=q.nom, niveau=q.niveau, bloc=q.bloc,
                     bloc_id=ids_blocs.get((q.bloc, nature), ids_blocs.get((q.bloc, q.nature))), ordre=q.ordre,
                     jusqu_ou=q.jusqu_ou, a_lier=q.a_lier, nature=q.nature, nature_origine=q.nature_origine,
                     dofus=list(q.dofus))
            if admin:
                v = {k: x for k, x in v.items() if k not in ("nature", "nature_origine", "dofus")}
            voulues_q[q.duffus_id] = v
        ids_quetes = await _synchroniser(c, t.quete, existantes, voulues_q, "masquee", "quête", res,
                                         {"etage_id": etage_id})
        for q in e.quetes:
            if q.fiche is not None:
                valeurs = {"source": q.source_fiche, "contenu": contenu_fiche_json(q.fiche)}
                await c.execute(insert_pg(t.fiche_quete).values(quete_id=ids_quetes[q.duffus_id], **valeurs)
                                .on_conflict_do_update(index_elements=["quete_id"], set_=valeurs))

        # Garde-fou d'un étage ouvert.
        if etage is not None and etage.statut == "ouvert":
            touches = len(avant - await _elements_visibles(c, etage_id)) + changent_de_nature
            if avant and touches / len(avant) > GARDE_FOU and not forcer:
                raise EcritureRefusee(f"étage ouvert : {touches} éléments sur {len(avant)} disparaîtraient ou "
                                      "changeraient de nature (plus de 10 %) ; relancer avec --forcer après "
                                      "vérification")

        await _disponibles(c, e.disponibles, maintenant)
        await c.execute(insert(t.journal).values(
            horodatage=maintenant, acteur_discord_id=acteur, type="contenu_cree" if res.cree else "contenu_maj",
            etage_id=etage_id, public=False,
            details={"tranche": e.tranche, "ajoutes": res.ajoutes, "masques": res.masques,
                     "demasques": res.demasques, "changements": res.changements[:200]},
        ))  # fmt: skip
        return res
