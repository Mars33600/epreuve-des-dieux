// Builder (lot E3) : l'éditeur d'un build. JavaScript sans dépendance, aucun innerHTML avec des données :
// tout passe par textContent (pas d'injection possible par un nom d'objet ou de build).
"use strict";

(function () {
  const config = JSON.parse(document.getElementById("config-builder").textContent);
  const modifiable = !!config.modifiable;
  const $ = (id) => document.getElementById(id);
  const NOMS = Object.fromEntries(config.emplacements);

  const etat = {
    nom: "", classe: config.classes[0], niveau: 200,
    objets: {}, // emplacement → résumé d'objet (id, nom, niveau, icone, caracs…)
    base: {}, parcho: {}, note: "",
    resultat: null,
  };

  function el(tag, attrs, enfants) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "texte") n.textContent = v;
      else if (k === "classe") n.className = v;
      else if (v !== null && v !== undefined && v !== false) n.setAttribute(k, v === true ? "" : v);
    }
    for (const e of enfants || []) if (e) n.append(e);
    return n;
  }

  function signe(v) { return (v > 0 ? "+" : "") + v; }

  function famille(emplacement) {
    if (emplacement === "arme") return config.familles.arme;
    if (emplacement === "familier") return config.familles.familier;
    if (emplacement.startsWith("dofus")) return config.familles.dofus;
    return null;
  }

  // --- Emplacements -------------------------------------------------------------------------------------------

  function dessinerEmplacements(alertes) {
    const ul = $("b-emplacements");
    ul.replaceChildren();
    for (const [e, nom] of config.emplacements) {
      const o = etat.objets[e];
      const raisons = (alertes && alertes[e]) || [];
      const bouton = el("button", {
        type: "button", classe: "b-case" + (o ? " pleine" : "") + (raisons.length ? " alerte" : ""),
        "aria-label": nom + (o ? " : " + o.nom + ", niveau " + o.niveau : " : vide") +
          (raisons.length ? " (" + raisons.join(", ") + ")" : ""),
        disabled: !modifiable && !o,
      }, [
        o && o.icone ? el("img", { src: o.icone, alt: "", loading: "lazy" }) : null,
        el("span", { classe: o ? "b-case-nom" : "", texte: o ? o.nom : nom }),
        raisons.length ? el("span", { classe: "b-signe", "aria-hidden": "true", texte: "!" }) : null,
      ]);
      if (modifiable) bouton.addEventListener("click", () => ouvrirChoix(e));
      ul.append(el("li", { classe: "b-emplacement" }, [bouton]));
    }
  }

  function dessinerAlertes(alertes) {
    const zone = $("b-alertes");
    zone.replaceChildren();
    for (const [e, raisons] of Object.entries(alertes || {})) {
      const o = etat.objets[e];
      for (const r of raisons) zone.append(el("p", { classe: "b-alerte", texte: NOMS[e] + " · " + (o ? o.nom : "") + " : " + r }));
    }
  }

  // --- Fenêtre de choix ---------------------------------------------------------------------------------------

  const choix = { emplacement: null, types: new Set(), caracs: [], decalage: 0, minuteur: null, requete: 0 };

  function ouvrirChoix(emplacement) {
    choix.emplacement = emplacement;
    choix.types = new Set();
    choix.caracs = [];
    $("b-choix-titre").textContent = NOMS[emplacement];
    $("f-texte").value = "";
    $("f-min").value = "";
    $("f-max").value = String(etat.niveau);
    $("b-retirer").hidden = !etat.objets[emplacement];
    dessinerTypes();
    dessinerCaracs();
    $("b-choix").showModal();
    chercher(true);
    $("f-texte").focus();
  }

  function dessinerTypes() {
    const zone = $("f-types");
    zone.replaceChildren();
    const f = famille(choix.emplacement);
    zone.hidden = !f;
    for (const [t, nom] of f || []) {
      const b = el("button", { type: "button", classe: "b-puce", "aria-pressed": choix.types.has(t) ? "true" : "false", texte: nom });
      b.addEventListener("click", () => {
        if (choix.types.has(t)) choix.types.delete(t); else choix.types.add(t);
        dessinerTypes();
        chercher(true);
      });
      zone.append(b);
    }
  }

  function dessinerCaracs() {
    const zone = $("f-caracs");
    zone.replaceChildren();
    for (const c of choix.caracs) {
      const b = el("button", { type: "button", classe: "b-puce retirable", "aria-pressed": "true", "aria-label": "Retirer le filtre " + c, texte: c });
      b.addEventListener("click", () => {
        choix.caracs = choix.caracs.filter((x) => x !== c);
        dessinerCaracs();
        chercher(true);
      });
      zone.append(b);
    }
  }

  function ligneCaracs(caracs) {
    const p = el("span", { classe: "b-objet-caracs" });
    caracs.slice(0, 8).forEach(([c, v], i) => {
      if (i) p.append(" · ");
      p.append(el("span", { classe: v < 0 ? "neg" : "", texte: signe(v) + " " + c }));
    });
    return p;
  }

  async function chercher(depuisDebut) {
    if (depuisDebut) choix.decalage = 0;
    const params = new URLSearchParams({ emplacement: choix.emplacement, q: $("f-texte").value.trim(), decalage: String(choix.decalage) });
    const min = parseInt($("f-min").value, 10), max = parseInt($("f-max").value, 10);
    if (!isNaN(min)) params.set("niveau_min", String(min));
    if (!isNaN(max)) params.set("niveau_max", String(max));
    for (const t of choix.types) params.append("type", String(t));
    for (const c of choix.caracs) params.append("carac", c);
    const numero = ++choix.requete;
    let donnees;
    try {
      const r = await fetch("/api/builder/objets?" + params.toString(), { headers: { Accept: "application/json" } });
      donnees = await r.json();
      if (!r.ok) throw new Error(donnees.message || "Erreur");
    } catch (err) {
      if (numero === choix.requete) $("b-choix-compte").textContent = "Recherche impossible : " + err.message;
      return;
    }
    if (numero !== choix.requete) return; // une recherche plus récente est partie entre-temps
    const ul = $("b-resultats");
    if (depuisDebut) ul.replaceChildren();
    for (const o of donnees.objets) {
      const b = el("button", { type: "button", classe: "b-objet" }, [
        o.icone ? el("img", { src: o.icone, alt: "", loading: "lazy" }) : el("span"),
        el("span", {}, [
          el("span", { classe: "b-objet-nom", texte: o.nom }), document.createElement("br"),
          el("span", { classe: "b-objet-meta", texte: "Niv. " + o.niveau + (o.conditions ? " · conditions" : "") }),
          document.createElement("br"), ligneCaracs(o.caracs),
        ]),
      ]);
      b.addEventListener("click", () => equiper(choix.emplacement, o));
      ul.append(el("li", {}, [b]));
    }
    choix.decalage += donnees.objets.length;
    $("b-choix-compte").textContent = donnees.total + " objet" + (donnees.total > 1 ? "s" : "");
    $("b-plus").hidden = choix.decalage >= donnees.total;
  }

  function relancer() {
    clearTimeout(choix.minuteur);
    choix.minuteur = setTimeout(() => chercher(true), 250);
  }

  function equiper(emplacement, objet) {
    if (objet) etat.objets[emplacement] = objet; else delete etat.objets[emplacement];
    $("b-choix").close();
    changement();
  }

  // --- Calcul (serveur : une seule source des formules) -------------------------------------------------------

  let minuteurCalcul = null, numeroCalcul = 0;

  function corpsBuild() {
    const objets = {};
    for (const [e, o] of Object.entries(etat.objets)) if (o) objets[e] = o.id;
    return { niveau: etat.niveau, objets, caracs_base: etat.base, caracs_parcho: etat.parcho };
  }

  function message(texte, erreur) {
    const p = $("b-etat");
    p.textContent = texte;
    p.classList.toggle("erreur", !!erreur);
  }

  async function calculer() {
    const numero = ++numeroCalcul;
    try {
      const r = await fetch("/api/builder/calcul", {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(corpsBuild()),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.message || "Erreur");
      if (numero !== numeroCalcul) return;
      etat.resultat = d;
      for (const [e, o] of Object.entries(d.objets)) etat.objets[e] = o;
      dessinerResultat();
    } catch (err) {
      if (numero === numeroCalcul) message("Calcul impossible : " + err.message, true);
    }
  }

  function dessinerResultat() {
    const d = etat.resultat;
    if (!d) return;
    dessinerEmplacements(d.alertes);
    dessinerAlertes(d.alertes);
    const a = d.affichage;
    const bulles = $("b-bulles");
    bulles.replaceChildren(...[["PA", "PA"], ["PM", "PM"], ["Vitalité", "PV"]].map(([c, nom]) =>
      el("div", { classe: "b-bulle" }, [el("strong", { texte: String(a[c]) }), el("span", { texte: nom })])));
    const p = $("b-points");
    p.replaceChildren("Points de caractéristique restants : ", el("strong", { texte: d.points.restants + " / " + d.points.total }));
    p.classList.toggle("negatif", d.points.restants < 0);
    dessinerBase();
    const groupes = $("b-groupes");
    groupes.replaceChildren();
    for (const [nom, caracs] of config.groupes) {
      const ul = el("ul");
      for (const c of caracs) {
        const v = a[c] || 0;
        const b = el("button", { type: "button", classe: "b-ligne-carac" + (v === 0 ? " nul" : v < 0 ? " neg" : ""),
          "aria-label": c + " : " + v + ", voir le détail" }, [el("span", { texte: c }), el("b", { texte: String(v) })]);
        b.addEventListener("click", () => ouvrirDetail(c));
        ul.append(el("li", {}, [b]));
      }
      groupes.append(el("div", { classe: "b-groupe" }, [el("h3", { texte: nom }), ul]));
    }
    const zone = $("b-panoplies");
    zone.replaceChildren();
    if (!d.panoplies.length) zone.append(el("p", { classe: "b-vide", texte: "Aucune panoplie active (il faut au moins 2 objets d'une même panoplie)." }));
    for (const pan of d.panoplies) {
      zone.append(el("div", { classe: "b-panoplie" }, [
        el("h3", { texte: pan.nom + " (" + pan.nb + "/" + pan.max + ")" }),
        el("p", { texte: pan.caracs.map(([c, v]) => signe(v) + " " + c).join(" · ") }),
      ]));
    }
    message("");
  }

  function dessinerBase() {
    const d = etat.resultat;
    const tbody = $("b-base").querySelector("tbody");
    tbody.replaceChildren();
    for (const c of config.principales) {
      const ligne = el("tr", {}, [el("th", { scope: "row", texte: c }), el("td", { texte: String(d.totaux[c] || 0) }),
        el("td", { texte: c in d.puissance ? String(d.puissance[c]) : "" })]);
      for (const [cle, max, min] of [["base", 10000, -10000], ["parcho", 100, 0]]) {
        const champ = el("input", { type: "number", inputmode: "numeric", min: String(min), max: String(max),
          value: String(etat[cle][c] || 0), "aria-label": c + (cle === "base" ? " : points de base" : " : parchemin"),
          disabled: !modifiable });
        champ.addEventListener("change", () => {
          let v = parseInt(champ.value, 10) || 0;
          v = Math.min(max, Math.max(min, v));
          champ.value = String(v);
          if (v) etat[cle][c] = v; else delete etat[cle][c];
          changement();
        });
        ligne.append(el("td", {}, [champ]));
      }
      tbody.append(ligne);
    }
  }

  function ouvrirDetail(c) {
    const d = etat.resultat.detail[c] || { objets: [], panoplies: [], base: 0, parchemin: 0 };
    const total = (etat.resultat.affichage[c] || 0);
    $("b-detail-titre").textContent = c + " : " + total;
    const ul = $("b-detail-liste");
    ul.replaceChildren();
    const ligne = (nom, v) => ul.append(el("li", {}, [el("span", { texte: nom }), el("b", { texte: signe(v) })]));
    for (const [nom, v] of d.objets) ligne(nom, v);
    for (const [nom, v] of d.panoplies) ligne(nom, v);
    if (d.base) ligne("Points de base", d.base);
    if (d.parchemin) ligne("Parchemin", d.parchemin);
    const derive = total - (etat.resultat.totaux[c] || 0);
    if (derive) ligne("Base du personnage et dérivés", derive);
    if (!ul.children.length) ul.append(el("li", { texte: "Rien pour l'instant." }));
    $("b-detail").showModal();
  }

  // --- Cycle de mise à jour -----------------------------------------------------------------------------------

  const extensions = []; // fonctions appelées à chaque changement (sauvegarde…)

  function changement() {
    dessinerEmplacements(etat.resultat && etat.resultat.alertes);
    clearTimeout(minuteurCalcul);
    minuteurCalcul = setTimeout(calculer, 150);
    for (const f of extensions) f();
  }

  function brancherFormulaire() {
    $("b-nom").addEventListener("input", (ev) => { etat.nom = ev.target.value; });
    $("b-classe").addEventListener("change", (ev) => { etat.classe = ev.target.value; changement(); });
    $("b-niveau").addEventListener("change", (ev) => {
      const n = Math.min(200, Math.max(1, parseInt(ev.target.value, 10) || 1));
      ev.target.value = String(n);
      etat.niveau = n;
      changement();
    });
    const select = $("f-carac");
    for (const c of config.caracs) select.append(el("option", { value: c, texte: c }));
    select.addEventListener("change", () => {
      if (select.value && !choix.caracs.includes(select.value)) choix.caracs.push(select.value);
      select.value = "";
      dessinerCaracs();
      chercher(true);
    });
    $("f-texte").addEventListener("input", relancer);
    $("f-min").addEventListener("input", relancer);
    $("f-max").addEventListener("input", relancer);
    $("b-plus").addEventListener("click", () => chercher(false));
    $("b-retirer").addEventListener("click", () => equiper(choix.emplacement, null));
    $("b-choix").addEventListener("click", (ev) => { if (ev.target === $("b-choix")) $("b-choix").close(); });
    $("b-detail").addEventListener("click", (ev) => { if (ev.target === $("b-detail")) $("b-detail").close(); });
    const tout = $("b-parcho-tout");
    if (tout) tout.addEventListener("click", () => {
      const plein = config.principales.every((c) => etat.parcho[c] === 100);
      etat.parcho = plein ? {} : Object.fromEntries(config.principales.map((c) => [c, 100]));
      changement();
    });
  }

  // --- Enregistrement (incrément 4) ---------------------------------------------------------------------------

  let buildId = config.build ? config.build.id : null;

  function charger(b) {
    etat.nom = b.nom; etat.classe = b.classe; etat.niveau = b.niveau; etat.note = b.note || "";
    etat.base = { ...b.caracs_base }; etat.parcho = { ...b.caracs_parcho };
    for (const [e, id] of Object.entries(b.objets)) etat.objets[e] = { id, nom: "…", niveau: 0, icone: null, caracs: [] };
    $("b-nom").value = b.nom; $("b-classe").value = b.classe; $("b-niveau").value = String(b.niveau);
    $("b-note").value = etat.note;
    const partage = $("b-partage");
    if (partage) partage.checked = !!b.partage;
  }

  async function enregistrer() {
    const csrf = document.querySelector('meta[name="csrf"]');
    const corps = { ...corpsBuild(), nom: etat.nom.trim() || "Mon build", classe: etat.classe, note: etat.note,
      partage: $("b-partage").checked };
    if (!etat.nom.trim()) { etat.nom = corps.nom; $("b-nom").value = corps.nom; }
    message("Enregistrement…");
    try {
      const r = await fetch(buildId ? "/api/builder/builds/" + buildId : "/api/builder/builds", {
        method: buildId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrf ? csrf.content : "" },
        body: JSON.stringify(corps),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.message || "Erreur");
      if (!buildId) {
        buildId = d.id;
        history.replaceState(null, "", "/builder/" + buildId);
        $("b-supprimer").hidden = false;
      }
      message("Enregistré.");
    } catch (err) {
      message("Enregistrement impossible : " + err.message, true);
    }
  }

  async function supprimer() {
    if (!buildId || !window.confirm("Supprimer ce build ?")) return;
    const csrf = document.querySelector('meta[name="csrf"]');
    const r = await fetch("/api/builder/builds/" + buildId, { method: "DELETE",
      headers: { Accept: "application/json", "X-CSRF-Token": csrf ? csrf.content : "" } });
    if (r.ok) window.location.assign("/builder");
    else message("Suppression impossible.", true);
  }

  async function dupliquer() {
    const csrf = document.querySelector('meta[name="csrf"]');
    message("Duplication…");
    const r = await fetch("/api/builder/builds/" + config.build.id + "/dupliquer", { method: "POST",
      headers: { Accept: "application/json", "X-CSRF-Token": csrf ? csrf.content : "" } });
    const d = await r.json().catch(() => ({}));
    if (r.ok) window.location.assign("/builder/" + d.id);
    else message("Duplication impossible : " + (d.message || r.status), true);
  }

  brancherFormulaire();
  if ($("b-dupliquer")) $("b-dupliquer").addEventListener("click", dupliquer);
  $("b-note").addEventListener("input", (ev) => { etat.note = ev.target.value; });
  if ($("b-enregistrer")) {
    $("b-enregistrer").addEventListener("click", enregistrer);
    $("b-supprimer").addEventListener("click", supprimer);
  }
  if (config.build) charger(config.build);
  dessinerEmplacements();
  calculer();
})();
