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

    def test_cashbox_transfer_success(self):
        """
        Verify that transferring money from one cashbox to another updates balances and creates CashTransactions.
        """
        from finance.models import Cashbox, CashTransaction
        import datetime

        # Give initial balance to self.cashbox
        CashTransaction.objects.create(
            organization=self.org,
            cashbox=self.cashbox,
            transaction_type="kirim",
            payment_method="naqd",
            amount=Decimal("1000000.00"),
            date=datetime.date(2026, 7, 1),
            student=self.student,
            category_name="o'quvchi to'lov",
            comment="Initial balance"
        )

        # Create second cashbox
        target_cashbox = Cashbox.objects.create(
            organization=self.org,
            name="Plastik karta",
            balance=Decimal("0.00")
        )
        CashTransaction.objects.create(
            organization=self.org,
            cashbox=target_cashbox,
            transaction_type="kirim",
            payment_method="naqd",
            amount=Decimal("200000.00"),
            date=datetime.date(2026, 7, 1),
            student=self.student,
            category_name="o'quvchi to'lov",
            comment="Initial target balance"
        )

        url = reverse('transaction-transfer')
        data = {
            "from_cashbox": self.cashbox.id,
            "to_cashbox": target_cashbox.id,
            "amount": "300000.00",
            "izoh": "Plastikka o'tkazma"
        }

        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("kassalararo muvaffaqiyatli o'tkazildi", response.data["detail"])

        # Verify balances
        self.cashbox.refresh_from_db()
        target_cashbox.refresh_from_db()

        # self.cashbox: 1000000 - 300000 = 700000
        # target_cashbox: 200000 + 300000 = 500000
        self.assertEqual(self.cashbox.balance, Decimal("700000.00"))
        self.assertEqual(target_cashbox.balance, Decimal("500000.00"))

        # Verify CashTransactions created
        txs = CashTransaction.objects.filter(category_name="Kassalararo o'tkazma").order_by('id')
        self.assertEqual(txs.count(), 2)

        self.assertEqual(txs[0].cashbox, self.cashbox)
        self.assertEqual(txs[0].transaction_type, "chiqim")
        self.assertEqual(txs[0].amount, Decimal("300000.00"))
        self.assertEqual(txs[0].employee, self.admin)

        self.assertEqual(txs[1].cashbox, target_cashbox)
        self.assertEqual(txs[1].transaction_type, "kirim")
        self.assertEqual(txs[1].amount, Decimal("300000.00"))
        self.assertEqual(txs[1].employee, self.admin)

        # Verify general Transactions created
        from finance.models import Transaction
        gen_txs = Transaction.objects.filter(description__icontains="Kassalararo o'tkazma").order_by('id')
        self.assertEqual(gen_txs.count(), 2)

        self.assertEqual(gen_txs[0].cashbox, self.cashbox)
        self.assertEqual(gen_txs[0].type, "EXPENSE")
        self.assertEqual(gen_txs[0].amount, Decimal("300000.00"))
        self.assertEqual(gen_txs[0].employee, self.admin)

        self.assertEqual(gen_txs[1].cashbox, target_cashbox)
        self.assertEqual(gen_txs[1].type, "INCOME")
        self.assertEqual(gen_txs[1].amount, Decimal("300000.00"))
        self.assertEqual(gen_txs[1].employee, self.admin)


class AnalyticsEndpointsTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Analytics Org")
        self.admin = User.objects.create_user(
            username="+998901112255",
            password="securepassword",
            role="admin",
            organization=self.org
        )
        self.client.force_authenticate(user=self.admin)

    def test_branch_monitoring_report(self):
        url = reverse('branch-monitoring')
        response = self.client.get(f"{url}?date=2026-06-23")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_teacher_efficiency_report(self):
        url = reverse('teacher-efficiency-report')
        response = self.client.get(f"{url}?from_date=2026-06-01&to_date=2026-06-19")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_efficiency_report(self):
        url = reverse('admin-efficiency-report')
        response = self.client.get(f"{url}?from_date=2026-06-01&to_date=2026-06-19")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_left_reasons_report(self):
        url = reverse('student-left-reasons-report')
        response = self.client.get(f"{url}?tab=all&from_date=2026-06-01&to_date=2026-06-20&time_resolution=kun")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unsubmitted_attendance_report(self):
        url = reverse('unsubmitted-attendance')
        response = self.client.get(f"{url}?from_date=2026-06-01&to_date=2026-06-23")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_revenue_plan_report(self):
        url = reverse('report-revenue-plan')
        response = self.client.get(f"{url}?branch=1&date=2026-06-19&status=active")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unpaid_payments_report(self):
        url = reverse('report-unpaid-payments')
        response = self.client.get(f"{url}?branch=1&start_date=2026-06-01")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cancelled_payments_report(self):
        url = reverse('report-cancelled-payments')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_discounts_bonuses_report(self):
        url = reverse('report-discounts-bonuses')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cash_flow_report(self):
        url = reverse('report-cash-flow')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_employee_balance_report(self):
        url = reverse('report-employee-balance')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FinanceSettingIntegrationTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Integration Test Org")
        self.manager = User.objects.create_user(
            username="+998901112277",
            password="securepassword",
            role="admin",
            is_staff=True,
            organization=self.org
        )
        self.client.force_authenticate(user=self.manager)
        
        from finance.models import Cashbox, FinanceSetting
        self.cashbox = Cashbox.objects.create(
            organization=self.org,
            name="Asosiy kassa",
            balance=0.00
        )
        
        self.setting = FinanceSetting.objects.create(
            organization=self.org,
            is_bonus_enabled=True,
            bonus_types=[
                {"id": 1, "name": "Buyurtma qo'shgani uchun bonus miqdori", "amount": "50000.00"},
                {"id": 2, "name": "Birinchi to'lovi uchun bonus miqdori", "amount": "30000.00"}
            ],
            is_penalty_enabled=True,
            penalty_types=[
                {"id": 1, "name": "To'lov qilmasdan ketgani uchun jarima", "amount": "15000.00"}
            ],
            is_percent_bonus_enabled=True,
            student_payment_percent="5.00",
            is_auto_discount_enabled=True,
            two_groups_discount_percent="10.00",
            three_groups_discount_percent="15.00",
            four_groups_discount_percent="20.00"
        )

    def test_lead_bonus_triggers(self):
        from crm.models import Lead
        from finance.models import Bonus, FinanceAction, Transaction

        # Create a lead
        Lead.objects.create(
            organization=self.org,
            name="Jane Doe",
            phone="+998905555555",
            created_by=self.manager
        )

        # Verify bonus creation
        bonus = Bonus.objects.filter(employee=self.manager).first()
        self.assertIsNotNone(bonus)
        self.assertEqual(bonus.amount, Decimal('50000.00'))

        # Verify FinanceAction
        action = FinanceAction.objects.filter(employee=self.manager, action_type='BONUS').first()
        self.assertIsNotNone(action)
        self.assertEqual(action.amount, Decimal('50000.00'))

        # Verify Transaction
        tx = Transaction.objects.filter(employee=self.manager, category='BONUS').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal('50000.00'))
        self.assertEqual(tx.type, 'EXPENSE')

    def test_first_payment_bonus_triggers(self):
        from academics.models import Student
        from finance.models import Payment, Bonus, FinanceAction, Transaction

        student = Student.objects.create(
            organization=self.org,
            first_name="Alice",
            phone="+998904444444",
            moderator=self.manager.id
        )

        # Create first payment
        Payment.objects.create(
            organization=self.org,
            student=student,
            amount=Decimal('100000.00'),
            date=timezone.now().date(),
            cashbox=self.cashbox,
            payment_method="Cash",
            employee=self.manager
        )

        # Moderator should get first payment bonus
        bonus = Bonus.objects.filter(employee=self.manager, reason__contains="Birinchi to'lov").first()
        self.assertIsNotNone(bonus)
        self.assertEqual(bonus.amount, Decimal('30000.00'))

    def test_finance_staff_payment_percent_bonus(self):
        from academics.models import Student
        from finance.models import Payment, Bonus

        student = Student.objects.create(
            organization=self.org,
            first_name="Bob",
            phone="+998903333333"
        )

        # Create payment
        Payment.objects.create(
            organization=self.org,
            student=student,
            amount=Decimal('200000.00'),
            date=timezone.now().date(),
            cashbox=self.cashbox,
            payment_method="Card",
            employee=self.manager
        )

        # Payment processor should get 5% bonus
        bonus = Bonus.objects.filter(employee=self.manager, reason__contains="Kirim to'lovi foiz bonusi").first()
        self.assertIsNotNone(bonus)
        # 5% of 200000 is 10000
        self.assertEqual(bonus.amount, Decimal('10000.00'))

    def test_student_leaving_unpaid_fine(self):
        from academics.models import Student, Group, Course, StudentGroupLeave
        from finance.models import Fine, FinanceAction

        course = Course.objects.create(
            organization=self.org,
            name="Physics",
            price=200000.00,
            duration_weeks=4
        )
        group = Group.objects.create(
            organization=self.org,
            name="Physics-1",
            course=course
        )
        student = Student.objects.create(
            organization=self.org,
            first_name="Charlie",
            phone="+998902222222",
            balance=Decimal('-1000.00'),  # negative balance
            moderator=self.manager.id
        )

        # Create leave record
        StudentGroupLeave.objects.create(
            organization=self.org,
            student=student,
            group=group,
            leave_date=timezone.now().date()
        )

        # Moderator should get penalty fine
        fine = Fine.objects.filter(employee=self.manager).first()
        self.assertIsNotNone(fine)
        self.assertEqual(fine.amount, Decimal('15000.00'))

        action = FinanceAction.objects.filter(employee=self.manager, action_type='PENALTY').first()
        self.assertIsNotNone(action)
        self.assertEqual(action.amount, Decimal('15000.00'))

    def test_auto_discount_applied_on_attendance(self):
        from academics.models import Student, Group, Course, StudentGroup, Attendance, charge_attendance
        from finance.models import Transaction

        course1 = Course.objects.create(organization=self.org, name="Bio", price=300000.00)
        course2 = Course.objects.create(organization=self.org, name="Chem", price=300000.00)
        
        group1 = Group.objects.create(organization=self.org, name="Bio-1", course=course1)
        group2 = Group.objects.create(organization=self.org, name="Chem-1", course=course2)

        student = Student.objects.create(
            organization=self.org,
            first_name="Diana",
            phone="+998901111111"
        )

        # Enroll in 2 groups
        StudentGroup.objects.create(organization=self.org, student=student, group=group1)
        StudentGroup.objects.create(organization=self.org, student=student, group=group2)

        # Charge attendance for group1 (monthly price: 300,000 UZS)
        # Lessons count in month (e.g. 27 days excluding Sundays)
        # Cost per lesson without discount: 300,000 / 27 = 11111.11 UZS
        # Cost with 10% discount: 11111.11 * 0.9 = 10000.00 UZS
        
        attendance = Attendance.objects.create(
            organization=self.org,
            group=group1,
            student=student,
            date=timezone.now().date(),
            status="present"
        )
        
        charge_attendance(student, group1, timezone.now().date(), attendance.id, self.org)
        
        # Verify transaction created with 10,000 UZS
        tx = Transaction.objects.filter(student=student, description__contains="Davomat").first()
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx.amount), 10000.00)

    def test_teacher_salary_percentage_fallback(self):
        from finance.models import StaffSalaryPercent, TeacherSalaryCalculation
        
        # Create StaffSalaryPercent
        percent_setting = StaffSalaryPercent.objects.create(
            organization=self.org,
            name="Senior Teacher",
            percent=Decimal('45.00')
        )
        
        # Create a teacher and link to percent_setting
        teacher = User.objects.create_user(
            username="+998901112288",
            password="securepassword",
            role="teacher",
            salary_percentage=percent_setting,
            organization=self.org
        )
        
        # We need to compute their salary. They have no specific TeacherSalaryRule.
        from academics.models import Course, Group, Student, StudentGroup
        course = Course.objects.create(organization=self.org, name="Math", price=200000.00)
        group = Group.objects.create(organization=self.org, name="Math-1", course=course, teacher=teacher)
        student = Student.objects.create(organization=self.org, first_name="Eve", phone="+998901234567")
        StudentGroup.objects.create(organization=self.org, student=student, group=group)
        
        # Calculate salary
        url = reverse('teacher-salary-calculate')
        data = {
            "period": "2026-07",
            "org_id": self.org.id
        }
        
        response = self.client.post(f"{url}?org_id={self.org.id}", data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Since they have 45% percentage set:
        # Total revenue: 200,000 UZS.
        # Expected payout: 200,000 * 0.45 = 90,000 UZS
        calc = TeacherSalaryCalculation.objects.get(teacher=teacher, period='2026-07')
        self.assertEqual(float(calc.calculated_amount), 90000.00)

    def test_finance_setting_sync_to_actions(self):
        from finance.models import FinanceAction
        
        # Verify they are synced as FinanceAction
        bonuses = FinanceAction.objects.filter(
            organization=self.org,
            action_type='BONUS',
            student__isnull=True,
            employee__isnull=True
        )
        self.assertEqual(bonuses.count(), 2)
        
        penalties = FinanceAction.objects.filter(
            organization=self.org,
            action_type='PENALTY',
            student__isnull=True,
            employee__isnull=True
        )
        self.assertEqual(penalties.count(), 1)
        
        # Modify settings to remove one bonus and add a new penalty
        self.setting.bonus_types = [
            {"id": 1, "name": "Buyurtma qo'shgani uchun bonus miqdori", "amount": "60000.00"}
        ]
        self.setting.penalty_types = [
            {"id": 1, "name": "To'lov qilmasdan ketgani uchun jarima", "amount": "15000.00"},
            {"id": 2, "name": "Yangi jarima", "amount": "25000.00"}
        ]
        self.setting.save()
        
        # Verify sync updated the amount, deleted the removed bonus, and added the new penalty
        bonuses = FinanceAction.objects.filter(
            organization=self.org,
            action_type='BONUS',
            student__isnull=True,
            employee__isnull=True
        )
        self.assertEqual(bonuses.count(), 1)
        self.assertEqual(bonuses.first().reason, "Buyurtma qo'shgani uchun bonus miqdori")
        self.assertEqual(bonuses.first().amount, Decimal('60000.00'))
        
        penalties = FinanceAction.objects.filter(
            organization=self.org,
            action_type='PENALTY',
            student__isnull=True,
            employee__isnull=True
        )
        self.assertEqual(penalties.count(), 2)

    def test_debtor_payment_percent_bonus(self):
        from academics.models import Student
        from finance.models import Payment, Bonus

        # Set debtor percent to 8% in settings
        self.setting.debtor_balance_percent = Decimal('8.00')
        self.setting.save()

        # Create a debtor student (balance < 0)
        student = Student.objects.create(
            organization=self.org,
            first_name="Frank",
            phone="+998901234569",
            balance=Decimal('-500.00')
        )

        Payment.objects.create(
            organization=self.org,
            student=student,
            amount=Decimal('1000.00'),
            date=timezone.now().date(),
            cashbox=self.cashbox,
            payment_method="Cash",
            employee=self.manager
        )

        # 8% of 1000 is 80 UZS
        bonus = Bonus.objects.filter(employee=self.manager, reason__contains="qarzdorlik to'lovi").first()
        self.assertIsNotNone(bonus)
        self.assertEqual(bonus.amount, Decimal('80.00'))

    def test_employee_salary_calculation_with_all_settings(self):
        from finance.models import StaffSalaryPercent, Salary, Payment
        from academics.models import Student
        from datetime import date
        
        # Link manager to a salary percentage (e.g. 10%)
        percent_setting = StaffSalaryPercent.objects.create(
            organization=self.org,
            name="Manager level",
            percent=Decimal('10.00')
        )
        self.manager.salary_percentage = percent_setting
        self.manager.save()

        # Enable count bonus and KPI settings
        self.setting.is_count_bonus_enabled = True
        self.setting.has_money_students_amount = Decimal('12000.00')  # active student count bonus
        self.setting.debtor_students_amount = Decimal('8000.00')  # zero debtors bonus
        self.setting.kpi_settings = {
            "target_revenue": "100000.00",
            "kpi_bonus": "15000.00"
        }
        self.setting.save()

        # Process a payment by the manager (total payments = 200,000 UZS)
        student = Student.objects.create(organization=self.org, first_name="Grace", phone="+998908888888", balance=Decimal('0.00'))
        Payment.objects.create(
            organization=self.org,
            student=student,
            amount=Decimal('200000.00'),
            date=date(2026, 7, 15),
            cashbox=self.cashbox,
            employee=self.manager
        )

        # Calculate salary
        url = reverse('salary-calculate')
        data = {
            "period": "2026-07"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Let's verify calculated salary:
        # Base salary (10% of 200,000) = 20,000 UZS
        # Active students (Grace balance >= 0, so count > 0) bonus = 12,000 UZS
        # Debtors (0 debtors) bonus = 8,000 UZS
        # KPI target revenue (payments 200,000 >= 100,000 target) bonus = 15,000 UZS
        # Expected base salary + bonuses = 20000 + 12000 + 8000 + 15000 = 55,000 UZS + bonuses
        
        salary_rec = Salary.objects.filter(employee=self.manager, date=date(2026, 7, 15)).first()
        self.assertIsNotNone(salary_rec)
        self.assertTrue(salary_rec.amount >= Decimal('55000.00'))






