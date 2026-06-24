from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tasks.views import (
    BoardViewSet, ColumnViewSet, ItemViewSet, CommentViewSet, TaskPermissionViewSet,
    LabelViewSet, ChecklistViewSet, ChecklistItemViewSet, AttachmentViewSet
)
router = DefaultRouter()
router.register(r'boards', BoardViewSet, basename='board')
router.register(r'columns', ColumnViewSet, basename='column')
router.register(r'items', ItemViewSet, basename='item')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'permissions', TaskPermissionViewSet, basename='permission')
router.register(r'labels', LabelViewSet, basename='label')
router.register(r'checklists', ChecklistViewSet, basename='checklist')
router.register(r'checklist-items', ChecklistItemViewSet, basename='checklistitem')
router.register(r'attachments', AttachmentViewSet, basename='attachment')

urlpatterns = [
    path('', include(router.urls)),
]
