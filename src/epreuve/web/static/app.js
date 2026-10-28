/* L'Épreuve des Dieux · le script du site (lot B).
   Tiré de docs/design/maquette-v2.html. Règles :
   - aucune donnée n'est insérée avec innerHTML : uniquement textContent et createElement (pseudos, libellés) ;
     le seul HTML inséré est la fiche de quête rendue et échappée par le serveur (Jinja) ;
   - la CSP interdit les styles en ligne : couleurs et pourcentages passent par des classes (c-…, p-…) ;
   - tout marche sans JavaScript (formulaires, liens) ; le script ajoute la coche sans rechargement,
     le filtre mémorisé, le panneau de la fiche de quête et le décor animé. */
(() => {
"use strict";
const $ = id => document.getElementById(id);
const reduit = matchMedia("(prefers-reduced-motion: reduce)").matches;
const CATS = ["donjons", "full_succes", "principales", "secondaires"];
const csrf = (document.querySelector('meta[name="csrf"]') || {}).content || "";

/* Classe « p-45 » (par pas de 5 %) pour une barre ou un anneau. */
function pct(el, faits, total){
  if (!el) return;
  [...el.classList].filter(c => /^p-\d+$/.test(c)).forEach(c => el.classList.remove(c));
  const p = total > 0 ? Math.min(100, Math.max(0, Math.round(faits / total * 20) * 5)) : 0;
  el.classList.add("p-" + p);
}
function texte(el, t){ if (el) el.textContent = t; }

/* =================== Heure de Paris (en-tête) =================== */
function horloge(){
  const ouverture = Date.parse(document.body.dataset.ouverture || "");
  if (!$("clock") || isNaN(ouverture)) return;
  const ms = ouverture - Date.now();
  if (ms <= 0){
    texte($("clockLabel"), "L'ascension a commencé");
    texte($("clock"), `Jour ${Math.floor(-ms / 864e5) + 1}`);
    texte($("clockSub"), "depuis le vendredi 13 novembre, 17 h 00");
    return;
  }
  const s = Math.floor(ms / 1000), d2 = n => String(n).padStart(2, "0");
  texte($("clockLabel"), "Les portes s'ouvrent dans");
  texte($("clock"), `${Math.floor(s / 86400)} j ${d2(Math.floor(s / 3600) % 24)} h ${d2(Math.floor(s / 60) % 60)} min ${d2(s % 60)} s`);
  texte($("clockSub"), "vendredi 13 novembre · 17 h 00, heure de Paris");
}

/* =================== Message d'échec =================== */
let minuteur;
function message(t){
  const el = $("messageCoche"); if (!el) return;
  el.textContent = t; el.hidden = false;
  clearTimeout(minuteur); minuteur = setTimeout(() => { el.hidden = true; }, 4000);
}

/* =================== Jauge, catégories, compteurs =================== */
function majJauge(j){
  const g = $("jauge"); if (!g || !j) return;
  g.classList.toggle("ok", j.pleine);
  texte(g.querySelector('[data-j="score"]'), String(j.score));
  const manque = Math.max(0, j.palier - j.score), m = g.querySelector('[data-j="manque"]');
  if (m){
    m.textContent = "";
    const b = document.createElement("b");
    if (j.pleine){ b.textContent = "Palier atteint"; m.append(b); }
    else { b.className = "num"; b.textContent = String(manque); m.append("Il manque ", b, ` point${manque > 1 ? "s" : ""}`); }
  }
  const actifs = `${j.actifs} grimpeur${j.actifs > 1 ? "s" : ""} actif${j.actifs > 1 ? "s" : ""}`;
  const pause = j.en_pause ? `, ${j.en_pause} en pause` : "";
  texte(g.querySelector('[data-j="texte"]'), (j.pleine
    ? `Score ${j.score} sur un palier de ${j.palier} : la jauge est pleine.`
    : `Score ${j.score} sur un palier de ${j.palier}, il en manque ${manque}.`) + ` ${actifs}${pause}.`);
  // Les encoches : une par point requis, dans l'ordre des catégories.
  const enc = $("encoches");
  if (enc){
    const pleines = []; CATS.forEach(c => { for (let i = 0; i < (j.points_par_categorie[c] || 0); i++) pleines.push(c); });
    const n = Math.max(j.palier, j.score); enc.textContent = "";
    for (let i = 0; i < n; i++){
      const e = document.createElement("i");
      if (i < pleines.length){ e.className = "c-" + pleines[i] + (i >= j.palier ? " over" : ""); e.dataset.c = ""; }
      else e.className = "vide";
      enc.append(e);
    }
    enc.setAttribute("aria-label", `${j.score} points sur ${j.palier} requis`);
  }
  CATS.forEach(c => {
    texte(document.querySelector(`[data-jcat="${c}"]`), String(j.points_par_categorie[c] || 0));
    pct(document.querySelector(`[data-jmini="${c}"]`), j.points_par_categorie[c] || 0, j.actifs);
  });
  const v = $("verdict");
  if (v){ v.classList.toggle("open", j.pleine); v.textContent = j.pleine ? v.dataset.plein : v.dataset.pasPlein; }
}
const NOMS = {donjons:"Donjons", full_succes:"Full succès", principales:"Quêtes principales", secondaires:"Quêtes secondaires"};
function majMoi(moi){
  const zone = $("maProgression"); if (!zone || !moi) return;
  texte(zone.querySelector('[data-moi="points"]'), String(moi.points));
  CATS.forEach(c => {
    const e = moi.categories[c]; if (!e) return;
    texte(zone.querySelector(`[data-moi-cat="${c}"]`), `${e.faits}/${e.total}${e.acquise ? " ✓" : ""}`);
    const p = zone.querySelector(`[data-pip="${c}"]`);
    if (p){ pct(p, e.faits, e.total); p.classList.toggle("got", e.acquise);
      const lab = `${NOMS[c]} : ${e.acquise ? "point obtenu" : `${e.faits} sur ${e.total}`}`;
      p.setAttribute("aria-label", lab); p.title = lab; }
  });
}
function majCompteurs(compteurs){
  Object.entries(compteurs || {}).forEach(([cle, n]) => {
    document.querySelectorAll(`[data-compteur="${cle}"]`).forEach(a => {
      a.textContent = `${n}/${a.textContent.split("/")[1]}`;
    });
  });
}
/* L'état d'une ligne de donjon (badges « Donjon » et « Full succès », compte x/5) et data-fait des lignes. */
function majLignes(){
  document.querySelectorAll("li[data-donjon]").forEach(li => {
    const boxes = [...li.querySelectorAll("input[data-ref]")];
    const faits = boxes.filter(b => b.checked).length, classique = boxes[0];
    texte(li.querySelector("[data-djcompte]"), String(faits));
    const tout = boxes.length > 0 && faits === boxes.length;
    li.querySelector('[data-djbadge="donjon"]')?.classList.toggle("on", !!(classique && classique.checked));
    li.querySelector('[data-djbadge="succes"]')?.classList.toggle("on", tout);
    li.dataset.fait = tout ? "1" : "0"; li.dataset.vaincu = classique && classique.checked ? "1" : "0";
  });
  document.querySelectorAll("li[data-cats] input[data-ref^='quete:']").forEach(b => { b.closest("li").dataset.fait = b.checked ? "1" : "0"; });
  filtrer();
}

/* =================== Cocher =================== */
const enCours = new Set();
function boites(ref){ return [...document.querySelectorAll(`input[data-ref="${ref}"]`)]; }
function remettre(refs, etats){ refs.forEach((r, i) => boites(r).forEach(b => { b.checked = etats[i]; })); }
async function envoyer(corps, refs, avant){
  const cible = document.querySelector("[data-cible]");
  if (cible){
    corps.grimpeur_id = Number(cible.dataset.cible);
    corps.motif = ($("motif") || {}).value || "";
    if (!corps.motif.trim()){ remettre(refs, avant); message("Indique d'abord un motif."); $("motif")?.focus(); return null; }
  }
  try{
    const r = await fetch("/api/coches", {method:"POST", credentials:"same-origin",
      headers:{"Content-Type":"application/json", "X-CSRF-Token":csrf}, body:JSON.stringify(corps)});
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.ok){ remettre(refs, avant); message(d.message || "Pas enregistré, réessaie."); return null; }
    return d;
  }catch(e){ remettre(refs, avant); message("Pas enregistré, réessaie."); return null; }
}
function appliquer(d){ majCompteurs(d.compteurs); majJauge(d.jauge); majMoi(d.moi); majLignes(); }
async function cocher(box){
  const ref = box.dataset.ref;
  if (enCours.has(ref)){ box.checked = !box.checked; return; }   // double toucher : on attend la réponse
  const [type, id] = ref.split(":"), cochee = box.checked;
  enCours.add(ref); boites(ref).forEach(b => { b.checked = cochee; b.disabled = true; });
  const d = await envoyer({type, id:Number(id), cochee}, [ref], [!cochee]);
  boites(ref).forEach(b => { b.disabled = false; });
  enCours.delete(ref);
  if (!d) return;
  // La cascade (T-16) : les éléments changés en plus prennent le même état.
  Object.keys(d.compteurs || {}).forEach(k => boites(k).forEach(b => { b.checked = cochee; }));
  appliquer(d);
}
async function toutLeDonjon(btn){
  const li = btn.closest("li[data-donjon]"), refs = [...li.querySelectorAll("input[data-ref]")].map(b => b.dataset.ref);
  if (btn.disabled) return; btn.disabled = true;
  const avant = refs.map(r => !!boites(r)[0]?.checked);
  refs.forEach(r => boites(r).forEach(b => { b.checked = true; }));
  const d = await envoyer({type:"donjon", id:Number(li.dataset.donjon), cochee:true}, refs, avant);
  btn.disabled = false;
  if (d) appliquer(d);
}
document.addEventListener("change", e => {
  const box = e.target.closest("input[data-ref]"); if (box) cocher(box);
});

/* =================== Filtre cumulatif (mémorisé sur l'appareil) =================== */
const CLE_FILTRE = "epreuve-filtre";
function lireFiltre(){ try{ return JSON.parse(localStorage.getItem(CLE_FILTRE)) || null; }catch(e){ return null; } }
function filtrer(){
  const f = $("filtre"); if (!f) return;
  const choix = [...f.querySelectorAll("input")].filter(i => i.checked).map(i => i.value);
  const reste = choix.includes("reste"), cats = choix.filter(c => c !== "reste");
  const seulSucces = cats.length === 1 && cats[0] === "full_succes";
  document.querySelectorAll("#liste li[data-cats]").forEach(li => {
    let voir = li.dataset.cats.split(" ").some(c => cats.includes(c));
    if (voir && reste){
      if (li.dataset.donjon && !cats.includes("full_succes")) voir = li.dataset.vaincu !== "1";
      else voir = li.dataset.fait !== "1";
    }
    li.hidden = !voir;
    const det = li.querySelector("details"); if (det && seulSucces) det.open = true;
  });
  document.querySelectorAll("#liste .bloc").forEach(b => { b.hidden = !b.querySelector("li[data-cats]:not([hidden])"); });
}
function initFiltre(){
  const f = $("filtre"); if (!f) return;
  const memo = lireFiltre();
  if (Array.isArray(memo)) f.querySelectorAll("input").forEach(i => { i.checked = memo.includes(i.value); });
  f.addEventListener("change", e => {
    e.stopPropagation();
    try{ localStorage.setItem(CLE_FILTRE, JSON.stringify([...f.querySelectorAll("input")].filter(i => i.checked).map(i => i.value))); }catch(err){ /* stockage indisponible : le filtre marche quand même */ }
    filtrer();
  });
  filtrer();
}

/* =================== Fiche de quête : panneau (dialog) =================== */
let declencheur = null, pousse = false;
async function ouvrirQuete(href, depuis){
  const dlg = $("qd"); if (!dlg){ location.href = href; return; }
  try{
    const r = await fetch(href, {headers:{"Accept":"text/html-fragment"}, credentials:"same-origin"});
    if (!r.ok) throw new Error(String(r.status));
    const t = document.createElement("template");
    t.innerHTML = await r.text();   // HTML rendu et échappé par le serveur (Jinja), pas une donnée brute
    dlg.replaceChildren(t.content);
  }catch(e){ location.href = href; return; }
  if (!dlg.open){
    declencheur = depuis || document.activeElement;
    dlg.showModal();
    history.pushState({quete:href}, "", href); pousse = true;
  } else {
    history.replaceState({quete:href}, "", href);
  }
  dlg.scrollTop = 0;
  $("qdTitle")?.focus();
}
function initQuete(){
  const dlg = $("qd"); if (!dlg) return;
  dlg.addEventListener("close", () => {
    if (pousse){ pousse = false; history.back(); }   // l'adresse de la liste revient, sa position de défilement aussi
    const id = declencheur && declencheur.dataset ? declencheur.dataset.qopen : null;
    const t = declencheur && document.contains(declencheur) ? declencheur
      : (id ? document.querySelector(`#liste [data-qopen="${id}"]`) : null);
    declencheur = null;
    if (t) t.focus({preventScroll:true});
  });
  dlg.addEventListener("click", e => {
    if (e.target === dlg || e.target.closest("[data-qclose]")) dlg.close();   // clic sur le fond, la croix ou « Retour »
  });
  addEventListener("popstate", () => { if (dlg.open){ pousse = false; dlg.close(); } });   // bouton retour du téléphone
}

/* =================== « Qui n'a pas fait… ? » (page des grimpeurs) =================== */
function puce(g, cls){
  const s = document.createElement("span"); s.className = "person " + cls; s.textContent = g.pseudo;
  if (g.classe){ const c = document.createElement("span"); c.className = "muted"; c.textContent = " " + g.classe; s.append(c); }
  return s;
}
function titre(t, petit){
  const h = document.createElement("h3"); h.textContent = t + " ";
  const s = document.createElement("small"); s.textContent = petit; h.append(s); return h;
}
async function demander(quoi){
  const form = $("ask"), ans = $("answer"); if (!form || !ans) return;
  const roster = [...document.querySelectorAll("#roster .player")];
  roster.forEach(p => p.classList.remove("target", "dim"));
  history.replaceState(null, "", quoi ? `/grimpeurs?quoi=${encodeURIComponent(quoi)}` : "/grimpeurs");
  ans.textContent = "";
  if (!quoi){ const p = document.createElement("p"); p.className = "muted"; p.textContent = "Choisis un objectif pour voir qui l'a fait et qui ne l'a pas encore fait."; ans.append(p); return; }
  const [type, id] = quoi.split(":");
  try{
    const r = await fetch(`/api/etages/${encodeURIComponent(form.dataset.etage)}/manque?type=${encodeURIComponent(type)}&id=${encodeURIComponent(id)}`, {credentials:"same-origin"});
    const d = await r.json(); if (!r.ok) throw new Error(d.message || "");
    const libelle = $("askSel").selectedOptions[0]?.textContent || "";
    const l1 = document.createElement("div"); l1.className = "people"; d.pas_fait.forEach(g => l1.append(puce(g, "miss")));
    if (!d.pas_fait.length) l1.textContent = "Tout le monde l'a fait.";
    const l2 = document.createElement("div"); l2.className = "people"; d.fait.forEach(g => l2.append(puce(g, "done")));
    if (!d.fait.length) l2.textContent = "Personne pour l'instant.";
    ans.append(titre("Qui ne l'a pas fait", `${d.pas_fait.length} sur ${d.pas_fait.length + d.fait.length} · ${libelle}`), l1,
               titre("Qui l'a fait (peut accompagner)", String(d.fait.length)), l2);
    const manque = new Set(d.pas_fait.map(g => g.id)), fait = new Set(d.fait.map(g => g.id));
    roster.forEach(p => { const n = Number(p.dataset.gid);
      if (manque.has(n)) p.classList.add("target"); else if (fait.has(n)) p.classList.add("dim"); });
  }catch(e){ const p = document.createElement("p"); p.className = "alerte"; p.textContent = "Réponse indisponible, réessaie."; ans.append(p); }
}
function initAsk(){
  const sel = $("askSel"); if (!sel) return;
  sel.addEventListener("change", e => { e.stopPropagation(); demander(sel.value); });
  $("askVoir")?.setAttribute("hidden", "");
}

/* =================== Clics =================== */
document.addEventListener("click", e => {
  const qo = e.target.closest("a[data-qopen]");
  if (qo && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0){
    e.preventDefault(); ouvrirQuete(qo.getAttribute("href"), $("qd")?.open ? null : qo); return;
  }
  const tout = e.target.closest("[data-donjon-tout]");
  if (tout){ toutLeDonjon(tout); return; }
  const cp = e.target.closest("[data-copier]");
  if (cp){
    const t = cp.dataset.copier, avant = cp.textContent;
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject(new Error("presse-papiers"))).then(
      () => { cp.textContent = "Copié"; setTimeout(() => { cp.textContent = avant; }, 1500); },
      () => message(t));
  }
});

/* =================== Décor : étoiles, poussières, image d'ambiance =================== */
function ambiance(url){
  if (!url || !$("ambiance") || !/^(https:\/\/|\/etages\/\d+\/image$)/.test(url)) return;
  const img = new Image(); img.decoding = "async";
  img.onload = () => { $("ambiance").style.backgroundImage = `url("${encodeURI(url).replace(/"/g, "%22")}")`; $("ambiance").classList.add("ready"); };
  img.src = url; // en cas d'erreur, rien ne change : le décor généré reste
}
function ciel(){
  const sc = $("stars"), mc = $("motes"); if (!sc || !mc) return;
  const sx = sc.getContext("2d"), mx = mc.getContext("2d");
  const dpr = Math.min(2, devicePixelRatio || 1), al = (a, b) => a + Math.random() * (b - a);
  const sprite = document.createElement("canvas"); sprite.width = sprite.height = 32;
  const g = sprite.getContext("2d"), rg = g.createRadialGradient(16, 16, 0, 16, 16, 16);
  rg.addColorStop(0, "rgba(255,236,190,1)"); rg.addColorStop(.25, "rgba(246,205,120,.5)"); rg.addColorStop(1, "rgba(227,181,82,0)");
  g.fillStyle = rg; g.fillRect(0, 0, 32, 32);
  let W, H, motes = [];
  const neuve = tout => ({x:al(0, W), y:tout ? al(0, H) : H + 10, v:al(5, 12), s:al(2.5, 6), ph:al(0, 6.28), amp:al(6, 18), vie:0, duree:al(10, 22)});
  function taille(){
    W = innerWidth; H = innerHeight;
    for (const c of [sc, mc]){ c.width = W * dpr; c.height = H * dpr; }
    sx.setTransform(dpr, 0, 0, dpr, 0, 0); mx.setTransform(dpr, 0, 0, dpr, 0, 0);
    sx.clearRect(0, 0, W, H);
    for (let i = 0, n = Math.min(260, W * H / 5000); i < n; i++){        // étoiles fixes : dessinées une fois
      const y = Math.pow(Math.random(), 1.5) * H * .85;
      sx.globalAlpha = al(.2, .8) * (1 - y / H * .7); sx.fillStyle = Math.random() < .2 ? "#fff3d6" : "#d8def5";
      sx.beginPath(); sx.arc(al(0, W), y, al(.25, 1.1), 0, 6.283); sx.fill();
    }
    motes = Array.from({length:Math.round(Math.min(24, W * H / 50000))}, () => neuve(true));
  }
  function dessin(t){
    mx.clearRect(0, 0, W, H);
    for (const m of motes){ mx.globalAlpha = Math.sin(Math.min(1, m.vie / m.duree) * Math.PI) * .7; mx.drawImage(sprite, m.x + Math.sin(t / 2600 + m.ph) * m.amp, m.y, m.s, m.s); }
  }
  let prec = 0, actif = !reduit;
  function boucle(t){
    if (!actif) return;
    if (t - prec >= 40){
      const dt = Math.min(.1, (t - (prec || t)) / 1000);
      motes.forEach((m, i) => { m.y -= m.v * dt; m.vie += dt; if (m.vie > m.duree) motes[i] = neuve(false); });
      dessin(t); prec = t;
    }
    requestAnimationFrame(boucle);
  }
  taille(); dessin(0);
  if (!reduit){ requestAnimationFrame(boucle);
    document.addEventListener("visibilitychange", () => { actif = !document.hidden; if (actif){ prec = 0; requestAnimationFrame(boucle); } }); }
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { taille(); dessin(performance.now()); }, 150); });
}

initFiltre();
initQuete();
initAsk();
horloge(); setInterval(horloge, 1000);
ambiance(document.body.dataset.ambiance);
ciel();
})();
