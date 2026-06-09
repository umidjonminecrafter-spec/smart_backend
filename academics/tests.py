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

