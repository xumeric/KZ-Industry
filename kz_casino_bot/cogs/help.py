# -*- coding: utf-8 -*-
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..utils import embed_info


# ============================================
# Données des commandes par catégorie
# ============================================

HELP_CATEGORIES = {
    "🏠 Accueil": {
        "emoji": "🏠",
        "description": "Vue d'ensemble du bot",
        "commands": None,  # Spécial : page d'accueil
    },
    "💰 Économie": {
        "emoji": "💰",
        "description": "Commandes pour gérer tes coins",
        "commands": [
            ("/register", "Créer ton compte casino"),
            ("/balance (ou /bal)", "Voir ton solde actuel"),
            ("/daily", "Récupérer ton bonus quotidien"),
            ("/weekly", "Récupérer ton bonus hebdomadaire"),
            ("/work", "Travailler pour gagner des coins"),
            ("/transfer (ou /pay) <user> <montant>", "Envoyer des coins (avec taxe)"),
            ("/leaderboard (ou /lb, /top)", "Voir le classement des joueurs"),
            ("/cooldowns (ou /cd)", "Voir tous tes temps d'attente"),
        ],
    },
    "👤 Profil": {
        "emoji": "👤",
        "description": "Personnaliser ton profil",
        "commands": [
            ("/profile (ou /p) [user]", "Voir ton profil ou celui d'un autre"),
            ("/profileset banner <url>", "Définir ta bannière (image/GIF)"),
            ("/profileset bio <texte>", "Définir ta bio (max 200 car.)"),
            ("/profileset color <couleur>", "Changer la couleur (nom ou #hex)"),
            ("/cosmetic framelist", "Voir les cadres que tu possèdes"),
            ("/cosmetic frameequip <cadre>", "Équiper un cadre de profil"),
            ("/cosmetic frameremove", "Retirer ton cadre de profil"),
            ("/profileset removebanner", "Retirer ta bannière"),
            ("/profileset reset", "Réinitialiser ton profil"),
        ],
    },
    "🎰 Jeux": {
        "emoji": "🎰",
        "description": "Jeux de casino (mise: nombre ou 'all'/'max'/'tout')",
        "commands": [
            ("/slots (ou /sl) <mise>", "Machine à sous (x2, x5, x10)"),
            ("/coinflip (ou /cf) <mise> <pile/face>", "Pile ou face (x2)"),
            ("/roulette (ou /rl) <mise> <choix>", "Roulette (rouge/noir/vert/numéro...)"),
            ("/blackjack (ou /bj) <mise>", "🎮 Blackjack interactif"),
            ("/crash (ou /cr) <mise>", "🎮 Crash interactif"),
            ("/guess <mise> <nombre>", "Devine un nombre 1-100"),
            ("/chest", "Ouvrir un coffre (cooldown)"),
            ("/prediction <cible> <victoire/défaite> <mise>", "Parier sur le prochain résultat d'un joueur"),
            ("/predictions", "Voir tes predictions + historique"),
            ("/prediction_cancel <cible>", "Annuler une prediction (rembourse)"),
        ],
    },
    "⚔️ PvP": {
        "emoji": "⚔️",
        "description": "Duels & actions contre d'autres joueurs",
        "commands": [
            ("/rps1v1 <adversaire> <mise>", "✋ Pierre/Feuille/Ciseaux en 1v1"),
            ("/pvp <adversaire> <mise>", "⚔️ Duel rapide Attaque/Défense/All-in"),
            ("/blackjack1v1 <adversaire> <mise>", "🎴 Blackjack en 1v1 (simultané)"),
            ("/pvp_stats", "📊 Tes stats PvP"),
            ("/botstats", "🤖 Tes stats contre le bot"),
            ("/steal <cible>", "Tenter de voler un joueur (25% réussite)"),
            ("/sabotage <cible>", "Saboter un joueur (bloque + vole)"),
        ],
    },
    "🎁 Cadeaux": {
        "emoji": "🎁",
        "description": "Offrir des coins ou items",
        "commands": [
            ("/gift coins <user> <montant>", "Offrir des coins à un joueur"),
            ("/gift item <user> <item_id>", "Offrir un item de ton inventaire"),
        ],
    },
    "🛒 Boutique & Items": {
        "emoji": "🛒",
        "description": "Acheter, voir et utiliser des items",
        "commands": [
            ("/shop [catégorie]", "🛒 Ouvrir la boutique interactive"),
            ("/buy <item> [quantité]", "🛒 Acheter un item directement"),
            ("/inventory", "🎒 Voir ton inventaire"),
            ("/inv", "🎒 Alias de /inventory"),
            ("/use <item>", "✨ Utiliser un item (bouclier, boost, VIP...)"),
            ("/boosts", "✨ Voir tes boosts actifs"),
        ],
    },
    "🏦 Prêts": {
        "emoji": "🏦",
        "description": "Prêts banque et entre joueurs",
        "commands": [
            ("/pret demander <montant> [duree_jours] [note]", "Demander un prêt (banque du bot)"),
            ("/pret proposer <joueur> <montant> <taux> <duree_jours>", "Proposer un prêt P2P"),
            ("/pret annuler <loan_id>", "Annuler une proposition P2P"),
            ("/pret rembourser <loan_id> [montant]", "Rembourser un prêt"),
            ("/pret mes", "Voir tes prêts (banque + P2P)"),
            ("/pret interet <pourcent>", "(Owner) Fixer l'intérêt banque"),
        ],
    },
    "🛡️ Admin": {
        "emoji": "🛡️",
        "description": "Commandes administrateur",
        "commands": [
            ("/give <user> <montant>", "🎁 Donner des KZ"),
            ("/take <user> [montant]", "💸 Retirer des KZ (0 = tout)"),
            ("/setbal <user> <montant>", "💰 Définir le solde exact"),
            ("/giveitem <user> <item> [qty]", "📦 Donner un item"),
            ("/takeitem <user> <item> [qty]", "📦 Retirer un item (0 = tout)"),
            ("/givevip <user> [jours]", "👑 Donner du VIP (défaut: 7j)"),
            ("/giveimmunity <user> [heures]", "🛡️ Donner immunité (défaut: 24h)"),
            ("/clearuser <user>", "🧹 Reset complet du joueur"),
            ("/clearcoins <user>", "💸 Mettre le solde à 0"),
            ("/clearinv <user>", "📦 Vider l'inventaire"),
            ("/addadmin <user>", "➕ Ajouter un admin"),
            ("/listadmin", "📋 Voir la liste des admins"),
            ("/bl add <user> [raison]", "⛔ Blacklist permanent"),
            ("/bl temp <user> <minutes>", "⏱️ Blacklist temporaire"),
            ("/bl remove <user>", "✅ Retirer de la blacklist"),
            ("/bl list", "📋 Voir la blacklist"),
            ("/channels allow <salon>", "✅ Autoriser un salon"),
            ("/channels remove <salon>", "🗑️ Retirer un salon"),
            ("/channels list", "📃 Voir les salons autorisés"),
            ("/channels clear", "🧹 Vider la whitelist salons"),
            ("/category allow <salon>", "✅ Autoriser une catégorie"),
            ("/category remove <salon>", "🗑️ Retirer une catégorie"),
            ("/category list", "📃 Voir les catégories autorisées"),
            ("/category clear", "🧹 Vider la whitelist catégories"),
            ("/permit add <user>", "✅ Autoriser un user partout"),
            ("/permit remove <user>", "🗑️ Retirer l'autorisation"),
            ("/permit list", "📃 Voir les users autorisés"),
        ],
    },
    "👑 Owner": {
        "emoji": "👑",
        "description": "Commandes réservées au propriétaire",
        "commands": [
            ("/deladmin <user>", "➖ Retirer un admin"),
            ("/wipeall", "🔥 Reset TOUS les joueurs"),
            ("/odds list", "📊 Voir les paramètres"),
            ("/odds help", "ℹ️ Aide et exemples"),
            ("/odds set <param> <valeur>", "✏️ Modifier un paramètre"),
            ("/odds reset <param|all>", "♻️ Remet un paramètre (ou tout)"),
        ],
    },
}


# ============================================
# Menu déroulant
# ============================================

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=name.split(" ", 1)[1] if " " in name else name,
                value=name,
                emoji=data["emoji"],
                description=data["description"][:50],
            )
            for name, data in HELP_CATEGORIES.items()
        ]
        super().__init__(
            placeholder="📚 Choisis une catégorie...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        embed = build_help_embed(category)
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.add_item(HelpSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Ce menu ne t'appartient pas. Fais `/help` pour en avoir un.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ============================================
# Construction des embeds
# ============================================

def build_help_embed(category: str) -> discord.Embed:
    data = HELP_CATEGORIES.get(category)
    if not data:
        return embed_info("❌ Erreur", "Catégorie introuvable.")

    # Page d'accueil
    if data["commands"] is None:
        e = discord.Embed(
            title=f"🎰 {config.BRAND['name']} — Aide",
            description=(
                f"Bienvenue sur **{config.BRAND['name']}** !\n\n"
                "Un bot casino complet avec jeux, économie, boutique et plus encore.\n"
                "🎁 **Récompenses d'activité** : tu gagnes aussi des KZ en envoyant des messages et en restant en vocal.\n\n"
                "**📚 Utilise le menu ci-dessous** pour explorer les commandes par catégorie."
            ),
            color=config.BRAND["info"],
        )
        
        # Résumé des catégories
        categories_list = []
        for name, cat_data in HELP_CATEGORIES.items():
            if cat_data["commands"] is not None:
                count = len(cat_data["commands"])
                categories_list.append(f"{cat_data['emoji']} **{name.split(' ', 1)[1]}** — {count} commandes")
        
        e.add_field(
            name="📂 Catégories disponibles",
            value="\n".join(categories_list),
            inline=False,
        )
        
        e.add_field(
            name="💡 Astuce",
            value="Commence par `/register` pour créer ton compte !",
            inline=False,
        )
        
        e.set_footer(text=f"{config.BRAND['name']} • Sélectionne une catégorie ⬇️")
        return e

    # Page de catégorie
    e = discord.Embed(
        title=f"{data['emoji']} {category.split(' ', 1)[1]}",
        description=data["description"],
        color=config.BRAND["info"],
    )

    # Diviser les commandes en plusieurs champs si nécessaire (limite 1024 car par champ)
    commands_list = data["commands"]
    current_field = []
    current_length = 0
    field_num = 1
    
    for cmd, desc in commands_list:
        line = f"`{cmd}`\n↳ {desc}\n"
        line_length = len(line)
        
        # Si ajouter cette ligne dépasse 950 caractères, créer un nouveau champ
        if current_length + line_length > 950 and current_field:
            field_name = "📋 Commandes" if field_num == 1 else f"📋 Commandes (suite {field_num})"
            e.add_field(
                name=field_name,
                value="\n".join(current_field),
                inline=False,
            )
            current_field = []
            current_length = 0
            field_num += 1
        
        current_field.append(f"`{cmd}`\n↳ {desc}")
        current_length += line_length
    
    # Ajouter le dernier champ
    if current_field:
        field_name = "📋 Commandes" if field_num == 1 else f"📋 Commandes (suite {field_num})"
        e.add_field(
            name=field_name,
            value="\n".join(current_field),
            inline=False,
        )

    e.set_footer(text=f"{config.BRAND['name']} • {len(data['commands'])} commande(s)")
    return e


# ============================================
# Cog
# ============================================

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="📚 Afficher l'aide du bot")
    async def help_command(self, interaction: discord.Interaction):
        embed = build_help_embed("🏠 Accueil")
        view = HelpView(author_id=interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
