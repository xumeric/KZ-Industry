# -*- coding: utf-8 -*-
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import Database
from ..utils import embed_info, embed_lose, embed_neutral, embed_win, fmt
from ..checks import enforce_blacklist


PRED_CHOICES = [
    app_commands.Choice(name="Victoire", value="win"),
    app_commands.Choice(name="Défaite", value="lose"),
]


class PredictionCog(commands.Cog):
    """Parier sur la prochaine victoire/défaite d'un autre joueur."""

    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    async def cog_app_command_invoke(self, interaction: discord.Interaction):
        allowed = await enforce_blacklist(self.db, interaction)
        if not allowed:
            raise app_commands.CheckFailure("Blacklisted")

    @app_commands.command(
        name="prediction",
        description="Parie sur la prochaine victoire/défaite d'un autre joueur",
    )
    @app_commands.describe(
        target="Le joueur que tu veux prédire",
        choice="Ce que tu penses qu'il va faire sur sa prochaine partie",
        bet="Ta mise (KZ)",
    )
    @app_commands.choices(choice=PRED_CHOICES)
    async def prediction(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        choice: app_commands.Choice[str],
        bet: app_commands.Range[int, 1, 1_000_000_000],
    ):
        if target.bot:
            return await interaction.response.send_message(
                embed=embed_lose("❌ Prediction", "Tu ne peux pas prédire un bot."),
                ephemeral=True,
            )
        if target.id == interaction.user.id:
            return await interaction.response.send_message(
                embed=embed_lose("❌ Prediction", "Tu ne peux pas te prédire toi-même."),
                ephemeral=True,
            )

        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        self.db.ensure_user(target.id, config.START_BALANCE)

        me = self.db.get_user(interaction.user.id)
        bal = int(me["balance"]) if me else 0
        bet = int(bet)
        if bet > bal:
            return await interaction.response.send_message(
                embed=embed_lose("❌ Prediction", f"Solde insuffisant. Tu as {fmt(bal)} KZ."),
                ephemeral=True,
            )

        # Si une prédiction existe déjà sur ce target, on la rembourse avant d'écraser.
        old = self.db.delete_prediction(interaction.user.id, target.id)
        if old:
            self.db.add_balance(interaction.user.id, int(old["bet"]))

        # Escrow: on retire la mise maintenant.
        self.db.add_balance(interaction.user.id, -bet)
        self.db.upsert_prediction(interaction.user.id, target.id, bet, choice.value)

        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e = embed_win(
            "🔮 Prediction enregistrée",
            (
                f"Tu as misé **{fmt(bet)} KZ** sur **{target.display_name}** : **{choice.name}**\n\n"
                "Résolution automatique quand le joueur termine sa prochaine partie (win/lose)."
            ),
        )
        e.add_field(name="🏦 Ton solde", value=f"{fmt(new_bal)} KZ", inline=True)
        e.set_footer(text="Si tu te trompes, ta mise va au joueur. Si tu as raison, tu récupères ta mise + tu prends la mise au joueur (si possible).")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="prediction_cancel", description="Annuler une prediction (rembourse ta mise)")
    @app_commands.describe(target="Le joueur ciblé")
    async def prediction_cancel(self, interaction: discord.Interaction, target: discord.Member):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        row = self.db.delete_prediction(interaction.user.id, target.id)
        if not row:
            return await interaction.response.send_message(
                embed=embed_neutral("🔮 Prediction", "Aucune prediction en cours sur ce joueur."),
                ephemeral=True,
            )
        bet = int(row["bet"])
        self.db.add_balance(interaction.user.id, bet)
        new_bal = int(self.db.get_user(interaction.user.id)["balance"])
        e = embed_win("✅ Prediction annulée", f"Mise remboursée : **{fmt(bet)} KZ**")
        e.add_field(name="🏦 Ton solde", value=f"{fmt(new_bal)} KZ", inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="predictions", description="Voir tes predictions (en cours + historique)")
    async def predictions(self, interaction: discord.Interaction):
        self.db.ensure_user(interaction.user.id, config.START_BALANCE)
        pending = self.db.list_predictions_for_user(interaction.user.id)
        logs = self.db.list_prediction_logs_for_user(interaction.user.id, limit=8)

        e = embed_info("🔮 Predictions", "")

        if pending:
            lines = []
            for p in pending[:10]:
                predictor_id = int(p["predictor_id"])
                target_id = int(p["target_id"])
                bet = int(p["bet"])
                choice = str(p["choice"])
                who = "toi" if predictor_id == interaction.user.id else f"<@{predictor_id}>"
                other = "toi" if target_id == interaction.user.id else f"<@{target_id}>"
                lines.append(f"• {who} → {other} : **{choice}** | mise **{fmt(bet)}**")
            e.add_field(name="⏳ En cours", value="\n".join(lines), inline=False)
        else:
            e.add_field(name="⏳ En cours", value="Aucune prediction en cours.", inline=False)

        if logs:
            lines = []
            for r in logs:
                predictor_id = int(r["predictor_id"])
                target_id = int(r["target_id"])
                bet = int(r["bet"])
                choice = str(r["choice"])
                result = str(r["result"])
                paid = int(r["paid_from_target"])
                outcome = "✅" if choice == result and predictor_id == interaction.user.id else ("❌" if predictor_id == interaction.user.id else "ℹ️")
                lines.append(
                    f"• {outcome} <@{predictor_id}> sur <@{target_id}> : {choice} → **{result}** | mise {fmt(bet)} | pris au target {fmt(paid)}"
                )
            e.add_field(name="📜 Historique (8 derniers)", value="\n".join(lines), inline=False)
        else:
            e.add_field(name="📜 Historique", value="Aucun historique pour l'instant.", inline=False)

        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    await bot.add_cog(PredictionCog(bot, db))
