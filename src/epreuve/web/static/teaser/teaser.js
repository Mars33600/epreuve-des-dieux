/* Script du teaser, extrait de docs/design/teaser.html (lot A, ARCHITECTURE §7.3).
   Écarts avec l'original, tous sans effet sur le rendu :
   - OUVERTURE et LIEN_SITE sont lus sur <body data-ouverture data-lien-site>, posés par le gabarit ;
     heureParis() disparaît : la date du serveur porte déjà son décalage ;
   - le rang des gradins (--i) passe par le CSSOM plutôt que par un attribut style (CSP stricte).
   Le reste est inchangé, aperçus de recette compris (?etat=ouvert, ?dans=12). */
(() => {
"use strict";

/* ---------- Réglages ---------- */
// Posés par le serveur sur <body> (SITE_OUVERT_LE et TEASER_LIEN_ENTRER), au lieu d'être écrits ici.
// L'ouverture est une date ISO avec son décalage (« 2026-11-13T17:00:00+01:00 ») : un instant exact.
const OUVERTURE = Date.parse(document.body.dataset.ouverture);
const LIEN_SITE = document.body.dataset.lienSite || "";  // vide : le bouton « Entrer dans la tour » reste masqué
const AMBIANCE = "";        // image d'ambiance optionnelle (URL). Vide = décor généré seul.

const params = new URLSearchParams(location.search);
const reduit = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = id => document.getElementById(id);

/* ---------- Heure de Paris, quel que soit le fuseau du visiteur ---------- */
// Décalage (en minutes) entre l'heure de Paris et UTC à l'instant ts.
function decalageParis(ts){
  try{
    const f = new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Paris",hourCycle:"h23",
      year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"});
    const p = {}; f.formatToParts(new Date(ts)).forEach(x => p[x.type] = x.value);
    return Math.round((Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute, +p.second) - ts) / 60000);
  }catch(e){ return 60; } // repli : heure d'hiver (UTC+1), valable en novembre
}
// La date ISO porte son décalage : Date.parse donne le même instant, quel que soit le fuseau du visiteur.
let CIBLE = OUVERTURE;
if (params.get("etat") === "ouvert") CIBLE = Date.now() - 1000;
if (params.has("dans")) CIBLE = Date.now() + Math.max(1, +params.get("dans") || 10) * 1000;

// Rappel de l'heure locale si le visiteur n'est pas à l'heure de Paris.
if (-new Date(CIBLE).getTimezoneOffset() !== decalageParis(CIBLE)){
  $("localTime").textContent = "Chez vous : " + new Date(CIBLE).toLocaleString("fr-FR",
    {weekday:"long", day:"numeric", month:"long", hour:"2-digit", minute:"2-digit"});
}

/* ---------- Compte à rebours ---------- */
const deux = n => String(n).padStart(2, "0");
let dernierePhrase = "";
function tic(){
  const ms = CIBLE - Date.now();
  if (ms <= 0){ ouvrir(true); return; }
  const s = Math.floor(ms / 1000);
  const j = Math.floor(s / 86400), h = Math.floor(s / 3600) % 24, m = Math.floor(s / 60) % 60;
  $("cdD").textContent = j; $("cdH").textContent = deux(h);
  $("cdM").textContent = deux(m); $("cdS").textContent = deux(s % 60);
  // Pour les lecteurs d'écran : une phrase par minute, pas un tic par seconde.
  const phrase = `Ouverture dans ${j} jour${j > 1 ? "s" : ""}, ${h} heure${h > 1 ? "s" : ""} et ${m} minute${m > 1 ? "s" : ""}.`;
  if (phrase !== dernierePhrase){ $("cdSpoken").textContent = phrase; dernierePhrase = phrase; }
  setTimeout(tic, 1000 - (Date.now() % 1000) + 8);
}
function ouvrir(enDirect){
  document.body.classList.add("is-open");
  if (enDirect && !reduit && document.body.dataset.vu) document.body.classList.add("opening");
  $("countdown").hidden = true; $("opened").hidden = false;
  if (LIEN_SITE){ $("enter").href = LIEN_SITE; $("enter").hidden = false; }
  document.title = "Les portes sont ouvertes · L'Épreuve des Dieux";
}

/* ---------- La tour (SVG généré) ---------- */
function construireTour(){
  const W = 600, CX = 300, NB = 14;
  let y = 1000, w = 560, h = 94, out = "";
  const defs = `<defs>
    <linearGradient id="stone" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a4268"/><stop offset="1" stop-color="#11162a"/></linearGradient>
    <linearGradient id="shade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#000" stop-opacity=".55"/><stop offset=".38" stop-color="#ffe2a0" stop-opacity=".07"/>
      <stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".6"/></linearGradient>
    <radialGradient id="warm" cx=".5" cy=".7" r=".7"><stop offset="0" stop-color="#ffd890"/><stop offset="1" stop-color="#9a6418"/></radialGradient>
    <radialGradient id="gateGlow" cx=".5" cy=".85" r=".9"><stop offset="0" stop-color="#fff1c8"/><stop offset=".35" stop-color="#f2c868"/><stop offset="1" stop-color="#6e4610" stop-opacity=".2"/></radialGradient>
    <linearGradient id="fadeUp" x1="0" y1="0" x2="0" y2="1"><stop offset=".2" stop-color="#fff" stop-opacity="0"/><stop offset=".42" stop-color="#fff" stop-opacity=".7"/><stop offset=".62" stop-color="#fff"/></linearGradient>
    <mask id="fade"><rect width="${W}" height="1000" fill="url(#fadeUp)"/></mask>
  </defs>`;
  for (let i = 0; i < NB; i++){
    const top = y - h, x0 = CX - w / 2, x1 = CX + w / 2, ins = w * .035, base = y - 7;
    let g = `<g class="tier">`;
    g += `<rect class="ledge" x="${x0 - 6}" y="${base}" width="${w + 12}" height="7"/>`;
    const body = `M${x0} ${base}L${x0 + ins} ${top}H${x1 - ins}L${x1} ${base}Z`;
    g += `<path d="${body}" fill="url(#stone)"/><path d="${body}" fill="url(#shade)"/>`;
    g += `<path class="rim" d="M${x0 + ins} ${top + .6}H${x1 - ins}"/>`;
    // Fenêtres en arche, réparties de part et d'autre du sceau central.
    const ww = Math.max(4, h * .15), wh = h * .42, yb = base - h * .2;
    const inner = w - 2 * ins, n = Math.max(2, Math.floor(inner / 54));
    for (let k = 0; k < n; k++){
      const x = x0 + ins + (k + .5) * inner / n;
      if (Math.abs(x - CX) < h * .45) continue;
      const lit = ((i * 7 + k * 13) % 4 === 0) ? " lit" : "";
      g += `<path class="win${lit}" d="M${x - ww / 2} ${yb}V${yb - wh + ww / 2}A${ww / 2} ${ww / 2} 0 0 1 ${x + ww / 2} ${yb - wh + ww / 2}V${yb}Z"/>`;
    }
    if (i === 0){
      // Porte d'entrée : faible lueur, qui s'embrase à l'ouverture.
      const gw = 66, gh = h * .74;
      g += `<path class="gate" d="M${CX - gw / 2} ${base}V${base - gh + gw / 2}A${gw / 2} ${gw / 2} 0 0 1 ${CX + gw / 2} ${base - gh + gw / 2}V${base}Z"/>`;
      g += `<path d="M${CX - gw / 2 - 5} ${base}V${base - gh + gw / 2}A${gw / 2 + 5} ${gw / 2 + 5} 0 0 1 ${CX + gw / 2 + 5} ${base - gh + gw / 2}V${base}" fill="none" stroke="#e3b552" stroke-opacity=".5" stroke-width="1.5"/>`;
    } else {
      const r = h * .3, cy = top + h * .48;
      g += `<g class="seal"><circle cx="${CX}" cy="${cy}" r="${r}"/><text x="${CX}" y="${cy + 1}" font-size="${(h * .4).toFixed(1)}">?</text></g>`;
    }
    out += g + "</g>";
    y = top; w *= .86; h *= .91;
  }
  // Flèche du sommet, déjà dans les nuées.
  out += `<path d="M${CX - w * .4} ${y}L${CX} ${y - 70}L${CX + w * .4} ${y}Z" fill="url(#stone)"/>`;
  $("tower").innerHTML = defs + `<g mask="url(#fade)">${out}</g>`;
  // Rang de chaque gradin pour l'éveil en cascade. La CSP refuse les attributs style en ligne ;
  // la variable passe donc par le CSSOM, que la CSP autorise.
  $("tower").querySelectorAll(".tier").forEach((g, i) => g.style.setProperty("--i", i));
}

/* ---------- Image d'ambiance optionnelle, avec repli ---------- */
function chargerAmbiance(url){
  if (!url) return;
  const img = new Image();
  img.decoding = "async";
  img.onload = () => { const el = $("ambiance"); el.style.backgroundImage = `url("${url.replace(/"/g, "%22")}")`; el.classList.add("ready"); };
  img.onerror = () => {}; // repli silencieux : le décor généré reste seul
  img.src = url;
}

/* ---------- Ciel étoilé et poussières d'or (canvas) ---------- */
function ciel(){
  const sc = $("stars"), mc = $("motes");
  const sx = sc.getContext("2d"), mx = mc.getContext("2d");
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  let W = 0, H = 0, etoiles = [], scintillantes = [], motes = [], fond = null;

  // Sprite de poussière : un dégradé radial pré-rendu, recopié à chaque image.
  const sprite = document.createElement("canvas"); sprite.width = sprite.height = 32;
  const sg = sprite.getContext("2d"), rg = sg.createRadialGradient(16, 16, 0, 16, 16, 16);
  rg.addColorStop(0, "rgba(255,236,190,1)"); rg.addColorStop(.25, "rgba(246,205,120,.55)"); rg.addColorStop(1, "rgba(227,181,82,0)");
  sg.fillStyle = rg; sg.fillRect(0, 0, 32, 32);

  const alea = (a, b) => a + Math.random() * (b - a);
  function dimensionner(){
    W = innerWidth; H = innerHeight;
    for (const c of [sc, mc]){ c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
    sx.setTransform(dpr, 0, 0, dpr, 0, 0); mx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.round(Math.min(320, W * H / 4200));
    etoiles = Array.from({length:n}, () => {
      const y = Math.pow(Math.random(), 1.6) * H * .8;          // plus denses vers le zénith
      return {x:alea(0, W), y, r:alea(.25, 1.15), a:alea(.25, .9) * (1 - y / H * .7), t:Math.random() < .1, p:alea(0, 6.28)};
    });
    scintillantes = etoiles.filter(e => e.t);
    // Fond d'étoiles fixes, dessiné une seule fois.
    fond = document.createElement("canvas"); fond.width = sc.width; fond.height = sc.height;
    const fx = fond.getContext("2d"); fx.setTransform(dpr, 0, 0, dpr, 0, 0);
    for (const e of etoiles) if (!e.t){
      fx.globalAlpha = e.a; fx.fillStyle = e.r > .9 ? "#fff3d6" : "#d8def5";
      fx.beginPath(); fx.arc(e.x, e.y, e.r, 0, 6.283); fx.fill();
    }
    const nm = Math.round(Math.min(46, W * H / 26000));
    motes = Array.from({length:nm}, () => nouvelle(true));
  }
  function nouvelle(partout){
    return {x:alea(W * .1, W * .9), y:partout ? alea(0, H) : H + 10, v:alea(6, 16), s:alea(2.5, 7),
            ph:alea(0, 6.28), amp:alea(6, 22), vie:0, duree:alea(10, 22)};
  }
  function dessiner(t){
    sx.setTransform(1, 0, 0, 1, 0, 0); sx.clearRect(0, 0, sc.width, sc.height); sx.drawImage(fond, 0, 0);
    sx.setTransform(dpr, 0, 0, dpr, 0, 0);
    for (const e of scintillantes){
      sx.globalAlpha = e.a * (.55 + .45 * Math.sin(t / 900 + e.p)); sx.fillStyle = "#fff6e0";
      sx.beginPath(); sx.arc(e.x, e.y, e.r + .2, 0, 6.283); sx.fill();
    }
    mx.clearRect(0, 0, W, H);
    for (const m of motes){
      const k = m.vie / m.duree, a = Math.sin(Math.min(1, Math.max(0, k)) * Math.PI) * .8;
      mx.globalAlpha = a;
      mx.drawImage(sprite, m.x + Math.sin(t / 2600 + m.ph) * m.amp - m.s / 2, m.y - m.s / 2, m.s, m.s);
    }
  }
  let prec = 0, enCours = false;
  function boucle(t){
    if (!enCours) return;
    const dt = Math.min(.1, (t - (prec || t)) / 1000);
    if (t - prec >= 33){                                            // ~30 images/s suffisent
      for (let i = 0; i < motes.length; i++){
        const m = motes[i]; m.y -= m.v * dt; m.vie += dt;
        if (m.vie > m.duree || m.y < -10) motes[i] = nouvelle(false);
      }
      dessiner(t); prec = t;
    }
    requestAnimationFrame(boucle);
  }
  dimensionner();
  dessiner(0);
  if (!reduit){
    enCours = true; requestAnimationFrame(boucle);
    document.addEventListener("visibilitychange", () => {
      enCours = !document.hidden; if (enCours){ prec = 0; requestAnimationFrame(boucle); }
    });
  }
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { dimensionner(); dessiner(performance.now()); }, 150); });
}

construireTour();
chargerAmbiance(params.get("ambiance") || AMBIANCE);
ciel();
if (CIBLE <= Date.now()) ouvrir(false); else { document.body.dataset.vu = "1"; tic(); }
})();
