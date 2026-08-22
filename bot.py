import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

CHANNEL_ID = int(
    os.getenv(
        "CHANNEL_ID",
        "-1003087197996"
    )
)

CHANNEL_LINK = os.getenv(
    "CHANNEL_LINK",
    "https://t.me/u20fgDLKHLHnZjV1"
).strip()

DB_PATH = os.getenv(
    "DB_PATH",
    "./bot.db"
).strip()

ADMIN_IDS = {
    8040845647,
    8296972506,
    6905592655,
}

REQUIRED_REFERRALS = 5
REQUIRED_COINS = 100

WHEEL = [
    1,
    0,
    3,
    0,
    5,
    0,
    1,
    0,
]

BD_TIMEZONE = ZoneInfo(
    "Asia/Dhaka"
)


# ============================================================
# DATABASE
# ============================================================

db_file = Path(DB_PATH)

db_file.parent.mkdir(
    parents=True,
    exist_ok=True
)

conn = sqlite3.connect(
    str(db_file),
    check_same_thread=False
)

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        coins INTEGER DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        last_spin TEXT DEFAULT ''
    )
    """
)

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS referrals (
        new_user INTEGER PRIMARY KEY,
        referrer INTEGER NOT NULL
    )
    """
)

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS panels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        value TEXT NOT NULL
    )
    """
)

conn.commit()


# ============================================================
# DATABASE HELPERS
# ============================================================

def ensure_user(
    user_id: int,
    username: str = ""
):
    conn.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, username)
        VALUES (?, ?)
        """,
        (
            user_id,
            username or ""
        )
    )

    conn.execute(
        """
        UPDATE users
        SET username = ?
        WHERE user_id = ?
        """,
        (
            username or "",
            user_id
        )
    )

    conn.commit()


def get_user(user_id: int):
    return conn.execute(
        """
        SELECT coins, referrals, last_spin
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()


def add_panel(
    name: str,
    kind: str,
    value: str
):
    conn.execute(
        """
        INSERT INTO panels
        (name, kind, value)
        VALUES (?, ?, ?)
        """,
        (
            name,
            kind,
            value
        )
    )

    conn.commit()


def get_today():
    return datetime.now(
        BD_TIMEZONE
    ).date().isoformat()


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    return InlineKeyboardMarkup(
        [
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
        ]
    )


# ============================================================
# ADMIN MENU
# ============================================================

def admin_menu():

    return InlineKeyboardMarkup(
        [
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
                    "🔙 Back",
                    callback_data="back"
                ),
            ],
        ]
    )


# ============================================================
# CHANNEL JOIN CHECK
# ============================================================

async def is_joined(
    bot,
    user_id: int
) -> bool:

    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id
        )

        return member.status in (
            "member",
            "administrator",
            "creator"
        )

    except Exception as error:
        print(
            "CHANNEL CHECK ERROR:",
            error
        )
        return False


# ============================================================
# JOIN MESSAGE
# ============================================================

async def send_join_message(
    message
):

    keyboard = InlineKeyboardMarkup(
        [
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
        ]
    )

    await message.reply_text(
        "✨ <b>WELCOME!</b> ✨\n\n"
        "👉 প্রথমে আমাদের Channel-এ Join করুন।\n\n"
        "তারপর <b>Check Join</b> চাপুন।",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


# ============================================================
# SHOW MAIN MENU
# ============================================================

async def show_main_menu(
    target,
    edit=False
):

    text = (
        "✨ <b>PANEL BOT</b> ✨\n\n"
        "🪙 Coin\n"
        "👥 Referral\n"
        "🎯 Daily Spin\n"
        "💎 Paid Panel\n"
        "🎁 Free Panel"
    )

    if edit:

        await target.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu()
        )

    else:

        await target.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu()
        )


# ============================================================
# START COMMAND
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    ensure_user(
        user.id,
        user.username
    )

    # -------------------------------
    # REFERRAL
    # -------------------------------

    if context.args:

        argument = context.args[0]

        if argument.isdigit():

            referrer_id = int(
                argument
            )

            if referrer_id != user.id:

                existing = conn.execute(
                    """
                    SELECT 1
                    FROM referrals
                    WHERE new_user = ?
                    """,
                    (user.id,)
                ).fetchone()

                if existing is None:

                    ensure_user(
                        referrer_id
                    )

                    try:

                        conn.execute(
                            """
                            INSERT INTO referrals
                            (new_user, referrer)
                            VALUES (?, ?)
                            """,
                            (
                                user.id,
                                referrer_id
                            )
                        )

                        conn.execute(
                            """
                            UPDATE users
                            SET referrals = referrals + 1,
                                coins = coins + 5
                            WHERE user_id = ?
                            """,
                            (referrer_id,)
                        )

                        conn.commit()

                    except sqlite3.IntegrityError:

                        conn.rollback()

    # -------------------------------
    # CHANNEL CHECK
    # -------------------------------

    if not await is_joined(
        context.bot,
        user.id
    ):

        await send_join_message(
            update.message
        )

        return

    await show_main_menu(
        update.message
    )


# ============================================================
# HELP COMMAND
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📍 <b>HELP</b>\n\n"
        "/start - Start bot\n"
        "/help - Help\n"
        "/admin - Admin panel\n"
        "/stats - Statistics\n"
        "/addfree Name|URL\n"
        "/addpaid Name|URL\n"
        "/delpanel ID",
        parse_mode=ParseMode.HTML
    )


# ============================================================
# ADMIN COMMAND
# ============================================================

async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id not in ADMIN_IDS:

        await update.message.reply_text(
            "⛔ Admin only."
        )

        return

    await update.message.reply_text(
        "👑 <b>ADMIN PANEL</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_menu()
    )


# ============================================================
# STATS COMMAND
# ============================================================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id not in ADMIN_IDS:

        await update.message.reply_text(
            "⛔ Admin only."
        )

        return

    users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    panels = conn.execute(
        "SELECT COUNT(*) FROM panels"
    ).fetchone()[0]

    coins = conn.execute(
        "SELECT COALESCE(SUM(coins), 0) FROM users"
    ).fetchone()[0]

    referrals = conn.execute(
        "SELECT COALESCE(SUM(referrals), 0) FROM users"
    ).fetchone()[0]

    text = (
        "📊 <b>BOT STATS</b>\n\n"
        f"👤 Users: <code>{users}</code>\n"
        f"📜 Panels: <code>{panels}</code>\n"
        f"🪙 Total Coins: <code>{coins}</code>\n"
        f"👥 Total Referrals: <code>{referrals}</code>"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML
    )


# ============================================================
# ADD FREE PANEL
# ============================================================

async def addfree_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id not in ADMIN_IDS:

        await update.message.reply_text(
            "⛔ Admin only."
        )

        return

    raw = " ".join(
        context.args
    ).strip()

    if "|" not in raw:

        await update.message.reply_text(
            "⚠️ ব্যবহার:\n"
            "/addfree Panel Name|https://example.com"
        )

        return

    name, value = raw.split(
        "|",
        1
    )

    name = name.strip()
    value = value.strip()

    if not name or not value:

        await update.message.reply_text(
            "⚠️ Name এবং URL দিতে হবে।"
        )

        return

    add_panel(
        name,
        "free",
        value
    )

    await update.message.reply_text(
        "✅ Free Panel added:\n"
        f"<b>{name}</b>",
        parse_mode=ParseMode.HTML
    )


# ============================================================
# ADD PAID PANEL
# ============================================================

async def addpaid_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id not in ADMIN_IDS:

        await update.message.reply_text(
            "⛔ Admin only."
        )

        return

    raw = " ".join(
        context.args
    ).strip()

    if "|" not in raw:

        await update.message.reply_text(
            "⚠️ ব্যবহার:\n"
            "/addpaid VIP Panel|https://example.com"
        )

        return

    name, value = raw.split(
        "|",
        1
    )

    name = name.strip()
    value = value.strip()

    if not name or not value:

        await update.message.reply_text(
            "⚠️ Name এবং URL দিতে হবে।"
        )

        return

    add_panel(
        name,
        "paid",
        value
    )

    await update.message.reply_text(
        "✅ Paid Panel added:\n"
        f"<b>{name}</b>",
        parse_mode=ParseMode.HTML
    )


# ============================================================
# DELETE PANEL
# ============================================================

async def delpanel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id not in ADMIN_IDS:

        await update.message.reply_text(
            "⛔ Admin only."
        )

        return

    if not context.args:

        await update.message.reply_text(
            "⚠️ ব্যবহার:\n"
            "/delpanel ID"
        )

        return

    panel_id_text = context.args[0]

    if not panel_id_text.isdigit():

        await update.message.reply_text(
            "⚠️ ID অবশ্যই সংখ্যা হতে হবে।"
        )

        return

    panel_id = int(
        panel_id_text
    )

    result = conn.execute(
        """
        DELETE FROM panels
        WHERE id = ?
        """,
        (panel_id,)
    )

    conn.commit()

    if result.rowcount > 0:

        await update.message.reply_text(
            f"🗑️ Panel #{panel_id} deleted."
        )

    else:

        await update.message.reply_text(
            "❌ Panel ID পাওয়া যায়নি।"
        )


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    user_id = query.from_user.id

    ensure_user(
        user_id,
        query.from_user.username
    )

    # ========================================================
    # CHECK JOIN
    # ========================================================

    if query.data == "check":

        if await is_joined(
            context.bot,
            user_id
        ):

            await query.answer(
                "✅ Join verified!"
            )

            await show_main_menu(
                query,
                edit=True
            )

        else:

            await query.answer(
                "❌ আপনি এখনো Channel Join করেননি।",
                show_alert=True
            )

        return

    # ========================================================
    # CHANNEL VERIFICATION
    # ========================================================

    if not await is_joined(
        context.bot,
        user_id
    ):

        await query.answer(
            "❌ আগে Channel Join করুন।",
            show_alert=True
        )

        return

    await query.answer()

    user_data = get_user(
        user_id
    )

    if user_data is None:

        ensure_user(
            user_id,
            query.from_user.username
        )

        user_data = get_user(
            user_id
        )

    coins = user_data[0]
    referrals = user_data[1]
    last_spin = user_data[2]

    # ========================================================
    # MY COINS
    # ========================================================

    if query.data == "coins":

        await query.edit_message_text(
            "👤 <b>MY ACCOUNT</b>\n\n"
            f"🪙 Coins: <code>{coins}</code>\n"
            f"👥 Referrals: <code>{referrals}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu()
        )

    # ========================================================
    # REFERRAL
    # ========================================================

    elif query.data == "ref":

        bot_info = await context.bot.get_me()

        referral_link = (
            "https://t.me/"
            + bot_info.username
            + "?start="
            + str(user_id)
        )

        await query.edit_message_text(
            "🎁 <b>REFERRAL</b>\n\n"
            "🪙 প্রতি valid referral = 5 Coin\n\n"
            f"👥 Your Referrals: <code>{referrals}</code>\n\n"
            "🔗 <b>Your Referral Link:</b>\n"
            f"<code>{referral_link}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu()
        )

    # ========================================================
    # DAILY SPIN
    # ========================================================

    elif query.data == "spin":

        current_day = get_today()

        if last_spin == current_day:

            await query.answer(
                "⏱️ আজকের Spin ইতিমধ্যে নেওয়া হয়েছে।",
                show_alert=True
            )

            return

        reward = random.choice(
            WHEEL
        )

        conn.execute(
            """
            UPDATE users
            SET coins = coins + ?,
                last_spin = ?
            WHERE user_id = ?
            """,
            (
                reward,
                current_day,
                user_id
            )
        )

        conn.commit()

        await query.edit_message_text(
            "🎯 <b>DAILY SPIN</b>\n\n"
            f"🎉 আপনি পেয়েছেন: "
            f"<b>{reward} Coin</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu()
        )

    # ========================================================
    # FREE PANELS
    # ========================================================

    elif query.data == "free":

        rows = conn.execute(
            """
            SELECT id, name, value
            FROM panels
            WHERE kind = 'free'
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

        if not rows:

            await query.edit_message_text(
                "🎁 <b>FREE PANELS</b>\n\n"
                "এখনো কোনো Free Panel নেই।",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu()
            )

            return

        buttons = []

        for panel_id, name, value in rows:

            buttons.append(
                [
                    InlineKeyboardButton(
                        "🎁 " + name,
                        url=value
                    )
                ]
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back"
                )
            ]
        )

        await query.edit_message_text(
            "🎁 <b>FREE PANELS</b>\n\n"
            "নিচের Panel নির্বাচন করুন:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                buttons
            )
        )

    # ========================================================
    # PAID PANEL
    # ========================================================

    elif query.data == "paid":

        if (
            referrals < REQUIRED_REFERRALS
            and coins < REQUIRED_COINS
        ):

            await query.answer(
                "⚠️ Paid Panel পেতে 5 Referral "
                "অথবা 100 Coin লাগবে।",
                show_alert=True
            )

            return

        panel = conn.execute(
            """
            SELECT name, value
            FROM panels
            WHERE kind = 'paid'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        if not panel:

            await query.edit_message_text(
                "💎 <b>PAID PANEL</b>\n\n"
                "এখনো কোনো Paid Panel নেই।",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu()
            )

            return

        panel_name = panel[0]
        panel_url = panel[1]

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "💎 " + panel_name,
                        url=panel_url
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="back"
                    )
                ],
            ]
        )

        await query.edit_message_text(
            "💎 <b>PAID PANEL</b>\n\n"
            "আপনার Paid Panel unlock হয়েছে।",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    # ========================================================
    # BACK
    # ========================================================

    elif query.data == "back":

        await show_main_menu(
            query,
            edit=True
        )

    # ========================================================
    # ADMIN STATS
    # ========================================================

    elif query.data == "astats":

        if user_id not in ADMIN_IDS:

            await query.answer(
                "⛔ Admin only.",
                show_alert=True
            )

            return

        users = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        panels = conn.execute(
            "SELECT COUNT(*) FROM panels"
        ).fetchone()[0]

        coins_total = conn.execute(
            "SELECT COALESCE(SUM(coins), 0) FROM users"
        ).fetchone()[0]

        referrals_total = conn.execute(
            "SELECT COALESCE(SUM(referrals), 0) FROM users"
        ).fetchone()[0]

        await query.edit_message_text(
            "📊 <b>BOT STATS</b>\n\n"
            f"👤 Users: <code>{users}</code>\n"
            f"📜 Panels: <code>{panels}</code>\n"
            f"🪙 Total Coins: <code>{coins_total}</code>\n"
            f"👥 Total Referrals: <code>{referrals_total}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu()
        )

    # ========================================================
    # ADMIN PANEL LIST
    # ========================================================

    elif query.data == "alist":

        if user_id not in ADMIN_IDS:

            await query.answer(
                "⛔ Admin only.",
                show_alert=True
            )

            return

        rows = conn.execute(
            """
            SELECT id, name, kind
            FROM panels
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()

        if rows:

            lines = []

            for panel_id, name, kind in rows:

                lines.append(
                    "#"
                    + str(panel_id)
                    + " | "
                    + name
                    + " | "
                    + kind
                )

            text = (
                "📜 <b>PANELS</b>\n\n"
                + "\n".join(lines)
            )

        else:

            text = (
                "📜 <b>PANELS</b>\n\n"
                "কোনো Panel নেই।"
            )

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu()
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "BOT ERROR:",
        repr(context.error)
    )


# ============================================================
# CREATE APPLICATION
# ============================================================

def create_app():

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin_command
        )
    )

    app.add_handler(
        CommandHandler(
            "stats",
            stats_command
        )
    )

    app.add_handler(
        CommandHandler(
            "addfree",
            addfree_command
        )
    )

    app.add_handler(
        CommandHandler(
            "addpaid",
            addpaid_command
        )
    )

    app.add_handler(
        CommandHandler(
            "delpanel",
            delpanel_command
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    app.add_error_handler(
        error_handler
    )

    return app


# ============================================================
# START BOT
# ============================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "       PANEL BOT STARTING"
    )

    print(
        "================================"
    )

    print(
        "Database:",
        DB_PATH
    )

    print(
        "Channel:",
        CHANNEL_ID
    )

    print(
        "Admins:",
        len(ADMIN_IDS)
    )

    print(
        "Mode: Polling"
    )

    print(
        "================================"
    )

    application = create_app()

    application.run_polling(
        drop_pending_updates=True
    )
