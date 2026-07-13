from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from organizations.mixins import TenantViewSetMixin
from organizations.permissions import IsAdminOrOwnerOrReadOnly
from support.models import FAQCategory, FAQItem, ChatSession, SupportTicket
from support.serializers import (
    FAQCategorySerializer, FAQItemSerializer, ChatSessionSerializer,
    ChatInputSerializer, SupportTicketSerializer
)
from support.services.chat import AIChatService
from django.utils import timezone


class FAQCategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    queryset = FAQCategory.objects.all()
    serializer_class = FAQCategorySerializer


class FAQItemViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    queryset = FAQItem.objects.all()
    serializer_class = FAQItemSerializer
    filterset_fields = ['category', 'is_active']
    search_fields = ['question', 'answer']


class ChatAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = ChatInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        session_id = serializer.validated_data.get('session_id')
        message = serializer.validated_data.get('message')
        
        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response(
                {"detail": "Foydalanuvchining tashkilot ID si aniqlanmadi."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        result = AIChatService.handle_chat_message(
            session_id_str=str(session_id) if session_id else None,
            message=message,
            user=request.user,
            organization_id=org_id
        )
        
        return Response(result, status=status.HTTP_200_OK)


class ChatHistoryViewSet(TenantViewSetMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ChatSession.objects.all().prefetch_related('messages')
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser and user.role not in ('owner', 'admin'):
            # Non-admins can only see their own chat history
            qs = qs.filter(user=user)
        return qs


class SupportTicketViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer
    filterset_fields = ['status', 'priority']
    search_fields = ['title', 'description']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_superuser and user.role not in ('owner', 'admin'):
            # Regular users only see their own tickets
            qs = qs.filter(user=user)
        return qs

    def perform_create(self, serializer):
        serializer.validated_data['user'] = self.request.user
        super().perform_create(serializer)

    def perform_update(self, serializer):
        instance = self.get_object()
        new_status = serializer.validated_data.get('status', instance.status)
        if new_status in ('resolved', 'closed') and instance.status not in ('resolved', 'closed'):
            serializer.validated_data['resolved_at'] = timezone.now()
        elif new_status not in ('resolved', 'closed'):
            serializer.validated_data['resolved_at'] = None
            
        super().perform_update(serializer)
