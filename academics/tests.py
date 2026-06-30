from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from organizations.models import Organization
from academics.models import Course, Student, Group

User = get_user_model()


class AcademicsAPITests(APITestCase):
    def setUp(self):
        # Create two distinct organizations to test multi-tenancy
        self.org1 = Organization.objects.create(name="Tenant 1")
        self.org2 = Organization.objects.create(name="Tenant 2")

        # Create active subscription for Org 1 and Org 2
        from organizations.models import Subscription, Tariff
        import datetime
        from decimal import Decimal
        today = datetime.date.today()
        default_tariff = Tariff.objects.create(name="Premium", price=Decimal("100.00"), student_limit=0)
        Subscription.objects.create(
            organization=self.org1,
            tariff=default_tariff,
            start_date=today,
            end_date=today + datetime.timedelta(days=365),
            is_active=True
        )
        Subscription.objects.create(
            organization=self.org2,
            tariff=default_tariff,
            start_date=today,
            end_date=today + datetime.timedelta(days=365),
            is_active=True
        )

        # User for tenant 1
        self.user1 = User.objects.create_user(
            username="teacher1",
            password="password123",
            role="admin",
            organization=self.org1
        )

        # User without organization
        self.user_no_org = User.objects.create_user(
            username="noorguser",
            password="password123",
            role="admin",
            organization=None
        )

        # Course and Student for tenant 1
        self.course1 = Course.objects.create(
            organization=self.org1,
            name="English Advanced",
            price=150.00,
            duration_weeks=12
        )
        self.student1 = Student.objects.create(
            organization=self.org1,
            first_name="Alice",
            last_name="Green",
            phone="+998909998877",
            balance=0.00
        )

        # Student for tenant 2
        self.student2 = Student.objects.create(
            organization=self.org2,
            first_name="Bob",
            last_name="Brown",
            phone="+998906665544",
            balance=0.00
        )

    def test_student_list_tenant_isolation(self):
        """
        Ensure student lists are isolated to the active tenant/organization.
        """
        # Try retrieving students with a user that has no organization, and no org_id query param
        self.client.force_authenticate(user=self.user_no_org)
        url = reverse('student-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

        # Authenticate as user of Org 1, request without org_id -> falls back to user org (Org 1) -> returns Alice
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['first_name'], "Alice")

        # Authenticate as user of Org 1, and explicitly request Org 2.
        # Since self.user1 is NOT a superuser, the override is ignored, and it falls back to Org 1 -> returns Alice (NOT Bob)
        response = self.client.get(f"{url}?org_id={self.org2.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['first_name'], "Alice")

        # Create a superuser to verify they CAN override the active organization
        superuser = User.objects.create_superuser(
            username="superuser",
            password="superpassword",
            email="super@admin.com"
        )
        self.client.force_authenticate(user=superuser)

        # Superuser explicitly requests Org 2 -> returns Bob
        response = self.client.get(f"{url}?org_id={self.org2.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['first_name'], "Bob")

        # Superuser requests specifying Org 1 explicitly via header -> returns Alice
        response = self.client.get(url, HTTP_X_ORG_ID=str(self.org1.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['first_name'], "Alice")

    def test_add_payment_updates_balance(self):
        """
        Ensure the add-payment student action updates the student's balance.
        """
        self.client.force_authenticate(user=self.user1)
        url = reverse('student-add-payment', kwargs={'pk': self.student1.id})

        data = {
            "amount": 250.00,
            "payment_method": "card"
        }

        response = self.client.post(f"{url}?org_id={self.org1.id}", data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['balance']), 250.00)

        # Verify student balance updated in DB
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.balance, 250.00)

    def test_delete_student_creates_archive(self):
        """
        Ensure deleting a student creates an archive entry with the provided reason and comment.
        """
        from academics.models import StudentArchive
        self.client.force_authenticate(user=self.user1)
        url = reverse('student-detail', kwargs={'pk': self.student1.id})

        # Call DELETE with reason and comment parameters
        response = self.client.delete(f"{url}?org_id={self.org1.id}&reason=To'lov&comment=Qarzdorlik sababli")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify student is deleted
        self.assertFalse(Student.objects.filter(id=self.student1.id).exists())

        # Verify archive entry exists with correct details
        archive = StudentArchive.objects.get(phone=self.student1.phone)
        self.assertEqual(archive.reason, "To'lov")
        self.assertEqual(archive.comment, "Qarzdorlik sababli")
        self.assertEqual(archive.organization, self.org1)

    def test_archive_student_deactivates_user_and_restores(self):
        """
        Verify that archiving a student deletes the corresponding User object,
        freeing the phone number, and restoring recreates the User object.
        """
        from accounts.models import User
        from academics.models import StudentArchive

        # Create a user object for student1
        User.objects.create_user(
            username=self.student1.phone,
            password="studentpassword",
            phone=self.student1.phone,
            role="student",
            organization=self.org1
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('student-detail', kwargs={'pk': self.student1.id})

        # Archive student1
        response = self.client.delete(f"{url}?org_id={self.org1.id}&reason=TestReason&comment=TestComment")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 1. Verify student User is deleted
        self.assertFalse(User.objects.filter(username=self.student1.phone, role="student").exists())

        # 2. Verify we can create a new student with that phone number (since it's freed)
        student_create_url = reverse('student-list')
        data = {
            "first_name": "NewAlice",
            "last_name": "NewGreen",
            "phone": self.student1.phone,
            "password": "newpassword123",
            "balance": 0.00
        }
        create_response = self.client.post(f"{student_create_url}?org_id={self.org1.id}", data=data)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        # 3. Verify we can restore the archived student (should fail if username conflict, but let's delete the newly created user first to test successful restore)
        # Delete new student and their user directly from DB to avoid a second archive entry
        new_student_id = create_response.data['id']
        Student.objects.filter(id=new_student_id).delete()
        User.objects.filter(username=self.student1.phone).delete()

        # Now restore the archived student
        archive_entry = StudentArchive.objects.get(phone=self.student1.phone)
        restore_url = reverse('student-archive-restore', kwargs={'pk': archive_entry.id})
        restore_response = self.client.post(f"{restore_url}?org_id={self.org1.id}")
        self.assertEqual(restore_response.status_code, status.HTTP_200_OK)

        # Verify User is recreated
        self.assertTrue(User.objects.filter(username=self.student1.phone, role="student").exists())

    def test_attendance_billing_logic(self):
        """
        Verify that marking a student as present/late deducts money from their balance,
        creates a Transaction in the Cashbox, and changing status or deleting refunds it.
        """
        import datetime
        from decimal import Decimal
        from academics.models import StudentGroup, Attendance, GroupLesson
        from finance.models import Cashbox, Transaction

        # 1. Update course price to a larger amount
        self.course1.price = Decimal("120000.00")
        self.course1.save()

        # 2. Create Group
        group = Group.objects.create(
            organization=self.org1,
            course=self.course1,
            name="Group 1",
            status="active",
            days=["mon", "wed", "fri"]
        )

        # 3. Link Student to Group
        StudentGroup.objects.create(
            organization=self.org1,
            student=self.student1,
            group=group,
            price=Decimal("120000.00")
        )

        # 4. Generate 12 GroupLessons in June 2026
        lessons = []
        for i in range(1, 13):
            lessons.append(
                GroupLesson(
                    organization=self.org1,
                    group=group,
                    date=datetime.date(2026, 6, i)
                )
            )
        GroupLesson.objects.bulk_create(lessons)

        # 5. Verify initial balance
        self.assertEqual(self.student1.balance, Decimal("0.00"))

        # 6. Create attendance on 2026-06-01 as 'present'
        att = Attendance.objects.create(
            organization=self.org1,
            student=self.student1,
            group=group,
            date=datetime.date(2026, 6, 1),
            status="present"
        )

        # Check student balance (should be -10,000.00)
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.balance, Decimal("-10000.00"))

        # Check Cashbox balance (should be 10,000.00)
        cashbox = Cashbox.objects.filter(organization=self.org1).first()
        self.assertIsNotNone(cashbox)
        self.assertEqual(cashbox.balance, Decimal("10000.00"))

        # Check Transaction was created
        tx = Transaction.objects.filter(description__startswith=f"Davomat #{att.id}:").first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal("10000.00"))
        self.assertEqual(tx.type, "INCOME")

        # 7. Update attendance status to 'absent'
        att.status = "absent"
        att.save()

        # Check student balance restored to 0
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.balance, Decimal("0.00"))

        # Check Cashbox balance goes back to 0
        cashbox.refresh_from_db()
        self.assertEqual(cashbox.balance, Decimal("0.00"))

        # Check Transaction was deleted
        self.assertFalse(Transaction.objects.filter(description__startswith=f"Davomat #{att.id}:").exists())

