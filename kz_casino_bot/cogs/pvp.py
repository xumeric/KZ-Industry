# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import Database
from ..utils import embed_info, embed_lose, embed_neutral, embed_win, fmt
from ..checks import enforce_blacklist


def _tunable_int(db: Database, name: str, default: int) -> int:
    v = db.get_setting(f"tunable_{name}")
    if v is None:
        return int(default)
    try:
        return int(float(v))
    except Exception:
        return int(default)


def _apply_tax(pot: int, tax_percent: int) -> tuple[int, int]:
    """Return (winner_gain, tax_amount)."""
    tax_percent = max(0, min(int(tax_percent), 100))
    tax = int(pot * tax_percent / 100)
    return max(0, pot - tax), max(0, tax)


def _get_win_gif(db: Database) -> str | None:
    try:
        enabled = _tunable_int(db, "win_gifs_enabled", 1)
        if int(enabled) != 1:
            return None
        raw = db.get_setting("win_gifs", "[]") or "[]"
        gifs = json.loads(raw)
        if not isinstance(gifs, list) or not gifs:
            return None
        return random.choice([g for g in gifs if isinstance(g, str) and g.strip()] )
    except Exception:
        return None




def _pick_bot_phrase(bot_won: bool) -> str:
    """Return a funny phrase. bot_won=True means player lost."""
    try:
        arr = config.BOT_WIN_PHRASES if bot_won else config.BOT_LOSS_PHRASES
        if isinstance(arr, list) and arr:
            return random.choice(arr)
    except Exception:
        pass
    # fallback
    return "🤖" if bot_won else "GG"


async def _resolve_vs_bot_public(channel: discord.abc.Messageable, db: Database, player_id: int, bet: int, bot_won: bool, title: str):
    """Public result embed for bot duels."""
    gif = _get_win_gif(db) or random.choice(getattr(config, 'DEFAULT_WIN_GIFS', []) or [None])
    phrase = _pick_bot_phrase(bot_won)

    if bot_won:
        desc = f"""<@{player_id}> vient de perdre contre le bot.

{phrase}

Perte: **{fmt(bet)} KZ**"""
        e = embed_lose(title, desc)
    else:
        kept = int(bet * _tunable_int(db, 'bot_loss_penalty', 50) / 100)
        desc = f"""<@{player_id}> a 'battu' le bot…

{phrase}

Perte: **{fmt(kept)} KZ** (le bot ne paye rien)"""
        e = embed_neutral(title, desc)
    if gif:
        try:
            e.set_image(url=str(gif))
        except Exception:
            pass

    try:
        await channel.send(embed=e)
    except Exception:
        pass
# --------------------
# RPS utilities
# --------------------

RPS_CHOICES = ("pierre", "feuille", "ciseaux")


def _rps_winner(a: str, b: str) -> int:
    """Return 0 tie, 1 if a wins, -1 if b wins."""
    a = a.lower()
    b = b.lower()
    if a == b:
        return 0
    wins = {
        "pierre": "ciseaux",
        "ciseaux": "feuille",
        "feuille": "pierre",
    }
    return 1 if wins.get(a) == b else -1


# --------------------
# Blackjack utilities
# --------------------

BJ_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
BJ_SUITS = ["♠", "♥", "♦", "♣"]


def _bj_draw(rng: random.Random) -> str:
    return f"{rng.choice(BJ_RANKS)}{rng.choice(BJ_SUITS)}"


def _bj_value(hand: list[str]) -> int:
    # Count A as 11 then adjust
    total = 0
    aces = 0
    for c in hand:
        rank = c[:-1]
        if rank in ("J", "Q", "K"):
            total += 10
        elif rank == "A":
            total += 11
            aces += 1
        else:
            total += int(rank)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def _bj_format_hand(hand: list[str]) -> str:
    return " ".join(hand)


@dataclass
class DuelSession:
    duel_type: str  # 'rps' | 'pvp' | 'bj'
    channel_id: int
    guild_id: int
    a_id: int
    b_id: int
    bet: int
    created_ts: float
    escrowed: bool = False

    # RPS / PVP
    a_choice: str | None = None
    b_choice: str | None = None

    # BJ
    rng_seed: int = 0
    a_hand: list[str] | None = None
    b_hand: list[str] | None = None
    a_done: bool = False
    b_done: bool = False


class DuelRequestView(discord.ui.View):
    def __init__(self, cog: "PVPCog", session: DuelSession):
        super().__init__(timeout=_tunable_int(cog.db, "pvp_timeout", 60))
        self.cog = cog
        self.session = session

    async def on_timeout(self):
        # If still pending and not escrowed, just disable.
        for child in self.children:
            child.disabled = True

    def _is_target(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.session.b_id

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._is_target(interaction):
            return await interaction.response.send_message("❌ Seul le joueur défié peut accepter.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        ok, msg = self.cog._start_session(self.session)
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)

        # Post the duel controller message in channel (public)
        channel = interaction.channel
        if not isinstance(channel, discord.abc.Messageable):
            return await interaction.followup.send("❌ Salon invalide.", ephemeral=True)

        if self.session.duel_type == "rps":
            view = RPSDuelView(self.cog, self.session)
            e = embed_info("✋ RPS 1v1", f"{interaction.guild.get_member(self.session.a_id).mention if interaction.guild else '<@'+str(self.session.a_id)+'>'} vs <@{self.session.b_id}>\nMise: **{fmt(self.session.bet)} KZ**\n\nClique sur un bouton pour choisir (choix privés en éphémère).")
            await channel.send(embed=e, view=view)
        elif self.session.duel_type == "pvp":
            view = QuickPVPView(self.cog, self.session)
            e = embed_info("⚔️ PvP", f"<@{self.session.a_id}> vs <@{self.session.b_id}>\nMise: **{fmt(self.session.bet)} KZ**\n\nChoisissez votre action (choix privés).")
            await channel.send(embed=e, view=view)
        else:
            view = Blackjack1v1LobbyView(self.cog, self.session)
            e = embed_info("🎴 Blackjack 1v1", f"<@{self.session.a_id}> vs <@{self.session.b_id}>\nMise: **{fmt(self.session.bet)} KZ**\n\nChaque joueur joue en privé (éphémère). Cliquez sur **Jouer**.")
            await channel.send(embed=e, view=view)

        # Ack privately
        await interaction.followup.send("✅ Duel lancé !", ephemeral=True)

        # Disable request buttons
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._is_target(interaction):
            return await interaction.response.send_message("❌ Seul le joueur défié peut refuser.", ephemeral=True)
        await interaction.response.send_message("✅ Duel refusé.", ephemeral=True)
        self.cog._cancel_session(self.session, refund=False)
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass


class RPSDuelView(discord.ui.View):
    def __init__(self, cog: "PVPCog", session: DuelSession):
        super().__init__(timeout=_tunable_int(cog.db, "pvp_timeout", 60))
        self.cog = cog
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.session.a_id, self.session.b_id):
            await interaction.response.send_message("❌ Ce duel ne te concerne pas.", ephemeral=True)
            return False
        return True

    async def _pick(self, interaction: discord.Interaction, choice: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id == self.session.a_id:
            self.session.a_choice = choice
        else:
            self.session.b_choice = choice

        await interaction.followup.send(f"✅ Choix enregistré: **{choice}**.", ephemeral=True)

        if self.session.a_choice and self.session.b_choice:
            await self._resolve(interaction)

    async def _resolve(self, interaction: discord.Interaction):
        # Resolve once
        sess = self.session
        res = _rps_winner(sess.a_choice or "", sess.b_choice or "")
        tax = _tunable_int(self.cog.db, "rps_tax", 5)
        pot = sess.bet * 2

        if res == 0:
            # tie => refund
            self.cog.db.add_balance(sess.a_id, sess.bet)
            self.cog.db.add_balance(sess.b_id, sess.bet)
            self.cog.db.add_pvp_stats(sess.a_id, games_delta=1)
            self.cog.db.add_pvp_stats(sess.b_id, games_delta=1)
            e = embed_neutral("✋ RPS 1v1 — Égalité", f"<@{sess.a_id}> a joué **{sess.a_choice}**\n<@{sess.b_id}> a joué **{sess.b_choice}**\n\nÉgalité → remboursement.")
        else:
            winner = sess.a_id if res == 1 else sess.b_id
            loser = sess.b_id if res == 1 else sess.a_id
            gain, tax_amount = _apply_tax(pot, tax)
            self.cog.db.add_balance(winner, gain)
            # stats
            self.cog.db.add_pvp_stats(winner, games_delta=1, wins_delta=1, profit_delta=gain - sess.bet)
            self.cog.db.add_pvp_stats(loser, games_delta=1, losses_delta=1, profit_delta=-sess.bet)
            e = embed_win("✋ RPS 1v1", f"<@{sess.a_id}>: **{sess.a_choice}**\n<@{sess.b_id}>: **{sess.b_choice}**\n\n🏆 Gagnant: <@{winner}>\nGain: **{fmt(gain)} KZ** (taxe {tax}% = {fmt(tax_amount)} KZ)")
        gif = _get_win_gif(self.cog.db)
        if gif:
            e.set_image(url=gif)

        # disable view
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass
        self.cog._forget_session(sess)
        await interaction.channel.send(embed=e)

    @discord.ui.button(label="🪨 Pierre", style=discord.ButtonStyle.secondary)
    async def pierre(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._pick(interaction, "pierre")

    @discord.ui.button(label="📄 Feuille", style=discord.ButtonStyle.secondary)
    async def feuille(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._pick(interaction, "feuille")

    @discord.ui.button(label="✂️ Ciseaux", style=discord.ButtonStyle.secondary)
    async def ciseaux(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._pick(interaction, "ciseaux")


class QuickPVPView(discord.ui.View):
    """Attaque / Défense / All-in."""

    def __init__(self, cog: "PVPCog", session: DuelSession):
        super().__init__(timeout=_tunable_int(cog.db, "pvp_timeout", 60))
        self.cog = cog
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.session.a_id, self.session.b_id):
            await interaction.response.send_message("❌ Ce duel ne te concerne pas.", ephemeral=True)
            return False
        return True

    async def _pick(self, interaction: discord.Interaction, choice: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id == self.session.a_id:
            self.session.a_choice = choice
        else:
            self.session.b_choice = choice
        await interaction.followup.send(f"✅ Action enregistrée: **{choice}**.", ephemeral=True)
        if self.session.a_choice and self.session.b_choice:
            await self._resolve(interaction)

    async def _resolve(self, interaction: discord.Interaction):
        sess = self.session
        a = (sess.a_choice or "").lower()
        b = (sess.b_choice or "").lower()
        # Règles type pierre/feuille/ciseaux
        beats = {"attaque": "defense", "defense": "allin", "allin": "attaque"}
        if a == b:
            res = 0
        elif beats.get(a) == b:
            res = 1
        else:
            res = -1

        tax = _tunable_int(self.cog.db, "pvp_tax", 5)
        pot = sess.bet * 2

        if res == 0:
            self.cog.db.add_balance(sess.a_id, sess.bet)
            self.cog.db.add_balance(sess.b_id, sess.bet)
            self.cog.db.add_pvp_stats(sess.a_id, games_delta=1)
            self.cog.db.add_pvp_stats(sess.b_id, games_delta=1)
            e = embed_neutral("⚔️ PvP — Égalité", f"<@{sess.a_id}>: **{a}**\n<@{sess.b_id}>: **{b}**\n\nÉgalité → remboursement.")
        else:
            winner = sess.a_id if res == 1 else sess.b_id
            loser = sess.b_id if res == 1 else sess.a_id
            gain, tax_amount = _apply_tax(pot, tax)
            self.cog.db.add_balance(winner, gain)
            self.cog.db.add_pvp_stats(winner, games_delta=1, wins_delta=1, profit_delta=gain - sess.bet)
            self.cog.db.add_pvp_stats(loser, games_delta=1, losses_delta=1, profit_delta=-sess.bet)
            e = embed_win("⚔️ PvP", f"<@{sess.a_id}>: **{a}**\n<@{sess.b_id}>: **{b}**\n\n🏆 Gagnant: <@{winner}>\nGain: **{fmt(gain)} KZ** (taxe {tax}% = {fmt(tax_amount)} KZ)")
        gif = _get_win_gif(self.cog.db)
        if gif:
            e.set_image(url=gif)

        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass
        self.cog._forget_session(sess)
        await interaction.channel.send(embed=e)

    @discord.ui.button(label="⚔️ Attaque", style=discord.ButtonStyle.secondary)
    async def attaque(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._pick(interaction, "attaque")

    @discord.ui.button(label="🛡️ Défense", style=discord.ButtonStyle.secondary)
    async def defense(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._pick(interaction, "defense")

    @discord.ui.button(label="🔥 All-in", style=discord.ButtonStyle.danger)
    async def allin(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._pick(interaction, "allin")


class Blackjack1v1LobbyView(discord.ui.View):
    def __init__(self, cog: "PVPCog", session: DuelSession):
        super().__init__(timeout=_tunable_int(cog.db, "pvp_timeout", 60))
        self.cog = cog
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.session.a_id, self.session.b_id):
            await interaction.response.send_message("❌ Ce duel ne te concerne pas.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎴 Jouer", style=discord.ButtonStyle.primary)
    async def play(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        view = BlackjackPrivateView(self.cog, self.session, interaction.user.id)
        embed = view._make_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class BlackjackPrivateView(discord.ui.View):
    def __init__(self, cog: "PVPCog", session: DuelSession, player_id: int):
        super().__init__(timeout=_tunable_int(cog.db, "pvp_timeout", 60))
        self.cog = cog
        self.session = session
        self.player_id = player_id

    def _get_hand(self) -> list[str]:
        if self.player_id == self.session.a_id:
            return self.session.a_hand or []
        return self.session.b_hand or []

    def _is_done(self) -> bool:
        return self.session.a_done if self.player_id == self.session.a_id else self.session.b_done

    def _set_done(self):
        if self.player_id == self.session.a_id:
            self.session.a_done = True
        else:
            self.session.b_done = True

    def _make_embed(self) -> discord.Embed:
        hand = self._get_hand()
        total = _bj_value(hand)
        status = "✅ Terminé" if self._is_done() else "En cours"
        e = embed_info("🎴 Blackjack 1v1", f"**Ta main:** {_bj_format_hand(hand)}\n**Total:** {total}\n**Statut:** {status}")
        e.set_footer(text="Hit pour tirer une carte • Stand pour finir")
        return e

    async def _maybe_finish(self, interaction: discord.Interaction):
        # If bust, auto-stand
        hand = self._get_hand()
        if _bj_value(hand) > 21:
            self._set_done()

        if self.session.a_done and self.session.b_done:
            await self.cog._resolve_blackjack(interaction, self.session)

    @discord.ui.button(label="➕ Hit", style=discord.ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("❌ Ce menu ne t'appartient pas.", ephemeral=True)
        if self._is_done():
            return await interaction.response.send_message("Déjà terminé.", ephemeral=True)
        # draw (deterministic, but without repeating the same card)
        hand = self._get_hand()
        seed = int(self.session.rng_seed) + int(self.player_id) * 1000 + len(hand) * 17
        rng = random.Random(seed)
        card = _bj_draw(rng)
        if self.player_id == self.session.a_id:
            self.session.a_hand = (self.session.a_hand or []) + [card]
        else:
            self.session.b_hand = (self.session.b_hand or []) + [card]

        await interaction.response.edit_message(embed=self._make_embed(), view=self)
        await self._maybe_finish(interaction)

    @discord.ui.button(label="✋ Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("❌ Ce menu ne t'appartient pas.", ephemeral=True)
        if self._is_done():
            return await interaction.response.send_message("Déjà terminé.", ephemeral=True)
        self._set_done()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)
        await self._maybe_finish(interaction)


class PVPCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db
        # active sessions in memory: key = (type, a_id, b_id, created_ts)
        self.sessions: dict[str, DuelSession] = {}

    async def cog_app_command_invoke(self, interaction: discord.Interaction):
        allowed = await enforce_blacklist(self.db, interaction)
        if not allowed:
            raise app_commands.CheckFailure("Blacklisted")

    # ---------- internal helpers ----------
    def _session_key(self, s: DuelSession) -> str:
        return f"{s.duel_type}:{s.a_id}:{s.b_id}:{int(s.created_ts)}"

    def _forget_session(self, s: DuelSession) -> None:
        self.sessions.pop(self._session_key(s), None)

    def _cancel_session(self, s: DuelSession, refund: bool = True) -> None:
        if refund and s.escrowed:
            self.db.add_balance(s.a_id, s.bet)
            self.db.add_balance(s.b_id, s.bet)
        self._forget_session(s)

    def _start_session(self, s: DuelSession) -> tuple[bool, str]:
        # Ensure users and take escrow
        self.db.ensure_user(s.a_id, config.START_BALANCE)
        self.db.ensure_user(s.b_id, config.START_BALANCE)
        a_bal = int(self.db.get_user(s.a_id)["balance"])
        b_bal = int(self.db.get_user(s.b_id)["balance"])
        if a_bal < s.bet:
            return False, "❌ Le challenger n'a pas assez de KZ."
        if b_bal < s.bet:
            return False, "❌ Le joueur défié n'a pas assez de KZ."
        self.db.add_balance(s.a_id, -s.bet)
        self.db.add_balance(s.b_id, -s.bet)
        s.escrowed = True

        if s.duel_type == "bj":
            s.rng_seed = int(time.time())
            rng = random.Random(s.rng_seed)
            s.a_hand = [_bj_draw(rng), _bj_draw(rng)]
            s.b_hand = [_bj_draw(rng), _bj_draw(rng)]

        self.sessions[self._session_key(s)] = s
        return True, "ok"

    async def _resolve_blackjack(self, interaction: discord.Interaction, s: DuelSession):
        # Compute values
        a_v = _bj_value(s.a_hand or [])
        b_v = _bj_value(s.b_hand or [])
        a_bust = a_v > 21
        b_bust = b_v > 21
        pot = s.bet * 2
        tax = _tunable_int(self.db, "blackjack1v1_tax", 5)

        if (a_bust and b_bust) or (a_v == b_v):
            # tie
            self.db.add_balance(s.a_id, s.bet)
            self.db.add_balance(s.b_id, s.bet)
            self.db.add_pvp_stats(s.a_id, games_delta=1)
            self.db.add_pvp_stats(s.b_id, games_delta=1)
            e = embed_neutral(
                "🎴 Blackjack 1v1 — Égalité",
                f"<@{s.a_id}>: {_bj_format_hand(s.a_hand or [])} → **{a_v}**\n"
                f"<@{s.b_id}>: {_bj_format_hand(s.b_hand or [])} → **{b_v}**\n\n"
                "Égalité → remboursement.",
            )
        else:
            # winner is closest to 21 without bust
            def score(v: int) -> int:
                return -999 if v > 21 else v

            winner = s.a_id if score(a_v) > score(b_v) else s.b_id
            loser = s.b_id if winner == s.a_id else s.a_id
            gain, tax_amount = _apply_tax(pot, tax)
            self.db.add_balance(winner, gain)
            self.db.add_pvp_stats(winner, games_delta=1, wins_delta=1, profit_delta=gain - s.bet)
            self.db.add_pvp_stats(loser, games_delta=1, losses_delta=1, profit_delta=-s.bet)
            e = embed_win(
                "🎴 Blackjack 1v1",
                f"<@{s.a_id}>: {_bj_format_hand(s.a_hand or [])} → **{a_v}**\n"
                f"<@{s.b_id}>: {_bj_format_hand(s.b_hand or [])} → **{b_v}**\n\n"
                f"🏆 Gagnant: <@{winner}>\nGain: **{fmt(gain)} KZ** (taxe {tax}% = {fmt(tax_amount)} KZ)",
            )

        self._forget_session(s)
        try:
            await interaction.channel.send(embed=e)
        except Exception:
            pass

    # ---------- commands ----------

    @app_commands.command(name="rps1v1", description="✋ Pierre/Feuille/Ciseaux en 1v1 (mise)")
    @app_commands.describe(adversaire="Le joueur à défier", mise="Mise en KZ")
    async def rps1v1(self, interaction: discord.Interaction, adversaire: discord.Member, mise: app_commands.Range[int, 1, 100_000_000]):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        if adversaire.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_lose("❌ Duel", "Choisis un autre joueur."), ephemeral=True)

        # Duel contre le bot (auto-accept + 99% win bot)
        if adversaire.bot:
            enabled = _tunable_int(self.db, "bot_enabled", 1)
            if int(enabled) != 1:
                return await interaction.response.send_message(embed=embed_lose("❌ Duel", "Le duel contre le bot est désactivé."), ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            self.db.ensure_user(interaction.user.id, config.START_BALANCE)
            row = self.db.get_user(interaction.user.id)
            bal = int(row["balance"]) if row else 0
            bet = int(mise)
            if bet > bal:
                return await interaction.followup.send("❌ Solde insuffisant.", ephemeral=True)
            # escrow: on retire la mise
            self.db.add_balance(interaction.user.id, -bet)

            chance = _tunable_int(self.db, "bot_win_chance", 99)
            bot_won = (random.randint(1, 100) <= int(chance))

            if bot_won:
                # joueur perd contre le bot
                self.db.add_bot_stats(interaction.user.id, bot_win=False)
                self.db.add_pvp_stats(interaction.user.id, games_delta=1, losses_delta=1, profit_delta=-bet)
            else:
                # le joueur "bat" le bot, mais le bot ne paye rien (le joueur perd une partie de sa mise)
                penalty_pct = _tunable_int(self.db, "bot_loss_penalty", 50)
                kept = int(bet * int(penalty_pct) / 100)
                refund = max(0, bet - kept)
                if refund:
                    self.db.add_balance(interaction.user.id, refund)
                self.db.add_bot_stats(interaction.user.id, bot_win=True)
                # on compte ça comme une win PvP (mais profit négatif car le joueur perd quand même)
                self.db.add_pvp_stats(interaction.user.id, games_delta=1, wins_delta=1, profit_delta=-kept)

            await interaction.followup.send("✅ Duel contre le bot terminé !", ephemeral=True)
            try:
                await _resolve_vs_bot_public(interaction.channel, self.db, interaction.user.id, bet, bot_won, "✋ RPS 1v1 — vs Bot")
            except Exception:
                pass
            return

        s = DuelSession("rps", interaction.channel_id, interaction.guild_id or 0, interaction.user.id, adversaire.id, int(mise), time.time())
        view = DuelRequestView(self, s)
        e = embed_info("✋ RPS 1v1", f"<@{s.a_id}> défie {adversaire.mention}\nMise: **{fmt(s.bet)} KZ**\n\n{adversaire.mention} : clique sur **Accepter** ou **Refuser**.")
        await interaction.response.send_message(embed=e, view=view)

    @app_commands.command(name="pvp", description="⚔️ Duel rapide Attaque/Défense/All-in (mise)")
    @app_commands.describe(adversaire="Le joueur à défier", mise="Mise en KZ")
    async def pvp(self, interaction: discord.Interaction, adversaire: discord.Member, mise: app_commands.Range[int, 1, 100_000_000]):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        if adversaire.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_lose("❌ Duel", "Choisis un autre joueur."), ephemeral=True)

        # Duel contre le bot (auto-accept + 99% win bot)
        if adversaire.bot:
            enabled = _tunable_int(self.db, "bot_enabled", 1)
            if int(enabled) != 1:
                return await interaction.response.send_message(embed=embed_lose("❌ Duel", "Le duel contre le bot est désactivé."), ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            self.db.ensure_user(interaction.user.id, config.START_BALANCE)
            row = self.db.get_user(interaction.user.id)
            bal = int(row["balance"]) if row else 0
            bet = int(mise)
            if bet > bal:
                return await interaction.followup.send("❌ Solde insuffisant.", ephemeral=True)
            # escrow: on retire la mise
            self.db.add_balance(interaction.user.id, -bet)

            chance = _tunable_int(self.db, "bot_win_chance", 99)
            bot_won = (random.randint(1, 100) <= int(chance))

            if bot_won:
                # joueur perd contre le bot
                self.db.add_bot_stats(interaction.user.id, bot_win=False)
                self.db.add_pvp_stats(interaction.user.id, games_delta=1, losses_delta=1, profit_delta=-bet)
            else:
                # le joueur "bat" le bot, mais le bot ne paye rien (le joueur perd une partie de sa mise)
                penalty_pct = _tunable_int(self.db, "bot_loss_penalty", 50)
                kept = int(bet * int(penalty_pct) / 100)
                refund = max(0, bet - kept)
                if refund:
                    self.db.add_balance(interaction.user.id, refund)
                self.db.add_bot_stats(interaction.user.id, bot_win=True)
                # on compte ça comme une win PvP (mais profit négatif car le joueur perd quand même)
                self.db.add_pvp_stats(interaction.user.id, games_delta=1, wins_delta=1, profit_delta=-kept)

            await interaction.followup.send("✅ Duel contre le bot terminé !", ephemeral=True)
            try:
                await _resolve_vs_bot_public(interaction.channel, self.db, interaction.user.id, bet, bot_won, "⚔️ PvP — vs Bot")
            except Exception:
                pass
            return
        s = DuelSession("pvp", interaction.channel_id, interaction.guild_id or 0, interaction.user.id, adversaire.id, int(mise), time.time())
        view = DuelRequestView(self, s)
        e = embed_info("⚔️ PvP", f"<@{s.a_id}> défie {adversaire.mention}\nMise: **{fmt(s.bet)} KZ**\n\n{adversaire.mention} : clique sur **Accepter** ou **Refuser**.")
        await interaction.response.send_message(embed=e, view=view)

    @app_commands.command(name="blackjack1v1", description="🎴 Blackjack en 1v1 (simultané)")
    @app_commands.describe(adversaire="Le joueur à défier", mise="Mise en KZ")
    async def blackjack1v1(self, interaction: discord.Interaction, adversaire: discord.Member, mise: app_commands.Range[int, 1, 100_000_000]):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        if adversaire.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_lose("❌ Duel", "Choisis un autre joueur."), ephemeral=True)

        # Duel contre le bot (auto-accept + 99% win bot)
        if adversaire.bot:
            enabled = _tunable_int(self.db, "bot_enabled", 1)
            if int(enabled) != 1:
                return await interaction.response.send_message(embed=embed_lose("❌ Duel", "Le duel contre le bot est désactivé."), ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            self.db.ensure_user(interaction.user.id, config.START_BALANCE)
            row = self.db.get_user(interaction.user.id)
            bal = int(row["balance"]) if row else 0
            bet = int(mise)
            if bet > bal:
                return await interaction.followup.send("❌ Solde insuffisant.", ephemeral=True)
            # escrow: on retire la mise
            self.db.add_balance(interaction.user.id, -bet)

            chance = _tunable_int(self.db, "bot_win_chance", 99)
            bot_won = (random.randint(1, 100) <= int(chance))

            if bot_won:
                # joueur perd contre le bot
                self.db.add_bot_stats(interaction.user.id, bot_win=False)
                self.db.add_pvp_stats(interaction.user.id, games_delta=1, losses_delta=1, profit_delta=-bet)
            else:
                # le joueur "bat" le bot, mais le bot ne paye rien (le joueur perd une partie de sa mise)
                penalty_pct = _tunable_int(self.db, "bot_loss_penalty", 50)
                kept = int(bet * int(penalty_pct) / 100)
                refund = max(0, bet - kept)
                if refund:
                    self.db.add_balance(interaction.user.id, refund)
                self.db.add_bot_stats(interaction.user.id, bot_win=True)
                # on compte ça comme une win PvP (mais profit négatif car le joueur perd quand même)
                self.db.add_pvp_stats(interaction.user.id, games_delta=1, wins_delta=1, profit_delta=-kept)

            await interaction.followup.send("✅ Duel contre le bot terminé !", ephemeral=True)
            try:
                await _resolve_vs_bot_public(interaction.channel, self.db, interaction.user.id, bet, bot_won, "🎴 Blackjack 1v1 — vs Bot")
            except Exception:
                pass
            return
        s = DuelSession("bj", interaction.channel_id, interaction.guild_id or 0, interaction.user.id, adversaire.id, int(mise), time.time())
        view = DuelRequestView(self, s)
        e = embed_info("🎴 Blackjack 1v1", f"<@{s.a_id}> défie {adversaire.mention}\nMise: **{fmt(s.bet)} KZ**\n\n{adversaire.mention} : clique sur **Accepter** ou **Refuser**.")
        await interaction.response.send_message(embed=e, view=view)

    @app_commands.command(name="pvp_stats", description="📊 Tes stats PvP")
    async def pvp_stats(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        if not row:
            return await interaction.response.send_message(embed=embed_neutral("📊 PvP", "Aucune donnée."), ephemeral=True)
        # sqlite3.Row doesn't support .get
        g = int(row["pvp_games"]) if "pvp_games" in row.keys() else 0
        w = int(row["pvp_wins"]) if "pvp_wins" in row.keys() else 0
        l = int(row["pvp_losses"]) if "pvp_losses" in row.keys() else 0
        p = int(row["pvp_profit"]) if "pvp_profit" in row.keys() else 0
        e = embed_neutral("📊 PvP", f"Parties: **{g}**\nVictoires: **{w}**\nDéfaites: **{l}**\nProfit: **{fmt(p)} KZ**")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="botstats", description="🤖 Tes stats contre le bot")
    async def botstats(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        if not row:
            return await interaction.response.send_message(embed=embed_neutral("🤖 Stats bot", "Aucune donnée."), ephemeral=True)
        bw = int(row["bot_wins"]) if "bot_wins" in row.keys() else 0
        bl = int(row["bot_losses"]) if "bot_losses" in row.keys() else 0
        e = embed_neutral("🤖 Stats contre le bot", f"Victoires (1%): **{bw}**\nDéfaites: **{bl}**")
        await interaction.response.send_message(embed=e, ephemeral=True)



async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(PVPCog(bot, db))
