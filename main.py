import os
import threading
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is running!"


def run():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


threading.Thread(target=run, daemon=True).start()
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, ConversationHandler, filters
)

# ----------------- কনফিগারেশন (আপনার তথ্য বসান) -----------------
BOT_TOKEN = "8803998786:AAETJSRZPzcu6aUI1q914TvA5jcNw3Mrw0A"  # BotFather এর টোকেন বসান
ADMIN_ID = 7792142088             # আপনার Telegram User ID (Number) বসান

BKASH_NUMBER = "01766872406"
NAGAD_NUMBER = "01821826206"
ROCKET_NUMBER = "01766872406"
MIN_DEPOSIT = 20.0  # সর্বনিম্ন ডিপোজিট টাকা

config = {
    "support_user": "@YourTelegramUsername"
}

mail_stock = ["test_meta1@gmail.com:pass1", "test_meta2@gmail.com:pass2"]  # আপনার Meta AI ID এর স্টক
DB_FILE = "bot_database.db"

# ----------------- ডাটাবেজ ফাংশন (SQLite Database) -----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0
        )
    ''')
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return 0.0

def update_balance(user_id, new_balance):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, balance) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET balance = ?
    ''', (user_id, new_balance, new_balance))
    conn.commit()
    conn.close()

def get_total_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ডাটাবেজ ইনিশিয়ালাইজেশন
init_db()

# Conversation states for Deposit
METHOD, AMOUNT, PROOF = range(3)

logging.basicConfig(level=logging.INFO)

# ----------------- কিবোর্ড লেআউট -----------------
def get_main_keyboard(is_admin=False):
    keyboard = [
        [KeyboardButton("💲 Buy Product")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🏦 Deposit")],
        [KeyboardButton("💬 Support")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ----------------- সাধারণ কমান্ড ও মেসেজ -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # ইউজার না থাকলে ডাটাবেজে ০.০ ব্যালেন্স সেট হবে
    if get_balance(user_id) == 0.0:
        update_balance(user_id, get_balance(user_id))

    is_admin = (user_id == ADMIN_ID)
    await update.message.reply_text(
        "👋 **স্বাগতম Mail Selling Bot-এ!**\nনিচের মেনু থেকে আপনার কাঙ্ক্ষিত অপশন সিলেক্ট করুন।",
        reply_markup=get_main_keyboard(is_admin),
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    user_id = user.id
    balance = get_balance(user_id)

    if text == "👤 Profile":
        msg = (
            f"👤 **আমার প্রোফাইল**\n\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"👤 **নাম:** {user.first_name}\n"
            f"💰 **ব্যালেন্স:** {balance:.2f} TK"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "💲 Buy Product":
        context.user_data['qty'] = 1  # ডিফল্ট পরিমাণ ১
        price = 0.80                  # Meta AI ID এর দাম
        stock = len(mail_stock)
        qty = context.user_data['qty']
        total = price * qty

        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data="qty_dec"),
                InlineKeyboardButton(f"{qty}", callback_data="qty_val"),
                InlineKeyboardButton("➕", callback_data="qty_inc")
            ],
            [
                InlineKeyboardButton("Confirm Order", callback_data="confirm_meta_ai"),
                InlineKeyboardButton("Cancel", callback_data="cancel_meta_ai")
            ]
        ]
        text_msg = (
            f"💲 **Meta AI ID**\n"
            f"💰 **প্রাইস:** {price:.2f} TK\n"
            f"📦 **স্টক:** {stock}\n\n"
            f"পরিমাণ: {qty}\n"
            f"মোট খরচ: {total:.2f} TK"
        )
        await update.message.reply_text(text_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif text == "💬 Support":
        await update.message.reply_text(f"💬 সহায়তার জন্য যোগাযোগ করুন: {config['support_user']}")

    elif text == "⚙️ Admin Panel" and user_id == ADMIN_ID:
        await admin_panel_cmd(update, context)

# ----------------- Meta AI ID কেনাকাটা ও কোয়ান্টিটি হ্যান্ডলার -----------------
async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    price = 0.80
    stock = len(mail_stock)

    # ১. কোয়ান্টিটি বাড়ান (+)
    if data == "qty_inc":
        context.user_data['qty'] = context.user_data.get('qty', 1) + 1
        qty = context.user_data['qty']
        total = price * qty

        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data="qty_dec"),
                InlineKeyboardButton(f"{qty}", callback_data="qty_val"),
                InlineKeyboardButton("➕", callback_data="qty_inc")
            ],
            [
                InlineKeyboardButton("Confirm Order", callback_data="confirm_meta_ai"),
                InlineKeyboardButton("Cancel", callback_data="cancel_meta_ai")
            ]
        ]
        text_msg = (
            f"💲 **Meta AI ID**\n"
            f"💰 **প্রাইস:** {price:.2f} TK\n"
            f"📦 **স্টক:** {stock}\n\n"
            f"পরিমাণ: {qty}\n"
            f"মোট খরচ: {total:.2f} TK"
        )
        await query.edit_message_text(text_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # ২. কোয়ান্টিটি কমান (-)
    elif data == "qty_dec":
        if context.user_data.get('qty', 1) > 1:
            context.user_data['qty'] -= 1
        qty = context.user_data['qty']
        total = price * qty

        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data="qty_dec"),
                InlineKeyboardButton(f"{qty}", callback_data="qty_val"),
                InlineKeyboardButton("➕", callback_data="qty_inc")
            ],
            [
                InlineKeyboardButton("Confirm Order", callback_data="confirm_meta_ai"),
                InlineKeyboardButton("Cancel", callback_data="cancel_meta_ai")
            ]
        ]
        text_msg = (
            f"💲 **Meta AI ID**\n"
            f"💰 **প্রাইস:** {price:.2f} TK\n"
            f"📦 **স্টক:** {stock}\n\n"
            f"পরিমাণ: {qty}\n"
            f"মোট খরচ: {total:.2f} TK"
        )
        await query.edit_message_text(text_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # ৩. অর্ডার কনফার্ম করা
    elif data == "confirm_meta_ai":
        qty = context.user_data.get('qty', 1)
        total_cost = price * qty
        balance = get_balance(user_id)

        if len(mail_stock) < qty:
            await query.edit_message_text("❌ **দুঃখিত! পর্যাপ্ত স্টক নেই।**", parse_mode="Markdown")
        elif balance < total_cost:
            await query.edit_message_text(
                f"❌ **অপর্যাপ্ত ব্যালেন্স!**\n\nমোট খরচ: {total_cost:.2f} TK\nআপনার ব্যালেন্স: {balance:.2f} TK\nআগে **Deposit** করুন।",
                parse_mode="Markdown"
            )
        else:
            purchased = []
            for _ in range(qty):
                purchased.append(mail_stock.pop(0))
            
            # ব্যালেন্স ডাটাবেজে আপডেট
            new_balance = balance - total_cost
            update_balance(user_id, new_balance)

            items_text = "\n".join([f"`{item}`" for item in purchased])
            await query.edit_message_text(
                f"✅ **অর্ডার সফল হয়েছে!**\n\n📧 **আপনার Meta AI ID:**\n{items_text}\n\nঅবশিষ্ট ব্যালেন্স: {new_balance:.2f} TK",
                parse_mode="Markdown"
            )

    # ৪. ক্যানসেল করা
    elif data == "cancel_meta_ai":
        await query.edit_message_text("❌ অর্ডার বাতিল করা হয়েছে।")

# ----------------- ডিপোজিট প্রসেস (Deposit Flow) -----------------
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("bKash", callback_data="dep_bkash"), InlineKeyboardButton("Nagad", callback_data="dep_nagad")],
        [InlineKeyboardButton("Rocket", callback_data="dep_rocket")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = (
        f"🏦 **ডিপোজিট করার নিয়ম:**\n\n"
        f"সর্বনিম্ন ডিপোজিট: **{MIN_DEPOSIT} TK**\n\n"
        f"পেমেন্ট মেথড সিলেক্ট করুন:"
    )
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
    return METHOD

async def deposit_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.split("_")[1]
    context.user_data['dep_method'] = method

    num = BKASH_NUMBER if method == "bkash" else (NAGAD_NUMBER if method == "nagad" else ROCKET_NUMBER)

    await query.message.reply_text(
        f"নিচে দেওয়া **{method.upper()}** নম্বরে Send Money করুন:\n\n"
        f"📱 **নম্বর:** `{num}`\n\n"
        f"টাকা পাঠানোর পর আপনি **কত টাকা পাঠিয়েছেন** তা লিখে নিচে মেসেজ দিন (সর্বনিম্ন {MIN_DEPOSIT} TK):",
        parse_mode="Markdown"
    )
    return AMOUNT

async def deposit_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount < MIN_DEPOSIT:
            await update.message.reply_text(f"❌ সর্বনিম্ন ডিপোজিট **{MIN_DEPOSIT} TK**। আবার সঠিক পরিমাণ লিখুন:")
            return AMOUNT

        context.user_data['dep_amount'] = amount
        await update.message.reply_text(
            "📷 এখন পেমেন্টের **স্ক্রিনশট (Photo)** অথবা **Transaction ID** লিখে পাঠান:"
        )
        return PROOF
    except ValueError:
        await update.message.reply_text("❌ পরিমাণটি নম্বরে লিখুন (যেমন: 50)।")
        return AMOUNT

async def deposit_proof_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    amount = context.user_data.get('dep_amount')
    method = context.user_data.get('dep_method')

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}_{amount}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    admin_msg = (
        f"📥 **নতুন ডিপোজিট রিকোয়েস্ট!**\n\n"
        f"👤 **ইউজার:** {user.first_name} (`{user.id}`)\n"
        f"💳 **মেথড:** {method.upper()}\n"
        f"💰 **পরিমাণ:** {amount} TK\n"
    )

    if update.message.photo:
        caption = admin_msg + f"📸 **প্রমাণ:** স্ক্রিনশট নিচে দেওয়া হলো।"
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        text_proof = update.message.text
        admin_msg += f"📝 **TrxID / নোট:** `{text_proof}`"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_msg,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    await update.message.reply_text(
        "✅ আপনার ডিপোজিট রিকোয়েস্ট এডমিনের কাছে পাঠানো হয়েছে। এডমিন চেক করে এপ্রুভ করলে ব্যালেন্স যোগ হয়ে যাবে।"
    )
    return ConversationHandler.END

async def cancel_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ ডিপোজিট প্রক্রিয়া বাতিল করা হয়েছে।")
    return ConversationHandler.END

# ----------------- এডমিন এপ্রুভাল হ্যান্ডলার -----------------
async def admin_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data.split("_")
    action = data[0]
    target_user_id = int(data[1])
    amount = float(data[2])

    if action == "app":
        current_bal = get_balance(target_user_id)
        new_bal = current_bal + amount
        update_balance(target_user_id, new_bal)  # ডাটাবেজে স্থায়ীভাবে সেভ

        if query.message.photo:
            await query.edit_message_caption(
                caption=query.message.caption + f"\n\n✅ **APPROVED by Admin!** (+{amount} TK)",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                text=query.message.text + f"\n\n✅ **APPROVED by Admin!** (+{amount} TK)",
                parse_mode="Markdown"
            )

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **আপনার {amount} TK ডিপোজিট এপ্রুভ করা হয়েছে!**\nনতুন ব্যালেন্স: {new_bal:.2f} TK",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif action == "rej":
        if query.message.photo:
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n❌ **REJECTED by Admin!**",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                text=query.message.text + "\n\n❌ **REJECTED by Admin!**",
                parse_mode="Markdown"
            )

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="❌ আপনার ডিপোজিট রিকোয়েস্টটি এডমিন বাতিল করেছেন। প্রয়োজনে সাপোর্টে কথা বলুন।"
            )
        except Exception:
            pass

# ----------------- এডমিন প্যানেল কমান্ডস -----------------
async def admin_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = (
        "⚙️ **ADMIN PANEL COMMANDS**\n\n"
        "📥 `/addstock email:pass` - স্টকে মেইল যোগ করুন\n"
        "💰 `/addbalance USER_ID AMOUNT` - কোনো ইউজারকে ডিরেক্ট টাকা দিন\n"
        "📊 `/adminstats` - কারেন্ট স্টক ও ইউজার সংখ্যা দেখুন"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.args:
        mail_data = " ".join(context.args)
        mail_stock.append(mail_data)
        await update.message.reply_text(f"✅ স্টকে Meta AI ID যোগ হয়েছে! বর্তমান মোট স্টক: {len(mail_stock)}")
    else:
        await update.message.reply_text("⚠️ নিয়ম: `/addstock email:password`", parse_mode="Markdown")

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        target_id = int(context.args[0])
        amount = float(context.args[1])
        
        current_bal = get_balance(target_id)
        new_bal = current_bal + amount
        update_balance(target_id, new_bal)  # ডাটাবেজে আপডেট
        
        await update.message.reply_text(f"✅ ইউজার `{target_id}`-কে {amount} TK এড করা হয়েছে। নতুন ব্যালেন্স: {new_bal:.2f} TK", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("⚠️ নিয়ম: `/addbalance USER_ID AMOUNT`", parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = (
        f"📊 **বটের বর্তমান অবস্থা:**\n\n"
        f"📦 **মোট Meta AI ID স্টক:** {len(mail_stock)} টি\n"
        f"👥 **মোট ডাটাবেজ ইউজার:** {get_total_users()} জন"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ----------------- প্রধান ফাইল প্রসেস -----------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    dep_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🏦 Deposit$'), deposit_start)],
        states={
            METHOD: [CallbackQueryHandler(deposit_method_selected, pattern="^dep_")],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount_received)],
            PROOF: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, deposit_proof_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel_deposit)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel_cmd))
    app.add_handler(CommandHandler("addstock", add_stock))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("adminstats", admin_stats))

    app.add_handler(dep_handler)
    
    # Meta AI ID কেনাকাটা প্রসেস হ্যান্ডলার
    app.add_handler(CallbackQueryHandler(shop_callback, pattern="^(qty_|confirm_|cancel_)"))
    
    # এডমিন এপ্রুভাল হ্যান্ডলার
    app.add_handler(CallbackQueryHandler(admin_approval_callback, pattern="^(app_|rej_)"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Broadcast command function
async def broadcast_command(update, context):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ ব্যবহার করার নিয়ম:\n`/broadcast আপনার বার্তা`", parse_mode="Markdown")
        return

    broadcast_text = " ".join(context.args)
    success_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text("📢 ব্রডকাস্ট পাঠানো শুরু হচ্ছে...")

    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 **ADMIN NOTICE** 📢\n\n{broadcast_text}", parse_mode="Markdown")
            success_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ **ব্রডকাস্ট সম্পন্ন হয়েছে!**\n\n"
        f"🎯 সফল: {success_count} জন\n"
        f"❌ ব্যর্থ/ব্লকড: {fail_count} জন",
        parse_mode="Markdown"
    )

app.add_handler(CommandHandler("broadcast", broadcast_command))

print("Bot is running with SQLite database...")
    app.run_polling()
