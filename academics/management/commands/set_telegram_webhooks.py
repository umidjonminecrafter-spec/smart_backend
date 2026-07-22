import requests
from django.core.management.base import BaseCommand
from organizations.models import TelegramNotificationSetting

class Command(BaseCommand):
    help = "PythonAnywhere va Telegram o'rtasida Webhook'larni o'rnatish"

    def add_arguments(self, parser):
        parser.add_argument('--domain', type=str, default='smartbackend.pythonanywhere.com', help='PythonAnywhere domeningiz')
        parser.add_argument('--report-token', type=str, default=None, help='Hisobot botingiz yangi tokeni')

    def handle(self, *args, **options):
        domain = options['domain'].strip().replace('https://', '').replace('http://', '').strip('/')
        report_token = options.get('report_token') or '8697561524:AAHyj2sGeNuYS5K8omuZoDdmtTBXz0Oob94'
        STUDENT_BOT_TOKEN = '8987298254:AAEGTUlbiXG1_ZO41JnowqIRWkqVOxbB2iY'

        # DB dagi sozlamalarni yangilaymiz
        try:
            TelegramNotificationSetting.objects.all().update(
                bot_token=report_token,
                student_bot_token=STUDENT_BOT_TOKEN
            )
        except Exception as e_db:
            self.stdout.write(self.style.WARNING(f"DB update warning: {str(e_db)}"))

        bots = [
            ('reports', report_token),
            ('student', STUDENT_BOT_TOKEN)
        ]

        for bot_type, token in set(bots):
            webhook_url = f"https://{domain}/api/telegram/webhook/{bot_type}/{token}/"
            masked_token = token[:10] + "..." + token[-4:] if len(token) > 15 else token
            try:
                res = requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}", timeout=5)
                if res.status_code == 200 and res.json().get('ok'):
                    self.stdout.write(self.style.SUCCESS(f"✅ Webhook o'rnatildi ({bot_type} | {masked_token}): {webhook_url}"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Webhook xatosi ({bot_type} | {masked_token}): {res.text}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Xatolik ({bot_type} | {masked_token}): {str(e)}"))
