from django.db import models
from organizations.models import TenantModel


class BillingHistory(TenantModel):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    plan_name = models.CharField(max_length=100)
    months = models.IntegerField()

    def __str__(self):
        return f"{self.organization.name} - {self.plan_name} ({self.months} months)"


class BalanceTopUp(TenantModel):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    comment = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.organization.name} - +{self.amount}"


class TariffPurchase(TenantModel):
    tariff = models.ForeignKey(
        'organizations.Tariff',
        on_delete=models.SET_NULL,
        null=True,
        related_name='purchases'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateField()
    next_charge_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.organization.name} - {self.tariff} ({self.next_charge_date})"


class SubscriptionRequest(TenantModel):
    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('approved', 'Tasdiqlangan'),
        ('rejected', 'Rad etilgan'),
    ]
    tariff = models.ForeignKey(
        'organizations.Tariff',
        on_delete=models.CASCADE,
        related_name='subscription_requests'
    )
    months = models.IntegerField(default=1)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.organization.name} - {self.tariff.name} ({self.status})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None
        if not is_new:
            old_status = SubscriptionRequest.objects.get(pk=self.pk).status

        super().save(*args, **kwargs)

        if self.status == 'approved' and old_status != 'approved':
            import datetime
            from organizations.models import Subscription
            subscription, _ = Subscription.objects.get_or_create(
                organization=self.organization,
                defaults={
                    'start_date': datetime.date.today(),
                    'end_date': datetime.date.today(),
                    'is_active': False,
                }
            )
            
            today = datetime.date.today()
            if subscription.is_active and subscription.end_date >= today:
                start = subscription.end_date
            else:
                start = today

            total_months = start.month + self.months - 1
            year = start.year + (total_months // 12)
            month = (total_months % 12) + 1
            day = min(start.day, 28)
            end = datetime.date(year, month, day)

            subscription.tariff = self.tariff
            subscription.start_date = start
            subscription.end_date = end
            subscription.is_active = True
            subscription.save()

            from billing.models import TariffPurchase, BillingHistory
            TariffPurchase.objects.get_or_create(
                organization=self.organization,
                tariff=self.tariff,
                amount=self.amount,
                start_date=start,
                next_charge_date=end,
                is_active=True,
            )

            BillingHistory.objects.get_or_create(
                organization=self.organization,
                amount=self.amount,
                plan_name=self.tariff.name,
                months=self.months,
            )