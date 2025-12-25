# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands

from . import config
from .db import Database
from .utils import embed_lose, human_time, now_utc, parse_dt


def is_owner(interaction: discord.Interaction) -> bool:
    return config.OWNER_ID and interaction.user.id == config.OWNER_ID


def is_bot_admin(db: Database, interaction: discord.Interaction) -> bool:
    if is_owner(interaction):
        return True
    return db.is_bot_admin(interaction.user.id)


async def enforce_blacklist(db: Database, interaction: discord.Interaction) -> bool:
    """Return True if allowed, False if blocked."""
    if is_owner(interaction):
        return True

    row = db.bl_get(interaction.user.id)
    if not row:
        return True

    expires_at = parse_dt(row["expires_at"])
    if expires_at and expires_at <= now_utc():
        db.bl_remove(interaction.user.id)
        return True

    reason = row["reason"] or "Aucune raison fournie"
    desc = f"Tu es blacklisté du bot.\n\n**Raison :** {reason}"
    if expires_at:
        left = int((expires_at - now_utc()).total_seconds())
        desc += f"\n**Fin :** dans {human_time(left)}"
    e = embed_lose("⛔ Accès refusé", desc)
    if interaction.response.is_done():
        await interaction.followup.send(embed=e, ephemeral=True)
    else:
        await interaction.response.send_message(embed=e, ephemeral=True)
    return False


def admin_only(db: Database):
    async def predicate(interaction: discord.Interaction):
        if is_bot_admin(db, interaction):
            return True
        raise app_commands.CheckFailure("Admin bot requis")

    return app_commands.check(predicate)


def owner_only():
    async def predicate(interaction: discord.Interaction):
        if is_owner(interaction):
            return True
        raise app_commands.CheckFailure("Owner requis")

    return app_commands.check(predicate)
