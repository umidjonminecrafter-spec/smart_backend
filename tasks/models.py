from django.db import models
from django.conf import settings
from organizations.models import TenantModel

class Board(TenantModel):
    name = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

class Column(TenantModel):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="columns")
    name = models.CharField(max_length=150)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.board.name} -> {self.name}"

class Label(TenantModel):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="labels")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=50, default="#000000")

    def __str__(self):
        return f"{self.name} ({self.color})"

class Item(TenantModel):
    column = models.ForeignKey(Column, on_delete=models.CASCADE, related_name="items")
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="items")
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tasks")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="task_members", blank=True)
    labels = models.ManyToManyField(Label, related_name="items", blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title

class Checklist(TenantModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="checklists")
    title = models.CharField(max_length=255, default="Checklist")

    def __str__(self):
        return self.title

class ChecklistItem(TenantModel):
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="items")
    title = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class Attachment(TenantModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="task_attachments/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.file.name if self.file else "Attachment"

class Comment(TenantModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_comments")
    text = models.TextField()

    def __str__(self):
        return f"Comment by {self.user} on {self.item.title}"

class TaskPermission(TenantModel):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="permissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="board_permissions")
    can_edit = models.BooleanField(default=True)

    class Meta:
        unique_together = ('board', 'user')

    def __str__(self):
        return f"{self.user} on {self.board.name} (Edit: {self.can_edit})"

class TaskHistory(TenantModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="history")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="task_histories")
    action = models.CharField(max_length=255)
    details = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.action} on {self.item.title} at {self.created_at}"


from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

@receiver(pre_save, sender=Item)
def item_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Item.objects.get(pk=instance.pk)
            instance._old_assigned_to_id = old.assigned_to_id
        except Item.DoesNotExist:
            instance._old_assigned_to_id = None
    else:
        instance._old_assigned_to_id = None

@receiver(post_save, sender=Item)
def notify_task_assignment(sender, instance, created, **kwargs):
    old_assigned_to_id = getattr(instance, '_old_assigned_to_id', None)
    should_send = False

    if created and instance.assigned_to:
        should_send = True
    elif not created and instance.assigned_to and old_assigned_to_id != instance.assigned_to_id:
        should_send = True

    if should_send and getattr(instance.assigned_to, 'telegram_chat_id', None):
        try:
            from organizations.models import TelegramNotificationSetting
            from academics.telegram_bot import send_telegram_message
            
            setting = TelegramNotificationSetting.objects.filter(organization=instance.organization).first()
            token = setting.staff_bot_token or setting.bot_token if setting else None
            
            if not token:
                from django.conf import settings
                token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None) or "7185362147:AAEX5h1s39q31_b126348123h12a"
                
            lang = getattr(instance.assigned_to, 'telegram_language', 'uz') or 'uz'
            due = instance.due_date.strftime("%d.%m.%Y %H:%M") if instance.due_date else "-"
            
            if lang == 'ru':
                msg = (
                    f"<b>📋 Новая задача назначена вам:</b>\n\n"
                    f"📌 Заголовок: {instance.title}\n"
                    f"💬 Описание: {instance.description or '-'}\n"
                    f"📅 Срок выполнения: <b>{due}</b>"
                )
            else:
                msg = (
                    f"<b>📋 Sizga yangi vazifa yuklatildi:</b>\n\n"
                    f"📌 Sarlavha: {instance.title}\n"
                    f"💬 Tavsif: {instance.description or '-'}\n"
                    f"📅 Muddat: <b>{due}</b>"
                )
            send_telegram_message(token, instance.assigned_to.telegram_chat_id, msg)
        except Exception as e:
            print(f"Error sending telegram task notification: {str(e)}")

