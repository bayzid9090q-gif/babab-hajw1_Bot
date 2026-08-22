import os
import random
import sqlite3
from datetime import date
from pathlib import Path

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
    MessageHandler,
    filters,
)

# ==============================================================================
# CONFIG
# ==============================================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

CHANNEL_ID = int(
    os.getenv("CHANNEL_ID", "-1003087197996").strip()
)

CHANNEL_LINK = os.getenv(
    "CHANNEL_LINK",
    "https://t.me/+Dmi8o5kg_3U0NGJl"
).strip()

ADMIN_IDS = {
    8040845647,
    8296972506,
    6905592655,
}

# ==============================================================================
# DATABASE PATH
# ==============================================================================

db_env = os.getenv("DB_PATH", "").strip()

if db_env:
    DB = Path(db_env)

    try:
        DB.parent.mkdir(parents=True, exist_ok=True)

        test_file = DB.parent / ".write_test"

        with open(test_file, "w") as f:
            f.write("ok")

        test_file.unlink(missing_ok=True)

    except (PermissionError, OSError):
        DB = Path("/tmp/panel_bot.db")
else:
    DB = Path("/tmp/panel_bot.db")


# ==============================================================================
# DATABASE
# ==============================================================================

conn = sqlite3.connect(
    DB,
    check_same_thread=False
)

conn.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT DEFAULT '',
    coins INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    last_spin TEXT DEFAULT ''
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    new_user INTEGER PRIMARY KEY,
    referrer INTEGER
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

WHEEL = [1, 0, 3, 0, 5, 0, 1, 0]


# ==============================================================================
# DATABASE HELPERS
# ==============================================================================

def ensure_user(uid: int, username: str = ""):
    username = username or ""

    conn.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, username, coins, referrals, last_spin)
        VALUES (?, ?, 0, 0, '')
        """,
        (uid, username),
    )

    conn.execute(
        """
        UPDATE users
        SET username = ?
        WHERE user_id = ?
        """,
        (username, uid),
    )

    conn.commit()


def add_panel(name: str, kind: str, value: str):
    conn.execute(
        """
        INSERT INTO panels (name, kind, value)
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
        WHERE user_id = ?
        """,
        (uid,),
    ).fetchone()


def delete_panel(panel_id: int):
    cur = conn.execute(
        """
        DELETE FROM panels
        WHERE id = ?
        """,
        (panel_id,),
    )

    conn.commit()

    return cur.rowcount > 0


# ==============================================================================
# USER MENU
# ==============================================================================

def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎯 Daily Spin",
                callback_data="spin"
            ),
            InlineKeyboardButton(
                "🪙 My Coins",
                callback_data="coins"
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Referral",
                callback_data="ref"
            ),
            InlineKeyboardButton(
                "💎 Paid Panel",
                callback_data="paid"
            ),
        ],
        [
            InlineKeyboardButton(
                "🎁 Free Panel",
                callback_data="free"
            ),
        ],
    ])


# ==============================================================================
# ADMIN MENU
# ==============================================================================

def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Stats",
                callback_data="astats"
            ),
            InlineKeyboardButton(
                "📜 Panels",
                callback_data="alist"
            ),
        ],
        [
            InlineKeyboardButton(
                "🎁 Upload Free App",
                callback_data="upload_free"
            ),
        ],
        [
            InlineKeyboardButton(
                "💎 Upload Paid App",
                callback_data="upload_paid"
            ),
        ],
        [
            InlineKeyboardButton(
                "🗑️ Delete App/Panel",
                callback_data="delete_help"
            ),
        ],
    ])


# ==============================================================================
# CHANNEL JOIN CHECK
# ==============================================================================

async def joined(bot, uid: int) -> bool:
    try:
        member = await bot.get_chat_member(
            CHANNEL_ID,
            uid
        )

        return member.status in (
            "member",
            "administrator",
            "creator",
        )

    except Exception as e:
        print("JOIN CHECK ERROR:", repr(e))
        return False


async def send_join_message(message):

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=CHANNEL_LINK
            )
        ],
        [
            InlineKeyboardButton(
                "🔍 Check Join",
                callback_data="check"
            )
        ],
    ])

    await message.reply_text(
        "✨ *WELCOME!* ✨\n\n"
        "👉 প্রথমে আমাদের Channel-এ Join করুন।\n\n"
        "তারপর নিচের *Check Join* বাটনে চাপুন।",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def send_main_menu(target, edit=False):

    text = (
        "✨ *PANEL BOT* ✨\n\n"
        "🪙 Coin • 👥 Referral • 🎯 Daily Spin\n"
        "💎 Paid Panel • 🎁 Free Panel"
    )

    if edit:
        await target.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
        )

    else:
        await target.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
        )


# ==============================================================================
# /START
# ==============================================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return
