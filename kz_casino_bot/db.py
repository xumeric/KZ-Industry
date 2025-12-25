# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Database:
    path: str

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        # Reduce "database is locked" issues
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.execute("PRAGMA foreign_keys=ON;")
        con.execute("PRAGMA busy_timeout=5000;")
        return con

    def init(self) -> None:
        with self.connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    xp INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    games_played INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    last_daily TEXT,
                    last_weekly TEXT,
                    last_work TEXT,
                    last_chest TEXT,
                    last_steal TEXT,
                    last_sabotage TEXT,
                    sabotaged_until TEXT,
                    vip_until TEXT,
                    immunity_until TEXT,
                    inventory_json TEXT NOT NULL DEFAULT '{}',
                    boosts_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )

            # Lightweight migration: add missing columns if the DB existed before.
            cols = {r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()}
            def add_col(name: str, ddl: str):
                if name not in cols:
                    con.execute(f"ALTER TABLE users ADD COLUMN {ddl}")
            add_col("created_at", "created_at TEXT NOT NULL DEFAULT ''")
            add_col("inventory_json", "inventory_json TEXT NOT NULL DEFAULT '{}' ")
            add_col("boosts_json", "boosts_json TEXT NOT NULL DEFAULT '{}' ")
            add_col("vip_until", "vip_until TEXT")
            add_col("immunity_until", "immunity_until TEXT")
            add_col("last_daily", "last_daily TEXT")
            add_col("last_weekly", "last_weekly TEXT")
            add_col("last_work", "last_work TEXT")
            add_col("last_chest", "last_chest TEXT")
            add_col("last_steal", "last_steal TEXT")
            add_col("last_sabotage", "last_sabotage TEXT")
            add_col("sabotaged_until", "sabotaged_until TEXT")
            add_col("xp", "xp INTEGER NOT NULL DEFAULT 0")
            add_col("level", "level INTEGER NOT NULL DEFAULT 1")
            add_col("games_played", "games_played INTEGER NOT NULL DEFAULT 0")
            add_col("wins", "wins INTEGER NOT NULL DEFAULT 0")
            add_col("losses", "losses INTEGER NOT NULL DEFAULT 0")
            add_col("profile_banner", "profile_banner TEXT")
            add_col("profile_bio", "profile_bio TEXT")
            add_col("profile_color", "profile_color TEXT")
            # Equipped cosmetics
            add_col("profile_frame", "profile_frame TEXT")

            # PvP stats
            add_col("pvp_games", "pvp_games INTEGER NOT NULL DEFAULT 0")
            add_col("pvp_wins", "pvp_wins INTEGER NOT NULL DEFAULT 0")
            add_col("pvp_losses", "pvp_losses INTEGER NOT NULL DEFAULT 0")
            add_col("pvp_profit", "pvp_profit INTEGER NOT NULL DEFAULT 0")

            # Bot duel stats
            add_col("bot_wins", "bot_wins INTEGER NOT NULL DEFAULT 0")
            add_col("bot_losses", "bot_losses INTEGER NOT NULL DEFAULT 0")

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS blacklist (
                    user_id INTEGER PRIMARY KEY,
                    reason TEXT,
                    by_id INTEGER,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                )
                """
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_admins (
                    user_id INTEGER PRIMARY KEY
                )
                """
            )

            
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS allowed_channels (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, channel_id)
                )
                """
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS allowed_categories (
                    guild_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, category_id)
                )
                """
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS bypass_users (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, user_id)
                )
                """
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS game_stats (
                    user_id INTEGER NOT NULL,
                    game TEXT NOT NULL,
                    games INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    profit INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, game)
                )
                """
            )

            # ===== Activity tracking table =====
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS activity (
                    user_id INTEGER PRIMARY KEY,
                    msg_count INTEGER NOT NULL DEFAULT 0,
                    voice_seconds INTEGER NOT NULL DEFAULT 0
                )
                '''
            )

            # ===== Predictions (pari sur la victoire/défaite d'un autre joueur) =====
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS predictions (
                    predictor_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    bet INTEGER NOT NULL,
                    choice TEXT NOT NULL, -- 'win' ou 'lose' (résultat attendu du target)
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (predictor_id, target_id)
                )
                '''
            )

            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS prediction_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    predictor_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    bet INTEGER NOT NULL,
                    choice TEXT NOT NULL,
                    result TEXT NOT NULL,          -- 'win' ou 'lose' (résultat réel du target)
                    paid_from_target INTEGER NOT NULL DEFAULT 0, -- montant effectivement prélevé au target
                    created_at TEXT NOT NULL,
                    resolved_at TEXT NOT NULL
                )
                '''
            )


            # ===== Loans / Prêts (banque du bot + prêts entre joueurs) =====
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL DEFAULT 'BANK', -- BANK | P2P
                    lender_id INTEGER,                 -- NULL pour BANK
                    borrower_id INTEGER NOT NULL,
                    principal INTEGER NOT NULL,
                    interest_pct REAL NOT NULL,
                    total_due INTEGER NOT NULL,
                    remaining_due INTEGER NOT NULL,
                    term_days INTEGER NOT NULL,
                    status TEXT NOT NULL, -- PENDING | ACTIVE | REJECTED | REPAID | CANCELLED
                    note TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    due_at TEXT,
                    decided_by INTEGER
                )
                """
            )

            # migrations légères
            cols = {r[1] for r in con.execute("PRAGMA table_info(loans)").fetchall()}
            def add_loan_col(name: str, ddl: str):
                if name not in cols:
                    con.execute(f"ALTER TABLE loans ADD COLUMN {ddl}")
            add_loan_col("kind", "kind TEXT NOT NULL DEFAULT 'BANK'")
            add_loan_col("lender_id", "lender_id INTEGER")
            add_loan_col("slot", "slot INTEGER")  # 1-3 pour prêts actifs, NULL pour historique

            # remplir la valeur kind si DB ancienne
            con.execute("UPDATE loans SET kind='BANK' WHERE kind IS NULL OR kind='' ")

            con.commit()

    # ---- low-level helpers ----
    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self.connect() as con:
            cur = con.execute(sql, tuple(params))
            return cur.fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as con:
            cur = con.execute(sql, tuple(params))
            return cur.fetchall()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self.connect() as con:
            con.execute(sql, tuple(params))
            con.commit()

    def insert_returning_id(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Execute an INSERT and return the last inserted row ID."""
        with self.connect() as con:
            cur = con.execute(sql, tuple(params))
            con.commit()
            return cur.lastrowid or 0

    # ---- user helpers ----
    def ensure_user(self, user_id: int, start_balance: int) -> None:
        with self.connect() as con:
            row = con.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
            if row is None:
                con.execute(
                    "INSERT INTO users (user_id, balance, created_at) VALUES (?, ?, ?)",
                    (user_id, start_balance, utcnow_iso()),
                )
            con.commit()

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        return self.fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))

    def set_balance(self, user_id: int, new_balance: int) -> None:
        # Empêcher les soldes négatifs
        new_balance = max(0, int(new_balance))
        self.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

    def add_balance(self, user_id: int, delta: int) -> int:
        """Ajoute ou retire des coins. Le solde ne peut jamais être négatif."""
        delta = int(delta)
        with self.connect() as con:
            # Récupérer le solde actuel
            row = con.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
            current = int(row["balance"]) if row else 0
            
            # Calculer le nouveau solde (jamais négatif)
            new_balance = max(0, current + delta)
            
            # Mettre à jour
            con.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
            con.commit()
            return new_balance

    # =====================
    # XP / Niveau
    # =====================
    def _add_xp_in_con(self, con, user_id: int, amount: int) -> tuple[int, int]:
        """Ajoute de l'XP via une connexion existante. Retourne (new_xp, new_level)."""
        amount = int(amount)

        # Lire XP avant (pour détecter les level up)
        prev_row = con.execute("SELECT xp, profile_color FROM users WHERE user_id=?", (int(user_id),)).fetchone()
        prev_xp = int(prev_row["xp"]) if prev_row else 0
        prev_profile_color = (prev_row["profile_color"] if prev_row else None)

        from . import config
        from .leveling import level_from_xp
        cap = int(getattr(config, 'XP_LEVEL_CAP', 100))
        old_level = level_from_xp(prev_xp, cap=cap)

        if amount <= 0:
            row = con.execute("SELECT xp FROM users WHERE user_id=?", (int(user_id),)).fetchone()
            xp = int(row["xp"]) if row else 0
            lvl = level_from_xp(xp, cap=cap)
            con.execute("UPDATE users SET level=? WHERE user_id=?", (int(lvl), int(user_id)))
            return xp, lvl

        con.execute("UPDATE users SET xp = MAX(0, xp + ?) WHERE user_id=?", (amount, int(user_id)))
        row = con.execute("SELECT xp FROM users WHERE user_id=?", (int(user_id),)).fetchone()
        xp = int(row["xp"]) if row else 0

        lvl = level_from_xp(xp, cap=cap)
        con.execute("UPDATE users SET level=? WHERE user_id=?", (int(lvl), int(user_id)))

        # Récompenses KZ au level up + bonus de grade + déblocage couleur
        try:
            if lvl > old_level:
                from .leveling import kz_per_level, grade_bonus_between_levels

                # KZ par niveau gagné
                kz_gain = 0
                for reached in range(old_level + 1, lvl + 1):
                    kz_gain += int(kz_per_level(reached))

                # Bonus à chaque nouveau grade
                grade_bonus, unlocked_grades = grade_bonus_between_levels(old_level, lvl, cap=cap)
                kz_gain += int(grade_bonus)

                if kz_gain != 0:
                    con.execute(
                        "UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id=?",
                        (int(kz_gain), int(user_id)),
                    )

                # Débloque / applique automatiquement la couleur du dernier grade atteint
                # - si l'utilisateur n'a pas défini de couleur
                # - OU si sa couleur actuelle correspondait à la couleur du grade précédent
                if unlocked_grades:
                    last_grade = unlocked_grades[-1]
                    if last_grade.profile_color:
                        from .leveling import grade_for_level
                        old_grade = grade_for_level(old_level, cap=cap)
                        if (prev_profile_color is None) or (old_grade.profile_color and prev_profile_color == old_grade.profile_color):
                            con.execute(
                                "UPDATE users SET profile_color=? WHERE user_id=?",
                                (str(last_grade.profile_color), int(user_id)),
                            )
        except Exception:
            pass

        return xp, lvl

    def add_xp(self, user_id: int, amount: int) -> tuple[int, int]:
        """Ajoute de l'XP et met à jour le niveau. Retourne (new_xp, new_level)."""
        with self.connect() as con:
            xp, lvl = self._add_xp_in_con(con, int(user_id), int(amount))
            con.commit()
            return xp, lvl
    def add_stat(self, user_id: int, wins_delta: int = 0, losses_delta: int = 0, games_delta: int = 0) -> None:
        # On résout aussi les prédictions sur ce joueur quand il gagne/perd.
        with self.connect() as con:
            con.execute(
                "UPDATE users SET wins=wins+?, losses=losses+?, games_played=games_played+? WHERE user_id=?",
                (wins_delta, losses_delta, games_delta, user_id),
            )

            # XP: progression via les jeux (difficile à monter, cf config + leveling)
            try:
                from . import config
                xp_gain = int(games_delta) * int(getattr(config, 'XP_PER_GAME', 25))
                xp_gain += int(wins_delta) * int(getattr(config, 'XP_BONUS_WIN', 25))
                xp_gain += int(losses_delta) * int(getattr(config, 'XP_BONUS_LOSS', 10))
                if xp_gain > 0:
                    self._add_xp_in_con(con, user_id, xp_gain)
            except Exception:
                pass

            target_result: str | None = None
            if wins_delta > 0:
                target_result = "win"
            elif losses_delta > 0:
                target_result = "lose"

            if target_result:
                self._resolve_predictions_for_target(con, user_id, target_result)

            con.commit()

    # =====================
    # PvP stats
    # =====================
    def add_pvp_stats(
        self,
        user_id: int,
        games_delta: int = 0,
        wins_delta: int = 0,
        losses_delta: int = 0,
        profit_delta: int = 0,
    ) -> None:
        """Met à jour les stats PvP (sans déclencher les prédictions)."""
        with self.connect() as con:
            con.execute(
                "UPDATE users SET pvp_games=pvp_games+?, pvp_wins=pvp_wins+?, pvp_losses=pvp_losses+?, pvp_profit=pvp_profit+? WHERE user_id=?",
                (int(games_delta), int(wins_delta), int(losses_delta), int(profit_delta), int(user_id)),
            )


            # XP: progression PvP
            try:
                from . import config
                xp_gain = int(games_delta) * int(getattr(config, 'XP_PER_PVP_GAME', 35))
                xp_gain += int(wins_delta) * int(getattr(config, 'XP_BONUS_PVP_WIN', 35))
                xp_gain += int(losses_delta) * int(getattr(config, 'XP_BONUS_PVP_LOSS', 15))
                if xp_gain > 0:
                    self._add_xp_in_con(con, user_id, xp_gain)
            except Exception:
                pass
            con.commit()

    # =====================
    # Predictions
    # =====================

    def add_bot_stats(self, user_id: int, *, bot_win: bool):
        """Enregistre un résultat contre le bot. bot_win=True si le joueur a 'battu' le bot."""
        if bot_win:
            self.execute("UPDATE users SET bot_wins = bot_wins + 1 WHERE user_id=?", (user_id,))
            # XP bot: petite récompense
            try:
                self.add_xp(user_id, 20)
            except Exception:
                pass
        else:
            self.execute("UPDATE users SET bot_losses = bot_losses + 1 WHERE user_id=?", (user_id,))
            try:
                self.add_xp(user_id, 10)
            except Exception:
                pass


    def upsert_prediction(self, predictor_id: int, target_id: int, bet: int, choice: str) -> None:
        """Crée/écrase une prédiction (l'argent est géré par la commande, pas ici)."""
        with self.connect() as con:
            con.execute(
                "INSERT INTO predictions (predictor_id, target_id, bet, choice, created_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(predictor_id, target_id) DO UPDATE SET bet=excluded.bet, choice=excluded.choice, created_at=excluded.created_at",
                (predictor_id, target_id, int(bet), str(choice), utcnow_iso()),
            )
            con.commit()

    def delete_prediction(self, predictor_id: int, target_id: int) -> sqlite3.Row | None:
        """Supprime une prédiction et renvoie la ligne supprimée (pour rembourser si besoin)."""
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM predictions WHERE predictor_id=? AND target_id=?",
                (predictor_id, target_id),
            ).fetchone()
            if row:
                con.execute(
                    "DELETE FROM predictions WHERE predictor_id=? AND target_id=?",
                    (predictor_id, target_id),
                )
            con.commit()
            return row

    def list_predictions_for_user(self, user_id: int) -> list[sqlite3.Row]:
        return self.fetchall(
            "SELECT * FROM predictions WHERE predictor_id=? OR target_id=? ORDER BY created_at DESC",
            (user_id, user_id),
        )

    def list_prediction_logs_for_user(self, user_id: int, limit: int = 10) -> list[sqlite3.Row]:
        return self.fetchall(
            "SELECT * FROM prediction_logs WHERE predictor_id=? OR target_id=? ORDER BY id DESC LIMIT ?",
            (user_id, user_id, int(limit)),
        )

    def _resolve_predictions_for_target(self, con: sqlite3.Connection, target_id: int, target_result: str) -> None:
        """Résout toutes les prédictions en attente concernant target_id.

        Règle:
          - Le predictor mise X (déjà retiré à la création = escrow).
          - Si la prédiction est correcte: le predictor récupère son escrow (X) + prend X au target (si possible).
          - Si incorrecte: l'escrow (X) est donné au target.
        """
        pending = con.execute(
            "SELECT * FROM predictions WHERE target_id=?",
            (target_id,),
        ).fetchall()
        if not pending:
            return

        # solde actuel du target (on le met à jour au fil des transferts)
        target_row = con.execute("SELECT balance FROM users WHERE user_id=?", (target_id,)).fetchone()
        target_balance = int(target_row["balance"]) if target_row else 0

        for p in pending:
            predictor_id = int(p["predictor_id"])
            bet = int(p["bet"])
            choice = str(p["choice"]).lower()

            # Always ensure predictor exists
            con.execute(
                "INSERT OR IGNORE INTO users (user_id, balance, created_at) VALUES (?, ?, ?)",
                (predictor_id, 0, utcnow_iso()),
            )

            correct = (choice == target_result)

            paid_from_target = 0
            if correct:
                # refund escrow
                con.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (bet, predictor_id))

                # take bet from target if possible
                paid_from_target = min(bet, target_balance)
                if paid_from_target > 0:
                    con.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (paid_from_target, target_id))
                    con.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (paid_from_target, predictor_id))
                    target_balance -= paid_from_target
            else:
                # give escrow to target
                con.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (bet, target_id))

            con.execute(
                "INSERT INTO prediction_logs (predictor_id, target_id, bet, choice, result, paid_from_target, created_at, resolved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    predictor_id,
                    target_id,
                    bet,
                    choice,
                    target_result,
                    paid_from_target,
                    str(p["created_at"]),
                    utcnow_iso(),
                ),
            )

        con.execute("DELETE FROM predictions WHERE target_id=?", (target_id,))

    def set_user_field(self, user_id: int, field: str, value: Any) -> None:
        # field must be trusted (internal)
        self.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        if row is None:
            return default
        return str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            con.commit()

    # ---- inventory / boosts ----
    # ===== Channel gating (allowed channels + bypass users) =====
    def add_allowed_channel(self, guild_id: int, channel_id: int) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO allowed_channels (guild_id, channel_id) VALUES (?, ?)",
                (int(guild_id), int(channel_id)),
            )

    def remove_allowed_channel(self, guild_id: int, channel_id: int) -> None:
        with self.connect() as con:
            con.execute(
                "DELETE FROM allowed_channels WHERE guild_id=? AND channel_id=?",
                (int(guild_id), int(channel_id)),
            )

    def list_allowed_channels(self, guild_id: int) -> list[int]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT channel_id FROM allowed_channels WHERE guild_id=? ORDER BY channel_id ASC",
                (int(guild_id),),
            ).fetchall()
        return [int(r[0]) for r in rows]


    def clear_allowed_channels(self, guild_id: int) -> None:
        """Supprime la whitelist de salons pour un serveur."""
        with self.connect() as con:
            con.execute(
                "DELETE FROM allowed_channels WHERE guild_id=?",
                (int(guild_id),),
            )

    def is_channel_allowed(self, guild_id: int, channel_id: int) -> bool:
        allowed = self.list_allowed_channels(guild_id)
        if not allowed:
            return True  # aucune restriction configurée
        return int(channel_id) in set(allowed)

    # ---- allowed categories ----
    def add_allowed_category(self, guild_id: int, category_id: int) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO allowed_categories (guild_id, category_id) VALUES (?, ?)",
                (int(guild_id), int(category_id)),
            )

    def remove_allowed_category(self, guild_id: int, category_id: int) -> None:
        with self.connect() as con:
            con.execute(
                "DELETE FROM allowed_categories WHERE guild_id=? AND category_id=?",
                (int(guild_id), int(category_id)),
            )

    def list_allowed_categories(self, guild_id: int) -> list[int]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT category_id FROM allowed_categories WHERE guild_id=? ORDER BY category_id ASC",
                (int(guild_id),),
            ).fetchall()
        return [int(r[0]) for r in rows]

    def clear_allowed_categories(self, guild_id: int) -> None:
        """Supprime la whitelist de catégories pour un serveur."""
        with self.connect() as con:
            con.execute(
                "DELETE FROM allowed_categories WHERE guild_id=?",
                (int(guild_id),),
            )

    def is_category_allowed(self, guild_id: int, category_id: int) -> bool:
        allowed = self.list_allowed_categories(guild_id)
        if not allowed:
            return True  # aucune restriction configurée
        return int(category_id) in set(allowed)

    def add_bypass_user(self, guild_id: int, user_id: int) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO bypass_users (guild_id, user_id) VALUES (?, ?)",
                (int(guild_id), int(user_id)),
            )

    def remove_bypass_user(self, guild_id: int, user_id: int) -> None:
        with self.connect() as con:
            con.execute(
                "DELETE FROM bypass_users WHERE guild_id=? AND user_id=?",
                (int(guild_id), int(user_id)),
            )

    def list_bypass_users(self, guild_id: int) -> list[int]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT user_id FROM bypass_users WHERE guild_id=? ORDER BY user_id ASC",
                (int(guild_id),),
            ).fetchall()
        return [int(r[0]) for r in rows]

    def is_bypass_user(self, guild_id: int, user_id: int) -> bool:
        with self.connect() as con:
            row = con.execute(
                "SELECT 1 FROM bypass_users WHERE guild_id=? AND user_id=?",
                (int(guild_id), int(user_id)),
            ).fetchone()
        return row is not None


    def get_inventory(self, user_id: int) -> dict[str, int]:
        row = self.fetchone("SELECT inventory_json FROM users WHERE user_id=?", (user_id,))
        if not row:
            return {}
        try:
            return json.loads(row["inventory_json"]) or {}
        except Exception:
            return {}

    def set_inventory(self, user_id: int, inv: dict[str, int]) -> None:
        self.execute("UPDATE users SET inventory_json=? WHERE user_id=?", (json.dumps(inv), user_id))

    def get_boosts(self, user_id: int) -> dict[str, Any]:
        row = self.fetchone("SELECT boosts_json FROM users WHERE user_id=?", (user_id,))
        if not row:
            return {}
        try:
            return json.loads(row["boosts_json"]) or {}
        except Exception:
            return {}

    def set_boosts(self, user_id: int, boosts: dict[str, Any]) -> None:
        self.execute("UPDATE users SET boosts_json=? WHERE user_id=?", (json.dumps(boosts), user_id))

    # ---- blacklist ----
    def bl_get(self, user_id: int) -> sqlite3.Row | None:
        return self.fetchone("SELECT * FROM blacklist WHERE user_id=?", (user_id,))

    def bl_add(self, user_id: int, by_id: int, reason: str | None, expires_at: str | None) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT INTO blacklist (user_id, reason, by_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET reason=excluded.reason, by_id=excluded.by_id, created_at=excluded.created_at, expires_at=excluded.expires_at",
                (user_id, reason, by_id, utcnow_iso(), expires_at),
            )
            con.commit()

    def bl_remove(self, user_id: int) -> None:
        self.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))

    def bl_list(self) -> list[sqlite3.Row]:
        return self.fetchall("SELECT * FROM blacklist ORDER BY created_at DESC")

    # ---- bot admins ----
    def is_bot_admin(self, user_id: int) -> bool:
        row = self.fetchone("SELECT user_id FROM bot_admins WHERE user_id=?", (user_id,))
        return row is not None

    def add_bot_admin(self, user_id: int) -> None:
        self.execute("INSERT OR IGNORE INTO bot_admins (user_id) VALUES (?)", (user_id,))

    def remove_bot_admin(self, user_id: int) -> None:
        self.execute("DELETE FROM bot_admins WHERE user_id=?", (user_id,))

    def list_bot_admins(self) -> list[int]:
        rows = self.fetchall("SELECT user_id FROM bot_admins")
        return [int(r["user_id"]) for r in rows]


# ==========================
    # Activity rewards helpers
    # ==========================
    def _activity_ensure_row(self, user_id: int) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO activity(user_id, msg_count, voice_seconds) VALUES(?, 0, 0)",
                (user_id,),
            )
            con.commit()

    def activity_add_message(self, user_id: int, n: int) -> int:
        self._activity_ensure_row(user_id)
        with self.connect() as con:
            con.execute("UPDATE activity SET msg_count = msg_count + ? WHERE user_id=?", (n, user_id))
            row = con.execute("SELECT msg_count FROM activity WHERE user_id=?", (user_id,)).fetchone()
            con.commit()
        return int(row["msg_count"]) if row else 0

    def activity_add_voice_seconds(self, user_id: int, seconds: int) -> int:
        self._activity_ensure_row(user_id)
        with self.connect() as con:
            con.execute("UPDATE activity SET voice_seconds = voice_seconds + ? WHERE user_id=?", (seconds, user_id))
            row = con.execute("SELECT voice_seconds FROM activity WHERE user_id=?", (user_id,)).fetchone()
            con.commit()
        return int(row["voice_seconds"]) if row else 0

    def activity_get(self, user_id: int):
        return self.fetchone("SELECT * FROM activity WHERE user_id=?", (user_id,))


# ==========================
    # Admin removal / wipe helpers
    # ==========================
    def clamp_balance_non_negative(self, user_id: int) -> int:
        row = self.get_user(user_id)
        if not row:
            return 0
        bal = int(row["balance"])
        if bal < 0:
            self.set_balance(user_id, 0)
            return 0
        return bal

    def remove_balance(self, user_id: int, amount: int) -> int:
        """Enlève des coins (clamp à 0) et renvoie le nouveau solde."""
        self.add_balance(user_id, -abs(int(amount)))
        return self.clamp_balance_non_negative(user_id)

    def remove_item(self, user_id: int, item_id: str, qty: int) -> int:
        """Enlève qty d'un item. Retourne la quantité restante."""
        inv = self.get_inventory(user_id)
        cur = int(inv.get(item_id, 0))
        qty = abs(int(qty))
        if qty <= 0:
            return cur
        new = cur - qty
        if new > 0:
            inv[item_id] = new
        else:
            inv.pop(item_id, None)
            new = 0
        self.set_inventory(user_id, inv)
        return new

    def clear_items(self, user_id: int) -> None:
        self.set_inventory(user_id, {})

    # ---- loans / prêts ----
    def loans_count_active_for_user(self, borrower_id: int) -> int:
        """Compte les prêts PENDING/ACTIVE pour un emprunteur (BANQUE + P2P)."""
        row = self.fetchone(
            "SELECT COUNT(*) AS c FROM loans WHERE borrower_id=? AND status IN ('PENDING','ACTIVE')",
            (int(borrower_id),),
        )
        return int(row["c"]) if row else 0

    def loans_count_pending_for_lender(self, lender_id: int) -> int:
        row = self.fetchone(
            "SELECT COUNT(*) AS c FROM loans WHERE lender_id=? AND status='PENDING' AND kind='P2P'",
            (int(lender_id),),
        )
        return int(row["c"]) if row else 0

    def loans_create_request(
        self,
        borrower_id: int,
        principal: int,
        interest_pct: float,
        term_days: int,
        note: str | None,
        *,
        kind: str = "BANK",
        lender_id: int | None = None,
    ) -> int:
        """Crée une demande de prêt (PENDING) et retourne son ID."""
        principal_i = int(principal)
        interest_f = float(interest_pct)
        total = int(round(principal_i * (1.0 + (interest_f / 100.0))))
        created_at = datetime.now(timezone.utc).isoformat()

        with self.connect() as con:
            cur = con.execute(
                """
                INSERT INTO loans (
                    kind, lender_id, borrower_id,
                    principal, interest_pct,
                    total_due, remaining_due,
                    term_days, status,
                    note, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (
                    str(kind),
                    int(lender_id) if lender_id is not None else None,
                    int(borrower_id),
                    principal_i,
                    interest_f,
                    int(total),
                    int(total),
                    int(term_days),
                    note,
                    created_at,
                ),
            )
            con.commit()
            return int(cur.lastrowid)

    def loans_get(self, loan_id: int) -> sqlite3.Row | None:
        return self.fetchone("SELECT * FROM loans WHERE loan_id=?", (int(loan_id),))

    def loans_list_for_user(self, user_id: int) -> list[sqlite3.Row]:
        # inclut les prêts où l'utilisateur est emprunteur OU prêteur (P2P)
        return self.fetchall(
            "SELECT * FROM loans WHERE borrower_id=? OR lender_id=? ORDER BY loan_id DESC LIMIT 50",
            (int(user_id), int(user_id)),
        )

    def loans_set_decision(
        self,
        loan_id: int,
        status: str,
        decided_by: int,
        approved_at: str | None = None,
        due_at: str | None = None,
    ) -> None:
        """Met à jour la décision (accept/refuse) d'un prêt."""
        with self.connect() as con:
            con.execute(
                """
                UPDATE loans
                SET
                    status=?,
                    decided_by=?,
                    approved_at=COALESCE(?, approved_at),
                    due_at=COALESCE(?, due_at)
                WHERE loan_id=?
                """,
                (str(status), int(decided_by), approved_at, due_at, int(loan_id)),
            )
            con.commit()

    def loans_set_status(self, loan_id: int, status: str) -> None:
        self.execute("UPDATE loans SET status=? WHERE loan_id=?", (str(status), int(loan_id)))

    def loans_apply_payment(self, loan_id: int, amount: int) -> sqlite3.Row | None:
        """Déduit un paiement. Renvoie la ligne mise à jour."""
        loan = self.loans_get(int(loan_id))
        if not loan:
            return None
        remaining = int(loan["remaining_due"])
        new_remaining = max(0, remaining - int(amount))
        new_status = "REPAID" if new_remaining == 0 else str(loan["status"])
        with self.connect() as con:
            con.execute(
                "UPDATE loans SET remaining_due=?, status=? WHERE loan_id=?",
                (int(new_remaining), new_status, int(loan_id)),
            )
            con.commit()
        return self.loans_get(int(loan_id))


    def wipe_user(self, user_id: int) -> None:
        """Reset total d’un joueur (KZ, inv, boosts, VIP, immunité, cooldowns, sabotage etc)."""
        self.set_balance(user_id, 0)
        self.set_inventory(user_id, {})
        self.set_boosts(user_id, {})
        safe_fields = [
            "vip_until",
            "immunity_until",
            "last_daily",
            "last_weekly",
            "last_work",
            "last_chest",
            "last_steal",
            "last_sabotage",
            "sabotaged_until",
        ]
        for f in safe_fields:
            try:
                self.set_user_field(user_id, f, None)
            except Exception:
                pass

    def wipe_all_users(self) -> None:
        """DANGEREUX: wipe tous les utilisateurs."""
        with self.connect() as con:
            con.execute("UPDATE users SET balance=0, inventory_json='{}', boosts_json='{}', vip_until=NULL, immunity_until=NULL, last_daily=NULL, last_weekly=NULL, last_work=NULL, last_chest=NULL, last_steal=NULL, last_sabotage=NULL, sabotaged_until=NULL")
            try:
                con.execute("DELETE FROM activity")
            except Exception:
                pass
            con.commit()

    # ======================================================
    # Game stats (par jeu) — blackjack / coinflip / etc.
    # ======================================================
    def add_game_stat(
        self,
        user_id: int,
        game: str,
        games_delta: int = 0,
        wins_delta: int = 0,
        losses_delta: int = 0,
        profit_delta: int = 0,
    ) -> None:
        """Incrémente les stats d'un jeu pour un utilisateur (table game_stats)."""
        game = (game or "").strip().lower()
        if not game:
            return
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO game_stats (user_id, game, games, wins, losses, profit, updated_at)
                VALUES (?, ?, 0, 0, 0, 0, ?)
                ON CONFLICT(user_id, game) DO UPDATE SET updated_at=excluded.updated_at
                """,
                (int(user_id), game, utcnow_iso()),
            )
            con.execute(
                "UPDATE game_stats SET games=games+?, wins=wins+?, losses=losses+?, profit=profit+?, updated_at=? WHERE user_id=? AND game=?",
                (int(games_delta), int(wins_delta), int(losses_delta), int(profit_delta), utcnow_iso(), int(user_id), game),
            )

    def get_game_stat(self, user_id: int, game: str) -> dict[str, int] | None:
        """Retourne les stats d'un jeu (games/wins/losses/profit) ou None."""
        game = (game or "").strip().lower()
        if not game:
            return None
        with self.connect() as con:
            row = con.execute(
                "SELECT games, wins, losses, profit FROM game_stats WHERE user_id=? AND game=?",
                (int(user_id), game),
            ).fetchone()
            if not row:
                return None
            return {"games": int(row[0] or 0), "wins": int(row[1] or 0), "losses": int(row[2] or 0), "profit": int(row[3] or 0)}

    def get_all_game_stats(self, user_id: int) -> dict[str, dict[str, int]]:
        """Retourne toutes les stats par jeu pour un utilisateur."""
        with self.connect() as con:
            rows = con.execute(
                "SELECT game, games, wins, losses, profit FROM game_stats WHERE user_id=? ORDER BY game ASC",
                (int(user_id),),
            ).fetchall()
        out: dict[str, dict[str, int]] = {}
        for g, games, wins, losses, profit in rows:
            out[str(g)] = {"games": int(games or 0), "wins": int(wins or 0), "losses": int(losses or 0), "profit": int(profit or 0)}
        return out