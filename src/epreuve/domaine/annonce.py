"""Les annonces Discord du « Gardien de la Tour » (demande de Shadoaze) : un étage qui s'ouvre, et le lancement
du site (le 13/11 à 17 h, une seule fois).

Ici, seulement le message : un dictionnaire au format des webhooks Discord, construit sans réseau ni horloge,
donc testable à l'identique. L'envoi (httpx, en tâche de fond) vit dans `epreuve.discord.webhook`.

Le ton suit le site : bleu nuit et or, sobre, « Même les Dieux se taisent ». Le `@everyone` du texte ne
notifie personne sans `allowed_mentions` : Discord exige qu'on autorise la mention explicitement.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from epreuve.domaine.modeles import Etage

NOM_GARDIEN = "Gardien de la Tour"
COULEUR_OR = 0xD4A84B  # l'or du site (#d4a84b), en entier : c'est le format des couleurs d'embed
# Après ce délai, le lancement n'est plus annoncé : un serveur éteint à 17 h et relancé le soir ne doit pas
# réveiller tout le serveur Discord des heures plus tard avec un « les portes s'ouvrent » périmé.
FENETRE_LANCEMENT = timedelta(hours=6)
# Le type de la ligne de journal qui réserve l'annonce du lancement (index unique partiel, migration g3).
JOURNAL_LANCEMENT = "annonce_lancement"
# Le seul `@everyone` autorisé : jamais les rôles ou membres qu'un texte pourrait contenir.
MENTIONS_EVERYONE = {"parse": ["everyone"]}


def lien_etage(site_url: str | None, numero: int) -> str | None:
    """L'adresse publique de la page de l'étage, ou None sans SITE_URL (en local, rien à montrer dehors)."""
    if not site_url:
        return None
    return f"{site_url.rstrip('/')}/etages/{numero}"


def image_publique(etage: Etage) -> str | None:
    """L'image d'ambiance seulement si Discord peut la lire : une adresse https externe. `/etages/N/image`
    exige une connexion (un étage scellé ne doit rien montrer), Discord n'y verrait qu'une redirection."""
    url = etage.ambiance_url
    return url if url and url.startswith("https://") else None


def annonce_ouverture(etage: Etage, site_url: str | None) -> dict:
    """Le corps JSON à poster sur le webhook pour l'ouverture de `etage`."""
    niveaux = f"{etage.niveau_min} à {etage.niveau_max}"
    embed: dict = {
        "title": f"L'étage {etage.numero} s'éveille",
        "description": (f"**{etage.nom}**\n\n"
                        "Un étage s'éveille quand la guilde en est digne : la jauge est pleine, la tour a entendu. "
                        "Les portes s'ouvrent sur la suite de l'ascension.\n\n"
                        "*Combien en reste-t-il ? Même les Dieux se taisent.*"),
        "color": COULEUR_OR,
        "fields": [{"name": "Niveaux", "value": niveaux, "inline": True},
                   {"name": "Cap", "value": f"niveau {etage.level_cap}", "inline": True}],
        "footer": {"text": "L'Épreuve des Dieux"},
    }
    lien = lien_etage(site_url, etage.numero)
    if lien:
        embed["url"] = lien  # le titre devient cliquable
    image = image_publique(etage)
    if image:
        embed["image"] = {"url": image}
    if etage.ouvert_le is not None:
        embed["timestamp"] = etage.ouvert_le.isoformat()  # Discord l'affiche à l'heure de chacun
    contenu = f"@everyone L'étage {etage.numero}, {etage.nom}, vient de s'ouvrir (niveaux {niveaux})."
    if lien:
        contenu += f"\n{lien}"
    return {
        "username": NOM_GARDIEN,
        "content": contenu,
        "embeds": [embed],
        # Sans cette ligne, « @everyone » s'afficherait sans prévenir personne ; on n'autorise que lui
        # (jamais les rôles ou membres qu'un nom d'étage pourrait contenir).
        "allowed_mentions": MENTIONS_EVERYONE,
    }


def lien_connexion(site_url: str | None) -> str | None:
    """La page de connexion du site, ou None sans SITE_URL."""
    return f"{site_url.rstrip('/')}/connexion" if site_url else None


def annonce_lancement(site_url: str | None) -> dict:
    """Le corps JSON à poster à l'ouverture du site. Les phrases en italique sont de Shadoaze (histoire.md),
    reprises telles quelles, apostrophes typographiques comprises ; celles du teaser vidéo (« Douziens… le premier
    étage vous attend », « Oserez-vous franchir le seuil ? ») sont écartées exprès, pour ne pas se répéter."""
    embed: dict = {
        "title": "La tour s’éveille",
        "description": ("*Ses portes s’entrouvrent à nouveau.*\n\n"
                        "*Gravissez les étages. Surmontez les épreuves. Prouvez votre valeur.*\n\n"
                        "*Cette fois, nul ne pourra triompher seul.*\n\n"
                        "Le site est ouvert : connectez-vous avec Discord pour créer votre fiche."),
        "color": COULEUR_OR,
        "footer": {"text": "L'Épreuve des Dieux"},
    }
    contenu = "@everyone L’Épreuve des Dieux commence."
    lien = lien_connexion(site_url)
    if lien:
        embed["url"] = lien
        contenu += f"\n{lien}"
    return {"username": NOM_GARDIEN, "content": contenu, "embeds": [embed], "allowed_mentions": MENTIONS_EVERYONE}


def doit_annoncer_lancement(maintenant: datetime, ouvert_le: datetime, deja_annonce: bool,
                            fenetre: timedelta = FENETRE_LANCEMENT) -> bool:
    """Vrai entre l'ouverture (comprise) et la fin de la fenêtre (exclue), si personne ne l'a déjà annoncé.
    `deja_annonce` est une lecture rapide : la garantie d'un seul envoi vient de la réservation en base."""
    return not deja_annonce and ouvert_le <= maintenant < ouvert_le + fenetre


def delai_avant_regard(maintenant: datetime, ouvert_le: datetime, periode: float) -> float:
    """Secondes à attendre avant le prochain regard de la veille : `periode`, sauf si l'ouverture tombe avant ;
    alors on se réveille pile à l'heure (17 h 00 et non 17 h 00 + 59 s)."""
    reste = (ouvert_le - maintenant).total_seconds()
    return reste if 0 < reste < periode else periode
