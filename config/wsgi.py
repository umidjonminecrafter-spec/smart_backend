import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Asosiy Django ilovasi ishga tushadi
application = get_wsgi_application()

# Mavlumotlar bazasi bilan ishlaydigan kod aynan shu yerda (pastda) bo'lishi kerak:
from django.contrib.auth import get_user_model

try:
    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'parol12345')
        print("Superuser muvaffaqiyatli yaratildi! ✅")
except Exception as e:
    print(f"Superuser yaratishda xatolik: {e}")