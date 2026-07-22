import requests
from django.core.management.base import BaseCommand
from organizations.models import TelegramNotificationSetting

class Command(BaseCommand):
    help = "PythonAnywhere va Telegram o'rtasida Webhook'larni o'rnatish"

    def add_arguments(self, parser):
        parser.add_argument('--domain', type=str, default='smartbackend.pythonanywhere.com', help='PythonAnywhere domeningiz')

    def handle(self, *args, **options):
        domain = options['domain'].strip().replace('https://', '').replace('http://', '').strip('/')
        REPORT_BOT_TOKEN = '8697561524:AAHyj2sGeNuYS5K8omuZoDdmtTBXz0oob94'
        STUDENT_BOT_TOKEN = '8987298254:AAEGTUlbiXG1_ZO41JnowqIRWkqVOxbB2iY'

        bots = [
            ('reports', REPORT_BOT_TOKEN),
            ('student', STUDENT_BOT_TOKEN)
        ]

        for setting in TelegramNotificationSetting.objects.all():
            if setting.bot_token:
                bots.append(('reports', setting.bot_token))
            if setting.student_bot_token:
                bots.append(('student', setting.student_bot_token))

        for bot_type, token in set(bots):
            webhook_url = f"https://{domain}/api/telegram/webhook/{bot_type}/{token}/"
            try:
                res = requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}", timeout=5)
                if res.status_code == 200 and res.json().get('ok'):
                    self.stdout.write(self.style.SUCCESS(f"✅ Webhook o'rnatildi ({bot_type}): {webhook_url}"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Webhook xatosi ({bot_type}): {res.text}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Xatolik ({bot_type}): {str(e)}"))
