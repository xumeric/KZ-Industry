# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import Database
from ..utils import fmt

# (Option) salon AFK à ignorer (mets l'ID sinon laisse None)
AFK_CHANNEL_ID: int | None = None

# (Option) limiter à certains salons textuels. None = tous
ALLOWED_TEXT_CHANNEL_IDS: set[int] | None = None


def format_duration(seconds: int) -> str:
    """Formate une durée en heures/minutes/secondes"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


class ActivityRewardsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db
        self._last_msg_ts: dict[int, float] = {}
        self._voice_join_ts: dict[int, float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return
        if ALLOWED_TEXT_CHANNEL_IDS is not None and message.channel.id not in ALLOWED_TEXT_CHANNEL_IDS:
            return

        uid = message.author.id
        now = time.time()

        cooldown = int(getattr(config, "ACTIVITY_MSG_COOLDOWN_SECONDS", 15))
        last = self._last_msg_ts.get(uid, 0.0)
        if now - last < cooldown:
            return
        self._last_msg_ts[uid] = now

        self.db.ensure_user(uid, config.START_BALANCE)
        total = self.db.activity_add_message(uid, 1)

        # XP (progression difficile)
        try:
            xp_gain = int(getattr(config, "XP_PER_ACTIVITY_MESSAGE", 10))
            if xp_gain > 0:
                self.db.add_xp(uid, xp_gain)
        except Exception:
            pass

        target = int(getattr(config, "ACTIVITY_MSG_TARGET", 100))
        reward = int(getattr(config, "ACTIVITY_MSG_REWARD", 100))
        if target > 0 and total % target == 0:
            self.db.add_balance(uid, reward)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        uid = member.id
        now = time.time()

        def valid(vs: discord.VoiceState | None) -> bool:
            if not vs or not vs.channel:
                return False
            if AFK_CHANNEL_ID and vs.channel.id == AFK_CHANNEL_ID:
                return False
            return True

        was_valid = valid(before)
        is_valid = valid(after)

        if was_valid and not is_valid:
            start = self._voice_join_ts.pop(uid, None)
            if start:
                delta = int(now - start)
                if delta > 0:
                    self._apply_voice_time(uid, delta)

        if not was_valid and is_valid:
            self._voice_join_ts[uid] = now

    def _apply_voice_time(self, user_id: int, seconds: int):
        self.db.ensure_user(user_id, config.START_BALANCE)

        total = self.db.activity_add_voice_seconds(user_id, seconds)

        # XP vocal (par minute)
        try:
            per_min = int(getattr(config, "XP_PER_VOICE_MINUTE", 4))
            mins = int(seconds) // 60
            xp_gain = per_min * mins
            if xp_gain > 0:
                self.db.add_xp(user_id, xp_gain)
        except Exception:
            pass

        target = int(getattr(config, "ACTIVITY_VOICE_TARGET_SECONDS", 3600))
        reward = int(getattr(config, "ACTIVITY_VOICE_REWARD", 1000))
        if target <= 0:
            return

        earned_before = (total - seconds) // target
        earned_after = total // target
        diff = earned_after - earned_before
        if diff > 0:
            self.db.add_balance(user_id, reward * diff)

    @app_commands.command(name="activite", description="📊 Voir tes récompenses d'activité (messages + vocal)")
    async def activite(self, interaction: discord.Interaction):
        uid = interaction.user.id
        self.db.ensure_user(uid, config.START_BALANCE)
        
        # Récupérer les données d'activité
        data = self.db.activity_get(uid)
        msg_count = data["msg_count"] if data else 0
        voice_seconds = data["voice_seconds"] if data else 0
        
        # Paramètres
        msg_target = int(getattr(config, "ACTIVITY_MSG_TARGET", 100))
        msg_reward = int(getattr(config, "ACTIVITY_MSG_REWARD", 100))
        voice_target = int(getattr(config, "ACTIVITY_VOICE_TARGET_SECONDS", 3600))
        voice_reward = int(getattr(config, "ACTIVITY_VOICE_REWARD", 1000))
        
        # Calculs messages
        msg_rewards_earned = msg_count // msg_target if msg_target > 0 else 0
        msg_total_kz = msg_rewards_earned * msg_reward
        msg_progress = msg_count % msg_target if msg_target > 0 else 0
        msg_remaining = msg_target - msg_progress if msg_target > 0 else 0
        
        # Calculs vocal
        voice_rewards_earned = voice_seconds // voice_target if voice_target > 0 else 0
        voice_total_kz = voice_rewards_earned * voice_reward
        voice_progress = voice_seconds % voice_target if voice_target > 0 else 0
        voice_remaining = voice_target - voice_progress if voice_target > 0 else 0
        
        # Temps en vocal actuellement (si connecté)
        current_voice_time = 0
        if uid in self._voice_join_ts:
            current_voice_time = int(time.time() - self._voice_join_ts[uid])
        
        # Total KZ gagné
        total_kz = msg_total_kz + voice_total_kz
        
        # Créer l'embed
        embed = discord.Embed(
            title="📊 Activité",
            description=f"Récompenses d'activité de {interaction.user.mention}",
            color=0x2ecc71
        )
        
        # Section Messages
        msg_bar = self._progress_bar(msg_progress, msg_target)
        embed.add_field(
            name="💬 Messages",
            value=(
                f"**Total envoyés:** {fmt(msg_count)}\n"
                f"**Récompenses obtenues:** {msg_rewards_earned}x ({fmt(msg_total_kz)} KZ)\n"
                f"**Progression:** {msg_progress}/{msg_target}\n"
                f"{msg_bar}\n"
                f"**Restant:** {msg_remaining} messages → +{fmt(msg_reward)} KZ"
            ),
            inline=False
        )
        
        # Section Vocal
        voice_bar = self._progress_bar(voice_progress, voice_target)
        voice_status = ""
        if current_voice_time > 0:
            voice_status = f"\n🎙️ **En vocal:** {format_duration(current_voice_time)}"
        
        embed.add_field(
            name="🎤 Vocal",
            value=(
                f"**Temps total:** {format_duration(voice_seconds)}\n"
                f"**Récompenses obtenues:** {voice_rewards_earned}x ({fmt(voice_total_kz)} KZ)\n"
                f"**Progression:** {format_duration(voice_progress)}/{format_duration(voice_target)}\n"
                f"{voice_bar}\n"
                f"**Restant:** {format_duration(voice_remaining)} → +{fmt(voice_reward)} KZ"
                f"{voice_status}"
            ),
            inline=False
        )
        
        # Total
        embed.add_field(
            name="💰 Total gagné en activité",
            value=f"**{fmt(total_kz)} KZ**",
            inline=False
        )
        
        embed.set_footer(text="Continue à discuter et rester en vocal pour gagner des KZ !")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="av", description="📊 Alias de /activite")
    async def av(self, interaction: discord.Interaction):
        await self.activite(interaction)
    
    def _progress_bar(self, current: int, total: int, length: int = 10) -> str:
        """Génère une barre de progression"""
        if total <= 0:
            return "▓" * length
        ratio = min(current / total, 1.0)
        filled = int(ratio * length)
        empty = length - filled
        percentage = int(ratio * 100)
        return f"{'█' * filled}{'░' * empty} {percentage}%"


async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(ActivityRewardsCog(bot, db))
