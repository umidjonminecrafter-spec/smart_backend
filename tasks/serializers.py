from rest_framework import serializers
from tasks.models import Board, Column, Item, Comment, TaskPermission
from accounts.serializers import UserSerializer

class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class ColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = Column
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

class ItemSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', default='', read_only=True)
    column_name = serializers.CharField(source='column.name', read_only=True)

    class Meta:
        model = Item
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')

    def validate(self, attrs):
        column = attrs.get('column')
        board = attrs.get('board')
        
        # PATCH (partial update) holatida self.instance'dan foydalanamiz
        if not column and self.instance:
            column = self.instance.column
        if not board and self.instance:
            board = self.instance.board
            
        if column and board and column.board_id != board.id:
            raise serializers.ValidationError(
                {"column": "Tanlangan ustun (column) ko'rsatilgan loyiha taxtasiga (board) tegishli emas."}
            )
        return attrs

class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', default='', read_only=True)

    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ('organization', 'user', 'created_at', 'updated_at')

class TaskPermissionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', default='', read_only=True)
    board_name = serializers.CharField(source='board.name', read_only=True)

    class Meta:
        model = TaskPermission
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')
