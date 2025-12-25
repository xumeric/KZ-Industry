# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import discord
from discord.ext import commands

from .. import config
from ..db import Database

# (Option) salon AFK à ignorer (mets l'ID sinon laisse None)
AFK_CHANNEL_ID: int | None = None

# (Option) limiter à certains salons textuels. None = tous
ALLOWED_TEXT_CHANNEL_IDS: set[int] | None = None


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


async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(ActivityRewardsCog(bot, db))
