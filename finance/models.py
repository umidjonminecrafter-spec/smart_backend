from django.db import models
from django.conf import settings
from organizations.models import TenantModel
from academics.models import Student, TeacherSalaryPayment


class ExpenseCategory(TenantModel):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class ExpenseSubcategory(TenantModel):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.category.name} -> {self.name}"


class TransactionCategory(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=[('INCOME', 'Kirim'), ('EXPENSE', 'Chiqim')])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.type})"


class Expense(TenantModel):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name="expenses")
    subcategory = models.ForeignKey(ExpenseSubcategory, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="expenses")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    date = models.DateField()
    cashbox = models.ForeignKey('Cashbox', on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")

    def __str__(self):
        return f"{self.category.name}: {self.amount} ({self.date})"


class MonthlyIncome(TenantModel):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()

    def __str__(self):
        return f"Income: {self.amount} ({self.date})"


class Payment(TenantModel):
    # TO'G'RILANDI: SET_NULL qilindi - talaba o'chsa to'lov loglari saqlanadi
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    cashbox = models.ForeignKey('Cashbox', on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    payment_method = models.CharField(max_length=100)  # e.g. Cash, Card, Bank
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="payments")
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        student_str = self.student if self.student else "O'chirilgan Talaba"
        return f"{student_str} - {self.amount} ({self.date})"


class Sale(TenantModel):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    product_or_course = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.product_or_course} - {self.amount} ({self.date})"


class Bonus(TenantModel):
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bonuses")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    date = models.DateField()

    def __str__(self):
        return f"Bonus: {self.employee} - {self.amount} ({self.date})"


class Fine(TenantModel):
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fines")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    date = models.DateField()

    def __str__(self):
        return f"Fine: {self.employee} - {self.amount} ({self.date})"


class Salary(TenantModel):
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid'),
    )
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="salaries")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')

    def __str__(self):
        return f"Salary: {self.employee} - {self.amount} ({self.status})"


class TeacherSalaryRule(TenantModel):
    RULE_TYPE_CHOICES = (
        ('fixed', 'Fixed Monthly'),
        ('per_student', 'Per Student enrolled'),
        ('per_hour', 'Per Hour taught'),
        ('percentage', 'Percentage of student fees'),
    )
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="salary_rules")
    rule_type = models.CharField(max_length=50, choices=RULE_TYPE_CHOICES)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=20)  # e.g. YYYY-MM
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Rule ({self.rule_type}): {self.teacher} - {self.rate} for {self.period}"


class TeacherSalaryCalculation(TenantModel):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="salary_calculations")
    calculated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    period = models.CharField(max_length=20)  # e.g. YYYY-MM
    details = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Calc: {self.teacher} - {self.calculated_amount} for {self.period}"


class Cashbox(TenantModel):
    name = models.CharField(max_length=255)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class FinanceSetting(TenantModel):
    """Menejer bonus/jarimalari, Moliya bo'limi, KPI va Talabalar avtochegirmasi sozlamalari"""

    # 1. Menejer bonuslari va jarimalari (Dinamik JSON ro'yxat)
    is_bonus_enabled = models.BooleanField(default=True)
    bonus_types = models.JSONField(default=list, blank=True)  # [{"id": 1, "name": "Nomi", "amount": 50000}]

    is_penalty_enabled = models.BooleanField(default=True)
    penalty_types = models.JSONField(default=list, blank=True)  # [{"id": 1, "name": "Nomi", "amount": 20000}]

    # 2. Moliya bo'limi bonusi Sozlamalari (Foizli va soni bo'yicha)
    is_percent_bonus_enabled = models.BooleanField(default=False)
    student_payment_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    debtor_balance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    is_count_bonus_enabled = models.BooleanField(default=False)
    has_money_students_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    debtor_students_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # 3. KPI Sozlamalari
    kpi_settings = models.JSONField(default=dict, blank=True)

    # 5. Talabalar uchun avtochegirma (Faqat bonus_types yoqilgan bo'lsa ishlaydi)
    is_auto_discount_enabled = models.BooleanField(default=False)
    two_groups_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    three_groups_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    four_groups_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Finance Settings - {self.organization.name if self.organization else 'No Org'}"

    def save(self, *args, **kwargs):
        # Talab: Bonus turi o'chsa, avtochegirmani ham majburiy o'chiramiz (yoqish mumkin emas)
        if not self.is_bonus_enabled:
            self.is_auto_discount_enabled = False
        super().save(*args, **kwargs)


class CashTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('kirim', 'Kirim'),
        ('chiqim', 'Chiqim'),
    )

    PAYMENT_METHODS = (
        ('naqd', 'Naqd'),
        ('plastik', 'Plastik'),
        ('terminal', 'Terminal'),
    )

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    cashbox = models.ForeignKey(Cashbox, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHODS)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()

    # Kim xarajat qilgani yoki qaysi o'quvchi to'lov qilgani
    student = models.ForeignKey('academics.Student', on_delete=models.SET_NULL, null=True, blank=True)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    category_name = models.CharField(max_length=255, null=True, blank=True)  # Marker, Hodimga oylik va h.k.
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StaffSalaryPercent(TenantModel):
    """4. Xodimlar va o'qituvchilar uchun oylik foiz stavkalari (Dinamik stavkalar qo'shish)"""
    name = models.CharField(max_length=255)  # Masalan: "Stajor o'qituvchi", "Katta o'qituvchi"
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    comment = models.CharField(max_length=255, null=True, blank=True, verbose_name="Izoh")

    def __str__(self):
        return f"{self.name} ({self.percent}%)"


# ================= MOLIYA KASSA INTEGRATSIYASI SIGNALLARI =================
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver


# ESKI KOD OLIB TASHLANDI: bu yerda avval `update_specific_cashbox` funksiyasi
# Payment/Expense/CashTransaction'dan kassa balansini NOLDAN qayta hisoblardi.
# Muammo: bu formula TeacherSalaryCalculateView, CashTransferAPIView va
# FinanceActionViewSet'da QO'LDA qilingan balans o'zgarishlarini bilmasdi -
# shuning uchun ular keyingi har qanday to'lov/xarajatda "yo'qolib" ketardi.
# Yangi, yagona (single-source-of-truth) yechim fayl OXIRIDA, Transaction
# modeli e'lon qilingandan keyin joylashtirilgan (pastga qarang).


# ================= TELEGRAM BOT ORQALI XABARNOMALAR INTEGRATSIYASI =================

def send_telegram_payment_notification(organization, message_text, setting_type):
    """
    Tashkilotning Telegram sozlamalariga asosan xabar yuboradi.
    setting_type: 'student_payments', 'teacher_salaries', 'expenses', 'other_payments'
    """
    if not organization:
        return

    try:
        from organizations.models import TelegramNotificationSetting
        setting = TelegramNotificationSetting.objects.filter(organization=organization).first()
        if not setting or not setting.is_active or not setting.bot_token or not setting.chat_ids:
            return

        # Xabarnoma turi yoqilganligini tekshiramiz
        if not getattr(setting, setting_type, False):
            return

        import urllib.request
        import json
        import threading

        chat_ids_list = [cid.strip() for cid in setting.chat_ids.replace(',', ' ').split() if cid.strip()]

        def worker():
            for chat_id in chat_ids_list:
                try:
                    url = f"https://api.telegram.org/bot{setting.bot_token}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': message_text,
                        'parse_mode': 'HTML'
                    }
                    data = json.dumps(payload).encode('utf-8')
                    req = urllib.request.Request(
                        url,
                        data=data,
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                    with urllib.request.urlopen(req, timeout=8) as res:
                        res.read()
                except Exception as e:
                    print(f"Error sending telegram payment notification to {chat_id}: {str(e)}")

        threading.Thread(target=worker, daemon=True).start()
    except Exception as e:
        print(f"Error initiating telegram payment notification: {str(e)}")


@receiver(post_save, sender=Payment)
def payment_telegram_notification(sender, instance, created, **kwargs):
    if created:
        # TO'G'RILANDI: Talaba o'chgan holatda Crash berishini oldi olindi
        student_name = f"{instance.student.first_name} {instance.student.last_name or ''}" if instance.student else "O'chirilgan Talaba"
        branch_name = instance.branch.name if hasattr(instance, 'branch') and instance.branch else "Noma'lum"
        comment_str = f"\n📝 Izoh: {instance.comment}" if instance.comment else ""

        try:
            amount_formatted = f"{int(instance.amount):,}".replace(",", " ")
        except:
            amount_formatted = str(instance.amount)

        text = (
            f"<b>Kirim (Talaba to'lovi)</b> 📥\n\n"
            f"👤 Talaba: {student_name}\n"
            f"💰 Summa: {amount_formatted} UZS\n"
            f"💳 To'lov turi: {instance.payment_method}\n"
            f"🗓 Sana: {instance.date}\n"
            f"🏢 Filial: {branch_name}"
            f"{comment_str}"
        )
        send_telegram_payment_notification(instance.organization, text, 'student_payments')


@receiver(post_save, sender=Expense)
def expense_telegram_notification(sender, instance, created, **kwargs):
    if created:
        category_name = instance.category.name if instance.category else "Noma'lum"
        subcategory_name = f" -> {instance.subcategory.name}" if instance.subcategory else ""
        branch_name = instance.branch.name if hasattr(instance, 'branch') and instance.branch else "Noma'lum"
        desc_str = f"\n📝 Izoh: {instance.description}" if instance.description else ""

        try:
            amount_formatted = f"{int(instance.amount):,}".replace(",", " ")
        except:
            amount_formatted = str(instance.amount)

        text = (
            f"<b>Chiqim (Xarajat)</b> 📉\n\n"
            f"📁 Kategoriya: {category_name}{subcategory_name}\n"
            f"💰 Summa: {amount_formatted} UZS\n"
            f"🗓 Sana: {instance.date}\n"
            f"🏢 Filial: {branch_name}"
            f"{desc_str}"
        )
        send_telegram_payment_notification(instance.organization, text, 'expenses')


@receiver(post_save, sender=Salary)
def salary_telegram_notification(sender, instance, created, **kwargs):
    if instance.status == 'paid':
        is_newly_paid = False
        if created:
            is_newly_paid = True
        else:
            old_instance = Salary.objects.filter(pk=instance.pk).exclude(status='paid').first()
            if old_instance:
                is_newly_paid = True

        if is_newly_paid:
            employee_name = f"{instance.employee.first_name} {instance.employee.last_name or ''}" if instance.employee else "Noma'lum"
            branch_name = instance.branch.name if hasattr(instance, 'branch') and instance.branch else "Noma'lum"

            try:
                amount_formatted = f"{int(instance.amount):,}".replace(",", " ")
            except:
                amount_formatted = str(instance.amount)

            text = (
                f"<b>Chiqim (Xodim maoshi)</b> 💸\n\n"
                f"👤 Xodim: {employee_name}\n"
                f"💰 Summa: {amount_formatted} UZS\n"
                f"🗓 Sana: {instance.date}\n"
                f"🏢 Filial: {branch_name}"
            )
            send_telegram_payment_notification(instance.organization, text, 'teacher_salaries')


@receiver(post_save, sender=TeacherSalaryPayment)
def teacher_salary_telegram_notification(sender, instance, created, **kwargs):
    if created:
        teacher_name = f"{instance.teacher.first_name} {instance.teacher.last_name or ''}" if instance.teacher else "Noma'lum"
        branch_name = instance.branch.name if hasattr(instance, 'branch') and instance.branch else "Noma'lum"

        try:
            amount_formatted = f"{int(instance.amount):,}".replace(",", " ")
        except:
            amount_formatted = str(instance.amount)

        text = (
            f"<b>Chiqim (O'qituvchi maoshi)</b> 💸\n\n"
            f"👤 O'qituvchi: {teacher_name}\n"
            f"💰 Summa: {amount_formatted} UZS\n"
            f"🗓 Davr: {instance.period}\n"
            f"🏢 Filial: {branch_name}"
        )
        send_telegram_payment_notification(instance.organization, text, 'teacher_salaries')


@receiver(post_save, sender=MonthlyIncome)
def monthly_income_telegram_notification(sender, instance, created, **kwargs):
    if created:
        branch_name = instance.branch.name if hasattr(instance, 'branch') and instance.branch else "Noma'lum"
        try:
            amount_formatted = f"{int(instance.amount):,}".replace(",", " ")
        except:
            amount_formatted = str(instance.amount)

        text = (
            f"<b>Kirim (Boshqa kirim)</b> 📥\n\n"
            f"💰 Summa: {amount_formatted} UZS\n"
            f"🗓 Sana: {instance.date}\n"
            f"🏢 Filial: {branch_name}"
        )
        send_telegram_payment_notification(instance.organization, text, 'other_payments')


@receiver(post_save, sender=Sale)
def sale_telegram_notification(sender, instance, created, **kwargs):
    if created:
        branch_name = instance.branch.name if hasattr(instance, 'branch') and instance.branch else "Noma'lum"
        try:
            amount_formatted = f"{int(instance.amount):,}".replace(",", " ")
        except:
            amount_formatted = str(instance.amount)

        text = (
            f"<b>Kirim (Sotuv/Kurs)</b> 📥\n\n"
            f"📦 Mahsulot/Kurs: {instance.product_or_course}\n"
            f"💰 Summa: {amount_formatted} UZS\n"
            f"🗓 Sana: {instance.date}\n"
            f"🏢 Filial: {branch_name}"
        )
        send_telegram_payment_notification(instance.organization, text, 'other_payments')


# ================= TALABA BALANSI INTEGRATSIYASI SIGNALLARI =================

@receiver(pre_save, sender=Payment)
def payment_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_payment = Payment.objects.get(pk=instance.pk)
            instance._old_amount = old_payment.amount
            instance._old_student = old_payment.student
        except Payment.DoesNotExist:
            instance._old_amount = None
            instance._old_student = None
    else:
        instance._old_amount = None
        instance._old_student = None


@receiver(post_save, sender=Payment)
def payment_student_balance_update(sender, instance, created, **kwargs):
    student = instance.student
    # TO'G'RILANDI: Agar talaba bo'lsa (NULL bo'lmasa) balansi yangilanadi
    if student:
        if created:
            student.balance += instance.amount
            student.save(update_fields=['balance'])
        else:
            old_amount = getattr(instance, '_old_amount', None)
            old_student = getattr(instance, '_old_student', None)

            if old_amount is not None:
                if old_student and old_student != instance.student:
                    # Eski talaba hali ham bazada bo'lsa uning balansini to'g'rilaymiz
                    old_student.balance -= old_amount
                    old_student.save(update_fields=['balance'])

                    student.balance += instance.amount
                    student.save(update_fields=['balance'])
                else:
                    diff = instance.amount - old_amount
                    if diff != 0:
                        student.balance += diff
                        student.save(update_fields=['balance'])


@receiver(post_delete, sender=Payment)
def payment_student_balance_delete(sender, instance, **kwargs):
    student = instance.student
    # TO'G'RILANDI: Agar talaba o'chirilgan bo'lsa, signal xatolik bermay o'tib ketadi.
    if student:
        student.balance -= instance.amount
        student.save(update_fields=['balance'])


from django.contrib.auth import get_user_model

# finance/models.py faylining oxiriga qo'shing:
User = get_user_model()


class Transaction(TenantModel):
    TRANSACTION_TYPES = [
        ('INCOME', 'Kirim'),
        ('EXPENSE', 'Chiqim'),
    ]

    # Qaysi bo'limdan tranzaksiya qo'shilganini bilish uchun
    CATEGORY_CHOICES = [
        ('DIRECT', 'To\'g\'ridan-to\'g\'ri'),
        ('BONUS', 'Bonus'),
        ('PENALTY', 'Jarima'),
        ('VOUCHER', 'Voucher / Chegirma'),
        ('SALARY', 'Oylik to\'lovi'),
    ]

    cashbox = models.ForeignKey('Cashbox', on_delete=models.PROTECT, related_name='finance_transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='DIRECT')

    # Kim tomonidan amalga oshirildi yoki kimga tegishli
    student = models.ForeignKey('academics.Student', on_delete=models.SET_NULL, null=True, blank=True)
    employee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # YANGI: Transaction endi YAGONA haqiqat manbai (single source of truth).
    # Payment/Expense/CashTransaction yaratilganda pastdagi signallar orqali
    # shu yerga "ko'zgu" (mirror) yozuv avtomatik qo'shiladi. Shu orqali
    # kassa balansi doim FAQAT shu jadvaldan hisoblanadi va hech qachon
    # ikki xil hisob-kitob usuli bir-biriga zid kelmaydi.
    source_payment = models.OneToOneField(
        'Payment', on_delete=models.CASCADE, null=True, blank=True, related_name='mirrored_transaction'
    )
    source_expense = models.OneToOneField(
        'Expense', on_delete=models.CASCADE, null=True, blank=True, related_name='mirrored_transaction'
    )
    source_cashtransaction = models.OneToOneField(
        'CashTransaction', on_delete=models.CASCADE, null=True, blank=True, related_name='mirrored_transaction'
    )


class FinanceAction(TenantModel):
    ACTION_TYPES = [
        ('BONUS', 'Bonus'),
        ('PENALTY', 'Jarima'),
    ]
    TARGET_TYPES = [
        ('STUDENT', 'Talaba'),
        ('EMPLOYEE', 'Xodim'),
    ]
    action_type = models.CharField(max_length=10, choices=ACTION_TYPES)
    target_type = models.CharField(max_length=10, choices=TARGET_TYPES)

    student = models.ForeignKey('academics.Student', on_delete=models.SET_NULL, null=True, blank=True)
    # Bu yerda to'g'ridan-to'g'ri tizimdagi User (Xodim)ga ulaymiz:
    employee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(null=True, blank=True)
    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# =====================================================================================
# YAGONA (SINGLE SOURCE OF TRUTH) KASSA BALANSI TIZIMI
# =====================================================================================
# G'OYA: Cashbox.balance HAR DOIM faqat Transaction jadvalidan hisoblanadi.
# Payment, Expense, CashTransaction o'z holicha kassa balansini o'zgartirmaydi -
# ular saqlanganda/o'zgartirilganda/o'chirilganda pastdagi signallar orqali
# mos Transaction yozuvi avtomatik yaratiladi/yangilanadi/o'chiriladi.
# Bonus, Jarima, Oylik to'lovi va Kassalararo o'tkazma views.py'da to'g'ridan-to'g'ri
# Transaction yaratadi - ular ham xuddi shu formula orqali balansga ta'sir qiladi.
# Natijada BUTUN tizimda kassa balansini o'zgartiradigan FAQAT BITTA yo'l qoladi.
# =====================================================================================

def _sync_transaction_mirror(source_field_name, instance, tx_type, category, cashbox, description):
    """
    Payment/Expense/CashTransaction obyekti uchun mos Transaction ('ko'zgu') yozuvini
    yaratadi yoki (agar allaqachon mavjud bo'lsa) yangilaydi.
    """
    if not cashbox:
        # Kassasiz obyekt uchun mos Transaction bo'lishi shart emas - eskisi bo'lsa o'chiramiz
        existing = getattr(instance, 'mirrored_transaction', None)
        if existing:
            existing.delete()
        return

    lookup = {source_field_name: instance}
    tx = Transaction.objects.filter(**lookup).first()

    values = {
        'organization': instance.organization,
        'cashbox': cashbox,
        'amount': instance.amount,
        'type': tx_type,
        'category': category,
        'student': getattr(instance, 'student', None),
        'employee': getattr(instance, 'employee', None),
        'description': description,
    }

    if tx:
        for field, value in values.items():
            setattr(tx, field, value)
        tx.save()
    else:
        Transaction.objects.create(**{**values, source_field_name: instance})


def _delete_transaction_mirror(instance):
    existing = getattr(instance, 'mirrored_transaction', None)
    if existing:
        existing.delete()


@receiver(post_save, sender=Payment)
def payment_transaction_mirror_sync(sender, instance, created, **kwargs):
    student_str = instance.student if instance.student else "O'chirilgan Talaba"
    _sync_transaction_mirror(
        'source_payment', instance, 'INCOME', 'DIRECT', instance.cashbox,
        description=f"To'lov: {student_str} ({instance.payment_method})"
    )


@receiver(post_delete, sender=Payment)
def payment_transaction_mirror_delete(sender, instance, **kwargs):
    _delete_transaction_mirror(instance)


@receiver(post_save, sender=Expense)
def expense_transaction_mirror_sync(sender, instance, created, **kwargs):
    category_name = instance.category.name if instance.category else "Xarajat"
    _sync_transaction_mirror(
        'source_expense', instance, 'EXPENSE', 'DIRECT', instance.cashbox,
        description=f"Xarajat: {category_name}"
    )


@receiver(post_delete, sender=Expense)
def expense_transaction_mirror_delete(sender, instance, **kwargs):
    _delete_transaction_mirror(instance)


@receiver(post_save, sender=CashTransaction)
def cashtransaction_transaction_mirror_sync(sender, instance, created, **kwargs):
    tx_type = 'INCOME' if instance.transaction_type == 'kirim' else 'EXPENSE'
    _sync_transaction_mirror(
        'source_cashtransaction', instance, tx_type, 'DIRECT', instance.cashbox,
        description=instance.comment or instance.category_name or ''
    )


@receiver(post_delete, sender=CashTransaction)
def cashtransaction_transaction_mirror_delete(sender, instance, **kwargs):
    _delete_transaction_mirror(instance)


def update_cashbox_balance(organization):
    """
    Backwards compatibility stub. Kassa balansi endi tranzaksiyalar asosida 
    avtomatik ravishda recompute_cashbox_balance orqali hisoblanadi.
    """
    pass


@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def recompute_cashbox_balance(sender, instance, **kwargs):
    """
    Kassa balansini FAQAT Transaction jadvalidan qayta hisoblaydigan
    YAGONA funksiya. Boshqa hech qayerda cashbox.balance qo'lda o'zgartirilmasligi kerak.
    """
    from django.db.models import Sum
    from decimal import Decimal

    cashbox = instance.cashbox
    if not cashbox:
        return

    income = Transaction.objects.filter(cashbox=cashbox, type='INCOME').aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')
    expense = Transaction.objects.filter(cashbox=cashbox, type='EXPENSE').aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')

    Cashbox.objects.filter(pk=cashbox.pk).update(balance=income - expense)


# ================= O'QITUVCHI OYLIK TO'LOVI BO'YICHA TRANZAKSIYA SINXRONIZATSIYASI =================
from academics.models import TeacherSalaryPayment

@receiver(post_save, sender=TeacherSalaryPayment)
def teacher_salary_payment_transaction_sync(sender, instance, created, **kwargs):
    # Tashkilotning birinchi kassasini topamiz (afzalroq nomi 'Asosiy Kassa' yoki o'shanga o'xshash bo'lgan)
    cashbox = Cashbox.objects.filter(organization=instance.organization, name__icontains="asosiy").first()
    if not cashbox:
        cashbox = Cashbox.objects.filter(organization=instance.organization).first()

    if not cashbox:
        return

    teacher_name = f"{instance.teacher.first_name} {instance.teacher.last_name or ''}".strip() or instance.teacher.username
    desc = f"O'qituvchi maosh to'lovi: {teacher_name} (SglID: {instance.id})"

    tx = Transaction.objects.filter(
        organization=instance.organization,
        description__endswith=f"(SglID: {instance.id})"
    ).first()

    if tx:
        tx.cashbox = cashbox
        tx.amount = instance.amount
        tx.save()
    else:
        Transaction.objects.create(
            organization=instance.organization,
            cashbox=cashbox,
            amount=instance.amount,
            type='EXPENSE',
            category='SALARY',
            employee=instance.teacher,
            description=desc
        )


@receiver(post_delete, sender=TeacherSalaryPayment)
def teacher_salary_payment_transaction_delete(sender, instance, **kwargs):
    Transaction.objects.filter(
        organization=instance.organization,
        description__endswith=f"(SglID: {instance.id})"
    ).delete()