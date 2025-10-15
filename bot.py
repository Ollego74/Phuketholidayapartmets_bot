import json
import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, Application,
    CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# ================= Render/ENV =================
# РЕКОМЕНДАЦИЯ: хранить секреты в переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ================= Logging ===================
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= States & Keys =============
LANG, PICK_APT, AFTER_APT, FORM_DATES, FORM_GUESTS, FORM_NAME, FORM_CONTACT, FORM_WISHES = range(8)
UD_LANG = "lang"
UD_APT = "apt_key"
UD_FORM = "form"

with open("data.json", "r", encoding="utf-8-sig") as f:
    DATA = json.load(f)

def t(lang: str, key: str) -> str:
    return DATA["texts"].get(lang, DATA["texts"]["en"]).get(key, key)

def k_lang() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Русский", callback_data="lang:ru"),
        InlineKeyboardButton("English", callback_data="lang:en")
    ]])

def k_apts(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for key, a in DATA["apartments"].items():
        title = a["ru_name"] if lang == "ru" else a["en_name"]
        rows.append([InlineKeyboardButton(title, callback_data=f"apt:{key}")])
    return InlineKeyboardMarkup(rows)

def k_yesno(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "btn_yes"), callback_data="yes"),
        InlineKeyboardButton(t(lang, "btn_no"), callback_data="no")
    ]])

# =============== Handlers ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(t("ru", "choose_lang"), reply_markup=k_lang())
    return LANG

async def on_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, lang = q.data.split(":", 1)
    context.user_data[UD_LANG] = lang

    welcome = t(lang, "welcome")
    welcome_photo = DATA.get("welcome_photo_file_id") or ""
    if welcome_photo:
        await q.message.reply_photo(welcome_photo, caption=welcome, parse_mode=ParseMode.HTML)
    else:
        await q.message.reply_text(welcome, parse_mode=ParseMode.HTML)

    await q.message.reply_text(t(lang, "which_apt"), reply_markup=k_apts(lang))
    return PICK_APT

async def on_pick_apartment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, apt_key = q.data.split(":", 1)
    context.user_data[UD_APT] = apt_key
    lang = context.user_data.get(UD_LANG, "en")

    apt = DATA["apartments"][apt_key]
    caption = apt["ru_caption"] if lang == "ru" else apt["en_caption"]
    photo_id = apt.get("photo_file_id") or ""
    if photo_id:
        await q.message.reply_photo(photo=photo_id, caption=caption, parse_mode=ParseMode.HTML)
    else:
        await q.message.reply_text(caption, parse_mode=ParseMode.HTML)

    await q.message.reply_text(t(lang, "want_request"), reply_markup=k_yesno(lang))
    return AFTER_APT

async def on_yesno(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = context.user_data.get(UD_LANG, "en")
    if q.data == "no":
        await q.message.reply_text(t(lang, "which_apt"), reply_markup=k_apts(lang))
        return PICK_APT

    context.user_data[UD_FORM] = {}
    await q.message.reply_text(t(lang, "q_dates"))
    return FORM_DATES

async def form_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_FORM]["dates"] = update.message.text.strip()
    lang = context.user_data.get(UD_LANG, "en")
    await update.message.reply_text(t(lang, "q_guests"))
    return FORM_GUESTS

async def form_guests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_FORM]["guests"] = update.message.text.strip()
    lang = context.user_data.get(UD_LANG, "en")
    await update.message.reply_text(t(lang, "q_name"))
    return FORM_NAME

async def form_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_FORM]["name"] = update.message.text.strip()
    lang = context.user_data.get(UD_LANG, "en")
    await update.message.reply_text(t(lang, "q_contact"))
    return FORM_CONTACT

async def form_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_FORM]["contact"] = update.message.text.strip()
    lang = context.user_data.get(UD_LANG, "en")
    await update.message.reply_text(t(lang, "q_wishes"))
    return FORM_WISHES

async def form_wishes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[UD_FORM]["wishes"] = update.message.text.strip()
    lang = context.user_data.get(UD_LANG, "en")
    apt_key = context.user_data.get(UD_APT)
    apt = DATA["apartments"].get(apt_key, {})
    apt_title = apt.get("ru_name") if lang == "ru" else apt.get("en_name")

    form = context.user_data.get(UD_FORM, {})
    admin_msg = (
        "✅ New booking request\n"
        f"Lang: {lang}\n"
        f"Apartment: {apt_title}\n\n"
        f"Dates: {form.get('dates','')}\n"
        f"Guests: {form.get('guests','')}\n"
        f"Name: {form.get('name','')}\n"
        f"Contact: {form.get('contact','')}\n"
        f"Wishes: {form.get('wishes','')}\n"
    )
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg)
        except Exception as e:
            logger.error(f"Failed to send admin message: {e}")

    await update.message.reply_text(t(lang, "request_sent"))
    await update.message.reply_text("Чтобы начать заново, нажмите /start")
    return ConversationHandler.END

async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get(UD_LANG, "ru")
    text_ru = (
        "📞 <b>Контакты Phuket Holiday Apartments</b>\n"
        "Свяжитесь с нами удобным способом:"
    )
    text_en = (
        "📞 <b>Contacts — Phuket Holiday Apartments</b>\n"
        "Reach us via your preferred method:"
    )
    buttons = [
        [InlineKeyboardButton("🌐 Website", url="https://phuket.holiday.apartments")],
        [InlineKeyboardButton("💬 WhatsApp", url="https://wa.me/66621839495")],
        [InlineKeyboardButton("✈️ Telegram", url="https://t.me/phuketholidayapartments")],
        [InlineKeyboardButton("📸 Instagram", url="https://instagram.com/phuket_holiday_apartments")]
    ]
    msg = text_ru if lang == "ru" else text_en
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог завершён. /start")
    return ConversationHandler.END

async def helper_photo_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        fid = update.message.photo[-1].file_id
        await update.message.reply_text(f"file_id: <code>{fid}</code>", parse_mode=ParseMode.HTML)

# =============== App bootstrap =================
def build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN env var is not set")
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(on_lang, pattern=r"^lang:(ru|en)$")],
            PICK_APT: [CallbackQueryHandler(on_pick_apartment, pattern=r"^apt:")],
            AFTER_APT: [CallbackQueryHandler(on_yesno, pattern=r"^(yes|no)$")],
            FORM_DATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_dates)],
            FORM_GUESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_guests)],
            FORM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_name)],
            FORM_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_contact)],
            FORM_WISHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_wishes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("contacts", contacts))
    app.add_handler(MessageHandler(filters.PHOTO, helper_photo_id))
    return app

# ======== Mini Flask server to keep Render Web Service alive ========
# (если позже переведём на Background Worker — это можно убрать)
from flask import Flask
import threading

flask_app = Flask(__name__)

@flask_app.get("/")
def health():
    return "Bot is alive!", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

def main():
    logger.info("Starting bot...")
    # поднимем Flask в отдельном потоке, чтобы Render видел HTTP-порт
    threading.Thread(target=run_flask, daemon=True).start()

    app = build_app()
    logger.info("Bot started!")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
