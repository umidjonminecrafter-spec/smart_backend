from django.contrib.auth.models import AbstractUser
from django.db import models
from organizations.models import Organization

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

    def __str__(self):
        return f"{self.username} ({self.role})"
