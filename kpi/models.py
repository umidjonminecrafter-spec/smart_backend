from django.db import models
from django.conf import settings
from organizations.models import TenantModel

class KPITemplate(TenantModel):
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=50, help_text="Roli: e.g. teacher, admin, employee")
    sub_goals_config = models.JSONField(
        default=list, 
        blank=True,
        help_text="Kichik maqsadlar ro'yxati: [{'name': 'Lid', 'metric_type': 'automatic', 'system_event': 'lead_to_student', 'target_value': 10, 'weight': 40}]"
    )

    def __str__(self):
        return f"{self.name} ({self.role})"


class KPIGoal(TenantModel):
    STATUS_CHOICES = (
        ('active', 'Faol'),
        ('completed', 'Bajarildi'),
        ('failed', 'Bajarilmadi'),
    )
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kpi_goals")
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    total_progress = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.name} - {self.employee} ({self.total_progress}%)"

    def calculate_progress(self):
        from decimal import Decimal
        total = Decimal('0.00')
        sub_goals = self.sub_goals.all()
        for sub in sub_goals:
            if sub.target_value > 0:
                progress_ratio = min(Decimal(str(sub.current_value)) / Decimal(str(sub.target_value)), Decimal('1.00'))
                total += progress_ratio * Decimal(str(sub.weight))
        self.total_progress = min(total, Decimal('100.00'))
        self.save(update_fields=['total_progress'])


class KPISubGoal(TenantModel):
    METRIC_TYPE_CHOICES = (
        ('manual', 'Qo\'lda kiritiladigan'),
        ('automatic', 'Tizim tomonidan avtomat hisoblanadigan'),
    )
    SYSTEM_EVENT_CHOICES = (
        ('lead_to_student', 'Lidni talabaga aylantirganda'),
        ('lost_lead', 'Lidni yo\'qotganda (Minus ball)'),
        ('new_payment', 'To\'lov yig\'ilganda'),
        ('attendance_taken', 'Yo\'qlama topshirilganda'),
    )
    parent_goal = models.ForeignKey(KPIGoal, on_delete=models.CASCADE, related_name="sub_goals")
    name = models.CharField(max_length=255)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPE_CHOICES, default='manual')
    system_event = models.CharField(max_length=50, choices=SYSTEM_EVENT_CHOICES, null=True, blank=True)
    
    target_value = models.DecimalField(max_digits=12, decimal_places=2)
    current_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Salmog'i %")

    def __str__(self):
        return f"{self.name} ({self.current_value}/{self.target_value})"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        old_val = Decimal('0.00')
        if self.pk:
            try:
                old_sub = KPISubGoal.objects.get(pk=self.pk)
                old_val = Decimal(str(old_sub.current_value))
            except KPISubGoal.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        diff = Decimal(str(self.current_value)) - old_val
        if diff != 0:
            KPILog.objects.create(
                organization=self.organization,
                branch_id=self.branch_id,
                sub_goal=self,
                changed_value=diff,
                description=f"Ko'rsatkich o'zgardi: {old_val} -> {self.current_value}"
            )
            
        if self.parent_goal:
            self.parent_goal.calculate_progress()


class KPILog(TenantModel):
    sub_goal = models.ForeignKey(KPISubGoal, on_delete=models.CASCADE, related_name="logs")
    changed_value = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sub_goal.name}: {self.changed_value} ({self.created_at})"
