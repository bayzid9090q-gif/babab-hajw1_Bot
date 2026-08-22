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
    "https://t.me/u20fgDLKHLHnZjV1"
).strip()

ADMIN_IDS = {
    8040845647,
    8296972506,
    6905592655,
}

# Render Free-তে /var/data ব্যবহার করা যাবে না
# Persistent Disk থাকলে DB_PATH=/var/data/bot.db দিতে পারো।
# না থাকলে /tmp ব্যবহার হবে।
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


# ==============================================================================
# UI
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

    except Exception:
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

    ensure_user(
        user.id,
        user.username
    )

    # Referral
    if context.args:
        ref_arg = context.args[0].strip()

        if ref_arg.isdigit():
            ref = int(ref_arg)

            if ref != user.id:
                already = conn.execute(
                    """
                    SELECT 1
                    FROM referrals
                    WHERE new_user = ?
                    """,
                    (user.id,),
                ).fetchone()

                if already is None:
                    ensure_user(ref)

                    conn.execute(
                        """
                        INSERT INTO referrals
                        (new_user, referrer)
                        VALUES (?, ?)
                        """,
                        (user.id, ref),
                    )

                    conn.execute(
                        """
                        UPDATE users
                        SET referrals = referrals + 1,
                            coins = coins + 5
                        WHERE user_id = ?
                        """,
                        (ref,),
                    )

                    conn.commit()

    # Channel verification
    if not await joined(
        context.bot,
        user.id
    ):
        await send_join_message(
            update.message
        )
        return

    await send_main_menu(
        update.message
    )


# ==============================================================================
# /HELP
# ==============================================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "📍 *HELP*\n\n"
        "/start - Start bot\n"
        "/admin - Admin panel\n"
        "/stats - Statistics\n"
        "/addfree Name|URL - Add free panel\n"
        "/addpaid Name|URL - Add paid panel\n"
        "/delpanel ID - Delete panel\n\n"
        "Channel join verification is required.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ==============================================================================
# ADMIN
# ==============================================================================

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def admin_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text(
            "⛔ Admin only."
        )
        return

    await update.message.reply_text(
        "👑 *ADMIN PANEL*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_menu(),
    )


# ==============================================================================
# /STATS
# ==============================================================================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    uid = update.effective_user.id

    if not is_admin(uid):
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

    refs = conn.execute(
        "SELECT COALESCE(SUM(referrals), 0) FROM users"
    ).fetchone()[0]

    text = (
        "📊 *BOT STATS*\n\n"
        f"👤 *Users:* `{users}`\n"
        f"📜 *Panels:* `{panels}`\n"
        f"🪙 *Total Coins:* `{coins}`\n"
        f"👥 *Total Referrals:* `{refs}`"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN
    )


# ==============================================================================
# /ADDFREE
# ==============================================================================

async def addfree_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    uid = update.effective_user.id

    if not is_admin(uid):
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
            "/addfree Panel Name|https://example.com/panel"
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
        f"✅ Free Panel added: *{name}*",
        parse_mode=ParseMode.MARKDOWN
    )


# ==============================================================================
# /ADDPAID
# ==============================================================================

async def addpaid_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    uid = update.effective_user.id

    if not is_admin(uid):
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
            "/addpaid VIP Panel|https://example.com/panel"
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
        f"✅ Paid Panel added: *{name}*",
        parse_mode=ParseMode.MARKDOWN
    )


# ==============================================================================
# /DELPANEL
# ==============================================================================

async def delpanel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text(
            "⛔ Admin only."
        )
        return

    if (
        not context.args
        or not context.args[0].isdigit()
    ):
        await update.message.reply_text(
            "⚠️ ব্যবহার:\n"
            "/delpanel Panel_ID"
        )
        return

    panel_id = int(
        context.args[0]
    )

    cur = conn.execute(
        """
        DELETE FROM panels
        WHERE id = ?
        """,
        (panel_id,),
    )

    conn.commit()

    if cur.rowcount:
        await update.message.reply_text(
            f"🗑️ Panel #{panel_id} মুছে ফেলা হয়েছে।"
        )
    else:
        await update.message.reply_text(
            "❌ Panel ID পাওয়া যায়নি।"
        )


# ==============================================================================
# CALLBACKS
# ==============================================================================

async def callbacks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    uid = query.from_user.id

    ensure_user(
        uid,
        query.from_user.username
    )

    # --------------------------------------------------------------------------
    # CHECK JOIN
    # --------------------------------------------------------------------------

    if query.data == "check":
        if await joined(
            context.bot,
            uid
        ):
            await query.answer(
                "✅ Join verified!"
            )

            await send_main_menu(
                query,
                edit=True
            )
        else:
            await query.answer(
                "❌ আপনি এখনো Channel-এ Join হননি!",
                show_alert=True
            )

        return

    # --------------------------------------------------------------------------
    # ADMIN CALLBACKS
    # --------------------------------------------------------------------------

    if query.data in (
        "astats",
        "alist",
    ):
        if not is_admin(uid):
            await query.answer(
                "⛔ Admin only.",
                show_alert=True
            )
            return

    # --------------------------------------------------------------------------
    # JOIN CHECK FOR NORMAL BUTTONS
    # --------------------------------------------------------------------------

    if not await joined(
        context.bot,
        uid
    ):
        await query.answer(
            "❌ আগে Channel-এ Join করুন!",
            show_alert=True
        )
        return

    await query.answer()

    row = get_user(uid)

    if row is None:
        ensure_user(uid)
        row = get_user(uid)

    coins, refs, last_spin = row

    # --------------------------------------------------------------------------
    # COINS
    # --------------------------------------------------------------------------

    if query.data == "coins":

        await query.edit_message_text(
            "👤 *MY ACCOUNT*\n\n"
            f"🪙 *Coins:* `{coins}`\n"
            f"👥 *Referrals:* `{refs}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
        )

    # --------------------------------------------------------------------------
    # REFERRAL
    # --------------------------------------------------------------------------

    elif query.data == "ref":

        me = await context.bot.get_me()

        link = (
            f"https://t.me/"
            f"{me.username}"
            f"?start={uid}"
        )

        await query.edit_message_text(
            "🎁 *REFERRAL*\n\n"
            "👉 প্রতি Valid Referral = 🪙 5 Coin\n\n"
            f"🔗 `{link}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
        )

    # --------------------------------------------------------------------------
    # DAILY SPIN
    # --------------------------------------------------------------------------

    elif query.data == "spin":

        today = date.today().isoformat()

        if last_spin == today:
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
                today,
                uid,
            ),
        )

        conn.commit()

        await query.edit_message_text(
            "🎯 *DAILY SPIN*\n\n"
            f"🎉 আপনি `{reward}` Coin পেয়েছেন!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
        )

    # --------------------------------------------------------------------------
    # FREE PANELS
    # --------------------------------------------------------------------------

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

        if rows:

            lines = []

            for pid, name, value in rows:
                lines.append(
                    f"• #{pid} [{name}]({value})"
                )

            text = (
                "🎁 *FREE PANELS*\n\n"
                + "\n".join(lines)
            )

        else:

            text = (
                "🎁 *FREE PANELS*\n\n"
                "এখনো কোনো Free Panel দেওয়া হয়নি।"
            )

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
            disable_web_page_preview=True,
        )

    # --------------------------------------------------------------------------
    # PAID PANEL
    # --------------------------------------------------------------------------

    elif query.data == "paid":

        if refs < 5 and coins < 100:
            await query.answer(
                "⚠️ Paid Panel পেতে 5 Referral অথবা 100 Coin লাগবে!",
                show_alert=True
            )
            return

        row = conn.execute(
            """
            SELECT name, value
            FROM panels
            WHERE kind = 'paid'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        if not row:

            await query.edit_message_text(
                "💎 *PAID PANEL*\n\n"
                "এখনো কোনো Paid Panel upload করা হয়নি।",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=menu(),
            )

            return

        name, value = row

        await query.edit_message_text(
            "💎 *PAID PANEL*\n\n"
            f"[{name}]({value})",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
            disable_web_page_preview=True,
        )

    # --------------------------------------------------------------------------
    # ADMIN STATS
    # --------------------------------------------------------------------------

    elif query.data == "astats":

        users = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        panels = conn.execute(
            "SELECT COUNT(*) FROM panels"
        ).fetchone()[0]

        coins_total = conn.execute(
            """
            SELECT COALESCE(SUM(coins), 0)
            FROM users
            """
        ).fetchone()[0]

        refs_total = conn.execute(
            """
            SELECT COALESCE(SUM(referrals), 0)
            FROM users
            """
        ).fetchone()[0]

        await query.edit_message_text(
            "📊 *BOT STATS*\n\n"
            f"👤 *Users:* `{users}`\n"
            f"📜 *Panels:* `{panels}`\n"
            f"🪙 *Total Coins:* `{coins_total}`\n"
            f"👥 *Total Referrals:* `{refs_total}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_menu(),
        )

    # --------------------------------------------------------------------------
    # ADMIN PANEL LIST
    # --------------------------------------------------------------------------

    elif query.data == "alist":

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

            for pid, name, kind in rows:
                lines.append(
                    f"#{pid} | {name} | {kind}"
                )

            text = (
                "📜 *PANELS*\n\n"
                + "\n".join(lines)
            )

        else:

            text = (
                "📜 *PANELS*\n\n"
                "কোনো Panel নেই।"
            )

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_menu(),
        )


# ==============================================================================
# ERROR HANDLER
# ==============================================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    print(
        "BOT ERROR:",
        repr(context.error)
    )


# ==============================================================================
# APPLICATION
# ==============================================================================

def create_app():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

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
            admin_cmd
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
            callbacks
        )
    )

    app.add_error_handler(
        error_handler
    )

    return app


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":

    application = create_app()

    print("================================")
    print("        PANEL BOT STARTED       ")
    print("================================")
    print(f"Database: {DB}")
    print("Polling started...")

    application.run_polling(
        drop_pending_updates=True
    )
