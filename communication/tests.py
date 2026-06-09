from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from organizations.models import Organization, Branch
from academics.models import Course, Group, Student, StudentGroup
from communication.models import NotificationSchedule, Notification
from communication.services import dispatch_notification_schedule
from organizations.admin import send_notification_to_organizations

User = get_user_model()

class NotificationScheduleAPITests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org")
        self.branch = Branch.objects.create(name="Test Branch", organization=self.org)
        self.user = User.objects.create_user(
            username="+998901112236",
            password="securepassword",
            email="owner@talim.com",
            phone="+998901112236",
            role="owner",
            organization=self.org
        )
        # Create some users
        self.employee = User.objects.create_user(
            username="+998901112237",
            password="securepassword",
            email="emp@talim.com",
            phone="+998901112237",
            role="employee",
            organization=self.org
        )
        self.teacher = User.objects.create_user(
            username="+998901112238",
            password="securepassword",
            email="teacher@talim.com",
            phone="+998901112238",
            role="teacher",
            organization=self.org
        )
        self.student_user = User.objects.create_user(
            username="+998901112239",
            password="securepassword",
            email="student@talim.com",
            phone="+998901112239",
            role="student",
            organization=self.org
        )
        # Create Course
        self.course = Course.objects.create(
            name="Math Course",
            price=200000.00,
            organization=self.org,
            branch=self.branch
        )
        # Create Student and Group link
        self.student = Student.objects.create(
            first_name="Jane",
            last_name="Doe",
            phone="+998901112239",
            organization=self.org,
            branch=self.branch
        )
        self.group = Group.objects.create(
            name="Math 101",
            course=self.course,
            organization=self.org,
            branch=self.branch
        )
        StudentGroup.objects.create(
            student=self.student,
            group=self.group,
            organization=self.org,
            branch=self.branch
        )

        self.client.force_authenticate(user=self.user)
        # Mock active branch in headers
        self.client.credentials(HTTP_X_BRANCH_ID=str(self.branch.id))

    def test_send_immediate_without_send_at(self):
        """
        Ensure sending an immediate notification (via send-now endpoint)
        does not fail validation when send_at is missing from the payload.
        """
        url = "/api/v1/communication/notification-schedules/send-now/"
        data = {
            "title": "Urgent Alert",
            "message": "This is an immediate notification.",
            "target_roles": ["employee"]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('schedule', response.data)
        self.assertEqual(response.data['schedule']['delivery_mode'], 'immediate')
        self.assertIsNotNone(response.data['schedule']['send_at'])

    def test_dispatch_to_multiple_recipients(self):
        """
        Test that dispatch_notification_schedule successfully resolves and
        creates notifications for target roles, target users, and target groups.
        """
        schedule = NotificationSchedule.objects.create(
            title="Bulk Announcement",
            message="Hello everyone!",
            delivery_mode="immediate",
            target_roles=["teacher", "employee"],
            target_user_ids=[self.user.id],
            target_group_ids=[self.group.id],
            organization=self.org,
            branch=self.branch,
            created_by=self.user
        )

        sent_count = dispatch_notification_schedule(schedule)
        self.assertEqual(sent_count, 4)
        self.assertEqual(Notification.objects.filter(title="Bulk Announcement").count(), 4)
        self.assertTrue(Notification.objects.filter(user=self.teacher, title="Bulk Announcement").exists())
        self.assertTrue(Notification.objects.filter(user=self.employee, title="Bulk Announcement").exists())
        self.assertTrue(Notification.objects.filter(user=self.user, title="Bulk Announcement").exists())
        self.assertTrue(Notification.objects.filter(user=self.student_user, title="Bulk Announcement").exists())

    def test_admin_send_notification_to_organizations_targets_only_ceos(self):
        """
        Test that send_notification_to_organizations Django Admin action
        creates notifications targeting only CEO (owner role) users in the organization.
        """
        # We simulate the POST apply request
        factory = RequestFactory()
        request = factory.post('/admin/organizations/organization/', {
            'apply': 'Apply',
            'title': 'System Maintenance',
            'message': 'Database will undergo upgrade.',
            'notification_type': 'info',
            '_selected_action': [str(self.org.id)]
        })
        request.user = self.user
        
        # Mock message storage that doesn't require middleware
        from django.contrib.messages.storage.base import BaseStorage
        class MockMessageStorage(BaseStorage):
            def _get(self):
                return [], True
            def _store(self, messages, response):
                return []
        
        request._messages = MockMessageStorage(request)

        # Queryset of organizations
        queryset = Organization.objects.filter(id=self.org.id)

        # Mock ModelAdmin
        class MockModelAdmin:
            def message_user(self, request, message, level):
                pass

        # Call the admin action
        response = send_notification_to_organizations(MockModelAdmin(), request, queryset)
        
        # Verify redirect response
        self.assertEqual(response.status_code, 302)

        # Verify created notifications
        notifications = Notification.objects.filter(title='System Maintenance')
        # Should be exactly 1, targeting the owner user (self.user)
        self.assertEqual(notifications.count(), 1)
        
        notif = notifications.first()
        self.assertEqual(notif.user, self.user) # owner role
        self.assertEqual(notif.organization, self.org)

        # Employees or other users should NOT have a notification record created for them in database
        self.assertFalse(Notification.objects.filter(user=self.employee, title='System Maintenance').exists())
        self.assertFalse(Notification.objects.filter(user=self.teacher, title='System Maintenance').exists())
        self.assertFalse(Notification.objects.filter(user=self.student_user, title='System Maintenance').exists())
