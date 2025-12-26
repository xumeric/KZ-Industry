# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..odds import get_param_value
from ..db import Database
from ..utils import (
    check_bet,
    maybe_flip_win_for_all_in,
    embed_lose,
    embed_neutral,
    embed_win,
    fmt,
    human_time,
    now_utc,
    seconds_left,
    parse_dt,
)
from ..checks import enforce_blacklist


# ============================================
# Parser de mise (supporte "all", "max", "tout")
# ============================================

def parse_bet(mise_str: str, balance: int) -> tuple[int | None, str | None]:
    """
    Parse une mise. Retourne (montant, None) si ok, ou (None, erreur) si invalide.
    Supporte: nombre, "all", "max", "tout", "half", "moitié"
    """
    m = mise_str.strip().lower()
    
    if m in ("all", "max", "tout", "allin", "all-in"):
        return balance, None
    elif m in ("half", "moitié", "moitie", "demi"):
        return max(1, balance // 2), None
    else:
        try:
            amount = int(m.replace(",", "").replace(" ", ""))
            if amount <= 0:
                return None, "La mise doit être positive."
            return amount, None
        except ValueError:
            return None, "Mise invalide. Utilise un nombre ou `all`/`max`/`tout`."


ROULETTE_RED = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36,
}


def roulette_color(n: int) -> str:
    if n == 0:
        return "Vert"
    return "Rouge" if n in ROULETTE_RED else "Noir"


# ============================================
# BLACKJACK - Classes et fonctions
# ============================================

CARD_SUITS = ["♠️", "♥️", "♦️", "♣️"]
CARD_NAMES = {1: "A", 11: "J", 12: "Q", 13: "K"}


def card_to_str(card: int) -> str:
    """Convertit un numéro de carte (1-13) en string lisible."""
    if card in CARD_NAMES:
        return CARD_NAMES[card]
    return str(card)


def card_value(card: int) -> int:
    """Valeur d'une carte pour le blackjack."""
    if card == 1:
        return 11  # As (peut devenir 1)
    if card >= 10:
        return 10
    return card


def hand_value(cards: list[int]) -> int:
    """Calcule la valeur d'une main avec gestion des As."""
    total = sum(card_value(c) for c in cards)
    aces = sum(1 for c in cards if c == 1)
    while total > 21 and aces > 0:
        total -= 10  # As 11 -> 1
        aces -= 1
    return total


def format_hand(cards: list[int], hide_second: bool = False) -> str:
    """Formate une main pour l'affichage."""
    if hide_second and len(cards) >= 2:
        suit1 = random.choice(CARD_SUITS)
        return f"{card_to_str(cards[0])}{suit1} | 🂠"
    
    result = []
    for card in cards:
        suit = random.choice(CARD_SUITS)
        result.append(f"{card_to_str(card)}{suit}")
    return " | ".join(result)


class BlackjackView(discord.ui.View):
    def __init__(self, cog: "GamesCog", user_id: int, mise: int, balance: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.mise = mise
        self.original_mise = mise  # Garder la mise originale
        self.balance = balance
        self.deck = [i for i in range(1, 14)] * 4
        random.shuffle(self.deck)
        self.player_cards: list[int] = []
        self.dealer_cards: list[int] = []
        self.game_over = False
        self.message: discord.Message | None = None
        self.bet_taken = False  # La mise a été retirée
        
        # Distribution initiale
        self.player_cards.append(self.deck.pop())
        self.dealer_cards.append(self.deck.pop())
        self.player_cards.append(self.deck.pop())
        self.dealer_cards.append(self.deck.pop())
        
        # Retirer la mise immédiatement
        self.cog.db.add_balance(self.user_id, -self.mise)
        self.bet_taken = True

    def draw_card(self) -> int:
        if not self.deck:
            self.deck = [i for i in range(1, 14)] * 4
            random.shuffle(self.deck)
        return self.deck.pop()

    def build_embed(self, reveal_dealer: bool = False, result: str | None = None) -> discord.Embed:
        player_val = hand_value(self.player_cards)
        
        if result == "win":
            e = embed_win("🃏 Blackjack — Victoire !")
        elif result == "lose":
            e = embed_lose("🃏 Blackjack — Défaite")
        elif result == "push":
            e = embed_neutral("🃏 Blackjack — Égalité")
        elif result == "blackjack":
            e = embed_win("🃏 BLACKJACK ! 🎉")
        else:
            e = discord.Embed(
                title="🃏 Blackjack",
                description="**Tire** une carte ou **Reste** avec ta main actuelle.",
                color=config.BRAND["info"]
            )
        
        # Main du croupier
        if reveal_dealer:
            dealer_display = format_hand(self.dealer_cards)
            dealer_text = f"{dealer_display}\n**Valeur : {hand_value(self.dealer_cards)}**"
        else:
            dealer_display = format_hand(self.dealer_cards, hide_second=True)
            dealer_text = f"{dealer_display}\n**Valeur : ?**"
        
        e.add_field(name="🎩 Croupier", value=dealer_text, inline=True)
        
        # Main du joueur
        player_display = format_hand(self.player_cards)
        player_text = f"{player_display}\n**Valeur : {player_val}**"
        e.add_field(name="🃏 Toi", value=player_text, inline=True)
        
        e.add_field(name="💸 Mise", value=f"{fmt(self.mise)} KZ", inline=False)
        
        if result:
            new_bal = int(self.cog.db.get_user(self.user_id)["balance"])
            e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=True)
        
        e.set_footer(text=config.BRAND["name"])
        return e

    async def end_game(self, interaction: discord.Interaction, result: str, gain: int = 0):
        self.game_over = True
        for item in self.children:
            item.disabled = True
        
        # La mise a déjà été retirée au début du jeu
        if result == "win" or result == "blackjack":
            # Rembourser la mise + le gain
            self.cog.db.add_balance(self.user_id, self.mise + gain)
            self.cog.db.add_stat(self.user_id, wins_delta=1, games_delta=1)
            self.cog.db.add_game_stat(self.user_id, "blackjack", games_delta=1, wins_delta=1, profit_delta=gain)
        elif result == "lose":
            # La mise est déjà perdue (retirée au début)
            self.cog.db.add_stat(self.user_id, losses_delta=1, games_delta=1)
            self.cog.db.add_game_stat(self.user_id, "blackjack", games_delta=1, losses_delta=1, profit_delta=-self.mise)
        else:  # push (égalité)
            # Rembourser la mise
            self.cog.db.add_balance(self.user_id, self.mise)
            self.cog.db.add_stat(self.user_id, games_delta=1)
            self.cog.db.add_game_stat(self.user_id, "blackjack", games_delta=1)
        
        embed = self.build_embed(reveal_dealer=True, result=result)
        if result == "win":
            embed.description = f"Tu gagnes **+{fmt(gain)}** KZ !"
        elif result == "blackjack":
            embed.description = f"BLACKJACK ! Tu gagnes **+{fmt(gain)}** KZ !"
        elif result == "lose":
            embed.description = f"Tu perds **-{fmt(self.mise)}** KZ..."
        else:
            embed.description = "Égalité ! Ta mise est remboursée."
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce n'est pas ta partie !", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if not self.game_over:
            self.game_over = True
            # La mise est déjà retirée au début, donc on ne fait que enregistrer la défaite
            self.cog.db.add_stat(self.user_id, losses_delta=1, games_delta=1)
            self.cog.db.add_game_stat(self.user_id, "blackjack", games_delta=1, losses_delta=1, profit_delta=-self.mise)
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = self.build_embed(reveal_dealer=True, result="lose")
                embed.description = "⏰ Temps écoulé ! Tu perds ta mise."
                try:
                    await self.message.edit(embed=embed, view=self)
                except:
                    pass

    @discord.ui.button(label="Tirer", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_cards.append(self.draw_card())
        player_val = hand_value(self.player_cards)
        
        if player_val > 21:
            await self.end_game(interaction, "lose")
        elif player_val == 21:
            await self.dealer_play(interaction)
        else:
            embed = self.build_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Rester", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.dealer_play(interaction)

    @discord.ui.button(label="Doubler", style=discord.ButtonStyle.success, emoji="💰")
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_bal = int(self.cog.db.get_user(self.user_id)["balance"])
        if current_bal < self.original_mise:
            await interaction.response.send_message("❌ Solde insuffisant pour doubler !", ephemeral=True)
            return
        
        # Retirer la mise additionnelle
        self.cog.db.add_balance(self.user_id, -self.original_mise)
        self.mise += self.original_mise  # La mise totale double
        
        self.player_cards.append(self.draw_card())
        
        player_val = hand_value(self.player_cards)
        if player_val > 21:
            await self.end_game(interaction, "lose")
        else:
            await self.dealer_play(interaction)

    async def dealer_play(self, interaction: discord.Interaction):
        while hand_value(self.dealer_cards) < 17:
            self.dealer_cards.append(self.draw_card())
        
        player_val = hand_value(self.player_cards)
        dealer_val = hand_value(self.dealer_cards)
        
        player_blackjack = len(self.player_cards) == 2 and player_val == 21
        dealer_blackjack = len(self.dealer_cards) == 2 and dealer_val == 21
        
        # Récupérer le payout configurable
        payout = get_param_value(self.cog.db, "blackjack_payout")
        
        # Appliquer les VRAIES règles du blackjack
        if player_blackjack and not dealer_blackjack:
            # Blackjack naturel = gain x2.5
            gain = int(self.mise * 2.5)
            await self.end_game(interaction, "blackjack", gain)
        elif dealer_blackjack and not player_blackjack:
            await self.end_game(interaction, "lose")
        elif player_val > 21:
            # Joueur a bust
            await self.end_game(interaction, "lose")
        elif dealer_val > 21:
            # Croupier a bust = joueur gagne
            gain = int(self.mise * payout)
            await self.end_game(interaction, "win", gain)
        elif player_val > dealer_val:
            # Joueur a plus = joueur gagne
            gain = int(self.mise * payout)
            await self.end_game(interaction, "win", gain)
        elif player_val == dealer_val:
            # Égalité = push (remboursement)
            await self.end_game(interaction, "push")
        else:
            # Croupier a plus = joueur perd
            await self.end_game(interaction, "lose")


# ============================================
# CRASH - Classes et fonctions
# ============================================

class CrashView(discord.ui.View):
    def __init__(self, cog: "GamesCog", user_id: int, mise: int, balance: int):
        super().__init__(timeout=30)
        self.cog = cog
        self.user_id = user_id
        self.mise = mise
        self.balance = balance
        self.multiplier = 1.00
        self.crashed = False
        self.cashed_out = False
        self.message: discord.Message | None = None
        self.task: asyncio.Task | None = None
        
        edge = config.CRASH_HOUSE_EDGE
        r = random.random()
        self.crash_point = max(1.0, (1.0 - edge) / max(1e-9, r))
        self.crash_point = min(config.CRASH_MAX_MULT, self.crash_point)
        
        # Retirer la mise immédiatement
        self.cog.db.add_balance(self.user_id, -self.mise)

    def build_embed(self) -> discord.Embed:
        if self.cashed_out:
            gain = int(self.mise * self.multiplier)
            e = embed_win("🚀 Crash — Cash Out !")
            e.description = f"Tu as récupéré à **x{self.multiplier:.2f}** !"
            e.add_field(name="💰 Gain", value=f"+{fmt(gain)} KZ", inline=True)
        elif self.crashed:
            e = embed_lose("💥 Crash — Perdu !")
            e.description = f"Le crash est arrivé à **x{self.crash_point:.2f}** !"
            e.add_field(name="💸 Perte", value=f"-{fmt(self.mise)} KZ", inline=True)
        else:
            if self.multiplier < 1.5:
                color = 0x3B82F6
            elif self.multiplier < 2.0:
                color = 0x10B981
            elif self.multiplier < 3.0:
                color = 0xF59E0B
            else:
                color = 0xEF4444
            
            e = discord.Embed(
                title="🚀 Crash",
                description=f"# x{self.multiplier:.2f}\n\n⚠️ Cash out avant le crash !",
                color=color
            )
            progress = min(20, int(self.multiplier * 4))
            bar = "🟩" * progress + "⬛" * (20 - progress)
            e.add_field(name="📊 Progression", value=bar, inline=False)
        
        e.add_field(name="💸 Mise", value=f"{fmt(self.mise)} KZ", inline=True)
        
        if self.cashed_out or self.crashed:
            new_bal = int(self.cog.db.get_user(self.user_id)["balance"])
            e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=True)
        else:
            potential = int(self.mise * self.multiplier)
            e.add_field(name="💰 Gain potentiel", value=f"{fmt(potential)} KZ", inline=True)
        
        e.set_footer(text=config.BRAND["name"])
        return e

    async def start_crash(self):
        await asyncio.sleep(1)
        
        while not self.crashed and not self.cashed_out:
            increment = 0.05 + (self.multiplier * 0.02)
            self.multiplier += increment
            self.multiplier = round(self.multiplier, 2)
            
            if self.multiplier >= self.crash_point:
                self.crashed = True
                # La mise est déjà retirée au début
                self.cog.db.add_stat(self.user_id, losses_delta=1, games_delta=1)
                self.cog.db.add_game_stat(self.user_id, "crash", games_delta=1, losses_delta=1, profit_delta=-self.mise)
                for item in self.children:
                    item.disabled = True
                embed = self.build_embed()
                if self.message:
                    try:
                        await self.message.edit(embed=embed, view=self)
                    except:
                        pass
                self.stop()
                return
            
            if self.message:
                try:
                    embed = self.build_embed()
                    await self.message.edit(embed=embed, view=self)
                except:
                    pass
            
            delay = max(0.3, 0.8 - (self.multiplier * 0.05))
            await asyncio.sleep(delay)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce n'est pas ta partie !", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if not self.crashed and not self.cashed_out:
            self.crashed = True
            # La mise est déjà retirée au début
            self.cog.db.add_stat(self.user_id, losses_delta=1, games_delta=1)
            self.cog.db.add_game_stat(self.user_id, "crash", games_delta=1, losses_delta=1, profit_delta=-self.mise)
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = self.build_embed()
                embed.description = "⏰ Temps écoulé ! Tu perds ta mise."
                try:
                    await self.message.edit(embed=embed, view=self)
                except:
                    pass

    @discord.ui.button(label="💰 CASH OUT", style=discord.ButtonStyle.success)
    async def cashout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.crashed or self.cashed_out:
            return
        
        self.cashed_out = True
        
        win = maybe_flip_win_for_all_in(True, self.balance, self.mise)
        
        if win:
            # Gain = mise * multiplicateur (inclut la mise initiale)
            gain = int(self.mise * self.multiplier)
            profit = gain - self.mise
            # Rembourser la mise + le profit
            self.cog.db.add_balance(self.user_id, gain)
            self.cog.db.add_stat(self.user_id, wins_delta=1, games_delta=1)
            self.cog.db.add_game_stat(self.user_id, "crash", games_delta=1, wins_delta=1, profit_delta=profit)
        else:
            # Malchance all-in : le joueur crash quand même
            self.cashed_out = False
            self.crashed = True
            self.crash_point = self.multiplier
            # La mise est déjà perdue (retirée au début)
            self.cog.db.add_stat(self.user_id, losses_delta=1, games_delta=1)
            self.cog.db.add_game_stat(self.user_id, "crash", games_delta=1, losses_delta=1, profit_delta=-self.mise)
        
        for item in self.children:
            item.disabled = True
        
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


# ============================================
# COG PRINCIPAL
# ============================================

class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    async def cog_app_command_invoke(self, interaction: discord.Interaction):
        allowed = await enforce_blacklist(self.db, interaction)
        if not allowed:
            raise app_commands.CheckFailure("Blacklisted")

    # ----- Slots -----
    @app_commands.command(name="slots", description="Machine à sous")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')")
    async def slots(self, interaction: discord.Interaction, mise: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        bal = int(row["balance"])
        
        amount, err = parse_bet(mise, bal)
        if err:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", err), ephemeral=True)
        
        ok = check_bet(bal, amount)
        if not ok.ok:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", ok.reason))

        # Retirer la mise AVANT le jeu
        self.db.add_balance(interaction.user.id, -amount)

        symbols = ["🍒", "🍋", "🔔", "💎", "7️⃣"]
        
        # Paramètres configurables via /odds
        pair_mult = get_param_value(self.db, "slots_pair_mult")
        triple_mult = get_param_value(self.db, "slots_triple_mult")
        jackpot_mult = get_param_value(self.db, "slots_jackpot_mult")
        forced_win_chance = get_param_value(self.db, "slots_win_chance")
        
        # Si win_chance > 0, forcer la probabilité (pour limiter les gains)
        if forced_win_chance > 0:
            is_win = random.random() < forced_win_chance
            if is_win:
                # Générer un résultat gagnant
                win_type = random.random()
                if win_type < 0.02:  # 2% des victoires = jackpot 777
                    reel = ["7️⃣", "7️⃣", "7️⃣"]
                    win_mult = jackpot_mult
                elif win_type < 0.15:  # 13% des victoires = triple
                    sym = random.choice(symbols[:-1])
                    reel = [sym, sym, sym]
                    win_mult = triple_mult
                else:  # 85% des victoires = paire
                    sym = random.choice(symbols)
                    other = random.choice([s for s in symbols if s != sym])
                    reel = [sym, sym, other]
                    random.shuffle(reel)
                    win_mult = pair_mult
            else:
                # Générer un résultat perdant (3 symboles différents)
                reel = random.sample(symbols, 3)
                win_mult = 0
        else:
            # VRAI tirage aléatoire des 3 rouleaux
            reel = [random.choice(symbols) for _ in range(3)]
            
            # Déterminer le gain basé sur le VRAI résultat
            win_mult = 0
            if reel[0] == reel[1] == reel[2]:
                # 3 identiques
                if reel[0] == "7️⃣":
                    win_mult = jackpot_mult  # Jackpot 777
                else:
                    win_mult = triple_mult  # Triple normal
            elif reel[0] == reel[1] or reel[1] == reel[2] or reel[0] == reel[2]:
                # 2 identiques (paire)
                win_mult = pair_mult

        if win_mult > 0:
            # Victoire: rembourser mise + profit
            profit = int(amount * (win_mult - 1))  # Profit net
            self.db.add_balance(interaction.user.id, amount + profit)  # Rembourser mise + profit
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "slots", games_delta=1, wins_delta=1, profit_delta=profit)
            new_bal = int(self.db.get_user(interaction.user.id)["balance"])
            e = embed_win("🎰 Slots — Gagné", " ".join(reel))
            e.add_field(name="💸 Mise", value=f"{fmt(amount)} KZ", inline=True)
            e.add_field(name="💰 Gain", value=f"+{fmt(profit)} KZ (x{win_mult})", inline=True)
            e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
            return await interaction.response.send_message(embed=e)
        else:
            # Défaite: la mise est déjà retirée
            self.db.add_stat(interaction.user.id, losses_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "slots", games_delta=1, losses_delta=1, profit_delta=-amount)
            new_bal = int(self.db.get_user(interaction.user.id)["balance"])
            e = embed_lose("🎰 Slots — Perdu", " ".join(reel))
            e.add_field(name="💸 Mise", value=f"{fmt(amount)} KZ", inline=True)
            e.add_field(name="💰 Perte", value=f"-{fmt(amount)} KZ", inline=True)
            e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
            return await interaction.response.send_message(embed=e)

    # ----- Roulette -----
    @app_commands.command(name="roulette", description="Roulette: /roulette mise choix")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')", choix="rouge/noir/vert/pair/impair/1-18/19-36/1-12/13-24/25-36/0-36")
    async def roulette(self, interaction: discord.Interaction, mise: str, choix: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        bal = int(row["balance"])
        
        amount, err = parse_bet(mise, bal)
        if err:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", err), ephemeral=True)
        
        ok = check_bet(bal, amount)
        if not ok.ok:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", ok.reason))

        c = choix.strip().lower()
        aliases = {
            "rouge": "red", "red": "red",
            "noir": "black", "black": "black",
            "vert": "green", "green": "green",
            "pair": "even", "impair": "odd",
            "1-18": "low", "19-36": "high",
            "1-12": "d1", "13-24": "d2", "25-36": "d3",
        }
        bet_kind = aliases.get(c)
        bet_num = None
        if bet_kind is None:
            try:
                n = int(c)
                if 0 <= n <= 36:
                    bet_kind = "num"
                    bet_num = n
            except:
                pass
        if bet_kind is None:
            return await interaction.response.send_message(
                embed=embed_lose("❌ Choix invalide", "Choix: rouge/noir/vert/pair/impair/1-18/19-36/1-12/13-24/25-36 ou 0-36.")
            )

        # Retirer la mise AVANT le jeu
        self.db.add_balance(interaction.user.id, -amount)

        # Paramètres configurables via /odds
        green_mult = int(get_param_value(self.db, "roulette_green_mult"))
        forced_win_chance = get_param_value(self.db, "roulette_win_chance")
        
        # Si win_chance > 0, forcer la probabilité (pour limiter les gains)
        if forced_win_chance > 0:
            is_win = random.random() < forced_win_chance
            
            if is_win:
                # Générer un spin gagnant pour ce pari
                if bet_kind == "red":
                    spin = random.choice(list(ROULETTE_RED))
                elif bet_kind == "black":
                    spin = random.choice([n for n in range(1, 37) if n not in ROULETTE_RED])
                elif bet_kind == "green":
                    spin = 0
                elif bet_kind == "even":
                    spin = random.choice([n for n in range(2, 37, 2)])
                elif bet_kind == "odd":
                    spin = random.choice([n for n in range(1, 37, 2)])
                elif bet_kind == "low":
                    spin = random.randint(1, 18)
                elif bet_kind == "high":
                    spin = random.randint(19, 36)
                elif bet_kind == "d1":
                    spin = random.randint(1, 12)
                elif bet_kind == "d2":
                    spin = random.randint(13, 24)
                elif bet_kind == "d3":
                    spin = random.randint(25, 36)
                elif bet_kind == "num":
                    spin = bet_num
                else:
                    spin = random.randint(0, 36)
            else:
                # Générer un spin perdant pour ce pari
                if bet_kind == "red":
                    spin = random.choice([0] + [n for n in range(1, 37) if n not in ROULETTE_RED])
                elif bet_kind == "black":
                    spin = random.choice([0] + list(ROULETTE_RED))
                elif bet_kind == "green":
                    spin = random.randint(1, 36)
                elif bet_kind == "even":
                    spin = random.choice([0] + [n for n in range(1, 37, 2)])
                elif bet_kind == "odd":
                    spin = random.choice([0] + [n for n in range(2, 37, 2)])
                elif bet_kind == "low":
                    spin = random.choice([0] + list(range(19, 37)))
                elif bet_kind == "high":
                    spin = random.randint(0, 18)
                elif bet_kind == "d1":
                    spin = random.choice([0] + list(range(13, 37)))
                elif bet_kind == "d2":
                    spin = random.choice([0] + list(range(1, 13)) + list(range(25, 37)))
                elif bet_kind == "d3":
                    spin = random.randint(0, 24)
                elif bet_kind == "num":
                    spin = random.choice([n for n in range(0, 37) if n != bet_num])
                else:
                    spin = random.randint(0, 36)
            
            win = is_win
        else:
            # VRAI tirage aléatoire 0-36
            spin = random.randint(0, 36)
            
            # Déterminer si le joueur gagne basé sur le VRAI résultat
            win = False
            if bet_kind == "red":
                win = spin != 0 and spin in ROULETTE_RED
            elif bet_kind == "black":
                win = spin != 0 and spin not in ROULETTE_RED
            elif bet_kind == "green":
                win = spin == 0
            elif bet_kind == "even":
                win = spin != 0 and spin % 2 == 0
            elif bet_kind == "odd":
                win = spin != 0 and spin % 2 == 1
            elif bet_kind == "low":
                win = 1 <= spin <= 18
            elif bet_kind == "high":
                win = 19 <= spin <= 36
            elif bet_kind == "d1":
                win = 1 <= spin <= 12
            elif bet_kind == "d2":
                win = 13 <= spin <= 24
            elif bet_kind == "d3":
                win = 25 <= spin <= 36
            elif bet_kind == "num":
                win = spin == bet_num
        
        color = roulette_color(spin)
        
        # Déterminer le multiplicateur
        mult = 0
        if bet_kind == "red":
            mult = 2
        elif bet_kind == "black":
            mult = 2
        elif bet_kind == "green":
            mult = green_mult
        elif bet_kind in ("even", "odd", "low", "high"):
            mult = 2
        elif bet_kind in ("d1", "d2", "d3"):
            mult = 3
        elif bet_kind == "num":
            mult = 36

        if win:
            # Victoire: rembourser mise + profit
            profit = int(amount * (mult - 1))  # Profit net (ex: 1000 * (2-1) = 1000)
            self.db.add_balance(interaction.user.id, amount + profit)  # Rembourser mise + profit
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "roulette", games_delta=1, wins_delta=1, profit_delta=profit)
            new_bal = int(self.db.get_user(interaction.user.id)["balance"])
            e = embed_win("🎡 Roulette — Gagné")
            e.add_field(name="🎲 Résultat", value=f"**{spin}** ({color})", inline=True)
            e.add_field(name="🎯 Pari", value=f"{choix}", inline=True)
            e.add_field(name="💸 Mise", value=f"{fmt(amount)} KZ", inline=True)
            e.add_field(name="💰 Gain", value=f"+{fmt(profit)} KZ (x{mult})", inline=True)
            e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
            return await interaction.response.send_message(embed=e)
        else:
            # Défaite: la mise est déjà retirée, ne rien ajouter
            self.db.add_stat(interaction.user.id, losses_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "roulette", games_delta=1, losses_delta=1, profit_delta=-amount)
            new_bal = int(self.db.get_user(interaction.user.id)["balance"])
            e = embed_lose("🎡 Roulette — Perdu")
            e.add_field(name="🎲 Résultat", value=f"**{spin}** ({color})", inline=True)
            e.add_field(name="🎯 Pari", value=f"{choix}", inline=True)
            e.add_field(name="💸 Mise", value=f"{fmt(amount)} KZ", inline=True)
            e.add_field(name="💰 Perte", value=f"-{fmt(amount)} KZ", inline=True)
            e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
            return await interaction.response.send_message(embed=e)

    # ----- Coinflip -----
    @app_commands.command(name="coinflip", description="Pile ou face")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')", choix="pile ou face")
    async def coinflip(self, interaction: discord.Interaction, mise: str, choix: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        bal = int(row["balance"])
        
        amount, err = parse_bet(mise, bal)
        if err:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", err), ephemeral=True)
        
        ok = check_bet(bal, amount)
        if not ok.ok:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", ok.reason))
        c = choix.strip().lower()
        if c not in ("pile", "face"):
            return await interaction.response.send_message(embed=embed_lose("❌ Choix invalide", "Choix: pile ou face"))
        
        # Retirer la mise AVANT le jeu
        self.db.add_balance(interaction.user.id, -amount)
        
        # Paramètres configurables via /odds
        payout = get_param_value(self.db, "coinflip_payout")
        forced_win_chance = get_param_value(self.db, "coinflip_win_chance")
        
        # Si win_chance > 0, forcer la probabilité (pour limiter les gains)
        # Sinon, vrai tirage 50/50
        if forced_win_chance > 0:
            win = random.random() < forced_win_chance
            res = c if win else ("face" if c == "pile" else "pile")
        else:
            # VRAI tirage 50/50
            res = random.choice(["pile", "face"])
            win = (res == c)
        
        if win:
            # Victoire: rembourser mise + profit
            profit = int(amount * (payout - 1))  # Profit net
            self.db.add_balance(interaction.user.id, amount + profit)  # Rembourser mise + profit
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "coinflip", games_delta=1, wins_delta=1, profit_delta=profit)
            new_bal = int(self.db.get_user(interaction.user.id)["balance"])
            e = embed_win("🪙 Coinflip — Gagné", f"Résultat: **{res}**")
            e.add_field(name="💸 Mise", value=f"{fmt(amount)} KZ", inline=True)
            e.add_field(name="💰 Gain", value=f"+{fmt(profit)} KZ (x{payout})", inline=True)
            e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
            return await interaction.response.send_message(embed=e)
        else:
            # Défaite: la mise est déjà retirée
            self.db.add_stat(interaction.user.id, losses_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "coinflip", games_delta=1, losses_delta=1, profit_delta=-amount)
            new_bal = int(self.db.get_user(interaction.user.id)["balance"])
            e = embed_lose("🪙 Coinflip — Perdu", f"Résultat: **{res}**")
            e.add_field(name="💸 Mise", value=f"{fmt(amount)} KZ", inline=True)
            e.add_field(name="💰 Perte", value=f"-{fmt(amount)} KZ", inline=True)
            e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
            return await interaction.response.send_message(embed=e)

    # ----- Guess -----
    @app_commands.command(name="guess", description="Devine un nombre (1-100)")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')", nombre="Nombre entre 1 et 100")
    async def guess(self, interaction: discord.Interaction, mise: str, nombre: app_commands.Range[int, 1, 100]):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        bal = int(row["balance"])
        
        amount, err = parse_bet(mise, bal)
        if err:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", err), ephemeral=True)
        
        ok = check_bet(bal, amount)
        if not ok.ok:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", ok.reason))
        
        # Retirer la mise AVANT le jeu
        self.db.add_balance(interaction.user.id, -amount)
        
        # Multiplicateurs configurables via /odds
        exact_mult = get_param_value(self.db, "guess_exact_mult")
        close1_mult = get_param_value(self.db, "guess_close1_mult")
        close2_mult = get_param_value(self.db, "guess_close2_mult")
        
        target = random.randint(1, 100)
        diff = abs(target - int(nombre))

        profit_win = diff in (0, 1, 2)
        profit_win = maybe_flip_win_for_all_in(profit_win, bal, amount)
        if diff in (0, 1, 2) and not profit_win:
            diff = 999

        if diff == 0:
            mult = exact_mult
            profit = int(amount * (mult - 1))  # Profit net
            self.db.add_balance(interaction.user.id, amount + profit)  # Rembourser mise + profit
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "guess", games_delta=1, wins_delta=1, profit_delta=profit)
            e = embed_win("🔢 Guess — JACKPOT ! 🎉")
            e.add_field(name="Résultat", value=f"Ton choix: **{nombre}** | Tiré: **{target}**", inline=False)
            e.add_field(name="Gain", value=f"+{fmt(profit)} KZ (x{mult})", inline=True)
        elif diff == 1:
            mult = close1_mult
            profit = int(amount * (mult - 1))
            self.db.add_balance(interaction.user.id, amount + profit)
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "guess", games_delta=1, wins_delta=1, profit_delta=profit)
            e = embed_win("🔢 Guess — Très proche !")
            e.add_field(name="Résultat", value=f"Ton choix: **{nombre}** | Tiré: **{target}**", inline=False)
            e.add_field(name="Gain", value=f"+{fmt(profit)} KZ (x{mult})", inline=True)
        elif diff == 2:
            mult = close2_mult
            profit = int(amount * (mult - 1))
            self.db.add_balance(interaction.user.id, amount + profit)
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "guess", games_delta=1, wins_delta=1, profit_delta=profit)
            e = embed_win("🔢 Guess — Proche !")
            e.add_field(name="Résultat", value=f"Ton choix: **{nombre}** | Tiré: **{target}**", inline=False)
            e.add_field(name="Gain", value=f"+{fmt(profit)} KZ (x{mult})", inline=True)
        elif diff <= 5:
            # Remboursement - rendre la mise
            self.db.add_balance(interaction.user.id, amount)
            self.db.add_stat(interaction.user.id, games_delta=1)
            e = embed_neutral("🔢 Guess — Remboursé")
            e.add_field(name="Résultat", value=f"Ton choix: **{nombre}** | Tiré: **{target}** (±{diff})", inline=False)
            e.add_field(name="Gain", value="0 KZ (mise remboursée)", inline=True)
        else:
            # Défaite: la mise est déjà retirée
            self.db.add_stat(interaction.user.id, losses_delta=1, games_delta=1)
            self.db.add_game_stat(interaction.user.id, "guess", games_delta=1, losses_delta=1, profit_delta=-amount)
            e = embed_lose("🔢 Guess — Perdu")
            e.add_field(name="Résultat", value=f"Ton choix: **{nombre}** | Tiré: **{target}** (±{diff})", inline=False)
            e.add_field(name="Perte", value=f"-{fmt(amount)} KZ", inline=True)

        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e.add_field(name="💸 Mise", value=f"{fmt(amount)} KZ", inline=True)
        e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
        await interaction.response.send_message(embed=e)

    # ----- Chest -----
    @app_commands.command(name="chest", description="Ouvrir un coffre")
    async def chest(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)

        vip_dt = parse_dt(row["vip_until"])
        is_vip = bool(vip_dt and vip_dt > now_utc())
        cd_h = config.CHEST_COOLDOWN_VIP_H if is_vip else config.CHEST_COOLDOWN_NORMAL_H
        left = seconds_left(row["last_chest"], int(cd_h * 3600))
        if left > 0:
            return await interaction.response.send_message(embed=embed_lose("⏳ Coffre", f"Reviens dans **{human_time(left)}**."))

        roll = random.random()
        if roll < 0.01:
            gain = 5000
            e = embed_win("🧰 Coffre — Jackpot", f"Tu trouves **{fmt(gain)}** KZ !")
            self.db.add_balance(interaction.user.id, gain)
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
        elif roll < 0.10:
            gain = random.randint(800, 1500)
            e = embed_win("🧰 Coffre — Gros gain", f"Tu trouves **{fmt(gain)}** KZ !")
            self.db.add_balance(interaction.user.id, gain)
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
        elif roll < 0.75:
            gain = random.randint(150, 450)
            e = embed_win("🧰 Coffre", f"Tu trouves **{fmt(gain)}** KZ !")
            self.db.add_balance(interaction.user.id, gain)
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
        else:
            loss = random.randint(50, 200)
            e = embed_lose("🧰 Coffre — Piège", f"Tu perds **{fmt(loss)}** KZ...")
            self.db.add_balance(interaction.user.id, -loss)
            self.db.add_stat(interaction.user.id, losses_delta=1, games_delta=1)

        self.db.set_user_field(interaction.user.id, "last_chest", now_utc().isoformat())
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
        if is_vip:
            e.set_footer(text=f"VIP actif — prochain coffre dans {cd_h}h")
        await interaction.response.send_message(embed=e)

    # ----- Steal -----
    @app_commands.command(name="steal", description="Tenter de voler un joueur")
    async def steal(self, interaction: discord.Interaction, cible: discord.Member):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        self.db.ensure_user(cible.id, config.START_BALANCE)
        if cible.bot or cible.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_lose("❌ Vol", "Cible invalide."))

        thief = self.db.get_user(interaction.user.id)
        left = seconds_left(thief["last_steal"], config.STEAL_COOLDOWN_H * 3600)
        if left > 0:
            return await interaction.response.send_message(embed=embed_lose("⏳ Vol", f"Reviens dans **{human_time(left)}**."))

        if config.IMMUNITY_PROTECTS_STEAL:
            imm = parse_dt(self.db.get_user(cible.id)["immunity_until"])
            if imm and imm > now_utc():
                self.db.set_user_field(interaction.user.id, "last_steal", now_utc().isoformat())
                return await interaction.response.send_message(embed=embed_lose("🛡️ Vol bloqué", f"{cible.mention} est immunisé."))

        target_row = self.db.get_user(cible.id)
        target_bal = int(target_row["balance"])
        if target_bal <= 0:
            self.db.set_user_field(interaction.user.id, "last_steal", now_utc().isoformat())
            return await interaction.response.send_message(embed=embed_lose("🕵️ Vol", "La cible n'a rien à voler."))

        success = random.random() < float(get_param_value(self.db, 'steal_success_rate'))
        if success:
            steal_pct = float(get_param_value(self.db, 'steal_steal_pct'))
            amount = max(1, int(target_bal * steal_pct))
            amount = min(amount, target_bal)
            self.db.add_balance(cible.id, -amount)
            self.db.add_balance(interaction.user.id, amount)
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
            self.db.add_stat(cible.id, losses_delta=1)
            e = embed_win("🕵️ Vol — Réussi", f"Tu voles **{fmt(amount)}** KZ à {cible.mention}.")
        else:
            pen_pct = float(get_param_value(self.db, 'steal_fail_penalty_pct'))
            pen_min = int(get_param_value(self.db, 'steal_fail_penalty_min'))
            pen_max = int(get_param_value(self.db, 'steal_fail_penalty_max'))
            penalty = min(pen_max, max(pen_min, int(thief["balance"]) * pen_pct))
            self.db.add_balance(interaction.user.id, -penalty)
            self.db.add_stat(interaction.user.id, losses_delta=1, games_delta=1)
            e = embed_lose("🕵️ Vol — Raté", f"Tu te fais attraper ! Tu perds **{fmt(penalty)}** KZ.")

        self.db.set_user_field(interaction.user.id, "last_steal", now_utc().isoformat())
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
        await interaction.response.send_message(embed=e)

    # ----- Blackjack INTERACTIF -----
    @app_commands.command(name="blackjack", description="Blackjack interactif contre le croupier")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')")
    async def blackjack(self, interaction: discord.Interaction, mise: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        bal = int(row["balance"])
        
        amount, err = parse_bet(mise, bal)
        if err:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", err), ephemeral=True)
        
        ok = check_bet(bal, amount)
        if not ok.ok:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", ok.reason))

        view = BlackjackView(self, interaction.user.id, amount, bal)
        embed = view.build_embed()
        
        player_val = hand_value(view.player_cards)
        if player_val == 21:
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
            await view.dealer_play(interaction)
            return
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    # ----- Crash INTERACTIF -----
    @app_commands.command(name="crash", description="Crash interactif : cash-out avant le crash !")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')")
    async def crash(self, interaction: discord.Interaction, mise: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        bal = int(row["balance"])
        
        amount, err = parse_bet(mise, bal)
        if err:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", err), ephemeral=True)
        
        ok = check_bet(bal, amount)
        if not ok.ok:
            return await interaction.response.send_message(embed=embed_lose("❌ Mise invalide", ok.reason))

        view = CrashView(self, interaction.user.id, amount, bal)
        embed = view.build_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        
        view.task = asyncio.create_task(view.start_crash())

    # ----- Sabotage -----
    @app_commands.command(name="sabotage", description="Tente de saboter un joueur (blocage + vol).")
    @app_commands.describe(cible="Joueur ciblé")
    async def sabotage(self, interaction: discord.Interaction, cible: discord.Member):
        if cible.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_lose("❌ Sabotage", "Tu ne peux pas te saboter toi-même."), ephemeral=True)
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        self.db.ensure_user(cible.id, config.START_BALANCE)

        thief = self.db.get_user(interaction.user.id)
        victim = self.db.get_user(cible.id)
        bal = int(thief["balance"])

        cost = config.SABOTAGE_COST
        if bal < cost:
            return await interaction.response.send_message(embed=embed_lose("❌ Sabotage", f"Il te faut **{fmt(cost)}** KZ pour saboter."), ephemeral=True)

        # Vérifier cooldown - utiliser get() au lieu de .keys()
        last_sabotage_str = thief["last_sabotage"] if thief["last_sabotage"] else None
        last = parse_dt(last_sabotage_str) if last_sabotage_str else None
        cd_h = config.SABOTAGE_COOLDOWN_H
        if last and (now_utc() - last) < timedelta(hours=cd_h):
            left = int((timedelta(hours=cd_h) - (now_utc() - last)).total_seconds())
            return await interaction.response.send_message(embed=embed_lose("⏳ Sabotage", f"Cooldown : **{human_time(left)}**"), ephemeral=True)

        imm_until = parse_dt(victim["immunity_until"]) if victim["immunity_until"] else None
        if imm_until and imm_until > now_utc():
            return await interaction.response.send_message(embed=embed_lose("🛡️ Sabotage bloqué", f"{cible.mention} est immunisé."), ephemeral=True)

        base_p = float(get_param_value(self.db, 'sabotage_success_rate'))
        win = random.random() < base_p
        win = maybe_flip_win_for_all_in(win, bal, cost)

        self.db.add_balance(interaction.user.id, -cost)

        if win:
            pct = float(get_param_value(self.db, 'sabotage_steal_pct'))
            cap = config.SABOTAGE_STEAL_CAP
            steal_amt = min(cap, max(0, int(int(victim["balance"]) * pct)))
            if steal_amt > 0:
                self.db.add_balance(cible.id, -steal_amt)
                self.db.add_balance(interaction.user.id, steal_amt)
            until = now_utc() + timedelta(minutes=config.SABOTAGE_BLOCK_MIN)
            self.db.set_user_field(cible.id, "sabotaged_until", until.isoformat())
            self.db.add_stat(interaction.user.id, wins_delta=1, games_delta=1)
            e = embed_win("🧨 Sabotage — Réussi")
            e.description = f"Tu paies **{fmt(cost)}** KZ et tu sabotes {cible.mention}."
            e.add_field(name="💸 Coût", value=f"{fmt(cost)} KZ", inline=True)
            e.add_field(name="💰 Vol", value=f"{fmt(steal_amt)} KZ", inline=True)
            e.add_field(name="⛔ Bloqué jusqu'à", value=until.strftime('%d/%m/%Y %H:%M UTC'), inline=False)
        else:
            self.db.add_stat(interaction.user.id, losses_delta=1, games_delta=1)
            e = embed_lose("🧨 Sabotage — Raté", f"Tu perds **{fmt(cost)}** KZ et tu rates ton sabotage.")

        self.db.set_user_field(interaction.user.id, "last_sabotage", now_utc().isoformat())
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
        return await interaction.response.send_message(embed=e)

    # ============================================
    # ALIAS (raccourcis de commandes)
    # ============================================

    @app_commands.command(name="bj", description="🎴 Alias de /blackjack")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')")
    async def bj(self, interaction: discord.Interaction, mise: str):
        await self.blackjack.callback(self, interaction, mise)

    @app_commands.command(name="sl", description="🎰 Alias de /slots")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')")
    async def sl(self, interaction: discord.Interaction, mise: str):
        await self.slots.callback(self, interaction, mise)

    @app_commands.command(name="rl", description="🎡 Alias de /roulette")
    @app_commands.describe(mise="Mise", choix="rouge/noir/vert/pair/impair/1-18/19-36/douzaine/numéro")
    async def rl(self, interaction: discord.Interaction, mise: str, choix: str):
        await self.roulette.callback(self, interaction, mise, choix)

    @app_commands.command(name="cf", description="🪙 Alias de /coinflip")
    @app_commands.describe(mise="Mise", choix="pile ou face")
    async def cf(self, interaction: discord.Interaction, mise: str, choix: str):
        await self.coinflip.callback(self, interaction, mise, choix)

    @app_commands.command(name="cr", description="🚀 Alias de /crash")
    @app_commands.describe(mise="Montant à miser (nombre ou 'all'/'max'/'tout')")
    async def cr(self, interaction: discord.Interaction, mise: str):
        await self.crash.callback(self, interaction, mise)


async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(GamesCog(bot, db))
