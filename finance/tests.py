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


class CashTransactionAPITests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Cash Test Org")
        self.admin = User.objects.create_user(
            username="cashadmin",
            password="securepassword",
            role="admin",
            organization=self.org
        )
        self.employee = User.objects.create_user(
            username="cashemployee",
            password="securepassword",
            role="teacher",
            organization=self.org
        )
        self.student = Student.objects.create(
            organization=self.org,
            first_name="Jane",
            last_name="Doe",
            phone="+998909876543",
            balance=0.00
        )

        from finance.models import Cashbox
        self.cashbox = Cashbox.objects.create(
            organization=self.org,
            name="Naqd pul",
            balance=Decimal("0.00")
        )

        self.client.force_authenticate(user=self.admin)

    def test_cash_transaction_kirim_student_required(self):
        """
        Verify that student is required for kirim (INCOME) if description/category contains student keywords.
        """
        url = reverse('transaction-create')
        data = {
            "cashbox": self.cashbox.id,
            "transaction_type": "kirim",
            "payment_method": "naqd",
            "amount": "150000.00",
            "date": "2026-07-01",
            "category_name": "o'quvchi to'ladi",
            "description": "Talaba dars to'lovi"
        }

        # Attempt without student -> should fail
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("student", response.data)

        # Attempt with student -> should pass
        data["student"] = self.student.id
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify kassa balance
        self.cashbox.refresh_from_db()
        self.assertEqual(self.cashbox.balance, Decimal("150000.00"))

    def test_cash_transaction_chiqim_employee_required(self):
        """
        Verify that employee is required for chiqim (EXPENSE) if description/category contains employee keywords.
        """
        url = reverse('transaction-create')
        data = {
            "cashbox": self.cashbox.id,
            "transaction_type": "chiqim",
            "payment_method": "naqd",
            "amount": "50000.00",
            "date": "2026-07-01",
            "category_name": "ish haqi oylik",
            "description": "Xodim oyligi"
        }

        # Attempt without employee -> should fail
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("employee", response.data)

        # Attempt with employee -> should pass
        data["employee"] = self.employee.id
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify kassa balance (starts at 0 before this test, so after subtracting 50000 it is -50000)
        self.cashbox.refresh_from_db()
        self.assertEqual(self.cashbox.balance, Decimal("-50000.00"))

    def test_transaction_report_api(self):
        """
        Verify that transaction report API returns CashTransaction serializer outputs correctly.
        """
        from finance.models import CashTransaction
        import datetime
        CashTransaction.objects.create(
            organization=self.org,
            cashbox=self.cashbox,
            transaction_type="kirim",
            payment_method="naqd",
            amount=Decimal("200000.00"),
            date=datetime.date(2026, 7, 1),
            student=self.student,
            category_name="o'quvchi to'lov",
            comment="Izoh matni"
        )

        url = reverse('transaction-report')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["student_name"], self.student.full_name)
        self.assertEqual(response.data[0]["description"], "Izoh matni")

