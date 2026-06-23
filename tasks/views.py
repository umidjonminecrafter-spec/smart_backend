from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from organizations.mixins import TenantViewSetMixin
from tasks.models import Board, Column, Item, Comment, TaskPermission
from tasks.serializers import (
    BoardSerializer, ColumnSerializer, ItemSerializer, CommentSerializer, TaskPermissionSerializer
)
from tasks.permissions import HasBoardPermission, IsCommentOwnerOrReadOnly

class BoardViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Tasks'
    queryset = Board.objects.all()
    serializer_class = BoardSerializer
    permission_classes = [permissions.IsAuthenticated, HasBoardPermission]

class ColumnViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Tasks'
    queryset = Column.objects.all()
    serializer_class = ColumnSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['board_id']
    permission_classes = [permissions.IsAuthenticated, HasBoardPermission]

class ItemViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Tasks'
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['column_id', 'board_id', 'assigned_to']
    search_fields = ['title', 'description']
    permission_classes = [permissions.IsAuthenticated, HasBoardPermission]

class CommentViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Tasks'
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['item_id']
    permission_classes = [permissions.IsAuthenticated, IsCommentOwnerOrReadOnly]

    def perform_create(self, serializer):
        org_id = self.get_organization_id()
        branch_id = self.get_branch_id()
        serializer.save(organization_id=org_id, branch_id=branch_id, user=self.request.user)

class TaskPermissionViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Tasks'
    queryset = TaskPermission.objects.all()
    serializer_class = TaskPermissionSerializer
    permission_classes = [permissions.IsAuthenticated]
