from django.contrib import admin
from support.models import FAQCategory, FAQItem, ChatSession, ChatMessage, SupportTicket


@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'organization', 'created_at']
    list_filter = ['is_active', 'organization']
    search_fields = ['name', 'description']


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'question', 'category', 'is_active', 'organization', 'created_at']
    list_filter = ['is_active', 'category', 'organization']
    search_fields = ['question', 'answer', 'keywords']


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ['sender', 'content', 'confidence_score', 'matched_faq', 'created_at']
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'telegram_chat_id', 'organization', 'created_at', 'updated_at']
    list_filter = ['organization', 'created_at']
    search_fields = ['session_id', 'user__username', 'telegram_chat_id']
    inlines = [ChatMessageInline]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'status', 'priority', 'user', 'assigned_admin', 'organization', 'created_at']
    list_filter = ['status', 'priority', 'organization', 'created_at']
    search_fields = ['title', 'description', 'user__username', 'email']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['session', 'user', 'assigned_admin']
