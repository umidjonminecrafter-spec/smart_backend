import time
import requests
from django.core.management.base import BaseCommand
from organizations.models import TelegramNotificationSetting
from academics.telegram_bot import handle_telegram_update


class Command(BaseCommand):
    help = "Mahalliy polling rejimida barcha faol Telegram botlarni ishga tushirish"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Telegram botlari polling rejimi ishga tushdi... 🚀"))

        # Har bir token uchun oxirgi update offset ini saqlaymiz
        offsets = {}

        while True:
            try:
                # Faol telegram sozlamalarini olamiz
                settings = TelegramNotificationSetting.objects.all()  # is_active=True yoki tokenlar borligini tekshiramiz

                active_bots = []
                for s in settings:
                    if s.verification_bot_token:
                        active_bots.append(('verification', s.verification_bot_token))
                    if s.student_bot_token:
                        active_bots.append(('student', s.student_bot_token))
                    if s.parent_bot_token:
                        active_bots.append(('parent', s.parent_bot_token))
                    if s.staff_bot_token:
                        active_bots.append(('staff', s.staff_bot_token))

                if not active_bots:
                    # Agar birorta ham token bo'lmasa 5 soniya kutib qayta tekshiramiz
                    time.sleep(5)
                    continue

                for bot_type, token in active_bots:
                    offset = offsets.get(token, 0)
                    url = f"https://api.telegram.org/bot{token}/getUpdates"
                    params = {"timeout": 1, "offset": offset}

                    try:
                        response = requests.get(url, params=params, timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get("ok"):
                                updates = data.get("result", [])
                                for update in updates:
                                    update_id = update["update_id"]
                                    offsets[token] = update_id + 1

                                    # Xabarni qayta ishlash
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f"[{bot_type.upper()}] Yangi xabar keldi (Update ID: {update_id})"
                                        )
                                    )
                                    handle_telegram_update(bot_type, token, update)
                        elif response.status_code == 401:
                            # Noto'g'ri token bo'lsa konsolga yozamiz
                            self.stdout.write(
                                self.style.ERROR(f"[{bot_type.upper()}] Xato token: {token[:10]}...")
                            )
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Botda xatolik ({bot_type}): {str(e)}"))

                time.sleep(1)
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS("\nTelegram botlari to'xtatildi. 🛑"))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Tizimda kutilmagan xato: {str(e)}"))
                time.sleep(5)
