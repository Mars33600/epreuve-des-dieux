/* En-tête commun : burger mobile, menu déroulant « Monde des Douze » et recherche globale en direct.
   Aucune donnée n'entre dans le HTML autrement que par textContent (pas d'innerHTML). Sans JS, les liens
   restent de simples liens et la recherche envoie le formulaire vers /recherche. */
(function () {
  "use strict";

  // --- Menu : burger et déroulant ---------------------------------------------------------------------
  var burger = document.getElementById("burger");
  var menu = document.getElementById("barMenu");
  var deroulant = document.querySelector(".deroulant");
  var bouton = deroulant && deroulant.querySelector(".deroulant-bouton");
  var liste = deroulant && deroulant.querySelector(".deroulant-liste");

  function basculerBurger(ouvert) {
    if (!burger) return;
    burger.setAttribute("aria-expanded", ouvert ? "true" : "false");
    document.body.classList.toggle("menu-ouvert", ouvert);
  }

  function basculerDeroulant(ouvert, focus) {
    if (!bouton) return;
    bouton.setAttribute("aria-expanded", ouvert ? "true" : "false");
    liste.hidden = !ouvert;
    if (ouvert && focus) { var a = liste.querySelector("a"); if (a) a.focus(); }
  }

  if (burger) burger.addEventListener("click", function () {
    basculerBurger(burger.getAttribute("aria-expanded") !== "true");
  });

  if (bouton) {
    bouton.addEventListener("click", function () {
      basculerDeroulant(bouton.getAttribute("aria-expanded") !== "true", false);
    });
    bouton.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); basculerDeroulant(true, true); }
    });
    liste.addEventListener("keydown", function (e) {
      var liens = Array.prototype.slice.call(liste.querySelectorAll("a"));
      var i = liens.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); liens[(i + 1) % liens.length].focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); liens[(i - 1 + liens.length) % liens.length].focus(); }
      else if (e.key === "Home") { e.preventDefault(); liens[0].focus(); }
      else if (e.key === "End") { e.preventDefault(); liens[liens.length - 1].focus(); }
    });
    deroulant.addEventListener("focusout", function (e) {
      if (e.relatedTarget && !deroulant.contains(e.relatedTarget)) basculerDeroulant(false);
    });
  }

  document.addEventListener("click", function (e) {
    if (deroulant && !deroulant.contains(e.target)) basculerDeroulant(false);
    if (menu && burger && !menu.contains(e.target) && !burger.contains(e.target)) basculerBurger(false);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (bouton && bouton.getAttribute("aria-expanded") === "true") {
      var dedans = deroulant.contains(document.activeElement);
      basculerDeroulant(false);
      if (dedans) bouton.focus();
    } else if (burger && burger.getAttribute("aria-expanded") === "true") {
      basculerBurger(false);
      burger.focus();
    }
  });
  // Retour arrière du navigateur (page restaurée depuis le cache) : tout est refermé.
  window.addEventListener("pageshow", function () { basculerDeroulant(false); basculerBurger(false); fermerTout(); });

  // --- Recherche en direct ----------------------------------------------------------------------------
  var DELAI = 180, MIN = 2, LIMITE = 5;
  var recherches = [];

  function fermerTout() { recherches.forEach(function (r) { r.fermer(); }); }

  function creer(champ) {
    var form = champ.form;
    var racine = champ.closest(".rech") || form || champ.parentNode;
    var panneau = racine.querySelector(".rech-panneau");
    if (!panneau) {
      panneau = document.createElement("div");
      panneau.className = "rech-panneau";
      panneau.id = "rechListe-" + (champ.name || "q") + "-" + recherches.length;
      panneau.setAttribute("role", "listbox");
      panneau.hidden = true;
      racine.appendChild(panneau);
      champ.setAttribute("role", "combobox");
      champ.setAttribute("aria-controls", panneau.id);
      champ.setAttribute("aria-autocomplete", "list");
      champ.setAttribute("aria-expanded", "false");
    }
    var minuterie = null, controle = null, numero = 0, actif = -1, cache = {};

    function items() { return Array.prototype.slice.call(panneau.querySelectorAll("a[role=option]")); }

    function fermer() {
      window.clearTimeout(minuterie);
      if (controle) controle.abort();
      numero++;
      panneau.hidden = true;
      champ.setAttribute("aria-expanded", "false");
      champ.removeAttribute("aria-activedescendant");
      actif = -1;
    }

    function activer(i) {
      var liens = items();
      liens.forEach(function (a) { a.classList.remove("actif"); a.removeAttribute("aria-selected"); });
      actif = i;
      if (i < 0 || !liens.length) { champ.removeAttribute("aria-activedescendant"); return; }
      var a = liens[i];
      a.classList.add("actif");
      a.setAttribute("aria-selected", "true");
      champ.setAttribute("aria-activedescendant", a.id);
      a.scrollIntoView({ block: "nearest" });
    }

    function message(texte) {
      panneau.textContent = "";
      var p = document.createElement("p");
      p.className = "rech-vide";
      p.textContent = texte;
      panneau.appendChild(p);
      panneau.hidden = false;
      champ.setAttribute("aria-expanded", "true");
    }

    function afficher(donnees) {
      panneau.textContent = "";
      actif = -1;
      champ.removeAttribute("aria-activedescendant");
      if (!donnees.groupes.length) { message("Aucun résultat pour « " + donnees.q.trim() + " »."); return; }
      var n = 0;
      donnees.groupes.forEach(function (g) {
        var bloc = document.createElement("div");
        bloc.className = "rech-groupe";
        bloc.setAttribute("role", "group");
        var titre = document.createElement("div");
        titre.className = "rech-titre";
        titre.id = panneau.id + "-g-" + g.type;
        titre.textContent = g.libelle;
        bloc.setAttribute("aria-labelledby", titre.id);
        bloc.appendChild(titre);
        g.resultats.forEach(function (r) {
          var a = document.createElement("a");
          a.href = r.lien; a.id = panneau.id + "-o" + (n++); a.className = "rech-item";
          a.setAttribute("role", "option"); a.tabIndex = -1;
          var nom = document.createElement("span");
          nom.className = "rech-nom"; nom.textContent = r.nom;
          a.appendChild(nom);
          if (r.detail) { var d = document.createElement("span"); d.className = "rech-detail"; d.textContent = r.detail; a.appendChild(d); }
          bloc.appendChild(a);
        });
        if (g.plus) {
          var t = document.createElement("a");
          t.href = g.voir_tout; t.id = panneau.id + "-o" + (n++); t.className = "rech-item rech-tout";
          t.setAttribute("role", "option"); t.tabIndex = -1;
          t.textContent = "Voir tout : " + g.libelle.toLowerCase();
          bloc.appendChild(t);
        }
        panneau.appendChild(bloc);
      });
      panneau.hidden = false;
      champ.setAttribute("aria-expanded", "true");
    }

    function lancer() {
      var q = champ.value.trim();
      if (q.length < MIN) { fermer(); return; }
      if (cache[q]) { afficher(cache[q]); return; }
      if (controle) controle.abort();
      controle = window.AbortController ? new AbortController() : null;
      var moi = ++numero;
      fetch("/api/recherche?limite=" + LIMITE + "&q=" + encodeURIComponent(q), {
        credentials: "same-origin", headers: { Accept: "application/json" }, signal: controle ? controle.signal : undefined
      }).then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      }).then(function (donnees) {
        if (moi !== numero) return;
        cache[q] = donnees;
        afficher(donnees);
      }).catch(function (err) {
        if (err && err.name === "AbortError") return;
        if (moi === numero) message("La recherche est indisponible pour le moment.");
      });
    }

    champ.addEventListener("input", function () {
      window.clearTimeout(minuterie);
      minuterie = window.setTimeout(lancer, DELAI);
    });
    champ.addEventListener("focus", function () { if (champ.value.trim().length >= MIN && panneau.hidden) lancer(); });
    champ.addEventListener("keydown", function (e) {
      var liens = items();
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (panneau.hidden) { if (champ.value.trim().length >= MIN) lancer(); return; }
        if (!liens.length) return;
        e.preventDefault();
        var suivant = e.key === "ArrowDown" ? actif + 1 : actif - 1;
        activer(suivant >= liens.length ? 0 : suivant < 0 ? liens.length - 1 : suivant);
      } else if (e.key === "Enter") {
        if (!panneau.hidden && actif >= 0 && liens[actif]) { e.preventDefault(); window.location.assign(liens[actif].href); }
        else { fermer(); }
      } else if (e.key === "Escape") {
        if (!panneau.hidden) { e.preventDefault(); e.stopPropagation(); fermer(); }
      }
    });
    document.addEventListener("click", function (e) {
      if (!panneau.hidden && !racine.contains(e.target)) fermer();
    });
    racine.addEventListener("focusout", function (e) {
      if (e.relatedTarget && !racine.contains(e.relatedTarget)) fermer();
    });
    return { fermer: fermer };
  }

  document.querySelectorAll("input[data-suggest]").forEach(function (champ) { recherches.push(creer(champ)); });

  // --- Images absentes -------------------------------------------------------------------------------
  // DofusDB n'a pas toutes les images : une image qui ne charge pas laisse sa case vide (classe « img-absente »)
  // au lieu de l'icône d'image cassée et du texte de remplacement.
  function absente(img) { if (img.tagName === "IMG") img.classList.add("img-absente"); }
  document.addEventListener("error", function (e) { if (e.target && e.target.tagName === "IMG") absente(e.target); }, true);
  Array.prototype.forEach.call(document.images, function (img) { if (img.complete && img.naturalWidth === 0 && img.src) absente(img); });
})();
