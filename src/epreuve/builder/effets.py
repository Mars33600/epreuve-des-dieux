"""Les tables de correspondance du builder de Duffus, recopiées de son code public (docs/lots/E3.md §2).

Un effet d'objet est un identifiant d'effet du jeu (`effectId`) et un jet `from`..`to`. Duffus ne retient
que les effets de cette table, chacun rattaché à une caractéristique ; les malus (ex. 157, « -# Force »)
arrivent déjà négatifs dans les données (`from` = -20).
"""

from __future__ import annotations

# effectId → caractéristique (table `dr` / `qc` du builder Duffus, identiques).
EFFET_CARAC: dict[int, str] = {
    125: "Vitalité", 153: "Vitalité", 124: "Sagesse", 156: "Sagesse", 118: "Force", 157: "Force",
    126: "Intelligence", 155: "Intelligence", 119: "Agilité", 154: "Agilité", 123: "Chance", 152: "Chance",
    138: "Puissance", 111: "PA", 168: "PA", 128: "PM", 169: "PM", 117: "Portée", 116: "Portée",
    115: "% Critique", 171: "% Critique", 112: "Dommages", 178: "Soins", 179: "Soins", 176: "Prospection",
    158: "Pods", 159: "Pods",
    210: "% Res Terre", 215: "% Res Terre", 211: "% Res Eau", 216: "% Res Eau", 212: "% Res Air", 217: "% Res Air",
    213: "% Res Feu", 218: "% Res Feu", 214: "% Res Neutre", 219: "% Res Neutre",
    430: "Do Neutre", 431: "Do Neutre", 422: "Do Terre", 423: "Do Terre", 424: "Do Feu", 425: "Do Feu",
    426: "Do Eau", 427: "Do Eau", 428: "Do Air", 429: "Do Air", 418: "Do Critique", 419: "Do Critique",
    182: "Invocations", 2990: "Invocations", 174: "Initiative", 175: "Initiative",
    752: "Fuite", 754: "Fuite", 753: "Tacle", 755: "Tacle",
    160: "Esquive PA", 162: "Esquive PA", 161: "Esquive PM", 163: "Esquive PM",
    410: "Retrait PA", 411: "Retrait PA", 412: "Retrait PM", 413: "Retrait PM",
    414: "Do Pou", 415: "Do Pou", 416: "Res Pou", 417: "Res Pou",
    2808: "% Do Armes", 2812: "% Do Sorts", 2813: "% Do Sorts", 2800: "% Do Mélée", 2801: "% Do Mélée",
    2804: "% Do Dist", 2805: "% Do Dist",
    244: "Re Neutre", 240: "Re Terre", 243: "Re Feu", 241: "Re Eau", 242: "Re Air", 246: "Re Eau",
    420: "Re Crit", 421: "Re Crit", 2806: "% Res Dist", 2807: "% Res Dist", 2803: "% Res Mélée", 2802: "% Res Mélée",
}  # fmt: skip

# L'ordre d'affichage des caractéristiques (liste `xd` de Duffus).
ORDRE_CARACS: tuple[str, ...] = (
    "Vitalité", "Force", "Intelligence", "Chance", "Agilité", "Sagesse", "Puissance", "% Critique", "PA", "PM",
    "Portée", "Invocations", "Dommages", "Do Neutre", "Do Terre", "Do Feu", "Do Eau", "Do Air", "Soins",
    "Prospection", "Initiative", "Pods", "% Res Neutre", "% Res Terre", "% Res Feu", "% Res Eau", "% Res Air",
    "Re Neutre", "Re Terre", "Re Feu", "Re Eau", "Re Air", "Re Crit", "Tacle", "Fuite", "Retrait PA", "Retrait PM",
    "Esquive PA", "Esquive PM", "Do Critique", "Do Pou", "Res Pou", "% Res Mélée", "% Res Dist", "% Do Sorts",
    "% Do Dist", "% Do Mélée", "% Do Armes",
)  # fmt: skip
assert set(EFFET_CARAC.values()) == set(ORDRE_CARACS)
# Pour un exo de forgemagie : l'effet positif de chaque caractéristique (le premier de la table).
EFFET_POSITIF: dict[str, int] = {}
for _eid, _carac in EFFET_CARAC.items():
    EFFET_POSITIF.setdefault(_carac, _eid)
EFFET_POSITIF["% Res Dist"] = 2807  # 2806 est le malus (bonustype -1 dans la table `effects`)

# Les 6 caractéristiques qui reçoivent des points de base et des parchemins (`$s`).
CARACS_PRINCIPALES: tuple[str, ...] = ("Vitalité", "Sagesse", "Force", "Intelligence", "Chance", "Agilité")
ELEMENTS: tuple[str, ...] = ("Force", "Intelligence", "Chance", "Agilité")

# Les groupes du panneau des caractéristiques (`kd`).
GROUPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Principales", ("PA", "PM", "Portée", "Invocations")),
    ("Éléments", ("Force", "Intelligence", "Chance", "Agilité")),
    ("Secondaires", ("Vitalité", "Sagesse", "Puissance", "% Critique", "Soins", "Prospection", "Pods", "Initiative")),
    ("Dommages", ("Dommages", "Do Critique", "Do Neutre", "Do Terre", "Do Feu", "Do Eau", "Do Air", "Do Pou",
                  "% Do Armes", "% Do Sorts", "% Do Mélée", "% Do Dist")),
    ("Résistances", ("% Res Neutre", "Re Neutre", "% Res Terre", "Re Terre", "% Res Feu", "Re Feu", "% Res Eau",
                     "Re Eau", "% Res Air", "Re Air", "Res Pou", "Re Crit", "% Res Dist", "% Res Mélée")),
    ("Esquive et retrait", ("Fuite", "Tacle", "Esquive PA", "Esquive PM", "Retrait PA", "Retrait PM")),
)  # fmt: skip

# Types d'objet (typeId du jeu) par famille d'emplacement, comme les fenêtres de choix de Duffus.
TYPES_ARMES: tuple[int, ...] = (2, 3, 6, 5, 7, 4, 22, 19, 271, 8)
TYPES_FAMILIERS: dict[str, int] = {"Familiers": 18, "Montiliers": 121, "Dragodindes": 331, "Muldos": 332,
                                   "Volkornes": 333}
TYPES_DOFUS: dict[str, int] = {"Dofus": 23, "Trophées": 151, "Prysmaradites": 217}
NOMS_TYPES: dict[int, str] = {
    16: "Coiffe", 17: "Cape", 1: "Amulette", 10: "Ceinture", 11: "Bottes", 9: "Anneau", 82: "Bouclier",
    2: "Arc", 3: "Baguette", 4: "Bâton", 5: "Dague", 6: "Épée", 7: "Marteau", 8: "Pelle", 19: "Hache",
    22: "Faux", 271: "Lance",
    **{v: k[:-1] for k, v in TYPES_FAMILIERS.items()}, 23: "Dofus", 151: "Trophée", 217: "Prysmaradite",
}  # fmt: skip

# Les emplacements du build, dans l'ordre de Duffus. Chacun accepte une famille de types.
EMPLACEMENTS: dict[str, tuple[int, ...]] = {
    "coiffe": (16,), "cape": (17,), "amulette": (1,), "ceinture": (10,), "bottes": (11,),
    "anneau1": (9,), "anneau2": (9,), "bouclier": (82,), "arme": TYPES_ARMES,
    "familier": tuple(TYPES_FAMILIERS.values()),
    **{f"dofus{i}": tuple(TYPES_DOFUS.values()) for i in range(1, 7)},
}  # fmt: skip
NOMS_EMPLACEMENTS: dict[str, str] = {
    "coiffe": "Coiffe", "cape": "Cape", "amulette": "Amulette", "ceinture": "Ceinture", "bottes": "Bottes",
    "anneau1": "Anneau 1", "anneau2": "Anneau 2", "bouclier": "Bouclier", "arme": "Arme", "familier": "Familier",
    **{f"dofus{i}": f"Dofus {i}" for i in range(1, 7)},
}  # fmt: skip
TOUS_LES_TYPES: frozenset[int] = frozenset(t for types in EMPLACEMENTS.values() for t in types)

# Objets que Duffus retire de ses fenêtres de choix (`excludeIds`).
EXCLUS: frozenset[int] = frozenset({29134, 29135, 21186, 6895, 6894})


def valeur_effet(de: int | float, a: int | float) -> int:
    """La valeur retenue pour un jet `de`..`a` (fonctions `Ra` / `Pm` de Duffus) : le jet maximal.

    Deux bornes de même signe : la plus grande ; une borne nulle : l'autre ; sinon la plus grande en valeur absolue.
    """
    if (de >= 0 and a >= 0) or (de < 0 and a < 0):
        return int(max(de, a))
    if de == 0:
        return int(a)
    if a == 0 or abs(de) >= abs(a):
        return int(de)
    return int(a)


# Lignes de dégâts d'arme (table `_` du calculateur d'arme de Duffus) : effectId → (libellé, élément).
EFFETS_ARME: dict[int, tuple[str, str]] = {
    95: ("vol Neutre", "neutre"), 92: ("vol Terre", "terre"), 94: ("vol Feu", "feu"), 91: ("vol Eau", "eau"),
    93: ("vol Air", "air"), 100: ("dommages Neutre", "neutre"), 97: ("dommages Terre", "terre"),
    99: ("dommages Feu", "feu"), 96: ("dommages Eau", "eau"), 98: ("dommages Air", "air"),
    108: ("soins Feu", "feu"), 2998: ("soins Eau", "eau"), 2999: ("soins Air", "air"), 3000: ("soins Terre", "terre"),
    3001: ("soins Neutre", "neutre"), 2822: ("do. meilleur élément", "meilleur"),
    2828: ("vol meilleur élément", "meilleur"), 5: ("Repousse", "poussee"),
}  # fmt: skip
