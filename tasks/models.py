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
