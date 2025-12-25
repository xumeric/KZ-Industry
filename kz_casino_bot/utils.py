# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import random

import discord

from . import config


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(s: str | None) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def seconds_left(last_iso: str | None, cooldown_seconds: int) -> int:
    last = parse_dt(last_iso)
    if not last:
        return 0
    end = last + timedelta(seconds=cooldown_seconds)
    return max(0, int((end - now_utc()).total_seconds()))


def embed_info(title: str, desc: str | None = None, extra: str | None = None) -> discord.Embed:
    description = desc or ""
    if extra:
        description = f"{desc}\n{extra}" if desc else extra
    e = discord.Embed(title=title, description=description, color=config.BRAND["info"])
    e.set_footer(text=config.BRAND["name"])
    e.timestamp = now_utc()
    return e


def embed_win(title: str, desc: str | None = None, extra: str | None = None) -> discord.Embed:
    description = desc or ""
    if extra:
        description = f"{desc}\n{extra}" if desc else extra
    e = discord.Embed(title=title, description=description, color=config.BRAND["win"])
    e.set_footer(text=config.BRAND["name"])
    e.timestamp = now_utc()
    return e


def embed_lose(title: str, desc: str | None = None, extra: str | None = None) -> discord.Embed:
    description = desc or ""
    if extra:
        description = f"{desc}\n{extra}" if desc else extra
    e = discord.Embed(title=title, description=description, color=config.BRAND["lose"])
    e.set_footer(text=config.BRAND["name"])
    e.timestamp = now_utc()
    return e


def embed_neutral(title: str, desc: str | None = None, extra: str | None = None) -> discord.Embed:
    description = desc or ""
    if extra:
        description = f"{desc}\n{extra}" if desc else extra
    e = discord.Embed(title=title, description=description, color=config.BRAND["neutral"])
    e.set_footer(text=config.BRAND["name"])
    e.timestamp = now_utc()
    return e


@dataclass
class BetCheckResult:
    ok: bool
    reason: str = ""


def check_bet(balance: int, bet: int) -> BetCheckResult:
    if bet < config.MIN_BET:
        return BetCheckResult(False, f"Mise minimum: **{fmt(config.MIN_BET)}**")
    # Allow true all-in even if it exceeds MAX_BET (optional)
    if bet > config.MAX_BET and not (config.ALLOW_ALL_IN_OVER_MAX_BET and bet == balance):
        return BetCheckResult(False, f"Mise maximum: **{fmt(config.MAX_BET)}**")
    if bet > balance:
        return BetCheckResult(False, "Tu n'as pas assez de coins.")
    return BetCheckResult(True)


def human_time(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}j")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s and not d:
        parts.append(f"{s}s")
    return " ".join(parts)


def all_in_scale(balance: int, bet: int) -> float:
    """Return 0..1 depending on how close bet is to balance (all-in).
    Used to bias outcomes against the player when they go (almost) all-in.
    """
    if balance <= 0 or bet <= 0:
        return 0.0
    if balance < config.ALL_IN_MIN_BALANCE:
        return 0.0
    ratio = bet / float(balance)
    if ratio < config.ALL_IN_THRESHOLD:
        return 0.0
    # scale from threshold..1 -> 0..1
    return max(0.0, min(1.0, (ratio - config.ALL_IN_THRESHOLD) / max(1e-9, (1.0 - config.ALL_IN_THRESHOLD))))


def maybe_flip_win_for_all_in(win: bool, balance: int, bet: int, rng: random.Random | None = None) -> bool:
    """If player wins but went (almost) all-in, sometimes flip to a loss.
    This creates a stronger house edge for all-in behavior.
    """
    if not win:
        return False
    s = all_in_scale(balance, bet)
    if s <= 0:
        return True
    r = rng or random
    p = config.ALL_IN_MAX_WIN_FLIP_P * s
    return False if (r.random() < p) else True
