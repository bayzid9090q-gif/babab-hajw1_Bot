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

# Render Persistent Disk-এর জন্য:
# DB_PATH=/var/data/bot.db
DB_PATH = os.getenv("DB_PATH", "./bot.db").strip()

DB = Path(DB_PATH)

# Database folder না থাকলে তৈরি করবে
DB.parent.mkdir(parents=True, exist_ok=True)

# Bangladesh timezone
BD_TIMEZONE = ZoneInfo("Asia/Dhaka")

ADMIN_IDS = {
    8040845647,
    8296972506,
    6905592655,
}

# Daily Spin rewards
WHEEL = [1, 0, 3, 0, 5, 0, 1, 0]

# Paid Panel unlock requirement
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
# UI
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
                callback_data="coins",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Referral",
                callback_data="ref",
            ),
            InlineKeyboardButton(
                "💎 Paid Panel",
                callback_data="paid",
            ),
        ],
        [
            InlineKeyboardButton(
                "🎁 Free Panel",
                callback_data="free",
            ),
        ],
    ])


def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Stats",
                callback_data="astats",
            ),
            InlineKeyboardButton(
                "📜 Panels",
                callback_data="alist",
            ),
        ],
    ])


# ==============================================================================
# TELEGRAM HELPERS
# ==============================================================================

async def joined(bot, uid: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=uid,
        )

        return member.status in {
            "member",
            "administrator",
            "creator",
        }

    except Exception:
        return False


async def send_join_message(message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=CHANNEL_LINK,
            )
        ],
        [
            InlineKeyboardButton(
                "🔍 Check Join",
                callback_data="check",
            )
        ],
    ])

    await message.reply_text(
        "✨ <b>WELCOME!</b> ✨\n\n"
        "👉 প্রথমে আমাদের Channel-এ Join করুন।\n"
        "তারপর নিচের <b>Check Join</b> বাটনে চাপুন।",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def send_main_menu(target, edit=False):
    text = (
        "✨ <b>PANEL BOT</b> ✨\n\n"
        "🪙 Coin • 👥 Referral • 🎯 Daily Spin\n"
        "💎 Paid Panel • 🎁 Free Panel"
    )

    if edit:
        await target.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=menu(),
        )
    else:
        await target.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=menu(),
        )


# ==============================================================================
# COMMANDS
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    ensure_user(
        user.id,
        user.username,
    )

    # --------------------------------------------------------------------------
    # REFERRAL
    # --------------------------------------------------------------------------

    if context.args:
        arg = context.args[0]

        if arg.isdigit():
            referrer_id = int(arg)

            if referrer_id != user.id:
                already = conn.execute(
                    """
                    SELECT 1
                    FROM referrals
                    WHERE new_user=?
                    """,
                    (user.id,),
                ).fetchone()

                if already is None:
                    ensure_user(referrer_id)

                    try:
                        conn.execute(
                            """
                            INSERT INTO referrals(new_user, referrer)
                            VALUES (?, ?)
                            """,
                            (user.id, referrer_id),
                        )

                        conn.execute(
                            """
                            UPDATE users
                            SET referrals=referrals+1,
                                coins=coins+5
                            WHERE user_id=?
                            """,
                            (referrer_id,),
                        )

                        conn.commit()

                    except sqlite3.IntegrityError:
                        conn.rollback()

    # --------------------------------------------------------------------------
    # CHANNEL CHECK
    # --------------------------------------------------------------------------

    if not await joined(context.bot, user.id):
        await send_join_message(update.message)
        return

    await send_main_menu(update.message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📍 <b>HELP</b>\n\n"
        "/start - Start bot\n"
        "/help - Help\n"
        "/admin - Admin panel\n"
        "/stats - Bot statistics\n"
        "/addfree
