from django.utils import timezone

from academics.models import Student
from accounts.models import User
from communication.models import Notification, NotificationSchedule


def resolve_notification_recipients(schedule):
    target_roles = schedule.target_roles or []
    target_user_ids = schedule.target_user_ids or []
    target_group_ids = schedule.target_group_ids or []
    target_course_ids = schedule.target_course_ids or []

    base_queryset = User.objects.filter(organization_id=schedule.organization_id).exclude(is_superuser=True)

    recipient_ids = set()
    if target_roles:
        recipient_ids.update(base_queryset.filter(role__in=target_roles).values_list('id', flat=True))
    if target_user_ids:
        recipient_ids.update(base_queryset.filter(id__in=target_user_ids).values_list('id', flat=True))

    student_phone_set = set()
    if target_group_ids:
        student_phone_set.update(
            Student.objects.filter(
                organization_id=schedule.organization_id,
                student_groups__group_id__in=target_group_ids,
            ).values_list('phone', flat=True).distinct()
        )
    if target_course_ids:
        student_phone_set.update(
            Student.objects.filter(
                organization_id=schedule.organization_id,
                student_groups__group__course_id__in=target_course_ids,
            ).values_list('phone', flat=True).distinct()
        )

    if student_phone_set:
        recipient_ids.update(
            base_queryset.filter(
                role='student',
                username__in=student_phone_set,
            ).values_list('id', flat=True)
        )

    if not recipient_ids:
        return base_queryset.none()

    return base_queryset.filter(id__in=recipient_ids).distinct()


def dispatch_notification_schedule(schedule: NotificationSchedule):
    recipients = list(resolve_notification_recipients(schedule))
    if not recipients:
        schedule.status = 'failed'
        schedule.last_error = "Recipient topilmadi."
        schedule.total_sent = 0
        schedule.total_failed = 0
        schedule.sent_at = timezone.now()
        schedule.save(update_fields=['status', 'last_error', 'total_sent', 'total_failed', 'sent_at', 'updated_at'])
        return 0

    sent_count = 0
    failed_count = 0
    for user in recipients:
        try:
            Notification.objects.create(
                organization_id=schedule.organization_id,
                user=user,
                title=schedule.title,
                message=schedule.message,
                type='info',
                is_read=False,
            )
            sent_count += 1
        except Exception:
            failed_count += 1

    schedule.status = 'sent' if failed_count == 0 else 'failed'
    schedule.sent_at = timezone.now()
    schedule.total_sent = sent_count
    schedule.total_failed = failed_count
    schedule.last_error = "" if failed_count == 0 else f"{failed_count} recipientga yuborishda xato yuz berdi."
    schedule.save(update_fields=['status', 'sent_at', 'total_sent', 'total_failed', 'last_error', 'updated_at'])
    return sent_count
