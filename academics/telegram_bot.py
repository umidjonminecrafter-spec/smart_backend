import requests
from django.db.models import Q
from django.contrib.auth import get_user_model
from academics.models import Student, StudentGroup, Attendance, ExamResult, LessonSchedule

User = get_user_model()


def normalize_phone(phone_str):
    if not phone_str:
        return ""
    digits = "".join(c for c in phone_str if c.isdigit())
    # O'zbekiston raqamlari formatini tuzatamiz (+998XXXXXXXXX)
    if len(digits) == 9:
        return f"+998{digits}"
    elif len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    return f"+{digits}"


def send_telegram_message(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=8)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending message to {chat_id}: {str(e)}")
        return False


def get_contact_keyboard(text="📱 Telefon raqamni yuborish"):
    return {
        "keyboard": [[
            {
                "text": text,
                "request_contact": True
            }
        ]],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


def get_reply_keyboard(buttons):
    keyboard = []
    for row in buttons:
        row_buttons = []
        for btn in row:
            row_buttons.append({"text": btn})
        keyboard.append(row_buttons)
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


def handle_telegram_update(bot_type, token, update_data):
    """
    Stateless telegram update handler
    bot_type: 'verification', 'student', 'parent', 'staff'
    """
    if "message" not in update_data:
        return

    message = update_data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    contact = message.get("contact")

    # 1. Telefon raqam yuborilganda bog'lash
    if contact:
        phone_raw = contact.get("phone_number")
        phone_normalized = normalize_phone(phone_raw)

        if bot_type == 'verification':
            # Verifikatsiya boti: ham student ham xodimlarni bog'laydi
            students = Student.objects.filter(phone=phone_normalized)
            users = User.objects.filter(phone=phone_normalized)

            linked = False
            if students.exists():
                students.update(telegram_chat_id=chat_id)
                linked = True
            if users.exists():
                users.update(telegram_chat_id=chat_id)
                linked = True

            if linked:
                msg = f"<b>Muvaffaqiyatli bog'landi!</b> 🔐\n\nTelefon raqam: {phone_normalized}\nUshbu bot orqali sizga kirish va parolni tiklash kodlari yuboriladi."
                send_telegram_message(token, chat_id, msg)
            else:
                msg = f"Kechirasiz, <code>{phone_normalized}</code> telefon raqami tizimda topilmadi. Iltimos, ma'muriyat bilan bog'laning."
                send_telegram_message(token, chat_id, msg, get_contact_keyboard())

        elif bot_type == 'student':
            students = Student.objects.filter(phone=phone_normalized)
            if students.exists():
                students.update(telegram_chat_id=chat_id)
                msg = f"<b>Muvaffaqiyatli bog'landi!</b> 🎓\n\nSiz Student botidan muvaffaqiyatli ro'yxatdan o'tdingiz."
                menu = get_reply_keyboard([["👤 Profilim", "💰 Balansim"], ["📅 Dars jadvalim"]])
                send_telegram_message(token, chat_id, msg, menu)
            else:
                msg = f"Kechirasiz, <code>{phone_normalized}</code> telefon raqamli talaba tizimda topilmadi."
                send_telegram_message(token, chat_id, msg, get_contact_keyboard())

        elif bot_type == 'parent':
            # Otasining yoki onasining raqami mos keladigan talabalarni bog'laymiz
            students_father = Student.objects.filter(father_phone=phone_normalized)
            students_mother = Student.objects.filter(mother_phone=phone_normalized)

            linked = False
            if students_father.exists():
                students_father.update(father_telegram_chat_id=chat_id)
                linked = True
            if students_mother.exists():
                students_mother.update(mother_telegram_chat_id=chat_id)
                linked = True

            if linked:
                msg = f"<b>Muvaffaqiyatli bog'landi!</b> 👨‍👩‍👧‍👦\n\nSiz Ota-ona botidan muvaffaqiyatli ro'yxatdan o'tdingiz."
                menu = get_reply_keyboard([["👶 Farzandlarim", "📊 Davomat"], ["🏆 Baholar", "💳 To'lovlar"]])
                send_telegram_message(token, chat_id, msg, menu)
            else:
                msg = f"Kechirasiz, <code>{phone_normalized}</code> telefon raqamli ota-ona tizimda topilmadi."
                send_telegram_message(token, chat_id, msg, get_contact_keyboard())

        elif bot_type == 'staff':
            users = User.objects.filter(phone=phone_normalized).exclude(role='student')
            if users.exists():
                users.update(telegram_chat_id=chat_id)
                msg = f"<b>Muvaffaqiyatli bog'landi!</b> 💼\n\nSiz Xodimlar botidan muvaffaqiyatli ro'yxatdan o'tdingiz."
                menu = get_reply_keyboard([["👤 Profilim", "📅 Kunlik dars jadvalim"]])
                send_telegram_message(token, chat_id, msg, menu)
            else:
                msg = f"Kechirasiz, <code>{phone_normalized}</code> telefon raqamli xodim topilmadi."
                send_telegram_message(token, chat_id, msg, get_contact_keyboard())
        return

    # 2. Buyruqlar yoki menyu tugmalarini bosganda
    if text == "/start":
        msg = "Assalomu alaykum! SmartTalim xizmatiga xush kelibsiz.\n\nBotdan foydalanish uchun telefon raqamingizni yuboring:"
        send_telegram_message(token, chat_id, msg, get_contact_keyboard())
        return

    # Tekshiruv: Akkaunt bog'langanligini aniqlash
    if bot_type == 'verification':
        # Verifikatsiya botida menyu yo'q, faqat telefon so'rash bo'ladi
        msg = "Siz botdan muvaffaqiyatli ro'yxatdan o'tgan ekansiz. Parolni tiklash kodi kerak bo'lganda shu yerga yuboriladi. 🔐"
        send_telegram_message(token, chat_id, msg)

    elif bot_type == 'student':
        student = Student.objects.filter(telegram_chat_id=chat_id).first()
        if not student:
            msg = "Siz hali ro'yxatdan o'tmagansiz. Iltimos, telefon raqamingizni yuboring:"
            send_telegram_message(token, chat_id, msg, get_contact_keyboard())
            return

        if text == "👤 Profilim":
            active_groups = StudentGroup.objects.filter(student=student, group__status='active')
            groups_str = ", ".join([g.group.name for g in active_groups]) or "Guruh yo'q"
            res = (
                f"<b>👤 Talaba Profili</b>\n\n"
                f"Ism: {student.first_name} {student.last_name or ''}\n"
                f"Telefon: {student.phone}\n"
                f"Guruhlar: {groups_str}\n"
                f"Balans: {int(student.balance):,} UZS\n".replace(",", " ")
            )
            send_telegram_message(token, chat_id, res)

        elif text == "💰 Balansim":
            status_emoji = "✅" if student.balance >= 0 else "⚠️"
            res = (
                f"<b>💰 Balans holati</b>\n\n"
                f"Joriy balans: <code>{int(student.balance):,} UZS</code> {status_emoji}\n"
                f"To'lov kuni: {student.payment_date or 'Belgilanmagan'}"
            ).replace(",", " ")
            send_telegram_message(token, chat_id, res)

        elif text == "📅 Dars jadvalim":
            active_groups = StudentGroup.objects.filter(student=student, group__status='active')
            if not active_groups.exists():
                send_telegram_message(token, chat_id, "Siz faol guruhlarda topilmadingiz.")
                return

            res = "<b>📅 Sizning dars jadvalingiz:</b>\n\n"
            for sg in active_groups:
                g = sg.group
                day_type_str = "Juft kunlar" if g.day_type == 'even' else "Toq kunlar"
                teacher_str = g.teacher.get_full_name() if g.teacher else "Noma'lum"
                res += (
                    f"📚 <b>{g.name}</b> ({g.course.name if g.course else ''})\n"
                    f"⏰ Vaqt: {g.start_time or 'Belgilanmagan'}\n"
                    f"🗓 Kunlar: {day_type_str}\n"
                    f"👤 O'qituvchi: {teacher_str}\n\n"
                )
            send_telegram_message(token, chat_id, res)

        else:
            send_telegram_message(token, chat_id, "Noma'lum buyruq. Iltimos menyudan foydalaning.")

    elif bot_type == 'parent':
        students = Student.objects.filter(Q(father_telegram_chat_id=chat_id) | Q(mother_telegram_chat_id=chat_id))
        if not students.exists():
            msg = "Siz hali ro'yxatdan o'tmagansiz. Iltimos, telefon raqamingizni yuboring:"
            send_telegram_message(token, chat_id, msg, get_contact_keyboard())
            return

        if text == "👶 Farzandlarim":
            res = "<b>👶 Farzandlaringiz ro'yxati:</b>\n\n"
            for s in students:
                active_groups = StudentGroup.objects.filter(student=s, group__status='active')
                groups_str = ", ".join([g.group.name for g in active_groups]) or "Guruh yo'q"
                res += (
                    f"👦 <b>{s.first_name} {s.last_name or ''}</b>\n"
                    f"Balans: {int(s.balance):,} UZS\n"
                    f"Guruhlar: {groups_str}\n\n"
                ).replace(",", " ")
            send_telegram_message(token, chat_id, res)

        elif text == "📊 Davomat":
            res = "<b>📊 Oxirgi darslardagi davomat:</b>\n\n"
            for s in students:
                res += f"👦 <b>{s.first_name}:</b>\n"
                attendances = Attendance.objects.filter(student=s).order_by('-date')[:10]
                if not attendances.exists():
                    res += "  Davomatlar topilmadi.\n\n"
                    continue
                for att in attendances:
                    status_text = "Keldi ✅" if att.status == 'present' else "Kelmadi ❌" if att.status == 'absent' else "Kechikdi ⚠️" if att.status == 'late' else "Sababli 📁"
                    res += f"  • {att.date}: {att.group.name} - <b>{status_text}</b>\n"
                res += "\n"
            send_telegram_message(token, chat_id, res)

        elif text == "🏆 Baholar":
            res = "<b>🏆 Imtihon baholari:</b>\n\n"
            for s in students:
                res += f"👦 <b>{s.first_name}:</b>\n"
                results = ExamResult.objects.filter(student=s).select_related('exam').order_by('-exam__date')
                if not results.exists():
                    res += "  Baholar topilmadi.\n\n"
                    continue
                for r in results:
                    res += f"  • {r.exam.name} ({r.exam.date}): <b>{int(r.score)} ball</b>\n"
                res += "\n"
            send_telegram_message(token, chat_id, res)

        elif text == "💳 To'lovlar":
            res = "<b>💳 To'lovlar va balans holati:</b>\n\n"
            for s in students:
                status_text = "Faol ✅" if s.balance >= 0 else "Qarzdorlik bor ⚠️"
                res += (
                    f"👦 <b>{s.first_name}:</b>\n"
                    f"  Joriy balans: <code>{int(s.balance):,} UZS</code>\n"
                    f"  Holat: {status_text}\n"
                    f"  Keyingi to'lov sanasi: {s.payment_date or 'Belgilanmagan'}\n\n"
                ).replace(",", " ")
            send_telegram_message(token, chat_id, res)

        else:
            send_telegram_message(token, chat_id, "Noma'lum buyruq. Iltimos menyudan foydalaning.")

    elif bot_type == 'staff':
        user = User.objects.filter(telegram_chat_id=chat_id).first()
        if not user:
            msg = "Siz hali ro'yxatdan o'tmagansiz. Iltimos, telefon raqamingizni yuboring:"
            send_telegram_message(token, chat_id, msg, get_contact_keyboard())
            return

        if text == "👤 Profilim":
            groups = StudentGroup.objects.filter(group__teacher=user, group__status='active').values('group__name',
                                                                                                     'group__course__name').distinct()
            groups_str = ", ".join(
                [f"{g['group__name']} ({g['group__course__name']})" for g in groups]) or "Guruh biriktirilmagan"
            res = (
                f"<b>👤 Xodim profili</b>\n\n"
                f"Ism: {user.get_full_name() or user.username}\n"
                f"Lavozim: {user.get_role_display()}\n"
                f"Telefon: {user.phone or 'Kiritilmagan'}\n"
                f"O'qitadigan guruhlar: {groups_str}\n"
            )
            send_telegram_message(token, chat_id, res)

        elif text == "📅 Kunlik dars jadvalim":
            schedules = LessonSchedule.objects.filter(teacher=user).select_related('group', 'group__course')
            if not schedules.exists():
                send_telegram_message(token, chat_id, "Kunlik dars jadvallari topilmadi.")
                return

            res = "<b>📅 Sizning dars jadvalingiz:</b>\n\n"
            for sch in schedules:
                day_type_str = "Juft kunlar" if sch.day_type == 'even' else "Toq kunlar"
                res += (
                    f"📚 <b>{sch.group.name}</b> ({sch.group.course.name if sch.group.course else ''})\n"
                    f"⏰ Vaqt: {sch.start_time.strftime('%H:%M')} - {sch.end_time.strftime('%H:%M')}\n"
                    f"🗓 Kunlar: {day_type_str}\n"
                    f"🚪 Xona: {sch.room_name}\n\n"
                )
            send_telegram_message(token, chat_id, res)

        else:
            send_telegram_message(token, chat_id, "Noma'lum buyruq. Iltimos menyudan foydalaning.")
