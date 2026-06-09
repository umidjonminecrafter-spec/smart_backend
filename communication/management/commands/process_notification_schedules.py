from django.core.management.base import BaseCommand
from django.utils import timezone

from communication.models import NotificationSchedule
from communication.services import dispatch_notification_schedule


class Command(BaseCommand):
    help = "Process due scheduled notifications and create in-app notifications."

    def handle(self, *args, **options):
        now = timezone.now()
        schedules = NotificationSchedule.objects.filter(status='pending', send_at__lte=now)

        processed = 0
        for schedule in schedules:
            dispatch_notification_schedule(schedule)
            processed += 1

        self.stdout.write(self.style.SUCCESS(f"Processed {processed} scheduled notification(s)."))
