import urllib.request
import json
from datetime import datetime
from academics.models import LessonSchedule
from organizations.models import LessonNotificationTemplate, TelegramNotificationSetting


def check_and_send_lesson_reminders():
    hozir = datetime.now()
    bugun_hafta_kuni = hozir.weekday()

    # Juft/Toq kunni aniqlash
    kun_turi = 'even' if bugun_hafta_kuni % 2 == 0 else 'odd'

    # Dars jadvallarini bazadan yuklash
    darslar = LessonSchedule.objects.filter(day_type=kun_turi).select_related(
        'group', 'group__course', 'group__teacher'
    )

    for dars in darslar:
        guruh = dars.group
        if not guruh:
            continue

        org = dars.organization

        bot_setting = TelegramNotificationSetting.objects.filter(organization=org, is_active=True).first()
        shablon = LessonNotificationTemplate.objects.filter(organization=org, is_active=True).first()

        if not bot_setting or not shablon or not bot_setting.bot_token or not bot_setting.chat_ids:
            continue

        # Ma'lumotlarni yig'ish
        ustoz_ismi = f"{guruh.teacher.first_name} {guruh.teacher.last_name or ''}".strip() if guruh.teacher else "Biriktirilmagan"
        kurs_nomi = guruh.course.name if guruh.course else "Noma'lum"
        filial_nomi = guruh.branch.name if hasattr(guruh, 'branch') and guruh.branch else "Asosiy Filial"
        dars_vaqti = dars.start_time.strftime("%H:%M")
        xona_nomi = dars.room_name

        # Shablonni o'zgartirish
        tayyor_matn = shablon.message_text
        tayyor_matn = tayyor_matn.replace("{groupName}", guruh.name)
        tayyor_matn = tayyor_matn.replace("{teacherName}", ustoz_ismi)
        tayyor_matn = tayyor_matn.replace("{courseName}", kurs_nomi)
        tayyor_matn = tayyor_matn.replace("{branchName}", filial_nomi)
        tayyor_matn = tayyor_matn.replace("{hours}", dars_vaqti)
        tayyor_matn = tayyor_matn.replace("{roomName}", xona_nomi)

        chat_ids_list = [cid.strip() for cid in bot_setting.chat_ids.replace(',', ' ').split() if cid.strip()]

        for chat_id in chat_ids_list:
            try:
                url = f"https://api.telegram.org/bot{bot_setting.bot_token}/sendMessage"
                payload = {'chat_id': chat_id, 'text': tayyor_matn, 'parse_mode': 'HTML'}
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'},
                                             method='POST')
                with urllib.request.urlopen(req, timeout=5) as res:
                    res.read()
            except Exception as e:
                print(f"Xatolik yuborishda: {str(e)}")