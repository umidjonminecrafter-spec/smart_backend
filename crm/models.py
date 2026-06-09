from django.db import models
from django.conf import settings
from organizations.models import TenantModel

class Pipeline(TenantModel):
    name = models.CharField(max_length=150)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name

class Source(TenantModel):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name

class LostReason(TenantModel):
    reason = models.CharField(max_length=255)

    def __str__(self):
        return self.reason

class Section(TenantModel):
    name = models.CharField(max_length=150)
    # TO'G'RILANDI: Pipeline o'chganda section o'chmasligi uchun SET_NULL qilindi
    pipeline = models.ForeignKey(Pipeline, on_delete=models.SET_NULL, null=True, blank=True, related_name="sections")

    def __str__(self):
        return self.name

class LeadForm(TenantModel):
    name = models.CharField(max_length=150)
    fields = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name


# TO'G'RILANDI: Ko'p martalik izohlar modeli
class LeadComment(TenantModel):
    lead = models.ForeignKey('Lead', on_delete=models.CASCADE, related_name="lead_comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class Lead(TenantModel):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    )
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    email = models.EmailField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # TO'G'RILANDI: Pipeline o'chib ketsa lidlar o'chib ketmaydi! SET_NULL qilindi.
    pipeline = models.ForeignKey(Pipeline, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    lost_reason = models.ForeignKey(LostReason, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_leads"
    )
    comment = models.TextField(null=True, blank=True)

    # Custom fields for contacts, timers and multi-notes
    contacted_at = models.DateTimeField(null=True, blank=True)
    next_contact_at = models.DateTimeField(null=True, blank=True)
    reminder_time = models.DateTimeField(null=True, blank=True)
    notes = models.JSONField(default=list, blank=True)

    # QO'SHILDI: Lid bilan ishlash muddati (Deadline)
    reminder_deadline = models.DateTimeField(null=True, blank=True, help_text="Lidning muddati (Sana va vaqt)")

    # Archiving fields
    is_archived = models.BooleanField(default=False)
    archive_reason = models.TextField(null=True, blank=True)
    archive_date = models.DateTimeField(null=True, blank=True)
    archived_by = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        # Baza darajasida filtrlash va qidirishni tezlashtiradigan indekslar
        indexes = [
            models.Index(fields=['organization', 'is_archived']),
            models.Index(fields=['pipeline']),
            models.Index(fields=['source']),
            models.Index(fields=['status']),
            models.Index(fields=['phone']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name

class CRMActivity(TenantModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=50) # call, meeting, etc.
    notes = models.TextField()
    date = models.DateField()

    def __str__(self):
        return f"{self.activity_type} - {self.lead.name}"

class CRMLeadsHistory(TenantModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="history")
    change_details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"History: {self.lead.name} at {self.created_at}"

class CRMLeadLost(TenantModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="lost_records")
    lost_reason = models.ForeignKey(LostReason, on_delete=models.SET_NULL, null=True, blank=True, related_name="lost_records")
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Lost: {self.lead.name}"
