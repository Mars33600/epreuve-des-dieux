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

  // --- Cycle de mise à jour -----------------------------------------------------------------------------------

  const extensions = []; // fonctions appelées à chaque changement (calcul, sauvegarde…)

  function changement() {
    dessinerEmplacements();
    for (const f of extensions) f();
  }

  function brancherFormulaire() {
    $("b-nom").addEventListener("input", (ev) => { etat.nom = ev.target.value; changement(); });
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
  }

  brancherFormulaire();
  dessinerEmplacements();
})();
