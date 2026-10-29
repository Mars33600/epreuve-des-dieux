/* Lot E2 : filtres de l'encyclopédie. Amélioration progressive : sans JS, le bouton « Filtrer » suffit.
   - un changement de liste ou de niveau relance la recherche ;
   - la saisie relance la recherche après 400 ms de pause (au moins 2 lettres, ou champ vidé) ;
   - les champs vides ne vont pas dans l'adresse, et on revient à la page 1.
   Aucune donnée n'est injectée en HTML : le serveur rend la page, le script ne fait que naviguer. */
(function () {
  "use strict";
  var formulaire = document.querySelector("form[data-filtres]");
  if (!formulaire) return;

  function envoyer() {
    var params = new URLSearchParams();
    new FormData(formulaire).forEach(function (valeur, cle) {
      if (cle !== "page" && String(valeur).trim() !== "") params.append(cle, String(valeur).trim());
    });
    var cible = formulaire.getAttribute("action") || window.location.pathname;
    var requete = params.toString();
    window.location.assign(cible + (requete ? "?" + requete : ""));
  }

  formulaire.addEventListener("submit", function (e) { e.preventDefault(); envoyer(); });
  formulaire.querySelectorAll("select, input[type=number]").forEach(function (champ) {
    champ.addEventListener("change", envoyer);
  });

  var saisie = formulaire.querySelector("input[type=search]");
  // Avec des suggestions en direct (entete.js), on ne recharge plus la page à chaque pause : Entrée suffit.
  if (saisie && !saisie.hasAttribute("data-suggest")) {
    var minuterie = null;
    var initiale = saisie.value;
    saisie.addEventListener("input", function () {
      window.clearTimeout(minuterie);
      var v = saisie.value.trim();
      if (v === initiale.trim() || (v.length > 0 && v.length < 2)) return;
      minuterie = window.setTimeout(envoyer, 400);
    });
    // Le curseur revient en fin de saisie après le rechargement (recherche au fil de la frappe).
    if (initiale && document.activeElement !== saisie && saisie.hasAttribute("data-focus")) {
      saisie.focus();
      saisie.setSelectionRange(initiale.length, initiale.length);
    }
  }
})();
