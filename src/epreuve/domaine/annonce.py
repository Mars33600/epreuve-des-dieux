"""L'annonce Discord d'un étage qui s'ouvre, postée par le « Gardien de la Tour » (demande de Shadoaze).

Ici, seulement le message : un dictionnaire au format des webhooks Discord, construit sans réseau ni horloge,
donc testable à l'identique. L'envoi (httpx, en tâche de fond) vit dans `epreuve.discord.webhook`.

Le ton suit le site : bleu nuit et or, sobre, « Même les Dieux se taisent ». Le `@everyone` du texte ne
notifie personne sans `allowed_mentions` : Discord exige qu'on autorise la mention explicitement.
"""

from __future__ import annotations

from epreuve.domaine.modeles import Etage

NOM_GARDIEN = "Gardien de la Tour"
COULEUR_OR = 0xD4A84B  # l'or du site (#d4a84b), en entier : c'est le format des couleurs d'embed


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
        "allowed_mentions": {"parse": ["everyone"]},
    }
