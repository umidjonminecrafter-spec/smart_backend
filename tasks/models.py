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

class Item(TenantModel):
    column = models.ForeignKey(Column, on_delete=models.CASCADE, related_name="items")
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="items")
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tasks")
    due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title

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
