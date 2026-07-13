from django.db.models import Q
from rest_framework import viewsets, mixins, permissions, status, decorators
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from organizations.mixins import TenantViewSetMixin
from organizations.permissions import HasOrganizationPagePermission
from communication.models import SmsProvider, SMSMessages, SmsSchedules, SmsTemplates, Notification, NotificationSchedule
from communication.serializers import (
    SmsProviderSerializer, SMSMessagesSerializer, SmsSchedulesSerializer, SmsTemplatesSerializer, NotificationScheduleSerializer
)
from communication.services import dispatch_notification_schedule

class SmsProviderViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Sozlamalar'
    queryset = SmsProvider.objects.all()
    serializer_class = SmsProviderSerializer

class SMSMessagesViewSet(TenantViewSetMixin,
                         mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    permission_page_name = 'Sozlamalar'
    queryset = SMSMessages.objects.all()
    serializer_class = SMSMessagesSerializer

class SmsSchedulesViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Sozlamalar'
    queryset = SmsSchedules.objects.all()
    serializer_class = SmsSchedulesSerializer

class SmsTemplatesViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Sozlamalar'
    queryset = SmsTemplates.objects.all()
    serializer_class = SmsTemplatesSerializer


class NotificationScheduleViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Xabarlar'
    queryset = NotificationSchedule.objects.all()
    serializer_class = NotificationScheduleSerializer

    def perform_create(self, serializer):
        serializer.save(
            organization_id=self.get_organization_id(),
            branch_id=self.get_branch_id(),
            created_by=self.request.user
        )

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['delivery_mode'] = 'scheduled'
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save(
            organization_id=self.get_organization_id(),
            branch_id=self.get_branch_id(),
            created_by=self.request.user,
            delivery_mode='scheduled',
        )
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(schedule).data, status=status.HTTP_201_CREATED, headers=headers)

    @decorators.action(detail=False, methods=['post'], url_path='send-now')
    def send_immediate(self, request):
        data = request.data.copy()
        data['delivery_mode'] = 'immediate'
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save(
            organization_id=self.get_organization_id(),
            branch_id=self.get_branch_id(),
            created_by=self.request.user,
            delivery_mode='immediate',
            send_at=timezone.now(),
        )
        sent_count = dispatch_notification_schedule(schedule)
        schedule.refresh_from_db()
        return Response({
            "detail": "Xabar yuborildi.",
            "sent_count": sent_count,
            "schedule": self.get_serializer(schedule).data,
        }, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=['post'], url_path='send-now')
    def send_now(self, request, pk=None):
        schedule = self.get_object()
        sent_count = dispatch_notification_schedule(schedule)
        return Response({
            "detail": "Xabar yuborildi.",
            "sent_count": sent_count,
            "status": schedule.status,
        }, status=status.HTTP_200_OK)

class NotificationView(APIView):
    """Frontend tepasidagi bildirishnomalar (Notificationlar)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """O'qilmagan va yaqindagi bildirishnomalarni qaytaradi"""
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response({"count": 0, "notifications": []})

        # Eng so'nggi 20 ta bildirishnomani yuklash (umumiy yoki joriy userga tegishli)
        notifications = Notification.objects.filter(
            organization=org
        ).filter(
            Q(user__isnull=True) | Q(user=request.user)
        )[:20]
        
        unread_count = Notification.objects.filter(
            organization=org,
            is_read=False
        ).filter(
            Q(user__isnull=True) | Q(user=request.user)
        ).count()

        return Response({
            "count": unread_count,
            "notifications": [
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "type": n.type,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() if n.created_at else "",
                }
                for n in notifications
            ]
        })

    def patch(self, request):
        """Bildirishnomani o'qilgan deb belgilash"""
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response({"detail": "Tashkilot topilmadi."}, status=400)

        notification_id = request.data.get('id')
        if notification_id:
            try:
                notification = Notification.objects.get(
                    id=notification_id, 
                    organization=org
                )
                # Faqat o'ziga tegishli yoki umumiy bo'lsa o'qilgan qilishi mumkin
                if notification.user and notification.user != request.user:
                    return Response({"detail": "Ruxsat etilmagan."}, status=403)
                    
                notification.is_read = True
                notification.save()
                return Response({"detail": "Bildirishnoma o'qildi deb belgilandi."})
            except Notification.DoesNotExist:
                return Response({"detail": "Bildirishnoma topilmadi."}, status=404)
        else:
            Notification.objects.filter(
                organization=org, 
                is_read=False
            ).filter(
                Q(user__isnull=True) | Q(user=request.user)
            ).update(is_read=True)
            return Response({"detail": "Barcha bildirishnomalar o'qildi."})

    def delete(self, request):
        """Bildirishnomani o'chirib tashlash"""
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response({"detail": "Tashkilot topilmadi."}, status=400)

        notification_id = request.data.get('id') or request.query_params.get('id')
        if notification_id:
            try:
                notification = Notification.objects.get(
                    id=notification_id, 
                    organization=org
                )
                if notification.user and notification.user != request.user:
                    return Response({"detail": "Ruxsat etilmagan."}, status=403)
                    
                notification.delete()
                return Response({"detail": "Bildirishnoma o'chirildi."})
            except Notification.DoesNotExist:
                return Response({"detail": "Bildirishnoma topilmadi."}, status=404)
        else:
            Notification.objects.filter(
                organization=org
            ).filter(
                Q(user__isnull=True) | Q(user=request.user)
            ).delete()
            return Response({"detail": "Barcha bildirishnomalar o'chirildi."})


class StudentSMSHistoryAPIView(APIView):
    """
    Bitta studentga yuborilgan barcha SMS xabarlarining tarixi.
    URL: /api/v1/communication/student-sms-history/<student_id>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        from academics.models import Student

        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response({"detail": "Tashkilot aniqlanmadi."}, status=400)

        # Studentni topish
        try:
            student = Student.objects.get(id=student_id, organization_id=org_id)
        except Student.DoesNotExist:
            return Response({"detail": "Talaba topilmadi."}, status=404)

        # Student telefon raqami va ota-ona raqamlari bo'yicha SMS xabarlarini qidirish
        phone_numbers = [student.phone]
        if student.father_phone:
            phone_numbers.append(student.father_phone)
        if student.mother_phone:
            phone_numbers.append(student.mother_phone)

        sms_messages = SMSMessages.objects.filter(
            organization_id=org_id,
            recipient__in=phone_numbers
        ).order_by('-sent_at')

        data = {
            "student": {
                "id": student.id,
                "full_name": student.full_name,
                "phone": student.phone,
                "father_phone": student.father_phone,
                "mother_phone": student.mother_phone,
            },
            "total_count": sms_messages.count(),
            "sms_history": [
                {
                    "id": sms.id,
                    "recipient": sms.recipient,
                    "message": sms.message,
                    "status": sms.status,
                    "sent_at": sms.sent_at.isoformat() if sms.sent_at else None,
                }
                for sms in sms_messages
            ]
        }

        return Response(data)
