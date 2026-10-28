/* Les outils (E4) : calculs dans le navigateur, sans dépendance. Chaque page dit son nom dans <main data-outil>.
   Tout le texte passe par textContent (jamais innerHTML). Ce que Duffus garde par utilisateur (plans de craft,
   montures obtenues) reste ici dans localStorage, sur l'appareil. */
(function(){
"use strict";
const $ = id => document.getElementById(id);
function el(tag, props, ...enfants){
  const e = document.createElement(tag);
  Object.entries(props || {}).forEach(([k, v]) => { if (k === "class") e.className = v; else if (k === "texte") e.textContent = v; else e.setAttribute(k, v); });
  enfants.forEach(c => c != null && e.append(c));
  return e;
}
function lire(cle, defaut){ try{ const v = JSON.parse(localStorage.getItem(cle)); return v == null ? defaut : v; }catch(e){ return defaut; } }
function ecrire(cle, valeur){ try{ localStorage.setItem(cle, JSON.stringify(valeur)); }catch(e){ /* stockage indisponible : l'outil marche quand même */ } }
async function donnees(nom){ const r = await fetch(`/outils/donnees/${nom}.json`, {credentials:"same-origin"}); if (!r.ok) throw new Error(nom); return r.json(); }
const nombre = (v, defaut = 0) => { const n = Number(String(v).replace(",", ".")); return Number.isFinite(n) ? n : defaut; };
const borne = (v, a, b) => Math.max(a, Math.min(b, v));
const fr = new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 2});

/* ---------------------------------------------------------------- calculateur de drop */
/* Coefficient de prospection : 0,74 à 2,5 (courbe logistique centrée sur 250 PP). */
const coefPP = pp => Math.min(0.74 + 1.755 / (1 + Math.exp((250 - pp) / 85)), 2.5);
const apres = (p, n) => { const c = p / 100; return c <= 0 ? 0 : c >= 1 ? 100 : (1 - Math.pow(1 - c, n)) * 100; };
const pc = v => v >= 99.95 ? "> 99,9 %" : `${v.toFixed(1).replace(".", ",")} %`;
function tauxFinal(base, pp, bonus, bouclier){
  return borne(base * coefPP(pp) * (bouclier ? 1.05 : 1) * (1 + bonus / 100), 0, 100);
}
function initDrop(){
  const calcul = () => {
    const base = nombre($("dBase").value), pp = nombre($("dPP").value), bonus = nombre($("dBonus").value), s = $("dShield").checked;
    const p = tauxFinal(base, pp, bonus, s);
    $("dFinal").textContent = `${p.toFixed(2).replace(".", ",")} %`;
    $("dC5").textContent = pc(apres(p, 5)); $("dC10").textContent = pc(apres(p, 10)); $("dC25").textContent = pc(apres(p, 25));
    const corps = $("dTable"); corps.replaceChildren();
    for (let x = 100; x <= 700; x += 100){
      corps.append(el("tr", {class: x === Math.round(pp / 100) * 100 ? "courant" : ""},
        el("td", {texte: `${x} PP`, class: "num"}), el("td", {texte: `${tauxFinal(base, x, bonus, s).toFixed(2).replace(".", ",")} %`, class: "num"})));
    }
  };
  ["dBase", "dPP", "dBonus", "dShield"].forEach(i => $(i).addEventListener("input", calcul));
  calcul();
}

/* ---------------------------------------------------------------- simulateur d'XP des métiers */
const xpNiveau = n => 10 * n * (n - 1);                                         // XP cumulée pour atteindre le niveau n
const niveauDe = xp => xp <= 0 ? 1 : borne(Math.floor((1 + Math.sqrt(1 + 0.4 * xp)) / 2), 1, 200);
function xpCraft(niveauObjet, niveauMetier, ratio){
  if (niveauMetier <= 0 || niveauObjet <= 0 || !ratio) return 0;
  const ecart = Math.max(0, niveauMetier - niveauObjet);
  return Math.max(0, Math.floor(20 * niveauObjet / (Math.pow(ecart, 1.1) / 10 + 1) * ratio / 100));
}
/* Crafts d'un même objet pour aller du niveau de départ au niveau visé (null si l'objet ne donne plus d'XP). */
function craftsPour(niveauObjet, ratio, de, vers, bonus){
  let xp = xpNiveau(de), but = xpNiveau(vers), crafts = 0;
  while (xp < but){
    const niv = niveauDe(xp); if (niv >= 200) break;
    const gain = Math.floor(xpCraft(niveauObjet, niv, ratio) * bonus); if (gain <= 0) return null;
    const pas = Math.ceil(Math.min(xpNiveau(niv + 1) - xp, but - xp) / gain);
    xp += gain * pas; crafts += pas;
  }
  return crafts;
}
async function initXP(){
  const craft = await donnees("craft");
  const metiers = Object.entries(craft.metiers).sort((a, b) => a[1].localeCompare(b[1], "fr"));
  $("xMetier").replaceChildren(...metiers.map(([id, nom]) => el("option", {value: id, texte: nom})));
  const cle = "epreuve-xp-metiers", memo = lire(cle, {});
  if (memo.metier && craft.metiers[memo.metier]) $("xMetier").value = memo.metier;
  if (memo.de) $("xDe").value = memo.de; if (memo.vers) $("xVers").value = memo.vers; if (memo.bonus) $("xBonus").value = memo.bonus;
  const calcul = () => {
    const metier = Number($("xMetier").value), de = borne(Math.round(nombre($("xDe").value, 1)), 1, 199);
    const vers = borne(Math.round(nombre($("xVers").value, 2)), de + 1, 200), bonus = 1 + nombre($("xBonus").value) / 100;
    ecrire(cle, {metier: String(metier), de, vers, bonus: nombre($("xBonus").value)});
    const recettes = craft.recettes.filter(r => r[1] === metier).map(r => {
      const [nom, ratio] = craft.objets[r[0]]; return {nom, niveau: r[2], ratio, xp: Math.floor(xpCraft(r[2], de, ratio) * bonus)};
    }).filter(r => r.xp > 0).sort((a, b) => b.xp - a.xp || a.nom.localeCompare(b.nom, "fr")).slice(0, 30);
    const necessaire = xpNiveau(vers) - xpNiveau(de);
    $("xResume").textContent = `Il faut ${fr.format(necessaire)} XP pour passer du niveau ${de} au niveau ${vers}.`;
    const corps = $("xTable"); corps.replaceChildren();
    if (!recettes.length) corps.append(el("tr", {}, el("td", {colspan: "4", class: "muted", texte: "Aucun craft ne donne d'XP à ce niveau."})));
    recettes.forEach(r => {
      const n = craftsPour(r.niveau, r.ratio, de, vers, bonus);
      corps.append(el("tr", {class: "num"}, el("td", {texte: r.nom}), el("td", {texte: r.niveau}), el("td", {texte: fr.format(r.xp)}),
        el("td", {texte: n == null ? "—" : `${fr.format(n)} crafts`})));
    });
  };
  ["xMetier", "xDe", "xVers", "xBonus"].forEach(i => $(i).addEventListener("input", calcul));
  calcul();
}

/* ---------------------------------------------------------------- module de craft */
async function initCraft(){
  const craft = await donnees("craft"), cle = "epreuve-craft";
  const parResultat = new Map(); craft.recettes.forEach(r => { if (!parResultat.has(r[0])) parResultat.set(r[0], r); });
  const nomDe = id => (craft.objets[id] || ["Objet " + id])[0];
  let liste = lire(cle, {plan: {}, pris: {}});     // plan : objet → quantité ; pris : ressource → déjà réunie
  Object.entries(craft.metiers).sort((a, b) => a[1].localeCompare(b[1], "fr")).forEach(([id, nom]) => $("cMetier").append(el("option", {value: id, texte: nom})));
  const sauver = () => ecrire(cle, liste);
  function ressources(){
    const total = new Map(), decomposer = $("cDecomposer").checked;
    const ajouter = (id, qte, profondeur) => {
      const r = parResultat.get(id);
      if (decomposer && profondeur > 0 && r && profondeur < 6){ r[3].forEach(([i, q]) => ajouter(i, q * qte, profondeur + 1)); return; }
      total.set(id, (total.get(id) || 0) + qte);
    };
    Object.entries(liste.plan).forEach(([id, n]) => { const r = parResultat.get(Number(id)); if (r) r[3].forEach(([i, q]) => ajouter(i, q * n, 1)); });
    return [...total].sort((a, b) => nomDe(a[0]).localeCompare(nomDe(b[0]), "fr"));
  }
  function dessiner(){
    const l = $("cListe"); l.replaceChildren();
    const ids = Object.keys(liste.plan);
    if (!ids.length) l.append(el("li", {class: "muted", texte: "Aucun objet pour l'instant."}));
    ids.forEach(id => {
      const champ = el("input", {type: "number", min: "1", value: liste.plan[id], inputmode: "numeric", "aria-label": `Quantité : ${nomDe(id)}`});
      champ.addEventListener("input", () => { liste.plan[id] = Math.max(1, Math.round(nombre(champ.value, 1))); sauver(); dessinerRessources(); });
      const retirer = el("button", {class: "btn", type: "button", texte: "Retirer", "aria-label": `Retirer ${nomDe(id)}`});
      retirer.addEventListener("click", () => { delete liste.plan[id]; sauver(); dessiner(); });
      l.append(el("li", {class: "res-ligne"}, el("span", {texte: nomDe(id)}), el("span", {class: "qte"}, champ, retirer)));
    });
    dessinerRessources();
  }
  function dessinerRessources(){
    const l = $("cRessources"); l.replaceChildren();
    const rs = ressources();
    if (!rs.length) l.append(el("li", {class: "muted", texte: "Rien à réunir."}));
    rs.forEach(([id, n]) => {
      const c = el("input", {type: "checkbox", "aria-label": `Réuni : ${nomDe(id)}`}); c.checked = !!liste.pris[id];
      const ligne = el("li", {class: "res-ligne" + (c.checked ? " fait" : "")},
        el("label", {class: "coche-simple"}, c, el("span", {texte: nomDe(id)})), el("b", {class: "num", texte: `× ${fr.format(n)}`}));
      c.addEventListener("change", () => { if (c.checked) liste.pris[id] = true; else delete liste.pris[id]; ligne.classList.toggle("fait", c.checked); sauver(); });
      l.append(ligne);
    });
  }
  function chercher(){
    const q = $("cRecherche").value.trim().toLocaleLowerCase("fr"), metier = $("cMetier").value, l = $("cResultats");
    l.replaceChildren();
    if (q.length < 2) return;
    craft.recettes.filter(r => (!metier || String(r[1]) === metier) && nomDe(r[0]).toLocaleLowerCase("fr").includes(q)).slice(0, 20).forEach(r => {
      const b = el("button", {class: "btn", type: "button", texte: "Ajouter", "aria-label": `Ajouter ${nomDe(r[0])}`});
      b.addEventListener("click", () => { liste.plan[r[0]] = (liste.plan[r[0]] || 0) + 1; sauver(); dessiner(); });
      l.append(el("li", {class: "res-ligne"}, el("span", {texte: `${nomDe(r[0])} · ${craft.metiers[r[1]]} · niv. ${r[2]}`}), b));
    });
    if (!l.children.length) l.append(el("li", {class: "muted", texte: "Aucune recette trouvée."}));
  }
  $("cRecherche").addEventListener("input", chercher); $("cMetier").addEventListener("change", chercher);
  $("cDecomposer").addEventListener("change", dessinerRessources);
  $("cVider").addEventListener("click", () => { liste = {plan: {}, pris: {}}; sauver(); dessiner(); });
  dessiner();
}

/* ---------------------------------------------------------------- croisements d'élevage */
const TYPES = [["dragodinde", "Dragodindes"], ["muldo", "Muldos"], ["volkorne", "Volkornes"]];
async function initElevage(){
  const montures = await donnees("montures"), cle = "epreuve-elevage";
  const eues = new Set(lire(cle, [])); let type = TYPES[0][0];
  const onglets = $("eOnglets");
  TYPES.forEach(([k, nom]) => { const b = el("button", {type: "button", texte: nom, "data-type": k}); b.addEventListener("click", () => { type = k; dessiner(); }); onglets.append(b); });
  $("eManquantes").addEventListener("change", dessiner);
  function dessiner(){
    onglets.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.type === type)));
    const liste = montures[type], manquantes = $("eManquantes").checked, zone = $("eGenerations");
    zone.replaceChildren();
    const avec = liste.filter(m => m[2] != null), nb = avec.filter(m => eues.has(m[0])).length;
    $("eBilan").textContent = `${nb} sur ${avec.length} obtenues (${avec.length ? Math.round(nb * 100 / avec.length) : 0} %).`;
    const gens = [...new Set(avec.map(m => m[2]))].sort((a, b) => a - b);
    gens.forEach(g => {
      const ms = avec.filter(m => m[2] === g), faites = ms.filter(m => eues.has(m[0])).length;
      const ul = el("ul", {class: "montures"});
      ms.filter(m => !manquantes || !eues.has(m[0])).forEach(m => {
        const c = el("input", {type: "checkbox"}); c.checked = eues.has(m[0]);
        c.addEventListener("change", () => { if (c.checked) eues.add(m[0]); else eues.delete(m[0]); ecrire(cle, [...eues]); dessiner(); });
        ul.append(el("li", {}, el("label", {}, c, el("span", {texte: m[1]}))));
      });
      if (!ul.children.length) return;
      zone.append(el("section", {class: "card"}, el("div", {class: "gen-titre"}, el("h3", {texte: `Génération ${g}`}), el("b", {class: "num", texte: `${faites}/${ms.length}`})), ul));
    });
  }
  dessiner();
}

const outil = (document.querySelector("main[data-outil]") || {dataset: {}}).dataset.outil;
const demarrage = {drop: initDrop, xp: initXP, craft: initCraft, elevage: initElevage}[outil];
if (demarrage) Promise.resolve(demarrage()).catch(() => {
  const m = document.querySelector("main[data-outil] .resultat") || document.querySelector("main[data-outil]");
  m.append(el("p", {class: "alerte", role: "alert", texte: "Les données de l'outil n'ont pas pu être chargées. Réessaie dans une minute."}));
});
})();
