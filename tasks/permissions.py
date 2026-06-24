from rest_framework import permissions
from tasks.models import TaskPermission, Board, Column, Item, Label, Checklist, ChecklistItem, Attachment

class HasBoardPermission(permissions.BasePermission):
    """
    Kanban taxtalarini (Board) tahrirlash huquqini tekshiruvchi klass.
    Tashkilot egasi (owner) va admini (admin) barcha taxtalarga to'liq huquqqa ega.
    Boshqa foydalanuvchilar esa maxsus TaskPermission modeli orqali ruxsatga ega bo'lishi kerak.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        if request.method in permissions.SAFE_METHODS:
            return True
            
        user = request.user
        if getattr(user, 'role', None) in ['owner', 'admin'] or user.is_superuser:
            return True

        # Yangi ustun yoki vazifa yaratilayotganda board_id ni tekshiramiz
        if view.action == 'create':
            board_id = request.data.get('board_id') or request.data.get('board')
            if not board_id and ('column_id' in request.data or 'column' in request.data):
                col_id = request.data.get('column_id') or request.data.get('column')
                col = Column.objects.filter(id=col_id).first()
                if col:
                    board_id = col.board_id
            elif not board_id and ('item_id' in request.data or 'item' in request.data):
                item_id = request.data.get('item_id') or request.data.get('item')
                item = Item.objects.filter(id=item_id).first()
                if item:
                    board_id = item.board_id
            elif not board_id and ('checklist_id' in request.data or 'checklist' in request.data):
                check_id = request.data.get('checklist_id') or request.data.get('checklist')
                check = Checklist.objects.filter(id=check_id).first()
                if check and check.item:
                    board_id = check.item.board_id
                    
            if not board_id:
                return False
                
            perm = TaskPermission.objects.filter(board_id=board_id, user=user).first()
            return perm is not None and perm.can_edit
            
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user
        if getattr(user, 'role', None) in ['owner', 'admin'] or user.is_superuser:
            return True

        # Tegishli loyiha taxtasini aniqlaymiz
        board = None
        if isinstance(obj, Board):
            board = obj
        elif isinstance(obj, Column):
            board = obj.board
        elif isinstance(obj, Item):
            board = obj.board
        elif isinstance(obj, Label):
            board = obj.board
        elif isinstance(obj, Checklist):
            board = obj.item.board
        elif isinstance(obj, ChecklistItem):
            board = obj.checklist.item.board
        elif isinstance(obj, Attachment):
            board = obj.item.board

        if not board:
            return False

        perm = TaskPermission.objects.filter(board=board, user=user).first()
        return perm is not None and perm.can_edit


class IsCommentOwnerOrReadOnly(permissions.BasePermission):
    """
    Izohlar (Comment) xavfsizligini ta'minlovchi klass.
    Faqat izohni yozgan muallifgina uni tahrirlashi (PATCH) yoki o'chirishi (DELETE) mumkin.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return obj.user == request.user
