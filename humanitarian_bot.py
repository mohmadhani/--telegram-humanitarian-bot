import pandas as pd
from datetime import datetime
import requests
from io import StringIO
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# مراحل الحوار
ASK_NAME, ASK_SERVICE, ASK_GOV = range(3)

# رابط ملف Google Sheets بصيغة CSV
CSV_URL = "https://docs.google.com/spreadsheets/d/1VpNH_22-Bjuijgcah7iN9TcHyqYJ_aMe3DvoWJQCW4c/export?format=csv"

# الخدمات والمحافظات — ممكن تعديلها حسب محتوى الجدول
services_list = ["صحة", "تعليم", "غذاء", "مياه", "حماية"]
governorates_list = ["حلب", "إدلب", "درعا", "حمص", "دمشق"]

def fetch_data():
    try:
        response = requests.get(CSV_URL)
        response.encoding = 'utf-8'
        return pd.read_csv(StringIO(response.text))
    except:
        return pd.DataFrame()

# بدء المحادثة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! ما اسمك؟")
    return ASK_NAME

# حفظ الاسم
async def ask_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text

    # عرض قائمة الخدمات
    buttons = [[InlineKeyboardButton(srv, callback_data=srv)] for srv in services_list]
    await update.message.reply_text("اختر نوع الخدمة المطلوبة:", reply_markup=InlineKeyboardMarkup(buttons))
    return ASK_SERVICE

# حفظ نوع الخدمة
async def save_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['service'] = query.data

    # عرض قائمة المحافظات
    buttons = [[InlineKeyboardButton(gov, callback_data=gov)] for gov in governorates_list]
    await query.edit_message_text("اختر المحافظة:", reply_markup=InlineKeyboardMarkup(buttons))
    return ASK_GOV

# البحث وعرض النتائج
async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gov = query.data
    service = context.user_data['service']
    name = context.user_data['name']

    df = fetch_data()
    if df.empty:
        await query.edit_message_text("عذراً، لا يمكن تحميل البيانات حالياً.")
        return ConversationHandler.END

    # تحويل الأعمدة لتواريخ
    today = datetime.today()
    df['بدء المشروع'] = pd.to_datetime(df['بدء المشروع'], errors='coerce')
    df['انتهاء المشروع'] = pd.to_datetime(df['انتهاء المشروع'], errors='coerce')

    # فلترة البيانات
    results = df[
        (df['نوع الخدمة'].str.strip() == service.strip()) &
        (df['المحافظة'].str.strip() == gov.strip()) &
        (df['انتهاء المشروع'] > today)
    ]

    if results.empty:
        await query.edit_message_text("لا توجد نتائج متاحة حالياً.")
        return ConversationHandler.END

    # إرسال النتائج واحدة واحدة
    for _, row in results.iterrows():
        org = row['اسم المنظمة']
        phone = str(row['رقم التواصل']).replace(" ", "")
        start = row['بدء المشروع'].date()
        end = row['انتهاء المشروع'].date()
        days_left = (end - today).days

        # رابط واتساب
        whatsapp_link = f"https://wa.me/963{phone[-9:]}" if phone.startswith("09") else None

        text = (
            f"👤 *{name}*\n"
            f"📍 المحافظة: *{gov}*\n"
            f"🛎 الخدمة: *{service}*\n\n"
            f"🔹 المنظمة: *{org}*\n"
            f"📅 المدة: {start} إلى {end} ({days_left} يوم متبقي)\n"
            f"📞 رقم التواصل: {phone}\n"
        )

        buttons = []
        if whatsapp_link:
            buttons.append([InlineKeyboardButton("📱 تواصل عبر واتساب", url=whatsapp_link)])

        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )

    return ConversationHandler.END

# إعداد التطبيق
app = ApplicationBuilder().token("7012021975:AAGR-MKld84_GB-g-9dI6tcZRBV-JKU3X50").build()

# إعداد المحادثة
conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.COMMAND, start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT, ask_service)],
        ASK_SERVICE: [CallbackQueryHandler(save_service)],
        ASK_GOV: [CallbackQueryHandler(show_results)],
    },
    fallbacks=[]
)

# إضافة المحادثة
app.add_handler(conv_handler)

# تشغيل البوت
app.run_polling()
