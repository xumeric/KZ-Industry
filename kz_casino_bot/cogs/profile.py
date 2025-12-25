# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import Database
from ..shop_data import get_item
from ..leveling import level_from_xp, xp_for_level, xp_progress, title_for_level, title_and_icon_for_level
from ..leveling import unlocked_profile_colors, grade_for_level
from ..utils import (
    embed_info,
    embed_lose,
    embed_win,
    fmt,
    now_utc,
    parse_dt,
    human_time,
)
from ..checks import enforce_blacklist


# Regex pour valider les URLs d'images
IMAGE_URL_PATTERN = re.compile(
    r'^https?://.*\.(png|jpg|jpeg|gif|webp)(\?.*)?$',
    re.IGNORECASE
)

# Couleurs prédéfinies
PROFILE_COLORS = {
    "gris": 0x64748B,
    "gray": 0x64748B,
    "grey": 0x64748B,
    "rouge": 0xDC2626,
    "red": 0xDC2626,
    "vert": 0x16A34A,
    "green": 0x16A34A,
    "bleu": 0x2563EB,
    "blue": 0x2563EB,
    "violet": 0x7C3AED,
    "purple": 0x7C3AED,
    "orange": 0xEA580C,
    "jaune": 0xEAB308,
    "yellow": 0xEAB308,
    "rose": 0xEC4899,
    "pink": 0xEC4899,
    "cyan": 0x06B6D4,
    "blanc": 0xF8FAFC,
    "white": 0xF8FAFC,
    "noir": 0x1E293B,
    "black": 0x1E293B,
    "or": 0xF59E0B,
    "gold": 0xF59E0B,
}

# Alias -> couleur "canonique" (celle qu'on utilise pour les déblocages)
COLOR_CANONICAL = {
    "gris": "gris",
    "gray": "gris",
    "grey": "gris",
    "bleu": "bleu",
    "blue": "bleu",
    "violet": "violet",
    "purple": "violet",
    "orange": "orange",
    "rouge": "rouge",
    "red": "rouge",
    "or": "or",
    "gold": "or",
    "jaune": "or",  # on force sur "or" pour rester cohérent avec les grades
    "yellow": "or",
    "cyan": "cyan",
    "rose": "rose",
    "pink": "rose",
    "blanc": "blanc",
    "white": "blanc",
    "noir": "noir",
    "black": "noir",
}


# =============================
# COSMÉTIQUES : CADRES PROFIL
# =============================
# Chaque cadre est un item shop "frame_*". Le joueur doit l'équiper pour qu'il s'affiche.
# Compat rétro: si un joueur possède l'ancien cadre or mais n'a jamais équipé de cadre,
# on l'affiche quand même pour ne pas "casser" les profils.
FRAME_STYLES = {
    "frame_gold": {
        "embed_color": 0xFFD700,
        "title_prefix": "✨👑 ",
        "badge": "🟡 **CADRE OR** 🟡",
        "footer": "Cadre Or équipé",
    },
    "frame_silver": {
        "embed_color": 0xC0C0C0,
        "title_prefix": "✨🥈 ",
        "badge": "⚪ **CADRE ARGENT** ⚪",
        "footer": "Cadre Argent équipé",
    },
    "frame_ruby": {
        "embed_color": 0xE11D48,
        "title_prefix": "✨💎 ",
        "badge": "🔴 **CADRE RUBIS** 🔴",
        "footer": "Cadre Rubis équipé",
    },
    "frame_diamond": {
        "embed_color": 0x38BDF8,
        "title_prefix": "✨💠 ",
        "badge": "🔷 **CADRE DIAMANT** 🔷",
        "footer": "Cadre Diamant équipé",
    },
    "frame_neon": {
        "embed_color": 0xA855F7,
        "title_prefix": "✨🌈 ",
        "badge": "🟣 **CADRE NÉON** 🟣",
        "footer": "Cadre Néon équipé",
    },
}


def get_rank_emoji(position: int) -> str:
    """Retourne l'emoji de rang selon la position."""
    if position == 1:
        return "🥇"
    elif position == 2:
        return "🥈"
    elif position == 3:
        return "🥉"
    elif position <= 10:
        return "🏅"
    elif position <= 50:
        return "⭐"
    else:
        return "👤"


# --- XP / Niveaux (courbe difficile) ---
# (implémentation centralisée dans kz_casino_bot/leveling.py)

def get_level_from_xp(xp: int) -> int:
    return level_from_xp(xp, cap=int(getattr(config, 'XP_LEVEL_CAP', 100)))

def get_xp_for_level(level: int) -> int:
    return xp_for_level(level)


def calculate_winrate(wins: int, losses: int) -> float:
    """Calcule le taux de victoire."""
    total = wins + losses
    if total == 0:
        return 0.0
    return (wins / total) * 100


def safe_row_get(row, key, default=None):
    """Accède à un champ de sqlite3.Row de manière sûre."""
    try:
        val = row[key]
        return val if val is not None else default
    except (KeyError, IndexError):
        return default


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db


    def _consume_setprofile_token(self, user_id: int) -> bool:
        """Return True if user has a setprofile token and consumes 1 of it."""
        inv = self.db.get_inventory(user_id)
        if int(inv.get("setprofile", 0)) <= 0:
            return False
        inv["setprofile"] = int(inv.get("setprofile", 0)) - 1
        if inv["setprofile"] <= 0:
            inv.pop("setprofile", None)
        self.db.set_inventory(user_id, inv)
        return True

    async def cog_app_command_invoke(self, interaction: discord.Interaction):
        allowed = await enforce_blacklist(self.db, interaction)
        if not allowed:
            raise app_commands.CheckFailure("Blacklisted")

    def _get_user_rank(self, user_id: int) -> int:
        """Récupère le rang d'un utilisateur par balance."""
        rows = self.db.fetchall("SELECT user_id FROM users ORDER BY balance DESC")
        for i, row in enumerate(rows, start=1):
            if int(row["user_id"]) == user_id:
                return i
        return 0

    def _build_profile_embed(self, user: discord.User | discord.Member, row) -> discord.Embed:
        """Construit l'embed de profil."""
        user_id = user.id

        inv = self.db.get_inventory(user_id)

        # Cadre équipé (si possédé). Compat: si le joueur possède frame_gold et n'a jamais choisi de cadre,
        # on continue à l'afficher par défaut.
        equipped_frame = safe_row_get(row, "profile_frame")
        frame_id: str | None = None

        # IMPORTANT:
        # - Compat historique: si profile_frame est NULL et que le joueur possède frame_gold, on l'affiche par défaut.
        # - MAIS si l'utilisateur a explicitement retiré son cadre via /cosmetic frameremove,
        #   on stocke la valeur "none" pour désactiver ce fallback (sinon le cadre or revient tout seul).
        if isinstance(equipped_frame, str) and equipped_frame.lower() == "none":
            frame_id = None
        elif equipped_frame and int(inv.get(str(equipped_frame), 0)) > 0:
            frame_id = str(equipped_frame)
        elif equipped_frame:
            # cadre équipé mais plus possédé => on déséquipe silencieusement
            frame_id = None
        else:
            # ancien comportement: cadre or auto si possédé
            if int(inv.get("frame_gold", 0)) > 0:
                frame_id = "frame_gold"

        frame_style = FRAME_STYLES.get(frame_id) if frame_id else None
        
        # Couleur personnalisée ou par défaut
        color_str = safe_row_get(row, "profile_color")
        if frame_style:
            # Un cadre force une couleur "thème" pour l'embed
            color = int(frame_style["embed_color"])
        elif color_str and color_str in PROFILE_COLORS:
            color = PROFILE_COLORS[color_str]
        elif color_str and str(color_str).startswith("#"):
            try:
                color = int(color_str[1:], 16)
            except Exception:
                color = config.BRAND["info"]
        else:
            color = config.BRAND["info"]

        # Titre avec cadre
        if frame_style:
            title = f"{frame_style['title_prefix']}👤 Profil de {user.display_name}"
        else:
            title = f"👤 Profil de {user.display_name}"

        e = discord.Embed(
            title=title,
            color=color
        )

        # Bannière (image en haut)
        banner_url = safe_row_get(row, "profile_banner")
        if banner_url:
            e.set_image(url=banner_url)

        # Avatar
        e.set_thumbnail(url=user.display_avatar.url)

        # Bio
        bio = safe_row_get(row, "profile_bio") or "*Aucune bio définie*"
        e.description = f"📝 {bio}"
        
        # Afficher le cadre dans la description
        if frame_style:
            e.description = f"{frame_style['badge']}\n\n{e.description}"

        # Stats principales
        balance = int(safe_row_get(row, "balance", 0))
        rank = self._get_user_rank(user.id)
        rank_emoji = get_rank_emoji(rank)
        
        xp = int(safe_row_get(row, "xp", 0))
        cap = int(getattr(config, "XP_LEVEL_CAP", 100))
        level, xp_in_level, xp_needed = xp_progress(xp, cap=cap)
        
        # Barre de progression XP
        if xp_needed <= 0:
            progress_pct = 100
            xp_bar = "🟩" * 10
        else:
            progress_pct = min(100, int((xp_in_level / max(1, xp_needed)) * 100))
            progress_bars = progress_pct // 10
            xp_bar = "🟩" * progress_bars + "⬛" * (10 - progress_bars)

        e.add_field(
            name="💰 Solde",
            value=f"**{fmt(balance)}** KZ",
            inline=True
        )
        e.add_field(
            name=f"{rank_emoji} Rang",
            value=f"**#{rank}**",
            inline=True
        )
        e.add_field(
            name="⭐ Niveau",
            value=f"**{level}**/{cap}",
            inline=True
        )

        title, icon = title_and_icon_for_level(level, cap=cap)
        e.add_field(
            name="🎖️ Statut",
            value=f"{icon} **{title}**",
            inline=True
        )


        e.add_field(
            name="📊 Progression XP",
            value=(f"{xp_bar}\n`MAX`" if xp_needed <= 0 else f"{xp_bar}\n`{xp_in_level}/{xp_needed}` XP"),
            inline=False
        )

        # Stats de jeu
        games = int(safe_row_get(row, "games_played", 0))
        wins = int(safe_row_get(row, "wins", 0))
        losses = int(safe_row_get(row, "losses", 0))
        winrate = calculate_winrate(wins, losses)

        e.add_field(
            name="🎮 Parties",
            value=f"**{games}**",
            inline=True
        )
        e.add_field(
            name="✅ Victoires",
            value=f"**{wins}**",
            inline=True
        )
        e.add_field(
            name="❌ Défaites",
            value=f"**{losses}**",
            inline=True
        )
        e.add_field(
            name="📈 Winrate",
            value=f"**{winrate:.1f}%**",
            inline=True
        )

        # Statuts VIP/Immunité
        vip_until = parse_dt(safe_row_get(row, "vip_until"))
        imm_until = parse_dt(safe_row_get(row, "immunity_until"))
        now = now_utc()

        status_parts = []
        if vip_until and vip_until > now:
            left = int((vip_until - now).total_seconds())
            status_parts.append(f"👑 VIP ({human_time(left)})")
        if imm_until and imm_until > now:
            left = int((imm_until - now).total_seconds())
            status_parts.append(f"🛡️ Immunité ({human_time(left)})")

        if status_parts:
            e.add_field(
                name="✨ Statuts actifs",
                value="\n".join(status_parts),
                inline=False
            )

        # Date d'inscription
        created = safe_row_get(row, "created_at")
        if created:
            try:
                created_dt = datetime.fromisoformat(created)
                e.add_field(
                    name="📅 Inscrit le",
                    value=f"<t:{int(created_dt.timestamp())}:D>",
                    inline=True
                )
            except:
                pass

        # Footer avec indication du cadre
        if frame_style:
            e.set_footer(text=f"🏆 {config.BRAND['name']} • {frame_style['footer']}")
        else:
            e.set_footer(text=f"{config.BRAND['name']} • /profileset pour personnaliser")
        
        return e

    # ============================================
    # COMMANDES PRINCIPALES
    # ============================================

    @app_commands.command(name="profile", description="Voir ton profil ou celui d'un autre joueur")
    async def profile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        self.db.ensure_user(target.id, config.START_BALANCE)
        row = self.db.get_user(target.id)
        
        if not row:
            return await interaction.response.send_message(
                embed=embed_lose("❌ Profil", "Utilisateur non trouvé."),
                ephemeral=True
            )

        embed = self._build_profile_embed(target, row)
        await interaction.response.send_message(embed=embed)

    # ============================================
    # GROUPE DE COMMANDES SET
    # ============================================

    profile_set = app_commands.Group(name="profileset", description="Personnaliser ton profil")

    # ============================================
    # GROUPE COSMÉTIQUES
    # ============================================
    cosmetic = app_commands.Group(name="cosmetic", description="Gérer tes cosmétiques (cadres, etc.)")

    async def _owned_frames(self, user_id: int) -> list[str]:
        inv = self.db.get_inventory(user_id)
        frames = [k for k, v in inv.items() if k.startswith("frame_") and int(v) > 0 and k in FRAME_STYLES]
        # garder un ordre stable
        order = ["frame_gold", "frame_diamond", "frame_ruby", "frame_neon", "frame_silver"]
        frames.sort(key=lambda x: order.index(x) if x in order else 999)
        return frames

    async def frame_autocomplete(self, interaction: discord.Interaction, current: str):
        # propose uniquement les cadres possédés
        try:
            frames = await self._owned_frames(interaction.user.id)
        except Exception:
            frames = []
        current = (current or "").lower()
        choices: list[app_commands.Choice[str]] = []
        for fid in frames:
            if current and current not in fid.lower():
                continue
            it = get_item(fid)
            label = it.name if it else fid
            choices.append(app_commands.Choice(name=label, value=fid))
        return choices[:25]

    @cosmetic.command(name="framelist", description="Voir les cadres que tu possèdes")
    async def cosmetic_frame_list(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.get_user(interaction.user.id)
        equipped = safe_row_get(row, "profile_frame") if row else None
        frames = await self._owned_frames(interaction.user.id)

        if not frames:
            return await interaction.response.send_message(
                embed=embed_info("🎨 Cadres", "Tu ne possèdes aucun cadre pour le moment. Va dans `/shop` → catégorie **Cosmetics**."),
                ephemeral=True,
            )

        lines = []
        for fid in frames:
            it = get_item(fid)
            name = it.name if it else fid
            mark = "✅" if equipped == fid else ""
            lines.append(f"{mark} **{name}** (`{fid}`)")

        desc = "\n".join(lines)
        e = embed_info("🎨 Tes cadres", desc)
        if equipped and not (isinstance(equipped, str) and equipped.lower() == "none"):
            e.set_footer(text=f"Cadre équipé: {equipped} • /cosmetic frameequip pour changer")
        return await interaction.response.send_message(embed=e, ephemeral=True)

    @cosmetic.command(name="frameequip", description="Équiper un cadre de profil")
    @app_commands.describe(frame_id="Cadre à équiper (doit être dans ton inventaire)")
    @app_commands.autocomplete(frame_id=frame_autocomplete)
    async def cosmetic_frame_equip(self, interaction: discord.Interaction, frame_id: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        inv = self.db.get_inventory(interaction.user.id)
        if int(inv.get(frame_id, 0)) <= 0 or frame_id not in FRAME_STYLES:
            return await interaction.response.send_message(
                embed=embed_lose("❌ Cadre introuvable", "Tu ne possèdes pas ce cadre (ou il est invalide)."),
                ephemeral=True,
            )

        self.db.set_user_field(interaction.user.id, "profile_frame", frame_id)
        it = get_item(frame_id)
        name = it.name if it else frame_id
        return await interaction.response.send_message(
            embed=embed_win("✅ Cadre équipé", f"Tu as équipé **{name}**.\n\nVa voir ton `/profile` ✨"),
            ephemeral=True,
        )

    @cosmetic.command(name="frameremove", description="Retirer ton cadre de profil")
    async def cosmetic_frame_remove(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        # On met "none" (et pas NULL) pour empêcher le fallback "cadre or auto".
        self.db.set_user_field(interaction.user.id, "profile_frame", "none")
        return await interaction.response.send_message(
            embed=embed_win("✅ Cadre retiré", "Ton profil est repassé sans cadre."),
            ephemeral=True,
        )

    @profile_set.command(name="banner", description="Définir ta bannière (image ou GIF)")
    @app_commands.describe(url="URL de l'image ou GIF (png, jpg, gif, webp)")
    async def set_banner(self, interaction: discord.Interaction, url: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)

        # 🔒 Requiert l'item setprofile (ticket) acheté dans le shop
        if not self._consume_setprofile_token(interaction.user.id):
            return await interaction.response.send_message(
                embed=embed_lose("❌ SetProfile", "Tu dois acheter **Ticket SetProfile** (`setprofile`) dans le shop pour mettre une image sur ton profil."),
                ephemeral=True,
            )


        # Valider l'URL
        if not IMAGE_URL_PATTERN.match(url):
            return await interaction.response.send_message(
                embed=embed_lose(
                    "❌ URL invalide",
                    "L'URL doit pointer vers une image (png, jpg, gif, webp).\n\n"
                    "**Exemples valides :**\n"
                    "• `https://i.imgur.com/abc123.gif`\n"
                    "• `https://media.tenor.com/xyz.gif`\n"
                    "• `https://exemple.com/image.png`"
                ),
                ephemeral=True
            )

        self.db.set_user_field(interaction.user.id, "profile_banner", url)
        
        e = embed_win("✅ Bannière mise à jour", "Ta bannière a été modifiée !")
        e.set_image(url=url)
        await interaction.response.send_message(embed=e)

    @profile_set.command(name="bio", description="Définir ta bio")
    @app_commands.describe(texte="Ta bio (max 200 caractères)")
    async def set_bio(self, interaction: discord.Interaction, texte: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)

        if len(texte) > 200:
            return await interaction.response.send_message(
                embed=embed_lose("❌ Bio trop longue", "Maximum 200 caractères."),
                ephemeral=True
            )

        self.db.set_user_field(interaction.user.id, "profile_bio", texte)
        await interaction.response.send_message(
            embed=embed_win("✅ Bio mise à jour", f"Nouvelle bio : *{texte}*")
        )

    @profile_set.command(name="color", description="Définir la couleur de ton profil")
    @app_commands.describe(couleur="Nom de couleur ou code hex (#FF5733)")
    async def set_color(self, interaction: discord.Interaction, couleur: str):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)

        # Niveau -> couleurs débloquées
        row = self.db.get_user(interaction.user.id)
        xp = int(safe_row_get(row, "xp", 0)) if row else 0
        cap = int(getattr(config, "XP_LEVEL_CAP", 100))
        level = level_from_xp(xp, cap=cap)
        unlocked = unlocked_profile_colors(level, cap=cap)

        color_input = couleur.lower().strip()
        
        # Vérifier si c'est un nom de couleur (et qu'il est débloqué)
        if color_input in PROFILE_COLORS:
            canonical = COLOR_CANONICAL.get(color_input, color_input)

            # Autoriser uniquement les couleurs débloquées par les grades (sauf blanc/noir si déjà proposés)
            # Les couleurs "bonus" du dictionnaire (blanc/noir) restent disponibles uniquement si elles sont débloquées.
            if canonical not in unlocked:
                next_grade = None
                for g in (10, 20, 35, 50, 70, 85, 100):
                    if g > level:
                        next_grade = g
                        break

                unlocked_str = ", ".join(unlocked) if unlocked else "gris"
                more = ""
                if next_grade:
                    ng = grade_for_level(next_grade, cap=cap)
                    more = f"\n\nProchaine couleur: **{ng.profile_color}** au niveau **{next_grade}**."

                return await interaction.response.send_message(
                    embed=embed_lose(
                        "🔒 Couleur non débloquée",
                        f"Tu as débloqué: **{unlocked_str}**.{more}",
                    ),
                    ephemeral=True,
                )

            self.db.set_user_field(interaction.user.id, "profile_color", canonical)
            color_hex = PROFILE_COLORS.get(canonical, PROFILE_COLORS[color_input])
            e = discord.Embed(
                title="✅ Couleur mise à jour",
                description=f"Nouvelle couleur : **{couleur}**",
                color=color_hex
            )
            return await interaction.response.send_message(embed=e)

        # Vérifier si c'est un code hex (réservé au niveau 100)
        if color_input.startswith("#") and len(color_input) == 7:
            if level < cap:
                return await interaction.response.send_message(
                    embed=embed_lose(
                        "🔒 Couleur personnalisée verrouillée",
                        f"Les codes hex sont disponibles uniquement au niveau **{cap}** (Maître du Casino).",
                    ),
                    ephemeral=True,
                )
            try:
                color_hex = int(color_input[1:], 16)
                self.db.set_user_field(interaction.user.id, "profile_color", color_input)
                e = discord.Embed(
                    title="✅ Couleur mise à jour",
                    description=f"Nouvelle couleur : **{couleur}**",
                    color=color_hex
                )
                return await interaction.response.send_message(embed=e)
            except:
                pass

        # Liste des couleurs disponibles
        colors_list = ", ".join(sorted(set(PROFILE_COLORS.keys())))
        await interaction.response.send_message(
            embed=embed_lose(
                "❌ Couleur invalide",
                f"**Couleurs disponibles :**\n{colors_list}\n\n"
                "**Ou utilise un code hex :** `#FF5733`"
            ),
            ephemeral=True
        )

    @profile_set.command(name="reset", description="Réinitialiser ton profil")
    async def reset_profile(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        self.db.set_user_field(interaction.user.id, "profile_banner", None)
        self.db.set_user_field(interaction.user.id, "profile_bio", None)
        self.db.set_user_field(interaction.user.id, "profile_color", None)
        self.db.set_user_field(interaction.user.id, "profile_frame", None)
        
        await interaction.response.send_message(
            embed=embed_win("✅ Profil réinitialisé", "Ton profil a été remis par défaut.")
        )

    @profile_set.command(name="removebanner", description="Retirer ta bannière")
    async def remove_banner(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)

        # 🔒 Requiert l'item setprofile (ticket) acheté dans le shop
        if not self._consume_setprofile_token(interaction.user.id):
            return await interaction.response.send_message(
                embed=embed_lose("❌ SetProfile", "Tu dois acheter **Ticket SetProfile** (`setprofile`) dans le shop pour modifier/supprimer ton image de profil."),
                ephemeral=True,
            )

        self.db.set_user_field(interaction.user.id, "profile_banner", None)
        
        await interaction.response.send_message(
            embed=embed_win("✅ Bannière retirée", "Ta bannière a été supprimée.")
        )

    # ============================================
    # ALIAS (raccourcis de commandes)
    # ============================================

    @app_commands.command(name="p", description="👤 Alias de /profile")
    @app_commands.describe(user="Utilisateur (optionnel)")
    async def p(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await self.profile.callback(self, interaction, user)


async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(ProfileCog(bot, db))
