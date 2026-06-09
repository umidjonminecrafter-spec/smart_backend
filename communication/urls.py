from django.urls import path, include
from rest_framework.routers import DefaultRouter
from communication.views import (
    SmsProviderViewSet, SMSMessagesViewSet, SmsSchedulesViewSet, SmsTemplatesViewSet, NotificationView, NotificationScheduleViewSet
)

router = DefaultRouter()
router.register(r'providers', SmsProviderViewSet, basename='sms-provider')
router.register(r'sms-messages', SMSMessagesViewSet, basename='sms-message')
router.register(r'sms-schedules', SmsSchedulesViewSet, basename='sms-schedule')
router.register(r'sms-templates', SmsTemplatesViewSet, basename='sms-template')
router.register(r'notification-schedules', NotificationScheduleViewSet, basename='notification-schedule')

urlpatterns = [
    path('', include(router.urls)),
    path('notifications/', NotificationView.as_view(), name='notifications'),
]
