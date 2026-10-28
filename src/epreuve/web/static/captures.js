/* L'Épreuve des Dieux · module E1 (archimonstres, boss, avis de recherche).
   Tout marche sans JavaScript (formulaires et liens) ; ce script ajoute :
   - le filtre en direct (recherche sans accents, état, exemplaires, milice, Émeraude) ;
   - le compteur −/+ et la case « capturé » sans rechargement (API JSON, en-tête X-CSRF-Token) ;
   - le recalcul des compteurs (barre, volets, pierres d'âme, récompenses restantes) ;
   - « Qui l'a ? » dans le panneau latéral du site (#qd).
   Aucune donnée n'est insérée avec innerHTML : uniquement textContent et createElement. */
(() => {
"use strict";
const csrf = (document.querySelector('meta[name="csrf"]') || {}).content || "";
const filtres = document.getElementById("cpFiltres");
if (!document.querySelector("main.cp")) return;
document.body.classList.add("cp-js");

const norm = t => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const cartes = () => [...document.querySelectorAll(".cp-carte")];
const persos = () => Number(document.querySelector("[data-pierres]")?.dataset.personnages || 1);
const estAvis = () => !!filtres?.dataset.avis;

function message(t){
  const m = document.getElementById("messageCoche"); if (!m) return;
  m.textContent = t; m.hidden = false; clearTimeout(message.t); message.t = setTimeout(() => { m.hidden = true; }, 4000);
}
function cran(faits, total){ return total > 0 ? Math.min(100, Math.max(0, Math.round(faits / total * 20) * 5)) : 0; }
function poserCran(el, p){
  if (!el) return;
  [...el.classList].filter(c => /^p-\d+$/.test(c)).forEach(c => el.classList.remove(c));
  el.classList.add("p-" + p);
}

/* =================== Filtre en direct =================== */
function valeur(sel){ const el = filtres?.querySelector(sel); return el ? el.value : ""; }
function etat(){ return filtres?.querySelector('[data-filtre-etat] input:checked')?.value || "tous"; }
function filtrer(){
  if (!filtres) return;
  const q = norm(valeur("[data-filtre-q]")), et = etat(), min = Number(valeur("[data-filtre-min]") || 0);
  const milice = valeur("[data-filtre-milice]"), emeraude = !!filtres.querySelector("[data-filtre-emeraude]")?.checked;
  const vus = new Set();
  cartes().forEach(c => {
    const n = Number(c.dataset.nombre || 0);
    let voir = !q || c.dataset.nom.includes(q) || (c.dataset.zones || "").includes(q);
    if (et === "captures" && n === 0) voir = false;
    if (et === "manquants" && n > 0) voir = false;
    if (min && n < min) voir = false;
    if (milice && c.dataset.milice !== milice) voir = false;
    if (emeraude && Number(c.dataset.niveau || 0) > 120) voir = false;
    c.hidden = !voir;
    if (voir) vus.add(c.dataset.id);
  });
  document.querySelectorAll("details[data-groupe]").forEach(g => { g.hidden = !g.querySelector(".cp-carte:not([hidden])"); });
  const aff = document.querySelector("[data-affiches]"); if (aff) aff.textContent = String(vus.size);
  const vide = document.querySelector("[data-vide]"); if (vide) vide.hidden = vus.size > 0;
  // L'adresse suit le filtre : un rechargement ou un lien partagé retrouve la même vue.
  const p = new URLSearchParams(location.search);
  const poser = (k, v) => { if (v) p.set(k, v); else p.delete(k); };
  poser("q", valeur("[data-filtre-q]").trim()); poser("etat", et === "tous" ? "" : et);
  if (filtres.querySelector("[data-filtre-min]")) poser("min", min ? String(min) : "");
  if (filtres.querySelector("[data-filtre-milice]")) poser("milice", milice);
  if (filtres.querySelector("[data-filtre-emeraude]")) poser("emeraude", emeraude ? "1" : "");
  p.delete("qui");
  history.replaceState(history.state, "", location.pathname + (p.toString() ? "?" + p : "") + location.hash);
  const retour = p.toString();
  document.querySelectorAll('input[name="retour"]').forEach(i => { i.value = retour; });
}
if (filtres){
  filtres.addEventListener("input", e => { e.stopPropagation(); filtrer(); });
  filtres.addEventListener("change", e => { e.stopPropagation(); filtrer(); });
  filtres.addEventListener("submit", e => { e.preventDefault(); filtrer(); });
}

/* =================== Compteurs =================== */
function recompter(){
  const q = persos(), uniques = new Map();
  cartes().forEach(c => uniques.set(c.dataset.id, c));
  const liste = [...uniques.values()];
  const faits = liste.filter(c => Number(c.dataset.nombre || 0) >= (estAvis() ? 1 : q)).length;
  const total = liste.length;
  const t = s => document.querySelector(s);
  if (t("[data-prog-faits]")) t("[data-prog-faits]").textContent = String(faits);
  if (t("[data-prog-pct]")) t("[data-prog-pct]").textContent = String(total ? Math.min(100, Math.round(faits / total * 100)) : 0);
  poserCran(t("[data-prog-barre]"), cran(faits, total));
  t(".cp-barre")?.setAttribute("aria-valuenow", String(faits));
  document.querySelectorAll("details[data-groupe]").forEach(g => {
    const ids = new Map(); g.querySelectorAll(".cp-carte").forEach(c => ids.set(c.dataset.id, c));
    const f = [...ids.values()].filter(c => Number(c.dataset.nombre || 0) >= q).length;
    const el = g.querySelector(":scope > summary [data-compte]"); if (el) el.textContent = `${f} / ${ids.size}`;
  });
  // Pierres d'âme : par personnage, la plus petite pierre qui capture jusqu'au niveau maximum.
  const pierres = [...document.querySelectorAll("[data-pierre]")];
  if (pierres.length){
    const besoin = new Map(pierres.map(p => [p, 0]));
    liste.forEach(c => {
      if (!c.dataset.niveau) return;
      const niv = Number(c.dataset.niveau), p = pierres.find(x => niv <= Number(x.dataset.cap));
      if (p) besoin.set(p, besoin.get(p) + Math.max(0, q - Number(c.dataset.nombre || 0)));
    });
    besoin.forEach((n, p) => { const b = p.querySelector("[data-pierre-n]"); if (b) b.textContent = String(n); });
  }
  // Avis : avitons et alitons encore disponibles.
  const reste = {aviton:0, aliton:0};
  liste.forEach(c => { if (c.dataset.type && Number(c.dataset.nombre || 0) === 0) reste[c.dataset.type] += Number(c.dataset.recompense || 0); });
  document.querySelectorAll("[data-reste]").forEach(el => { el.textContent = reste[el.dataset.reste].toLocaleString("fr-FR"); });
}

function majCarte(id, n){
  const q = estAvis() ? 1 : persos();
  document.querySelectorAll(`.cp-carte[data-id="${CSS.escape(String(id))}"]`).forEach(c => {
    c.dataset.nombre = String(n);
    c.classList.toggle("complet", n >= q); c.classList.toggle("entame", n > 0 && n < q);
    const out = c.querySelector("[data-nombre]"); if (out) out.textContent = String(n);
    const moins = c.querySelector('button[name="delta"][value="-1"]'); if (moins) moins.disabled = n === 0;
    const et = c.querySelector(".cp-etat[data-etat]"); if (et) et.textContent = n >= q ? "✓ Complet" : n > 0 ? "Capturé" : "Manquant";
  });
}

async function appeler(url, corps){
  const r = await fetch(url, {method:"POST", credentials:"same-origin",
    headers:{"Content-Type":"application/json", "X-CSRF-Token":csrf}, body:JSON.stringify(corps)});
  let d = {}; try{ d = await r.json(); }catch(e){ /* corps vide */ }
  if (!r.ok || !d.ok) throw new Error(d.message || "Enregistrement impossible, réessaie.");
  return d;
}

document.addEventListener("submit", async e => {
  const f = e.target, b = e.submitter;
  if (!(f instanceof HTMLFormElement) || !("cp" in f.dataset) || !b || !b.name) return;
  e.preventDefault();
  const zone = b.parentElement;
  if (zone.getAttribute("aria-busy") === "true") return;
  zone.setAttribute("aria-busy", "true");
  // L'API a la même adresse que le formulaire, préfixée par /api.
  const api = "/api" + new URL(b.formAction || f.action, location.href).pathname;
  const carte = b.closest(".cp-carte");
  try{
    if (b.name === "delta"){
      const d = await appeler(api, {delta:Number(b.value)});
      majCarte(carte.dataset.id, d.nombre);
    } else if (b.name === "capture"){
      const d = await appeler(api, {capture:b.value === "1"});
      b.value = d.capture ? "0" : "1"; b.setAttribute("aria-pressed", d.capture ? "true" : "false");
      const et = b.querySelector("[data-etat]"); if (et) et.textContent = d.capture ? "Capturé" : "Pas capturé";
      if (carte) majCarte(carte.dataset.id, d.capture ? 1 : 0);
    }
    recompter(); filtrer();
  }catch(err){ message(err.message); }
  finally{ zone.removeAttribute("aria-busy"); }
});

/* =================== « Qui l'a ? » dans le panneau latéral =================== */
function personne(g, cls, nombre){
  const s = document.createElement("span"); s.className = "person " + cls; s.textContent = g.pseudo;
  if (g.classe){ const c = document.createElement("span"); c.className = "muted"; c.textContent = " " + g.classe; s.append(c); }
  if (nombre && g.nombre > 0){ const n = document.createElement("span"); n.className = "num"; n.textContent = " ×" + g.nombre; s.append(n); }
  return s;
}
function liste(titre, gens, cls, nombre, vide){
  const h = document.createElement("h3"); h.className = "cp-qui-h"; h.textContent = titre + " ";
  const sm = document.createElement("small"); sm.className = "muted"; sm.textContent = String(gens.length); h.append(sm);
  const d = document.createElement("div"); d.className = "people";
  if (gens.length) gens.forEach(g => d.append(personne(g, cls, nombre)));
  else { const p = document.createElement("p"); p.className = "muted"; p.textContent = vide; d.append(p); }
  return [h, d];
}
async function qui(lien){
  const dlg = document.getElementById("qd"), main = lien.closest("[data-genre]"), carte = lien.closest(".cp-carte");
  if (!dlg || typeof dlg.showModal !== "function" || !main || !carte){ location.href = lien.href; return; }
  const genre = main.dataset.genre, id = encodeURIComponent(carte.dataset.id);
  const url = genre === "avis" ? `/api/avis-de-recherche/${id}/qui` : `/api/archimonstres/${encodeURIComponent(genre)}/${id}/qui`;
  const nom = carte.querySelector(".cp-nom")?.textContent || "";
  let d;
  try{
    const r = await fetch(url, {credentials:"same-origin"});
    d = await r.json(); if (!r.ok) throw new Error(d.message || "");
  }catch(e){ location.href = lien.href; return; }
  const wrap = document.createElement("div"); wrap.className = "qd-in";
  const head = document.createElement("header"); head.className = "qd-head";
  const top = document.createElement("div"); top.className = "qd-top";
  const bloc = document.createElement("div");
  const eb = document.createElement("div"); eb.className = "eyebrow"; eb.textContent = "Entraide";
  const h = document.createElement("h2"); h.id = "qdTitle"; h.tabIndex = -1; h.textContent = `Qui a ${nom} ?`;
  bloc.append(eb, h);
  const x = document.createElement("button"); x.type = "button"; x.className = "x"; x.dataset.qclose = ""; x.setAttribute("aria-label", "Fermer"); x.textContent = "×";
  top.append(bloc, x); head.append(top);
  const corps = document.createElement("div"); corps.className = "qd-body cp-qui";
  corps.append(...liste("L'ont déjà", d.ont, "done", "quiNombre" in main.dataset, "Personne pour l'instant."),
               ...liste("Ne l'ont pas encore", d.pas, "miss", false, "Tout le monde l'a."));
  wrap.append(head, corps);
  dlg.replaceChildren(wrap);
  const avant = document.activeElement;
  dlg.addEventListener("close", () => { if (avant && document.contains(avant)) avant.focus({preventScroll:true}); }, {once:true});
  if (!dlg.open) dlg.showModal();
  h.focus();
}
document.addEventListener("click", e => {
  const a = e.target.closest("a[data-qui]");
  if (a && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0){ e.preventDefault(); qui(a); }
});

filtrer();
})();
