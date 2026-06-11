import urllib.request
import json
from datetime import datetime, timedelta
from django.db import connection
from django.core.cache import cache
from academics.models import LessonSchedule
from organizations.models import LessonNotificationTemplate, TelegramNotificationSetting


def check_and_send_lesson_reminders():
    # Close old connections to avoid database connection issues in background threads
    connection.close()

    hozir = datetime.now()
    today_date = hozir.date()

    # Get all active Telegram settings
    active_settings = TelegramNotificationSetting.objects.filter(is_active=True).select_related('organization')

    for bot_setting in active_settings:
        org = bot_setting.organization
        if not bot_setting.bot_token or not bot_setting.chat_ids:
            continue

        # Get all active templates for this organization
        shablonlar = LessonNotificationTemplate.objects.filter(organization=org, is_active=True)
        if not shablonlar.exists():
            continue

        # Get all schedules for this organization
        darslar = LessonSchedule.objects.filter(organization=org).select_related(
            'group', 'group__course', 'group__teacher', 'group__branch'
        )

        for dars in darslar:
            guruh = dars.group
            if not guruh:
                continue

            for shablon in shablonlar:
                # Combine schedule times with current date to do timedelta calculations
                try:
                    dars_start_dt = datetime.combine(today_date, dars.start_time)
                    dars_end_dt = datetime.combine(today_date, dars.end_time)
                except Exception as e:
                    print(f"Time combining error for lesson {dars.id}: {str(e)}")
                    continue

                # Determine target datetime based on template_type
                if shablon.template_type == 'before':
                    target_dt = dars_start_dt - timedelta(minutes=shablon.delay_minutes)
                elif shablon.template_type == 'during':
                    target_dt = dars_start_dt + timedelta(minutes=shablon.delay_minutes)
                elif shablon.template_type == 'after':
                    target_dt = dars_end_dt + timedelta(minutes=shablon.delay_minutes)
                else:
                    continue

                # Calculate which date the lesson would occur on, so that target_dt falls on today
                days_diff = (target_dt.date() - today_date).days
                occurrence_date = today_date - timedelta(days=days_diff)

                # Check if the occurrence date matches the lesson schedule's day_type (even/odd)
                occurrence_weekday = occurrence_date.weekday()
                occurrence_day_type = 'even' if occurrence_weekday % 2 == 0 else 'odd'

                if dars.day_type != occurrence_day_type:
                    continue

                # Check if the target send time matches the current time to the exact hour and minute
                if target_dt.hour == hozir.hour and target_dt.minute == hozir.minute:
                    # Cache key to prevent duplicate sending within the same minute
                    cache_key = f"lesson_rem_{dars.id}_{shablon.id}_{occurrence_date}_{target_dt.hour}_{target_dt.minute}"
                    if cache.get(cache_key):
                        continue

                    # Mark in cache immediately before network request to prevent concurrent duplicate sends
                    cache.set(cache_key, True, timeout=600)

                    # Gather information for placeholders
                    ustoz_ismi = f"{guruh.teacher.first_name} {guruh.teacher.last_name or ''}".strip() if guruh.teacher else "Biriktirilmagan"
                    kurs_nomi = guruh.course.name if guruh.course else "Noma'lum"
                    filial_nomi = guruh.branch.name if guruh.branch else "Asosiy Filial"
                    dars_vaqti = f"{dars.start_time.strftime('%H:%M')}-{dars.end_time.strftime('%H:%M')}"
                    xona_nomi = dars.room_name or ""
                    kun_nomi = "Juft kunlar" if dars.day_type == 'even' else "Toq kunlar"
                    sub_kurs_nomi = guruh.course.code or ""

                    # Replace template variables
                    tayyor_matn = shablon.message_text
                    replacements = {
                        "{groupName}": guruh.name,
                        "{teacherName}": ustoz_ismi,
                        "{courseName}": kurs_nomi,
                        "{branchName}": filial_nomi,
                        "{hours}": dars_vaqti,
                        "{roomName}": xona_nomi,
                        "{days}": kun_nomi,
                        "{subCourseName}": sub_kurs_nomi
                    }
                    for key, val in replacements.items():
                        if val is not None:
                            tayyor_matn = tayyor_matn.replace(key, str(val))

                    # Parse chat IDs and send to each
                    chat_ids_list = [cid.strip() for cid in bot_setting.chat_ids.replace(',', ' ').split() if
                                     cid.strip()]

                    for chat_id in chat_ids_list:
                        try:
                            url = f"https://api.telegram.org/bot{bot_setting.bot_token}/sendMessage"
                            payload = {'chat_id': chat_id, 'text': tayyor_matn, 'parse_mode': 'HTML'}
                            data = json.dumps(payload).encode('utf-8')
                            req = urllib.request.Request(
                                url,
                                data=data,
                                headers={'Content-Type': 'application/json'},
                                method='POST'
                            )
                            with urllib.request.urlopen(req, timeout=5) as res:
                                res.read()
                        except Exception as e:
                            print(f"Error sending telegram message to chat {chat_id} for lesson {dars.id}: {str(e)}")


def check_and_send_parent_checkout_notifications():
    # Close old connections
    connection.close()

    hozir = datetime.now()
    today_date = hozir.date()

    # Faol Telegram bot sozlamalari mavjud tashkilotlarni tekshiramiz
    active_settings = TelegramNotificationSetting.objects.filter(is_active=True).select_related('organization')

    for bot_setting in active_settings:
        org = bot_setting.organization
        if not bot_setting.parent_bot_token:
            continue

        # Ushbu tashkilot uchun faol 'parent_check_out' shablonini qidiramiz
        from academics.models import BotMessageTemplate, StudentGroup
        shablon = BotMessageTemplate.objects.filter(
            organization=org, template_type='parent_check_out', is_active=True
        ).first()

        # Agar shablon bo'lmasa, default matn ishlatamiz
        default_text = "Hurmatli ota-ona, farzandingiz {first_name}ning {group_name} guruhi darsi tugadi. 🚪"
        shablon_text = shablon.text if shablon else default_text

        # Ushbu tashkilotning dars jadvallarini tekshiramiz
        darslar = LessonSchedule.objects.filter(organization=org).select_related('group', 'group__course')

        for dars in darslar:
            guruh = dars.group
            if not guruh:
                continue

            try:
                dars_end_dt = datetime.combine(today_date, dars.end_time)
            except Exception:
                continue

            # Target date day_type (even/odd) mosligini tekshiramiz
            occurrence_weekday = today_date.weekday()
            occurrence_day_type = 'even' if occurrence_weekday % 2 == 0 else 'odd'

            if dars.day_type != occurrence_day_type:
                continue

            # Agarda dars joriy soat va daqiqada tugagan bo'lsa
            if dars_end_dt.hour == hozir.hour and dars_end_dt.minute == hozir.minute:
                # Takroran yuborishni oldini olish uchun keshlaymiz
                cache_key = f"parent_checkout_{dars.id}_{today_date}_{dars_end_dt.hour}_{dars_end_dt.minute}"
                if cache.get(cache_key):
                    continue

                cache.set(cache_key, True, timeout=600)

                # Guruhdagi talabalarni olamiz
                student_groups = StudentGroup.objects.filter(group=guruh).select_related('student')
                for sg in student_groups:
                    student = sg.student
                    if not student:
                        continue

                    # Ota yoki onaning telegram_chat_id si borligini tekshiramiz
                    parent_chats = []
                    if student.father_telegram_chat_id:
                        parent_chats.append(student.father_telegram_chat_id)
                    if student.mother_telegram_chat_id:
                        parent_chats.append(student.mother_telegram_chat_id)

                    if not parent_chats:
                        continue

                    # Matndagi o'zgaruvchilarni almashtiramiz
                    tayyor_matn = shablon_text.replace("{first_name}", student.first_name)
                    tayyor_matn = tayyor_matn.replace("{last_name}", student.last_name or "")
                    tayyor_matn = tayyor_matn.replace("{group_name}", guruh.name)
                    tayyor_matn = tayyor_matn.replace("{course_name}", guruh.course.name if guruh.course else "")

                    # Har bir ota-onaga xabarni yuboramiz
                    import requests
                    for chat_id in parent_chats:
                        try:
                            url = f"https://api.telegram.org/bot{bot_setting.parent_bot_token}/sendMessage"
                            payload = {
                                'chat_id': chat_id,
                                'text': tayyor_matn,
                                'parse_mode': 'HTML'
                            }
                            requests.post(url, json=payload, timeout=5)
                        except Exception as e:
                            print(f"Error sending checkout notification to parent {chat_id}: {str(e)}")
