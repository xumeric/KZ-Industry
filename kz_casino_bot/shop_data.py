# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Rarity = Literal["Common", "Rare", "Epic", "Legendary"]
Category = Literal["Protection", "VIP", "Boost", "Cosmetics"]

@dataclass(frozen=True)
class ShopItem:
    item_id: str
    name: str
    category: Category
    rarity: Rarity
    price: int
    description: str
    # if temporary boost: effect_key + duration_minutes
    effect_key: str | None = None
    duration_minutes: int | None = None


# NOTE:
# - item_id is the key stored in inventory.
# - effect_key is used by /use to apply boosts/vip/immunity.
DEFAULT_ITEMS: list[ShopItem] = [
    # Protection
    ShopItem(
        "shield_1h",
        "Bouclier 1h",
        "Protection",
        "Common",
        52500,
        "Te protège contre le vol pendant 1 heure.",
        effect_key="immunity",
        duration_minutes=60,
    ),
    ShopItem(
        "shield_6h",
        "Bouclier 6h",
        "Protection",
        "Rare",
        100200,
        "Te protège contre le vol pendant 6 heures.",
        effect_key="immunity",
        duration_minutes=360,
    ),
    ShopItem(
        "shield_24h",
        "Bouclier 24h",
        "Protection",
        "Epic",
        100000,
        "Te protège contre le vol pendant 24 heures.",
        effect_key="immunity",
        duration_minutes=1440,
    ),

    # VIP
    ShopItem(
        "vip_7d",
        "VIP 7 jours",
        "VIP",
        "Rare",
        80000,
        "Statut VIP pendant 7 jours (bonus / petits avantages selon la config du bot).",
        effect_key="vip",
        duration_minutes=7 * 24 * 60,
    ),
    ShopItem(
        "vip_30d",
        "VIP 30 jours",
        "VIP",
        "Epic",
        250000,
        "Statut VIP pendant 30 jours (bonus / petits avantages selon la config du bot).",
        effect_key="vip",
        duration_minutes=30 * 24 * 60,
    ),

    # Boost (temporaires)
    ShopItem(
        "boost_all_15m",
        "Chance Globale 15 min",
        "Boost",
        "Rare",
        9000,
        "+10% chance favorable sur certains jeux pendant 15 minutes.",
        effect_key="boost_all",
        duration_minutes=15,
    ),
    ShopItem(
        "boost_roulette_30m",
        "Boost Roulette 30 min",
        "Boost",
        "Rare",
        12000,
        "+20% chance favorable roulette pendant 30 minutes.",
        effect_key="boost_roulette",
        duration_minutes=30,
    ),
    ShopItem(
        "boost_blackjack_30m",
        "Boost Blackjack 30 min",
        "Boost",
        "Rare",
        32000,
        "+20% chance favorable blackjack pendant 30 minutes.",
        effect_key="boost_blackjack",
        duration_minutes=30,
    ),
    ShopItem(
        "boost_crash_30m",
        "Boost Crash 30 min",
        "Boost",
        "Epic",
        58000,
        "+20% chance favorable crash pendant 30 minutes.",
        effect_key="boost_crash",
        duration_minutes=30,
    ),
    ShopItem(
        "boost_steal_30m",
        "Boost Vol 30 min",
        "Boost",
        "Epic",
        22000,
        "+20% chance favorable vol pendant 30 minutes.",
        effect_key="boost_steal",
        duration_minutes=30,
    ),

    # Cosmetics / Profil
    ShopItem(
        "setprofile",
        "Ticket SetProfile",
        "Cosmetics",
        "Common",
        20000,
        "Nécessaire pour définir une image sur ton profil (bannière). Consommé à l'utilisation.",
        effect_key="setprofile",
        duration_minutes=None,
    ),
    ShopItem(
        "frame_gold",
        "Cadre Or",
        "Cosmetics",
        "Legendary",
        150000,
        "Ajoute un cadre Or sur ta carte profil (cosmétique).",
    ),

    ShopItem(
        "frame_silver",
        "Cadre Argent",
        "Cosmetics",
        "Rare",
        65000,
        "Cadre Argent pour ton profil (cosmétique).",
    ),
    ShopItem(
        "frame_ruby",
        "Cadre Rubis",
        "Cosmetics",
        "Epic",
        120000,
        "Cadre Rubis pour ton profil (cosmétique).",
    ),
    ShopItem(
        "frame_diamond",
        "Cadre Diamant",
        "Cosmetics",
        "Legendary",
        200000,
        "Cadre Diamant pour ton profil (cosmétique).",
    ),
    ShopItem(
        "frame_neon",
        "Cadre Néon",
        "Cosmetics",
        "Epic",
        110000,
        "Cadre Néon pour ton profil (cosmétique).",
    ),
]


def get_item(item_id: str) -> ShopItem | None:
    for it in DEFAULT_ITEMS:
        if it.item_id == item_id:
            return it
    return None


def items_by_category(category: str) -> list[ShopItem]:
    return [it for it in DEFAULT_ITEMS if it.category == category]
