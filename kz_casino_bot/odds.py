# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from . import config
from .db import Database

ParamType = Literal["int", "float", "bool"]

# NOTE:
# - Probabilités: utilisez 0.25 = 25% (float entre 0 et 1)
# - Pourcentages de vol: utilisez 0.10 = 10% (float entre 0 et 1)

TUNABLE_PARAMS: dict[str, dict[str, Any]] = {
    # === COINFLIP ===
    "coinflip_payout": {"desc": "Multiplicateur coinflip (gain = mise × payout)", "type": "float", "min": 1.0, "max": 3.0, "default": 1.95, "config_attr": "COINFLIP_PAYOUT"},
    "coinflip_win_chance": {"desc": "Probabilité de gagner coinflip (0.50 = 50%)", "type": "float", "min": 0.01, "max": 0.99, "default": 0.50, "config_attr": "COINFLIP_WIN_CHANCE"},

    # === SLOTS ===
    "slots_pair_mult": {"desc": "Multiplicateur 2 symboles identiques", "type": "float", "min": 1.0, "max": 10.0, "default": 2.0, "config_attr": "SLOTS_PAIR_MULT"},
    "slots_triple_mult": {"desc": "Multiplicateur 3 symboles identiques", "type": "float", "min": 1.0, "max": 50.0, "default": 5.0, "config_attr": "SLOTS_TRIPLE_MULT"},
    "slots_jackpot_mult": {"desc": "Multiplicateur jackpot (7️⃣7️⃣7️⃣)", "type": "float", "min": 1.0, "max": 100.0, "default": 10.0, "config_attr": "SLOTS_JACKPOT_MULT"},
    "slots_win_chance": {"desc": "Chance de gagner slots (0.40 = 40%)", "type": "float", "min": 0.01, "max": 0.99, "default": 0.40, "config_attr": "SLOTS_WIN_CHANCE"},

    # === ROULETTE ===
    "roulette_green_mult": {"desc": "Multiplicateur vert (0)", "type": "int", "min": 2, "max": 100, "default": 14, "config_attr": "ROULETTE_GREEN_MULT"},
    "roulette_win_chance": {"desc": "Probabilité de gagner roulette (0.45 = 45%)", "type": "float", "min": 0.01, "max": 0.99, "default": 0.48, "config_attr": "ROULETTE_WIN_CHANCE"},

    # === GUESS ===
    "guess_exact_mult": {"desc": "Multiplicateur nombre exact", "type": "float", "min": 1.0, "max": 500.0, "default": 50.0, "config_attr": "GUESS_EXACT_MULT"},
    "guess_close1_mult": {"desc": "Multiplicateur ±1", "type": "float", "min": 1.0, "max": 100.0, "default": 10.0, "config_attr": "GUESS_CLOSE1_MULT"},
    "guess_close2_mult": {"desc": "Multiplicateur ±2", "type": "float", "min": 1.0, "max": 50.0, "default": 5.0, "config_attr": "GUESS_CLOSE2_MULT"},

    # === BLACKJACK ===
    "blackjack_payout": {"desc": "Multiplicateur blackjack", "type": "float", "min": 1.0, "max": 3.0, "default": 1.95, "config_attr": "BLACKJACK_PAYOUT"},
    "blackjack_win_chance": {"desc": "Probabilité de gagner au blackjack (0.45 = 45%)", "type": "float", "min": 0.01, "max": 0.99, "default": 0.45, "config_attr": "BLACKJACK_WIN_CHANCE"},

    # === CRASH ===
    "crash_house_edge": {"desc": "Avantage maison crash (0.05 = 5%)", "type": "float", "min": 0.0, "max": 0.5, "default": 0.05, "config_attr": "CRASH_HOUSE_EDGE"},
    "crash_max_mult": {"desc": "Multiplicateur max crash", "type": "float", "min": 1.01, "max": 100.0, "default": 20.0, "config_attr": "CRASH_MAX_MULT"},

    # All-in
    "allin_threshold": {"desc": "Seuil all-in (0.90 = 90%)", "type": "float", "min": 0.0, "max": 1.0, "default": 0.90, "config_attr": "ALL_IN_THRESHOLD"},
    "allin_flip_chance": {"desc": "Chance flip victoire->défaite si all-in", "type": "float", "min": 0.0, "max": 0.9, "default": 0.0, "config_attr": "ALL_IN_MAX_WIN_FLIP_P"},
    "allin_min_balance": {"desc": "Solde min pour biais all-in", "type": "int", "min": 0, "max": 100000, "default": 500, "config_attr": "ALL_IN_MIN_BALANCE"},

    # Vol
    "steal_success_rate": {"desc": "Taux réussite vol (0.25 = 25%)", "type": "float", "min": 0.0, "max": 1.0, "default": 0.25, "config_attr": "STEAL_SUCCESS_P"},
    "steal_steal_pct": {"desc": "% volé à la cible (0.10 = 10%)", "type": "float", "min": 0.01, "max": 0.50, "default": 0.10, "config_attr": "STEAL_STEAL_PCT"},
    "steal_fail_penalty_pct": {"desc": "Pénalité échec (0.05 = 5% de ton solde)", "type": "float", "min": 0.0, "max": 0.50, "default": 0.05, "config_attr": "STEAL_FAIL_PENALTY_PCT"},
    "steal_fail_penalty_min": {"desc": "Pénalité min échec", "type": "int", "min": 0, "max": 100000, "default": 10, "config_attr": "STEAL_FAIL_PENALTY_MIN"},
    "steal_fail_penalty_max": {"desc": "Pénalité max échec", "type": "int", "min": 0, "max": 1000000, "default": 200, "config_attr": "STEAL_FAIL_PENALTY_MAX"},

    # Sabotage
    "sabotage_success_rate": {"desc": "Taux réussite sabotage", "type": "float", "min": 0.0, "max": 1.0, "default": 0.12, "config_attr": "SABOTAGE_SUCCESS_P"},
    "sabotage_steal_pct": {"desc": "% volé lors sabotage (0.15 = 15%)", "type": "float", "min": 0.01, "max": 1.0, "default": 0.15, "config_attr": "SABOTAGE_STEAL_PCT"},

    # Éco
    "daily_amount": {"desc": "Montant daily", "type": "int", "min": 0, "max": 1000000, "default": 500, "config_attr": "DAILY_AMOUNT"},
    "weekly_amount": {"desc": "Montant weekly", "type": "int", "min": 0, "max": 10000000, "default": 2500, "config_attr": "WEEKLY_AMOUNT"},
    "work_min": {"desc": "Gain min work", "type": "int", "min": 0, "max": 1000000, "default": 50, "config_attr": "WORK_MIN"},
    "work_max": {"desc": "Gain max work", "type": "int", "min": 0, "max": 10000000, "default": 250, "config_attr": "WORK_MAX"},
    "min_bet": {"desc": "Mise minimum", "type": "int", "min": 1, "max": 10000000, "default": 10, "config_attr": "MIN_BET"},
    "max_bet": {"desc": "Mise maximum", "type": "int", "min": 1, "max": 1000000000, "default": 100000, "config_attr": "MAX_BET"},

    # PvP
    "pvp_tax": {"desc": "Taxe PvP (%)", "type": "float", "min": 0.0, "max": 0.9, "default": 0.0, "config_attr": "PVP_TAX"},
    "rps_tax": {"desc": "Taxe Pierre/Feuille/Ciseaux (%)", "type": "float", "min": 0.0, "max": 0.9, "default": 0.0, "config_attr": "RPS_TAX"},
    "blackjack1v1_tax": {"desc": "Taxe Blackjack 1v1 (%)", "type": "float", "min": 0.0, "max": 0.9, "default": 0.0, "config_attr": "BJ1V1_TAX"},
    "pvp_timeout": {"desc": "Timeout défis PvP (secondes)", "type": "int", "min": 10, "max": 600, "default": 60, "config_attr": "PVP_TIMEOUT"},

    # Bot
    "bot_enabled": {"desc": "Activer bot en PvP (0/1)", "type": "int", "min": 0, "max": 1, "default": 1, "config_attr": "BOT_ENABLED"},
    "bot_win_chance": {"desc": "Chance du bot de gagner (0.50 = 50%)", "type": "float", "min": 0.0, "max": 1.0, "default": 0.50, "config_attr": "BOT_WIN_CHANCE"},
    "bot_loss_penalty": {"desc": "Pénalité si tu perds vs bot (KZ)", "type": "int", "min": 0, "max": 1000000, "default": 0, "config_attr": "BOT_LOSS_PENALTY"},

    # GIFs
    "win_gifs_enabled": {"desc": "Activer les GIFs de win (0/1)", "type": "int", "min": 0, "max": 1, "default": 1, "config_attr": "WIN_GIFS_ENABLED"},
}

CATEGORIES: dict[str, list[str]] = {
    "🪙 Coinflip": ["coinflip_payout", "coinflip_win_chance"],
    "🎰 Slots": ["slots_win_chance", "slots_pair_mult", "slots_triple_mult", "slots_jackpot_mult"],
    "🎡 Roulette": ["roulette_win_chance", "roulette_green_mult"],
    "🔢 Guess": ["guess_exact_mult", "guess_close1_mult", "guess_close2_mult"],
    "🃏 Blackjack": ["blackjack_payout", "blackjack_win_chance"],
    "🚀 Crash": ["crash_house_edge", "crash_max_mult"],
    "⚠️ All-in": ["allin_threshold", "allin_flip_chance", "allin_min_balance"],
    "⚔️ Vol": ["steal_success_rate", "steal_steal_pct", "steal_fail_penalty_pct", "steal_fail_penalty_min", "steal_fail_penalty_max", "sabotage_success_rate", "sabotage_steal_pct"],
    "💰 Éco": ["daily_amount", "weekly_amount", "work_min", "work_max", "min_bet", "max_bet"],
    "🧑‍🤝‍🧑 PvP": ["pvp_tax", "rps_tax", "blackjack1v1_tax", "pvp_timeout"],
    "🤖 Bot": ["bot_enabled", "bot_win_chance", "bot_loss_penalty"],
    "🎞️ GIFs": ["win_gifs_enabled"],
}

def get_param_value(db: Database, param_name: str):
    pi = TUNABLE_PARAMS.get(param_name)
    if not pi:
        return 0
    db_value = db.get_setting(f"tunable_{param_name}")
    if db_value is not None:
        try:
            return float(db_value) if pi["type"] == "float" else int(db_value)
        except:
            pass
    config_attr = pi.get("config_attr")
    if config_attr and hasattr(config, config_attr):
        return getattr(config, config_attr)
    return pi["default"]

def set_param_value(db: Database, param_name: str, value):
    pi = TUNABLE_PARAMS.get(param_name)
    if not pi:
        return False, "Paramètre inconnu"
    t = pi["type"]
    try:
        v = float(value) if t == "float" else int(value)
    except:
        return False, "Valeur invalide"
    if v < pi["min"] or v > pi["max"]:
        return False, f"Valeur hors limites ({pi['min']} - {pi['max']})"
    db.set_setting(f"tunable_{param_name}", str(v))
    return True, None

def reset_param(db: Database, param_name: str | None = None):
    if param_name is None:
        # reset all
        for k, pi in TUNABLE_PARAMS.items():
            db.set_setting(f"tunable_{k}", None)
        return
    pi = TUNABLE_PARAMS.get(param_name)
    if not pi:
        return False
    db.set_setting(f"tunable_{param_name}", None)
    return True
