# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timedelta
import asyncio

import json

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import Database
from ..shop_data import get_item
from ..utils import embed_info, embed_lose, embed_neutral, embed_win, fmt, human_time, now_utc, parse_dt
from ..checks import is_bot_admin, is_owner


# ============================================
# Paramètres modifiables en temps réel
# ============================================

from ..odds import TUNABLE_PARAMS, CATEGORIES, get_param_value, set_param_value, reset_param

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        return is_owner(interaction) or is_bot_admin(self.db, interaction)

    async def _db_call(self, fn, *args, timeout: float = 8.0):
        """Exécute une opération DB bloquante dans un thread, avec timeout.

        Objectif : éviter les interactions qui restent en "réfléchit" si SQLite bloque.
        """
        return await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout=timeout)

    # ============================================
    # COMMANDES SIMPLES (sans groupe)
    # ============================================

    @app_commands.command(name="give", description="🎁 Donner des KZ à un joueur")
    @app_commands.describe(user="Joueur ciblé", amount="Montant à donner")
    async def give(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, 100_000_000]):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)

        self.db.ensure_user(user.id, config.START_BALANCE)
        new_bal = self.db.add_balance(user.id, int(amount))

        e = embed_win("🎁 Give", f"{user.mention} a reçu **{fmt(amount)}** KZ\nNouveau solde: **{fmt(new_bal)}** KZ")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="take", description="💸 Retirer des KZ à un joueur")
    @app_commands.describe(user="Joueur ciblé", amount="Montant à retirer (0 = tout prendre)")
    async def take(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 0, 100_000_000] = 0):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.ensure_user(user.id, config.START_BALANCE)
        row = self.db.get_user(user.id)
        current = int(row["balance"]) if row else 0
        
        if amount == 0:
            self.db.set_balance(user.id, 0)
            await interaction.response.send_message(embed=embed_win("💸 Take All", f"{user.mention} → **-{fmt(current)}** KZ confisqués\nNouveau solde: **0** KZ"))
        else:
            new_bal = self.db.remove_balance(user.id, amount)
            taken = min(amount, current)
            await interaction.response.send_message(embed=embed_win("💸 Take", f"{user.mention} → **-{fmt(taken)}** KZ\nNouveau solde: **{fmt(new_bal)}** KZ"))

    @app_commands.command(name="setbal", description="💰 Définir le solde exact d'un joueur")
    @app_commands.describe(user="Joueur ciblé", amount="Nouveau solde")
    async def setbal(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 0, 100_000_000]):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.ensure_user(user.id, config.START_BALANCE)
        row = self.db.get_user(user.id)
        old = int(row["balance"]) if row else 0
        self.db.set_balance(user.id, amount)
        await interaction.response.send_message(embed=embed_win("💰 SetBal", f"{user.mention}\n**{fmt(old)}** → **{fmt(amount)}** KZ"))

    @app_commands.command(name="giveitem", description="📦 Donner un item à un joueur")
    @app_commands.describe(user="Joueur ciblé", item_id="ID de l'item", qty="Quantité")
    async def giveitem(self, interaction: discord.Interaction, user: discord.Member, item_id: str, qty: app_commands.Range[int, 1, 1000] = 1):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.ensure_user(user.id, config.START_BALANCE)
        inv = self.db.get_inventory(user.id)
        inv[item_id] = int(inv.get(item_id, 0)) + qty
        self.db.set_inventory(user.id, inv)
        it = get_item(item_id)
        name = it.name if it else item_id
        await interaction.response.send_message(embed=embed_win("📦 Item", f"{user.mention} a reçu **{qty}× {name}**"))

    @app_commands.command(name="takeitem", description="📦 Retirer un item à un joueur")
    @app_commands.describe(user="Joueur ciblé", item_id="ID de l'item", qty="Quantité (0 = tout)")
    async def takeitem(self, interaction: discord.Interaction, user: discord.Member, item_id: str, qty: app_commands.Range[int, 0, 1000] = 0):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        inv = self.db.get_inventory(user.id)
        current = int(inv.get(item_id, 0))
        if qty == 0:
            inv.pop(item_id, None)
            removed = current
        else:
            removed = min(qty, current)
            inv[item_id] = max(0, current - qty)
            if inv[item_id] == 0:
                inv.pop(item_id, None)
        self.db.set_inventory(user.id, inv)
        it = get_item(item_id)
        name = it.name if it else item_id
        await interaction.response.send_message(embed=embed_win("📦 Item retiré", f"{user.mention} → **-{removed}× {name}**"))

    @app_commands.command(name="givevip", description="👑 Donner du VIP à un joueur")
    @app_commands.describe(user="Joueur ciblé", jours="Nombre de jours")
    async def givevip(self, interaction: discord.Interaction, user: discord.Member, jours: app_commands.Range[int, 1, 365] = 7):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.ensure_user(user.id, config.START_BALANCE)
        row = self.db.get_user(user.id)
        now = now_utc()
        current_vip = parse_dt(row["vip_until"]) if row["vip_until"] else None
        base = current_vip if (current_vip and current_vip > now) else now
        new_until = base + timedelta(days=jours)
        self.db.set_user_field(user.id, "vip_until", new_until.isoformat())
        e = embed_win("👑 VIP", f"{user.mention} → **+{jours} jours** VIP")
        e.add_field(name="Expire", value=f"<t:{int(new_until.timestamp())}:F>")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="giveimmunity", description="🛡️ Donner de l'immunité à un joueur")
    @app_commands.describe(user="Joueur ciblé", heures="Nombre d'heures")
    async def giveimmunity(self, interaction: discord.Interaction, user: discord.Member, heures: app_commands.Range[int, 1, 720] = 24):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.ensure_user(user.id, config.START_BALANCE)
        row = self.db.get_user(user.id)
        now = now_utc()
        current_imm = parse_dt(row["immunity_until"]) if row["immunity_until"] else None
        base = current_imm if (current_imm and current_imm > now) else now
        new_until = base + timedelta(hours=heures)
        self.db.set_user_field(user.id, "immunity_until", new_until.isoformat())
        e = embed_win("🛡️ Immunité", f"{user.mention} → **+{heures}h** d'immunité")
        e.add_field(name="Expire", value=f"<t:{int(new_until.timestamp())}:F>")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="clearuser", description="🧹 Reset complet d'un joueur (solde, items, stats)")
    @app_commands.describe(user="Joueur ciblé")
    async def clearuser(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.wipe_user(user.id)
        await interaction.response.send_message(embed=embed_win("🧹 Clear", f"{user.mention} a été complètement reset"))

    @app_commands.command(name="clearcoins", description="💸 Mettre le solde d'un joueur à 0")
    @app_commands.describe(user="Joueur ciblé")
    async def clearcoins(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.ensure_user(user.id, config.START_BALANCE)
        row = self.db.get_user(user.id)
        old = int(row["balance"]) if row else 0
        self.db.set_balance(user.id, 0)
        await interaction.response.send_message(embed=embed_win("💸 Clear Coins", f"{user.mention} → **-{fmt(old)}** KZ\nNouveau solde: **0** KZ"))

    @app_commands.command(name="clearinv", description="📦 Vider l'inventaire d'un joueur")
    @app_commands.describe(user="Joueur ciblé")
    async def clearinv(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.set_inventory(user.id, {})
        await interaction.response.send_message(embed=embed_win("📦 Clear Inventaire", f"{user.mention} → inventaire vidé"))

    @app_commands.command(name="addadmin", description="➕ Ajouter un admin du bot")
    @app_commands.describe(user="Utilisateur à promouvoir admin")
    async def addadmin(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.add_bot_admin(user.id)
        await interaction.response.send_message(embed=embed_win("✅ Admin", f"{user.mention} est maintenant admin"))

    @app_commands.command(name="deladmin", description="➖ Retirer un admin du bot (Owner)")
    @app_commands.describe(user="Utilisateur à retirer des admins")
    async def deladmin(self, interaction: discord.Interaction, user: discord.Member):
        if not is_owner(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)
        self.db.remove_bot_admin(user.id)
        await interaction.response.send_message(embed=embed_win("✅ Admin retiré", f"{user.mention} n'est plus admin"))

    @app_commands.command(name="listadmin", description="📋 Voir la liste des admins du bot")
    async def listadmin(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        admins = self.db.list_bot_admins()
        if not admins:
            return await interaction.response.send_message(embed=embed_neutral("📋 Admins", "Aucun admin configuré.\n\n(L'owner a toujours les droits admin)"))
        lines = [f"• <@{uid}>" for uid in admins]
        # Ajouter l'owner
        if config.OWNER_ID:
            lines.insert(0, f"👑 <@{config.OWNER_ID}> (Owner)")
        await interaction.response.send_message(embed=embed_neutral("📋 Admins du bot", "\n".join(lines)))

    @app_commands.command(name="wipeall", description="🔥 Reset TOUS les joueurs (Owner)")
    @app_commands.describe(confirm="Écrire 'oui' pour confirmer")
    async def wipeall(self, interaction: discord.Interaction, confirm: str = ""):
        if not is_owner(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)
        if confirm.lower() != "oui":
            return await interaction.response.send_message(embed=embed_lose("⚠️ Attention", "Tape `/wipeall confirm:oui` pour confirmer"), ephemeral=True)
        self.db.wipe_all_users()
        await interaction.response.send_message(embed=embed_win("🔥 Wipe Global", "Tous les joueurs ont été reset"))

    
    # ============================================
    # XP / LEVELS (groupe /xp)
    # ============================================
    xp_group = app_commands.Group(name="xp", description="Gérer l'XP et les niveaux (admin)")

    @xp_group.command(name="give", description="➕ Ajouter de l'XP à un joueur (admin)")
    @app_commands.describe(user="Joueur ciblé", amount="Quantité d'XP à ajouter")
    async def xp_give(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, 10_000_000]):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)

        # Important : certaines opérations DB peuvent prendre > 3 secondes
        # (WAL/busy_timeout) et Discord affiche "L'application ne répond plus".
        # On defer tout de suite pour éviter le timeout d'interaction.
        # Toujours defer, puis répondre via followup (sinon InteractionResponded)
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await self._db_call(self.db.ensure_user, user.id, config.START_BALANCE)

            before = await self._db_call(self.db.get_user, user.id)
            old_xp = int(before["xp"]) if before else 0
            old_level = int(before["level"]) if before else 1

            new_xp, new_level = await self._db_call(self.db.add_xp, user.id, int(amount))

            from ..leveling import title_and_icon_for_level
            title, icon = title_and_icon_for_level(new_level, cap=int(getattr(config, "XP_LEVEL_CAP", 100)))

            e = embed_win(
                "✅",
                "XP ajoutée",
                f"👤 {user.mention}\n"
                f"➕ **+{int(amount):,} XP**\n"
                f"📊 XP: **{new_xp:,}** (avant {old_xp:,})\n"
                f"⭐ Niveau: **{new_level}** (avant {old_level})\n"
                f"🏷️ Grade: **{title}** {icon}",
            )
            await interaction.followup.send(embed=e, ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=embed_lose("⏱️", "Timeout", "La base de données est occupée. Réessaie dans quelques secondes."),
                ephemeral=True,
            )
        except Exception as ex:
            await interaction.followup.send(
                embed=embed_lose("❌", "Erreur", f"{type(ex).__name__}: {ex}"),
                ephemeral=True,
            )

    @xp_group.command(name="remove", description="➖ Retirer de l'XP à un joueur (admin)")
    @app_commands.describe(user="Joueur ciblé", amount="Quantité d'XP à retirer")
    async def xp_remove(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, 10_000_000]):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await self._db_call(self.db.ensure_user, user.id, config.START_BALANCE)
            row = await self._db_call(self.db.get_user, user.id)
            cur_xp = int(row["xp"]) if row else 0
            new_xp = max(0, cur_xp - int(amount))

            from ..leveling import level_from_xp, title_and_icon_for_level
            cap = int(getattr(config, "XP_LEVEL_CAP", 100))
            new_level = level_from_xp(new_xp, cap=cap)
            title, icon = title_and_icon_for_level(new_level, cap=cap)

            def _do_update():
                with self.db.connect() as con:
                    con.execute(
                        "UPDATE users SET xp=?, level=? WHERE user_id=?",
                        (int(new_xp), int(new_level), int(user.id)),
                    )
                    con.commit()

            await self._db_call(_do_update)

            e = embed_neutral(
                "🧹",
                "XP retirée",
                f"👤 {user.mention}\n"
                f"➖ **-{int(amount):,} XP**\n"
                f"📊 XP: **{new_xp:,}** (avant {cur_xp:,})\n"
                f"⭐ Niveau: **{new_level}**\n"
                f"🏷️ Grade: **{title}** {icon}\n"
                f"ℹ️ Retirer de l'XP ne retire pas les KZ déjà gagnés.",
            )
            await interaction.followup.send(embed=e, ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=embed_lose("⏱️", "Timeout", "La base de données est occupée. Réessaie dans quelques secondes."),
                ephemeral=True,
            )
        except Exception as ex:
            await interaction.followup.send(
                embed=embed_lose("❌", "Erreur", f"{type(ex).__name__}: {ex}"),
                ephemeral=True,
            )

    @xp_group.command(name="reset", description="🔄 Reset XP + niveau d'un joueur (admin)")
    @app_commands.describe(user="Joueur ciblé")
    async def xp_reset(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await self._db_call(self.db.ensure_user, user.id, config.START_BALANCE)

            def _do_reset():
                with self.db.connect() as con:
                    con.execute(
                        "UPDATE users SET xp=0, level=1, profile_color=? WHERE user_id=?",
                        ("gris", int(user.id)),
                    )
                    con.commit()

            await self._db_call(_do_reset)

            e = embed_win("✅", "Reset effectué", f"{user.mention}\nXP: **0**\nNiveau: **1**\nCouleur: **gris**")
            await interaction.followup.send(embed=e, ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=embed_lose("⏱️", "Timeout", "La base de données est occupée. Réessaie dans quelques secondes."),
                ephemeral=True,
            )
        except Exception as ex:
            await interaction.followup.send(
                embed=embed_lose("❌", "Erreur", f"{type(ex).__name__}: {ex}"),
                ephemeral=True,
            )

    @xp_group.command(name="setlevel", description="🎯 Définir un niveau (admin)")
    @app_commands.describe(user="Joueur ciblé", level="Niveau cible")
    async def xp_setlevel(self, interaction: discord.Interaction, user: discord.Member, level: app_commands.Range[int, 1, 100]):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await self._db_call(self.db.ensure_user, user.id, config.START_BALANCE)
            cap = int(getattr(config, "XP_LEVEL_CAP", 100))
            level = max(1, min(int(level), cap))

            from ..leveling import xp_for_level, level_from_xp, title_and_icon_for_level
            target_xp = int(xp_for_level(level, cap=cap))

            row = await self._db_call(self.db.get_user, user.id)
            cur_xp = int(row["xp"]) if row else 0
            cur_level = level_from_xp(cur_xp, cap=cap)

            if target_xp > cur_xp:
                # On passe par add_xp pour déclencher rewards / bonus / couleurs automatiquement
                await self._db_call(self.db.add_xp, user.id, target_xp - cur_xp)
            else:
                # Baisse de niveau: on met à jour directement (pas de retrait KZ)
                def _do_update():
                    with self.db.connect() as con:
                        con.execute(
                            "UPDATE users SET xp=?, level=? WHERE user_id=?",
                            (int(target_xp), int(level), int(user.id)),
                        )
                        con.commit()
                await self._db_call(_do_update)

            row2 = await self._db_call(self.db.get_user, user.id)
            new_xp = int(row2["xp"]) if row2 else target_xp
            new_level = int(row2["level"]) if row2 else level
            title, icon = title_and_icon_for_level(new_level, cap=cap)

            e = embed_win(
                "🎯",
                "Niveau défini",
                f"👤 {user.mention}\n"
                f"⭐ Niveau: **{cur_level}** → **{new_level}**\n"
                f"📊 XP: **{cur_xp:,}** → **{new_xp:,}**\n"
                f"🏷️ Grade: **{title}** {icon}\n"
                f"ℹ️ Si on augmente le niveau, les récompenses (KZ/bonus) sont accordées. Si on diminue, elles ne sont pas retirées.",
            )
            await interaction.followup.send(embed=e, ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=embed_lose("⏱️", "Timeout", "La base de données est occupée. Réessaie dans quelques secondes."),
                ephemeral=True,
            )
        except Exception as ex:
            await interaction.followup.send(
                embed=embed_lose("❌", "Erreur", f"{type(ex).__name__}: {ex}"),
                ephemeral=True,
            )

    @xp_group.command(name="info", description="📊 Voir l'XP et la progression d'un joueur (admin)")
    @app_commands.describe(user="Joueur ciblé")
    async def xp_info(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await self._db_call(self.db.ensure_user, user.id, config.START_BALANCE)
            row = await self._db_call(self.db.get_user, user.id)
            xp = int(row["xp"]) if row else 0

            from ..leveling import xp_progress, title_and_icon_for_level
            cap = int(getattr(config, "XP_LEVEL_CAP", 100))
            lvl_calc, in_lvl, need = xp_progress(xp, cap=cap)
            title, icon = title_and_icon_for_level(lvl_calc, cap=cap)

            desc = (
                f"👤 {user.mention}\n"
                f"🏷️ Grade: **{title}** {icon}\n"
                f"⭐ Niveau: **{lvl_calc}**\n"
                f"📊 XP totale: **{xp:,}**\n"
            )
            if lvl_calc >= cap:
                desc += "🏁 **Niveau max atteint.**"
            else:
                desc += f"⏳ Progression: **{in_lvl:,} / {need:,}** XP vers le niveau {lvl_calc + 1}"

            await interaction.followup.send(embed=embed_info("📊 XP Info", desc), ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=embed_lose("⏱️", "Timeout", "La base de données est occupée. Réessaie dans quelques secondes."),
                ephemeral=True,
            )
        except Exception as ex:
            await interaction.followup.send(
                embed=embed_lose("❌", "Erreur", f"{type(ex).__name__}: {ex}"),
                ephemeral=True,
            )

# ============================================
    # BLACKLIST (groupe /bl)
    # ============================================
    bl_group = app_commands.Group(name="bl", description="Gérer la blacklist")

    @bl_group.command(name="add", description="⛔ Blacklist définitif")
    @app_commands.describe(user="Utilisateur à blacklist", reason="Raison (optionnel)")
    async def bl_add(self, interaction: discord.Interaction, user: discord.Member, reason: str | None = None):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if user.id == config.OWNER_ID:
            return await interaction.response.send_message(embed=embed_lose("❌", "Impossible."), ephemeral=True)
        self.db.bl_add(user.id, interaction.user.id, reason, None)
        await interaction.response.send_message(embed=embed_win("⛔ Blacklist", f"{user.mention} blacklisté"))

    @bl_group.command(name="temp", description="⏱️ Blacklist temporaire")
    @app_commands.describe(user="Utilisateur à blacklist", minutes="Durée en minutes", reason="Raison (optionnel)")
    async def bl_temp(self, interaction: discord.Interaction, user: discord.Member, minutes: app_commands.Range[int, 1, 525600], reason: str | None = None):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if user.id == config.OWNER_ID:
            return await interaction.response.send_message(embed=embed_lose("❌", "Impossible."), ephemeral=True)
        expires_at = (now_utc() + timedelta(minutes=minutes)).isoformat()
        self.db.bl_add(user.id, interaction.user.id, reason, expires_at)
        await interaction.response.send_message(embed=embed_win("⛔ Blacklist temp", f"{user.mention} → {minutes} min"))

    @bl_group.command(name="remove", description="✅ Retirer de la blacklist")
    async def bl_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        self.db.bl_remove(user.id)
        await interaction.response.send_message(embed=embed_win("✅ Unban", f"{user.mention} retiré de la blacklist"))

    @bl_group.command(name="list", description="📋 Voir la blacklist")
    async def bl_list(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        rows = self.db.bl_list()
        if not rows:
            return await interaction.response.send_message(embed=embed_info("Blacklist", "Vide"))
        lines = []
        for r in rows[:20]:
            uid = int(r['user_id'])
            reason = r['reason'] or '—'
            expires = parse_dt(r['expires_at'])
            if expires:
                left = int((expires - now_utc()).total_seconds())
                if left > 0:
                    lines.append(f"<@{uid}> — {reason} ({human_time(left)})")
                continue
            lines.append(f"<@{uid}> — {reason} (permanent)")
        await interaction.response.send_message(embed=embed_neutral("⛔ Blacklist", "\n".join(lines) or "Vide"))

    
    # ============================================
    # /stat (Admin) — Stats PvP
    # ============================================

    @app_commands.command(name="stat", description="📊 Voir les stats PvP d’un joueur (admin)")
    @app_commands.describe(joueur="Joueur à consulter (optionnel)")
    async def stat(self, interaction: discord.Interaction, joueur: discord.User | None = None):
        """Affiche les stats PvP (duels entre joueurs) : parties, victoires, défaites, % de victoire, profit."""
        if not self._is_admin(interaction):
            return await interaction.response.send_message(
                embed=embed_lose("❌", "Commande réservée aux admins du bot."),
                ephemeral=True,
            )

        target = joueur or interaction.user
        # S'assure que l'utilisateur existe en base
        try:
            self.db.ensure_user(int(target.id), config.START_BALANCE)
        except Exception:
            # si la DB est temporairement indisponible
            return await interaction.response.send_message(
                embed=embed_lose("❌", "Impossible de charger la base de données."),
                ephemeral=True,
            )

        row = self.db.get_user(int(target.id))
        if not row:
            return await interaction.response.send_message(
                embed=embed_neutral("ℹ️ Stats", "Aucune donnée pour ce joueur."),
                ephemeral=True,
            )

        games = int(row["pvp_games"] or 0)
        wins = int(row["pvp_wins"] or 0)
        losses = int(row["pvp_losses"] or 0)
        profit = int(row["pvp_profit"] or 0)

        winrate = (wins / games * 100.0) if games > 0 else 0.0
        avg_profit = (profit / games) if games > 0 else 0.0

        desc = (
            f"**Joueur :** <@{target.id}>\n"
            f"__**PvP**__\n"
            f"• **Parties :** {games}\n"
            f"• **Victoires / Défaites :** {wins} / {losses}\n"
            f"• **% victoire :** {winrate:.1f}%\n"
            f"• **Profit :** {fmt(profit)}\n"
            f"• **Moy. / partie :** {fmt(int(avg_profit))}"
        )

        # Stats par jeux (blackjack, coinflip, roulette, slots, crash, guess)
        per_game = self.db.get_all_game_stats(int(target.id))
        order = [
            ("blackjack", "🃏 Blackjack"),
            ("coinflip", "🪙 Coinflip"),
            ("roulette", "🎡 Roulette"),
            ("slots", "🎰 Slots"),
            ("crash", "📈 Crash"),
            ("guess", "❓ Guess"),
        ]

        lines = []
        for key, label in order:
            s = per_game.get(key)
            if not s:
                continue
            g = int(s.get("games", 0) or 0)
            if g <= 0:
                continue
            w = int(s.get("wins", 0) or 0)
            l = int(s.get("losses", 0) or 0)
            p = int(s.get("profit", 0) or 0)
            wr = (w / g * 100.0) if g > 0 else 0.0
            avg = (p / g) if g > 0 else 0.0
            lines.append(
                f"**{label}** — {g} parties | {w}W/{l}L | {wr:.1f}% | Profit {fmt(p)} | Moy. {fmt(int(avg))}"
            )

        if lines:
            desc += "\n\n__**Jeux casino**__\n" + "\n".join(lines)

        await interaction.response.send_message(embed=embed_info("📊 Stats (PvP + jeux)", desc), ephemeral=True)
# ============================================
    # PROBABILITÉS /odds (Owner)
    # ============================================
    odds_group = app_commands.Group(name="odds", description="Modifier les probabilités (Owner)")

    @odds_group.command(name="list", description="📊 Voir tous les paramètres")
    async def odds_list(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)
        categories = CATEGORIES
        e = discord.Embed(title="⚙️ Paramètres", color=config.BRAND["info"])
        for cat, params in categories.items():
            lines = []
            for p in params:
                pi = TUNABLE_PARAMS[p]
                cur = get_param_value(self.db, p)
                mod = "✏️" if cur != pi["default"] else ""
                val = f"{cur:.2f}" if pi["type"] == "float" else str(cur)
                lines.append(f"`{p}`: **{val}** {mod}")
            e.add_field(name=cat, value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=e)

    @odds_group.command(name="set", description="✏️ Modifier un paramètre")
    async def odds_set(self, interaction: discord.Interaction, param: str, valeur: str):
        if not is_owner(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)
        param = param.lower()
        pi = TUNABLE_PARAMS.get(param)
        if not pi:
            return await interaction.response.send_message(embed=embed_lose("❌", "Paramètre inconnu. `/odds list`"), ephemeral=True)
        ok, err = set_param_value(self.db, param, valeur)
        if not ok:
            return await interaction.response.send_message(embed=embed_lose("❌", err or "Valeur invalide"), ephemeral=True)
        cur = get_param_value(self.db, param)
        val = f"{cur:.2f}" if pi["type"] == "float" else str(cur)
        await interaction.response.send_message(embed=embed_win("✅", f"`{param}` → **{val}**"))

    

    @odds_group.command(name="help", description="ℹ️ Aide sur /odds (format, exemples)")
    async def odds_help(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)

        e = discord.Embed(title="ℹ️ Aide — /odds", color=config.BRAND["info"])
        e.description = (
            "Avec `/odds`, tu règles les paramètres sans toucher au code.\n\n"
            "**Commandes :**\n"
            "• `/odds list` → affiche tous les paramètres\n"
            "• `/odds set <param> <valeur>` → modifie un paramètre\n"
            "• `/odds reset <param|all>` → remet par défaut\n\n"
            "**Formats importants :**\n"
            "• Probabilités / pourcentages : **0.25 = 25%** (valeur entre 0 et 1)\n"
            "• Ex: `steal_success_rate 0.30` = 30%\n"
            "• Ex: `steal_steal_pct 0.12` = vole 12%\n"
        )
        e.add_field(
            name="Exemples rapides",
            value=(
                "`/odds set steal_success_rate 0.30`\n"
                "`/odds set steal_steal_pct 0.12`\n"
                "`/odds set sabotage_success_rate 0.10`\n"
                "`/odds set bot_win_chance 0.60`\n"
                "`/odds reset steal_success_rate`\n"
                "`/odds reset all`"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    @odds_group.command(name="reset", description="♻️ Remet un paramètre (ou tout) par défaut")
    @app_commands.describe(param="Paramètre à reset (ou 'all' pour tout)")
    async def odds_reset(self, interaction: discord.Interaction, param: str):
        try:
            if not is_owner(interaction):
                return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)

            p = param.lower().strip()
            if p in ("all", "*", "all (tout réinitialiser)"):
                reset_param(self.db, None)
                return await interaction.response.send_message(embed=embed_win("♻️", "Tous les paramètres ont été réinitialisés."), ephemeral=True)

            if p not in TUNABLE_PARAMS:
                return await interaction.response.send_message(embed=embed_lose("❌", f"Paramètre inconnu: `{p}`\nUtilise `/odds list`"), ephemeral=True)

            reset_param(self.db, p)
            default_val = TUNABLE_PARAMS[p]["default"]
            await interaction.response.send_message(embed=embed_win("♻️", f"`{p}` remis par défaut: **{default_val}**"), ephemeral=True)
        except Exception as e:
            try:
                await interaction.response.send_message(embed=embed_lose("❌ Erreur", str(e)), ephemeral=True)
            except:
                await interaction.followup.send(embed=embed_lose("❌ Erreur", str(e)), ephemeral=True)

    @odds_set.autocomplete("param")
    async def param_ac_set(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=n, value=n) for n in TUNABLE_PARAMS if current.lower() in n][:25]

    @odds_reset.autocomplete("param")
    async def param_ac_reset(self, interaction: discord.Interaction, current: str):
        # Ajouter "all" en premier pour reset tout
        choices = [app_commands.Choice(name="all (tout réinitialiser)", value="all")]
        choices += [app_commands.Choice(name=n, value=n) for n in TUNABLE_PARAMS if current.lower() in n][:24]
        return choices


    @odds_group.command(name="gif_list", description="🎞️ Voir les GIFs de victoire")
    async def odds_gif_list(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)

        raw = self.db.get_setting("win_gifs", "[]")
        try:
            gifs = json.loads(raw) if raw else []
            if not isinstance(gifs, list):
                gifs = []
        except Exception:
            gifs = []

        enabled = int(get_param_value(self.db, "win_gifs_enabled"))
        desc = f"Status: **{'ON' if enabled else 'OFF'}** (change avec `/odds set win_gifs_enabled 0/1`)\n\n"
        if not gifs:
            desc += "Aucun GIF enregistré. Ajoute-en avec `/odds gif_add <url>`."
        else:
            lines = []
            for i, url in enumerate(gifs[:50]):
                lines.append(f"`{i}` • {url}")
            desc += "\n".join(lines)

        e = discord.Embed(title="🎞️ GIFs victoire", description=desc, color=config.BRAND["info"])
        await interaction.followup.send(embed=e, ephemeral=True)

    @odds_group.command(name="gif_add", description="➕ Ajouter un GIF de victoire")
    @app_commands.describe(url="Lien direct .gif/.png/.jpg/.webp")
    async def odds_gif_add(self, interaction: discord.Interaction, url: str):
        if not is_owner(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)

        u = url.strip()
        low = u.lower()
        if not any(low.endswith(ext) for ext in (".gif", ".png", ".jpg", ".jpeg", ".webp")):
            return await interaction.response.send_message(embed=embed_lose("❌", "Lien non direct. Mets un lien qui finit par .gif/.png/.jpg/.webp"), ephemeral=True)

        raw = self.db.get_setting("win_gifs", "[]")
        try:
            gifs = json.loads(raw) if raw else []
            if not isinstance(gifs, list):
                gifs = []
        except Exception:
            gifs = []

        if u in gifs:
            return await interaction.response.send_message(embed=embed_neutral("ℹ️", "Ce GIF est déjà dans la liste."), ephemeral=True)

        gifs.append(u)
        self.db.set_setting("win_gifs", json.dumps(gifs))
        await interaction.response.send_message(embed=embed_win("✅", f"GIF ajouté. Total: **{len(gifs)}**"), ephemeral=True)

    @odds_group.command(name="gif_remove", description="➖ Supprimer un GIF de victoire")
    @app_commands.describe(index="Index du GIF (voir /odds gif_list)")
    async def odds_gif_remove(self, interaction: discord.Interaction, index: int):
        if not is_owner(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Owner uniquement."), ephemeral=True)

        raw = self.db.get_setting("win_gifs", "[]")
        try:
            gifs = json.loads(raw) if raw else []
            if not isinstance(gifs, list):
                gifs = []
        except Exception:
            gifs = []

        if index < 0 or index >= len(gifs):
            return await interaction.response.send_message(embed=embed_lose("❌", "Index invalide."), ephemeral=True)

        removed = gifs.pop(index)
        self.db.set_setting("win_gifs", json.dumps(gifs))
        await interaction.response.send_message(embed=embed_win("✅", f"GIF supprimé: {removed}"), ephemeral=True)





# ==========================
# UI PANEL (EPHEMERAL)
# ==========================

from .shop import ShopView, build_shop_embed  # noqa: E402


def _panel_embed(title: str, description: str, gif_url: str | None = None) -> discord.Embed:
    e = embed_neutral(title, description)
    if gif_url:
        e.set_image(url=gif_url)
    return e



class PanelView(discord.ui.View):
    """
    Panel PUBLIC (visible par tout le monde),
    mais chaque bouton renvoie un menu EPHEMERAL pour l'utilisateur qui clique.
    """
    def __init__(self, db: Database, gif_url: str | None = None):
        super().__init__(timeout=None)
        self.db = db
        self.gif_url = gif_url

    @discord.ui.button(label="🚀 Débuter", style=discord.ButtonStyle.secondary)
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        txt = (
            "**1) Crée ton compte** : `/register`\n"
            "**2) Récupère des KZ** : `/daily`, `/weekly`, `/work` (+ récompenses messages/vocal)\n"
            "**3) Achète des items** : `/shop` (boutons **Acheter x1/x5**)\n"
            "**4) Joue** : `/slots`, `/roulette`, `/blackjack`, `/crash`, etc.\n"
            "**5) PvP** : duels (`/pvp`, `/rps1v1`, `/blackjack1v1`) + actions (`/steal`, `/sabotage`)\n\n"
            "➡️ Conseil : fais `/help` pour voir toutes les commandes."
        )
        e = embed_info("🚀 Bien démarrer", txt)
        if self.gif_url:
            e.set_image(url=self.gif_url)
        await interaction.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="🛒 Shop", style=discord.ButtonStyle.success)
    async def shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ouvre le shop en ephemeral pour la personne qui clique
        view = ShopView(self.db, interaction.user.id, start_category=config.SHOP_CATEGORIES[0])
        await interaction.response.send_message(
            embed=view.current_embed(interaction.user.id),
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="🎮 Jeux", style=discord.ButtonStyle.primary)
    async def games_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        txt = (
            "**Miser** : tu peux mettre un nombre, ou `all` / `max` / `tout`.\n\n"
            "🎰 **Jeux casino** :\n"
            "• **/slots** — machine à sous\n"
            "• **/roulette** — rouge/noir/vert/numéro\n"
            "• **/coinflip** — pile/face\n"
            "• **/blackjack** — interactif\n"
            "• **/crash** — cash-out avant le crash\n"
            "• **/guess** — devine 1-100\n"
            "• **/chest** — coffre (cooldown)\n\n"
            "📌 **Prediction** : `/prediction`, `/predictions`, `/prediction_cancel`\n\n"
            "⚔️ **Duels** : `/pvp`, `/rps1v1`, `/blackjack1v1` (possible contre le bot si activé)\n\n"
            "➡️ `/help` pour les détails et les cooldowns."
        )
        e = embed_info("🎮 Jeux", txt)
        if self.gif_url:
            e.set_image(url=self.gif_url)
        await interaction.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="🧑‍🎤 Profil", style=discord.ButtonStyle.primary)
    async def profile_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        txt = (
            "Commandes profil :\n"
            "• **/profile** — afficher ton profil\n"
            "• **/profileset banner:<url>** — mettre une image\n"
            "• **/profileset removebanner** — retirer l'image\n\n"
            "⚠️ Pour définir une image, il faut l'item **setprofile** dans le shop."
        )
        e = embed_info("🧑‍🎤 Profil", txt)
        if self.gif_url:
            e.set_image(url=self.gif_url)
        await interaction.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="📜 Règles", style=discord.ButtonStyle.secondary)
    async def rules_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        txt = (
            "• Respect & fair-play\n"
            "• Pas de spam / exploit / abuse de bugs\n"
            "• Pas de multi-comptes pour farmer les KZ\n"
            "• Les gains/pertes sont automatiques (les décisions du bot font foi)\n"
            "• En cas de bug : contacte un staff avec un screen\n\n"
            "Astuce : **/help** pour toutes les commandes."
        )
        e = embed_info("📜 Règles", txt)
        if self.gif_url:
            e.set_image(url=self.gif_url)
        await interaction.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="✖️ Fermer", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ Menu fermé pour toi.", ephemeral=True)



class PanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    @app_commands.command(name="panel", description="Publier le menu interactif (public) — boutons = menus privés")
    @app_commands.describe(gif_url="Lien direct vers un GIF (optionnel)")
    async def panel(self, interaction: discord.Interaction, gif_url: str | None = None):
        # ✅ répond immédiatement (évite "l’app ne répond plus")
        await interaction.response.defer(ephemeral=True)

        # admin only
        # NOTE: is_bot_admin signature is (db, interaction)
        if not is_bot_admin(self.db, interaction):
            return await interaction.followup.send(
                embed=embed_lose("❌ Panel", "Accès refusé."),
                ephemeral=True,
            )

        view = PanelView(self.db, gif_url=gif_url)
        start = _panel_embed(
            "📌 Menu",
            "Clique sur un bouton pour ouvrir le menu correspondant **en privé (ephemeral)**.\n\n"
            "✅ **À faire en premier :** `/register` pour créer ton compte.\n"
            "🎁 Bonus : tu gagnes aussi des KZ en envoyant des messages et en restant en vocal.\n\n"
            "🚀 Débuter • 🛒 Shop • 🎮 Jeux • 🧑‍🎤 Profil • 📜 Règles",
            gif_url,
        )

        # message PUBLIC dans le salon
        if interaction.channel is None:
            return await interaction.followup.send("❌ Impossible d’envoyer le panel ici.", ephemeral=True)
        await interaction.channel.send(embed=start, view=view)

        # confirmation PRIVÉE
        await interaction.followup.send("✅ Panel envoyé dans ce salon.", ephemeral=True)



    # ===== Salons autorisés (whitelist) =====
    channels = app_commands.Group(name="channels", description="Configurer les salons autorisés pour les commandes")

    @channels.command(name="allow", description="✅ Autoriser un salon pour les commandes")
    @app_commands.describe(channel="Salon à autoriser")
    async def channels_allow(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        self.db.add_allowed_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(embed=embed_win("✅", f"Salon autorisé: {channel.mention}"), ephemeral=True)

    @channels.command(name="remove", description="🗑️ Retirer un salon autorisé")
    @app_commands.describe(channel="Salon à retirer")
    async def channels_remove(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        self.db.remove_allowed_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(embed=embed_win("✅", f"Salon retiré: {channel.mention}"), ephemeral=True)

    @channels.command(name="list", description="📃 Voir la liste des salons autorisés")
    async def channels_list(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        allowed = self.db.list_allowed_channels(interaction.guild.id)
        if not allowed:
            return await interaction.response.send_message(embed=embed_neutral("📃 Salons autorisés", "Aucun salon configuré (donc commandes autorisées partout)."), ephemeral=True)
        salons = "\n".join(f"• <#{cid}>" for cid in allowed)
        await interaction.response.send_message(embed=embed_neutral("📃 Salons autorisés", salons), ephemeral=True)

    

    @channels.command(name="clear", description="🧹 Vider la liste des salons autorisés (reset whitelist)")
    async def channels_clear(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)

        self.db.clear_allowed_channels(interaction.guild.id)
        await interaction.response.send_message(
            embed=embed_win("✅", "Whitelist des salons vidée. Les commandes sont maintenant autorisées partout (sauf si tu reconfigures des salons ou catégories)."),
            ephemeral=True,
        )

    # ===== Catégories autorisées (whitelist) =====
    category = app_commands.Group(name="category", description="Configurer les catégories autorisées pour les commandes")

    @category.command(name="allow", description="✅ Autoriser une catégorie pour les commandes")
    @app_commands.describe(category_channel="Un salon dans la catégorie à autoriser")
    async def category_allow(self, interaction: discord.Interaction, category_channel: discord.TextChannel):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        
        if category_channel.category is None:
            return await interaction.response.send_message(
                embed=embed_lose("❌", f"{category_channel.mention} n'est pas dans une catégorie."),
                ephemeral=True
            )
        
        cat = category_channel.category
        self.db.add_allowed_category(interaction.guild.id, cat.id)
        
        # Compter les salons dans la catégorie
        channels_count = len([c for c in interaction.guild.channels if getattr(c, 'category_id', None) == cat.id])
        
        await interaction.response.send_message(
            embed=embed_win("✅ Catégorie autorisée", f"📁 **{cat.name}**\n\nTous les salons de cette catégorie ({channels_count} salons) sont maintenant autorisés."),
            ephemeral=True
        )

    @category.command(name="remove", description="🗑️ Retirer une catégorie autorisée")
    @app_commands.describe(category_channel="Un salon dans la catégorie à retirer")
    async def category_remove(self, interaction: discord.Interaction, category_channel: discord.TextChannel):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        
        if category_channel.category is None:
            return await interaction.response.send_message(
                embed=embed_lose("❌", f"{category_channel.mention} n'est pas dans une catégorie."),
                ephemeral=True
            )
        
        cat = category_channel.category
        self.db.remove_allowed_category(interaction.guild.id, cat.id)
        
        await interaction.response.send_message(
            embed=embed_win("✅", f"Catégorie retirée: 📁 **{cat.name}**"),
            ephemeral=True
        )

    @category.command(name="list", description="📃 Voir la liste des catégories autorisées")
    async def category_list(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        
        allowed = self.db.list_allowed_categories(interaction.guild.id)
        if not allowed:
            return await interaction.response.send_message(
                embed=embed_neutral("📃 Catégories autorisées", "Aucune catégorie configurée.\n\nUtilise `/category allow` pour en ajouter."),
                ephemeral=True
            )
        
        lines = []
        for cat_id in allowed:
            cat = discord.utils.get(interaction.guild.categories, id=cat_id)
            if cat:
                channels_count = len([c for c in interaction.guild.channels if getattr(c, 'category_id', None) == cat.id])
                lines.append(f"📁 **{cat.name}** — {channels_count} salons")
            else:
                lines.append(f"📁 *(Catégorie supprimée: {cat_id})*")
        
        await interaction.response.send_message(
            embed=embed_neutral("📃 Catégories autorisées", "\n".join(lines)),
            ephemeral=True
        )

    @category.command(name="clear", description="🧹 Vider la liste des catégories autorisées")
    async def category_clear(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)

        self.db.clear_allowed_categories(interaction.guild.id)
        await interaction.response.send_message(
            embed=embed_win("✅", "Whitelist des catégories vidée."),
            ephemeral=True,
        )

# ===== Utilisateurs autorisés partout =====
    permit = app_commands.Group(name="permit", description="Autoriser un utilisateur à utiliser les commandes partout")

    @permit.command(name="add", description="✅ Autoriser un utilisateur partout")
    @app_commands.describe(user="Utilisateur à autoriser")
    async def permit_add(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        self.db.add_bypass_user(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=embed_win("✅", f"{user.mention} peut utiliser les commandes partout."), ephemeral=True)

    @permit.command(name="remove", description="🗑️ Retirer l'autorisation partout")
    @app_commands.describe(user="Utilisateur à retirer")
    async def permit_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        self.db.remove_bypass_user(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=embed_win("✅", f"Autorisation retirée pour {user.mention}."), ephemeral=True)

    @permit.command(name="list", description="📃 Voir les utilisateurs autorisés partout")
    async def permit_list(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message(embed=embed_lose("❌", "Accès refusé."), ephemeral=True)
        if interaction.guild is None:
            return await interaction.response.send_message(embed=embed_lose("❌", "Commande serveur uniquement."), ephemeral=True)
        users = self.db.list_bypass_users(interaction.guild.id)
        if not users:
            return await interaction.response.send_message(embed=embed_neutral("📃 Utilisateurs autorisés partout", "Aucun utilisateur."), ephemeral=True)
        lines = "\n".join(f"• <@{uid}>" for uid in users)
        await interaction.response.send_message(embed=embed_neutral("📃 Utilisateurs autorisés partout", lines), ephemeral=True)


async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(AdminCog(bot, db))
    await bot.add_cog(PanelCog(bot, db))