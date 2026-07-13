from django.urls import path, include
from rest_framework.routers import DefaultRouter
from support.views import (
    FAQCategoryViewSet, FAQItemViewSet, ChatAPIView,
    ChatHistoryViewSet, SupportTicketViewSet
)

router = DefaultRouter()
router.register(r'faq-categories', FAQCategoryViewSet, basename='faq-category')
router.register(r'faq-items', FAQItemViewSet, basename='faq-item')
router.register(r'history', ChatHistoryViewSet, basename='chat-history')
router.register(r'tickets', SupportTicketViewSet, basename='support-ticket')

urlpatterns = [
    path('chat/', ChatAPIView.as_view(), name='chat-api'),
    path('', include(router.urls)),
]
