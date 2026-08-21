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

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003087197996"))
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/u20fgDLKHLHnZjV1")

ADMIN_IDS = [
    8040845647,
    8296972506,
    6905592655,
]

DB = Path("/tmp/panel_bot.db")

conn = sqlite3.connect(DB, check_same_thread=False)
conn.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    coins INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    last_spin TEXT
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS referrals(
    new_user INTEGER PRIMARY KEY,
    referrer INTEGER
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS panels(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    kind TEXT,
    value TEXT
)
""")
conn.commit()

WHEEL = [1, 0, 3, 0, 5, 0, 1, 0]

# ==============================================================================
# DATABASE HELPERS
# ==============================================================================

def ensure_user(uid: int, username: str = ""):
    conn.execute("""
    INSERT OR IGNORE INTO users(user_id, username) VALUES(?, ?)
    """, (uid, username or ""))
    conn.execute("""
    UPDATE users SET username=? WHERE user_id=?
    """, (username or "", uid))
    conn.commit()

def add_panel(name: str, kind: str, value: str):
    conn.execute("""
    INSERT INTO panels(name, kind, value) VALUES(?, ?, ?)
    """, (name, kind, value))
    conn.commit()

# ==============================================================================
# UI
# ==============================================================================

def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Daily Spin", callback_data="spin"),
            InlineKeyboardButton("🪙 My Coins", callback_data="coins"),
        ],
        [
            InlineKeyboardButton("👥 Referral", callback_data="ref"),
            InlineKeyboardButton("💎 Paid Panel", callback_data="paid"),
        ],
        [
            InlineKeyboardButton("🎁 Free Panel", callback_data="free"),
        ],
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats", callback_data="astats"),
            InlineKeyboardButton("📜 Panels", callback_data="alist"),
        ],
    ])

async def joined(bot, uid: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

async def send_join_message(message):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("🔍 Check Join", callback_data="check")],
    ])
    await message.reply_text(
        "✨WELCOME!✨\n\n"
        "👉 আমাদের Channel-এ Join করুন।\n"
        "তারপর 'Check Join' চাপুন।",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )

async def send_main_menu(target, edit=False):
    text = (
        "✨ *PANEL BOT* ✨\n\n"
        "🪙 Coin • 👥 Referral • 🎯 Daily Spin\n"
        "💎 Paid Panel • 🎁 Free Panel"
    )
    if edit:
        await target.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=menu())
    else:
        await target.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=menu())

# ==============================================================================
# COMMANDS
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username)

    if context.args and context.args[0].isdigit():
        ref = int(context.args[0])
        if ref != user.id:
            already = conn.execute("SELECT 1 FROM referrals WHERE new_user=?", (user.id,)).fetchone()
            if already is None:
                ensure_user(ref)
                conn.execute("INSERT INTO referrals(new_user, referrer) VALUES(?, ?)", (user.id, ref))
                conn.execute("UPDATE users SET referrals=referrals+1, coins=coins+5 WHERE user_id=?", (ref,))
                conn.commit()

    if not await joined(context.bot, user.id):
        await send_join_message(update.message)
        return

    await send_main_menu(update.message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📍 *HELP*\n\n"
        "/start - Start bot\n"
        "/admin - Admin panel (admins only)\n"
        "/stats - Admin statistics\n\n"
        "Channel join verification is required.",
        parse_mode=ParseMode.MARKDOWN,
    )

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return
    await update.message.reply_text("👑 *ADMIN PANEL*", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return

    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    panels = conn.execute("SELECT COUNT(*) FROM panels").fetchone()[0]
    coins = conn.execute("SELECT COALESCE(SUM(coins), 0) FROM users").fetchone()[0]
    refs = conn.execute("SELECT COALESCE(SUM(referrals), 0) FROM users").fetchone()[0]

    text = (
        "📊 *BOT STATS*\n"
        f"👤 *Users:* `{users}`\n"
        f"📜 *Panels:* `{panels}`\n"
        f"🪙 *Total Coins:* `{coins}`\n"
        f"👥 *Total Referrals:* `{refs}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def addfree_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return

    raw = " ".join(context.args).strip()
    if "|" not in raw:
        await update.message.reply_text("⚠️ ব্যবহার: /addfree Panel Name|https://example.com/panel")
        return

    name, value = raw.split("|", 1)
    name, value = name.strip(), value.strip()

    if not name or not value:
        await update.message.reply_text("⚠️ Name এবং Value প্রদান করুন।")
        return

    add_panel(name, "free", value)
    await update.message.reply_text(f"✅ Free Panel added: *{name}*", parse_mode=ParseMode.MARKDOWN)

async def addpaid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return

    raw = " ".join(context.args).strip()
    if "|" not in raw:
        await update.message.reply_text("⚠️ ব্যবহার: /addpaid VIP Panel|https://example.com/panel")
        return

    name, value = raw.split("|", 1)
    name, value = name.strip(), value.strip()

    if not name or not value:
        await update.message.reply_text("⚠️ Name এবং Value প্রদান করুন।")
        return

    add_panel(name, "paid", value)
    await update.message.reply_text(f"✅ Paid Panel added: *{name}*", parse_mode=ParseMode.MARKDOWN)

async def delpanel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ ব্যবহার: /delpanel Panel_ID")
        return

    panel_id = int(context.args[0])
    cur = conn.execute("DELETE FROM panels WHERE id=?", (panel_id,))
    conn.commit()

    if cur.rowcount:
        await update.message.reply_text(f"🗑️ Panel #{panel_id} মুছে ফেলা হয়েছে।")
    else:
        await update.message.reply_text("❌ আইডি পাওয়া যায়নি।")

# ==============================================================================
# CALLBACKS
# ==============================================================================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id

    ensure_user(uid, query.from_user.username)

    if query.data == "check":
        if await joined(context.bot, uid):
            await query.answer("✅ Join verified!")
            await send_main_menu(query, edit=True)
        else:
            await query.answer("❌ আপনি এখনো Channel-এ Join হননি!", show_alert=True)
        return

    if not await joined(context.bot, uid):
        await query.answer("❌ আগে Channel-এ Join করুন!", show_alert=True)
        return

    await query.answer()

    row = conn.execute("SELECT coins, referrals, last_spin FROM users WHERE user_id=?", (uid,)).fetchone()
    coins, refs, last_spin = row

    if query.data == "coins":
        await query.edit_message_text(
            f"👤 *MY ACCOUNT*\n\n🪙 *Coins:* `{coins}`\n👥 *Referrals:* `{refs}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
        )

    elif query.data == "ref":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start={uid}"
        await query.edit_message_text(
            f"🎁 *REFERRAL*\n\n👉 Valid referral = 🪙 5 Coin\n🔗 *Link:* `{link}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
        )

    elif query.data == "spin":
        if last_spin == date.today().isoformat():
            await query.answer("⏱️আজকের স্পিন নেওয়া হয়ে গেছে।", show_alert=True)
            return

        reward = random.choice(WHEEL)
        conn.execute("UPDATE users SET coins=coins+?, last_spin=? WHERE user_id=?", (reward, date.today().isoformat(), uid))
        conn.commit()

        await query.edit_message_text(
            f"🎯 *DAILY SPIN*\n\n🎉 আপনি {reward} Coin পেয়েছেন!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu(),
        )

    elif query.data == "free":
        rows = conn.execute("SELECT id, name, value FROM panels WHERE kind='free' ORDER BY id DESC LIMIT 10").fetchall()
        if rows:
            lines = [f"• #{pid} [{name}]({value})" for pid, name, value in rows]
            text = "🎁 *FREE PANELS*\n\n" + "\n".join(lines)
        else:
            text = "🎁 *FREE PANELS*\n\nএখনো কোনো Free Panel দেওয়া হয়নি।"

        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=menu(), disable_web_page_preview=True)

    elif query.data == "paid":
        if refs < 5 and coins < 100:
            await query.answer("⚠️ Paid Panel পেতে 5 Referral অথবা 100 Coin লাগবে!", show_alert=True)
            return

        row = conn.execute("SELECT name, value FROM panels WHERE kind='paid' ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            await query.edit_message_text("💎 *PAID PANEL*\n\nএখনো কোনো Paid Panel upload করা হয়নি।", reply_markup=menu())
            return

        await query.edit_message_text(f"💎 *PAID PANEL*\n\n[{row[0]}]({row[1]})", parse_mode=ParseMode.MARKDOWN, reply_markup=menu(), disable_web_page_preview=True)

    elif query.data == "astats":
        if uid not in ADMIN_IDS:
            await query.answer("⛔ Admin only.", show_alert=True)
            return

        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        panels = conn.execute("SELECT COUNT(*) FROM panels").fetchone()[0]
        coins_total = conn.execute("SELECT COALESCE(SUM(coins), 0) FROM users").fetchone()[0]
        refs_total = conn.execute("SELECT COALESCE(SUM(referrals), 0) FROM users").fetchone()[0]

        await query.edit_message_text(
            f"📊 *BOT STATS*\n\n👤 *Users:* `{users}`\n📜 *Panels:* `{panels}`\n🪙 *Total Coins:* `{coins_total}`\n👥 *Total Referrals:* `{refs_total}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_menu(),
        )

    elif query.data == "alist":
        if uid not in ADMIN_IDS:
            await query.answer("⛔ Admin only.", show_alert=True)
            return

        rows = conn.execute("SELECT id, name, kind FROM panels ORDER BY id DESC LIMIT 30").fetchall()
        if rows:
            lines = [f"#{pid} | {name} | {kind}" for pid, name, kind in rows]
            text = "📜 *PANELS*\n\n" + "\n".join(lines)
        else:
            text = "📜 *PANELS*\n\nকোনো panel নেই।"

        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())

# ==============================================================================
# APPLICATION BUILDER
# ==============================================================================

def create_app():
    token = BOT_TOKEN if BOT_TOKEN else "DUMMY_TOKEN"
    app_builder = Application.builder().token(token)
    app_builder.add_handler(CommandHandler("start", start))
    app_builder.add_handler(CommandHandler("help", help_command))
    app_builder.add_handler(CommandHandler("admin", admin_cmd))
    app_builder.add_handler(CommandHandler("stats", stats_command))
    app_builder.add_handler(CommandHandler("addfree", addfree_command))
    app_builder.add_handler(CommandHandler("addpaid", addpaid_command))
    app_builder.add_handler(CommandHandler("delpanel", delpanel_command))
    app_builder.add_handler(CallbackQueryHandler(callbacks))
    return app_builder.build()

if __name__ == "__main__":
    app = create_app()
    app.run_polling()
