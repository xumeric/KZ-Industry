# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN") or ""
OWNER_ID = int(os.getenv("OWNER_ID") or "0")
DB_PATH = os.getenv("DB_PATH") or "casino.db"

# ============================================
# 🔒 RESTRICTIONS DE SALONS / CATÉGORIES
# ============================================
# Mets les IDs des salons ou catégories autorisés ici.
# Si les deux listes sont vides, les commandes sont autorisées partout.
# Ces valeurs s'ajoutent à celles configurées avec /channels et /category.

# IDs des SALONS autorisés (clique droit sur un salon > Copier l'ID)
ALLOWED_CHANNEL_IDS: list[int] = [
    1453747683482140886,  #🎰-casino-1
    1453747918749044818,  #🎲-casino-2      
    1453591743113990215,  #regles-casino
]

# IDs des CATÉGORIES autorisées (clique droit sur une catégorie > Copier l'ID)
ALLOWED_CATEGORY_IDS: list[int] = [
    # 123456789012345678,  # Exemple: 🎰 Casino
]

# Commandes toujours autorisées partout (pas besoin de modifier)
COMMANDS_ALLOWED_EVERYWHERE: set[str] = {"help", "panel"}

# ============================================

# Economy (Option 2 - Objectif: 1M en 2-4 semaines)
START_BALANCE = int(os.getenv("START_BALANCE") or "2500")
MIN_BET = int(os.getenv("MIN_BET") or "10")
MAX_BET = int(os.getenv("MAX_BET") or "1000000")

# All-in risk bias (when bet ~ balance, win becomes less likely)
ALLOW_ALL_IN_OVER_MAX_BET = (os.getenv("ALLOW_ALL_IN_OVER_MAX_BET") or "1") == "1"
ALL_IN_THRESHOLD = float(os.getenv("ALL_IN_THRESHOLD") or "0.90")  # ratio bet/balance
ALL_IN_MAX_WIN_FLIP_P = float(os.getenv("ALL_IN_MAX_WIN_FLIP_P") or "0.0")  # DÉSACTIVÉ - était 0.35 (injuste)
ALL_IN_MIN_BALANCE = int(os.getenv("ALL_IN_MIN_BALANCE") or "500")  # apply only if balance >= this

DAILY_AMOUNT = int(os.getenv("DAILY_AMOUNT") or "1500")  # Avant: 500
DAILY_COOLDOWN_H = int(os.getenv("DAILY_COOLDOWN_H") or "20")

WEEKLY_AMOUNT = int(os.getenv("WEEKLY_AMOUNT") or "7500")  # Avant: 2500
WEEKLY_COOLDOWN_D = int(os.getenv("WEEKLY_COOLDOWN_D") or "7")

WORK_MIN = int(os.getenv("WORK_MIN") or "200")  # Avant: 80
WORK_MAX = int(os.getenv("WORK_MAX") or "500")  # Avant: 220
WORK_COOLDOWN_MIN = int(os.getenv("WORK_COOLDOWN_MIN") or "30")

TRANSFER_TAX_PCT = float(os.getenv("TRANSFER_TAX_PCT") or "2.0")

CHEST_COOLDOWN_NORMAL_H = int(os.getenv("CHEST_COOLDOWN_NORMAL_H") or os.getenv("CHEST_COOLDOWN_H") or "72")
CHEST_COOLDOWN_VIP_H = int(os.getenv("CHEST_COOLDOWN_VIP_H") or "24")

STEAL_COOLDOWN_H = int(os.getenv("STEAL_COOLDOWN_H") or "12")
STEAL_SUCCESS_P = float(os.getenv("STEAL_SUCCESS_P") or "0.25")
STEAL_STEAL_PCT = float(os.getenv("STEAL_STEAL_PCT") or "0.10")  # 10% de la cible
STEAL_FAIL_PENALTY_PCT = float(os.getenv("STEAL_FAIL_PENALTY_PCT") or "0.05")  # 5% du voleur
STEAL_FAIL_PENALTY_MIN = int(os.getenv("STEAL_FAIL_PENALTY_MIN") or "10")
STEAL_FAIL_PENALTY_MAX = int(os.getenv("STEAL_FAIL_PENALTY_MAX") or "200")

# Shop / VIP / Immunity
IMMUNITY_PROTECTS_STEAL = int(os.getenv("IMMUNITY_PROTECTS_STEAL") or "1")

# ===== Activity rewards (configurable via /odds set) =====
ACTIVITY_MSG_TARGET = int(os.getenv("ACTIVITY_MSG_TARGET") or "50")  # Avant: 100
ACTIVITY_MSG_REWARD = int(os.getenv("ACTIVITY_MSG_REWARD") or "200")  # Avant: 100
ACTIVITY_MSG_COOLDOWN_SECONDS = int(os.getenv("ACTIVITY_MSG_COOLDOWN_SECONDS") or "15")
ACTIVITY_VOICE_TARGET_SECONDS = int(os.getenv("ACTIVITY_VOICE_TARGET_SECONDS") or "1800")  # Avant: 3600 (30min au lieu de 1h)
ACTIVITY_VOICE_REWARD = int(os.getenv("ACTIVITY_VOICE_REWARD") or "1000")

# ===== XP / Niveaux =====
# Progression volontairement difficile (voir kz_casino_bot/leveling.py)
XP_LEVEL_CAP = int(os.getenv("XP_LEVEL_CAP") or "100")

# Gains d'XP (tu peux ajuster dans .env si besoin)
XP_PER_ACTIVITY_MESSAGE = int(os.getenv("XP_PER_ACTIVITY_MESSAGE") or "10")
# XP par minute vocale (appliqué au moment où on quitte un vocal)
XP_PER_VOICE_MINUTE = int(os.getenv("XP_PER_VOICE_MINUTE") or "4")

# XP gagnée via les jeux (quand les stats win/lose sont enregistrées)
XP_PER_GAME = int(os.getenv("XP_PER_GAME") or "25")
XP_BONUS_WIN = int(os.getenv("XP_BONUS_WIN") or "25")
XP_BONUS_LOSS = int(os.getenv("XP_BONUS_LOSS") or "10")

# XP PvP (optionnel)
XP_PER_PVP_GAME = int(os.getenv("XP_PER_PVP_GAME") or "35")
XP_BONUS_PVP_WIN = int(os.getenv("XP_BONUS_PVP_WIN") or "35")
XP_BONUS_PVP_LOSS = int(os.getenv("XP_BONUS_PVP_LOSS") or "15")

# Styling
BRAND = {
    "name": "KZ Casino",
    "info": 0x7C3AED,   # violet
    "win": 0x16A34A,    # green
    "lose": 0xDC2626,   # red
    "neutral": 0x64748B # slate
}

RARITY_INFO = {
    "Common": {"emoji": "⚪", "color": 0xB0B0B0},
    "Rare": {"emoji": "🔵", "color": 0x3B82F6},
    "Epic": {"emoji": "🟣", "color": 0x8B5CF6},
    "Legendary": {"emoji": "🟡", "color": 0xF59E0B},
}

SHOP_CATEGORIES = ["Protection", "VIP", "Boost", "Cosmetics"]

# Games tuning (Option 2 - Objectif: 1M en 2-4 semaines)
COINFLIP_PAYOUT = float(os.getenv("COINFLIP_PAYOUT") or "1.98")  # Avant: 1.95
COINFLIP_WIN_CHANCE = float(os.getenv("COINFLIP_WIN_CHANCE") or "0.51")  # Avant: 0.48 (EV ≈ 0%)

# Slots
SLOTS_PAIR_MULT = float(os.getenv("SLOTS_PAIR_MULT") or "2.2")  # Avant: 2.0
SLOTS_TRIPLE_MULT = float(os.getenv("SLOTS_TRIPLE_MULT") or "5.0")  # Inchangé
SLOTS_JACKPOT_MULT = float(os.getenv("SLOTS_JACKPOT_MULT") or "12.0")  # Avant: 10.0
SLOTS_WIN_CHANCE = float(os.getenv("SLOTS_WIN_CHANCE") or "0.42")  # Avant: 0.35

# Roulette
ROULETTE_GREEN_MULT = int(os.getenv("ROULETTE_GREEN_MULT") or "14")  # Inchangé
ROULETTE_WIN_CHANCE = float(os.getenv("ROULETTE_WIN_CHANCE") or "0.50")  # Avant: 0.45 (EV = 0%)
ROULETTE_SIMPLE_PAYOUT = float(os.getenv("ROULETTE_SIMPLE_PAYOUT") or "2.0")  # Avant: 1.95
ROULETTE_DOZEN_PAYOUT = float(os.getenv("ROULETTE_DOZEN_PAYOUT") or "3.0")   # Avant: 2.90
ROULETTE_STRAIGHT_PAYOUT = float(os.getenv("ROULETTE_STRAIGHT_PAYOUT") or "36.0")  # Avant: 35.0

# Guess
GUESS_EXACT_MULT = float(os.getenv("GUESS_EXACT_MULT") or "50.0")  # Inchangé
GUESS_CLOSE1_MULT = float(os.getenv("GUESS_CLOSE1_MULT") or "10.0")  # Inchangé
GUESS_CLOSE2_MULT = float(os.getenv("GUESS_CLOSE2_MULT") or "5.0")  # Inchangé

BLACKJACK_PAYOUT = float(os.getenv("BLACKJACK_PAYOUT") or "2.0")  # Avant: 1.95
CRASH_HOUSE_EDGE = float(os.getenv("CRASH_HOUSE_EDGE") or "0.03")  # Avant: 0.05 (réduit à 3%)
CRASH_MAX_MULT = float(os.getenv("CRASH_MAX_MULT") or "25.0")  # Avant: 20.0
CRASH_DEFAULT_CASHOUT = float(os.getenv("CRASH_DEFAULT_CASHOUT") or "2.0")

SABOTAGE_COST = int(os.getenv("SABOTAGE_COST") or "100")
SABOTAGE_SUCCESS_P = float(os.getenv("SABOTAGE_SUCCESS_P") or "0.12")
SABOTAGE_STEAL_PCT = float(os.getenv("SABOTAGE_STEAL_PCT") or "0.15")
SABOTAGE_STEAL_CAP = int(os.getenv("SABOTAGE_STEAL_CAP") or "8000")
SABOTAGE_BLOCK_MIN = int(os.getenv("SABOTAGE_BLOCK_MIN") or "60")
SABOTAGE_COOLDOWN_H = int(os.getenv("SABOTAGE_COOLDOWN_H") or "6")

# --- FREE SHOP MODE (owner toggle) ---
FREE_SHOP = False  # si True : shop gratuit pour tout le monde (achats sans payer)

# GIFs de victoire (utilisés par PvP si win_gifs est vide)
DEFAULT_WIN_GIFS = [
    "https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif",
    "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif"
]

# ===== Bot PvP (troll) phrases =====
# Tu peux modifier ces listes facilement.

BOT_WIN_PHRASES = [
    "💀 T’es même pas capable de gagner contre un bot… c’est chaud là.",
    "🤖 J’ai même pas forcé. Tu veux un mode facile ?",
    "🧻 Tiens, prends un mouchoir. Le bot vient de te plier.",
    "📉 Ton ego vient de prendre -99%.",
    "🧠 Plot twist : c’était moi le tutoriel.",
    "🚑 Appelle le SAMU, ton niveau vient de tomber.",
    "🪦 Ici repose ton espoir de win contre une IA.",
]

BOT_LOSS_PHRASES = [
    "😏 GG… mais tu restes le perdant de l’histoire.",
    "🧪 Bravo, t’as gagné sur 1%… t’as eu de la chance, pas du talent.",
    "🎉 Félicitations ! (Le bot était AFK.)",
    "🍀 T’as win ? Non. T’as juste déclenché le bug de la chance.",
    "😌 Je te laisse croire que t’es fort… ça fait plaisir.",
    "📸 Screenshot, ça arrivera plus jamais.",
]

# Loans / Prêts (banque gérée par le bot + validation owner)
LOANS_ENABLED = (os.getenv("LOANS_ENABLED") or "1") == "1"
LOANS_FIXED_INTEREST_PCT = float(os.getenv("LOANS_FIXED_INTEREST_PCT") or "10")  # ex: 10 = 10%
LOANS_MIN_AMOUNT = int(os.getenv("LOANS_MIN_AMOUNT") or "100")
LOANS_MAX_AMOUNT = int(os.getenv("LOANS_MAX_AMOUNT") or "50000")
LOANS_MAX_ACTIVE_PER_USER = int(os.getenv("LOANS_MAX_ACTIVE_PER_USER") or "3")
LOANS_MAX_TERM_DAYS = int(os.getenv("LOANS_MAX_TERM_DAYS") or "14")
LOANS_DEFAULT_TERM_DAYS = int(os.getenv("LOANS_DEFAULT_TERM_DAYS") or "7")
LOANS_SEND_REQUESTS_TO_OWNER_DM = (os.getenv("LOANS_SEND_REQUESTS_TO_OWNER_DM") or "1") == "1"

# --- P2P loans (entre joueurs) ---
LOANS_P2P_ENABLED = (os.getenv("LOANS_P2P_ENABLED") or "1") == "1"
LOANS_P2P_MAX_INTEREST_PCT = float(os.getenv("LOANS_P2P_MAX_INTEREST_PCT") or "30")
LOANS_P2P_MAX_TERM_DAYS = int(os.getenv("LOANS_P2P_MAX_TERM_DAYS") or str(LOANS_MAX_TERM_DAYS))