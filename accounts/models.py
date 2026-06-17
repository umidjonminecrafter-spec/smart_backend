from django.contrib.auth.models import AbstractUser
from django.db import models
from organizations.models import Organization
from django.core.exceptions import ValidationError


class User(AbstractUser):
    ROLE_CHOICES = (
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('teacher', 'Teacher'),
        ('receptionist', 'Receptionist'),
        ('employee', 'Employee'),
        ('student', 'Student'),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True
    )
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.SET_NULL,
        related_name="users",
        null=True,
        blank=True
    )
    phone = models.CharField(max_length=50, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    position = models.CharField(max_length=100, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    photo = models.ImageField(upload_to='user_photos/', null=True, blank=True)
    telegram_chat_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="Telegram Chat ID")

    # 🚀 O'qituvchi xodim yaratilayotganda moliya foiz stavkasini biriktirish (1-rasm)
    salary_percentage = models.ForeignKey(
        'finance.StaffSalaryPercent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teachers",
        verbose_name="Oladigan foizi"
    )

    def clean(self):
        super().clean()
        # Role 'teacher' bo'lganda foiz stavkasi majburiy bo'lishini tekshirish
        if self.role == 'teacher' and not self.salary_percentage:
            raise ValidationError({
                'salary_percentage': "O'qituvchi roli uchun oladigan foizini tanlash majburiy!"
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"