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
    base: {}, parcho: {}, note: "", modeArme: "melee", buffArme: "",
    fm: {}, // emplacement → { effectId: valeur } (forgemagie : jets choisis et exos)
    variantes: {}, // emplacement → { objet: résumé, fm: {…} } : un second objet, hors des totaux
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
          (etat.variantes[e] ? ", variante " + etat.variantes[e].objet.nom : "") +
          (raisons.length ? " (" + raisons.join(", ") + ")" : ""),
        disabled: !modifiable && !o,
      }, [
        o && o.icone ? el("img", { src: o.icone, alt: "", loading: "lazy" }) : null,
        el("span", { classe: o ? "b-case-nom" : "", texte: o ? o.nom : nom }),
        raisons.length ? el("span", { classe: "b-signe", "aria-hidden": "true", texte: "!" }) : null,
        etat.variantes[e] ? el("span", { classe: "b-var", title: "Variante : " + etat.variantes[e].objet.nom, texte: "⇄" }) : null,
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

  // La cible de la fenêtre : l'objet porté, ou la variante de l'emplacement.
  function objetCible() {
    return choix.variante ? (etat.variantes[choix.emplacement] || {}).objet : etat.objets[choix.emplacement];
  }
  function fmCible() {
    return (choix.variante ? (etat.variantes[choix.emplacement] || {}).fm : etat.fm[choix.emplacement]) || {};
  }

  function ouvrirChoix(emplacement, variante) {
    choix.emplacement = emplacement;
    choix.variante = !!variante;
    choix.types = new Set();
    choix.caracs = [];
    $("b-choix-titre").textContent = NOMS[emplacement] + (variante ? " · variante" : "");
    $("f-texte").value = "";
    $("f-min").value = "";
    $("f-max").value = String(etat.niveau);
    $("b-retirer").hidden = !objetCible();
    $("b-retirer").textContent = variante ? "Retirer la variante" : "Retirer l'objet";
    dessinerFm();
    dessinerVariante();
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
    if (choix.variante) {
      const avant = etat.variantes[emplacement];
      if (objet) etat.variantes[emplacement] = { objet, fm: avant && avant.objet.id === objet.id ? avant.fm : {} };
      else delete etat.variantes[emplacement];
      $("b-choix").close();
      changement();
      return;
    }
    const avant = etat.objets[emplacement];
    if (!objet || !avant || avant.id !== objet.id) delete etat.fm[emplacement]; // nouvel objet : jets par défaut
    if (objet) etat.objets[emplacement] = objet; else delete etat.objets[emplacement];
    $("b-choix").close();
    changement();
  }

  // --- Forgemagie de l'objet porté --------------------------------------------------------------------------------

  function regler(emplacement, eid, valeur, defaut) {
    const fm = { ...fmCible() };
    if (valeur === null || valeur === defaut) delete fm[eid]; else fm[eid] = valeur;
    if (choix.variante) etat.variantes[emplacement].fm = fm;
    else if (Object.keys(fm).length) etat.fm[emplacement] = fm; else delete etat.fm[emplacement];
    changement();
    dessinerFm();
  }

  // --- Variantes (Duffus : un second objet par emplacement, à échanger avec l'objet porté) -----------------------

  function dessinerVariante() {
    const e = choix.emplacement, zone = $("b-variante");
    zone.replaceChildren();
    if (choix.variante) {
      const retour = el("button", { type: "button", classe: "b-bouton", texte: "Revenir à l'objet porté" });
      retour.addEventListener("click", () => ouvrirChoix(e, false));
      zone.append(retour);
      return;
    }
    const v = etat.variantes[e], o = etat.objets[e];
    zone.append(el("h3", { classe: "b-surtitre", texte: "Variante" }));
    if (v) {
      zone.append(el("p", { classe: "b-objet-nom", texte: v.objet.nom + " (niv. " + v.objet.niveau + ")" }));
      const ecart = ecartCaracs(o ? o.caracs : [], v.objet.caracs);
      zone.append(el("p", { classe: "b-aide", texte: ecart.length ? "Si tu la portes : " + ecart.map(([c, d]) => signe(d) + " " + c).join(" · ") : "Même caractéristiques que l'objet porté." }));
    }
    const choisir = el("button", { type: "button", classe: "b-bouton", texte: v ? "Changer la variante" : "Choisir une variante" });
    choisir.addEventListener("click", () => ouvrirChoix(e, true));
    zone.append(choisir);
    if (v) {
      const echanger = el("button", { type: "button", classe: "b-bouton b-bouton-or", texte: "Échanger avec l'objet porté" });
      echanger.addEventListener("click", () => {
        const porte = etat.objets[e] ? { objet: etat.objets[e], fm: etat.fm[e] || {} } : null;
        etat.objets[e] = v.objet;
        if (Object.keys(v.fm || {}).length) etat.fm[e] = v.fm; else delete etat.fm[e];
        if (porte) etat.variantes[e] = porte; else delete etat.variantes[e];
        $("b-choix").close();
        changement();
      });
      zone.append(echanger);
    }
  }

  // Écart objet par objet (sans panoplie ni forgemagie), comme le badge de Duffus.
  function ecartCaracs(porte, variante) {
    const d = {};
    for (const [c, v] of variante || []) d[c] = (d[c] || 0) + v;
    for (const [c, v] of porte || []) d[c] = (d[c] || 0) - v;
    return config.caracs.filter((c) => d[c]).map((c) => [c, d[c]]);
  }

  function dessinerFm() {
    const e = choix.emplacement, o = objetCible();
    const zone = $("b-fm");
    zone.hidden = !o || !o.effets;
    if (zone.hidden) return;
    const lignes = $("b-fm-lignes");
    lignes.replaceChildren();
    const fm = fmCible();
    const surObjet = new Set();
    const ligne = (eid, carac, valeur, defaut, exo) => {
      const champ = el("input", { type: "number", inputmode: "numeric", value: String(valeur), "aria-label": carac + (exo ? " (exo)" : "") });
      champ.addEventListener("change", () => regler(e, String(eid), parseInt(champ.value, 10) || 0, defaut));
      const effacer = el("button", { type: "button", classe: "b-fermer", "aria-label": exo ? "Retirer l'exo " + carac : "Jet maximal pour " + carac, texte: exo ? "×" : "↺" });
      effacer.addEventListener("click", () => regler(e, String(eid), null, defaut));
      lignes.append(el("div", { classe: "b-fm-ligne" + (exo ? " exo" : "") }, [el("span", { texte: carac }), champ, effacer]));
    };
    for (const [eid, , , carac, defaut] of o.effets) {
      surObjet.add(String(eid));
      ligne(eid, carac, String(eid) in fm ? fm[eid] : defaut, defaut, false);
    }
    const nomDe = Object.fromEntries(Object.entries(config.effet_positif).map(([c, id]) => [String(id), c]));
    for (const [eid, v] of Object.entries(fm)) if (!surObjet.has(eid)) ligne(eid, nomDe[eid] || "Effet " + eid, v, null, true);
  }

  // --- Calcul (serveur : une seule source des formules) -------------------------------------------------------

  let minuteurCalcul = null, numeroCalcul = 0;

  function corpsBuild() {
    const objets = {};
    for (const [e, o] of Object.entries(etat.objets)) if (o) objets[e] = o.id;
    return { niveau: etat.niveau, objets, caracs_base: etat.base, caracs_parcho: etat.parcho,
      mode_arme: etat.modeArme, buff_arme: etat.buffArme, fm: etat.fm,
      variantes: Object.fromEntries(Object.entries(etat.variantes).map(([e, v]) => [e, { id: v.objet.id, fm: v.fm || {} }])) };
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
      for (const [e, o] of Object.entries(d.variantes || {})) if (etat.variantes[e]) etat.variantes[e].objet = o;
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
    dessinerArme(d.arme);
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

  function jet(j) { return j ? (j[0] === j[1] ? String(j[0]) : j[0] + " à " + j[1]) : "—"; }

  function dessinerArme(a) {
    const zone = $("b-arme");
    zone.replaceChildren();
    for (const b of document.querySelectorAll("[data-mode]")) b.setAttribute("aria-pressed", String(b.dataset.mode === etat.modeArme));
    for (const b of document.querySelectorAll("[data-buff]")) b.setAttribute("aria-pressed", String(b.dataset.buff === etat.buffArme));
    if (!a) { zone.append(el("p", { classe: "b-vide", texte: "Aucune arme équipée." })); return; }
    zone.append(el("p", { classe: "b-arme-meta", texte: a.pa + " PA · PO " + a.po[0] + "–" + a.po[1] + " · critique " +
      a.cc + " % (+" + a.bonus_cc + ") · " + a.lancers + " par tour · taux de critique " + a.taux_critique + " %" }));
    const corps = el("tbody");
    for (const l of a.lignes) {
      corps.append(el("tr", {}, [el("th", { scope: "row", texte: l.libelle }), el("td", { texte: jet(l.normal) }), el("td", { texte: jet(l.critique) })]));
    }
    corps.append(el("tr", {}, [el("th", { scope: "row", texte: "Total dégâts" }), el("td", { texte: jet(a.degats) }), el("td", { texte: a.cc ? jet(a.degats_critique) : "—" })]));
    if (a.vol) corps.append(el("tr", {}, [el("th", { scope: "row", texte: "Vol de vie (moitié des dégâts volés)" }), el("td", { texte: jet(a.vol) }), el("td", { texte: jet(a.vol_critique) })]));
    if (a.soins[0] || a.soins[1]) corps.append(el("tr", {}, [el("th", { scope: "row", texte: "Soins" }), el("td", { texte: jet(a.soins) }), el("td", { texte: a.cc ? jet(a.soins_critique) : "—" })]));
    zone.append(el("div", { classe: "b-base-defile" }, [el("table", { classe: "b-comparaison" }, [
      el("thead", {}, [el("tr", {}, [el("th", { scope: "col", texte: "Ligne" }), el("th", { scope: "col", texte: "Normal" }), el("th", { scope: "col", texte: "Critique" })])]), corps])]));
    const tuile = (v, nom) => el("div", { classe: "b-bulle" }, [el("strong", { texte: v === null ? "—" : String(v).replace(".", ",") }), el("span", { texte: nom })]);
    zone.append(el("div", { classe: "b-arme-resume" }, [tuile(a.par_coup, "par coup"), tuile(a.par_tour, "par tour"), tuile(a.par_pa, "par PA")]));
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

  // --- Sorts (chargés seulement quand la section est ouverte) ---------------------------------------------------

  let numeroSorts = 0;

  async function chargerSorts() {
    const zone = $("b-sorts");
    if (!$("b-sorts-zone").open) return;
    const numero = ++numeroSorts;
    try {
      const r = await fetch("/api/builder/sorts", {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ ...corpsBuild(), classe: etat.classe }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.message || "Erreur");
      if (numero !== numeroSorts) return;
      zone.replaceChildren();
      if (!d.sorts.length) zone.append(el("li", { classe: "b-vide", texte: "Aucun sort de dégâts connu pour cette classe à ce niveau." }));
      const texte = (ls) => ls.map((l) => l.libelle + " " + jet(l.jet)).join(" · ");
      for (const s of d.sorts) {
        zone.append(el("li", { classe: "b-sort" }, [
          s.icone ? el("img", { src: s.icone, alt: "", loading: "lazy" }) : el("span"),
          el("div", {}, [
            el("p", {}, [el("span", { classe: "b-objet-nom", texte: s.nom }), " ",
              el("span", { classe: "b-objet-meta", texte: "grade " + s.grade + " · " + s.pa + " PA · PO " + s.po[0] + "–" + s.po[1] +
                (s.cc ? " · critique " + s.taux_critique + " %" : "") })]),
            el("p", { texte: texte(s.normal) || "—" }),
            s.critique.length ? el("p", { texte: "Critique : " + texte(s.critique) }) : null,
          ]),
        ]));
      }
    } catch (err) {
      if (numero === numeroSorts) zone.replaceChildren(el("li", { classe: "b-vide", texte: "Calcul impossible : " + err.message }));
    }
  }

  // --- Navigateur de panoplies ---------------------------------------------------------------------------------

  const panos = { decalage: 0, total: 0, requete: 0, minuteur: null };

  function ouvrirPanos() {
    $("p-max").value = String(etat.niveau);
    $("b-pano").hidden = true;
    $("b-panos-filtres").hidden = false;
    $("b-panos-liste").hidden = false;
    $("b-panos").showModal();
    chercherPanos(true);
  }

  async function chercherPanos(depuisDebut) {
    if (depuisDebut) panos.decalage = 0;
    const params = new URLSearchParams({ q: $("p-texte").value.trim(), decalage: String(panos.decalage) });
    const min = parseInt($("p-min").value, 10), max = parseInt($("p-max").value, 10);
    if (!isNaN(min)) params.set("niveau_min", String(min));
    if (!isNaN(max)) params.set("niveau_max", String(max));
    if ($("p-carac").value) params.set("carac", $("p-carac").value);
    const numero = ++panos.requete;
    const r = await fetch("/api/builder/panoplies?" + params.toString(), { headers: { Accept: "application/json" } });
    const d = await r.json();
    if (numero !== panos.requete) return;
    if (!r.ok) { $("b-panos-compte").textContent = d.message || "Recherche impossible."; return; }
    const ul = $("b-panos-liste");
    if (depuisDebut) ul.replaceChildren();
    for (const p of d.panoplies) {
      const b = el("button", { type: "button", classe: "b-objet b-objet-pano" }, [el("span", {}, [
        el("span", { classe: "b-objet-nom", texte: p.nom }), document.createElement("br"),
        el("span", { classe: "b-objet-meta", texte: "Niv. " + p.niveau + " · " + p.nb_objets + " objets" }), document.createElement("br"),
        el("span", { classe: "b-objet-caracs", texte: p.bonus_complet.slice(0, 6).map(([c, v]) => signe(v) + " " + c).join(" · ") }),
      ])]);
      b.addEventListener("click", () => voirPano(p.id));
      ul.append(el("li", {}, [b]));
    }
    panos.decalage += d.panoplies.length;
    panos.total = d.total;
    $("b-panos-compte").textContent = d.total + " panoplie" + (d.total > 1 ? "s" : "");
    $("b-panos-plus").hidden = panos.decalage >= d.total;
  }

  async function voirPano(id) {
    const r = await fetch("/api/builder/panoplies/" + id, { headers: { Accept: "application/json" } });
    if (!r.ok) return;
    const p = await r.json();
    const zone = $("b-pano");
    zone.replaceChildren();
    const retour = el("button", { type: "button", classe: "b-bouton", texte: "← Toutes les panoplies" });
    retour.addEventListener("click", () => {
      zone.hidden = true; $("b-panos-filtres").hidden = false; $("b-panos-liste").hidden = false;
      $("b-panos-plus").hidden = panos.decalage >= panos.total;
    });
    zone.append(retour, el("h3", { texte: p.nom + " · niv. " + p.niveau }));
    const objets = el("ul", { classe: "b-resultats" });
    for (const o of p.objets) {
      objets.append(el("li", {}, [el("div", { classe: "b-objet" }, [
        o.icone ? el("img", { src: o.icone, alt: "", loading: "lazy" }) : el("span"),
        el("span", {}, [el("span", { classe: "b-objet-nom", texte: o.nom }), document.createElement("br"),
          el("span", { classe: "b-objet-meta", texte: "Niv. " + o.niveau + (o.emplacement ? " · " + NOMS[o.emplacement] : " · non placé") })]),
      ])]));
    }
    zone.append(objets);
    const bonus = el("ul", { classe: "b-pano-bonus" });
    for (const [n, caracs] of p.bonus) {
      bonus.append(el("li", {}, [el("b", { texte: n + " objets : " }), caracs.map(([c, v]) => signe(v) + " " + c).join(" · ")]));
    }
    zone.append(el("h3", { classe: "b-surtitre", texte: "Bonus" }), bonus);
    if (modifiable) {
      const equiper = el("button", { type: "button", classe: "b-bouton b-bouton-or", texte: "Équiper toute la panoplie" });
      equiper.addEventListener("click", () => {
        for (const o of p.objets) {
          if (!o.emplacement) continue;
          if (!etat.objets[o.emplacement] || etat.objets[o.emplacement].id !== o.id) delete etat.fm[o.emplacement];
          etat.objets[o.emplacement] = o;
        }
        $("b-panos").close();
        changement();
      });
      zone.append(el("div", { classe: "b-pano-actions" }, [equiper]));
    }
    $("b-panos-filtres").hidden = true;
    $("b-panos-liste").hidden = true;
    $("b-panos-plus").hidden = true;
    zone.hidden = false;
  }

  // --- Cycle de mise à jour -----------------------------------------------------------------------------------

  const extensions = []; // fonctions appelées à chaque changement (sauvegarde…)

  function changement() {
    dessinerEmplacements(etat.resultat && etat.resultat.alertes);
    clearTimeout(minuteurCalcul);
    minuteurCalcul = setTimeout(() => { calculer(); chargerSorts(); }, 150);
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
    for (const c of config.caracs) $("b-fm-carac").append(el("option", { value: String(config.effet_positif[c]), texte: c }));
    $("b-fm-ajouter").addEventListener("click", () => {
      const v = parseInt($("b-fm-valeur").value, 10) || 0;
      if (v) regler(choix.emplacement, $("b-fm-carac").value, v, null);
    });
    $("b-retirer").addEventListener("click", () => equiper(choix.emplacement, null));
    $("b-choix").addEventListener("click", (ev) => { if (ev.target === $("b-choix")) $("b-choix").close(); });
    $("b-detail").addEventListener("click", (ev) => { if (ev.target === $("b-detail")) $("b-detail").close(); });
    for (const b of document.querySelectorAll("[data-mode]")) b.addEventListener("click", () => { etat.modeArme = b.dataset.mode; changement(); });
    for (const b of document.querySelectorAll("[data-buff]")) b.addEventListener("click", () => {
      etat.buffArme = etat.buffArme === b.dataset.buff ? "" : b.dataset.buff;
      changement();
    });
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
    etat.base = { ...b.caracs_base }; etat.parcho = { ...b.caracs_parcho }; etat.fm = JSON.parse(JSON.stringify(b.fm || {}));
    for (const [e, v] of Object.entries(b.variantes || {})) {
      etat.variantes[e] = { objet: { id: v.id, nom: "…", niveau: 0, icone: null, caracs: [] }, fm: { ...(v.fm || {}) } };
    }
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
  for (const c of config.caracs) $("p-carac").append(el("option", { value: c, texte: c }));
  $("b-panos-ouvrir").addEventListener("click", ouvrirPanos);
  $("b-panos-plus").addEventListener("click", () => chercherPanos(false));
  for (const id of ["p-texte", "p-min", "p-max"]) $(id).addEventListener("input", () => {
    clearTimeout(panos.minuteur);
    panos.minuteur = setTimeout(() => chercherPanos(true), 250);
  });
  $("p-carac").addEventListener("change", () => chercherPanos(true));
  $("b-panos").addEventListener("click", (ev) => { if (ev.target === $("b-panos")) $("b-panos").close(); });
  $("b-sorts-zone").addEventListener("toggle", chargerSorts);
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
