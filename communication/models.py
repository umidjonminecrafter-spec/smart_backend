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
