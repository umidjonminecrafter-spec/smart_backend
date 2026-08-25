import time
import requests
from django.core.management.base import BaseCommand
from organizations.models import TelegramNotificationSetting
from academics.telegram_bot import handle_telegram_update, REPORT_BOT_TOKEN, STUDENT_BOT_TOKEN, STAFF_BOT_TOKEN


class Command(BaseCommand):
    help = "Mahalliy polling rejimida barcha faol Telegram botlarni ishga tushirish"

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Faqat bitta marta yangilanishlarni tekshirib to\'xtash')
        parser.add_argument('--interval', type=float, default=1.0, help='Polling oralig\'i (soniyalarda)')

    def handle(self, *args, **options):
        run_once = options.get('once', False)
        interval = options.get('interval', 1.0)
        self.stdout.write(self.style.SUCCESS("Telegram botlari polling rejimi ishga tushdi... 🚀"))

        # Har bir token uchun oxirgi update offset ini saqlaymiz
        offsets = {}
        cleaned_webhooks = set()

        while True:
            try:
                # Faol telegram sozlamalarini olamiz
                settings = TelegramNotificationSetting.objects.all()

                raw_bots = []
                for s in settings:
                    if s.bot_token:
                        raw_bots.append(('reports', s.bot_token.strip()))
                    if s.verification_bot_token:
                        raw_bots.append(('verification', s.verification_bot_token.strip()))
                    if s.student_bot_token:
                        raw_bots.append(('student', s.student_bot_token.strip()))
                    if s.parent_bot_token:
                        raw_bots.append(('parent', s.parent_bot_token.strip()))
                    if s.staff_bot_token:
                        raw_bots.append(('staff', s.staff_bot_token.strip()))
                    if s.support_bot_token:
                        raw_bots.append(('support', s.support_bot_token.strip()))

                # Standart botlar agar DB da yo'q bo'lsa qo'shamiz
                if not any(b[0] == 'reports' for b in raw_bots):
                    raw_bots.append(('reports', REPORT_BOT_TOKEN))
                if not any(b[0] == 'student' for b in raw_bots):
                    raw_bots.append(('student', STUDENT_BOT_TOKEN))
                if not any(b[0] == 'staff' for b in raw_bots):
                    raw_bots.append(('staff', STAFF_BOT_TOKEN))

                # Unikal botlar ro'yxati
                active_bots = []
                seen_tokens = set()
                for b_type, t_val in raw_bots:
                    if t_val and (b_type, t_val) not in seen_tokens:
                        active_bots.append((b_type, t_val))
                        seen_tokens.add((b_type, t_val))

                # Webhooklarni tozalash (polling bilan to'qnashmasligi uchun)
                for bot_type, token in active_bots:
                    if token not in cleaned_webhooks:
                        try:
                            wh_info = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=5).json()
                            if wh_info.get("result", {}).get("url"):
                                requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=5)
                                self.stdout.write(self.style.WARNING(f"[{bot_type.upper()}] Webhook olib tashlandi (polling uchun)"))
                            cleaned_webhooks.add(token)
                        except Exception as e_wh:
                            self.stdout.write(self.style.WARNING(f"[{bot_type.upper()}] Webhook tekshirishda ogohlantirish: {str(e_wh)}"))
                            cleaned_webhooks.add(token)

                for bot_type, token in active_bots:
                    offset = offsets.get(token, 0)
                    url = f"https://api.telegram.org/bot{token}/getUpdates"
                    params = {"timeout": 1, "offset": offset}

                    try:
                        response = requests.get(url, params=params, timeout=6)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get("ok"):
                                updates = data.get("result", [])
                                for update in updates:
                                    update_id = update["update_id"]
                                    offsets[token] = update_id + 1

                                    # Xabarni qayta ishlash
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f"[{bot_type.upper()}] Yangi xabar keldi (Update ID: {update_id})"
                                        )
                                    )
                                    try:
                                        handle_telegram_update(bot_type, token, update)
                                    except Exception as e_handler:
                                        self.stdout.write(self.style.ERROR(f"[{bot_type.upper()}] Xabarni ishlashda xato: {str(e_handler)}"))
                        elif response.status_code == 401:
                            self.stdout.write(
                                self.style.ERROR(f"[{bot_type.upper()}] Yaroqsiz token: {token[:12]}...")
                            )
                        elif response.status_code == 409:
                            # Webhook hali to'liq o'chmagan bo'lsa
                            requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=5)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Botda xatolik ({bot_type}): {str(e)}"))

                if run_once:
                    self.stdout.write(self.style.SUCCESS("Bir martalik tekshiruv yakunlandi."))
                    break

                time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS("\nTelegram botlari to'xtatildi. 🛑"))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Tizimda kutilmagan xato: {str(e)}"))
                if run_once:
                    break
                time.sleep(3)
