# -*- coding: utf-8 -*-
"""XP / Niveaux / Grades / Récompenses.

Ce module centralise TOUT ce qui touche à la progression:
- Courbe d'XP (difficile, mais plus lisible)
- Calcul niveau depuis l'XP
- Grades (Débutant → Maître du Casino)
- Couleurs débloquées par grade
- Récompenses KZ à chaque niveau + bonus à chaque nouveau grade

NOTE: La DB stocke aussi `level`, mais on garde le calcul à partir de l'XP
comme source de vérité pour éviter les incohérences.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


# -----------------
# Courbe d'XP
# -----------------
# XP total requis pour atteindre le niveau `level` (début de niveau).
# Lvl 1 => 0 XP
#
# On utilise une courbe "par niveau" puis on cumule:
#   XP_to_next(L) = 100 + (L^2 * 12)
#
# => la progression reste très dure au haut niveau, sans tomber dans des
# nombres astronomiques.


def level_cap(cfg_level_cap: int | None = None) -> int:
    try:
        cap = int(cfg_level_cap) if cfg_level_cap is not None else 100
    except Exception:
        cap = 100
    return max(1, cap)


@lru_cache(maxsize=8)
def _xp_table(cap: int = 100) -> list[int]:
    """Table XP cumulée: index i = XP requis pour début du niveau (i+1)."""
    cap = level_cap(cap)
    xp = 0
    table: list[int] = []
    for lvl in range(1, cap + 1):
        table.append(int(xp))
        # xp requis pour passer du niveau lvl -> lvl+1
        xp += 100 + (lvl * lvl * 12)
    return table


def xp_for_level(level: int, *, cap: int = 100) -> int:
    """XP total requis pour être au niveau `level` (début du niveau)."""
    cap = level_cap(cap)
    level = max(1, min(int(level), cap))
    return _xp_table(cap)[level - 1]


def level_from_xp(xp: int, *, cap: int = 100) -> int:
    """Calcule le niveau à partir de l'XP (capé)."""
    cap = level_cap(cap)
    xp = max(0, int(xp))

    # Recherche binaire sur [1..cap]
    lo, hi = 1, cap
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if xp_for_level(mid, cap=cap) <= xp:
            lo = mid
        else:
            hi = mid - 1
    return lo


# -----------------
# Grades / Couleurs / Récompenses
# -----------------

@dataclass(frozen=True)
class LevelTitle:
    min_level: int
    max_level: int
    title: str
    icon: str = ""
    profile_color: str | None = None  # nom dans PROFILE_COLORS (ex: "bleu")
    grade_bonus_kz: int = 0


# Grades demandés: Débutant + paliers + couleur débloquée + bonus KZ.
TITLES: list[LevelTitle] = [
    LevelTitle(1, 9, "Débutant", "🪙", profile_color="gris", grade_bonus_kz=0),
    LevelTitle(10, 19, "Apprenti", "🎲", profile_color="bleu", grade_bonus_kz=2000),
    LevelTitle(20, 34, "Habitué", "💎", profile_color="violet", grade_bonus_kz=5000),
    LevelTitle(35, 49, "Joueur Pro", "🔥", profile_color="orange", grade_bonus_kz=10000),
    LevelTitle(50, 69, "High Roller", "🃏", profile_color="rouge", grade_bonus_kz=20000),
    LevelTitle(70, 84, "Élite", "👑", profile_color="or", grade_bonus_kz=35000),
    LevelTitle(85, 99, "Légende", "🌟", profile_color="cyan", grade_bonus_kz=50000),
    LevelTitle(100, 100, "Maître du Casino", "🏆", profile_color="rose", grade_bonus_kz=100000),
]


def title_and_icon_for_level(level: int, *, cap: int = 100) -> tuple[str, str]:
    """Retourne (titre, icône) pour un niveau donné."""
    lvl = max(1, min(int(level), level_cap(cap)))
    for t in TITLES:
        if t.min_level <= lvl <= t.max_level:
            return t.title, (t.icon or "")
    return "Débutant", "🟤"


def title_for_level(level: int, *, cap: int = 100) -> str:
    return title_and_icon_for_level(level, cap=cap)[0]


def xp_progress(xp: int, *, cap: int = 100) -> tuple[int, int, int]:
    """Retourne (level, in_level_xp, needed_in_level_xp)."""
    cap = level_cap(cap)
    xp = max(0, int(xp))
    lvl = level_from_xp(xp, cap=cap)
    cur = xp_for_level(lvl, cap=cap)
    if lvl >= cap:
        return lvl, 0, 0
    nxt = xp_for_level(lvl + 1, cap=cap)
    return lvl, xp - cur, (nxt - cur)


# -----------------
# Récompenses KZ
# -----------------

def kz_per_level(level: int) -> int:
    """KZ gagnés à chaque niveau atteint (quand on passe à `level`)."""
    lvl = max(1, int(level))
    return 150 + (lvl * 10)


def grade_for_level(level: int, *, cap: int = 100) -> LevelTitle:
    lvl = max(1, min(int(level), level_cap(cap)))
    for g in TITLES:
        if g.min_level <= lvl <= g.max_level:
            return g
    return TITLES[0]


def unlocked_profile_colors(level: int, *, cap: int = 100) -> list[str]:
    """Liste (unique) des couleurs débloquées jusqu'au niveau donné."""
    lvl = max(1, min(int(level), level_cap(cap)))
    colors: list[str] = []
    for g in TITLES:
        if g.profile_color and g.min_level <= lvl:
            if g.profile_color not in colors:
                colors.append(g.profile_color)
    return colors


def grade_bonus_between_levels(old_level: int, new_level: int, *, cap: int = 100) -> tuple[int, list[LevelTitle]]:
    """Retourne (bonus_kz_total, grades_débloqués) entre deux niveaux."""
    cap = level_cap(cap)
    old_level = max(1, min(int(old_level), cap))
    new_level = max(1, min(int(new_level), cap))
    if new_level <= old_level:
        return 0, []

    unlocked: list[LevelTitle] = []
    bonus = 0
    for g in TITLES:
        # Débloqué si on franchit son min_level
        if old_level < g.min_level <= new_level:
            unlocked.append(g)
            bonus += int(g.grade_bonus_kz)
    return bonus, unlocked
