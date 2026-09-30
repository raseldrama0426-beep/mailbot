import os
import threading
import logging
import sqlite3
import requests
import re
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

# ----------------- Flask Server for Keeping Alive -----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ----------------- Configuration Settings -----------------
BOT_TOKEN = "8803998786:AAHnmue-EM-uLp09jlXwrCxj_bUrqv6mw54"  # Apnar Bot Token
ADMIN_ID = 8967812900                                      # Admin ID

# Payment Numbers
BKASH_NUMBER = "01766872406"
NAGAD_NUMBER = "01821826206"
ROCKET_NUMBER = "01766872406"

MIN_DEPOSIT = 20.0
DB_FILE = os.path.join(os.getcwd(), "bot_database.db")

# Bot Main Data
mail_stock = ["kelli.731@piepla.com:rasel24", "michal@piepla.com:rasel24"]
support_user = "@PremiumStoreBD_Support"  # Support ID
unit_price = 0.80  # Per Mail Price

# Conversation States
METHOD, AMOUNT, PROOF = range(3)

logging.basicConfig(level=logging.INFO)

# ----------------- Database Setup -----------------
def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    res = c.fetchone() if fetchone else (c.fetchall() if fetchall else None)
    if commit: 
        conn.commit()
    conn.close()
    return res

db_query("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)", commit=True)

def get_bal(uid):
    r = db_query("SELECT balance FROM users WHERE user_id = ?", (uid,), fetchone=True)
    return r[0] if r else 0.0

def set_bal(uid, bal):
    db_query("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = ?", (uid, bal, bal), commit=True)

def get_all_users():
    rows = db_query("SELECT user_id FROM users", fetchall=True)
    return [r[0] for r in rows] if rows else []

# ----------------- Keyboards -----------------
def get_kbd(is_admin):
    kbd = [
        [KeyboardButton("💲 প্রডাক্ট কিনুন")],
        [KeyboardButton("👤 প্রোফাইল"), KeyboardButton("🏦 ডিপোজিট")],
        [KeyboardButton("💬 সাপোর্ট")]
    ]
    if is_admin:
        kbd.append([KeyboardButton("⚙️ এডমিন প্যানেল")])
    return ReplyKeyboardMarkup(kbd, resize_keyboard=True)

MENU_REGEX = r'(প্রোফাইল|Profile|প্রডাক্ট কিনুন|Buy Product|সাপোর্ট|Support|এডমিন প্যানেল|Admin Panel|ডিপোজিট|Deposit)'

# ----------------- Core Commands -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if get_bal(uid) == 0.0:
        set_bal(uid, 0.0)
    
    msg = (
        "👋 **স্বাগতম আমাদের প্রিমিয়াম স্টোরে!**\n\n"
        "আপনার প্রয়োজনীয় সেবা পেতে নিচের মেনু থেকে অপশন সিলেক্ট করুন:"
    )
    await update.message.reply_text(msg, reply_markup=get_kbd(uid == ADMIN_ID), parse_mode="Markdown")

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    bal = get_bal(uid)
    profile_msg = (
        "👤 **আপনার প্রোফাইল বিবরণী**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 **ইউজার আইডি:** `{uid}`\n"
        f"📛 **নাম:** {user.first_name}\n"
        f"💰 **বর্তমান ব্যালেন্স:** `{bal:.2f}` টাকা"
    )
    await update.message.reply_text(profile_msg, parse_mode="Markdown")

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💬 **আমাদের সাপোর্ট টিম:** {support_user}\n\nযেকোনো সহায়তার জন্য মেসেজ দিন।", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    uid = user.id
    
    if context.user_data.get('waiting_qty'):
        if re.search(MENU_REGEX, text, re.IGNORECASE):
            context.user_data['waiting_qty'] = False
        elif text.isdigit() and int(text) > 0:
            context.user_data['qty'] = int(text)
            context.user_data['waiting_qty'] = False
            await send_shop_menu(update.message, context, is_edit=False)
            return
        else:
            await update.message.reply_text("⚠️ অনুগ্রহ করে সঠিক একটি সংখ্যা লিখুন:")
            return

    if "প্রোফাইল" in text or "profile" in text.lower():
        await show_profile(update, context)
    elif "প্রডাক্ট কিনুন" in text or "buy product" in text.lower():
        if not mail_stock:
            await update.message.reply_text("❌ দুঃখিত! বর্তমানে স্টকে কোনো মেইল নেই।")
            return
        context.user_data['qty'] = 1
        await send_shop_menu(update.message, context, is_edit=False)
    elif "সাপোর্ট" in text or "support" in text.lower():
        await show_support(update, context)
    elif ("এডমিন প্যানেল" in text or "admin panel" in text.lower()) and uid == ADMIN_ID:
        await admin_panel(update, context)

# ----------------- Shop / Buy System -----------------
async def send_shop_menu(msg_obj, context, is_edit=True):
    qty = context.user_data.get('qty', 1)
    stock = len(mail_stock)
    total = unit_price * qty
    
    kbd = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖", callback_data="qty_dec"),
            InlineKeyboardButton(f"📦 {qty} টি", callback_data="qty_val"),
            InlineKeyboardButton("➕", callback_data="qty_inc")
        ],
        [InlineKeyboardButton("✏️ কাস্টম পরিমাণ লিখুন", callback_data="qty_custom")],
        [
            InlineKeyboardButton("✅ অর্ডার নিশ্চিত করুন", callback_data="confirm_buy"),
            InlineKeyboardButton("❌ বাতিল", callback_data="cancel_buy")
        ]
    ])
    
    txt = (
        "🌟 **Meta AI ID (স্টোর পণ্য)**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💎 **একক মূল্য:** {unit_price:.2f} টাকা\n"
        f"📦 **মোট স্টক আছে:** {stock} টি\n"
        f"📊 **নির্বাচিত পরিমাণ:** {qty} টি\n"
        f"💰 **মোট দেয় মূল্য:** {total:.2f} টাকা"
    )
    if is_edit:
        await msg_obj.edit_message_text(txt, reply_markup=kbd, parse_mode="Markdown")
    else:
        await msg_obj.reply_text(txt, reply_markup=kbd, parse_mode="Markdown")

async def shop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    
    if data == "qty_inc":
        context.user_data['qty'] = context.user_data.get('qty', 1) + 1
        await send_shop_menu(query, context, is_edit=True)
    elif data == "qty_dec":
        if context.user_data.get('qty', 1) > 1:
            context.user_data['qty'] -= 1
        await send_shop_menu(query, context, is_edit=True)
    elif data == "qty_custom":
        context.user_data['waiting_qty'] = True
        await query.message.reply_text("✏️ আপনি কতটি কিনতে চান? সংখ্যাটি লিখে দিন:")
    elif data == "confirm_buy":
        qty = context.user_data.get('qty', 1)
        total = unit_price * qty
        bal = get_bal(uid)
        
        if len(mail_stock) < qty:
            await query.edit_message_text("❌ পর্যাপ্ত স্টক নেই! দুঃখিত।")
        elif bal < total:
            await query.edit_message_text(f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই!\n\nপ্রয়োজন: {total:.2f} টাকা\nআপনার আছে: {bal:.2f} টাকা")
        else:
            items = [mail_stock.pop(0) for _ in range(qty)]
            set_bal(uid, bal - total)
            
            formatted_items = []
            for item in items:
                if ":" in item:
                    m, p = item.split(":", 1)
                    formatted_items.append(f"📧 `{m}` | 🔑 `{p}`")
                else:
                    formatted_items.append(f"📦 `{item}`")
            
            out_txt = (
                "🎉 **অর্ডার সফল হয়েছে!**\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "আপনার ক্রয়কৃত একাউন্ট তথ্য নিচে দেওয়া হলো:\n\n" + "\n".join(formatted_items)
            )
            await query.edit_message_text(out_txt, parse_mode="Markdown")
            
    elif data == "cancel_buy":
        await query.edit_message_text("❌ অর্ডার বাতিল করা হয়েছে।")

# ----------------- Deposit System -----------------
async def dep_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 bKash", callback_data="d_bkash"), InlineKeyboardButton("🔴 Nagad", callback_data="d_nagad")],
        [InlineKeyboardButton("🟣 Rocket", callback_data="d_rocket")],
        [InlineKeyboardButton("❌ বাতিল করুন", callback_data="cancel_dep")]
    ])
    msg = (
        "🏦 **ডিপোজিট সিস্টেম**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💡 সর্বনিম্ন ডিপোজিট: **{MIN_DEPOSIT:.0f} টাকা**\n\n"
        "অনুগ্রহ করে আপনার পছন্দের **Payment Method** সিলেক্ট করুন:"
    )
    await update.message.reply_text(msg, reply_markup=kbd, parse_mode="Markdown")
    return METHOD

async def dep_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if q.data == "cancel_dep":
        await q.edit_message_text("❌ ডিপোজিট প্রক্রিয়া বাতিল করা হয়েছে।")
        return ConversationHandler.END
        
    m = q.data.split("_")[1]
    context.user_data['dep_m'] = m
    
    method_name = "bKash" if m == "bkash" else ("Nagad" if m == "nagad" else "Rocket")
    
    await q.edit_message_text(
        f"✅ আপনি **{method_name}** বেছে নিয়েছেন।\n\n"
        f"💰 আপনি কত টাকা ডিপোজিট করতে চান? (সর্বনিম্ন {MIN_DEPOSIT:.0f} টাকা লিখে পাঠান):",
        parse_mode="Markdown"
    )
    return AMOUNT

async def dep_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    try:
        amt = float(text)
        if amt < MIN_DEPOSIT:
            await update.message.reply_text(f"❌ সর্বনিম্ন ডিপোজিট **{MIN_DEPOSIT:.0f} টাকা**। অনুগ্রহ করে সঠিক পরিমাণ লিখুন:")
            return AMOUNT
            
        context.user_data['dep_a'] = amt
        m = context.user_data.get('dep_m')
        num = BKASH_NUMBER if m == "bkash" else (NAGAD_NUMBER if m == "nagad" else ROCKET_NUMBER)
        method_name = "bKash" if m == "bkash" else ("Nagad" if m == "nagad" else "Rocket")
        
        instructions = (
            f"📥 **{method_name} Personal Number:** `{num}`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"💵 মোট জমার পরিমাণ: **{amt:.2f} টাকা**\n\n"
            "📌 **নির্দেশনা:**\n"
            f"১. উপরের নম্বরে **Send Money** করুন।\n"
            "২. টাকা পাঠানোর পর পাওয়া **Transaction ID (TrxID)** অথবা পেমেন্টের **স্ক্রিনশট** এখানে মেসেজ দিন।"
        )
        await update.message.reply_text(instructions, parse_mode="Markdown")
        return PROOF
    except ValueError:
        await update.message.reply_text("❌ অনুগ্রহ করে শুধু সংখ্যার মাধ্যমে টাকার পরিমাণ লিখুন (যেমন: 50):")
        return AMOUNT

async def dep_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    a = context.user_data.get('dep_a')
    m = context.user_data.get('dep_m')

    if not update.message.photo:
        trx_text = update.message.text.strip()
        if len(trx_text) < 6 or " " in trx_text or len(trx_text) > 20:
            await update.message.reply_text(
                "❌ **ভুল Transaction ID!**\n\n"
                "অনুগ্রহ করে পেমেন্ট শেষ করার পর প্রাপ্ত সঠিক TrxID (যেমন: `3A4B5C6D7E`) অথবা পেমেন্টের স্ক্রিনশট পাঠান।"
            )
            return PROOF

    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"app_{u.id}_{a}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{u.id}_{a}")]
    ])
    txt = (
        f"📥 **নতুন ডিপোজিট রিকোয়েস্ট**\n"
        f"👤 ইউজার: {u.first_name} (`{u.id}`)\n"
        f"💳 মাধ্যম: {m.upper()}\n"
        f"💰 পরিমাণ: {a:.2f} টাকা"
    )
    
    if update.message.photo:
        await context.bot.send_photo(ADMIN_ID, photo=update.message.photo[-1].file_id, caption=txt, reply_markup=kbd, parse_mode="Markdown")
    else:
        await context.bot.send_message(ADMIN_ID, text=f"{txt}\n🔑 TrxID: `{update.message.text.strip()}`", reply_markup=kbd, parse_mode="Markdown")
    
    await update.message.reply_text("✅ আপনার ডিপোজিট তথ্য জমা হয়েছে! এডমিন যাচাই করে দ্রুত ব্যালেন্স যুক্ত করে দেবেন।")
    return ConversationHandler.END

async def dep_cancel_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message(update, context)
    return ConversationHandler.END

async def dep_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ ডিপোজিট প্রক্রিয়া বাতিল করা হয়েছে।")
    return ConversationHandler.END

# ----------------- Admin Action Callback -----------------
async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        return
        
    parts = q.data.split("_")
    act, target_id, amt = parts[0], int(parts[1]), float(parts[2])
    
    if act == "app":
        new_b = get_bal(target_id) + amt
        set_bal(target_id, new_b)
        msg_txt = (q.message.caption if q.message.photo else q.message.text) + f"\n\n✅ **APPROVED (+{amt:.2f} TK)**"
        
        if q.message.photo:
            await q.edit_message_caption(caption=msg_txt, parse_mode="Markdown")
        else:
            await q.edit_message_text(text=msg_txt, parse_mode="Markdown")
            
        try:
            await context.bot.send_message(target_id, f"🎉 আপনার **{amt:.2f} টাকা** ডিপোজিট সফল হয়েছে!\n💰 বর্তমান ব্যালেন্স: **{new_b:.2f} টাকা**")
        except Exception:
            pass
    else:
        msg_txt = (q.message.caption if q.message.photo else q.message.text) + "\n\n❌ **REJECTED**"
        if q.message.photo:
            await q.edit_message_caption(caption=msg_txt, parse_mode="Markdown")
        else:
            await q.edit_message_text(text=msg_txt, parse_mode="Markdown")
            
        try:
            await context.bot.send_message(target_id, f"❌ দুঃখিত, আপনার **{amt:.2f} টাকার** ডিপোজিট রিকোয়েস্টটি প্রত্যাখান করা হয়েছে। সঠিক তথ্য দিয়ে আবার চেষ্টা করুন।")
        except Exception:
            pass

# ----------------- Admin Commands -----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        msg = (
            "⚙️ **ADMIN PANEL COMMANDS**\n\n"
            "📊 `/importsheet <Link>` - Google Sheet থেকে সরাসরি মেইল যুক্ত করুন\n"
            "📬 `/addstock mail:pass` - কমান্ডের মাধ্যমে মেইল যুক্ত করুন\n"
            "💰 `/addbalance USER_ID AMOUNT` - ইউজারের ব্যালেন্স যোগ/বিয়োগ করুন\n"
            "🏷 `/setprice AMOUNT` - প্রতি মেইলের দাম নির্ধারণ করুন\n"
            "📊 `/adminstats` - বর্তমান স্টক ও হিসেব দেখুন\n"
            "📢 `/broadcast বার্তা` - সকল ইউজারকে নোটিশ পাঠান"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

async def import_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ ব্যবহার করার নিয়ম: `/importsheet <Google_Sheet_Link>`", parse_mode="Markdown")
        return
    
    url = context.args[0]
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        await update.message.reply_text("❌ ভুল Google Sheet লিঙ্ক! সঠিক লিঙ্ক দিন।")
        return
    
    sheet_id = match.group(1)
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    
    try:
        res = requests.get(csv_url)
        if res.status_code == 200:
            lines = res.text.strip().split('\n')
            added = 0
            for line in lines:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    m, p = parts[0].strip(), parts[1].strip()
                    if m and p and m.lower() != "mail":
                        item = f"{m}:{p}"
                        if item not in mail_stock:
                            mail_stock.append(item)
                            added += 1
            await update.message.reply_text(f"✅ Google Sheet থেকে **{added}** টি মেইল যোগ করা হয়েছে!\n📦 মোট স্টক: {len(mail_stock)} টি", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Sheet লোড হয়নি! লিঙ্ক শেয়ার অপশন **'Anyone with the link'** করা আছে কিনা নিশ্চিত করুন।")
    except Exception as e:
        await update.message.reply_text(f"⚠️ ত্রুটি: {str(e)}")

async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.args:
        new_mails = context.args
        mail_stock.extend(new_mails)
        await update.message.reply_text(f"✅ সফলভাবে **{len(new_mails)}** টি মেইল যোগ হয়েছে! মোট স্টক: {len(mail_stock)}")

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and len(context.args) == 2:
        try:
            uid, amt = int(context.args[0]), float(context.args[1])
            new_bal = get_bal(uid) + amt
            set_bal(uid, new_bal)
            await update.message.reply_text(f"✅ ইউজার `{uid}` এর নতুন ব্যালেন্স: `{new_bal:.2f}` টাকা", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("⚠️ ব্যবহার করার নিয়ম: `/addbalance USER_ID AMOUNT`", parse_mode="Markdown")

async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global unit_price
    if update.effective_user.id == ADMIN_ID and context.args:
        try:
            unit_price = float(context.args[0])
            await update.message.reply_text(f"✅ প্রতি মেইলের নতুন মূল্য: `{unit_price:.2f}` টাকা", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("⚠ ব্যবহার করার নিয়ম: `/setprice 1.5`", parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        total_users = len(get_all_users())
        await update.message.reply_text(
            f"📊 **স্টোর তথ্য:**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👥 মোট ইউজার: {total_users} জন\n"
            f"📦 অবশিষ্ট স্টক: {len(mail_stock)} টি\n"
            f"💎 বর্তমান মেইল মূল্য: {unit_price:.2f} টাকা",
            parse_mode="Markdown"
        )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ ব্যবহার করার নিয়ম:\n`/broadcast আপনার বার্তা`", parse_mode="Markdown")
        return

    broadcast_text = " ".join(context.args)
    all_users = get_all_users()
    
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

# ----------------- Set Bot Commands Menu -----------------
async def post_init(application):
    commands = [
        BotCommand("start", "বট পুনরায় শুরু করুন")
    ]
    await application.bot.set_my_commands(commands)

# ----------------- App Initialization -----------------
if __name__ == "__main__":
    app_builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init)
    app = app_builder.build()

    dep = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r'.*(ডিপোজিট|Deposit).*'), dep_start)
        ],
        states={
            METHOD: [
                CallbackQueryHandler(dep_method, pattern="^(d_|cancel_dep)"),
                MessageHandler(filters.Regex(MENU_REGEX), dep_cancel_to_menu)
            ],
            AMOUNT: [
                MessageHandler(filters.Regex(MENU_REGEX), dep_cancel_to_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, dep_amount)
            ],
            PROOF: [
                MessageHandler(filters.Regex(MENU_REGEX), dep_cancel_to_menu),
                MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, dep_proof)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', dep_cancel),
            MessageHandler(filters.Regex(MENU_REGEX), dep_cancel_to_menu)
        ]
    )

    # Handlers Priority Order
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("importsheet", import_sheet))
    app.add_handler(CommandHandler("addstock", add_stock))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("setprice", set_price))
    app.add_handler(CommandHandler("adminstats", admin_stats))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Explicit message handlers for Profile and Support
    app.add_handler(MessageHandler(filters.Regex(r'.*(প্রোফাইল|Profile).*'), show_profile))
    app.add_handler(MessageHandler(filters.Regex(r'.*(সাপোর্ট|Support).*'), show_support))

    app.add_handler(dep)
    app.add_handler(CallbackQueryHandler(shop_cb, pattern="^(qty_|confirm_|cancel_)"))
    app.add_handler(CallbackQueryHandler(admin_cb, pattern="^(app_|rej_)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running with SQLite database...")
    app.run_polling()
