from django.db import models
from django.conf import settings
from organizations.models import TenantModel

from organizations.models import Organization
from django.utils import timezone
import datetime

class TelegramVerification(models.Model):
    PURPOSE_CHOICES = (
        ('register', 'Ro‘yxatdan o‘tish'),
        ('forgot', 'Parolni tiklash'),
    )

    # O'quvchining telefon raqami (bu orqali bazadan o'quvchini topamiz)
    phone = models.CharField(max_length=50)
    # Tasdiqlash uchun 6 xonali random kod
    code = models.CharField(max_length=6)
    # Qaysi maqsadda yuborilgani
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    # Kod yaratilgan vaqt
    created_at = models.DateTimeField(auto_now_add=True)
    # Kod ishlatildimi yoki yo'q
    is_verified = models.BooleanField(default=False)

    def is_valid(self):
        # Kod faqat 2 daqiqa davomida amal qiladi
        expiry_time = self.created_at + datetime.timedelta(minutes=2)
        return timezone.now() <= expiry_time and not self.is_verified

    def __str__(self):
        return f"{self.phone} - {self.code} ({self.purpose})"


class Course(TenantModel):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_weeks = models.IntegerField(default=12)
    code = models.CharField(max_length=50, null=True, blank=True)
    lesson_time = models.CharField(max_length=50, null=True, blank=True)
    image = models.ImageField(upload_to='course_images/', null=True, blank=True)

    def __str__(self):
        return self.name

class Room(TenantModel):
    name = models.CharField(max_length=100)
    capacity = models.IntegerField(default=30)

    def __str__(self):
        return self.name

class Student(TenantModel):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, null=True, blank=True)
    phone = models.CharField(max_length=50)
    email = models.EmailField(null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    photo = models.ImageField(upload_to='student_photos/', null=True, blank=True)
    telegram_chat_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="Telegram Chat ID")
    category = models.CharField(max_length=255, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    application = models.TextField(null=True, blank=True)
    language = models.CharField(max_length=100, null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    target_university = models.CharField(max_length=255, null=True, blank=True)

    # organization qatorini BUTUNLAY olib tashla

    father_name = models.CharField(max_length=255, null=True, blank=True)
    father_phone = models.CharField(max_length=50, null=True, blank=True)
    father_email = models.EmailField(null=True, blank=True)
    father_telegram_chat_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="Otasining Telegram Chat IDsi")

    mother_name = models.CharField(max_length=255, null=True, blank=True)
    mother_phone = models.CharField(max_length=50, null=True, blank=True)
    mother_email = models.EmailField(null=True, blank=True)
    mother_telegram_chat_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="Onasining Telegram Chat IDsi")


class StudentFieldSetting(TenantModel):

    FIELD_CHOICES = [
        ("last_name", "Familiya"),
        ("email", "Elektron pochta"),
        ("photo", "Rasm"),
        ("category", "Kategoriya"),
        ("birth_date", "Tug'ilgan sana"),
        ("application", "So'rovnoma"),
        ("language", "Til"),
        ("payment_date", "To'lov sanasi"),
        ("address", "Uy manzili"),
        ("target_university", "Maqsad qilgan universitet"),
        ("organization", "Tashkilot"),
        ("father_name", "Otasining ismi"),
        ("father_phone", "Otasining telefon raqami"),
        ("father_email", "Otasining elektron pochtasi"),
        ("mother_name", "Onasining ismi"),
        ("mother_phone", "Onasining telefon raqami"),
        ("mother_email", "Onasining elektron pochtasi"),
    ]
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="student_field_settings"
    )

    field_name = models.CharField(
        max_length=100,
        choices=FIELD_CHOICES
    )
    is_required = models.BooleanField(default=False)

class Group(TenantModel):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('upcoming', 'Upcoming'),
    )
    name = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="groups")
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="groups")
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="teaching_groups")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    day_type = models.CharField(max_length=50, null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name

class StudentGroup(TenantModel):
    # TO'G'RILANDI: on_delete=models.SET_NULL qilindi.
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="student_groups")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="group_students")
    joined_at = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        # unique_together olib tashlandi, chunki student NULL bo'lganda bir nechta NULL yozuvlar tushsa xato beradi.
        pass

    def save(self, *args, **kwargs):
        # Guruhdagi kursning joriy narxini muzlatib saqlaymiz (agar narx berilmagan bo'lsa)
        if self.price is None and self.group and self.group.course:
            self.price = self.group.course.price
        super().save(*args, **kwargs)

    def __str__(self):
        student_name = self.student if self.student else "O'chirilgan Talaba"
        return f"{student_name} in {self.group}"

class GroupTeacher(TenantModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="group_teachers")
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="teacher_groups")

    class Meta:
        unique_together = ('group', 'teacher')

    def __str__(self):
        return f"{self.teacher} for {self.group}"

class TeacherSalaryPayment(TenantModel):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="salary_payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    period = models.CharField(max_length=20) # e.g. "2026-05"

    def __str__(self):
        return f"{self.teacher} - {self.amount} for {self.period}"

class Attendance(TenantModel):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="attendances")
    # TO'G'RILANDI: on_delete=models.SET_NULL qilindi. Eski davomatlar o'chib ketmaydi.
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendances")
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')

    class Meta:
        # unique_together cheklovi olib tashlandi, chunki student NULL bo'lsa baza konflikt beradi.
        pass

    def __str__(self):
        student_name = self.student if self.student else "O'chirilgan Talaba"
        return f"{student_name} - {self.group} ({self.date}): {self.status}"

class LessonSchedule(TenantModel):
    DAY_TYPE_CHOICES = (
        ('even', 'Even Days (Juft kunlar)'),
        ('odd', 'Odd Days (Toq kunlar)'),
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="schedules")
    room_name = models.CharField(max_length=255)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="schedules")
    start_time = models.TimeField()
    end_time = models.TimeField()
    day_type = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default='even')

    def __str__(self):
        return f"{self.group} - {self.room_name} ({self.start_time}-{self.end_time})"

    @classmethod
    def _sync_group_start_time(cls, group_id, organization_id):
        if not group_id:
            return

        next_start_time = (
            cls.objects.filter(group_id=group_id, organization_id=organization_id)
            .order_by('start_time', 'id')
            .values_list('start_time', flat=True)
            .first()
        )
        Group.objects.filter(id=group_id).update(start_time=next_start_time)

    def save(self, *args, **kwargs):
        previous_group_id = None
        previous_organization_id = None
        if self.pk:
            previous = LessonSchedule.objects.filter(pk=self.pk).values('group_id', 'organization_id').first()
            if previous:
                previous_group_id = previous['group_id']
                previous_organization_id = previous['organization_id']

        super().save(*args, **kwargs)
        self._sync_group_start_time(self.group_id, self.organization_id)
        if previous_group_id and previous_group_id != self.group_id:
            self._sync_group_start_time(previous_group_id, previous_organization_id)

    def delete(self, *args, **kwargs):
        group_id = self.group_id
        organization_id = self.organization_id
        super().delete(*args, **kwargs)
        self._sync_group_start_time(group_id, organization_id)

class BalanceHistory(TenantModel):
    # TO'G'RILANDI: on_delete=models.SET_NULL qilindi. Moliyaviy loglar saqlanib qoladi!
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="balance_histories")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=50) # deposit, withdrawal, etc.
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        student_name = self.student if self.student else "O'chirilgan Talaba"
        return f"{student_name} - {self.amount} ({self.transaction_type})"

class Exam(TenantModel):
    name = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="exams")
    group = models.ForeignKey('academics.Group', on_delete=models.CASCADE, related_name="exams", null=True, blank=True)
    date = models.DateField()
    min_score = models.IntegerField(default=60)
    max_score = models.IntegerField(default=100)

    def __str__(self):
        return self.name

class ExamResult(TenantModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="results")
    # TO'G'RILANDI: on_delete=models.SET_NULL qilindi.
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="exam_results")
    score = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        student_name = self.student if self.student else "O'chirilgan Talaba"
        return f"{student_name} - {self.exam.name}: {self.score}"

class LeaveReason(TenantModel):
    reason = models.CharField(max_length=255)

    def __str__(self):
        return self.reason

class LessonTime(TenantModel):
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.name} ({self.start_time}-{self.end_time})"


class OnlineLesson(TenantModel):
    title = models.CharField(max_length=255)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="online_lessons")

    # 🛠️ TO'G'RILANDI: Bo'sh dars ochilishi uchun video_url ixtiyoriy qilindi
    video_url = models.URLField(null=True, blank=True)
    description = models.TextField(null=True, blank=True, verbose_name="Dars tavsifi")
    is_published = models.BooleanField(default=False)

    # 🛠️ Qaysi davomat kunidan ochilganini bilishimiz uchun bog'liqlik zanjiri:
    attendance_date = models.DateField(null=True, blank=True, verbose_name="Bog'langan dars sanasi")

    def __str__(self):
        return self.title

class StudentGroupLeave(TenantModel):
    # TO'G'RILANDI: on_delete=models.SET_NULL qilindi.
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="group_leaves")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="student_leaves")
    leave_reason = models.ForeignKey(LeaveReason, on_delete=models.SET_NULL, null=True, blank=True, related_name="student_leaves")
    leave_date = models.DateField()
    comment = models.TextField(null=True, blank=True)
    refound_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_archived = models.BooleanField(default=False)
    is_sent_to_leads = models.BooleanField(default=False)

    def __str__(self):
        student_name = self.student if self.student else "O'chirilgan Talaba"
        return f"{student_name} left {self.group}"

class StudentPricing(TenantModel):
    # TO'G'RILANDI: on_delete=models.SET_NULL qilindi.
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="pricings")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="student_pricings")
    custom_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        student_name = self.student if self.student else "O'chirilgan Talaba"
        return f"{student_name} - {self.course.name}: {self.custom_price}"

class StudentArchive(TenantModel):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, null=True, blank=True)
    phone = models.CharField(max_length=50)
    email = models.EmailField(null=True, blank=True)
    role = models.CharField(max_length=50, default="Student")
    reason = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    archived_by = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} (Archived)"

class Holiday(TenantModel):
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    student_impact = models.BooleanField(default=False)
    staff_impact = models.BooleanField(default=False)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be earlier than start date.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Homework(TenantModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="homeworks")
    title = models.CharField(max_length=255)
    text = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='group_homeworks/images/', null=True, blank=True)
    video = models.FileField(upload_to='group_homeworks/videos/', null=True, blank=True)
    file = models.FileField(upload_to='group_homeworks/files/', null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_homeworks_created",
    )

    def __str__(self):
        return f"{self.group.name} - {self.title}"

# ================= O'QITUVCHI OYLIK TO'LOVI BO'YICHA KASSA SIGNALI =================
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=TeacherSalaryPayment)
@receiver(post_delete, sender=TeacherSalaryPayment)
def teacher_salary_payment_cashbox_update(sender, instance, **kwargs):
    from finance.models import update_cashbox_balance
    update_cashbox_balance(instance.organization)


@receiver(post_save, sender=Exam)
def exam_internal_notification(sender, instance, created, **kwargs):
    """
    Yangi imtihon yaratilganda guruh o'qituvchilariga tizim ichida bildirishnoma yuboradi.
    """
    if created:
        group = instance.group
        course_name = instance.course.name if instance.course else "Kurs nomi noma'lum"

        if group:
            title = f"Yangi imtihon e'lon qilindi: {instance.name}"
            message = (
                f"Sizning '{group.name}' guruhingiz uchun '{course_name}' kursi bo'yicha imtihon belgilandi.\n"
                f"Sana: {instance.date}\n"
                f"O'tish bali: {instance.min_score} / Max ball: {instance.max_score}"
            )

            from communication.models import Notification

            teachers_to_notify = []
            if group.teacher:
                teachers_to_notify.append(group.teacher)

            additional_teachers = group.group_teachers.select_related('teacher').all()
            for gt in additional_teachers:
                if gt.teacher and gt.teacher not in teachers_to_notify:
                    teachers_to_notify.append(gt.teacher)

            for teacher in teachers_to_notify:
                Notification.objects.create(
                    organization=instance.organization,
                    user=teacher,
                    title=title,
                    message=message,
                    type='info',
                    is_read=False
                )


@receiver(post_save, sender=Holiday)
def holiday_internal_notification(sender, instance, created, **kwargs):
    """
    Yangi dam olish kuni (Bayram) e'lon qilinganda xodimlarga bildirishnoma yuboradi.
    """
    if created and instance.staff_impact:
        end_date_str = f" dan {instance.end_date} gacha" if instance.end_date else " kuni"
        title = f"Diqqat: Dam olish kuni — {instance.name}"
        message = (
            f"Hurmatli hamkasblar, tizimda yangi dam olish kuni e'lon qilindi.\n"
            f"Bayram: {instance.name}\n"
            f"Muddati: {instance.start_date}{end_date_str}.\n"
            f"Shu munosabat bilan dars jadvallaringizni muvofiqlashtirishingizni so'raymiz."
        )

        from django.contrib.auth import get_user_model
        from communication.models import Notification
        User = get_user_model()

        users = User.objects.filter(is_active=True, organization=instance.organization)

        notifications_pool = []
        for user in users:
            notifications_pool.append(
                Notification(
                    organization=instance.organization,
                    user=user,
                    title=title,
                    message=message,
                    type='info',
                    is_read=False
                )
            )

        if notifications_pool:
            Notification.objects.bulk_create(notifications_pool)


class BotMessageTemplate(TenantModel):
    # 🎯 SHABLON QAYSI AUDITORIYA UCHUN EKANLIGINI FILTRLASH
    AUDIENCE_CHOICES = (
        ('leads', 'Lidlar (CRM)'),
        ('students', 'Talabalar (Academics)'),
        ('staff', 'Xodimlar (Staff)'),
    )

    TEMPLATE_TYPES = (
        # CRM (Lidlar) uchun shablonlar
        ('lead_marketing', 'Lid: Reklama/Aksiya xabari'),
        ('lead_holiday', 'Lid: Bayram tabrigi'),
        ('lead_followup', 'Lid: Qayta aloqa/Eslatma'),

        # Talabalar uchun shablonlar
        ('remind', 'Talaba: Dars eslatmasi (Darsga chaqiriq)'),
        ('payment_due', 'Talaba: To‘lov vaqti kelganda ogohlantirish'),
        ('payment_success', 'Talaba: To‘lov muvaffaqiyatli bo‘lganda chek'),
        ('news', 'Talaba: Umumiy yangiliklar'),

        # Ota-onalar uchun shablonlar
        ('parent_check_in', 'Ota-ona: Farzandi darsga kelganda'),
        ('parent_check_out', 'Ota-ona: Dars tugaganda (ketganda)'),
        ('parent_exam_result', 'Ota-ona: Imtihon baholari chiqganda'),
        ('parent_payment_due', 'Ota-ona: To‘lov vaqti kelganda'),

        # Xodimlar uchun shablonlar
        ('staff_general_news', 'Xodimlar: Boshliqdan umumiy xabar/topshiriq'),
        ('staff_salary_remind', 'Xodimlar: Oylik to‘lov eslatmasi'),
        ('staff_holiday_remind', 'Xodimlar: Bayram va dam olish kuni eslatmasi'),
    )

    title = models.CharField(max_length=150, verbose_name="Shablon nomi")
    target_audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='students',
                                       verbose_name="Kimlar uchun")
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES, verbose_name="Turi")
    text = models.TextField(
        verbose_name="Xabar matni",
        help_text="O'zgaruvchilarni jingalak qavs ichida yozing, masalan: {first_name}, {balance}, {section_name}"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faolmi?")

    class Meta:
        # unique_together olib tashlandi, chunki bitta turda bir nechta marketing SMS shablonlari bo'lishi mumkin (Rasmda ko'ringandek)
        verbose_name = "Bot Xabar Shabloni"
        verbose_name_plural = "Bot Xabar Shablonlari"

    def __str__(self):
        return f"[{self.get_target_audience_display()}] {self.title}"

@receiver(post_save, sender=Attendance)
def notify_parent_attendance(sender, instance, created, **kwargs):
    """
    Davomat o'zgartirilganda yoki yaratilganda ota-onaga Telegram orqali xabar beradi.
    """
    student = instance.student
    if not student:
        return

    # Ota-onaning Telegram chat ID'larini yig'amiz
    parent_chats = []
    if student.father_telegram_chat_id:
        parent_chats.append(student.father_telegram_chat_id)
    if student.mother_telegram_chat_id:
        parent_chats.append(student.mother_telegram_chat_id)

    if not parent_chats:
        return

    from organizations.models import TelegramNotificationSetting
    setting = TelegramNotificationSetting.objects.filter(organization=student.organization).first()
    if not setting or not setting.parent_bot_token:
        return

    # Davomat statusiga qarab xabar tayyorlaymiz
    if instance.status == 'present':
        status_text = "darsga keldi. ✅"
    elif instance.status == 'absent':
        status_text = "darsga kelmadi! ❌"
    elif instance.status == 'late':
        status_text = "darsga kechikib keldi. ⚠️"
    elif instance.status == 'excused':
        status_text = "darsga sababli kelmadi. 📁"
    else:
        return

    # Shablonni qidiramiz
    shablon = BotMessageTemplate.objects.filter(
        organization=student.organization, template_type='parent_check_in', is_active=True
    ).first()

    default_text = "Hurmatli ota-ona, farzandingiz {first_name} bugun {status_text}"
    shablon_text = shablon.text if shablon else default_text

    # O'zgaruvchilarni almashtiramiz
    tayyor_matn = shablon_text.replace("{first_name}", student.first_name)
    tayyor_matn = tayyor_matn.replace("{last_name}", student.last_name or "")
    tayyor_matn = tayyor_matn.replace("{group_name}", instance.group.name if instance.group else "")
    tayyor_matn = tayyor_matn.replace("{status_text}", status_text)

    # Telegram bot orqali jo'natish
    import requests
    for chat_id in parent_chats:
        try:
            url = f"https://api.telegram.org/bot{setting.parent_bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': tayyor_matn,
                'parse_mode': 'HTML'
            }
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"Error sending attendance notification to parent {chat_id}: {str(e)}")


class GroupLesson(TenantModel):
    """Guruhning yo'qlamadan mustaqil, kalendardagi har bitta dars kuni"""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="lessons")
    date = models.DateField(verbose_name="Dars sanasi")

    # Mavzu va izoh
    title = models.CharField(max_length=255, null=True, blank=True, verbose_name="Dars mavzusi")
    description = models.TextField(null=True, blank=True, verbose_name="Dars izohi")

    # Bekor qilish va ko'chirish maydonlari
    is_canceled = models.BooleanField(default=False, verbose_name="Dars bekor qilinganmi?")
    original_date = models.DateField(null=True, blank=True, verbose_name="Asl sanasi")

    def __str__(self):
        return f"{self.group.name} - {self.date} - {self.title or 'Mavzusiz'}"



@receiver(post_save, sender=GroupLesson)
def sync_group_lesson_with_lms(sender, instance, created, **kwargs):
    if not instance.title:
        return

    # Guruh dars kuniga qarab LMS darsini qidiramiz
    online_lesson = OnlineLesson.objects.filter(
        group=instance.group,
        video_url__isnull=True, # faqat avtomat ochilgan bo'sh darslarni topish uchun
        title=instance.title
    ).first()

    if not online_lesson:
        OnlineLesson.objects.create(
            organization=instance.organization,
            group=instance.group,
            title=instance.title,
            is_published=True
        )


import datetime


def generate_group_lessons(group_instance):
    """Guruhning boshlanish va tugash sanasi oralig'idagi dars kunlarini yaratadi"""
    if not group_instance.start_date or not group_instance.end_date:
        return

    current_date = group_instance.start_date
    delta = datetime.timedelta(days=1)

    # Guruhning dars kunlari turi (Juft / Toq / Har kuni)
    # Kodingizdagi day_type qiymatlariga qarab moslashtiring (masalan: 'even', 'odd')
    day_type = getattr(group_instance, 'day_type', '').lower()

    lessons_to_create = []

    while current_date <= group_instance.end_date:
        # Hafta kuni indeksi: 0=Dushanba, 1=Seshanba, 2=Chorshanba, 3=Payshanba, 4=Juma, 5=Shanba, 6=Yakshanba
        weekday = current_date.weekday()

        should_create = False
        if 'even' in day_type or 'juft' in day_type:  # Se-Pay-Sha
            if weekday in [1, 3, 5]:
                should_create = True
        elif 'odd' in day_type or 'toq' in day_type:  # Du-Chor-Ju
            if weekday in [0, 2, 4]:
                should_create = True
        else:  # Agar aniq belgilanmagan bo'lsa, Yakshanbadan tashqari hamma kunlar
            if weekday != 6:
                should_create = True

        if should_create:
            # Agar bu sana uchun dars allaqachon yaratilmagan bo'lsa
            if not GroupLesson.objects.filter(group=group_instance, date=current_date).exists():
                lessons_to_create.append(
                    GroupLesson(
                        organization=group_instance.organization,
                        group=group_instance,
                        date=current_date
                    )
                )

        current_date += delta

    if lessons_to_create:
        GroupLesson.objects.bulk_create(lessons_to_create)


# Guruh saqlanganda dars kunlarini generatsiya qilish signali
@receiver(post_save, sender=Group)
def trigger_lesson_generation(sender, instance, created, **kwargs):
    # Tracker xatoligini oldini olish uchun to'g'ridan-to'g'ri funksiyani chaqiramiz
    generate_group_lessons(instance)