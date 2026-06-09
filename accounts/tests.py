from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from organizations.models import Organization

User = get_user_model()

class AccountsAPITests(APITestCase):
    def test_register_creates_user_and_organization(self):
        """
        Ensure user registration works and automatically creates a new organization.
        """
        url = reverse('account-register')
        data = {
            "password": "testpassword123",
            "email": "owner@talim.com",
            "phone": "+998901112233",
            "full_name": "John Doe",
            "organization_name": "John's Academy"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['username'], '+998901112233')
        
        # Verify organization is created
        org_name = response.data['user']['organization_name']
        self.assertEqual(org_name, "John's Academy")
        self.assertTrue(Organization.objects.filter(name="John's Academy").exists())

    def test_login_returns_token_and_user_info(self):
        """
        Ensure login validates credentials and returns tokens.
        """
        org = Organization.objects.create(name="Login Test Org")
        user = User.objects.create_user(
            username="+998901112234",
            password="securepassword",
            email="test@talim.com",
            phone="+998901112234",
            role="owner",
            organization=org
        )
        
        url = reverse('account-login')
        data = {
            "username": "+998901112234",
            "password": "securepassword"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], '+998901112234')

    def test_profile_update_photo(self):
        """
        Ensure user profile photo can be updated via PATCH request.
        """
        org = Organization.objects.create(name="Profile Test Org")
        user = User.objects.create_user(
            username="+998901112235",
            password="securepassword",
            email="test@talim.com",
            phone="+998901112235",
            role="employee",
            organization=org
        )
        self.client.force_authenticate(user=user)
        
        # Create a mock image file
        from django.core.files.uploadedfile import SimpleUploadedFile
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9'
            b'\x04\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00'
            b'\x00\x02\x02\x4c\x01\x00\x3b'
        )
        photo = SimpleUploadedFile('avatar.gif', small_gif, content_type='image/gif')
        
        url = reverse('account-profile')
        response = self.client.patch(url, {'photo': photo}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['photo'])

