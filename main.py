# -*- coding: utf-8 -*-
"""KZ Casino Bot (modulaire)

Structure:
  - main.py                 : point d'entrée
  - kz_casino_bot/config.py : configuration (.env)
  - kz_casino_bot/db.py     : base de données
  - kz_casino_bot/cogs/*    : commandes (slash)

Lancer:
  pip install -U discord.py python-dotenv
  # .env : DISCORD_TOKEN=...  OWNER_ID=... (optionnel)
  python main.py
"""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from kz_casino_bot import config
from kz_casino_bot.db import Database
from keep_alive import keep_alive


class CasinoCommandTree(app_commands.CommandTree):
    """Custom CommandTree avec vérification des salons autorisés."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Vérifie si la commande peut être utilisée dans ce salon."""
        # Récupérer le bot et la db
        bot: CasinoBot = self.client  # type: ignore
        db = bot.db

        # Autoriser partout: /help et /panel (et autres dans COMMANDS_ALLOWED_EVERYWHERE)
        try:
            cmd_name = interaction.command.name if interaction.command else None
        except Exception:
            cmd_name = None
        allowed_everywhere = getattr(config, "COMMANDS_ALLOWED_EVERYWHERE", {"help", "panel"})
        if cmd_name in allowed_everywhere:
            return True

        # Refuser les DMs
        if interaction.guild is None:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Utilise cette commande sur le serveur, dans un salon dédié.",
                    ephemeral=True,
                )
            return False

        # Owner bot
        if config.OWNER_ID and interaction.user.id == config.OWNER_ID:
            return True

        # Admin serveur
        if getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.administrator:
            return True

        # Admin bot (table bot_admins)
        try:
            if db.is_bot_admin(interaction.user.id):
                return True
        except Exception:
            pass

        # Utilisateur autorisé partout (par serveur)
        try:
            if db.is_bypass_user(interaction.guild.id, interaction.user.id):
                return True
        except Exception:
            pass

        # ============================================
        # Récupérer les restrictions (config.py + DB)
        # ============================================
        
        # Depuis config.py
        config_channels = getattr(config, "ALLOWED_CHANNEL_IDS", []) or []
        config_categories = getattr(config, "ALLOWED_CATEGORY_IDS", []) or []
        
        # Depuis la base de données
        db_channels = []
        db_categories = []
        try:
            db_channels = db.list_allowed_channels(interaction.guild.id)
        except Exception:
            db_channels = []
        try:
            db_categories = db.list_allowed_categories(interaction.guild.id)
        except Exception:
            db_categories = []
        
        # Combiner les deux sources
        allowed_channels = set(config_channels) | set(db_channels)
        allowed_categories = set(config_categories) | set(db_categories)

        # Si aucune restriction => autoriser partout
        if not allowed_channels and not allowed_categories:
            return True

        # Vérifier si le salon est directement autorisé
        if allowed_channels and interaction.channel_id in allowed_channels:
            return True

        # Récupérer la catégorie du salon (ou du parent si c'est un thread)
        channel = interaction.channel
        category_id = None
        if hasattr(channel, "category_id") and channel.category_id:
            category_id = channel.category_id
        elif hasattr(channel, "parent") and channel.parent:
            # Thread -> récupérer la catégorie du salon parent
            parent = channel.parent
            if hasattr(parent, "category_id"):
                category_id = parent.category_id

        # Vérifier si le salon est dans une catégorie autorisée
        if allowed_categories and category_id and category_id in allowed_categories:
            return True

        # ============================================
        # Construire le message d'erreur
        # ============================================
        error_parts = []
        if allowed_categories:
            cats = []
            for cat_id in list(allowed_categories)[:5]:
                cat = discord.utils.get(interaction.guild.categories, id=cat_id)
                if cat:
                    cats.append(f"📁 **{cat.name}**")
            if cats:
                error_parts.append("Catégories: " + ", ".join(cats))
        if allowed_channels:
            chans_list = list(allowed_channels)[:5]
            chans = " ".join(f"<#{cid}>" for cid in chans_list)
            more = f" (+{len(allowed_channels)-5} autres)" if len(allowed_channels) > 5 else ""
            error_parts.append(f"Salons: {chans}{more}")

        error_msg = "\n".join(error_parts) if error_parts else "Contacte un admin."
        
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"❌ Tu n'es pas dans le bon salon.\n➡️ Utilise les commandes dans :\n{error_msg}",
                ephemeral=True,
            )
        return False


class CasinoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True  # IMPORTANT pour le tracking vocal
        super().__init__(
            command_prefix="!",
            intents=intents,
            tree_cls=CasinoCommandTree  # Utilise notre CommandTree personnalisé
        )
        self.db = Database(config.DB_PATH)

    async def setup_hook(self):
        # init db
        self.db.init()

        # default win gifs
        if self.db.get_setting("win_gifs") is None:
            try:
                import json as _json
                self.db.set_setting("win_gifs", _json.dumps(getattr(config, "DEFAULT_WIN_GIFS", [])))
            except Exception:
                self.db.set_setting("win_gifs", "[]")

        # load cogs
        await self.load_extension("kz_casino_bot.cogs.economy")
        await self.load_extension("kz_casino_bot.cogs.games")
        await self.load_extension("kz_casino_bot.cogs.shop")
        await self.load_extension("kz_casino_bot.cogs.admin")
        await self.load_extension("kz_casino_bot.cogs.profile")
        await self.load_extension("kz_casino_bot.cogs.help")

        # NEW: prediction game
        await self.load_extension("kz_casino_bot.cogs.prediction")

        # NEW: PvP / Duels
        await self.load_extension("kz_casino_bot.cogs.pvp")

        # NEW: loans / prêts (banque + P2P)
        await self.load_extension("kz_casino_bot.cogs.loans")

        # NEW: activity rewards
        await self.load_extension("kz_casino_bot.cogs.activity_rewards")

        # sync commands
        await self.tree.sync()
        print("✅ Slash commands synchronisées")


async def main():
    if not config.TOKEN:
        raise RuntimeError("DISCORD_TOKEN manquant. Mets-le dans .env")
    keep_alive()
    bot = CasinoBot()

    @bot.event
    async def on_ready():
        print(f"🎰 Connecté en tant que {bot.user}")

    try:
        await bot.start(config.TOKEN)
    except KeyboardInterrupt:
        pass
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot arrêté proprement.")
