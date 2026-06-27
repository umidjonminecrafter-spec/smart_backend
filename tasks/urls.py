from django.urls import path
from tasks.views import (
    BoardViewSet, ColumnViewSet, ItemViewSet, CommentViewSet, TaskPermissionViewSet,
    LabelViewSet, ChecklistViewSet, ChecklistItemViewSet, AttachmentViewSet, TaskHistoryViewSet
)

urlpatterns = [
    # ===== Boards =====
    path('boards/', BoardViewSet.as_view({'get': 'list', 'post': 'create'}), name='board-list'),
    path('boards/<int:pk>/', BoardViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='board-detail'),

    # ===== Columns =====
    path('columns/', ColumnViewSet.as_view({'get': 'list', 'post': 'create'}), name='column-list'),
    path('columns/<int:pk>/', ColumnViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='column-detail'),

    # ===== Items =====
    path('items/', ItemViewSet.as_view({'get': 'list', 'post': 'create'}), name='item-list'),
    path('items/<int:pk>/', ItemViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='item-detail'),
    path('items/<int:pk>/move/', ItemViewSet.as_view({'post': 'move'}), name='item-move'),
    path('items/<int:pk>/history/', ItemViewSet.as_view({'get': 'history'}), name='item-history'),

    # ===== Comments =====
    path('comments/', CommentViewSet.as_view({'get': 'list', 'post': 'create'}), name='comment-list'),
    path('comments/<int:pk>/', CommentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='comment-detail'),

    # ===== Permissions =====
    path('permissions/', TaskPermissionViewSet.as_view({'get': 'list', 'post': 'create'}), name='permission-list'),
    path('permissions/<int:pk>/', TaskPermissionViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='permission-detail'),

    # ===== Labels =====
    path('labels/', LabelViewSet.as_view({'get': 'list', 'post': 'create'}), name='label-list'),
    path('labels/<int:pk>/', LabelViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='label-detail'),

    # ===== Checklists =====
    path('checklists/', ChecklistViewSet.as_view({'get': 'list', 'post': 'create'}), name='checklist-list'),
    path('checklists/<int:pk>/', ChecklistViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='checklist-detail'),

    # ===== Checklist Items =====
    path('checklist-items/', ChecklistItemViewSet.as_view({'get': 'list', 'post': 'create'}), name='checklistitem-list'),
    path('checklist-items/<int:pk>/', ChecklistItemViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='checklistitem-detail'),

    # ===== Attachments =====
    path('attachments/', AttachmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='attachment-list'),
    path('attachments/<int:pk>/', AttachmentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='attachment-detail'),

    # ===== Task History =====
    path('history/', TaskHistoryViewSet.as_view({'get': 'list'}), name='taskhistory-list'),
    path('history/<int:pk>/', TaskHistoryViewSet.as_view({'get': 'retrieve'}), name='taskhistory-detail'),
]
