from django.db import models
from organizations.models import TenantModel, Organization
from django.conf import settings


class SmsProvider(TenantModel):
    name = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class SMSMessages(TenantModel):
    recipient = models.CharField(max_length=50)
    message = models.TextField()
    status = models.CharField(max_length=50, default='pending')
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.recipient} - {self.status}"


class SmsSchedules(TenantModel):
    recipient = models.CharField(max_length=50)
    message = models.TextField()
    scheduled_time = models.DateTimeField()
    is_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"Schedule to {self.recipient} at {self.scheduled_time}"


class SmsTemplates(TenantModel):
    title = models.CharField(max_length=255)
    body = models.TextField()

    def __str__(self):
        return self.title


class BulkSMS(models.Model):
    """Admin tomonidan hamma/tanlangan organizationlarga yuborilgan SMS"""
    message = models.TextField()
    organizations = models.ManyToManyField(
        Organization,
        blank=True,
        help_text="Bo'sh qolsa — hamma organizationlarga yuboriladi"
    )
    sent_by = models.CharField(max_length=255, null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    total_sent = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('done', 'Done'), ('failed', 'Failed')],
        default='pending'
      )

    def __str__(self):
        return f"BulkSMS {self.sent_at} - {self.status}"


class NotificationSchedule(TenantModel):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    DELIVERY_CHOICES = (
        ('immediate', 'Immediate'),
        ('scheduled', 'Scheduled'),
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    send_at = models.DateTimeField(null=True, blank=True)
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default='scheduled')
    target_roles = models.JSONField(default=list, blank=True)
    target_user_ids = models.JSONField(default=list, blank=True)
    target_group_ids = models.JSONField(default=list, blank=True)
    target_course_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notification_schedules'
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    total_sent = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.send_at} ({self.status})"


class SubscriptionReminder(models.Model):
    """Avtomatik eslatma sozlamalari"""
    TRIGGER_CHOICES = [
        ('subscription_expiry', 'Tarif tugashidan oldin'),
        ('balance_low', 'Balance kam qolganda'),
    ]
    trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    days_before = models.IntegerField(
        default=3,
        help_text="Necha kun oldin eslatsin (faqat subscription_expiry uchun)"
    )
    balance_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Qancha balancedan kam bo'lsa eslatsin (faqat balance_low uchun)"
    )
    template = models.ForeignKey(
        SmsTemplates,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reminders'
    )
    custom_message = models.TextField(
        null=True, blank=True,
        help_text="Template yo'q bo'lsa shu xabar yuboriladi"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.trigger} - {self.days_before} kun oldin"


class ReminderLog(models.Model):
    """Yuborilgan eslatmalar tarixi"""
    reminder = models.ForeignKey(
        SubscriptionReminder,
        on_delete=models.SET_NULL,
        null=True,
        related_name='logs'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='reminder_logs'
    )
    phone = models.CharField(max_length=50)
    message = models.TextField()
    status = models.CharField(max_length=20, default='sent')
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.organization.name} - {self.sent_at}"


class Notification(models.Model):
    """Sayt ichida bildirishnoma"""
    TYPES = [
        ('subscription_expiry', 'Tarif tugashidan oldin'),
        ('balance_low', 'Balance kam'),
        ('info', 'Umumiy xabar'),
        ('birthday_reminder', 'Tug\'ilgan kun eslatmasi'),
    ]
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50, choices=TYPES, default='info')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.organization.name} - {self.title}"

    class Meta:
        ordering = ['-created_at']


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Notification)
def send_notification_to_telegram(sender, instance, created, **kwargs):
    if created and instance.user and getattr(instance.user, 'telegram_chat_id', None):
        try:
            from organizations.models import TelegramNotificationSetting
            from academics.telegram_bot import send_telegram_message
            
            setting = TelegramNotificationSetting.objects.filter(organization=instance.organization).first()
            token = setting.staff_bot_token or setting.bot_token if setting else None
            
            if not token:
                from django.conf import settings
                token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None) or "7185362147:AAEX5h1s39q31_b126348123h12a"
                
            lang = getattr(instance.user, 'telegram_language', 'uz') or 'uz'
            if lang == 'ru':
                msg = f"<b>🔔 Новое уведомление:</b> {instance.title}\n\n{instance.message}"
            else:
                msg = f"<b>🔔 Yangi bildirishnoma:</b> {instance.title}\n\n{instance.message}"
                
            send_telegram_message(token, instance.user.telegram_chat_id, msg)
        except Exception as e:
            print(f"Error sending telegram notification: {str(e)}")


@receiver(post_save, sender=SMSMessages)
def send_sms_to_telegram(sender, instance, created, **kwargs):
    if created:
        try:
            from academics.models import Student
            from accounts.models import User
            from academics.telegram_bot import send_telegram_message
            from organizations.models import TelegramNotificationSetting
            
            chat_id = None
            org = None
            
            # Find student first
            student = Student.objects.filter(phone=instance.recipient).first()
            if student and student.telegram_chat_id:
                chat_id = student.telegram_chat_id
                org = student.organization
            else:
                # Try user (staff/parent)
                user = User.objects.filter(phone=instance.recipient).first()
                if user and user.telegram_chat_id:
                    chat_id = user.telegram_chat_id
                    org = user.organization
                    
            if chat_id and org:
                setting = TelegramNotificationSetting.objects.filter(organization=org).first()
                token = setting.bot_token or setting.staff_bot_token if setting else None
                
                if not token:
                    from django.conf import settings
                    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None) or "7185362147:AAEX5h1s39q31_b126348123h12a"
                    
                msg = f"<b>✉️ Yangi xabar:</b>\n\n{instance.message}"
                send_telegram_message(token, chat_id, msg)
        except Exception as e:
            print(f"Error sending SMS to telegram: {str(e)}")
