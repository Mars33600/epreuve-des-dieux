// L'Épreuve des Dieux : affichage de /api/etat, repris de docs/maquette-v1.html.
//
// Règle de sécurité : AUCUNE donnée n'est insérée comme du HTML. On construit les éléments avec
// la fonction el() et textContent, si bien qu'un pseudo comme « <img onerror=…> » s'affiche tel
// quel au lieu de s'exécuter.
//
// Le calcul de la jauge n'est PAS refait ici : le serveur envoie points, maximum et seuil.
// Ce fichier ne fait que dessiner, et rafraîchit les données toutes les 30 secondes.
"use strict";

const Epreuve = (() => {
  const PARIS = "Europe/Paris";
  const RAFRAICHIR_MS = 30000;
  const DIFF = {
    easy: { nom: "Aventurier", pluriel: "Aventuriers", c: "var(--easy)" },
    med: { nom: "Éclaireur", pluriel: "Éclaireurs", c: "var(--med)" },
    hard: { nom: "Collectionneur", pluriel: "Collectionneurs", c: "var(--hard)" },
  };
  // Le nom court des marques sur les cartes, par rang de palier (sinon : le libellé).
  const COURT = { 1: "Donjon", 2: "Full succès", 3: "Quêtes" };
  const COULEUR_PALIER = { 1: "var(--easy)", 2: "var(--med)", 3: "var(--hard)" };

  // --- Fonctions pures (testées sans navigateur) ------------------------------------------------

  /** Le compte à rebours : vers l'ouverture de l'étage 0, puis vers la date plancher.
   *  Renvoie null quand il n'y a plus rien à attendre (le bloc disparaît). */
  function compteARebours(maintenant, etat) {
    const ouverture = etat.ouverture_etage0 ? new Date(etat.ouverture_etage0) : null;
    if (ouverture && maintenant < ouverture) {
      return { libelle: "Ouverture de l'étage 0", cible: ouverture };
    }
    const ec = etat.etage_courant;
    if (ec && ec.date_plancher_suivant) {
      const plancher = new Date(ec.date_plancher_suivant);
      const suivant = ec.numero + 1;
      if (maintenant < plancher) {
        return { libelle: `Étage ${suivant} déblocable au plus tôt`, cible: plancher };
      }
      if (ec.jauge && ec.jauge.pleine) {
        return { libelle: `Étage ${suivant}`, texte: `Étage ${suivant} déblocable` };
      }
    }
    return null;
  }

  /** « 3 j 04 h 07 » entre deux dates. */
  function duree(ms) {
    const j = Math.floor(ms / 864e5), h = Math.floor(ms / 36e5) % 24, m = Math.floor(ms / 6e4) % 60;
    return `${j} j ${String(h).padStart(2, "0")} h ${String(m).padStart(2, "0")}`;
  }

  /** « il y a 2 h », « hier », « le 31/10 ». */
  function ilYA(date, maintenant) {
    const min = Math.round((maintenant - date) / 6e4);
    if (min < 1) return "à l'instant";
    if (min < 60) return `il y a ${min} min`;
    const h = Math.round(min / 60);
    if (h < 24) return `il y a ${h} h`;
    if (h < 48) return "hier";
    if (h < 24 * 7) return `il y a ${Math.round(h / 24)} j`;
    return "le " + date.toLocaleDateString("fr-FR", { timeZone: PARIS, day: "2-digit", month: "2-digit" });
  }

  function trierGrimpeurs(liste) {
    // Actifs d'abord, puis ordre alphabétique. Pas de tri par score : l'ascension est collective.
    return [...liste].sort((a, b) =>
      (a.statut === "actif" ? 0 : 1) - (b.statut === "actif" ? 0 : 1) ||
      a.pseudo.localeCompare(b.pseudo, "fr", { sensitivity: "base" }));
  }

  // --- Le reste a besoin du navigateur -----------------------------------------------------------

  /** Crée un élément. `props` : class, text, style (variables CSS), attrs, data. Le texte passe toujours par textContent. */
  function el(tag, props = {}, ...enfants) {
    const n = document.createElement(tag);
    if (props.class) n.className = props.class;
    if (props.text !== undefined) n.textContent = String(props.text);
    for (const [k, v] of Object.entries(props.style || {})) n.style.setProperty(k, v);
    for (const [k, v] of Object.entries(props.attrs || {})) n.setAttribute(k, v);
    for (const [k, v] of Object.entries(props.data || {})) n.dataset[k] = v;
    for (const e of enfants.flat()) if (e !== null && e !== undefined && e !== false) {
      n.append(typeof e === "string" ? document.createTextNode(e) : e);
    }
    return n;
  }
  const $ = (id) => document.getElementById(id);
  const remplacer = (id, ...enfants) => $(id).replaceChildren(...enfants.flat());

  let etat = null;
  let filtre = "all";
  let horlogeDecalage = 0; // en démo : écart entre l'heure simulée et l'heure réelle
  let dernierFil = null;

  function maintenant() { return new Date(Date.now() + horlogeDecalage); }

  function dateLongue(d) {
    return d.toLocaleDateString("fr-FR", { timeZone: PARIS, weekday: "long", day: "numeric", month: "long" });
  }
  /** « vendredi 13 novembre à 17 h » */
  function quandLong(d) {
    const h = d.toLocaleTimeString("fr-FR", { timeZone: PARIS, hour: "numeric", minute: "2-digit" });
    const [hh, mm] = h.split(":");
    return `${dateLongue(d)} à ${Number(hh)} h${mm && mm !== "00" ? " " + mm : ""}`;
  }

  function dessinerHorloge() {
    if (!etat) return;
    const cr = compteARebours(maintenant(), etat);
    $("clockBox").hidden = !cr;
    if (!cr) return;
    $("clockLabel").textContent = cr.libelle;
    if (cr.texte) {
      $("clock").textContent = cr.texte;
      $("clockSub").textContent = "";
      return;
    }
    $("clock").textContent = duree(cr.cible - maintenant());
    $("clockSub").textContent = quandLong(cr.cible);
  }

  function dessinerTour() {
    const tour = etat.tour || [];
    const courant = tour.find((e) => e.statut === "ouvert");
    const scelles = tour.filter((e) => e.statut === "scelle");
    const termines = tour.filter((e) => e.statut === "termine");
    // On ne connaît pas le nombre d'étages : on dessine 6 étages scellés « ? » au-dessus.
    const hauts = Math.max(6, scelles.length);
    const lignes = [];
    for (let i = hauts; i >= 1; i--) {
      const w = 52 + (hauts - i) * (48 / hauts);
      lignes.push(el("div", { class: "floor locked", style: { "--w": `${w}%` } },
        el("b", { text: "?" }), el("span", { text: i === 1 ? "scellé" : "" })));
    }
    if (courant) {
      lignes.push(el("div", { class: "floor current", style: { "--w": "100%" }, attrs: { "aria-current": "step" } },
        el("b", { text: `Étage ${courant.numero}` }), el("span", { text: courant.nom || "" })));
    }
    for (const e of [...termines].reverse()) {
      lignes.push(el("div", { class: "floor", style: { "--w": "100%" } },
        el("b", { text: `Étage ${e.numero}` }), el("span", { text: e.nom || "terminé" })));
    }
    remplacer("floors", lignes);
  }

  function dessinerEtage() {
    const ec = etat.etage_courant;
    if (!ec) {
      $("floorTitle").textContent = "Aucun étage ouvert";
      remplacer("facts"); remplacer("gauges");
      $("verdict").textContent = "La tour attend son premier étage.";
      return;
    }
    $("floorTitle").textContent = `Étage ${ec.numero} · ${ec.nom}`;
    remplacer("facts",
      el("span", {}, "Cap de niveau ", el("b", { class: "num", text: ec.level_cap })),
      ec.donjons.length ? el("span", {}, ec.donjons.length > 1 ? "Donjons " : "Donjon ",
        el("b", { text: ec.donjons.join(", ") })) : null,
      ec.zone_quetes ? el("span", {}, "Quêtes ", el("b", { text: ec.zone_quetes })) : null);

    // Une seule jauge : remplie à min(points ÷ maximum, 100 %), repère au seuil.
    const j = ec.jauge, d = ec.comptes_par_difficulte;
    const pct = j.maximum > 0 ? Math.min(100, (j.points / j.maximum) * 100) : 0;
    const manque = Math.max(0, j.seuil - j.points);
    const lecture = `${j.points} points sur ${j.seuil} requis, maximum ${j.maximum}`;
    remplacer("gauges", el("div", { class: "gauge" + (j.pleine ? " ok" : ""), style: { "--c": "var(--gold)" } },
      el("span", { class: "tag", text: `Jauge de l'étage · seuil ${ec.seuil_pourcent} % du maximum` }),
      // Le texte est toujours là : la jauge se lit sans la couleur.
      el("div", { class: "count" }, String(j.points), el("small", { text: ` points sur ${j.seuil} requis` })),
      el("div", { class: "bar", attrs: { role: "img", "aria-label": lecture } },
        el("i", { style: { "--p": `${pct}%` } }),
        el("span", { class: "seuil", style: { "--s": `${ec.seuil_pourcent}%` }, attrs: { "data-label": `seuil ${j.seuil}` } })),
      el("span", { class: "left", text: j.pleine ? "Seuil atteint" : `Il en manque ${manque}` }),
      el("div", { class: "detail" },
        el("span", {}, "Maximum ", el("b", { class: "num", text: j.maximum }),
          ` = ${d.hard} Collectionneur${d.hard > 1 ? "s" : ""} × 3 + ${d.med} Éclaireur${d.med > 1 ? "s" : ""} × 2`
          + ` + ${d.easy} Aventurier${d.easy > 1 ? "s" : ""} × 1. Seuil ${ec.seuil_pourcent} %.`),
        el("div", { class: "paliers" }, ec.paliers.map((p) =>
          el("span", { class: "mark" + (p.grimpeurs ? " done" : ""), style: { "--c": COULEUR_PALIER[p.rang] } },
            `Palier ${p.rang} · ${COURT[p.rang] || p.libelle} : `, el("b", { class: "num", text: p.grimpeurs })))))));

    const v = $("verdict");
    const suivant = ec.numero + 1;
    const plancher = ec.date_plancher_suivant ? new Date(ec.date_plancher_suivant) : null;
    const avantPlancher = plancher && maintenant() < plancher;
    v.className = "verdict" + (j.pleine ? " open" : "");
    if (j.maximum === 0) {
      v.replaceChildren(el("b", { text: "Aucun grimpeur compté." }), " La jauge se remplira dès la première inscription.");
      return;
    }
    const morceaux = [`${ec.n_comptes} grimpeur${ec.n_comptes > 1 ? "s" : ""} compté${ec.n_comptes > 1 ? "s" : ""}`];
    if (ec.n_pause) morceaux.push(`${ec.n_pause} en pause`);
    if (ec.n_retardataires) morceaux.push(`${ec.n_retardataires} retardataire${ec.n_retardataires > 1 ? "s" : ""} (hors de la jauge tant qu'il n'a pas rattrapé)`);
    const base = " " + morceaux.join(", ") + ".";
    if (j.pleine) {
      v.replaceChildren(el("b", { text: "Le seuil est atteint." }),
        avantPlancher ? ` Un admin pourra ouvrir l'étage ${suivant} le ${quandLong(plancher)}, pas avant.`
          : ` Un admin peut ouvrir l'étage ${suivant}.`, base);
    } else {
      v.replaceChildren(`L'étage ${suivant} s'ouvre quand la jauge atteint le seuil` +
        (plancher ? `, et pas avant le ${quandLong(plancher)}.` : ".") + base);
    }
  }

  function dessinerClasses() {
    remplacer("classes", etat.classes.map((c) => {
      const vide = c.actifs === 0;
      return el("li", { class: "classe" + (vide ? " vide" : "") },
        el("b", { text: c.classe }),
        el("span", { class: "combien", text: vide ? "Personne encore" : String(c.actifs) }),
        c.en_pause ? el("small", { text: `+ ${c.en_pause} en pause` }) : null);
    }));
  }

  function dessinerFiltres() {
    const options = [["all", "Tous"], ...Object.entries(DIFF).map(([k, d]) => [k, d.pluriel])];
    remplacer("filters", options.map(([k, libelle]) => {
      const n = k === "all" ? etat.grimpeurs.length : etat.grimpeurs.filter((g) => g.difficulte === k).length;
      return el("button", { class: "chip", attrs: { type: "button", "aria-pressed": String(filtre === k) }, data: { f: k } },
        `${libelle} `, el("span", { class: "num", text: n }));
    }));
  }

  function statutLisible(g) {
    if (g.statut !== "actif") return "En pause";
    return g.retardataire ? "Rattrape le groupe" : "Actif";
  }

  function marques(g) {
    return [1, 2, 3].map((rang) => {
      const fait = !!g.marques[String(rang)];
      return el("span", { class: "mark" + (fait ? " done" : ""),
        attrs: { title: `${COURT[rang]} : ${fait ? "fait" : "pas encore"}` },
        text: rang === 3 && fait ? "Quêtes déclarées" : COURT[rang] });
    });
  }

  function carteGrimpeur(g, ec) {
    const d = DIFF[g.difficulte];
    const cap = ec ? ec.level_cap : null;
    const niveau = g.niveau === null ? "Niveau inconnu" : cap ? `Niv. ${g.niveau} / ${cap}` : `Niv. ${g.niveau}`;
    const pct = g.niveau && cap ? Math.min(100, (g.niveau / cap) * 100) : 0;
    return el("button", { class: "player" + (g.statut === "actif" ? "" : " paused"), style: { "--c": d.c },
      attrs: { type: "button", "aria-haspopup": "dialog" }, data: { id: g.id } },
      el("div", { class: "ptop" }, el("strong", { text: g.pseudo }), el("span", { class: "diff", text: d.nom })),
      el("div", { class: "meta" }, el("span", { text: g.classe }), el("span", { text: statutLisible(g) }),
        el("span", { class: "pts", text: `${g.points} / ${g.points_vises} pt${g.points_vises > 1 ? "s" : ""}` })),
      el("div", { class: "lvl" },
        el("div", { class: "meta" }, el("span", { class: "num" + (g.au_dessus_du_cap ? " over" : ""), text: niveau }),
          g.au_dessus_du_cap ? el("span", { class: "over", text: "Dépasse le cap" }) : null),
        el("div", { class: "bar", attrs: { "aria-hidden": "true" } }, el("i", { style: { "--p": `${pct}%` } }))),
      el("div", { class: "marks" }, marques(g)));
  }

  function dessinerGrimpeurs() {
    const ec = etat.etage_courant;
    const liste = trierGrimpeurs(etat.grimpeurs.filter((g) => filtre === "all" || g.difficulte === filtre));
    if (!liste.length) {
      remplacer("roster", el("p", { class: "vide-liste", text: "Aucun grimpeur pour l'instant." }));
      return;
    }
    remplacer("roster", liste.map((g) => carteGrimpeur(g, ec)));
  }

  function dessinerFil() {
    const cle = JSON.stringify(etat.fil[0] || null);
    const nouveau = dernierFil !== null && cle !== dernierFil;
    dernierFil = cle;
    if (!etat.fil.length) {
      remplacer("feed", el("li", {}, el("span"), el("span", { class: "note", text: "Aucune validation pour l'instant." })));
      return;
    }
    const now = maintenant();
    remplacer("feed", etat.fil.map((f, i) => {
      const quand = new Date(f.horodatage);
      const noms = [];
      f.pseudos.forEach((p, j) => {
        if (j > 0) noms.push(j === f.pseudos.length - 1 ? " et " : ", ");
        noms.push(el("b", { text: p }));
      });
      return el("li", { class: nouveau && i === 0 ? "fresh" : "" },
        el("time", { attrs: { datetime: f.horodatage }, text: ilYA(quand, now) }),
        el("span", {}, ...noms, " ", f.texte));
    }));
  }

  function ouvrirFiche(id) {
    const g = etat.grimpeurs.find((x) => x.id === id);
    if (!g) return;
    const ec = etat.etage_courant, d = DIFF[g.difficulte];
    const corps = $("sheetBody");
    corps.style.setProperty("--c", d.c);
    const niveau = g.niveau === null ? "Niveau inconnu" : ec ? `Niveau ${g.niveau}, cap ${ec.level_cap}` : `Niveau ${g.niveau}`;
    corps.replaceChildren(
      el("div", { class: "row" },
        el("div", {}, el("div", { class: "eyebrow", style: { color: d.c }, text: d.nom }),
          el("h3", { attrs: { id: "sheetTitle" }, text: g.pseudo })),
        el("button", { class: "btn", attrs: { type: "button" }, data: { close: "1" }, text: "Fermer" })),
      el("div", { class: "meta" }, el("span", { text: g.classe }),
        el("span", { class: "num" + (g.au_dessus_du_cap ? " over" : ""), text: niveau }),
        el("span", { text: statutLisible(g) }),
        el("span", { class: "pts", text: `${g.points} / ${g.points_vises} points` })),
      el("div", { class: "checks" }, (ec ? ec.paliers : []).map((p) => {
        const fait = !!g.marques[String(p.rang)];
        return el("div", { class: "check" + (fait ? " done" : "") },
          el("span", {}, `Palier ${p.rang} · ${p.libelle}`,
            el("small", { text: fait ? (p.rang === 3 ? "Déclaré par le grimpeur" : "Validé par un admin") : "Pas encore fait" })),
          el("span", { class: "etat", text: fait ? "Fait" : "À faire" }));
      })),
      el("p", { class: "note", text: "Les points suivent l'ordre des paliers : les quêtes ne rapportent qu'une fois le full succès atteint." }),
      g.retardataire ? el("p", { class: "note", text: "Rattrape le groupe : ses points ne comptent pas encore. Il entrera dans la jauge en rattrapant le grimpeur le moins avancé." }) : null,
      g.au_dessus_du_cap ? el("p", { class: "note over", text: "Niveau au-dessus du cap : un admin jugera s'il s'agit d'un dépassement involontaire." }) : null,
      g.statut !== "actif" ? el("p", { class: "note", text: "En pause : ne compte pas dans la jauge pour l’instant." }) : null);
    const dlg = $("sheet");
    if (!dlg.open) dlg.showModal();
    corps.querySelector("[data-close]").focus();
  }

  function toutDessiner() {
    dessinerHorloge(); dessinerTour(); dessinerEtage(); dessinerClasses();
    dessinerFiltres(); dessinerGrimpeurs(); dessinerFil();
  }

  async function rafraichir() {
    const alerte = $("alerte");
    try {
      const params = new URLSearchParams(location.search);
      const url = "/api/etat" + (params.get("horloge") ? `?horloge=${encodeURIComponent(params.get("horloge"))}` : "");
      const r = await fetch(url, { headers: { Accept: "application/json" } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      etat = await r.json();
      alerte.hidden = r.headers.get("X-Etat-Perime") !== "1";
      alerte.textContent = "Dernier état connu : la mise à jour a échoué, nouvel essai dans 30 secondes.";
      toutDessiner();
    } catch (e) {
      alerte.hidden = false;
      alerte.textContent = etat
        ? "Dernier état connu : la mise à jour a échoué, nouvel essai dans 30 secondes."
        : "Les données sont momentanément indisponibles. Réessaie dans une minute.";
    }
  }

  function demarrer() {
    const simulee = document.body.dataset.horloge;
    if (simulee) horlogeDecalage = new Date(simulee) - Date.now();
    try { etat = JSON.parse($("etat-initial").textContent); } catch { etat = null; }
    if (etat) toutDessiner();

    $("filters").addEventListener("click", (e) => {
      const b = e.target.closest("[data-f]");
      if (!b) return;
      filtre = b.dataset.f;
      dessinerFiltres(); dessinerGrimpeurs();
    });
    $("roster").addEventListener("click", (e) => {
      const b = e.target.closest("[data-id]");
      if (b) ouvrirFiche(Number(b.dataset.id));
    });
    $("sheet").addEventListener("click", (e) => {
      if (e.target === $("sheet") || e.target.closest("[data-close]")) $("sheet").close();
    });
    setInterval(dessinerHorloge, 30000);
    setInterval(rafraichir, RAFRAICHIR_MS);
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
    else demarrer();
  }

  return { compteARebours, duree, ilYA, trierGrimpeurs };
})();
