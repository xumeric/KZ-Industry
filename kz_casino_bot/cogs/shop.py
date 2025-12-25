# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import Database
from ..shop_data import ShopItem, get_item, items_by_category, DEFAULT_ITEMS
from ..utils import embed_info, embed_lose, embed_neutral, embed_win, fmt
from ..checks import enforce_blacklist


def _rarity_tag(it: ShopItem) -> str:
    r = config.RARITY_INFO.get(it.rarity, {"emoji": "⚪"})
    return f"{r['emoji']} {it.rarity}"


def _category_embed(category: str, selected: ShopItem | None, page: int, pages: int) -> discord.Embed:
    if selected:
        r = config.RARITY_INFO.get(selected.rarity, {"emoji": "⚪", "color": config.BRAND["info"]})
        e = discord.Embed(
            title=f"🛒 Boutique — {category}",
            description=(
                f"**{selected.name}** (`{selected.item_id}`)\n"
                f"{_rarity_tag(selected)}\n\n"
                f"{selected.description}\n\n"
                f"**Prix unitaire :** {fmt(selected.price)} KZ"
            ),
            color=r.get("color", config.BRAND["info"]),
        )
    else:
        e = embed_info(f"🛒 Boutique — {category}", "Choisis un item dans le menu ci-dessous.")
        items = items_by_category(category)
        if items:
            preview = "\n".join([f"• **{it.name}** — {fmt(it.price)} KZ" for it in items[:8]])
            e.add_field(name="📦 Aperçu", value=preview, inline=False)

    e.set_footer(text=f"{config.BRAND['name']} • Page {page+1}/{max(1,pages)} • Acheter x1/x5")
    return e



def build_shop_embed(category: str, selected: ShopItem | None = None) -> discord.Embed:
    """Compat: utilisé par d'autres cogs (ex: admin panel)."""
    return _category_embed(category, selected, page=0, pages=1)

class CategorySelect(discord.ui.Select):
    def __init__(self, view: "ShopView"):
        self.shop_view = view
        super().__init__(
            placeholder="📂 Choisir une catégorie…",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=c, value=c) for c in config.SHOP_CATEGORIES],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.shop_view.category = self.values[0]
        self.shop_view.page = 0
        self.shop_view.item_id = None
        self.shop_view._rebuild_item_select()

        await interaction.response.edit_message(
            embed=self.shop_view.current_embed(interaction.user.id),
            view=self.shop_view,
        )


class ItemSelect(discord.ui.Select):
    def __init__(self, view: "ShopView"):
        self.shop_view = view
        items = self.shop_view.page_items()

        options: list[discord.SelectOption] = []
        for it in items[:25]:
            options.append(
                discord.SelectOption(
                    label=it.name[:100],
                    value=it.item_id,
                    description=f"{fmt(it.price)} KZ • {_rarity_tag(it)}"[:100],
                )
            )

        if not options:
            options = [discord.SelectOption(label="Aucun item", value="none")]

        super().__init__(
            placeholder="🧾 Choisir un item…",
            min_values=1,
            max_values=1,
            options=options,
            disabled=(len(options) == 1 and options[0].value == "none"),
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "none":
            return await interaction.response.send_message("Aucun item dans cette catégorie.", ephemeral=True)

        self.shop_view.item_id = val
        await interaction.response.edit_message(
            embed=self.shop_view.current_embed(interaction.user.id),
            view=self.shop_view,
        )


class ShopView(discord.ui.View):
    def __init__(self, db: Database, author_id: int, start_category: str | None = None):
        super().__init__(timeout=180)
        self.db = db
        self.author_id = author_id

        self.category = start_category or config.SHOP_CATEGORIES[0]
        self.page = 0
        self.per_page = 25
        self.item_id: str | None = None

        self.cat_select = CategorySelect(self)
        self.item_select: ItemSelect | None = None

        self.add_item(self.cat_select)
        self._rebuild_item_select()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Ce shop ne t'appartient pas. Fais `/shop`.", ephemeral=True)
            return False
        return True

    def _pages(self) -> int:
        items = items_by_category(self.category)
        if not items:
            return 1
        return (len(items) + self.per_page - 1) // self.per_page

    def page_items(self) -> list[ShopItem]:
        items = items_by_category(self.category)
        start = self.page * self.per_page
        end = start + self.per_page
        return items[start:end]

    def _rebuild_item_select(self):
        if self.item_select:
            try:
                self.remove_item(self.item_select)
            except Exception:
                pass
        self.item_select = ItemSelect(self)
        self.add_item(self.item_select)

    def current_embed(self, user_id: int) -> discord.Embed:
        selected = get_item(self.item_id) if self.item_id else None
        return _category_embed(self.category, selected, self.page, self._pages())

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True

    # ---------- NAV ----------
    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=3)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        pages = self._pages()
        self.page = (self.page - 1) % pages if pages > 0 else 0
        self.item_id = None
        self._rebuild_item_select()
        await interaction.response.edit_message(embed=self.current_embed(interaction.user.id), view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=3)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        pages = self._pages()
        self.page = (self.page + 1) % pages if pages > 0 else 0
        self.item_id = None
        self._rebuild_item_select()
        await interaction.response.edit_message(embed=self.current_embed(interaction.user.id), view=self)

    # ---------- BUY ----------
    async def _buy(self, interaction: discord.Interaction, qty: int):
        if not self.item_id:
            return await interaction.response.send_message("Choisis d'abord un item.", ephemeral=True)

        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        it = get_item(self.item_id)
        if not it:
            return await interaction.response.send_message("Item introuvable.", ephemeral=True)

        row = self.db.get_user(interaction.user.id)
        bal = int(row["balance"])
        total = int(it.price) * int(qty)

        if total > bal:
            return await interaction.response.send_message("❌ Solde insuffisant.", ephemeral=True)

        inv = self.db.get_inventory(interaction.user.id)
        inv[it.item_id] = int(inv.get(it.item_id, 0)) + int(qty)
        self.db.set_inventory(interaction.user.id, inv)
        self.db.add_balance(interaction.user.id, -total)
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])

        e = embed_win("✅ Achat", f"Tu as acheté **{it.name}** (`{it.item_id}`) × **{qty}**.")
        e.add_field(name="Prix unitaire", value=f"{fmt(it.price)} KZ", inline=True)
        e.add_field(name="💰 Total", value=f"{fmt(total)} KZ", inline=True)
        e.add_field(name="🏦 Solde", value=f"{fmt(new_bal)} KZ", inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🛒 Acheter x1", style=discord.ButtonStyle.success, row=2)
    async def buy_x1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._buy(interaction, 1)

    @discord.ui.button(label="🛒 Acheter x5", style=discord.ButtonStyle.success, row=2)
    async def buy_x5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._buy(interaction, 5)

    @discord.ui.button(label="🎒 Inventaire", style=discord.ButtonStyle.primary, row=2)
    async def inv_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        inv = self.db.get_inventory(interaction.user.id)
        if not inv:
            return await interaction.response.send_message(embed=embed_neutral("🎒 Inventaire", "Vide."), ephemeral=True)

        lines = []
        for item_id, qty in inv.items():
            it = get_item(item_id)
            name = it.name if it else item_id
            lines.append(f"• **{name}** (`{item_id}`) × **{qty}**")
        e = embed_neutral("🎒 Inventaire", "\n".join(lines))
        e.set_footer(text="Utilise /use <item_id> pour utiliser un item")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="✖️ Fermer", style=discord.ButtonStyle.danger, row=2)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(view=self)


# ============================================
# Autocomplete pour les items
# ============================================

async def item_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete pour les IDs d'items du shop."""
    choices = []
    current_lower = current.lower()
    for it in DEFAULT_ITEMS:
        if current_lower in it.item_id.lower() or current_lower in it.name.lower():
            choices.append(app_commands.Choice(name=f"{it.name} ({it.item_id})", value=it.item_id))
        if len(choices) >= 25:
            break
    return choices


async def inventory_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete pour les items de l'inventaire de l'utilisateur."""
    choices = []
    try:
        bot: commands.Bot = interaction.client  # type: ignore
        db: Database = bot.db  # type: ignore
        inv = db.get_inventory(interaction.user.id)
        current_lower = current.lower()
        for item_id, qty in inv.items():
            if int(qty) <= 0:
                continue
            it = get_item(item_id)
            name = it.name if it else item_id
            if current_lower in item_id.lower() or current_lower in name.lower():
                choices.append(app_commands.Choice(name=f"{name} x{qty}", value=item_id))
            if len(choices) >= 25:
                break
    except Exception:
        pass
    return choices


# ============================================
# Cog principal
# ============================================

class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    async def cog_app_command_invoke(self, interaction: discord.Interaction):
        allowed = await enforce_blacklist(self.db, interaction)
        if not allowed:
            raise app_commands.CheckFailure("Blacklisted")

    # ============================================
    # /shop - Boutique interactive
    # ============================================
    @app_commands.command(name="shop", description="🛒 Boutique interactive")
    @app_commands.describe(category="Catégorie à ouvrir directement (optionnel)")
    async def shop(self, interaction: discord.Interaction, category: str | None = None):
        cat = category or config.SHOP_CATEGORIES[0]
        if cat not in config.SHOP_CATEGORIES:
            return await interaction.response.send_message(
                embed=embed_lose("❌ Shop", f"Catégories: {', '.join(config.SHOP_CATEGORIES)}"),
                ephemeral=True,
            )

        view = ShopView(self.db, interaction.user.id, start_category=cat)
        await interaction.response.send_message(embed=view.current_embed(interaction.user.id), view=view, ephemeral=True)

    # ============================================
    # /inventory - Voir son inventaire
    # ============================================
    @app_commands.command(name="inventory", description="🎒 Voir ton inventaire")
    async def inventory(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        inv = self.db.get_inventory(interaction.user.id)
        
        if not inv:
            e = embed_neutral("🎒 Inventaire", "Ton inventaire est vide.\n\nUtilise `/shop` pour acheter des items !")
            return await interaction.response.send_message(embed=e, ephemeral=True)

        lines = []
        total_value = 0
        for item_id, qty in inv.items():
            qty = int(qty)
            if qty <= 0:
                continue
            it = get_item(item_id)
            name = it.name if it else item_id
            rarity = _rarity_tag(it) if it else "⚪ Unknown"
            value = (it.price * qty) if it else 0
            total_value += value
            lines.append(f"{rarity} **{name}** (`{item_id}`) × **{qty}**")
        
        if not lines:
            e = embed_neutral("🎒 Inventaire", "Ton inventaire est vide.\n\nUtilise `/shop` pour acheter des items !")
            return await interaction.response.send_message(embed=e, ephemeral=True)

        e = embed_neutral("🎒 Ton Inventaire", "\n".join(lines))
        e.add_field(name="💰 Valeur totale", value=f"{fmt(total_value)} KZ", inline=False)
        e.set_footer(text="Utilise /use <item_id> pour utiliser un item")
        await interaction.response.send_message(embed=e, ephemeral=True)

    # Alias /inv
    @app_commands.command(name="inv", description="🎒 Voir ton inventaire (alias)")
    async def inv_alias(self, interaction: discord.Interaction):
        await self.inventory.callback(self, interaction)

    # ============================================
    # /buy - Acheter un item directement
    # ============================================
    @app_commands.command(name="buy", description="🛒 Acheter un item directement")
    @app_commands.describe(item="ID de l'item à acheter", quantity="Quantité (défaut: 1)")
    @app_commands.autocomplete(item=item_autocomplete)
    async def buy(self, interaction: discord.Interaction, item: str, quantity: app_commands.Range[int, 1, 100] = 1):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        
        it = get_item(item)
        if not it:
            # Chercher par nom partiel
            item_lower = item.lower()
            for shop_item in DEFAULT_ITEMS:
                if item_lower in shop_item.item_id.lower() or item_lower in shop_item.name.lower():
                    it = shop_item
                    break
        
        if not it:
            e = embed_lose("❌ Item introuvable", f"L'item `{item}` n'existe pas.\n\nUtilise `/shop` pour voir les items disponibles.")
            return await interaction.response.send_message(embed=e, ephemeral=True)

        row = self.db.get_user(interaction.user.id)
        bal = int(row["balance"])
        total = it.price * quantity

        if total > bal:
            e = embed_lose("❌ Solde insuffisant", f"Tu as besoin de **{fmt(total)}** KZ mais tu n'as que **{fmt(bal)}** KZ.")
            return await interaction.response.send_message(embed=e, ephemeral=True)

        # Effectuer l'achat
        inv = self.db.get_inventory(interaction.user.id)
        inv[it.item_id] = int(inv.get(it.item_id, 0)) + quantity
        self.db.set_inventory(interaction.user.id, inv)
        self.db.add_balance(interaction.user.id, -total)
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])

        e = embed_win("✅ Achat réussi", f"Tu as acheté **{it.name}** × **{quantity}**")
        e.add_field(name="💳 Prix unitaire", value=f"{fmt(it.price)} KZ", inline=True)
        e.add_field(name="💰 Total payé", value=f"{fmt(total)} KZ", inline=True)
        e.add_field(name="🏦 Nouveau solde", value=f"{fmt(new_bal)} KZ", inline=True)
        e.add_field(name="📦 En inventaire", value=f"{inv[it.item_id]}× {it.name}", inline=False)
        e.set_footer(text=f"Utilise /use {it.item_id} pour l'utiliser")
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ============================================
    # /use - Utiliser un item
    # ============================================
    @app_commands.command(name="use", description="✨ Utiliser un item de ton inventaire")
    @app_commands.describe(item="ID de l'item à utiliser")
    @app_commands.autocomplete(item=inventory_autocomplete)
    async def use(self, interaction: discord.Interaction, item: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        
        inv = self.db.get_inventory(interaction.user.id)
        qty = int(inv.get(item, 0))
        
        if qty <= 0:
            e = embed_lose("❌ Item non possédé", f"Tu ne possèdes pas l'item `{item}`.\n\nUtilise `/inventory` pour voir tes items.")
            return await interaction.response.send_message(embed=e, ephemeral=True)

        it = get_item(item)
        if not it:
            e = embed_lose("❌ Item inconnu", f"L'item `{item}` n'est pas reconnu.")
            return await interaction.response.send_message(embed=e, ephemeral=True)

        # Vérifier si l'item est utilisable
        if not it.effect_key:
            # Cadres de profil
            if item.startswith("frame_"):
                e = embed_info(
                    "🎨 Cadre de profil",
                    f"Tu possèdes **{it.name}**.\n\n"
                    "➡️ Pour l'activer: `/cosmetic frameequip <cadre>`\n"
                    "➡️ Pour le retirer: `/cosmetic frameremove`",
                )
                return await interaction.response.send_message(embed=e, ephemeral=True)
            
            e = embed_neutral("ℹ️ Item cosmétique", f"**{it.name}** est un item cosmétique et ne peut pas être \"utilisé\".\n\nIl s'affiche automatiquement sur ton profil.")
            return await interaction.response.send_message(embed=e, ephemeral=True)

        # Appliquer l'effet selon le type
        now = datetime.now(timezone.utc)
        effect_key = it.effect_key
        duration = it.duration_minutes or 0

        # ==== IMMUNITY (Boucliers) ====
        if effect_key == "immunity":
            row = self.db.get_user(interaction.user.id)
            current_imm = None
            if row and row["immunity_until"]:
                try:
                    current_imm = datetime.fromisoformat(row["immunity_until"])
                except:
                    pass
            
            base = current_imm if (current_imm and current_imm > now) else now
            new_until = base + timedelta(minutes=duration)
            self.db.set_user_field(interaction.user.id, "immunity_until", new_until.isoformat())
            
            # Retirer l'item
            self.db.remove_item(interaction.user.id, item, 1)
            
            e = embed_win("🛡️ Bouclier activé !", f"Tu es protégé contre le vol pendant **{duration} minutes**.")
            e.add_field(name="⏰ Expire", value=f"<t:{int(new_until.timestamp())}:R>", inline=True)
            e.add_field(name="📦 Restant", value=f"{qty - 1}× {it.name}", inline=True)
            return await interaction.response.send_message(embed=e, ephemeral=True)

        # ==== VIP ====
        if effect_key == "vip":
            row = self.db.get_user(interaction.user.id)
            current_vip = None
            if row and row["vip_until"]:
                try:
                    current_vip = datetime.fromisoformat(row["vip_until"])
                except:
                    pass
            
            base = current_vip if (current_vip and current_vip > now) else now
            new_until = base + timedelta(minutes=duration)
            self.db.set_user_field(interaction.user.id, "vip_until", new_until.isoformat())
            
            # Retirer l'item
            self.db.remove_item(interaction.user.id, item, 1)
            
            days = duration // (24 * 60)
            e = embed_win("👑 VIP activé !", f"Tu es maintenant VIP pendant **{days} jours** !")
            e.add_field(name="⏰ Expire", value=f"<t:{int(new_until.timestamp())}:R>", inline=True)
            e.add_field(name="📦 Restant", value=f"{qty - 1}× {it.name}", inline=True)
            return await interaction.response.send_message(embed=e, ephemeral=True)

        # ==== BOOSTS ====
        if effect_key.startswith("boost_"):
            boosts = self.db.get_boosts(interaction.user.id)
            
            # Vérifier si un boost du même type est déjà actif
            existing_until = boosts.get(effect_key)
            if existing_until:
                try:
                    existing_dt = datetime.fromisoformat(existing_until)
                    if existing_dt > now:
                        # Étendre le boost existant
                        new_until = existing_dt + timedelta(minutes=duration)
                    else:
                        new_until = now + timedelta(minutes=duration)
                except:
                    new_until = now + timedelta(minutes=duration)
            else:
                new_until = now + timedelta(minutes=duration)
            
            boosts[effect_key] = new_until.isoformat()
            self.db.set_boosts(interaction.user.id, boosts)
            
            # Retirer l'item
            self.db.remove_item(interaction.user.id, item, 1)
            
            boost_names = {
                "boost_all": "🎯 Chance Globale",
                "boost_roulette": "🎡 Boost Roulette",
                "boost_blackjack": "🃏 Boost Blackjack",
                "boost_crash": "📈 Boost Crash",
                "boost_steal": "🥷 Boost Vol",
            }
            boost_name = boost_names.get(effect_key, effect_key)
            
            e = embed_win(f"{boost_name} activé !", f"**{it.name}** est maintenant actif pendant **{duration} minutes** !")
            e.add_field(name="⏰ Expire", value=f"<t:{int(new_until.timestamp())}:R>", inline=True)
            e.add_field(name="📦 Restant", value=f"{qty - 1}× {it.name}", inline=True)
            return await interaction.response.send_message(embed=e, ephemeral=True)

        # ==== SETPROFILE (ticket consommable) ====
        if effect_key == "setprofile":
            e = embed_win("🎫 Ticket SetProfile", f"Tu possèdes **{qty}× {it.name}**.\n\nCe ticket te permet de définir une bannière sur ton profil.\nUtilise `/profileset banner <url>` pour l'utiliser (le ticket sera consommé automatiquement).")
            return await interaction.response.send_message(embed=e, ephemeral=True)

        # ==== EFFET INCONNU ====
        e = embed_neutral("❓ Effet inconnu", f"L'item `{it.name}` a un effet non reconnu: `{effect_key}`")
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ============================================
    # /boosts - Voir ses boosts actifs
    # ============================================
    @app_commands.command(name="boosts", description="✨ Voir tes boosts actifs")
    async def boosts(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        
        boosts = self.db.get_boosts(interaction.user.id)
        row = self.db.get_user(interaction.user.id)
        
        now = datetime.now(timezone.utc)
        active_boosts = []
        
        # Vérifier VIP
        if row and row["vip_until"]:
            try:
                vip_until = datetime.fromisoformat(row["vip_until"])
                if vip_until > now:
                    active_boosts.append(f"👑 **VIP** — expire <t:{int(vip_until.timestamp())}:R>")
            except:
                pass
        
        # Vérifier Immunité
        if row and row["immunity_until"]:
            try:
                imm_until = datetime.fromisoformat(row["immunity_until"])
                if imm_until > now:
                    active_boosts.append(f"🛡️ **Immunité** — expire <t:{int(imm_until.timestamp())}:R>")
            except:
                pass
        
        # Vérifier boosts temporaires
        boost_names = {
            "boost_all": "🎯 Chance Globale (+10%)",
            "boost_roulette": "🎡 Roulette (+20%)",
            "boost_blackjack": "🃏 Blackjack (+20%)",
            "boost_crash": "📈 Crash (+20%)",
            "boost_steal": "🥷 Vol (+20%)",
        }
        
        for boost_key, boost_name in boost_names.items():
            if boost_key in boosts:
                try:
                    boost_until = datetime.fromisoformat(boosts[boost_key])
                    if boost_until > now:
                        active_boosts.append(f"{boost_name} — expire <t:{int(boost_until.timestamp())}:R>")
                except:
                    pass
        
        if not active_boosts:
            e = embed_neutral("✨ Boosts actifs", "Tu n'as aucun boost actif.\n\nAchète des boosts dans le `/shop` !")
        else:
            e = embed_win("✨ Boosts actifs", "\n".join(active_boosts))
        
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(ShopCog(bot, db))
