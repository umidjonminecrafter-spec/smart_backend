import os
import sys
import threading
from django.core.wsgi import get_wsgi_application

# 🛠️ Loyihangiz sozlamasi (config papkasida)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Asosiy Django ilovasi ishga tushadi
application = get_wsgi_application()

# ================= 1. SUPERUSER YARATISH QISMI =================
try:
    from django.contrib.auth import get_user_model

    User = get_user_model()

    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'parol12345')
        print("🚀 Superuser muvaffaqiyatli yaratildi!")
    else:
        print("✅ Superuser allaqachon bazada bor, qayta yaratilmadi.")
except Exception as e:
    print(f"⚠️ Superuser yaratishda xatolik yuz berdi: {e}")


# ================= 2. BOT VA SCHEDULERNI GLOBAL FONDA ISHGA TUSHIRISH =================
def start_bot_and_scheduler():
    # A) Dars eslatmalari taymerini (Scheduler) ishga tushirish
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from academics.tasks import check_and_send_lesson_reminders

        scheduler = BackgroundScheduler()
        # Har 1 daqiqada darslarni tekshirib eslatma yuboradi
        scheduler.add_job(check_and_send_lesson_reminders, 'interval', minutes=1)
        scheduler.start()
        print("🚀 Telegram Bot scheduler-i muvaffaqiyatli yurib ketdi!")
    except Exception as e:
        print(f"⚠️ Scheduler ishga tushishda xatolik: {str(e)}")

    # B) Telegram botning o'zini (Eshitish rejimini) fonda global yoqish
    try:
        # academics/bot.py ichidagi main funksiyani chaqiramiz
        from academics.bot import main as start_telegram_bot
        print("🤖 Telegram bot global rejimda (polling) ishga tushmoqda...")
        start_telegram_bot()
    except Exception as e:
        print(f"❌ Botni global yoqishda xatolik: {e}")


# Faqat asosiy protsessda ishga tushishini ta'minlash (Render va lokal muhit takrorlanish xavfsizligi)
if "runserver" in sys.argv or not os.environ.get('RUN_MAIN') == 'true':
    # Tizim qotib qolmasligi uchun alohida fonda (Thread) parallel yoqamiz
    threading.Thread(target=start_bot_and_scheduler, daemon=True).start()