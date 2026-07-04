"""
Bu buyruqni loyihangizda quyidagi joyga qo'ying:
finance/management/commands/backfill_transactions.py
(finance/management/ va finance/management/commands/ papkalarida bo'sh __init__.py fayllari bo'lishi kerak)

Ishga tushirish:
    python manage.py backfill_transactions

Bu buyruq:
1. Barcha mavjud Payment, Expense, CashTransaction yozuvlari uchun
   mos Transaction ("ko'zgu") yozuvini yaratadi (agar hali yo'q bo'lsa).
2. Barcha Cashbox balansini Transaction jadvalidan qayta hisoblaydi.

Xavfsiz: bir necha marta ishga tushirilsa ham xato bermaydi va
ma'lumotni ikki marta yaratmaydi (get_or_create asosida ishlaydi).
"""
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.db.models import Sum
from decimal import Decimal

from finance.models import Payment, Expense, CashTransaction, Transaction, Cashbox


class Command(BaseCommand):
    help = "Eski Payment/Expense/CashTransaction yozuvlarini Transaction jadvaliga ko'chiradi va kassa balanslarini qayta hisoblaydi"

    def handle(self, *args, **options):
        created_count = 0

        with db_transaction.atomic():
            # 1. Paymentlar
            for payment in Payment.objects.filter(cashbox__isnull=False).select_related('student', 'employee', 'cashbox', 'organization'):
                if hasattr(payment, 'mirrored_transaction'):
                    continue
                student_str = payment.student if payment.student else "O'chirilgan Talaba"
                Transaction.objects.create(
                    organization=payment.organization,
                    cashbox=payment.cashbox,
                    amount=payment.amount,
                    type='INCOME',
                    category='DIRECT',
                    student=payment.student,
                    employee=payment.employee,
                    description=f"To'lov: {student_str} ({payment.payment_method})",
                    source_payment=payment,
                )
                created_count += 1

            # 2. Xarajatlar
            for expense in Expense.objects.filter(cashbox__isnull=False).select_related('category', 'cashbox', 'organization'):
                if hasattr(expense, 'mirrored_transaction'):
                    continue
                category_name = expense.category.name if expense.category else "Xarajat"
                Transaction.objects.create(
                    organization=expense.organization,
                    cashbox=expense.cashbox,
                    amount=expense.amount,
                    type='EXPENSE',
                    category='DIRECT',
                    description=f"Xarajat: {category_name}",
                    source_expense=expense,
                )
                created_count += 1

            # 3. Qo'lda kirim/chiqimlar
            for ct in CashTransaction.objects.select_related('student', 'employee', 'cashbox', 'organization'):
                if hasattr(ct, 'mirrored_transaction'):
                    continue
                tx_type = 'INCOME' if ct.transaction_type == 'kirim' else 'EXPENSE'
                Transaction.objects.create(
                    organization=ct.organization,
                    cashbox=ct.cashbox,
                    amount=ct.amount,
                    type=tx_type,
                    category='DIRECT',
                    student=ct.student,
                    employee=ct.employee,
                    description=ct.comment or ct.category_name or '',
                    source_cashtransaction=ct,
                )
                created_count += 1

            # 4. Barcha kassalar balansini Transaction'dan qayta hisoblash
            for cashbox in Cashbox.objects.all():
                income = Transaction.objects.filter(cashbox=cashbox, type='INCOME').aggregate(
                    total=Sum('amount'))['total'] or Decimal('0.00')
                expense = Transaction.objects.filter(cashbox=cashbox, type='EXPENSE').aggregate(
                    total=Sum('amount'))['total'] or Decimal('0.00')
                Cashbox.objects.filter(pk=cashbox.pk).update(balance=income - expense)

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor! {created_count} ta Transaction yozuvi yaratildi va barcha kassa balanslari qayta hisoblandi."
        ))