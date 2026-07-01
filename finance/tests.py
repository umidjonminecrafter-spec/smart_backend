from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from organizations.models import Organization
from academics.models import Course, Student, Group, StudentGroup, Holiday
from finance.models import TeacherSalaryRule, TeacherSalaryCalculation

User = get_user_model()

class HolidayImpactTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Holiday Test Org")
        self.teacher = User.objects.create_user(
            username="testteacher",
            password="securepassword",
            role="teacher",
            organization=self.org
        )
        self.admin_user = User.objects.create_user(
            username="testadmin",
            password="securepassword",
            role="admin",
            organization=self.org
        )
        self.client.force_authenticate(user=self.teacher)

        self.course = Course.objects.create(
            organization=self.org,
            name="Math",
            price=200000.00,
            duration_weeks=12
        )
        self.group = Group.objects.create(
            organization=self.org,
            name="Math-1",
            course=self.course,
            teacher=self.teacher
        )
        self.student = Student.objects.create(
            organization=self.org,
            first_name="John",
            last_name="Doe",
            phone="+998901112233",
            balance=0.00
        )
        self.student_group = StudentGroup.objects.create(
            organization=self.org,
            student=self.student,
            group=self.group
        )

        # Create a rule for fixed salary
        self.fixed_rule = TeacherSalaryRule.objects.create(
            organization=self.org,
            teacher=self.teacher,
            rule_type='fixed',
            rate=Decimal('1000000.00'),
            period='2026-05',
            is_active=True
        )

    def test_fixed_salary_holiday_deduction(self):
        # Create a staff impact holiday in May 2026 (3 days)
        Holiday.objects.create(
            organization=self.org,
            name="May Day Holiday",
            start_date=timezone.datetime(2026, 5, 1).date(),
            end_date=timezone.datetime(2026, 5, 3).date(),
            staff_impact=True,
            student_impact=False
        )

        url = reverse('teacher-salary-calculate')
        data = {
            "period": "2026-05",
            "org_id": self.org.id
        }
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(f"{url}?org_id={self.org.id}", data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # May has 31 days. 3 days holiday.
        # Expected payout: 1,000,000 * (1 - 3/31) = 1,000,000 * 28/31 = 903225.81
        calc = TeacherSalaryCalculation.objects.get(teacher=self.teacher, period='2026-05')
        expected_amount = Decimal('1000000.00') * (Decimal(28) / Decimal(31))
        self.assertAlmostEqual(float(calc.calculated_amount), float(expected_amount), places=2)

    def test_student_price_holiday_discount(self):
        # Create a student impact holiday in the current month (e.g. 5 days)
        now = timezone.now().date()
        import calendar
        _, last_day = calendar.monthrange(now.year, now.month)
        
        # Clear existing holidays to be sure
        Holiday.objects.all().delete()
        
        # Create holiday starting at the start of the month for 5 days
        h_start = now.replace(day=1)
        h_end = now.replace(day=5)
        
        Holiday.objects.create(
            organization=self.org,
            name="Student Holiday",
            start_date=h_start,
            end_date=h_end,
            staff_impact=False,
            student_impact=True
        )

        url = reverse('student-group-detail', kwargs={'pk': self.student_group.id})
        response = self.client.get(f"{url}?org_id={self.org.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Expected price: 200,000 * (1 - 5 / last_day)
        expected_price = Decimal('200000.00') * (Decimal(last_day - 5) / Decimal(last_day))
        self.assertAlmostEqual(float(response.data['price']), float(expected_price), places=2)
