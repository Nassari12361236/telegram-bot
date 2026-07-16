#!/usr/bin/env python3
import os
import json
import asyncio
import logging
from datetime import datetime
from aiohttp import web
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))

CARD_NUMBER = "6219861861016524"
CARD_HOLDER = "نصاری روشن"
SHOP_NAME = "EasyNet | ایزی نت"

PLANS = [
    {"id": 1, "emoji": "🔥", "name": "۱۰۰ گیگ دو کاربره", "volume": "100 گیگابایت", "users": "۲ کاربره", "period": "۱ ماهه", "price": 199000},
    {"id": 2, "emoji": "⚡", "name": "۷۰ گیگ دو کاربره",  "volume": "70 گیگابایت",  "users": "۲ کاربره", "period": "۱ ماهه", "price": 139000},
    {"id": 3, "emoji": "💎", "name": "۵۰ گیگ سه کاربره",  "volume": "50 گیگابایت",  "users": "۳ کاربره", "period": "۱ ماهه", "price": 109000},
    {"id": 4, "emoji": "🌱", "name": "۲۰ گیگ تک کاربره",  "volume": "20 گیگابایت",  "users": "۱ کاربره", "period": "۱ ماهه", "price": 50000},
]

DB_FILE = "bot/orders.json"

# Conversation states
SELECTING_PLAN, WAITING_RECEIPT, SUPPORT_MSG = range(3)
BROADCAST_MSG = 10
SEND_SUB = 11


# ─── DB helpers ────────────────────────────────────────────────────────────────
def load_db():
    if not os.path.exists(DB_FILE):
        return {"orders": [], "next_id": 1, "users": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "users" not in data:
        data["users"] = {}
    return data

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def save_user(user):
    db = load_db()
    db["users"][str(user.id)] = {
        "id": user.id,
        "username": user.username or "—",
        "first_name": user.first_name or "—",
        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_db(db)

def get_all_users():
    db = load_db()
    return list(db["users"].values())

def add_order(user_id, username, plan_id, receipt_file_id):
    db = load_db()
    order = {
        "id": db["next_id"],
        "user_id": user_id,
        "username": username or "—",
        "plan_id": plan_id,
        "receipt": receipt_file_id,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    db["orders"].append(order)
    db["next_id"] += 1
    save_db(db)
    return order

def find_order(order_id):
    db = load_db()
    for o in db["orders"]:
        if o["id"] == order_id:
            return o
    return None

def update_order_status(order_id, status):
    db = load_db()
    for o in db["orders"]:
        if o["id"] == order_id:
            o["status"] = status
    save_db(db)


# ─── Keyboards ─────────────────────────────────────────────────────────────────
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📦 مشاهده پلن‌ها"), KeyboardButton("🛒 خرید اشتراک")],
            [KeyboardButton("🎫 پشتیبانی")],
        ],
        resize_keyboard=True,
    )

def plans_inline_keyboard():
    buttons = []
    for p in PLANS:
        price_fa = f"{p['price']:,}".replace(",", "،")
        buttons.append([InlineKeyboardButton(
            f"{p['emoji']} {p['name']} — {price_fa} تومان",
            callback_data=f"buy_{p['id']}"
        )])
    return InlineKeyboardMarkup(buttons)

def admin_order_keyboard(order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_{order_id}"),
        ]
    ])


# ─── Handlers ──────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"سلام *{name}* عزیز 👋\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🌐 *{SHOP_NAME}*\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"به فروشگاه اشتراک اینترنت ما خوش اومدی 🎉\n\n"
        f"⚡ سرعت بالا\n"
        f"💰 قیمت مناسب\n"
        f"🛡 پشتیبانی همیشگی\n\n"
        f"از منو زیر گزینه‌ات رو انتخاب کن 👇",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )

async def show_plans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    text = f"📦 *پلن‌های {SHOP_NAME}*\n\n"
    for p in PLANS:
        price_fa = f"{p['price']:,}".replace(",", "،")
        text += (
            f"{p['emoji']} *{p['name']}*\n"
            f"   • حجم: {p['volume']}\n"
            f"   • کاربر: {p['users']}\n"
            f"   • مدت: {p['period']}\n"
            f"   • قیمت: {price_fa} تومان\n\n"
        )
    text += "برای خرید روی دکمه «🛒 خرید اشتراک» بزن."
    await update.message.reply_text(text, parse_mode="Markdown")

async def buy_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    ctx.user_data.pop("selected_plan", None)
    await update.message.reply_text(
        "🛒 *خرید اشتراک*\n\nپلن مورد نظرت رو انتخاب کن:",
        parse_mode="Markdown",
        reply_markup=plans_inline_keyboard(),
    )
    return SELECTING_PLAN

async def plan_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[1])
    plan = next(p for p in PLANS if p["id"] == plan_id)
    ctx.user_data["selected_plan"] = plan_id

    price_fa = f"{plan['price']:,}".replace(",", "،")

    # Card number with copy hint
    card_display = f"`{CARD_NUMBER}`"

    await query.edit_message_text(
        f"✅ پلن *{plan['name']}* انتخاب شد.\n\n"
        f"💳 *مبلغ:* {price_fa} تومان\n\n"
        f"لطفاً مبلغ رو به کارت زیر واریز کن:\n\n"
        f"🏦 شماره کارت:\n{card_display}\n"
        f"👤 به نام: *{CARD_HOLDER}*\n\n"
        f"بعد از پرداخت، *تصویر رسید* رو برام بفرست 📸",
        parse_mode="Markdown",
    )
    return WAITING_RECEIPT

async def receipt_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    plan_id = ctx.user_data.get("selected_plan")
    if not plan_id:
        await update.message.reply_text("لطفاً دوباره از «🛒 خرید اشتراک» شروع کن.")
        return ConversationHandler.END

    plan = next(p for p in PLANS if p["id"] == plan_id)
    photo = update.message.photo
    if not photo:
        await update.message.reply_text("⚠️ لطفاً تصویر رسید رو بفرست (نه فایل).")
        return WAITING_RECEIPT

    file_id = photo[-1].file_id
    order = add_order(user.id, user.username, plan_id, file_id)

    await update.message.reply_text(
        f"✅ *رسید شما دریافت شد!*\n\n"
        f"📦 پلن: *{plan['name']}*\n\n"
        f"⏳ در حال بررسی توسط تیم پشتیبانی...\n"
        f"به زودی اشتراک‌تون ارسال می‌شه 🙏",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )

    # Notify admin
    if ADMIN_ID:
        price_fa = f"{plan['price']:,}".replace(",", "،")
        caption = (
            f"🛎 *سفارش جدید — #{order['id']}*\n\n"
            f"👤 کاربر: @{user.username or '—'} (ID: {user.id})\n"
            f"📦 پلن: {plan['name']}\n"
            f"💰 مبلغ: {price_fa} تومان\n"
            f"🕐 زمان: {order['created_at']}"
        )
        await ctx.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=admin_order_keyboard(order["id"]),
        )

    return ConversationHandler.END

async def admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, order_id_str = query.data.split("_", 1)
    order_id = int(order_id_str)
    order = find_order(order_id)
    if not order:
        await query.edit_message_caption("⚠️ سفارش پیدا نشد.")
        return

    if action == "approve":
        update_order_status(order_id, "approved")
        await query.edit_message_caption(
            query.message.caption + "\n\n✅ *تایید شد — منتظر ارسال اشتراک*",
            parse_mode="Markdown",
        )
        # Store pending delivery in admin's user_data
        ctx.user_data["pending_sub_order"] = order_id
        plan = next(p for p in PLANS if p["id"] == order["plan_id"])
        await ctx.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📤 *حالا اشتراک مشتری رو بفرست*\n\n"
                f"👤 کاربر: @{order['username']}\n"
                f"📦 پلن: *{plan['name']}*\n\n"
                f"متن، لینک یا کانفیگ رو همینجا بفرست تا مستقیم به مشتری برسه 👇"
            ),
            parse_mode="Markdown",
        )
    elif action == "reject":
        update_order_status(order_id, "rejected")
        await query.edit_message_caption(
            query.message.caption + "\n\n❌ *رد شد*",
            parse_mode="Markdown",
        )
        plan = next(p for p in PLANS if p["id"] == order["plan_id"])
        await ctx.bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"⚠️ *پرداخت شما تأیید نشد*\n\n"
                f"📦 پلن: *{plan['name']}*\n\n"
                f"اگه مشکلی داری از بخش پشتیبانی پیام بده 🎫"
            ),
            parse_mode="Markdown",
        )

async def admin_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("هنوز کاربری ثبت نشده.")
        return
    text = f"👥 *کاربران ربات — {len(users)} نفر*\n\n"
    for u in users:
        uname = f"@{u['username']}" if u['username'] != "—" else "—"
        text += f"• {u['first_name']} | {uname} | `{u['id']}`\n  آخرین بازدید: {u['last_seen']}\n\n"
    # Split if too long
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def admin_send_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin sends subscription details after approving an order."""
    if update.effective_user.id != ADMIN_ID:
        return
    order_id = ctx.user_data.get("pending_sub_order")
    if not order_id:
        return
    order = find_order(order_id)
    if not order:
        return
    plan = next(p for p in PLANS if p["id"] == order["plan_id"])
    sub_text = update.message.text or ""
    caption = (
        f"🎉 *اشتراک شما آماده‌ست!*\n\n"
        f"📦 پلن: *{plan['name']}*\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"{sub_text}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"ممنون از خریدت 🙏\n"
        f"مشکلی بود از پشتیبانی بپرس 🎫"
    )
    # Try to send with bot's profile photo
    try:
        bot_photos = await ctx.bot.get_user_profile_photos(ctx.bot.id, limit=1)
        if bot_photos.total_count > 0:
            photo_file_id = bot_photos.photos[0][-1].file_id
            await ctx.bot.send_photo(
                chat_id=order["user_id"],
                photo=photo_file_id,
                caption=caption,
                parse_mode="Markdown",
            )
        else:
            await ctx.bot.send_message(
                chat_id=order["user_id"],
                text=caption,
                parse_mode="Markdown",
            )
    except Exception:
        await ctx.bot.send_message(
            chat_id=order["user_id"],
            text=caption,
            parse_mode="Markdown",
        )
    ctx.user_data.pop("pending_sub_order", None)
    await update.message.reply_text("✅ اشتراک برای مشتری ارسال شد!")

async def broadcast_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = get_all_users()
    await update.message.reply_text(
        f"📣 *ارسال پیام انبوه*\n\n"
        f"تعداد کاربران: *{len(users)} نفر*\n\n"
        f"پیامت رو بنویس تا برای همه ارسال بشه.\n"
        f"برای لغو /cancel بزن.",
        parse_mode="Markdown",
    )
    return BROADCAST_MSG

async def broadcast_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    msg = update.message.text
    users = get_all_users()
    sent, failed = 0, 0
    for u in users:
        try:
            await ctx.bot.send_message(chat_id=u["id"], text=f"📣 *پیام از {SHOP_NAME}*\n\n{msg}", parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ پیام ارسال شد!\n\n"
        f"• موفق: {sent} نفر\n"
        f"• ناموفق: {failed} نفر",
    )
    return ConversationHandler.END

async def support_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    await update.message.reply_text(
        "🎫 *پشتیبانی*\n\n"
        "پیامت رو بنویس، اولین فرصت جواب می‌دیم 👇\n\n"
        "برای لغو /cancel بزن.",
        parse_mode="Markdown",
    )
    return SUPPORT_MSG

async def support_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message.text

    await update.message.reply_text(
        "✅ پیامت ثبت شد! به زودی پاسخ می‌دیم. 🙏",
        reply_markup=main_menu_keyboard(),
    )

    if ADMIN_ID:
        await ctx.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🎫 *تیکت جدید*\n\n"
                f"👤 @{user.username or '—'} (ID: {user.id})\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"💬 {msg}"
            ),
            parse_mode="Markdown",
        )
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لغو شد.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "از منو پایین گزینه انتخاب کن 👇",
        reply_markup=main_menu_keyboard(),
    )


# ─── Ping server (keeps bot alive via UptimeRobot) ─────────────────────────────
async def run_ping_server():
    async def handle(request):
        return web.Response(text="✅ EasyNet Bot is alive!")

    server = web.Application()
    server.router.add_get("/", handle)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", os.environ.get("PING_PORT", 3000)))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Ping server روی پورت {port} فعاله")
    await asyncio.Event().wait()


# ─── Main ──────────────────────────────────────────────────────────────────────
async def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده!")

    app = Application.builder().token(BOT_TOKEN).build()

    buy_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛒 خرید اشتراک$"), buy_start)],
        states={
            SELECTING_PLAN: [CallbackQueryHandler(plan_selected, pattern=r"^buy_\d+$")],
            WAITING_RECEIPT: [MessageHandler(filters.PHOTO, receipt_received)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🛒 خرید اشتراک$"), buy_start),
            CommandHandler("cancel", cancel),
        ],
    )

    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎫 پشتیبانی$"), support_start)],
        states={
            SUPPORT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(MessageHandler(filters.Regex("^📦 مشاهده پلن‌ها$"), show_plans))
    app.add_handler(buy_conv)
    app.add_handler(support_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^(approve|reject)_\d+$"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID),
        admin_send_sub,
    ), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    logger.info(f"✅ ربات {SHOP_NAME} شروع به کار کرد...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()


async def main():
    await asyncio.gather(run_bot(), run_ping_server())

if __name__ == "__main__":
    asyncio.run(main())
