import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)


# ==============================================================================
# CONFIG
# ==============================================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set.")

try:
    CHANNEL_ID = int(
        os.getenv("CHANNEL_ID", "-1003087197996").strip()
    )
except ValueError:
    raise RuntimeError("CHANNEL_ID must be a valid Telegram chat ID.")

CHANNEL_LINK = os.getenv(
    "CHANNEL_LINK",
    "https://t.me/u20fgDLKHLHnZjV1",
).strip()

DB_PATH = os.getenv("DB_PATH", "./bot.db").strip()

DB = Path(DB_PATH)
DB.parent.mkdir(parents=True, exist_ok=True)

BD_TIMEZONE = ZoneInfo("Asia/Dhaka")

ADMIN_IDS = {
    8040845647,
    8296972506,
    6905592655,
}

WHEEL = [1, 0, 3, 0, 5, 0, 1, 0]

REQUIRED_REFERRALS = 5
REQUIRED_COINS = 100


# ==============================================================================
# DATABASE
# ==============================================================================

conn = sqlite3.connect(
    DB,
    check_same_thread=False,
)

conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")

conn.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT DEFAULT '',
    coins INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    last_spin TEXT
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    new_user INTEGER PRIMARY KEY,
    referrer INTEGER NOT NULL
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL
)
""")

conn.commit()


# ==============================================================================
# DATABASE HELPERS
# ==============================================================================

def ensure_user(uid: int, username: str = ""):
    username = username or ""

    conn.execute(
        """
        INSERT OR IGNORE INTO users(user_id, username)
        VALUES (?, ?)
        """,
        (uid, username),
    )

    conn.execute(
        """
        UPDATE users
        SET username=?
        WHERE user_id=?
        """,
        (username, uid),
    )

    conn.commit()


def add_panel(name: str, kind: str, value: str):
    conn.execute(
        """
        INSERT INTO panels(name, kind, value)
        VALUES (?, ?, ?)
        """,
        (name, kind, value),
    )

    conn.commit()


def get_user(uid: int):
    return conn.execute(
        """
        SELECT coins, referrals, last_spin
        FROM users
        WHERE user_id=?
        """,
        (uid,),
    ).fetchone()


def today_bd() -> str:
    return datetime.now(BD_TIMEZONE).date().isoformat()


# ==============================================================================
# USER MENU
# ==============================================================================

def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎯 Daily Spin",
                callback_data="spin",
            ),
            InlineKeyboardButton(
                "🪙 My Coins",
                callback_data="coins
