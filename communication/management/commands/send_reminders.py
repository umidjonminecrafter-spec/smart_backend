import datetime
from django.core.management.base import BaseCommand
from organizations.models import Subscription
from communication.models import SubscriptionReminder, ReminderLog, Notification


def send_reminders():
    today = datetime.date.today()
    sent = 0

    reminders = SubscriptionReminder.objects.filter(is_active=True)

    for reminder in reminders:

        # 1. Tarif tugashidan oldin
        if reminder.trigger == 'subscription_expiry':
            target_date = today + datetime.timedelta(days=reminder.days_before)
            subscriptions = Subscription.objects.filter(
                end_date=target_date,
                is_active=True
            ).select_related('organization', 'tariff')

            for sub in subscriptions:
                org = sub.organization

                # Bugun allaqachon yuborilganmi?
                already_sent = ReminderLog.objects.filter(
                    reminder=reminder,
                    organization=org,
                    sent_at__date=today
                ).exists()
                if already_sent:
                    continue

                message = (
                    reminder.template.body.format(
                        org_name=org.name,
                        days_left=reminder.days_before,
                        tariff_name=sub.tariff.name if sub.tariff else '',
                        balance=sub.balance,
                    ) if reminder.template else
                    reminder.custom_message or
                    f"Tarifingiz {reminder.days_before} kun ichida tugaydi. "
                    f"Uzluksiz xizmat uchun tarifni yangilang."
                )

                # Notification yaratish
                Notification.objects.create(
                    organization=org,
                    title="Tarif tugashidan oldin eslatma",
                    message=message,
                    type='subscription_expiry'
                )

                ReminderLog.objects.create(
                    reminder=reminder,
                    organization=org,
                    phone='',
                    message=message,
                    status='sent'
                )
                sent += 1

        # 2. Balance kam qolganda
        elif reminder.trigger == 'balance_low':
            subscriptions = Subscription.objects.filter(
                balance__lte=reminder.balance_threshold,
                is_active=True
            ).select_related('organization')

            for sub in subscriptions:
                org = sub.organization

                already_sent = ReminderLog.objects.filter(
                    reminder=reminder,
                    organization=org,
                    sent_at__date=today
                ).exists()
                if already_sent:
                    continue

                message = (
                    reminder.template.body.format(
                        org_name=org.name,
                        balance=sub.balance,
                        days_left=0,
                        tariff_name='',
                    ) if reminder.template else
                    reminder.custom_message or
                    f"Balancingiz {sub.balance} UZS qoldi. "
                    f"Uzluksiz xizmat uchun balansingizni to'ldiring."
                )

                Notification.objects.create(
                    organization=org,
                    title="Balance kam qoldi",
                    message=message,
                    type='balance_low'
                )

                ReminderLog.objects.create(
                    reminder=reminder,
                    organization=org,
                    phone='',
                    message=message,
                    status='sent'
                )
                sent += 1

    # 3. Xodimlarning tug'ilgan kunlari (2 kun qolganda CEO ga yuboriladi)
    birthday_target = today + datetime.timedelta(days=2)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    staff_with_birthday = User.objects.filter(
        organization__isnull=False,
        birth_date__isnull=False
    ).exclude(
        role='student'
    ).filter(
        birth_date__month=birthday_target.month,
        birth_date__day=birthday_target.day
    )
    
    for member in staff_with_birthday:
        org = member.organization
        
        # Bugun allaqachon ushbu xodim uchun tug'ilgan kun eslatmasi yuborilganmi?
        already_notified = Notification.objects.filter(
            organization=org,
            type='birthday_reminder',
            message__contains=f"(ID: {member.id})",
            created_at__date=today
        ).exists()
        
        if already_notified:
            continue
            
        # CEO (owner) roldagilarga yuborish
        owners = User.objects.filter(organization=org, role='owner')
        for owner in owners:
            full_name = f"{member.first_name} {member.last_name}".strip() or member.username
            message = (
                f"Tashkilotingiz xodimi {full_name} ning 2 kundan keyin "
                f"({birthday_target.strftime('%d.%m')}) tug'ilgan kuni! "
                f"Tabriklashni unutmang. (ID: {member.id})"
            )
            Notification.objects.create(
                organization=org,
                user=owner,
                title="Xodim tug'ilgan kuni yaqinlashmoqda",
                message=message,
                type='birthday_reminder'
            )
            sent += 1

    return {"sent": sent, "date": str(today)}


class Command(BaseCommand):
    help = 'Subscription eslatmalarini yuboradi'

    def handle(self, *args, **kwargs):
        result = send_reminders()
        self.stdout.write(f"✅ Yuborildi: {result['sent']}, 📅 Sana: {result['date']}")
