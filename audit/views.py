from rest_framework import viewsets
from organizations.mixins import TenantViewSetMixin
from audit.models import AuditLog
from audit.serializers import AuditLogSerializer

class AuditLogViewSet(TenantViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
