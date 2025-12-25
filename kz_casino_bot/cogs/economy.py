# -*- coding: utf-8 -*-
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import Database
from ..shop_data import get_item
from ..utils import (
    BetCheckResult,
    check_bet,
    embed_info,
    embed_lose,
    embed_neutral,
    embed_win,
    fmt,
    human_time,
    now_utc,
    seconds_left,
)
from ..checks import enforce_blacklist


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    async def cog_app_command_invoke(self, interaction: discord.Interaction):
        allowed = await enforce_blacklist(self.db, interaction)
        if not allowed:
            raise app_commands.CheckFailure("Blacklisted")

    # ---------- core ----------
    @app_commands.command(name="register", description="Créer ton compte casino")
    async def register(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        e = embed_win("✅ Inscription", f"Compte créé !\nSolde: **{fmt(int(row['balance']))}** KZ")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="balance", description="Voir ton solde")
    async def balance(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        e = embed_neutral("🏦 Solde", f"Tu as **{fmt(int(row['balance']))}** KZ coins.")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="daily", description="Récupérer ton bonus daily")
    async def daily(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        left = seconds_left(row["last_daily"], config.DAILY_COOLDOWN_H * 3600)
        if left > 0:
            e = embed_lose("⏳ Daily", f"Reviens dans **{human_time(left)}**.")
            return await interaction.response.send_message(embed=e)
        self.db.add_balance(interaction.user.id, config.DAILY_AMOUNT)
        self.db.set_user_field(interaction.user.id, "last_daily", now_utc().isoformat())
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e = embed_win("🎁 Daily", f"Tu gagnes **{fmt(config.DAILY_AMOUNT)}** KZ !")
        e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="weekly", description="Récupérer ton bonus weekly")
    async def weekly(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        left = seconds_left(row["last_weekly"], config.WEEKLY_COOLDOWN_D * 86400)
        if left > 0:
            e = embed_lose("⏳ Weekly", f"Reviens dans **{human_time(left)}**.")
            return await interaction.response.send_message(embed=e)
        self.db.add_balance(interaction.user.id, config.WEEKLY_AMOUNT)
        self.db.set_user_field(interaction.user.id, "last_weekly", now_utc().isoformat())
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e = embed_win("🎁 Weekly", f"Tu gagnes **{fmt(config.WEEKLY_AMOUNT)}** KZ !")
        e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="work", description="Gagner un petit montant")
    async def work(self, interaction: discord.Interaction):
        import random

        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        left = seconds_left(row["last_work"], config.WORK_COOLDOWN_MIN * 60)
        if left > 0:
            e = embed_lose("⏳ Travail", f"Reviens dans **{human_time(left)}**.")
            return await interaction.response.send_message(embed=e)
        gain = random.randint(config.WORK_MIN, config.WORK_MAX)
        self.db.add_balance(interaction.user.id, gain)
        self.db.set_user_field(interaction.user.id, "last_work", now_utc().isoformat())
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e = embed_win("🛠️ Travail", f"Tu as gagné **{fmt(gain)}** KZ.")
        e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="transfer", description="Virer des coins à un joueur")
    async def transfer(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, 100000000]):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        self.db.ensure_user(user.id, config.START_BALANCE)
        if user.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_lose("❌ Virement", "Tu ne peux pas te virer à toi-même."))

        sender = self.db.get_user(interaction.user.id)
        bal = int(sender["balance"])
        if amount > bal:
            return await interaction.response.send_message(embed=embed_lose("❌ Virement", "Solde insuffisant."))

        tax = int(amount * (config.TRANSFER_TAX_PCT / 100.0))
        send_net = max(0, amount - tax)

        self.db.add_balance(interaction.user.id, -amount)
        self.db.add_balance(user.id, send_net)

        e = embed_info("💸 Virement", f"Tu as envoyé **{fmt(send_net)}** KZ à {user.mention}.")
        e.add_field(name="Taxe", value=f"{fmt(tax)} KZ ({config.TRANSFER_TAX_PCT}%)", inline=True)
        e.add_field(name="Montant débité", value=f"{fmt(amount)} KZ", inline=True)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="leaderboard", description="Top des joueurs")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = self.db.fetchall("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
        if not rows:
            return await interaction.response.send_message(embed=embed_info("🏆 Leaderboard", "Aucun joueur pour le moment."))
        lines = []
        for i, r in enumerate(rows, start=1):
            uid = int(r["user_id"])
            bal = int(r["balance"])
            lines.append(f"**{i}.** <@{uid}> — **{fmt(bal)}** KZ")
        e = embed_info("🏆 Leaderboard", "\n".join(lines))
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="cooldowns", description="Voir tes cooldowns")
    async def cooldowns(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)

        daily_left = seconds_left(row["last_daily"], config.DAILY_COOLDOWN_H * 3600)
        weekly_left = seconds_left(row["last_weekly"], config.WEEKLY_COOLDOWN_D * 86400)
        work_left = seconds_left(row["last_work"], config.WORK_COOLDOWN_MIN * 60)

        # chest cooldown depends on VIP
        vip_until = row["vip_until"]
        from ..utils import parse_dt
        vip_dt = parse_dt(vip_until)
        is_vip = bool(vip_dt and vip_dt > now_utc())
        chest_cd_h = config.CHEST_COOLDOWN_VIP_H if is_vip else config.CHEST_COOLDOWN_NORMAL_H
        chest_left = seconds_left(row["last_chest"], int(chest_cd_h * 3600))
        steal_left = seconds_left(row["last_steal"], config.STEAL_COOLDOWN_H * 3600)

        e = embed_neutral("⏱️ Cooldowns")
        e.add_field(name="Daily", value=("✅" if daily_left == 0 else human_time(daily_left)), inline=True)
        e.add_field(name="Weekly", value=("✅" if weekly_left == 0 else human_time(weekly_left)), inline=True)
        e.add_field(name="Work", value=("✅" if work_left == 0 else human_time(work_left)), inline=True)
        e.add_field(name="Chest", value=("✅" if chest_left == 0 else human_time(chest_left)), inline=True)
        e.add_field(name="Steal", value=("✅" if steal_left == 0 else human_time(steal_left)), inline=True)
        e.add_field(name="VIP", value=("✅" if is_vip else "❌"), inline=True)
        await interaction.response.send_message(embed=e)


    # -------- Gifts (joueur -> joueur) --------
    gift_group = app_commands.Group(name="gift", description="Offrir des coins ou des items à un joueur")

    @gift_group.command(name="coins", description="Offrir des coins à un joueur")
    async def gift_coins(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100000000],
    ):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        self.db.ensure_user(user.id, config.START_BALANCE)
        if user.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_lose("❌ Gift", "Tu ne peux pas t'offrir des coins à toi-même."))

        sender = self.db.get_user(interaction.user.id)
        bal = int(sender["balance"])
        if amount > bal:
            return await interaction.response.send_message(embed=embed_lose("❌ Gift", "Solde insuffisant."))

        tax = int(amount * (getattr(config, "GIFT_TAX_PCT", 0.0) / 100.0))
        net = max(0, amount - tax)

        self.db.add_balance(interaction.user.id, -amount)
        self.db.add_balance(user.id, net)

        e = embed_win("🎁 Gift (coins)", f"Tu offres **{fmt(net)}** KZ à {user.mention}.")
        e.add_field(name="💸 Montant", value=f"{fmt(amount)} KZ", inline=True)
        if tax > 0:
            e.add_field(name="🧾 Taxe", value=f"{fmt(tax)} KZ", inline=True)
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e.add_field(name="🏦 Ton solde", value=f"{fmt(new_bal)} KZ", inline=False)
        await interaction.response.send_message(embed=e)

    @gift_group.command(name="item", description="Offrir un item de ton inventaire")
    async def gift_item(self, interaction: discord.Interaction, user: discord.Member, item_id: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        self.db.ensure_user(user.id, config.START_BALANCE)
        if user.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_lose("❌ Gift", "Tu ne peux pas t'offrir un item à toi-même."))

        inv = self.db.get_inventory(interaction.user.id)
        have = int(inv.get(item_id, 0))
        if have <= 0:
            return await interaction.response.send_message(embed=embed_lose("❌ Gift", "Tu n'as pas cet item dans ton inventaire."))

        # move item
        inv[item_id] = have - 1
        if inv[item_id] <= 0:
            inv.pop(item_id, None)
        self.db.set_inventory(interaction.user.id, inv)

        inv_to = self.db.get_inventory(user.id)
        inv_to[item_id] = int(inv_to.get(item_id, 0)) + 1
        self.db.set_inventory(user.id, inv_to)

        it = get_item(item_id)
        name = it.name if it else item_id
        e = embed_win("🎁 Gift (item)", f"Tu offres **{name}** à {user.mention}.")
        await interaction.response.send_message(embed=e)

    # ============================================
    # ALIAS (raccourcis de commandes)
    # ============================================

    @app_commands.command(name="bal", description="💰 Alias de /balance")
    async def bal(self, interaction: discord.Interaction):
        await self.balance.callback(self, interaction)

    @app_commands.command(name="lb", description="🏆 Alias de /leaderboard")
    async def lb(self, interaction: discord.Interaction):
        await self.leaderboard.callback(self, interaction)

    @app_commands.command(name="top", description="🏆 Alias de /leaderboard")
    async def top(self, interaction: discord.Interaction):
        await self.leaderboard.callback(self, interaction)

    @app_commands.command(name="pay", description="💸 Alias de /transfer")
    @app_commands.describe(user="Joueur destinataire", amount="Montant à envoyer")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, 100000000]):
        await self.transfer.callback(self, interaction, user, amount)

    @app_commands.command(name="cd", description="⏱️ Alias de /cooldowns")
    async def cd(self, interaction: discord.Interaction):
        await self.cooldowns.callback(self, interaction)


async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(EconomyCog(bot, db))
