from rest_framework import serializers
from .models import KPITemplate, KPIGoal, KPISubGoal, KPILog

class KPITemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KPITemplate
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


class KPISubGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = KPISubGoal
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


class KPIGoalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    sub_goals = KPISubGoalSerializer(many=True, read_only=True)

    class Meta:
        model = KPIGoal
        fields = '__all__'
        read_only_fields = ('organization', 'total_progress', 'created_at', 'updated_at')


class KPILogSerializer(serializers.ModelSerializer):
    sub_goal_name = serializers.CharField(source='sub_goal.name', read_only=True)

    class Meta:
        model = KPILog
        fields = '__all__'
        read_only_fields = ('organization', 'created_at')
