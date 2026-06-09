from django.contrib import admin
from tasks.models import Board, Column, Item, Comment, TaskPermission

@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organization')
    search_fields = ('name',)

@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display = ('id', 'board', 'name', 'order', 'organization')
    list_filter = ('board',)
    search_fields = ('name',)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'column', 'board', 'title', 'assigned_to', 'due_date', 'organization')
    list_filter = ('board', 'column', 'assigned_to')
    search_fields = ('title', 'description')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'user', 'organization')

@admin.register(TaskPermission)
class TaskPermissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'board', 'user', 'can_edit', 'organization')
    list_filter = ('board', 'can_edit')
