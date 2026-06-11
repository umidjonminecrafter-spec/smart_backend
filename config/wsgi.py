import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Asosiy Django ilovasi ishga tushadi
application = get_wsgi_application()




try:
    import sys
    from apscheduler.schedulers.background import BackgroundScheduler
    from academics.tasks import check_and_send_lesson_reminders  # Yangi ochgan faylimizni chaqiramiz

    # Faqat asosiy protsessda ishga tushishini ta'minlash (Render uchun cheklov)
    if "runserver" in sys.argv or not os.environ.get('RUN_MAIN') == 'true':
        scheduler = BackgroundScheduler()
        # Har 1 daqiqada darslarni tekshirib eslatma yuboradi
        scheduler.add_job(check_and_send_lesson_reminders, 'interval', minutes=1)
        scheduler.start()
        print("🚀 Telegram Bot scheduler-i muvaffaqiyatli yurib ketdi!")
except Exception as e:
    print(f"⚠️ Scheduler ishga tushishda xatolik: {str(e)}")