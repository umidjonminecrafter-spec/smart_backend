from django.core.management.base import BaseCommand
from academics.tasks import send_daily_telegram_reports

class Command(BaseCommand):
    help = "Moliya bo'limi bo'yicha kunlik hisobotni Telegram botga yuboradi"

    def handle(self, *args, **options):
        self.stdout.write("Kunlik Telegram hisobotlarini yuborish boshlandi...")
        send_daily_telegram_reports()
        self.stdout.write(self.style.SUCCESS("Kunlik Telegram hisobotlari muvaffaqiyatli yuborildi!"))
