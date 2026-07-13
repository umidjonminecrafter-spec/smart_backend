from django.core.management.base import BaseCommand
from django.utils import timezone
from communication.models import SmsSchedules, SMSMessages

class Command(BaseCommand):
    help = "Process due scheduled SMS messages and create sent SMSMessage records."

    def handle(self, *args, **options):
        now = timezone.now()
        schedules = SmsSchedules.objects.filter(is_sent=False, scheduled_time__lte=now)

        processed = 0
        for schedule in schedules:
            # Create SMSMessages record
            SMSMessages.objects.create(
                organization_id=schedule.organization_id,
                recipient=schedule.recipient,
                message=schedule.message,
                status='sent'
            )
            # Mark schedule as sent
            schedule.is_sent = True
            schedule.save(update_fields=['is_sent', 'updated_at'])
            processed += 1

        self.stdout.write(self.style.SUCCESS(f"Processed {processed} scheduled SMS message(s)."))
