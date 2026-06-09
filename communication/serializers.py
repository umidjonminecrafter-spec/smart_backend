from rest_framework import serializers
from django.contrib.auth import get_user_model
from communication.models import SmsProvider, SMSMessages, SmsSchedules, SmsTemplates, NotificationSchedule
from academics.models import Course, Group

User = get_user_model()

class SmsProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsProvider
        fields = '__all__'
        read_only_fields = ('organization',)
        extra_kwargs = {
            'api_key': {'write_only': True}
        }

class SMSMessagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = SMSMessages
        fields = '__all__'
        read_only_fields = ('organization', 'sent_at')

class SmsSchedulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsSchedules
        fields = '__all__'
        read_only_fields = ('organization',)

class SmsTemplatesSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsTemplates
        fields = '__all__'
        read_only_fields = ('organization',)


class NotificationScheduleSerializer(serializers.ModelSerializer):
    delivery_mode = serializers.ChoiceField(choices=NotificationSchedule.DELIVERY_CHOICES, required=False)
    target_roles = serializers.ListField(
        child=serializers.ChoiceField(choices=[key for key, _ in User.ROLE_CHOICES]),
        required=False,
        allow_empty=True
    )
    target_user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    target_group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    target_course_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')

    class Meta:
        model = NotificationSchedule
        fields = '__all__'
        read_only_fields = ('organization', 'branch', 'created_by', 'sent_at', 'status', 'total_sent', 'total_failed', 'last_error')

    def validate(self, attrs):
        roles = attrs.get('target_roles') or []
        user_ids = attrs.get('target_user_ids') or []
        group_ids = attrs.get('target_group_ids') or []
        course_ids = attrs.get('target_course_ids') or []
        delivery_mode = attrs.get('delivery_mode') or getattr(self.instance, 'delivery_mode', 'scheduled')

        if delivery_mode == 'scheduled' and not attrs.get('send_at'):
            raise serializers.ValidationError({"send_at": "Rejalashtirilgan xabar uchun vaqt majburiy."})

        if not roles and not user_ids and not group_ids and not course_ids:
            raise serializers.ValidationError({
                "detail": "Kamida bitta qabul qiluvchi tanlang: xodim, guruh, kurs yoki individual foydalanuvchi."
            })

        valid_roles = {key for key, _ in User.ROLE_CHOICES}
        invalid_roles = [role for role in roles if role not in valid_roles]
        if invalid_roles:
            raise serializers.ValidationError({"target_roles": f"Noto'g'ri rol: {', '.join(invalid_roles)}"})
        return attrs

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        from communication.services import resolve_notification_recipients
        rep['recipient_count'] = resolve_notification_recipients(instance).count()
        rep['delivery_mode_display'] = dict(NotificationSchedule.DELIVERY_CHOICES).get(instance.delivery_mode, instance.delivery_mode)
        rep['target_roles_display'] = [
            dict(User.ROLE_CHOICES).get(role, role) for role in (instance.target_roles or [])
        ]
        rep['target_groups_display'] = list(
            Group.objects.filter(id__in=instance.target_group_ids or [])
            .order_by('name')
            .values_list('name', flat=True)
        )
        rep['target_courses_display'] = list(
            Course.objects.filter(id__in=instance.target_course_ids or [])
            .order_by('name')
            .values_list('name', flat=True)
        )
        return rep
