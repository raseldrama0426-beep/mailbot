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
BOT_TOKEN = "8803998786:AAHnmue-EM-uLp09jlXwrCxj_bUrqv6mw54"
ADMIN_ID = 8967812900

BKASH_NUMBER = "01766872406"
NAGAD_NUMBER = "01821826206"
ROCKET_NUMBER = "01766872406"

MIN_DEPOSIT = 20.0
DB_FILE = os.path.join(os.getcwd(), "bot_database.db")

mail_stock = ["kelli.731@piepla.com:rasel24", "michal@piepla.com:rasel24"]
support_user = "@PremiumStoreBD_Support"
unit_price = 0.80

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

# ----------------- Core Commands -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    uid = update.effective_user.id
    if get_bal(uid) == 0.0:
        set_bal(uid, 0.0)
    
    msg = (
        "<b>👋 স্বাগতম আমাদের প্রিমিয়াম স্টোরে!</b>\n\n"
        "আপনার প্রয়োজনীয় সেবা পেতে নিচের মেনু থেকে অপশন সিলেক্ট করুন:"
    )
    await update.message.reply_text(msg, reply_markup=get_kbd(uid == ADMIN_ID), parse_mode="HTML")

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    bal = get_bal(uid)
    profile_msg = (
        "<b>👤 আপনার প্রোফাইল বিবরণী</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>ইউজার আইডি:</b> <code>{uid}</code>\n"
        f"📛 <b>নাম:</b> {user.first_name}\n"
        f"💰 <b>বর্তমান ব্যালেন্স:</b> <code>{bal:.2f}</code> টাকা"
    )
    await update.message.reply_text(profile_msg, parse_mode="HTML")

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💬 <b>আমাদের সাপোর্ট টিম:</b> {support_user}\n\nযেকোনো সহায়তার জন্য মেসেজ দিন।", parse_mode="HTML")

async def start_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'DEP_METHOD'
    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 bKash", callback_data="d_bkash"), InlineKeyboardButton("🔴 Nagad", callback_data="d_nagad")],
        [InlineKeyboardButton("🟣 Rocket", callback_data="d_rocket")],
        [InlineKeyboardButton("❌ বাতিল করুন", callback_data="cancel_dep")]
    ])
    msg = (
        "<b>🏦 ডিপোজিট সিস্টেম</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💡 সর্বনিম্ন ডিপোজিট: <b>{MIN_DEPOSIT:.0f} টাকা</b>\n\n"
        "অনুগ্রহ করে আপনার পছন্দের <b>Payment Method</b> সিলেক্ট করুন:"
    )
    await update.message.reply_text(msg, reply_markup=kbd, parse_mode="HTML")

# ----------------- Main Direct Event Router -----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text
    text = raw_text.lower().strip()
    uid = update.effective_user.id

    if "প্রোফাইল" in raw_text or "profile" in text:
        context.user_data.clear()
        await show_profile(update, context)
        return

    elif "সাপোর্ট" in raw_text or "support" in text:
        context.user_data.clear()
        await show_support(update, context)
        return

    elif "প্রডাক্ট" in raw_text or "product" in text or "কিনুন" in raw_text or "buy" in text:
        context.user_data.clear()
        if not mail_stock:
            await update.message.reply_text("❌ দুঃখিত! বর্তমানে স্টকে কোনো মেইল নেই।")
            return
        context.user_data['qty'] = 1
        await send_shop_menu(update.message, context, is_edit=False)
        return

    elif "ডিপোজিট" in raw_text or "deposit" in text:
        context.user_data.clear()
        await start_deposit(update, context)
        return

    elif ("এডমিন" in raw_text or "admin" in text) and uid == ADMIN_ID:
        context.user_data.clear()
        await admin_panel(update, context)
        return

    state = context.user_data.get('state')

    if state == 'WAITING_QTY':
        if raw_text.isdigit() and int(raw_text) > 0:
            context.user_data['qty'] = int(raw_text)
            context.user_data['state'] = None
            await send_shop_menu(update.message, context, is_edit=False)
        else:
            await update.message.reply_text("⚠️ অনুগ্রহ করে সঠিক একটি সংখ্যা লিখুন:")
        return

    elif state == 'DEP_AMOUNT':
        try:
            amt = float(raw_text)
            if amt < MIN_DEPOSIT:
                await update.message.reply_text(f"❌ সর্বনিম্ন ডিপোজিট <b>{MIN_DEPOSIT:.0f} টাকা</b>। অনুগ্রহ করে সঠিক পরিমাণ লিখুন:", parse_mode="HTML")
                return
            context.user_data['dep_a'] = amt
            context.user_data['state'] = 'DEP_PROOF'
            m = context.user_data.get('dep_m', 'bkash')
            num = BKASH_NUMBER if m == "bkash" else (NAGAD_NUMBER if m == "nagad" else ROCKET_NUMBER)
            method_name = "bKash" if m == "bkash" else ("Nagad" if m == "nagad" else "Rocket")
            instructions = (
                f"📥 <b>{method_name} Personal Number:</b> <code>{num}</code>\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"💵 মোট জমার পরিমাণ: <b>{amt:.2f} টাকা</b>\n\n"
                "📌 <b>নির্দেশনা:</b>\n"
                "১. উপরের নম্বরে <b>Send Money</b> করুন।\n"
                "২. টাকা পাঠানোর পর পাওয়া <b>Transaction ID (TrxID)</b> অথবা পেমেন্টের <b>স্ক্রিনশট</b> এখানে মেসেজ দিন।"
            )
            await update.message.reply_text(instructions, parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ অনুগ্রহ করে শুধু সংখ্যার মাধ্যমে টাকার পরিমাণ লিখুন (যেমন: 50):")
        return

    elif state == 'DEP_PROOF':
        await process_dep_proof(update, context)
        return

async def process_dep_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    a = context.user_data.get('dep_a', 0.0)
    m = context.user_data.get('dep_m', 'bkash')

    if not update.message.photo:
        trx_text = update.message.text.strip()
        if len(trx_text) < 6 or " " in trx_text or len(trx_text) > 20:
            await update.message.reply_text(
                "❌ <b>ভুল Transaction ID!</b>\n\n"
                "অনুগ্রহ করে পেমেন্ট শেষ করার পর প্রাপ্ত সঠিক TrxID অথবা পেমেন্টের স্ক্রিনশট পাঠান।",
                parse_mode="HTML"
            )
            return

    context.user_data.clear()
    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"app_{u.id}_{a}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{u.id}_{a}")]
    ])
    txt = (
        f"📥 <b>নতুন ডিপোজিট রিকোয়েস্ট</b>\n"
        f"👤 ইউজার: {u.first_name} (<code>{u.id}</code>)\n"
        f"💳 মাধ্যম: {m.upper()}\n"
        f"💰 পরিমাণ: {a:.2f} টাকা"
    )
    
    if update.message.photo:
        await context.bot.send_photo(ADMIN_ID, photo=update.message.photo[-1].file_id, caption=txt, reply_markup=kbd, parse_mode="HTML")
    else:
        await context.bot.send_message(ADMIN_ID, text=f"{txt}\n🔑 TrxID: <code>{update.message.text.strip()}</code>", reply_markup=kbd, parse_mode="HTML")
    
    await update.message.reply_text("✅ আপনার ডিপোজিট তথ্য জমা হয়েছে! এডমিন যাচাই করে দ্রুত ব্যালেন্স যুক্ত করে দেবেন।")

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
        "🌟 <b>Meta AI ID (স্টোর পণ্য)</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>একক মূল্য:</b> {unit_price:.2f} টাকা\n"
        f"📦 <b>মোট স্টক আছে:</b> {stock} টি\n"
        f"📊 <b>নির্বাচিত পরিমাণ:</b> {qty} টি\n"
        f"💰 <b>মোট দেয় মূল্য:</b> {total:.2f} টাকা"
    )
    if is_edit:
        await msg_obj.edit_message_text(txt, reply_markup=kbd, parse_mode="HTML")
    else:
        await msg_obj.reply_text(txt, reply_markup=kbd, parse_mode="HTML")

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
        context.user_data['state'] = 'WAITING_QTY'
        await query.message.reply_text("✏️ আপনি কতটি কিনতে চান? সংখ্যাটি লিখে দিন:")
    elif data == "confirm_buy":
        qty = context.user_data.get('qty', 1)
        total = unit_price * qty
        bal = get_bal(uid)
        
        if len(mail_stock) < qty:
            await query.edit_message_text("❌ পর্যাপ্ত স্টক নেই! দুঃখিত।")
        elif bal < total:
            await query.edit_message_text(f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই!\n\nপ্রয়োজন: {total:.2f} টাকা\nআপনার আছে: {bal:.2f} টাকা")
        else:
            items = [mail_stock.pop(0) for _ in range(qty)]
            set_bal(uid, bal - total)
            
            formatted_items = []
            for item in items:
                if ":" in item:
                    m, p = item.split(":", 1)
                    formatted_items.append(f"📧 <code>{m}</code> | 🔑 <code>{p}</code>")
                else:
                    formatted_items.append(f"📦 <code>{item}</code>")
            
            out_txt = (
                "🎉 <b>অর্ডার সফল হয়েছে!</b>\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "আপনার ক্রয়কৃত একাউন্ট তথ্য নিচে দেওয়া হলো:\n\n" + "\n".join(formatted_items)
            )
            await query.edit_message_text(out_txt, parse_mode="HTML")
            
    elif data == "cancel_buy":
        context.user_data.clear()
        await query.edit_message_text("❌ অর্ডার বাতিল করা হয়েছে।")

# ----------------- Admin Action Callbacks -----------------
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
        msg_txt = (q.message.caption if q.message.photo else q.message.text) + f"\n\n✅ <b>APPROVED (+{amt:.2f} TK)</b>"
        
        if q.message.photo:
            await q.edit_message_caption(caption=msg_txt, parse_mode="HTML")
        else:
            await q.edit_message_text(text=msg_txt, parse_mode="HTML")
            
        try:
            await context.bot.send_message(target_id, f"🎉 আপনার <b>{amt:.2f} টাকা</b> ডিপোজিট সফল হয়েছে!\n💰 বর্তমান ব্যালেন্স: <b>{new_b:.2f} টাকা</b>", parse_mode="HTML")
        except Exception:
            pass
    else:
        msg_txt = (q.message.caption if q.message.photo else q.message.text) + "\n\n❌ <b>REJECTED</b>"
        if q.message.photo:
            await q.edit_message_caption(caption=msg_txt, parse_mode="HTML")
        else:
            await q.edit_message_text(text=msg_txt, parse_mode="HTML")
            
        try:
            await context.bot.send_message(target_id, f"❌ দুঃখিত, আপনার <b>{amt:.2f} টাকার</b> ডিপোজিট রিকোয়েস্টটি প্রত্যাখান করা হয়েছে।", parse_mode="HTML")
        except Exception:
            pass

# ----------------- Deposit Callback Handler -----------------
async def dep_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if q.data == "cancel_dep":
        context.user_data.clear()
        await q.edit_message_text("❌ ডিপোজিট প্রক্রিয়া বাতিল করা হয়েছে।")
        return
        
    m = q.data.split("_")[1]
    context.user_data['dep_m'] = m
    context.user_data['state'] = 'DEP_AMOUNT'
    
    method_name = "bKash" if m == "bkash" else ("Nagad" if m == "nagad" else "Rocket")
    
    await q.edit_message_text(
        f"✅ আপনি <b>{method_name}</b> বেছে নিয়েছেন।\n\n"
        f"💰 আপনি কত টাকা ডিপোজিট করতে চান? (সর্বনিম্ন {MIN_DEPOSIT:.0f} টাকা লিখে পাঠান):",
        parse_mode="HTML"
    )

# ----------------- Admin Commands -----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        msg = (
            "⚙️ <b>ADMIN PANEL COMMANDS</b>\n\n"
            "📊 <code>/importsheet &lt;Link&gt;</code> - Google Sheet থেকে সরাসরি মেইল যুক্ত করুন\n"
            "📬 <code>/addstock mail:pass</code> - কমান্ডের মাধ্যমে মেইল যুক্ত করুন\n"
            "💰 <code>/addbalance USER_ID AMOUNT</code> - ইউজারের ব্যালেন্স যোগ/বিয়োগ করুন\n"
            "🏷 <code>/setprice AMOUNT</code> - প্রতি মেইলের দাম নির্ধারণ করুন\n"
            "📊 <code>/adminstats</code> - বর্তমান স্টক ও হিসেব দেখুন\n"
            "📢 <code>/broadcast বার্তা</code> - সকল ইউজারকে নোটিশ পাঠান"
        )
        await update.message.reply_text(msg, parse_mode="HTML")

async def import_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ ব্যবহার করার নিয়ম: <code>/importsheet &lt;Google_Sheet_Link&gt;</code>", parse_mode="HTML")
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
            await update.message.reply_text(f"✅ Google Sheet থেকে <b>{added}</b> টি মেইল যোগ করা হয়েছে!\n📦 মোট স্টক: {len(mail_stock)} টি", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Sheet লোড হয়নি! লিঙ্ক শেয়ার অপশন <b>'Anyone with the link'</b> করা আছে কিনা নিশ্চিত করুন।", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"⚠️ ত্রুটি: {str(e)}")

async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.args:
        new_mails = context.args
        mail_stock.extend(new_mails)
        await update.message.reply_text(f"✅ সফলভাবে <b>{len(new_mails)}</b> টি মেইল যোগ হয়েছে! মোট স্টক: {len(mail_stock)}", parse_mode="HTML")

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and len(context.args) == 2:
        try:
            uid, amt = int(context.args[0]), float(context.args[1])
            new_bal = get_bal(uid) + amt
            set_bal(uid, new_bal)
            await update.message.reply_text(f"✅ ইউজার <code>{uid}</code> এর নতুন ব্যালেন্স: <code>{new_bal:.2f}</code> টাকা", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("⚠️ ব্যবহার করার নিয়ম: <code>/addbalance USER_ID AMOUNT</code>", parse_mode="HTML")

async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global unit_price
    if update.effective_user.id == ADMIN_ID and context.args:
        try:
            unit_price = float(context.args[0])
            await update.message.reply_text(f"✅ প্রতি মেইলের নতুন মূল্য: <code>{unit_price:.2f}</code> টাকা", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("⚠️ ব্যবহার করার নিয়ম: <code>/setprice 1.5</code>", parse_mode="HTML")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        total_users = len(get_all_users())
        await update.message.reply_text(
            f"📊 <b>স্টোর তথ্য:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👥 মোট ইউজার: {total_users} জন\n"
            f"📦 অবশিষ্ট স্টক: {len(mail_stock)} টি\n"
            f"💎 বর্তমান মেইল মূল্য: {unit_price:.2f} টাকা",
            parse_mode="HTML"
        )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ ব্যবহার করার নিয়ম:\n<code>/broadcast আপনার বার্তা</code>", parse_mode="HTML")
        return

    broadcast_text = " ".join(context.args)
    all_users = get_all_users()
    
    success_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text("📢 ব্রডকাস্ট পাঠানো শুরু হচ্ছে...")

    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 <b>ADMIN NOTICE</b> 📢\n\n{broadcast_text}", parse_mode="HTML")
            success_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ <b>ব্রডকাস্ট সম্পন্ন হয়েছে!</b>\n\n"
        f"🎯 সফল: {success_count} জন\n"
        f"❌ ব্যর্থ/ব্লকড: {fail_count} জন",
        parse_mode="HTML"
    )

# ----------------- Error Handler -----------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

# ----------------- Set Bot Commands Menu -----------------
async def post_init(application):
    commands = [
        BotCommand("start", "বট পুনরায় শুরু করুন")
    ]
    await application.bot.set_my_commands(commands)

# ----------------- App Initialization -----------------
if __name__ == "__main__":
    app_builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init)
    app = app_builder.build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("importsheet", import_sheet))
    app.add_handler(CommandHandler("addstock", add_stock))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("setprice", set_price))
    app.add_handler(CommandHandler("adminstats", admin_stats))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    app.add_handler(CallbackQueryHandler(dep_cb, pattern="^(d_|cancel_dep)"))
    app.add_handler(CallbackQueryHandler(shop_cb, pattern="^(qty_|confirm_|cancel_)"))
    app.add_handler(CallbackQueryHandler(admin_cb, pattern="^(app_|rej_)"))

    app.add_handler(MessageHandler(filters.PHOTO, process_dep_proof))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_error_handler(error_handler)

    print("Bot is running with HTML safe parsing...")
    app.run_polling()
