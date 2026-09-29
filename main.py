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
import logging, sqlite3, requests, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

# ----------------- Configuration -----------------
BOT_TOKEN = "8803998786:AAETJSRZPzcu6aUI1q914TvA5jcNw3Mrw0A"  # BotFather token
ADMIN_ID = 7792142088               # Telegram Admin User ID (Number)

BKASH_NUMBER, NAGAD_NUMBER, ROCKET_NUMBER = "01766872406", "01821826206", "01766872406"
MIN_DEPOSIT, DB_FILE = 20.0, "bot_database.db"
mail_stock, support_user = ["kelli.731@piepla.com:rasel24", "michal@piepla.com:rasel24"], "@YourTelegramUsername"
unit_price = 0.80  # Default Mail Price
METHOD, AMOUNT, PROOF = range(3)

logging.basicConfig(level=logging.INFO)

# ----------------- Database Setup -----------------
def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    res = c.fetchone() if fetchone else (c.fetchall() if fetchall else None)
    if commit: conn.commit()
    conn.close()
    return res

db_query("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)", commit=True)

def get_bal(uid):
    r = db_query("SELECT balance FROM users WHERE user_id = ?", (uid,), fetchone=True)
    return r[0] if r else 0.0

def set_bal(uid, bal):
    db_query("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = ?", (uid, bal, bal), commit=True)

# ----------------- Keyboards & Interface -----------------
def get_kbd(is_admin):
    kbd = [[KeyboardButton("💲 Buy Product")], [KeyboardButton("👤 Profile"), KeyboardButton("🏦 Deposit")], [KeyboardButton("💬 Support")]]
    if is_admin: kbd.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(kbd, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if get_bal(uid) == 0.0: set_bal(uid, 0.0)
    await update.message.reply_text("👋 **Swagotom!** Menu select korun:", reply_markup=get_kbd(uid == ADMIN_ID), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, user, uid = update.message.text, update.effective_user, update.effective_user.id
    
    if context.user_data.get('waiting_qty'):
        if text.isdigit() and int(text) > 0:
            context.user_data['qty'], context.user_data['waiting_qty'] = int(text), False
            await send_shop_menu(update.message, context, is_edit=False)
        else:
            await update.message.reply_text("⚠️ Sothik shongkha likhun:")
        return

    bal = get_bal(uid)
    if text == "👤 Profile":
        await update.message.reply_text(f"👤 **Profile**\n🆔 ID: `{uid}`\n📛 Name: {user.first_name}\n💰 Balance: `{bal:.2f}` TK", parse_mode="Markdown")
    elif text in ["💲 Buy Product", "🛒 Buy Product"]:
        if not mail_stock:
            await update.message.reply_text("❌ Dukkhito! Stock-e mail nei.")
            return
        context.user_data['qty'] = 1
        await send_shop_menu(update.message, context, is_edit=False)
    elif text == "💬 Support":
        await update.message.reply_text(f"💬 Support: {support_user}")
    elif text in ["⚙️ Admin Panel", "⚙ Admin Panel"] and uid == ADMIN_ID:
        await admin_panel(update, context)

async def send_shop_menu(msg_obj, context, is_edit=True):
    qty = context.user_data.get('qty', 1)
    stock, total = len(mail_stock), unit_price * qty
    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("➖", callback_data="qty_dec"), InlineKeyboardButton(f"📦 {qty} Pcs", callback_data="qty_val"), InlineKeyboardButton("➕", callback_data="qty_inc")],
        [InlineKeyboardButton("✏️ Custom Quantity", callback_data="qty_custom")],
        [InlineKeyboardButton("✅ Confirm Order", callback_data="confirm_buy"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_buy")]
    ])
    txt = f"🌟 **Meta AI ID**\n\n💎 Unit Price: {unit_price:.2f} TK\n📦 Stock: {stock} Pcs\n📊 Selected Qty: {qty}\n💰 Total: {total:.2f} TK"
    if is_edit: await msg_obj.edit_message_text(txt, reply_markup=kbd, parse_mode="Markdown")
    else: await msg_obj.reply_text(txt, reply_markup=kbd, parse_mode="Markdown")

async def shop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, uid = query.data, query.from_user.id
    
    if data == "qty_inc":
        context.user_data['qty'] = context.user_data.get('qty', 1) + 1
        await send_shop_menu(query, context, is_edit=True)
    elif data == "qty_dec":
        if context.user_data.get('qty', 1) > 1: context.user_data['qty'] -= 1
        await send_shop_menu(query, context, is_edit=True)
    elif data == "qty_custom":
        context.user_data['waiting_qty'] = True
        await query.message.reply_text("✏️ Koy piece nite chan? Shongkha likhun:")
    elif data == "confirm_buy":
        qty = context.user_data.get('qty', 1)
        total, bal = unit_price * qty, get_bal(uid)
        if len(mail_stock) < qty: await query.edit_message_text("❌ Porjapto stock nei.")
        elif bal < total: await query.edit_message_text(f"❌ Balance nei! Required: {total:.2f} TK, Yours: {bal:.2f} TK")
        else:
            items = [mail_stock.pop(0) for _ in range(qty)]
            set_bal(uid, bal - total)
            
            formatted_items = []
            for item in items:
                if ":" in item:
                    m, p = item.split(":", 1)
                    formatted_items.append(f"`{m}` | `{p}`")
                else:
                    formatted_items.append(f"`{item}`")
            
            out_txt = "🎉 **Order Success!**\n\n📧 **Mail** | 🔑 **Password**\n" + "\n".join(formatted_items)
            await query.edit_message_text(out_txt, parse_mode="Markdown")
            
    elif data == "cancel_buy":
        await query.edit_message_text("❌ Order batil.")

# ----------------- Deposit System -----------------
async def dep_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kbd = InlineKeyboardMarkup([[InlineKeyboardButton("🟢 bKash", callback_data="d_bkash"), InlineKeyboardButton("🔴 Nagad", callback_data="d_nagad")], [InlineKeyboardButton("🟣 Rocket", callback_data="d_rocket")]])
    await update.message.reply_text(f"🏦 **Deposit System** (Min {MIN_DEPOSIT} TK)\nSelect Method:", reply_markup=kbd, parse_mode="Markdown")
    return METHOD

async def dep_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    m = q.data.split("_")[1]
    context.user_data['dep_m'] = m
    num = BKASH_NUMBER if m == "bkash" else (NAGAD_NUMBER if m == "nagad" else ROCKET_NUMBER)
    await q.message.reply_text(f"👉 **{m.upper()}**: `{num}`\nAmount likhe message din:", parse_mode="Markdown")
    return AMOUNT

async def dep_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        if amt < MIN_DEPOSIT:
            await update.message.reply_text(f"❌ Min deposit {MIN_DEPOSIT} TK.")
            return AMOUNT
        context.user_data['dep_a'] = amt
        await update.message.reply_text("📸 Screenshot ba TrxID pathan:")
        return PROOF
    except:
        await update.message.reply_text("❌ Sothik amount likhun:")
        return AMOUNT

async def dep_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u, a, m = update.effective_user, context.user_data.get('dep_a'), context.user_data.get('dep_m')
    kbd = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"app_{u.id}_{a}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{u.id}_{a}")]])
    txt = f"📥 **Deposit Request**\nUser: {u.first_name} (`{u.id}`)\nMethod: {m.upper()}\nAmount: {a} TK"
    
    if update.message.photo:
        await context.bot.send_photo(ADMIN_ID, photo=update.message.photo[-1].file_id, caption=txt, reply_markup=kbd, parse_mode="Markdown")
    else:
        await context.bot.send_message(ADMIN_ID, text=f"{txt}\nTrxID: `{update.message.text}`", reply_markup=kbd, parse_mode="Markdown")
    
    await update.message.reply_text("✅ Request Admin-e pathano hoyeche.")
    return ConversationHandler.END

# ----------------- Admin Commands & Google Sheet Auto Import -----------------
async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID: return
    act, target_id, amt = q.data.split("_")[0], int(q.data.split("_")[1]), float(q.data.split("_")[2])
    
    if act == "app":
        new_b = get_bal(target_id) + amt
        set_bal(target_id, new_b)
        msg_txt = (q.message.caption if q.message.photo else q.message.text) + f"\n\n✅ APPROVED (+{amt} TK)"
        if q.message.photo: await q.edit_message_caption(caption=msg_txt, parse_mode="Markdown")
        else: await q.edit_message_text(text=msg_txt, parse_mode="Markdown")
        try: await context.bot.send_message(target_id, f"🎉 {amt} TK Deposit Approved! Balance: {new_b:.2f} TK")
        except: pass
    else:
        msg_txt = (q.message.caption if q.message.photo else q.message.text) + "\n\n❌ REJECTED"
        if q.message.photo: await q.edit_message_caption(caption=msg_txt, parse_mode="Markdown")
        else: await q.edit_message_text(text=msg_txt, parse_mode="Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        msg = (
            "⚙️ **ADMIN PANEL COMMANDS**\n\n"
            "📊 `/importsheet <Google_Sheet_Link>` - Google Sheet theke direct mail stock-e add korun\n"
            "📬 `/addstock mail:pass` - Direct Text diye mail add korun\n"
            "💰 `/addbalance USER_ID AMOUNT` - Balance comano/barano (Jemon: 50 ba -20)\n"
            "🏷 `/setprice AMOUNT` - Mail unit price change korun\n"
            "📊 `/adminstats` - Current stock status dekhoon"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

async def import_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Rule: `/importsheet <Google_Sheet_Link>`", parse_mode="Markdown")
        return
    
    url = context.args[0]
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        await update.message.reply_text("❌ Invalid Google Sheet link! Link dekhe abar pathan.")
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
                    if m and p and m.lower() != "mail":  # Column Header Ignore
                        item = f"{m}:{p}"
                        if item not in mail_stock:
                            mail_stock.append(item)
                            added += 1
            await update.message.reply_text(f"✅ Google Sheet theke **{added}** ti mail stock-e add hoyeche!\n📦 Total Stock: {len(mail_stock)} Pcs", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Sheet load hoyni! Link share setting **'Anyone with the link can view'** ache kina check korun.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.args:
        new_mails = context.args
        mail_stock.extend(new_mails)
        await update.message.reply_text(f"✅ Added {len(new_mails)} Mails! Total Stock: {len(mail_stock)}")

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and len(context.args) == 2:
        try:
            uid, amt = int(context.args[0]), float(context.args[1])
            new_bal = get_bal(uid) + amt
            set_bal(uid, new_bal)
            await update.message.reply_text(f"✅ User `{uid}` er new balance: `{new_bal:.2f}` TK", parse_mode="Markdown")
        except:
            await update.message.reply_text("⚠️ Rule: `/addbalance USER_ID AMOUNT`", parse_mode="Markdown")

async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global unit_price
    if update.effective_user.id == ADMIN_ID and context.args:
        try:
            unit_price = float(context.args[0])
            await update.message.reply_text(f"✅ Mail unit price: `{unit_price:.2f}` TK", parse_mode="Markdown")
        except:
            await update.message.reply_text("⚠ Rule: `/setprice 15`", parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(f"📊 Stock: {len(mail_stock)} pcs\n💎 Current Mail Price: {unit_price:.2f} TK")

# ----------------- App Main Run -----------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    dep = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^(🏦 Deposit|💳 Deposit)$'), dep_start)],
        states={
            METHOD: [CallbackQueryHandler(dep_method, pattern="^d_")],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, dep_amount)],
            PROOF: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, dep_proof)]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("importsheet", import_sheet))
    app.add_handler(CommandHandler("addstock", add_stock))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("setprice", set_price))
    app.add_handler(CommandHandler("adminstats", admin_stats))
    app.add_handler(dep)
    app.add_handler(CallbackQueryHandler(shop_cb, pattern="^(qty_|confirm_|cancel_)"))
    app.add_handler(CallbackQueryHandler(admin_cb, pattern="^(app_|rej_)"))
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
