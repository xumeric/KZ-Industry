# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands

from ..db import Database
from .. import config
from ..utils import embed_info


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _due_iso(term_days: int) -> str:
    return (dt.datetime.utcnow().replace(microsecond=0) + dt.timedelta(days=int(term_days))).isoformat() + "Z"


async def _safe_reply(interaction: discord.Interaction, content: str | None = None, *, embed=None, ephemeral: bool = True):
    """Reply safely whether the interaction was deferred or not."""
    try:
        if interaction.response.is_done():
            return await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
        return await interaction.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
    except Exception:
        try:
            return await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
        except Exception:
            return None


def _get_fixed_interest(db: Database) -> float:
    raw = db.get_setting("loans_fixed_interest_pct", str(config.LOANS_FIXED_INTEREST_PCT))
    try:
        return float(raw) if raw is not None else float(config.LOANS_FIXED_INTEREST_PCT)
    except Exception:
        return float(config.LOANS_FIXED_INTEREST_PCT)


def _calc_total_due(principal: int, interest_pct: float) -> int:
    return int(round(principal * (1.0 + (float(interest_pct) / 100.0))))


def _get_next_slot(db: Database, borrower_id: int) -> int | None:
    """Trouve le prochain slot disponible (1, 2 ou 3) pour un emprunteur."""
    used_slots = db.fetchall(
        "SELECT slot FROM loans WHERE borrower_id=? AND status IN ('PENDING','ACTIVE') AND slot IS NOT NULL",
        (borrower_id,)
    )
    used = {int(r["slot"]) for r in used_slots}
    for s in range(1, config.LOANS_MAX_ACTIVE_PER_USER + 1):
        if s not in used:
            return s
    return None


def _get_loan_by_slot(db: Database, borrower_id: int, slot: int):
    """Récupère un prêt actif par son slot."""
    return db.fetchone(
        "SELECT * FROM loans WHERE borrower_id=? AND slot=? AND status IN ('PENDING','ACTIVE')",
        (borrower_id, slot)
    )


def _release_slot(db: Database, loan_id: int):
    """Libère le slot d'un prêt (le met à NULL)."""
    db.execute("UPDATE loans SET slot=NULL WHERE loan_id=?", (loan_id,))


@dataclass
class DecisionPayload:
    loan_id: int
    kind: str  # BANK or P2P


class LoanDecisionView(discord.ui.View):
    """Buttons to accept/refuse a loan request."""
    def __init__(self, bot: commands.Bot, payload: DecisionPayload, approver_id: int, slot: int):
        super().__init__(timeout=60 * 60 * 24)  # 24h
        self.bot = bot
        self.payload = payload
        self.approver_id = int(approver_id)
        self.slot = slot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.approver_id:
            await _safe_reply(interaction, "❌ Tu n'es pas autorisé à décider ce prêt.", ephemeral=True)
            return False
        return True

    async def _decide(self, interaction: discord.Interaction, accept: bool):
        db: Database = self.bot.db  # type: ignore
        loan = db.fetchone("SELECT * FROM loans WHERE loan_id=?", (self.payload.loan_id,))
        if loan is None:
            await _safe_reply(interaction, "❌ Prêt introuvable.", ephemeral=True)
            self.stop()
            return

        if loan["status"] != "PENDING":
            await _safe_reply(interaction, f"ℹ️ Ce prêt est déjà traité (status: {loan['status']}).", ephemeral=True)
            self.stop()
            return

        borrower_id = int(loan["borrower_id"])
        lender_id = loan["lender_id"]
        principal = int(loan["principal"])
        interest_pct = float(loan["interest_pct"])
        term_days = int(loan["term_days"])

        if not accept:
            db.execute(
                "UPDATE loans SET status='REJECTED', approved_at=?, decided_by=?, slot=NULL WHERE loan_id=?",
                (_now_iso(), interaction.user.id, self.payload.loan_id),
            )
            await _safe_reply(interaction, "❌ Prêt refusé.", ephemeral=True)
            try:
                borrower = self.bot.get_user(borrower_id) or await self.bot.fetch_user(borrower_id)
                await borrower.send(f"❌ Ta demande de prêt #{self.slot} a été refusée.")
            except Exception:
                pass
            self.stop()
            return

        # ACCEPT
        if loan["kind"] == "P2P":
            if lender_id is None:
                await _safe_reply(interaction, "❌ Erreur: prêteur manquant (P2P).", ephemeral=True)
                self.stop()
                return
            lender_id = int(lender_id)
            lender_row = db.fetchone("SELECT balance FROM users WHERE user_id=?", (lender_id,))
            lender_balance = int(lender_row["balance"]) if lender_row else 0
            if lender_balance < principal:
                db.execute(
                    "UPDATE loans SET status='CANCELLED', approved_at=?, decided_by=?, slot=NULL WHERE loan_id=?",
                    (_now_iso(), interaction.user.id, self.payload.loan_id),
                )
                await _safe_reply(interaction, "❌ Acceptation impossible: le prêteur n'a plus assez de KZ.", ephemeral=True)
                try:
                    lender = self.bot.get_user(lender_id) or await self.bot.fetch_user(lender_id)
                    await lender.send(f"❌ Le prêt P2P #{self.slot} a été annulé (fonds insuffisants).")
                except Exception:
                    pass
                self.stop()
                return
            db.ensure_user(lender_id, config.START_BALANCE)
            db.ensure_user(borrower_id, config.START_BALANCE)
            db.remove_balance(lender_id, principal)
            db.add_balance(borrower_id, principal)
        else:
            db.ensure_user(borrower_id, config.START_BALANCE)
            db.add_balance(borrower_id, principal)

        total_due = _calc_total_due(principal, interest_pct)
        db.execute(
            """
            UPDATE loans
            SET status='ACTIVE',
                total_due=?,
                remaining_due=?,
                approved_at=?,
                due_at=?,
                decided_by=?
            WHERE loan_id=?
            """,
            (total_due, total_due, _now_iso(), _due_iso(term_days), interaction.user.id, self.payload.loan_id),
        )

        await _safe_reply(interaction, f"✅ Prêt #{self.slot} accepté.", ephemeral=True)

        try:
            borrower = self.bot.get_user(borrower_id) or await self.bot.fetch_user(borrower_id)
            await borrower.send(
                f"✅ Ton prêt #{self.slot} est accepté : +{principal} KZ. "
                f"À rembourser : {total_due} KZ (intérêt {interest_pct}%)."
            )
        except Exception:
            pass

        if loan["kind"] == "P2P":
            try:
                lender = self.bot.get_user(int(lender_id)) or await self.bot.fetch_user(int(lender_id))
                await lender.send(f"✅ Ton prêt P2P #{self.slot} a été accepté. -{principal} KZ.")
            except Exception:
                pass

        self.stop()

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._decide(interaction, True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger)
    async def refuse_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._decide(interaction, False)


class LoansCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: Database = bot.db  # type: ignore

    pret = app_commands.Group(name="pret", description="Système de prêts (banque + entre joueurs)")

    # ---------------- BANK ----------------
    @pret.command(name="demander", description="Demander un prêt à la banque (validation owner).")
    @app_commands.describe(montant="Montant en KZ", duree_jours="Durée en jours", note="Optionnel")
    async def pret_demander(self, interaction: discord.Interaction, montant: int, duree_jours: int, note: str = "Aucune"):
        await interaction.response.defer(ephemeral=True)
        try:
            if not config.LOANS_ENABLED:
                return await _safe_reply(interaction, "❌ Les prêts sont désactivés.", ephemeral=True)

            owner_id = int(config.OWNER_ID or 0)
            if owner_id <= 0:
                return await _safe_reply(interaction, "❌ OWNER_ID n'est pas configuré dans .env.", ephemeral=True)

            montant = int(montant)
            duree_jours = int(duree_jours or config.LOANS_DEFAULT_TERM_DAYS)

            if montant < config.LOANS_MIN_AMOUNT or montant > config.LOANS_MAX_AMOUNT:
                return await _safe_reply(
                    interaction,
                    f"❌ Montant invalide. Min {config.LOANS_MIN_AMOUNT} / Max {config.LOANS_MAX_AMOUNT}.",
                    ephemeral=True,
                )
            if duree_jours < 1 or duree_jours > config.LOANS_MAX_TERM_DAYS:
                return await _safe_reply(
                    interaction,
                    f"❌ Durée invalide. 1 à {config.LOANS_MAX_TERM_DAYS} jours.",
                    ephemeral=True,
                )

            # Trouver un slot disponible
            slot = _get_next_slot(self.db, interaction.user.id)
            if slot is None:
                return await _safe_reply(
                    interaction,
                    f"❌ Tu as déjà {config.LOANS_MAX_ACTIVE_PER_USER} prêts en cours (max atteint).",
                    ephemeral=True,
                )

            interest = _get_fixed_interest(self.db)
            loan_id = self.db.insert_returning_id(
                """
                INSERT INTO loans(kind, lender_id, borrower_id, principal, interest_pct, total_due, remaining_due, term_days, status, note, created_at, slot)
                VALUES('BANK', NULL, ?, ?, ?, 0, 0, ?, 'PENDING', ?, ?, ?)
                """,
                (interaction.user.id, montant, float(interest), duree_jours, note[:300], _now_iso(), slot),
            )

            # DM owner with decision buttons
            try:
                owner = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
                embed = embed_info(
                    "📩 Demande de prêt (BANQUE)",
                    f"**Slot:** #{slot}\n"
                    f"**Demandeur:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"**Montant:** {montant} KZ\n"
                    f"**Intérêt fixe:** {interest}%\n"
                    f"**Durée:** {duree_jours} jours\n"
                    f"**Note:** {note}",
                )
                view = LoanDecisionView(self.bot, DecisionPayload(loan_id=loan_id, kind="BANK"), approver_id=owner_id, slot=slot)
                await owner.send(embed=embed, view=view)
            except discord.Forbidden:
                return await _safe_reply(
                    interaction,
                    "❌ Impossible d'envoyer un MP au owner (MP fermés).",
                    ephemeral=True,
                )
            except Exception:
                return await _safe_reply(
                    interaction,
                    "⚠️ Demande créée mais impossible d'envoyer le MP au owner. Vérifie ses MP.",
                    ephemeral=True,
                )

            return await _safe_reply(interaction, f"✅ Demande envoyée au owner. Ton prêt: **#{slot}**", ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur prêt: `{type(e).__name__}`", ephemeral=True)

    @pret.command(name="interet", description="(Owner) Fixer l'intérêt global banque.")
    @app_commands.describe(pourcent="Ex: 10 = 10%")
    async def pret_interet(self, interaction: discord.Interaction, pourcent: float):
        await interaction.response.defer(ephemeral=True)
        try:
            if interaction.user.id != int(config.OWNER_ID or 0):
                return await _safe_reply(interaction, "❌ Réservé au owner.", ephemeral=True)
            pct = float(pourcent)
            if pct < 0 or pct > 100:
                return await _safe_reply(interaction, "❌ Valeur invalide (0 à 100).", ephemeral=True)
            self.db.set_setting("loans_fixed_interest_pct", str(pct))
            return await _safe_reply(interaction, f"✅ Intérêt banque fixé à {pct}%.", ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur: `{type(e).__name__}`", ephemeral=True)

    # ---------------- P2P ----------------
    @pret.command(name="proposer", description="Proposer un prêt à un joueur (MP + accept/refuse).")
    @app_commands.describe(joueur="Emprunteur", montant="Montant en KZ", taux="Intérêt %", duree_jours="Durée en jours", note="Optionnel")
    async def pret_proposer(self, interaction: discord.Interaction, joueur: discord.Member, montant: int, taux: float, duree_jours: int, note: str = "Aucune"):
        await interaction.response.defer(ephemeral=True)
        try:
            if not config.LOANS_P2P_ENABLED:
                return await _safe_reply(interaction, "❌ Les prêts entre joueurs sont désactivés.", ephemeral=True)

            if joueur.bot or joueur.id == interaction.user.id:
                return await _safe_reply(interaction, "❌ Joueur invalide.", ephemeral=True)

            montant = int(montant)
            duree_jours = int(duree_jours)
            taux = float(taux)

            if montant < config.LOANS_MIN_AMOUNT or montant > config.LOANS_MAX_AMOUNT:
                return await _safe_reply(interaction, f"❌ Montant invalide. Min {config.LOANS_MIN_AMOUNT} / Max {config.LOANS_MAX_AMOUNT}.", ephemeral=True)
            if duree_jours < 1 or duree_jours > int(config.LOANS_P2P_MAX_TERM_DAYS):
                return await _safe_reply(interaction, f"❌ Durée invalide. 1 à {config.LOANS_P2P_MAX_TERM_DAYS} jours.", ephemeral=True)
            if taux < 0 or taux > float(config.LOANS_P2P_MAX_INTEREST_PCT):
                return await _safe_reply(interaction, f"❌ Taux invalide. 0 à {config.LOANS_P2P_MAX_INTEREST_PCT}%.", ephemeral=True)

            self.db.ensure_user(interaction.user.id, config.START_BALANCE)
            lender_bal_row = self.db.fetchone("SELECT balance FROM users WHERE user_id=?", (interaction.user.id,))
            lender_bal = int(lender_bal_row["balance"]) if lender_bal_row else 0
            if lender_bal < montant:
                return await _safe_reply(interaction, "❌ Tu n'as pas assez de KZ pour proposer ce prêt.", ephemeral=True)

            # Trouver un slot disponible pour l'emprunteur
            slot = _get_next_slot(self.db, joueur.id)
            if slot is None:
                return await _safe_reply(interaction, f"❌ {joueur.mention} a déjà {config.LOANS_MAX_ACTIVE_PER_USER} prêts en cours.", ephemeral=True)

            loan_id = self.db.insert_returning_id(
                """
                INSERT INTO loans(kind, lender_id, borrower_id, principal, interest_pct, total_due, remaining_due, term_days, status, note, created_at, slot)
                VALUES('P2P', ?, ?, ?, ?, 0, 0, ?, 'PENDING', ?, ?, ?)
                """,
                (interaction.user.id, joueur.id, montant, float(taux), duree_jours, note[:300], _now_iso(), slot),
            )

            # DM borrower
            try:
                embed = embed_info(
                    "📩 Proposition de prêt (Joueur)",
                    f"**Slot:** #{slot}\n"
                    f"**Prêteur:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"**Montant:** {montant} KZ\n"
                    f"**Intérêt:** {taux}%\n"
                    f"**Durée:** {duree_jours} jours\n"
                    f"**Note:** {note}",
                )
                view = LoanDecisionView(self.bot, DecisionPayload(loan_id=loan_id, kind="P2P"), approver_id=joueur.id, slot=slot)
                await joueur.send(embed=embed, view=view)
            except discord.Forbidden:
                return await _safe_reply(interaction, "❌ Impossible d'envoyer un MP à l'emprunteur (MP fermés).", ephemeral=True)
            except Exception as e:
                return await _safe_reply(interaction, f"❌ Erreur MP: `{type(e).__name__}`", ephemeral=True)

            return await _safe_reply(interaction, f"✅ Proposition envoyée à {joueur.mention}. Slot: **#{slot}**", ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur prêt P2P: `{type(e).__name__}`", ephemeral=True)

    @pret.command(name="annuler", description="Annuler un prêt en attente (par son numéro 1-3).")
    @app_commands.describe(numero="Numéro du prêt (1, 2 ou 3)")
    async def pret_annuler(self, interaction: discord.Interaction, numero: int):
        await interaction.response.defer(ephemeral=True)
        try:
            if numero < 1 or numero > config.LOANS_MAX_ACTIVE_PER_USER:
                return await _safe_reply(interaction, f"❌ Numéro invalide (1 à {config.LOANS_MAX_ACTIVE_PER_USER}).", ephemeral=True)

            # Chercher le prêt par slot (emprunteur ou prêteur P2P)
            loan = self.db.fetchone(
                """SELECT * FROM loans 
                   WHERE slot=? AND status='PENDING' 
                   AND (borrower_id=? OR (kind='P2P' AND lender_id=?))""",
                (numero, interaction.user.id, interaction.user.id)
            )
            
            if loan is None:
                return await _safe_reply(interaction, f"❌ Aucun prêt en attente trouvé avec le numéro #{numero}.", ephemeral=True)

            user_id = interaction.user.id
            borrower_id = int(loan["borrower_id"])
            lender_id = int(loan["lender_id"]) if loan["lender_id"] else None
            kind = loan["kind"]
            loan_id = int(loan["loan_id"])

            # Qui peut annuler ?
            can_cancel = False
            cancel_reason = ""

            if user_id == borrower_id:
                can_cancel = True
                cancel_reason = "annulée par l'emprunteur"
            elif kind == "P2P" and lender_id is not None and user_id == lender_id:
                can_cancel = True
                cancel_reason = "annulée par le prêteur"

            if not can_cancel:
                return await _safe_reply(interaction, "❌ Tu n'es pas autorisé à annuler ce prêt.", ephemeral=True)

            self.db.execute("UPDATE loans SET status='CANCELLED', approved_at=?, slot=NULL WHERE loan_id=?", (_now_iso(), loan_id))

            # Notifier l'autre partie
            try:
                if user_id == borrower_id and kind == "P2P" and lender_id is not None:
                    lender = self.bot.get_user(lender_id) or await self.bot.fetch_user(lender_id)
                    await lender.send(f"ℹ️ La demande de prêt #{numero} a été annulée par l'emprunteur.")
                elif user_id == lender_id:
                    borrower = self.bot.get_user(borrower_id) or await self.bot.fetch_user(borrower_id)
                    await borrower.send(f"ℹ️ Le prêt #{numero} a été annulé par le prêteur.")
            except Exception:
                pass

            return await _safe_reply(interaction, f"✅ Prêt #{numero} annulé ({cancel_reason}).", ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur: `{type(e).__name__}`", ephemeral=True)

    # ---------------- REPAY ----------------
    @pret.command(name="rembourser", description="Rembourser un prêt (par son numéro 1-3).")
    @app_commands.describe(numero="Numéro du prêt (1, 2 ou 3)", montant="Montant (vide = tout rembourser)")
    async def pret_rembourser(self, interaction: discord.Interaction, numero: int, montant: int | None = None):
        await interaction.response.defer(ephemeral=True)
        try:
            if numero < 1 or numero > config.LOANS_MAX_ACTIVE_PER_USER:
                return await _safe_reply(interaction, f"❌ Numéro invalide (1 à {config.LOANS_MAX_ACTIVE_PER_USER}).", ephemeral=True)

            loan = _get_loan_by_slot(self.db, interaction.user.id, numero)
            if loan is None:
                return await _safe_reply(interaction, f"❌ Aucun prêt actif trouvé avec le numéro #{numero}.", ephemeral=True)
            if loan["status"] != "ACTIVE":
                return await _safe_reply(interaction, f"❌ Ce prêt n'est pas encore actif (status: {loan['status']}). Attends qu'il soit validé.", ephemeral=True)

            remaining = int(loan["remaining_due"])
            pay = remaining if montant is None else max(1, int(montant))
            pay = min(pay, remaining)

            self.db.ensure_user(interaction.user.id, config.START_BALANCE)
            bal_row = self.db.fetchone("SELECT balance FROM users WHERE user_id=?", (interaction.user.id,))
            bal = int(bal_row["balance"]) if bal_row else 0
            if bal < pay:
                return await _safe_reply(interaction, "❌ Solde insuffisant pour ce remboursement.", ephemeral=True)

            loan_id = int(loan["loan_id"])
            
            # money moves
            self.db.remove_balance(interaction.user.id, pay)
            if loan["kind"] == "P2P" and loan["lender_id"] is not None:
                self.db.ensure_user(int(loan["lender_id"]), config.START_BALANCE)
                self.db.add_balance(int(loan["lender_id"]), pay)

            new_remaining = remaining - pay
            if new_remaining <= 0:
                self.db.execute("UPDATE loans SET remaining_due=0, status='REPAID', slot=NULL WHERE loan_id=?", (loan_id,))
                await _safe_reply(interaction, f"✅ Prêt #{numero} remboursé en totalité ! 🎉", ephemeral=True)
            else:
                self.db.execute("UPDATE loans SET remaining_due=? WHERE loan_id=?", (new_remaining, loan_id))
                await _safe_reply(interaction, f"✅ Remboursé {pay} KZ. Reste {new_remaining} KZ sur le prêt #{numero}.", ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur: `{type(e).__name__}`", ephemeral=True)

    # ---------------- LIST COMMANDS ----------------
    @pret.command(name="mes", description="Voir tes prêts en cours (en attente + actifs).")
    async def pret_mes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            rows = self.db.fetchall(
                """
                SELECT slot, kind, lender_id, borrower_id, principal, interest_pct, remaining_due, total_due, status, due_at
                FROM loans
                WHERE (borrower_id=? OR lender_id=?) AND status IN ('PENDING','ACTIVE') AND slot IS NOT NULL
                ORDER BY slot ASC
                """,
                (interaction.user.id, interaction.user.id),
            )
            if not rows:
                return await _safe_reply(interaction, "ℹ️ Tu n'as aucun prêt en cours.", ephemeral=True)

            lines = []
            for r in rows:
                slot = int(r["slot"])
                kind = r["kind"]
                status = "⏳ En attente" if r["status"] == "PENDING" else "✅ Actif"
                rem = int(r["remaining_due"])
                total = int(r["total_due"])
                principal = int(r["principal"])
                pct = float(r["interest_pct"])
                due = r["due_at"][:10] if r["due_at"] else "—"
                role = "Emprunteur" if int(r["borrower_id"]) == interaction.user.id else "Prêteur"
                
                if r["status"] == "ACTIVE":
                    lines.append(f"**#{slot}** [{kind}] ({role}) — {status}\n└ Reste **{rem}** / {total} KZ — Échéance: {due}")
                else:
                    lines.append(f"**#{slot}** [{kind}] ({role}) — {status}\n└ Montant: **{principal}** KZ — Intérêt: {pct}%")

            embed = embed_info("💳 Tes prêts en cours", "\n\n".join(lines))
            embed.set_footer(text=f"Utilise /pret rembourser <numéro> pour rembourser")
            return await _safe_reply(interaction, embed=embed, ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur: `{type(e).__name__}`", ephemeral=True)

    @pret.command(name="attente", description="Voir tes prêts en attente de validation.")
    async def pret_attente(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            rows = self.db.fetchall(
                """
                SELECT slot, kind, lender_id, borrower_id, principal, interest_pct, note, created_at
                FROM loans
                WHERE (borrower_id=? OR lender_id=?) AND status='PENDING' AND slot IS NOT NULL
                ORDER BY slot ASC
                """,
                (interaction.user.id, interaction.user.id),
            )
            if not rows:
                return await _safe_reply(interaction, "ℹ️ Tu n'as aucun prêt en attente.", ephemeral=True)

            lines = []
            for r in rows:
                slot = int(r["slot"])
                kind = r["kind"]
                principal = int(r["principal"])
                pct = float(r["interest_pct"])
                role = "Emprunteur" if int(r["borrower_id"]) == interaction.user.id else "Prêteur"
                created = r["created_at"][:10] if r["created_at"] else "—"
                lines.append(f"**#{slot}** [{kind}] ({role})\n└ Montant: **{principal}** KZ — Intérêt: {pct}% — Créé: {created}")

            embed = embed_info("⏳ Prêts en attente", "\n\n".join(lines))
            embed.set_footer(text="Utilise /pret annuler <numéro> pour annuler")
            return await _safe_reply(interaction, embed=embed, ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur: `{type(e).__name__}`", ephemeral=True)

    @pret.command(name="actifs", description="Voir tes prêts actifs (en cours de remboursement).")
    async def pret_actifs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            rows = self.db.fetchall(
                """
                SELECT slot, kind, lender_id, borrower_id, principal, interest_pct, remaining_due, total_due, due_at
                FROM loans
                WHERE (borrower_id=? OR lender_id=?) AND status='ACTIVE' AND slot IS NOT NULL
                ORDER BY slot ASC
                """,
                (interaction.user.id, interaction.user.id),
            )
            if not rows:
                return await _safe_reply(interaction, "ℹ️ Tu n'as aucun prêt actif.", ephemeral=True)

            lines = []
            for r in rows:
                slot = int(r["slot"])
                kind = r["kind"]
                rem = int(r["remaining_due"])
                total = int(r["total_due"])
                principal = int(r["principal"])
                pct = float(r["interest_pct"])
                due = r["due_at"][:10] if r["due_at"] else "—"
                role = "Emprunteur" if int(r["borrower_id"]) == interaction.user.id else "Prêteur"
                progress = int((1 - rem/total) * 100) if total > 0 else 0
                lines.append(f"**#{slot}** [{kind}] ({role})\n└ Reste **{rem}** / {total} KZ ({progress}% remboursé) — Échéance: {due}")

            embed = embed_info("✅ Prêts actifs", "\n\n".join(lines))
            embed.set_footer(text="Utilise /pret rembourser <numéro> pour rembourser")
            return await _safe_reply(interaction, embed=embed, ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur: `{type(e).__name__}`", ephemeral=True)

    @pret.command(name="historique", description="Voir l'historique de tous tes prêts terminés.")
    async def pret_historique(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            rows = self.db.fetchall(
                """
                SELECT loan_id, kind, lender_id, borrower_id, principal, interest_pct, total_due, status, created_at, approved_at
                FROM loans
                WHERE (borrower_id=? OR lender_id=?) AND status IN ('REPAID','REJECTED','CANCELLED')
                ORDER BY loan_id DESC
                LIMIT 15
                """,
                (interaction.user.id, interaction.user.id),
            )
            if not rows:
                return await _safe_reply(interaction, "ℹ️ Aucun prêt dans l'historique.", ephemeral=True)

            lines = []
            status_emoji = {"REPAID": "✅", "REJECTED": "❌", "CANCELLED": "🚫"}
            status_text = {"REPAID": "Remboursé", "REJECTED": "Refusé", "CANCELLED": "Annulé"}
            
            for r in rows:
                kind = r["kind"]
                status = r["status"]
                emoji = status_emoji.get(status, "❓")
                text = status_text.get(status, status)
                principal = int(r["principal"])
                total = int(r["total_due"]) if r["total_due"] else principal
                role = "Emprunteur" if int(r["borrower_id"]) == interaction.user.id else "Prêteur"
                date = r["approved_at"][:10] if r["approved_at"] else r["created_at"][:10] if r["created_at"] else "—"
                lines.append(f"{emoji} [{kind}] ({role}) — **{text}**\n└ {principal} KZ → {total} KZ — {date}")

            embed = embed_info("📜 Historique des prêts", "\n\n".join(lines))
            embed.set_footer(text="15 derniers prêts terminés")
            return await _safe_reply(interaction, embed=embed, ephemeral=True)
        except Exception as e:
            return await _safe_reply(interaction, f"❌ Erreur: `{type(e).__name__}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LoansCog(bot))
