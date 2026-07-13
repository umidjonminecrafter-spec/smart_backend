from django.db import models
from django.contrib.auth import get_user_model
from organizations.models import TenantModel
import uuid

User = get_user_model()


class FAQCategory(TenantModel):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    class Meta:
        verbose_name = "FAQ Category"
        verbose_name_plural = "FAQ Categories"


class FAQItem(TenantModel):
    category = models.ForeignKey(FAQCategory, on_delete=models.CASCADE, related_name="items")
    question = models.CharField(max_length=255)
    answer = models.TextField()
    keywords = models.JSONField(default=list, blank=True, help_text="Kalit so'zlar ro'yxati")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.question

    class Meta:
        verbose_name = "FAQ Item"
        verbose_name_plural = "FAQ Items"


class ChatSession(TenantModel):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_sessions")
    telegram_chat_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"Session {self.session_id} - {self.user.username}"
        if self.telegram_chat_id:
            return f"Session {self.session_id} - TG:{self.telegram_chat_id}"
        return f"Session {self.session_id} - Guest"


class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=10, choices=[('user', 'User'), ('ai', 'AI')])
    content = models.TextField()
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    matched_faq = models.ForeignKey(FAQItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="matched_messages")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.content[:30]}"

    class Meta:
        ordering = ['created_at']


class SupportTicket(TenantModel):
    STATUS_CHOICES = (
        ('open', 'Ochilgan (Open)'),
        ('in_progress', 'Jarayonda (In Progress)'),
        ('resolved', 'Hal etilgan (Resolved)'),
        ('closed', 'Yopilgan (Closed)'),
    )
    PRIORITY_CHOICES = (
        ('low', 'Past (Low)'),
        ('medium', 'O\'rta (Medium)'),
        ('high', 'Yuqori (High)'),
        ('critical', 'Kritik (Critical)'),
    )
    session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="support_tickets")
    email = models.EmailField(null=True, blank=True, help_text="Guest userlar uchun aloqa emaili")
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    assigned_admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets")
    admin_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ticket #{self.id} - {self.title} ({self.status})"
