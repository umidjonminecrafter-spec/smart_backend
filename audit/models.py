from django.db import models
from django.conf import settings
from organizations.models import TenantModel

class AuditLog(TenantModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=100)
    entity_id = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"
