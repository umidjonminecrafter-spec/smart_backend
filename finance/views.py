from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status, decorators, generics, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from decimal import Decimal
from django.db import transaction
from django.db import transaction as db_transaction
from django.utils.dateparse import parse_date
from crm.models import Pipeline, Lead
from organizations.mixins import TenantViewSetMixin
from django.db.models.functions import TruncDate, Coalesce
from organizations.permissions import HasOrganizationPagePermission
from datetime import datetime, time
from finance.models import (
    ExpenseCategory, ExpenseSubcategory, Expense, MonthlyIncome,
    Payment, Sale, Bonus, Fine, Salary, TeacherSalaryRule, TeacherSalaryCalculation, Cashbox, CashTransaction,
    TransactionCategory, Transaction
)
from finance.serializers import (
    ExpenseCategorySerializer, ExpenseSubcategorySerializer, ExpenseSerializer,
    MonthlyIncomeSerializer, PaymentSerializer, SaleSerializer, BonusSerializer,
    FineSerializer, SalarySerializer, TeacherSalaryRuleSerializer, TeacherSalaryCalculationSerializer, CashboxSerializer
)
from academics.models import Student, Group, StudentGroup, TeacherSalaryPayment,GroupLesson
from academics.serializers import StudentSerializer, TeacherSalaryPaymentSerializer
from django.contrib.auth import get_user_model

from finance.serializers import CashTransactionSerializer, CashTransferSerializer
from organizations.models import TenantModel

from .serializers import FinanceActionSerializer, TransactionSerializer, TransactionCategorySerializer
from .filters import BonusFilter, FineFilter

User = get_user_model()


def get_active_branch_id(request):
    branch_id = request.query_params.get('branch') or request.query_params.get('branch_id')
    if branch_id:
        return branch_id
    branch_id = request.META.get('HTTP_X_BRANCH_ID') or request.headers.get('x-branch-id')
    if branch_id:
        return branch_id
    if request.user and request.user.is_authenticated:
        return getattr(request.user, 'branch_id', None)
    return None


class ExpenseCategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Xarajatlar'
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer


from decimal import Decimal
from rest_framework import viewsets, status, decorators
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework import filters


class TransactionViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['type', 'category', 'cashbox']
    search_fields = ['description', 'student__full_name', 'employee__username']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']

    def get_queryset(self):
        branch_id = self.get_branch_id()
        print("LOG: TransactionViewSet - branch_id from request:", branch_id, "query_params:", self.request.query_params, "headers:", {k: v for k, v in self.request.headers.items() if 'branch' in k.lower() or 'authorization' in k.lower()})
        return super().get_queryset()


class TransactionTypesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return self._get_types_response()

    def post(self, request, *args, **kwargs):
        return self._get_types_response()

    def put(self, request, *args, **kwargs):
        return self._get_types_response()

    def patch(self, request, *args, **kwargs):
        return self._get_types_response()

    def delete(self, request, *args, **kwargs):
        return self._get_types_response()

    # Asosiy ma'lumot qaytaruvchi logika
    def _get_types_response(self):
        types = [
            {"key": key, "label": label}
            for key, label in Transaction.TRANSACTION_TYPES
        ]
        categories = [
            {"key": key, "label": label}
            for key, label in Transaction.CATEGORY_CHOICES
        ]

        return Response({
            "types": types,  # Kirim, Chiqim
            "categories": categories  # To'g'ridan-to'g'ri, Bonus, Jarima, Voucher, Oylik
        }, status=status.HTTP_200_OK)


class ExpenseSubcategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Xarajatlar'
    queryset = ExpenseSubcategory.objects.all()
    serializer_class = ExpenseSubcategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category']


from django.db import transaction as db_transaction


class ExpenseViewSet(TenantViewSetMixin,
                     viewsets.ModelViewSet):  # Agar TenantViewSetMixin kerak bo'lsa, merosxo'rlikka qaytarib qo'ying
    permission_page_name = 'Xarajatlar'
    queryset = Expense.objects.all().select_related('category', 'subcategory', 'cashbox')
    serializer_class = ExpenseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['category', 'subcategory', 'cashbox']
    search_fields = ['description']
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()

        # Date range filtering
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        # Category filtering
        category_id = self.request.query_params.get('expense_category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Search query
        search_query = self.request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(description__icontains=search_query)

        # Payment type / Cashbox filtering
        payment_type = self.request.query_params.get('payment_type')
        if payment_type:
            queryset = queryset.filter(cashbox_id=payment_type)

        return queryset

    def perform_create(self, serializer):
        with db_transaction.atomic():
            user = self.request.user
            org = getattr(user, 'organization', None)

            if not org:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"detail": "Sizda hech qanday tashkilot biriktirilmagan! Tizimga qayta kiring."})

            save_kwargs = {'organization': org}

            # Agar filial (branch) ham bo'lsa biriktiramiz
            branch_id = self.get_branch_id()
            if branch_id:
                from organizations.models import Branch
                try:
                    save_kwargs['branch'] = Branch.objects.get(id=branch_id)
                except Branch.DoesNotExist:
                    pass

            # Xarajatni saqlaymiz
            expense = serializer.save(**save_kwargs)

            # TO'G'RILANDI: Kassa balansini bu yerda QO'LDA o'zgartirmaymiz va
            # Transaction'ni ham qo'lda yaratmaymiz! Expense modelidagi
            # `expense_transaction_mirror_sync` signali (models.py) buni AVTOMATIK
            # va TO'G'RI bajaradi - shu bilan birga kassa balansi ham yagona
            # (Transaction asosidagi) formula bo'yicha to'g'ri qayta hisoblanadi.

    @decorators.action(detail=False, methods=['get'], url_path='monthly-summary')
    def monthly_summary(self, request):
        # Tashkilot ID'sini olish qismi
        org_id = getattr(request.user, 'organization_id', None) or self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Faqat joriy tashkilot xarajatlari
        expenses = Expense.objects.filter(cashbox__tenant_id=org_id) if hasattr(Cashbox,
                                                                                'tenant') else Expense.objects.all()

        summary = {}
        for exp in expenses:
            if exp.date:
                month_key = exp.date.strftime('%Y-%m')
                summary[month_key] = summary.get(month_key, Decimal('0.00')) + exp.amount

        result = [{"month": k, "total_expense": v} for k, v in sorted(summary.items())]
        return Response(result, status=status.HTTP_200_OK)


class DetailedExpenseViewSet(TenantViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Detailed views of expenses with helper reports.
    """
    permission_page_name = 'Xarajatlar'
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer

    @decorators.action(detail=False, methods=['get'], url_path='chart-data')
    def chart_data(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        expenses = Expense.objects.filter(organization_id=org_id)
        by_category = {}
        by_month = {}

        for exp in expenses:
            cat_name = exp.category.name
            month_name = exp.date.strftime('%B %Y')

            by_category[cat_name] = by_category.get(cat_name, Decimal('0.00')) + exp.amount
            by_month[month_name] = by_month.get(month_name, Decimal('0.00')) + exp.amount

        return Response({
            "category_data": [{"category": k, "amount": v} for k, v in by_category.items()],
            "monthly_data": [{"month": k, "amount": v} for k, v in by_month.items()]
        }, status=status.HTTP_200_OK)

    @decorators.action(detail=False, methods=['get'], url_path='directors-summary')
    def directors_summary(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        expenses = Expense.objects.filter(organization_id=org_id)
        total_exp = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        highest_expense = expenses.order_by('-amount').first()

        # Breakdown by category
        breakdown = expenses.values('category__name').annotate(total=Sum('amount')).order_by('-total')

        return Response({
            "total_expenses": total_exp,
            "highest_single_expense": {
                "description": highest_expense.description if highest_expense else "",
                "amount": highest_expense.amount if highest_expense else Decimal('0.00'),
                "date": highest_expense.date if highest_expense else None
            },
            "category_breakdown": breakdown
        }, status=status.HTTP_200_OK)


class MonthlyIncomeViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Barcha to\'lovlar'
    queryset = MonthlyIncome.objects.all()
    serializer_class = MonthlyIncomeSerializer

    @decorators.action(detail=True, methods=['get'], url_path='net-profit')
    def net_profit(self, request, pk=None):
        income = self.get_object()
        org_id = self.get_organization_id()

        # Calculate expenses for the same month/year
        start_date = income.date.replace(day=1)
        # Simple end date calculation for month boundary
        if income.date.month == 12:
            end_date = income.date.replace(year=income.date.year + 1, month=1, day=1)
        else:
            end_date = income.date.replace(month=income.date.month + 1, day=1)

        total_expenses = Expense.objects.filter(
            organization_id=org_id,
            date__gte=start_date,
            date__lt=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        net = income.amount - total_expenses
        return Response({
            "month": income.date.strftime('%Y-%m'),
            "income": income.amount,
            "expenses": total_expenses,
            "net_profit": net
        }, status=status.HTTP_200_OK)


class PaymentViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Barcha to\'lovlar'
    queryset = Payment.objects.all().select_related('student', 'employee')
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['student', 'payment_method']
    search_fields = ['student__first_name', 'student__last_name', 'comment']
    pagination_class = None


class SaleViewSet(TenantViewSetMixin, viewsets.ReadOnlyModelViewSet):
    permission_page_name = 'Moliya'
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer

    @decorators.action(detail=False, methods=['get'])
    def statistics(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        sales = Sale.objects.filter(organization_id=org_id)
        stats = sales.aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        total = stats['total'] or Decimal('0.00')
        count = stats['count'] or 0
        avg = total / count if count > 0 else Decimal('0.00')

        return Response({
            "total_sales_amount": total,
            "total_sales_count": count,
            "average_sale_value": avg
        }, status=status.HTTP_200_OK)

    @decorators.action(detail=False, methods=['get'], url_path='active-count')
    def active_count(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)
        # In our CRM context, active sales can be mocked or count of sales in the current month
        count = Sale.objects.filter(organization_id=org_id, date__month=timezone.now().date().month).count()
        return Response({"active_sales_count_current_month": count}, status=status.HTTP_200_OK)


class BonusViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Ish haqi'
    queryset = Bonus.objects.all().order_by('-id')
    serializer_class = BonusSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = BonusFilter
    search_fields = ['reason', 'employee__first_name', 'employee__last_name']


class FineViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Ish haqi'
    queryset = Fine.objects.all().order_by('-id')
    serializer_class = FineSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = FineFilter
    search_fields = ['reason', 'employee__first_name', 'employee__last_name']


class SalaryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Ish haqi'
    queryset = Salary.objects.all().select_related('employee')
    serializer_class = SalarySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'status']
    pagination_class = None

    @decorators.action(detail=False, methods=['post'])
    def calculate(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        period = request.data.get('period') or request.data.get('month')  # Support both period and month
        if not period:
            return Response({"detail": "Period (YYYY-MM) is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Parse year/month
        try:
            year, month = map(int, period.split('-'))
            # TO'G'RILANDI: timezone datetime xatoligi to'g'ri Python datetime obyektiga o'tkazildi
            calc_date = datetime(year, month, 15).date()
        except ValueError:
            return Response({"detail": "Invalid period format. Use YYYY-MM."}, status=status.HTTP_400_BAD_REQUEST)

        from finance.models import FinanceSetting
        setting = FinanceSetting.objects.filter(organization_id=org_id).first()

        employees = User.objects.filter(organization_id=org_id).exclude(is_superuser=True)
        calculated = []
        for emp in employees:
            # Simple employee salary base calculation: check if there's rules or configure default
            # Deduct fines and add bonuses in the same period
            bonuses = \
            Bonus.objects.filter(employee=emp, date__year=year, date__month=month).aggregate(total=Sum('amount'))[
                'total'] or Decimal('0.00')
            fines = \
            Fine.objects.filter(employee=emp, date__year=year, date__month=month).aggregate(total=Sum('amount'))[
                'total'] or Decimal('0.00')

            # 1. StaffSalaryPercent (Oylik foizlari) integration
            base_salary = Decimal('0.00')
            if emp.salary_percentage:
                payments_sum = Payment.objects.filter(
                    employee=emp,
                    date__year=year,
                    date__month=month
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                base_salary = payments_sum * (Decimal(str(emp.salary_percentage.percent)) / Decimal('100.00'))
                base_salary = round(base_salary, 2)
            else:
                base_salary = Decimal('1000.00')  # Default base salary
                if emp.role == 'manager':
                    base_salary = Decimal('1500.00')
                elif emp.role == 'admin':
                    base_salary = Decimal('2000.00')

            total_salary = base_salary + bonuses - fines

            # 2. Count-based bonus integration
            if setting and setting.is_count_bonus_enabled:
                from academics.models import Student
                active_count = Student.objects.filter(organization_id=org_id, balance__gte=0).count()
                debtor_count = Student.objects.filter(organization_id=org_id, balance__lt=0).count()

                if active_count > 0 and setting.has_money_students_amount > 0:
                    total_salary += Decimal(str(setting.has_money_students_amount))
                if debtor_count == 0 and setting.debtor_students_amount > 0:
                    total_salary += Decimal(str(setting.debtor_students_amount))

            # 3. KPI target revenue bonus integration
            if setting and setting.kpi_settings:
                target_revenue = Decimal(str(setting.kpi_settings.get('target_revenue', '0.00')))
                kpi_bonus = Decimal(str(setting.kpi_settings.get('kpi_bonus', '0.00')))
                if target_revenue > 0 and kpi_bonus > 0:
                    total_revenue = Payment.objects.filter(
                        organization_id=org_id,
                        date__year=year,
                        date__month=month
                    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    if total_revenue >= target_revenue:
                        total_salary += kpi_bonus

            # Upsert
            sal, created = Salary.objects.update_or_create(
                organization_id=org_id,
                employee=emp,
                date=calc_date,
                defaults={'amount': total_salary, 'status': 'unpaid'}
            )
            calculated.append(sal)

        return Response({
            "detail": f"Salaries calculated successfully for {len(calculated)} employees.",
            "period": period
        }, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=['get'])
    def summary(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        salaries = Salary.objects.filter(organization_id=org_id)
        paid = salaries.filter(status='paid').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        unpaid = salaries.filter(status='unpaid').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        return Response({
            "total_paid": paid,
            "total_unpaid": unpaid,
            "total_calculated": paid + unpaid
        }, status=status.HTTP_200_OK)


class TeacherSalaryRuleViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Ish haqi'
    queryset = TeacherSalaryRule.objects.all()
    serializer_class = TeacherSalaryRuleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['teacher', 'is_active']

    def perform_create(self, serializer):
        org_id = self.get_organization_id()
        if not org_id:
            raise exceptions.ValidationError({"detail": "Organization context is required."})

        branch_id = self.get_branch_id()
        instance = serializer.save(organization_id=org_id, branch_id=branch_id)

        override_all = self.request.data.get('override_all')
        if override_all is True or str(override_all).lower() == 'true':
            if instance.teacher is None:
                # O'sha period uchun barcha individual tariflarni o'chiramiz
                TeacherSalaryRule.objects.filter(
                    organization_id=org_id,
                    period=instance.period,
                    teacher__isnull=False
                ).delete()

    def perform_update(self, serializer):
        instance = serializer.save()

        override_all = self.request.data.get('override_all')
        if override_all is True or str(override_all).lower() == 'true':
            if instance.teacher is None:
                org_id = self.get_organization_id()
                # O'sha period uchun barcha individual tariflarni o'chiramiz
                TeacherSalaryRule.objects.filter(
                    organization_id=org_id,
                    period=instance.period,
                    teacher__isnull=False
                ).delete()

    @decorators.action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        rules_data = request.data.get('rules', [])
        created_rules = []
        for r_data in rules_data:
            teacher_id = r_data.get('teacher')
            rule_type = r_data.get('rule_type')
            rate = r_data.get('rate')
            period = r_data.get('period', '2026-05')

            rule = TeacherSalaryRule.objects.create(
                organization_id=org_id,
                branch_id=self.get_branch_id(),
                teacher_id=teacher_id,
                rule_type=rule_type,
                rate=Decimal(str(rate)),
                period=period,
                is_active=True
            )
            created_rules.append(rule)

        return Response(TeacherSalaryRuleSerializer(created_rules, many=True).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=['get'], url_path='get-by-period')
    def get_by_period(self, request):
        org_id = self.get_organization_id()
        period = request.query_params.get('period')
        if not org_id or not period:
            return Response({"detail": "Organization and period query params are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        rules = TeacherSalaryRule.objects.filter(organization_id=org_id, period=period)
        return Response(TeacherSalaryRuleSerializer(rules, many=True).data, status=status.HTTP_200_OK)

    @decorators.action(detail=False, methods=['post'], url_path='configure-period')
    def configure_period(self, request):
        org_id = self.get_organization_id()
        source_period = request.data.get('source_period')
        target_period = request.data.get('target_period')

        if not org_id or not source_period or not target_period:
            return Response({"detail": "org_id, source_period, and target_period are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Copy rules from source to target
        source_rules = TeacherSalaryRule.objects.filter(organization_id=org_id, period=source_period)
        copied = []
        for rule in source_rules:
            new_rule = TeacherSalaryRule.objects.create(
                organization_id=org_id,
                branch_id=self.get_branch_id(),
                teacher=rule.teacher,
                rule_type=rule.rule_type,
                rate=rule.rate,
                period=target_period,
                is_active=True
            )
            copied.append(new_rule)

        return Response({
            "detail": f"Successfully configured period {target_period} by copying {len(copied)} rules from {source_period}."
        }, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=['get'], url_path='active-periods')
    def active_periods(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        periods = TeacherSalaryRule.objects.filter(organization_id=org_id).values_list('period', flat=True).distinct()
        return Response(list(periods), status=status.HTTP_200_OK)

    @decorators.action(detail=False, methods=['get'], url_path='period-summary')
    def period_summary(self, request):
        org_id = self.get_organization_id()
        period = request.query_params.get('period')
        if not org_id or not period:
            return Response({"detail": "Organization and period query params are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        rules = TeacherSalaryRule.objects.filter(organization_id=org_id, period=period)
        count = rules.count()
        avg_rate = rules.aggregate(avg=Sum('rate'))['avg'] or Decimal('0.00')
        if count > 0:
            avg_rate = avg_rate / count

        return Response({
            "period": period,
            "total_rules": count,
            "average_rate": avg_rate
        }, status=status.HTTP_200_OK)


class TeacherSalaryCalculationViewSet(TenantViewSetMixin, viewsets.ReadOnlyModelViewSet):
    permission_page_name = 'Ish haqi'
    queryset = TeacherSalaryCalculation.objects.all()
    serializer_class = TeacherSalaryCalculationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['teacher', 'period']
    pagination_class = None

    @decorators.action(detail=False, methods=['get'], url_path='monthly-report')
    def monthly_report(self, request):
        org_id = self.get_organization_id()
        period = request.query_params.get('period')
        if not org_id or not period:
            return Response({"detail": "org_id and period query params are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        calcs = TeacherSalaryCalculation.objects.filter(organization_id=org_id, period=period)
        total_payout = calcs.aggregate(total=Sum('calculated_amount'))['total'] or Decimal('0.00')

        return Response({
            "period": period,
            "total_calculated_payout": total_payout,
            "teachers_count": calcs.count(),
            "calculations": TeacherSalaryCalculationSerializer(calcs, many=True).data
        }, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        with transaction.atomic():
            # 1. Oylik hisob-kitobini saqlaymiz
            salary_calc = serializer.save()

            # 2. Frontenddan qaysi kassadan oylik berilayotgani keladi
            cashbox_id = self.request.data.get('cashbox')
            if not cashbox_id:
                raise serializers.ValidationError({"cashbox": "Oylik berish uchun kassa tanlanishi shart!"})

            cashbox = Cashbox.objects.get(id=cashbox_id)

            # 3. Haqiqatda kassadan chiqib ketadigan yakuniy summani hisoblaymiz:
            # Formula: (Asosiy Oylik + Bonuslar) - (Avans + Jarimalar)
            # eslatma: field nomlarini o'zingizning modelingizga qarab moslab olasiz
            final_payout = (salary_calc.calculated_amount + salary_calc.bonus) - (
                    salary_calc.advance + salary_calc.penalty)

            # 4. Moliyaviy tranzaksiya yaratamiz (Chiqim)
            # TO'G'RILANDI: organization qo'shildi (avval yo'q edi - NOT NULL xatoligi
            # berishi mumkin edi) va category='SALARY' qilib belgilandi.
            Transaction.objects.create(
                organization=cashbox.organization,
                cashbox=cashbox,
                amount=final_payout,
                type='EXPENSE',
                category='SALARY',
                employee=salary_calc.teacher,
                description=f"Oylik to'lovi: {salary_calc.teacher} uchun ({salary_calc.period} davri)"
            )

            # TO'G'RILANDI: Kassa balansini bu yerda QO'LDA kamaytirmaymiz!
            # Yuqoridagi Transaction.objects.create() chaqirilganda
            # `recompute_cashbox_balance` signali (models.py) kassa balansini
            # AVTOMATIK va TO'G'RI (yagona formula asosida) qayta hisoblaydi.


class TeacherSalaryCalculateView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Ish haqi'
    """
    POST: Triggers Teacher Salary calculation for a period.
    """

    def post(self, request):
        from decimal import Decimal
        import calendar
        from django.db.models import Q
        from academics.models import Holiday, StudentPricing

        org_id = self.get_organization_id()
        period = request.data.get('period') or request.data.get('month')  # Support both period and month

        if not org_id or not period:
            return Response({"detail": "org_id and period are required in payload."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            year, month = map(int, period.split('-'))
            _, last_day = calendar.monthrange(year, month)
            month_start = timezone.datetime(year, month, 1).date()
            month_end = timezone.datetime(year, month, last_day).date()
        except ValueError:
            return Response({"detail": "Invalid period format. Use YYYY-MM."}, status=status.HTTP_400_BAD_REQUEST)

        teachers = User.objects.filter(organization_id=org_id, role='teacher')
        calcs = []

        # Get subscription/account settings for salary rules
        from organizations.models import Subscription
        subscription = Subscription.objects.filter(
            organization_id=org_id,
            is_active=True
        ).first()

        # Find standard fallback rule for the organization
        std_rule = TeacherSalaryRule.objects.filter(
            organization_id=org_id,
            teacher__isnull=True,
            period=period,
            is_active=True
        ).first()
        if not std_rule:
            std_rule = TeacherSalaryRule.objects.filter(
                organization_id=org_id,
                teacher__isnull=True,
                is_active=True
            ).order_by('-created_at').first()

        # Query holidays for the month with staff_impact=True
        staff_holidays = Holiday.objects.filter(
            organization_id=org_id,
            staff_impact=True,
            start_date__lte=month_end
        )
        staff_holidays = staff_holidays.filter(Q(end_date__gte=month_start) | Q(end_date__isnull=True))

        holiday_dates = set()
        for h in staff_holidays:
            start = max(h.start_date, month_start)
            end = min(h.end_date or h.start_date, month_end)
            curr = start
            while curr <= end:
                holiday_dates.add(curr)
                curr += timezone.timedelta(days=1)
        holiday_days_count = len(holiday_dates)

        # Query holidays for the month with student_impact=True
        student_holidays = Holiday.objects.filter(
            organization_id=org_id,
            student_impact=True,
            start_date__lte=month_end
        )
        student_holidays = student_holidays.filter(Q(end_date__gte=month_start) | Q(end_date__isnull=True))

        stud_holiday_dates = set()
        for h in student_holidays:
            start = max(h.start_date, month_start)
            end = min(h.end_date or h.start_date, month_end)
            curr = start
            while curr <= end:
                stud_holiday_dates.add(curr)
                curr += timezone.timedelta(days=1)
        stud_holiday_days = len(stud_holiday_dates)

        student_discount = Decimal(1)
        if stud_holiday_days > 0 and last_day > 0:
            student_discount = Decimal(1) - (Decimal(stud_holiday_days) / Decimal(last_day))

        for teacher in teachers:
            # Find rule for this teacher
            rule = TeacherSalaryRule.objects.filter(
                organization_id=org_id,
                teacher=teacher,
                period=period,
                is_active=True
            ).first()

            if not rule:
                # Use teacher's profile salary percentage if set
                if teacher.salary_percentage:
                    rule_type = 'percentage'
                    rate = Decimal(str(teacher.salary_percentage.percent))
                # Use default standard rule if available, otherwise static fallback
                elif std_rule:
                    rule_type = std_rule.rule_type
                    rate = std_rule.rate
                else:
                    rule_type = 'fixed'
                    rate = Decimal('800.00')
            else:
                rule_type = rule.rule_type
                rate = rule.rate

            details = {"rule_type": rule_type, "rate": str(rate)}
            calculated_amount = Decimal('0.00')

            if rule_type == 'fixed':
                if holiday_days_count > 0 and last_day > 0:
                    discount_factor = Decimal(1) - (Decimal(holiday_days_count) / Decimal(last_day))
                    calculated_amount = rate * discount_factor
                    details['holiday_days_deducted'] = holiday_days_count
                    details['original_rate'] = str(rate)
                else:
                    calculated_amount = rate

            elif rule_type == 'per_student' or rule_type == 'percentage':
                # Enrolled students count in classes taught by this teacher
                student_groups = StudentGroup.objects.filter(
                    group__teacher=teacher,
                    organization_id=org_id
                )

                # Apply subscription settings dynamically
                if subscription:
                    if subscription.ignore_trial_salary:
                        # Exclude students whose first name indicates a trial/mock entry
                        student_groups = student_groups.exclude(student__first_name__icontains='trial').exclude(
                            student__first_name__icontains='sinov')

                student_count = student_groups.count()

                if rule_type == 'per_student':
                    base_amount = rate * student_count
                    if holiday_days_count > 0 and last_day > 0:
                        discount_factor = Decimal(1) - (Decimal(holiday_days_count) / Decimal(last_day))
                        calculated_amount = base_amount * discount_factor
                        details['holiday_days_deducted'] = holiday_days_count
                        details['original_rate'] = str(base_amount)
                    else:
                        calculated_amount = base_amount
                    details['student_count'] = student_count

                else:  # percentage
                    from academics.models import Attendance
                    attendances = Attendance.objects.filter(
                        group__teacher=teacher,
                        organization_id=org_id,
                        date__year=year,
                        date__month=month,
                        status__in=['present', 'late']
                    ).select_related('student', 'group')
                    
                    student_groups = StudentGroup.objects.filter(group__teacher=teacher,
                                                                 organization_id=org_id)
                    student_count = student_groups.count()
                    
                    if attendances.exists():
                        # Calculate based on lessons/attendances
                        total_earned = Decimal('0.00')
                        attendance_charges = {}
                        
                        for att in attendances:
                            monthly_price = Decimal('0.00')
                            sg = StudentGroup.objects.filter(student=att.student, group=att.group).first()
                            if sg and sg.price is not None:
                                monthly_price = sg.price
                            elif att.group.course:
                                monthly_price = att.group.course.price
                                
                            try:
                                from finance.models import FinanceSetting
                                setting = FinanceSetting.objects.filter(organization_id=org_id).first()
                                if setting and setting.is_auto_discount_enabled:
                                    groups_count = StudentGroup.objects.filter(student=att.student).count()
                                    discount_percent = Decimal('0.00')
                                    if groups_count == 2:
                                        discount_percent = Decimal(str(setting.two_groups_discount_percent))
                                    elif groups_count == 3:
                                        discount_percent = Decimal(str(setting.three_groups_discount_percent))
                                    elif groups_count >= 4:
                                        discount_percent = Decimal(str(setting.four_groups_discount_percent))
                                    
                                    if discount_percent > 0:
                                        monthly_price = monthly_price * (Decimal('1.00') - (discount_percent / Decimal('100.00')))
                            except Exception as e:
                                print(f"Error applying auto discount: {str(e)}")
                                
                            from academics.models import get_lessons_in_month
                            lessons_in_month = get_lessons_in_month(att.group, att.date.year, att.date.month)
                            lesson_cost = monthly_price / Decimal(lessons_in_month)
                            lesson_cost = round(lesson_cost, 2)
                            
                            share = lesson_cost * (rate / Decimal('100.00'))
                            share = round(share, 2)
                            total_earned += share
                            attendance_charges[str(att.id)] = str(share)
                            
                        calculated_amount = total_earned
                        details['student_count'] = student_count
                        details['attendance_charges'] = attendance_charges
                        details['calculated_from_lessons'] = True
                    else:
                        # Fallback to monthly student pricing enrollment calculation
                        total_revenue = Decimal('0.00')
                        student_groups = StudentGroup.objects.filter(group__teacher=teacher,
                                                                     organization_id=org_id).select_related('group',
                                                                                                            'group__course')
                        
                        student_ids = [sg.student_id for sg in student_groups]
                        course_ids = [sg.group.course_id for sg in student_groups if sg.group and sg.group.course]

                        pricings = StudentPricing.objects.filter(student_id__in=student_ids, course_id__in=course_ids)
                        pricing_map = {(p.student_id, p.course_id): p.custom_price for p in pricings}

                        for sg in student_groups:
                            custom_price = None
                            if sg.group and sg.group.course:
                                custom_price = pricing_map.get((sg.student_id, sg.group.course_id))

                            if custom_price is not None:
                                price = custom_price
                            else:
                                price = sg.price or getattr(sg.group, 'price', None) or (
                                    sg.group.course.price if sg.group and sg.group.course else Decimal('0.00'))

                            total_revenue += price * student_discount

                        calculated_amount = total_revenue * (rate / Decimal('100.00'))
                        details['student_count'] = student_count
                        details['total_revenue'] = str(total_revenue)
                        if stud_holiday_days > 0:
                            details['student_holiday_days'] = stud_holiday_days

            elif rule_type == 'per_hour':
                from academics.models import LessonSchedule

                schedules = LessonSchedule.objects.filter(group__teacher=teacher, organization_id=org_id)
                if schedules.exists():
                    total_hours = Decimal('0.00')
                    even_schedules = [s for s in schedules if s.day_type == 'even']
                    odd_schedules = [s for s in schedules if s.day_type == 'odd']

                    curr = month_start
                    while curr <= month_end:
                        # Skip holidays
                        if curr in holiday_dates:
                            curr += timezone.timedelta(days=1)
                            continue

                        weekday = curr.weekday()
                        day_schedules = []
                        if weekday in (1, 3, 5):  # Tue, Thu, Sat
                            day_schedules = even_schedules
                        elif weekday in (0, 2, 4):  # Mon, Wed, Fri
                            day_schedules = odd_schedules

                        for s in day_schedules:
                            from datetime import datetime, combine
                            duration = datetime.combine(curr, s.end_time) - datetime.combine(curr, s.start_time)
                            hours = Decimal(duration.total_seconds()) / Decimal('3600.0')
                            total_hours += hours

                        curr += timezone.timedelta(days=1)

                    hours_taught = total_hours
                    details['calculated_via_schedules'] = True
                else:
                    hours_taught = max(Decimal('0.00'), Decimal('24.00') - Decimal(holiday_days_count * 2))
                    details['calculated_via_schedules'] = False

                calculated_amount = rate * hours_taught
                details['hours_taught'] = str(hours_taught)
                if holiday_days_count > 0:
                    details['holiday_days_deducted'] = holiday_days_count

            calc, created = TeacherSalaryCalculation.objects.update_or_create(
                organization_id=org_id,
                teacher=teacher,
                period=period,
                defaults={'calculated_amount': calculated_amount, 'details': details}
            )
            calcs.append(calc)

        return Response({
            "detail": f"Teacher salaries calculated successfully for {len(calcs)} teachers.",
            "period": period,
            "results": TeacherSalaryCalculationSerializer(calcs, many=True).data
        }, status=status.HTTP_201_CREATED)


class TeacherSalaryPaymentsView(TenantViewSetMixin, viewsets.ReadOnlyModelViewSet):
    # This matches /teacher-salary-payments/ endpoints in finance
    permission_page_name = 'Ish haqi'
    queryset = TeacherSalaryPayment.objects.all()
    serializer_class = TeacherSalaryPaymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['teacher']
    pagination_class = None

    @decorators.action(detail=False, methods=['get'])
    def summary(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        payments = TeacherSalaryPayment.objects.filter(organization_id=org_id)
        total = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        count = payments.count()
        return Response({
            "total_salary_paid": total,
            "payments_count": count
        }, status=status.HTTP_200_OK)


class StudentDebtsView(TenantViewSetMixin, generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Qarzdorlar'
    serializer_class = StudentSerializer

    def get_queryset(self):
        org_id = self.get_organization_id()
        if not org_id:
            return Student.objects.none()
        from django.db.models import Q
        qs = Student.objects.filter(organization_id=org_id, balance__lt=0)
        branch_id = self.get_branch_id()
        if branch_id:
            qs = qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
        return qs


class StudentDebtsSummaryView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Qarzdorlar'

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        from django.db.models import Q
        branch_id = self.get_branch_id()
        base_filter = Q(organization_id=org_id, balance__lt=0, is_archived=False)
        if branch_id:
            base_filter &= (Q(branch_id=branch_id) | Q(branch__isnull=True))

        total_debt = Student.objects.filter(base_filter).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        return Response({
            "total_student_debts": abs(total_debt),
            "debtors_count": Student.objects.filter(base_filter).count()
        }, status=status.HTTP_200_OK)


class StudentDebtDetailView(TenantViewSetMixin, generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Qarzdorlar'
    serializer_class = StudentSerializer

    def get_queryset(self):
        org_id = self.get_organization_id()
        from django.db.models import Q
        qs = Student.objects.filter(organization_id=org_id, balance__lt=0)
        branch_id = self.get_branch_id()
        if branch_id:
            qs = qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
        return qs


class TeacherDebtsView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Qarzdorlar'

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Teachers whose calculations are greater than payments made to them
        teachers = User.objects.filter(organization_id=org_id, role='teacher')
        debts = []

        for t in teachers:
            # Get total calculated amount
            total_calc = TeacherSalaryCalculation.objects.filter(teacher=t).aggregate(total=Sum('calculated_amount'))[
                             'total'] or Decimal('0.00')
            # Get total paid amount
            total_paid = TeacherSalaryPayment.objects.filter(teacher=t).aggregate(total=Sum('amount'))[
                             'total'] or Decimal('0.00')

            diff = total_calc - total_paid
            if diff > 0:
                debts.append({
                    "teacher_id": t.id,
                    "teacher_name": t.get_full_name() or t.username,
                    "total_calculated": total_calc,
                    "total_paid": total_paid,
                    "outstanding_debt": diff
                })

        return Response(debts, status=status.HTTP_200_OK)


class TeacherDebtsSummaryView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Qarzdorlar'

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Sum outstanding calculations
        teachers = User.objects.filter(organization_id=org_id, role='teacher')
        total_teacher_debt = Decimal('0.00')
        count = 0
        for t in teachers:
            total_calc = TeacherSalaryCalculation.objects.filter(teacher=t).aggregate(total=Sum('calculated_amount'))[
                             'total'] or Decimal('0.00')
            total_paid = TeacherSalaryPayment.objects.filter(teacher=t).aggregate(total=Sum('amount'))[
                             'total'] or Decimal('0.00')
            diff = total_calc - total_paid
            if diff > 0:
                total_teacher_debt += diff
                count += 1

        return Response({
            "total_teacher_debts": total_teacher_debt,
            "teachers_in_debt_count": count
        }, status=status.HTTP_200_OK)


class AllDebtsView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Qarzdorlar'

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Combined student and teacher debts
        student_debt = Student.objects.filter(organization_id=org_id, balance__lt=0).aggregate(total=Sum('balance'))[
                           'total'] or Decimal('0.00')
        student_debt_abs = abs(student_debt)

        # Teacher debts calculation
        teachers = User.objects.filter(organization_id=org_id, role='teacher')
        teacher_debt_val = Decimal('0.00')
        for t in teachers:
            total_calc = TeacherSalaryCalculation.objects.filter(teacher=t).aggregate(total=Sum('calculated_amount'))[
                             'total'] or Decimal('0.00')
            total_paid = TeacherSalaryPayment.objects.filter(teacher=t).aggregate(total=Sum('amount'))[
                             'total'] or Decimal('0.00')
            diff = total_calc - total_paid
            if diff > 0:
                teacher_debt_val += diff

        return Response({
            "student_debts": student_debt_abs,
            "teacher_debts": teacher_debt_val,
            "total_debts": student_debt_abs + teacher_debt_val
        }, status=status.HTTP_200_OK)


class CashboxViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Moliya'
    queryset = Cashbox.objects.all()
    serializer_class = CashboxSerializer
    pagination_class = None


class FinanceReportView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Moliya'

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        filters = {'organization_id': org_id}
        branch_id = self.get_branch_id()
        if branch_id:
            from django.db.models import Q
            payment_filter = Q(organization_id=org_id) & (Q(branch_id=branch_id) | Q(branch__isnull=True))
            expense_filter = Q(organization_id=org_id) & (Q(branch_id=branch_id) | Q(branch__isnull=True))
            payments_sum = Payment.objects.filter(payment_filter).aggregate(total=Sum('amount'))['total'] or Decimal(
                '0.00')
            expenses_sum = Expense.objects.filter(expense_filter).aggregate(total=Sum('amount'))['total'] or Decimal(
                '0.00')
        else:
            payments_sum = Payment.objects.filter(organization_id=org_id).aggregate(total=Sum('amount'))[
                               'total'] or Decimal('0.00')
            expenses_sum = Expense.objects.filter(organization_id=org_id).aggregate(total=Sum('amount'))[
                               'total'] or Decimal('0.00')

        return Response({
            "total_income": payments_sum,
            "total_expense": expenses_sum,
            "net_profit": payments_sum - expenses_sum
        }, status=status.HTTP_200_OK)


class CompanyProfitChartView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Moliya'

    def get(self, request):
        import datetime
        from django.db.models import Sum
        from decimal import Decimal
        from finance.models import Payment, Expense, Salary
        from academics.models import TeacherSalaryPayment

        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        branch_id = self.get_branch_id()

        today = datetime.date.today()
        months = []
        for i in range(5, -1, -1):
            month_offset = today.month - i
            year_offset = today.year
            while month_offset <= 0:
                month_offset += 12
                year_offset -= 1
            months.append((year_offset, month_offset))

        labels = []
        values = []

        uz_months = {
            1: "Yan", 2: "Fev", 3: "Mar", 4: "Apr", 5: "May", 6: "Iyun",
            7: "Iyul", 8: "Avg", 9: "Sen", 10: "Okt", 11: "Nov", 12: "Dek"
        }

        for year, month in months:
            p_filter = {'organization_id': org_id, 'date__year': year, 'date__month': month}
            e_filter = {'organization_id': org_id, 'date__year': year, 'date__month': month}
            s_filter = {'organization_id': org_id, 'date__year': year, 'date__month': month, 'status': 'paid'}
            t_filter = {'organization_id': org_id, 'paid_at__year': year, 'paid_at__month': month}

            if branch_id:
                from django.db.models import Q
                p_filter['branch_id'] = branch_id
                e_filter['branch_id'] = branch_id
                s_filter['branch_id'] = branch_id
                t_filter['branch_id'] = branch_id

            total_income = Payment.objects.filter(**p_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            total_expense = Expense.objects.filter(**e_filter).aggregate(total=Sum('amount'))['total'] or Decimal(
                '0.00')
            total_salary = Salary.objects.filter(**s_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            total_teacher_salary = TeacherSalaryPayment.objects.filter(**t_filter).aggregate(total=Sum('amount'))[
                                       'total'] or Decimal('0.00')

            net_profit = total_income - (total_expense + total_salary + total_teacher_salary)

            year_short = str(year)[2:]
            label = f"{uz_months[month]} {year_short}"
            labels.append(label)
            values.append(float(net_profit))

        return Response({
            "labels": labels,
            "values": values
        }, status=status.HTTP_200_OK)


class WithdrawalViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Yechib olish'
    serializer_class = PaymentSerializer
    pagination_class = None

    def get_queryset(self):
        org_id = self.get_organization_id()
        if not org_id:
            return Payment.objects.none()
        from django.db.models import Q
        qs = Payment.objects.filter(organization_id=org_id, amount__lt=0)
        branch_id = self.get_branch_id()
        if branch_id:
            qs = qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
        return qs

    def perform_create(self, serializer):
        # Ensure the amount is saved as negative when creating a withdrawal
        amount = serializer.validated_data.get('amount')
        if amount and amount > 0:
            serializer.validated_data['amount'] = -amount

        # TO'G'RILANDI: Talaba balansini bu yerda QO'LDA yangilamaymiz!
        # Payment modelida `payment_student_balance_update` degan post_save signal bor,
        # u serializer.save() chaqirilganda AVTOMATIK ravishda
        # student.balance += instance.amount qiladi. Bu yerda ham qo'lda qo'shilsa,
        # balans HAR SAFAR ikki baravar (2x) o'zgarardi.
        serializer.save(organization_id=self.get_organization_id(), branch_id=self.get_branch_id())

    def perform_destroy(self, instance):
        # TO'G'RILANDI: Talaba balansini bu yerda QO'LDA qaytarmaymiz!
        # Payment modelida `payment_student_balance_delete` degan post_delete signal bor,
        # u instance.delete() chaqirilganda AVTOMATIK ravishda
        # student.balance -= instance.amount qiladi. Bu yerda ham qo'lda ayirilsa,
        # balans HAR SAFAR ikki baravar (2x) o'zgarardi.
        instance.delete()


class ConversionReportsFunnelView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Konversiya hisoboti'

    """
    Sotuv voronkasi, jadval va grafiklar uchun to'liq analitika endpointi.
    """

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Abdulmajid so'ragan barcha filtrlarni qabul qilish (Section'ga moslandi)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        marketing_id = request.query_params.get('marketing')
        section_id = request.query_params.get('course')  # Frontend 'course' deb yuboraveradi
        moderator_id = request.query_params.get('moderator')
        teacher_id = request.query_params.get('teacher')
        source_id = request.query_params.get('source')

        pipelines = Pipeline.objects.filter(organization_id=org_id).order_by('order')

        if not pipelines.exists():
            return Response({
                "table_data": [],
                "funnel_chart": [],
                "linear_chart": {"labels": [], "total_leads": [], "lost_leads": [], "sales_count": []},
                "course_chart": {"labels": [], "values": []}
            }, status=status.HTTP_200_OK)

        # Baza filterlash uchun umumiy query yaratamiz
        base_filter = Q(organization_id=org_id, is_archived=False)

        if start_date:
            base_filter &= Q(created_at__date__gte=start_date)
        if end_date:
            base_filter &= Q(created_at__date__lte=end_date)
        if marketing_id:
            base_filter &= Q(marketing_id=marketing_id)
        if section_id:
            base_filter &= Q(section_id=section_id)  # 🌟 TO'G'RILANDI: course_id -> section_id
        if moderator_id:
            base_filter &= Q(moderator_id=moderator_id)
        if teacher_id:
            base_filter &= Q(group__teacher_id=teacher_id)
        if source_id:
            base_filter &= Q(source_id=source_id)

        # 2. O'ng tomondagi Voronka grafik ma'lumotlari (Pipeline'lar bo'yicha)
        funnel_chart_data = []
        for pl in pipelines:
            lead_count = Lead.objects.filter(base_filter & Q(pipeline=pl)).count()
            funnel_chart_data.append({
                "pipeline_id": pl.id,
                "pipeline_name": pl.name,
                "total_leads": lead_count
            })

        # 3. Chap tomondagi Jadval (Table) ma'lumotlari (1 dan 11 gacha bo'lgan statistikalar)
        stats = Lead.objects.filter(base_filter).aggregate(
            total_orders=Count('id'),
            left_before_trial=Count('id', filter=Q(status='LEFT_BEFORE_TRIAL')),
            trial_registered=Count('id', filter=Q(status='TRIAL_REGISTERED')),
            trial_missed=Count('id', filter=Q(status='TRIAL_MISSED')),
            trial_attended=Count('id', filter=Q(status='TRIAL_ATTENDED')),
            converted_to_group=Count('id', filter=Q(status='CONVERTED')),
            first_payment=Count('id', filter=Q(status='PAID')),
            first_payment_left=Count('id', filter=Q(status='PAID_BUT_LEFT')),
            finished=Count('id', filter=Q(status='FINISHED')),
            moved_to_branch=Count('id', filter=Q(status='MOVED_BRANCH')),
        )

        table_data = [
            {"id": 1, "status_name": "Barcha buyurtmalar soni", "count": stats['total_orders']},
            {"id": 2, "status_name": "Buyurtmadan ketganlar", "count": stats['left_before_trial']},
            {"id": 3, "status_name": "Sinov darsiga yozilganlar", "count": stats['trial_registered']},
            {"id": 4, "status_name": "Sinov darsiga kelmay ketganlar", "count": stats['trial_missed']},
            {"id": 5, "status_name": "Sinov darsiga kelganlar", "count": stats['trial_attended']},
            {"id": 6, "status_name": "Sinov darsiga kelib ketganlar", "count": stats['converted_to_group']},
            {"id": 7, "status_name": "Birinchi to'lovni qilganlar", "count": stats['first_payment']},
            {"id": 8, "status_name": "Birinchi to'lovni qibly ketganlar", "count": stats['first_payment_left']},
            {"id": 9, "status_name": "Tugatganlar", "count": stats['finished']},
            {"id": 10, "status_name": "Boshqa filialdan ko'chirilgan", "count": stats['moved_to_branch']},
        ]

        # 4. Pastki chap tomondagi "Lidlar tahlili (Kun)" - Chiziqli grafik
        daily_leads = (
            Lead.objects.filter(base_filter)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                total=Count('id'),
                lost=Count('id', filter=Q(status__in=['LEFT_BEFORE_TRIAL', 'TRIAL_MISSED'])),
                sales=Count('id', filter=Q(status='PAID'))
            )
            .order_by('date')
        )

        linear_chart = {
            "labels": [item['date'].strftime('%d.%m.%Y') for item in daily_leads],
            "total_leads": [item['total'] for item in daily_leads],
            "lost_leads": [item['lost'] for item in daily_leads],
            "sales_count": [item['sales'] for item in daily_leads]
        }

        # 5. Pastki o'ng tomondagi "Kurslar kesimida buyurtmalar taqsimoti" - Diagramma
        # 🌟 TO'G'RILANDI: course__name -> section__name ga almashtirildi
        course_distribution = (
            Lead.objects.filter(base_filter)
            .values('section__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        course_chart = {
            "labels": [c['section__name'] or "Noma'lum" for c in course_distribution],
            "values": [c['count'] for c in course_distribution]
        }

        # 6. Yakuniy jamlangan javobni qaytarish
        return Response({
            "table_data": table_data,
            "funnel_chart": funnel_chart_data,
            "linear_chart": linear_chart,
            "course_chart": course_chart
        }, status=status.HTTP_200_OK)


class CRMLeadsListView(TenantViewSetMixin, generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Lidlar hisoboti'
    """
    Tanlangan bosqichdagi (pipeline_name bo'yicha) lidlarni filter va saralangan holda qaytaradi.
    """

    def get_serializer_class(self):
        from crm.serializers import LeadSerializer
        return LeadSerializer

    def get_queryset(self):
        org_id = self.get_organization_id()
        if not org_id:
            from crm.models import Lead
            return Lead.objects.none()

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        source_id = self.request.query_params.get('source')
        pipeline_name = self.request.query_params.get('pipeline_name')

        from crm.models import Lead
        from django.db.models import Q
        leads_qs = Lead.objects.filter(organization_id=org_id, is_archived=False)
        branch_id = self.get_branch_id()
        if branch_id:
            leads_qs = leads_qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))

        if pipeline_name:
            leads_qs = leads_qs.filter(pipeline__name=pipeline_name)
        if start_date:
            leads_qs = leads_qs.filter(created_at__date__gte=start_date)
        if end_date:
            leads_qs = leads_qs.filter(created_at__date__lte=end_date)
        if source_id:
            leads_qs = leads_qs.filter(source_id=source_id)

        return leads_qs.order_by('-created_at')


class ConversionReportsOverviewView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Konversiya hisoboti'

    def get(self, request):
        return Response({"detail": "Stub endpoint"}, status=status.HTTP_200_OK)


class ConversionReportsLostReasonsView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Konversiya hisoboti'

    def get(self, request):
        return Response({"detail": "Stub endpoint"}, status=status.HTTP_200_OK)


class ConversionReportsPipelineTransitionsView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Konversiya hisoboti'

    def get(self, request):
        return Response({"detail": "Stub endpoint"}, status=status.HTTP_200_OK)


class LeadsReportPieChartView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Lidlar hisoboti'
    """
    Manbalar bo'yicha lidlar sonini qaytaradi (Pie chart).
    """

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        from crm.models import Lead
        leads_qs = Lead.objects.filter(organization_id=org_id)

        if start_date:
            leads_qs = leads_qs.filter(created_at__date__gte=start_date)
        if end_date:
            leads_qs = leads_qs.filter(created_at__date__lte=end_date)

        # Group by source
        from django.db.models import Count
        sources_data = leads_qs.values('source__name').annotate(count=Count('id'))

        result = []
        for item in sources_data:
            name = item['source__name'] or "Noma'lum"
            result.append({
                "name": name,
                "count": item['count']
            })
        return Response(result, status=status.HTTP_200_OK)


class LeadsReportBarChartView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Lidlar hisoboti'
    """
    Oylar bo'yicha lidlar oqimini qaytaradi (Bar chart).
    """

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        from crm.models import Lead
        leads_qs = Lead.objects.filter(organization_id=org_id)

        if start_date:
            leads_qs = leads_qs.filter(created_at__date__gte=start_date)
        if end_date:
            leads_qs = leads_qs.filter(created_at__date__lte=end_date)

        # Group by month in python to keep it database-agnostic
        monthly_counts = {}
        for lead in leads_qs:
            month_str = lead.created_at.strftime('%Y-%m')
            monthly_counts[month_str] = monthly_counts.get(month_str, 0) + 1

        result = []
        for month in sorted(monthly_counts.keys()):
            result.append({
                "month": month,
                "count": monthly_counts[month]
            })
        return Response(result, status=status.HTTP_200_OK)


class LeadsReportStatisticsView(TenantViewSetMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPagePermission]
    permission_page_name = 'Lidlar hisoboti'
    """
    Jami lidlar sonini qaytaruvchi API.
    """

    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        from crm.models import Lead
        leads_qs = Lead.objects.filter(organization_id=org_id)

        if start_date:
            leads_qs = leads_qs.filter(created_at__date__gte=start_date)
        if end_date:
            leads_qs = leads_qs.filter(created_at__date__lte=end_date)

        total_leads = leads_qs.count()
        return Response({
            "total_leads": total_leads,
            "total_count": total_leads
        }, status=status.HTTP_200_OK)


from finance.models import FinanceSetting, StaffSalaryPercent
from finance.serializers import FinanceSettingSerializer, StaffSalaryPercentSerializer
from organizations.mixins import TenantViewSetMixin  # Agar mixiningiz nomi boshqacha bo'lsa to'g'rilab oling
from rest_framework.permissions import IsAuthenticated


class FinanceSettingAPIView(APIView):
    """Moliya sozlamalarini bitta ob'ekt sifatida boshqarish endpointi"""
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Har bir tashkilot uchun bitta sozlama nusxasi mavjudligini ta'minlaydi
        setting, created = FinanceSetting.objects.get_or_create(
            organization=self.request.user.organization
        )
        return setting

    def get_response_data(self, setting):
        serializer = FinanceSettingSerializer(setting)
        
        # Build choices
        from accounts.models import User
        from academics.models import Student
        from finance.models import Cashbox
        
        roles_data = [{"id": key, "name": value} for key, value in User.ROLE_CHOICES]
        
        students_data = [
            {"id": s.id, "full_name": s.full_name} 
            for s in Student.objects.filter(organization=setting.organization)
        ]
        
        employees_data = [
            {"id": u.id, "full_name": f"{u.first_name} {u.last_name}".strip() or u.username, "role": u.role} 
            for u in User.objects.filter(organization=setting.organization)
        ]
        
        branch_id = get_active_branch_id(self.request)
        cashboxes_qs = Cashbox.objects.filter(organization=setting.organization, is_archived=False)
        if branch_id:
            cashboxes_qs = cashboxes_qs.filter(branch_id=branch_id)
            
        cashboxes_data = [
            {"id": c.id, "name": c.name} 
            for c in cashboxes_qs
        ]
        
        response_data = dict(serializer.data)
        response_data['choices'] = {
            'roles': roles_data,
            'students': students_data,
            'employees': employees_data,
            'cashboxes': cashboxes_data
        }
        return response_data

    def get(self, request):
        setting = self.get_object()
        return Response(self.get_response_data(setting), status=status.HTTP_200_OK)

    def put(self, request):
        setting = self.get_object()
        serializer = FinanceSettingSerializer(setting, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(self.get_response_data(setting), status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StaffSalaryPercentViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    """Dinamik oylik foiz stavkalarini qo'shish va o'chirish endpointi"""
    permission_classes = [IsAuthenticated]
    serializer_class = StaffSalaryPercentSerializer
    queryset = StaffSalaryPercent.objects.all()

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class CashboxListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = getattr(request.user, 'organization_id', None)
        branch_id = get_active_branch_id(request)
        
        queryset = Cashbox.objects.filter(organization_id=org_id, is_archived=False)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
            
        serializer = CashboxSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CashboxSerializer(data=request.data)
        if serializer.is_valid():
            branch_id = get_active_branch_id(request)
            serializer.save(
                organization=request.user.organization,
                branch_id=branch_id
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdvancedPaymentReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """To'lovlar uchun o'qituvchi, sana va kassa bo'yicha o'ta tez ishlaydigan filter"""
        org_id = getattr(request.user, 'organization_id', None)
        queryset = Payment.objects.filter(organization_id=org_id).select_related('student', 'cashbox', 'employee')

        # Filter: Branch bo'yicha (filiallararo ma'lumotlar aralashib ketmasligi uchun)
        branch_id = get_active_branch_id(request)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)

        # 1. Sana bo'yicha filter (Sana oralig'i)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])

        # 2. Kassa bo'yicha filter
        cashbox_id = request.query_params.get('cashbox_id')
        if cashbox_id:
            queryset = queryset.filter(cashbox_id=cashbox_id)

        # 3. O'QITUVCHI BO'YICHA FILTER (Eng muhimi va tez ishlaydigani)
        # O'quvchi o'qituvchining faol guruhlarida bormi yoki yo'qligini StudentGroup orqali bog'lab tekshiradi
        teacher_id = request.query_params.get('teacher_id')
        if teacher_id:
            queryset = queryset.filter(
                student__student_groups__group__teacher_id=teacher_id
            ).distinct()

        serializer = PaymentSerializer(queryset, many=True)
        return Response(serializer.data)


class TransactionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Kirim yoki Chiqim yaratish (Rasmdagi Saqlash tugmasi uchun)"""
        serializer = CashTransactionSerializer(data=request.data)
        if serializer.is_valid():
            # Tranzaksiyani xavfsiz (atomic) bajarish
            with transaction.atomic():
                # Avval kassa amaliyotini saqlaymiz
                instance = serializer.save(organization=request.user.organization)

                # TO'G'RILANDI: Modelda maydon 'transaction_type' va qiymatlar kichik harfda ('kirim'/'chiqim')
                if instance.student:
                    student = instance.student
                    amount = instance.amount

                    if instance.transaction_type == 'kirim':
                        # Kassaga kirim bo'ldi -> O'quvchi balansi ko'payadi
                        student.balance += amount
                        student.save(update_fields=['balance'])

                    elif instance.transaction_type == 'chiqim':
                        # Kassadan o'quvchiga chiqim bo'ldi (Refund) -> O'quvchi balansi kamayadi
                        student.balance -= amount
                        student.save(update_fields=['balance'])

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CashTransferAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Kassadan kassaga pul o'tkazish API"""
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

        # Naming normalizations
        if 'from_cashbox' not in data:
            if 'cashbox' in data:
                data['from_cashbox'] = data['cashbox']
            elif 'from_cashbox_id' in data:
                data['from_cashbox'] = data['from_cashbox_id']

        if 'to_cashbox' not in data and 'to_cashbox_id' in data:
            data['to_cashbox'] = data['to_cashbox_id']

        if 'comment' not in data:
            if 'description' in data:
                data['comment'] = data['description']
            elif 'izoh' in data:
                data['comment'] = data['izoh']

        serializer = CashTransferSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            from_cashbox = serializer.validated_data['from_cashbox']
            to_cashbox = serializer.validated_data['to_cashbox']
            amount = serializer.validated_data['amount']
            comment = serializer.validated_data.get('comment') or "Kassalararo o'tkazma"

            # 🛠️ TRANZAKSIYANI XAVFSIZ (ATOMIC) BAJARISH
            with db_transaction.atomic():

                # 🌟 KASSALAR BALANSINI TEKSHIRISH VA YANGILASH
                from_box = Cashbox.objects.select_for_update().get(id=from_cashbox.id)
                to_box = Cashbox.objects.select_for_update().get(id=to_cashbox.id)

                if from_box.balance < amount:
                    return Response(
                        {"detail": f"'{from_box.name}' kassasida yetarli mablag' yo'q (Balans: {from_box.balance})!"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # TO'G'RILANDI: Balanslarni bu yerda QO'LDA o'zgartirmaymiz!
                # Pastdagi ikkita Transaction.objects.create() chaqirilganda
                # `recompute_cashbox_balance` signali (models.py) har ikkala
                # kassaning balansini ham AVTOMATIK va TO'G'RI qayta hisoblaydi.
                # Avval bu yerda QO'LDA ham, Transaction orqali ham o'zgartirilgani
                # uchun balanslar noto'g'ri chiqishi mumkin edi.

                # 🌟 1. CashTransaction (chiqim)
                CashTransaction.objects.create(
                    organization=request.user.organization,
                    cashbox=from_box,
                    amount=amount,
                    transaction_type='chiqim',
                    payment_method='naqd',
                    date=timezone.now().date(),
                    employee=request.user,
                    category_name="Kassalararo o'tkazma",
                    comment=f"Kassalararo o'tkazma chiqim: {from_box.name} -> {to_box.name}. Izoh: {comment}"
                )

                # 🌟 2. CashTransaction (kirim)
                CashTransaction.objects.create(
                    organization=request.user.organization,
                    cashbox=to_box,
                    amount=amount,
                    transaction_type='kirim',
                    payment_method='naqd',
                    date=timezone.now().date(),
                    employee=request.user,
                    category_name="Kassalararo o'tkazma",
                    comment=f"Kassalararo o'tkazma kirim: {from_box.name} -> {to_box.name}. Izoh: {comment}"
                )

            # Muvaffaqiyatli javob qaytarish
            return Response({
                "detail": f"{amount} UZS kassalararo muvaffaqiyatli o'tkazildi!",
                "from_cashbox": from_box.id,
                "to_cashbox": to_box.id,
                "amount": float(amount)
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TransactionReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Moliya jadvali va filterlar (Sana, Kassa, O'qituvchi bo'yicha)"""
        queryset = CashTransaction.objects.filter(
            organization=request.user.organization
        ).select_related('student', 'cashbox', 'employee').order_by('-date', '-id')

        # Filter: Branch bo'yicha (filiallararo ma'lumotlar aralashib ketmasligi uchun)
        branch_id = get_active_branch_id(request)
        print("LOG: TransactionReportAPIView - branch_id from request:", branch_id, "query_params:", request.query_params, "headers:", {k: v for k, v in request.headers.items() if 'branch' in k.lower() or 'authorization' in k.lower()})
        if branch_id:
            queryset = queryset.filter(cashbox__branch_id=branch_id)

        # Filter: Kassa bo'yicha
        cashbox_id = request.query_params.get('cashbox_id')
        if cashbox_id:
            queryset = queryset.filter(cashbox_id=cashbox_id)

        # Filter: To'lov turi (naqd, plastik, terminal) - kichik harfda tekshiriladi
        payment_method = request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method.lower())

        # Filter: Sana oralig'i
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])

        # Filter: O'qituvchi bo'yicha
        teacher_id = request.query_params.get('teacher_id')
        if teacher_id:
            queryset = queryset.filter(
                student__student_groups__group__teacher_id=teacher_id
            ).distinct()

        # Serializer'ga context orqali request'ni uzatamiz (bu student_name to'g'ri ishlashi uchun kerak bo'lishi mumkin)
        serializer = CashTransactionSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


# finance/models.py faylining oxiriga qo'shing:

# finance/views.py ichida:
from rest_framework import viewsets
from .models import FinanceAction, Transaction, Cashbox
from django.db import transaction


class FinanceActionViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    queryset = FinanceAction.objects.all()

    serializer_class = FinanceActionSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            branch_id = self.get_branch_id()
            cashbox_id = self.request.data.get('cashbox')
            
            validated_data = serializer.validated_data.copy()
            validated_data.pop('cashbox', None)
            
            instance = FinanceAction(**validated_data)
            instance.organization = self.request.user.organization
            instance.branch_id = branch_id
            if cashbox_id:
                instance._cashbox_id = cashbox_id
            instance.save()
            serializer.instance = instance

    def perform_update(self, serializer):
        with transaction.atomic():
            cashbox_id = self.request.data.get('cashbox')
            instance = serializer.instance
            if cashbox_id:
                instance._cashbox_id = cashbox_id
            serializer.save()


from .filters import FinancialReportFilter


class FinancialAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get('type', 'kirim').lower()
        branch_id = get_active_branch_id(request)

        tx_filters = Q(cashbox__organization_id=request.user.organization_id)
        if branch_id:
            tx_filters &= Q(cashbox__branch_id=branch_id)
        tx_queryset = Transaction.objects.filter(tx_filters)

        filtered_tx = FinancialReportFilter(request.GET, queryset=tx_queryset).qs

        labels_data = {}
        total_sum = 0
        table_rows = []

        if report_type == 'kirim':
            queryset = filtered_tx.filter(type='INCOME')
            total_sum = queryset.aggregate(total=Sum('amount'))['total'] or 0

            for tx in queryset:
                desc = tx.description or "Boshqa kirimlar"
                labels_data[desc] = labels_data.get(desc, 0) + float(tx.amount)
                table_rows.append({"nomi": desc, "summa": float(tx.amount), "sana": tx.created_at})

        elif report_type == 'chiqim':
            queryset = filtered_tx.filter(type='EXPENSE')
            total_sum = queryset.aggregate(total=Sum('amount'))['total'] or 0

            for tx in queryset:
                desc = tx.description or "Boshqa chiqimlar"
                labels_data[desc] = labels_data.get(desc, 0) + float(tx.amount)
                table_rows.append({"nomi": desc, "summa": float(tx.amount), "sana": tx.created_at})

        elif report_type == 'bonus':
            # Har bir tashkilot o'z bonuslarini ko'rishi uchun agar FinanceAction ichida ham organization bo'lsa filter qo'shish tavsiya etiladi
            actions = FinanceAction.objects.filter(action_type='BONUS')
            if hasattr(FinanceAction, 'organization_id'):
                actions = actions.filter(organization_id=request.user.organization_id)
            if branch_id:
                actions = actions.filter(branch_id=branch_id)

            if request.GET.get('start_date'):
                actions = actions.filter(created_at__gte=request.GET.get('start_date'))
            if request.GET.get('end_date'):
                actions = actions.filter(created_at__lte=request.GET.get('end_date'))

            total_sum = actions.aggregate(total=Sum('amount'))['total'] or 0

            for act in actions:
                name = f"{act.get_target_type_display()}: {act.employee or act.student}"
                labels_data[name] = labels_data.get(name, 0) + float(act.amount)
                table_rows.append(
                    {"nomi": f"{name} ({act.reason or ''})", "summa": float(act.amount), "sana": act.created_at})

        elif report_type == 'jarima':
            actions = FinanceAction.objects.filter(action_type='PENALTY')
            if hasattr(FinanceAction, 'organization_id'):
                actions = actions.filter(organization_id=request.user.organization_id)

            if request.GET.get('start_date'):
                actions = actions.filter(created_at__gte=request.GET.get('start_date'))
            if request.GET.get('end_date'):
                actions = actions.filter(created_at__lte=request.GET.get('end_date'))

            total_sum = actions.aggregate(total=Sum('amount'))['total'] or 0

            for act in actions:
                name = f"{act.get_target_type_display()}: {act.employee}"
                labels_data[name] = labels_data.get(name, 0) + float(act.amount)
                table_rows.append(
                    {"nomi": f"{name} - {act.reason or ''}", "summa": float(act.amount), "sana": act.created_at})

        return Response({
            "total_amount": total_sum,
            "chart_data": {
                "labels": list(labels_data.keys()),
                "values": list(labels_data.values())
            },
            "table_data": table_rows
        })


class FinancialReportsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        start_date_str = request.query_params.get('from_date')
        end_date_str = request.query_params.get('to_date')
        cashbox_id = request.query_params.get('kassa') or request.query_params.get('cashbox')

        branch_id = get_active_branch_id(request)
        if hasattr(Transaction, 'organization'):
            tx_filters = Q(organization_id=request.user.organization_id)
        else:
            tx_filters = Q(cashbox__organization_id=request.user.organization_id)
        if branch_id:
            tx_filters &= Q(branch_id=branch_id)
        queryset = Transaction.objects.filter(tx_filters)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                pass

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                queryset = queryset.filter(created_at__lte=datetime.combine(end_date, time.max))
            except ValueError:
                pass

        # Abdulmajid xatolik yuborganda filtrdan xavfsiz o'tish
        if cashbox_id:
            try:
                queryset = queryset.filter(cashbox_id=int(cashbox_id))
            except ValueError:
                pass

        total_income = queryset.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or 0
        total_expense = queryset.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or 0
        balance = total_income - total_expense

        income_breakdown = {}
        for tx in queryset.filter(type='INCOME'):
            desc = tx.description or "Boshqa kirimlar"
            income_breakdown[desc] = income_breakdown.get(desc, 0) + float(tx.amount)

        expense_breakdown = {}
        for tx in queryset.filter(type='EXPENSE'):
            desc = tx.description or "Boshqa chiqimlar"
            expense_breakdown[desc] = expense_breakdown.get(desc, 0) + float(tx.amount)

        daily_data = {}
        for tx in queryset.order_by('created_at'):
            date_key = tx.created_at.strftime('%d.%m')
            if date_key not in daily_data:
                daily_data[date_key] = {'kirim': 0, 'chiqim': 0}

            if tx.type == 'INCOME':
                daily_data[date_key]['kirim'] += float(tx.amount)
            else:
                daily_data[date_key]['chiqim'] += float(tx.amount)

        return Response({
            "cards": {
                "total_income": float(total_income),
                "total_expense": float(total_expense),
                "balance": float(balance)
            },
            "linear_chart": {
                "labels": list(daily_data.keys()),
                "kirim_line": [v['kirim'] for v in daily_data.values()],
                "chiqim_line": [v['chiqim'] for v in daily_data.values()]
            },
            "pie_chart": {
                "kirim": {
                    "labels": list(income_breakdown.keys()),
                    "values": list(income_breakdown.values())
                },
                "chiqim": {
                    "labels": list(expense_breakdown.keys()),
                    "values": list(expense_breakdown.values())
                }
            }
        })


from .models import Transaction
from datetime import datetime, time


class CashFlowReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        cashbox_id = request.query_params.get('kassa') or request.query_params.get('cashbox')

        branch_id = get_active_branch_id(request)
        if hasattr(Transaction, 'organization'):
            tx_filters = Q(organization_id=request.user.organization_id)
        else:
            tx_filters = Q(cashbox__organization_id=request.user.organization_id)
        if branch_id:
            tx_filters &= Q(branch_id=branch_id)
        queryset = Transaction.objects.filter(tx_filters)

        # 2. Sana filtri (Xavfsiz parsing bilan)
        if from_date:
            try:
                queryset = queryset.filter(created_at__gte=datetime.strptime(from_date, '%Y-%m-%d'))
            except ValueError:
                pass
        if to_date:
            try:
                queryset = queryset.filter(
                    created_at__lte=datetime.combine(datetime.strptime(to_date, '%Y-%m-%d'), time.max)
                )
            except ValueError:
                pass

        # 3. 🌟 MANA SHU JOYI GLOBAL XATOLIKNI OLDINI OLADI:
        # Abdulmajid xato matn yuborib qolsa ham ushlab qolib, dasturni qulatmaydi
        if cashbox_id:
            try:
                queryset = queryset.filter(cashbox_id=int(cashbox_id))
            except ValueError:
                pass

        # Kirim va Chiqimlarni tavsifi (description) bo'yicha guruhlaymiz
        incomes = queryset.filter(type='INCOME').values('description').annotate(total=Sum('amount'))
        expenses = queryset.filter(type='EXPENSE').values('description').annotate(total=Sum('amount'))

        total_income = sum(item['total'] for item in incomes) or 0
        total_expense = sum(item['total'] for item in expenses) or 0

        return Response({
            "kirimlar": [
                {"kategoriya": item['description'] or "Boshqa kirim", "summa": float(item['total'])}
                for item in incomes
            ],
            "chiqimlar": [
                {"kategoriya": item['description'] or "Boshqa xarajat", "summa": float(item['total'])}
                for item in expenses
            ],
            "jami_kirim": float(total_income),
            "jami_chiqim": float(total_expense),
            "sof_pul_oqimi": float(total_income - total_expense)
        }, status=status.HTTP_200_OK)


class PnLReportView(APIView):
    """
    Foyda va Zarar (PnL) hisoboti endpointi.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        branch_id = get_active_branch_id(request)
        if hasattr(Transaction, 'organization'):
            tx_filters = Q(organization_id=request.user.organization_id)
        else:
            tx_filters = Q(cashbox__organization_id=request.user.organization_id)
        if branch_id:
            tx_filters &= Q(branch_id=branch_id)
        queryset = Transaction.objects.filter(tx_filters)

        # Sanalar bo'yicha xavfsiz filterlash
        if from_date:
            try:
                queryset = queryset.filter(created_at__gte=datetime.strptime(from_date, '%Y-%m-%d'))
            except ValueError:
                pass
        if to_date:
            try:
                queryset = queryset.filter(
                    created_at__lte=datetime.combine(datetime.strptime(to_date, '%Y-%m-%d'), time.max))
            except ValueError:
                pass

        # Kirim va chiqimlarni jamlash
        total_income = queryset.filter(type='INCOME').aggregate(total=Sum('amount'))['total'] or 0
        total_expense = queryset.filter(type='EXPENSE').aggregate(total=Sum('amount'))['total'] or 0
        net_profit = total_income - total_expense

        return Response({
            "total_income": float(total_income),
            "total_expense": float(total_expense),
            "net_profit": float(net_profit)
        }, status=status.HTTP_200_OK)


class TransactionCategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    queryset = TransactionCategory.objects.all()
    serializer_class = TransactionCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type']


class EmployeeFinanceBalanceReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)

        # Foydalanuvchilar (Xodimlar) ro'yxatini olamiz
        from django.contrib.auth import get_user_model
        User = get_user_model()

        employees_qs = User.objects.filter(organization_id=org_id, is_staff=True)
        if branch_id:
            employees_qs = employees_qs.filter(branch_id=branch_id)

        rows = []
        total_salary = 0
        total_bonus = 0
        total_advance = 0
        total_penalty = 0

        for emp in employees_qs:
            # Modellaringiz asosida xodimga tegishli summalar yig'indisini hisoblaymiz
            salary_amount = Salary.objects.filter(employee=emp, status='paid').aggregate(total=Sum('amount'))[
                                'total'] or 0
            bonus_amount = Bonus.objects.filter(employee=emp).aggregate(total=Sum('amount'))['total'] or 0
            penalty_amount = Fine.objects.filter(employee=emp).aggregate(total=Sum('amount'))['total'] or 0

            # Chiqim tranzaksiyalaridan xodim oylik to'lovlarini (Avans) hisoblaymiz
            advance_amount = \
                Transaction.objects.filter(employee=emp, type='EXPENSE', category='SALARY').aggregate(
                    total=Sum('amount'))[
                    'total'] or 0

            final_salary = float(salary_amount)
            b_val = float(bonus_amount)
            a_val = float(advance_amount)
            p_val = float(penalty_amount)

            total_salary += final_salary
            total_bonus += b_val
            total_advance += a_val
            total_penalty += p_val

            full_name = f"{getattr(emp, 'first_name', '')} {getattr(emp, 'last_name', '')}".strip() or emp.username

            rows.append({
                "id": emp.id,
                "full_name": full_name,
                "phone": getattr(emp, 'phone', '-'),
                "salary": f"{final_salary:,.0f} UZS".replace(",", " "),
                "bonus": f"{b_val:,.0f} UZS".replace(",", " "),
                "advance": f"{a_val:,.0f} UZS".replace(",", " "),
                "penalty": f"{p_val:,.0f} UZS".replace(",", " ")
            })

        return Response({
            "table_data": rows,
            "totals": {
                "salary": total_salary,
                "bonus": total_bonus,
                "advance": total_advance,
                "penalty": total_penalty
            }
        }, status=status.HTTP_200_OK)


# =====================================================================
# 3-RASM: TUSHUM REJASI (Revenue Plan)
# =====================================================================
class RevenuePlanReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)
        date_str = request.query_params.get('date', 'Bugun')

        # Qarzdor o'quvchilar soni va umumiy summa
        debtors = Student.objects.filter(organization_id=org_id, balance__lt=0)
        if branch_id:
            debtors = debtors.filter(branch_id=branch_id)

        debtors_count = debtors.count()
        debtors_sum = abs(float(debtors.aggregate(total=Sum('balance'))['total'] or 0))

        # Shu oyda to'langan umumiy summalar (Transaction modeli orqali)
        tx_filters = Q(cashbox__organization_id=org_id, type='INCOME')
        if branch_id:
            tx_filters &= Q(cashbox__branch_id=branch_id)

        paid_sum = float(Transaction.objects.filter(tx_filters).aggregate(total=Sum('amount'))['total'] or 0)

        data = [
            {"target": f"{date_str} holatiga", "students_count": debtors_count,
             "expected_amount": debtors_sum + paid_sum},
            {"target": "Eski oydan qarzdor bo'lib o'tgan o'quvchilar summasi", "students_count": debtors_count,
             "expected_amount": debtors_sum},
            {"target": "Eski oydan o'quvchilar to'lab o'tgan summa", "students_count": 0, "expected_amount": 0},
            {"target": "Shu oyda to'langan summa", "students_count": 0, "expected_amount": paid_sum},
            {"target": "Qolgan kutilayotgan tushum", "students_count": debtors_count, "expected_amount": debtors_sum},
        ]
        return Response(data, status=status.HTTP_200_OK)


# =====================================================================
# 4-RASM: OʻQUVCHINING UMUMIY TOʻLANMAGAN TOʻLOVLARI (Debtors)
# =====================================================================
class UnpaidLessonsReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)

        # Balansi minusda bo'lgan o'quvchilarni olamiz
        students_qs = Student.objects.filter(organization_id=org_id, balance__lt=0)
        if branch_id:
            students_qs = students_qs.filter(branch_id=branch_id)

        rows = []
        for index, student in enumerate(students_qs, start=1):
            balance_val = abs(float(student.balance))

            # Guruhlarni chiqarish (agar m2m bog'liqlik bo'lsa)
            groups_str = "-"
            if hasattr(student, 'groups'):
                groups_str = ", ".join([g.name for g in student.groups.all()])

            # DIQQAT: bitta dars narxi hozircha 60 000 so'm deb QAT'IY (hardcoded) olingan.
            # Bu haqiqiy kurs narxi emas - shuning uchun "unpaid_lessons_count" noaniq bo'lishi mumkin.
            # To'g'ri yechim uchun: talabaning faol guruhi -> Course.price va dars soni orqali
            # haqiqiy bitta dars narxini hisoblash kerak (bu o'zgarish alohida muhokama talab qiladi).
            rows.append({
                "id": index,
                "name": f"{student.first_name} {student.last_name or ''}".strip(),
                "groups": groups_str,
                "unpaid_lessons_count": int(balance_val / 60000) or 1,
                "total_unpaid_amount": balance_val
            })

        return Response({
            "total_count": len(rows),
            "table_data": rows
        }, status=status.HTTP_200_OK)


# =====================================================================
# 5-RASM: BEKOR QILINGAN TOʻLOVLAR HISOBOTI (Cancelled Transactions)
# =====================================================================
class CancelledPaymentsReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)

        # Yangi Transaction modelidan 'EXPENSE' yoki bekor qilingan deb belgilanganlarini qidiramiz
        # Agar modelingizda maxsus status bo'lmasa, chiqim description'da 'bekor' so'zi borligini olamiz
        tx_qs = Transaction.objects.filter(
            cashbox__organization_id=org_id,
            description__icontains="bekor"
        )
        if branch_id:
            tx_qs = tx_qs.filter(cashbox__branch_id=branch_id)

        rows = []
        for index, tx in enumerate(tx_qs, start=1):
            st_name = "Noma'lum"
            if tx.student:
                st_name = f"{tx.student.first_name} {tx.student.last_name or ''}".strip()

            rows.append({
                "id": index,
                "name": st_name,
                "unpaid_lessons": 0,
                "total_unpaid": float(tx.amount),
                "teacher": "-",
                "group": "-",
                "description": tx.description or "To'lov bekor qilingan"
            })

        return Response({
            "total_count": len(rows),
            "table_data": rows
        }, status=status.HTTP_200_OK)


# =====================================================================
# 6-RASM: UMUMIY CHEGIRMALAR VA VOUCHERLAR HISOBOTI
# =====================================================================
class DiscountsAndBonusesReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from finance.models import Transaction
        from django.db.models import Sum, Q

        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)
        print("DEBUG DiscountsAndBonusesReportView: org_id:", org_id, "branch_id:", branch_id)

        # 1. Tashkilot va filial bo'yicha bazaviy filtr
        if hasattr(Transaction, 'organization'):
            base_txs = Transaction.objects.filter(organization_id=org_id)
        else:
            base_txs = Transaction.objects.filter(cashbox__organization_id=org_id)

        print("DEBUG DiscountsAndBonusesReportView: Total transactions for org before branch filter:", base_txs.count())
        for tx in base_txs[:10]:
            print(f"DEBUG Tx ID: {tx.id}, category: {tx.category}, student: {tx.student_id}, cashbox_id: {tx.cashbox_id}, cashbox_branch: {tx.cashbox.branch_id if tx.cashbox else None}, tx_branch: {tx.branch_id}, desc: {tx.description}")

        if branch_id:
            if hasattr(Transaction, 'branch'):
                base_txs = base_txs.filter(branch_id=branch_id)
            else:
                base_txs = base_txs.filter(cashbox__branch_id=branch_id)
            print("DEBUG DiscountsAndBonusesReportView: After branch filter count:", base_txs.count())

        # 1.1 Sana bo'yicha filter (start_date/end_date yoki from_date/to_date)
        from datetime import datetime
        start_date = request.query_params.get('start_date') or request.query_params.get('from_date')
        end_date = request.query_params.get('end_date') or request.query_params.get('to_date')
        if start_date:
            try:
                base_txs = base_txs.filter(created_at__date__gte=datetime.strptime(start_date.split('T')[0], '%Y-%m-%d').date())
            except (ValueError, TypeError):
                pass
        if end_date:
            try:
                base_txs = base_txs.filter(created_at__date__lte=datetime.strptime(end_date.split('T')[0], '%Y-%m-%d').date())
            except (ValueError, TypeError):
                pass

        # 1.2 O'quvchi ismi bo'yicha filter (search, student, student_name, name)
        student_search = request.query_params.get('search') or request.query_params.get('student') or request.query_params.get('student_name') or request.query_params.get('name')
        if student_search:
            base_txs = base_txs.filter(
                Q(student__first_name__icontains=student_search) |
                Q(student__last_name__icontains=student_search) |
                Q(description__icontains=student_search)
            )

        # 1.3 Guruh bo'yicha filter
        group_id = request.query_params.get('group') or request.query_params.get('group_id')
        if group_id and group_id != 'Barchasi':
            base_txs = base_txs.filter(student__student_groups__group_id=group_id)

        # 1.4 Kurs bo'yicha filter
        course_id = request.query_params.get('course') or request.query_params.get('course_id')
        if course_id and course_id != 'Barchasi':
            base_txs = base_txs.filter(student__student_groups__group__course_id=course_id)

        # 2. 🌟 FILTR KENGAYTIRILDI: Category 'DIRECT' bo'lsa ham izohida chegirma/bonus borlarni qidiradi
        discount_filter = (
                Q(category='VOUCHER') |
                Q(description__icontains='chegirma') |
                Q(description__icontains='voucher') |
                Q(source_payment__comment__icontains='chegirma') |
                Q(source_payment__comment__icontains='voucher')
        )

        bonus_filter = (
                Q(category='BONUS') |
                Q(description__icontains='bonus') |
                Q(source_payment__comment__icontains='bonus')
        )

        # Munosabatlarni oldindan yuklaymiz (prefetch_related)
        discount_txs = base_txs.filter(discount_filter).select_related('student', 'source_payment').prefetch_related(
            'student__student_groups__group__course'
        )
        bonus_txs = base_txs.filter(bonus_filter).select_related('student', 'source_payment').prefetch_related(
            'student__student_groups__group__course'
        )

        print("DEBUG DiscountsAndBonusesReportView: discount_txs count:", discount_txs.count(), "bonus_txs count:", bonus_txs.count())

        rows = []
        index = 1

        # Universal yordamchi funksiya: O'quvchining Kurs va Guruh nomlarini aniqlash
        def get_student_details(student):
            if not student:
                return "-", "-"

            student_groups = []
            # 'group_students' yoki 'student_groups' munosabatini tekshirish
            if hasattr(student, 'group_students') and student.group_students.exists():
                student_groups = student.group_students.all()
            elif hasattr(student, 'student_groups') and student.student_groups.exists():
                student_groups = student.student_groups.all()

            if student_groups:
                group_names = []
                course_names = []
                for sg in student_groups:
                    if sg.group:
                        g_name = getattr(sg.group, 'name', None) or str(sg.group)
                        group_names.append(g_name)
                        if getattr(sg.group, 'course', None):
                            c_name = getattr(sg.group.course, 'name', "-")
                            course_names.append(c_name)

                final_groups = ", ".join(list(set(group_names))) if group_names else "-"
                final_courses = ", ".join(list(set(course_names))) if course_names else "-"
                return final_courses, final_groups

            return "-", "-"

        # 3. Chegirmalarni jadvalga qo'shish
        for tx in discount_txs:
            st_name = "Umumiy Chegirma"
            course_name, group_name = "-", "-"

            if tx.student:
                st_name = f"{tx.student.first_name} {tx.student.last_name or ''}".strip()
                course_name, group_name = get_student_details(tx.student)

            tx_branch_id = tx.branch_id or (tx.cashbox.branch_id if tx.cashbox else None)

            rows.append({
                "id": index,
                "name": st_name,
                "student_name": st_name,
                "student": st_name,
                "course": course_name,
                "group": group_name,
                "total_discount": float(tx.amount),
                "discount": float(tx.amount),
                "bonus": 0.0,
                "branch": tx_branch_id,
                "branch_id": tx_branch_id,
            })
            index += 1

        # 4. Bonuslarni jadvalga qo'shish
        for tx in bonus_txs:
            st_name = "Umumiy Bonus"
            course_name, group_name = "-", "-"

            if tx.student:
                st_name = f"{tx.student.first_name} {tx.student.last_name or ''}".strip()
                course_name, group_name = get_student_details(tx.student)

            tx_branch_id = tx.branch_id or (tx.cashbox.branch_id if tx.cashbox else None)

            rows.append({
                "id": index,
                "name": st_name,
                "student_name": st_name,
                "student": st_name,
                "course": course_name,
                "group": group_name,
                "total_discount": 0.0,
                "discount": 0.0,
                "bonus": float(tx.amount),
                "branch": tx_branch_id,
                "branch_id": tx_branch_id,
            })
            index += 1

        # Jami summalarni hisoblash
        total_discounts = sum(r['total_discount'] for r in rows)
        total_bonuses = sum(r['bonus'] for r in rows)

        return Response({
            "total_bonuses": float(total_bonuses),
            "total_discounts": float(total_discounts),
            "summary": {
                "total_bonuses": float(total_bonuses),
                "total_discounts": float(total_discounts)
            },
            "total_count": len(rows),
            "table_data": rows
        }, status=status.HTTP_200_OK)

class TeacherEfficiencyReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        from django.utils.dateparse import parse_date
        
        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)
        from_date_str = request.query_params.get('from_date')
        to_date_str = request.query_params.get('to_date')

        from_date = parse_date(from_date_str) if from_date_str else None
        to_date = parse_date(to_date_str) if to_date_str else timezone.now().date()

        from academics.models import StudentGroup, StudentGroupLeave
        teachers = User.objects.filter(organization_id=org_id, role='teacher')
        if branch_id:
            teachers = teachers.filter(branch_id=branch_id)

        report = []
        for index, teacher in enumerate(teachers, 1):
            group_ids = list(teacher.teaching_groups.values_list('id', flat=True))

            # StudentGroup joins
            sg_qs = StudentGroup.objects.filter(group_id__in=group_ids)
            # StudentGroupLeave leaves
            sl_qs = StudentGroupLeave.objects.filter(group_id__in=group_ids)

            # Start Status (before from_date)
            if from_date:
                start_active = sg_qs.filter(joined_at__date__lt=from_date).count()
                start_left = sl_qs.filter(leave_date__lt=from_date).count()
            else:
                start_active = 0
                start_left = 0

            # Changes (between from_date and to_date)
            change_sg = sg_qs
            change_sl = sl_qs
            if from_date:
                change_sg = change_sg.filter(joined_at__date__gte=from_date)
                change_sl = change_sl.filter(leave_date__gte=from_date)
            if to_date:
                change_sg = change_sg.filter(joined_at__date__lte=to_date)
                change_sl = change_sl.filter(leave_date__lte=to_date)

            change_active = change_sg.count()
            change_left = change_sl.count()

            # End Status (before to_date)
            end_sg = sg_qs
            end_sl = sl_qs
            if to_date:
                end_sg = end_sg.filter(joined_at__date__lte=to_date)
                end_sl = end_sl.filter(leave_date__lte=to_date)

            end_active = end_sg.count()
            end_left = end_sl.count()

            name = f"{teacher.first_name} {teacher.last_name or ''}".strip() or teacher.username

            report.append({
                "id": index,
                "teacher_name": name,
                "start_status": {
                    "active": start_active,
                    "left": start_left,
                    "finished": 0,
                    "frozen": 0
                },
                "changes": {
                    "active": change_active,
                    "left": change_left,
                    "finished": 0,
                    "frozen": 0
                },
                "end_status": {
                    "active": end_active,
                    "left": end_left,
                    "finished": 0,
                    "frozen": 0
                }
            })

        return Response(report)


class AdministratorEfficiencyReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        from django.utils.dateparse import parse_date
        
        # Sanalarni frontend'dan olish
        from_date_str = request.query_params.get('from_date')
        to_date_str = request.query_params.get('to_date')

        from_date = parse_date(from_date_str) if from_date_str else None
        to_date = parse_date(to_date_str) if to_date_str else timezone.now().date()

        from academics.models import Student, StudentGroupLeave
        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)
        admins = User.objects.filter(organization_id=org_id, is_staff=True)
        if branch_id:
            admins = admins.filter(branch_id=branch_id)

        report = []
        for index, admin in enumerate(admins, 1):
            students_qs = Student.objects.filter(organization_id=org_id, moderator=admin.id)
            leaves_qs = StudentGroupLeave.objects.filter(organization_id=org_id, student__moderator=admin.id)
            if branch_id:
                students_qs = students_qs.filter(branch_id=branch_id)
                leaves_qs = leaves_qs.filter(branch_id=branch_id)

            # Start Status
            if from_date:
                start_active = students_qs.filter(created_at__date__lt=from_date, student_groups__isnull=False).distinct().count()
                start_left = leaves_qs.filter(leave_date__lt=from_date).count()
            else:
                start_active = 0
                start_left = 0

            # Changes
            change_active_qs = students_qs.filter(student_groups__isnull=False)
            change_left_qs = leaves_qs
            if from_date:
                change_active_qs = change_active_qs.filter(created_at__date__gte=from_date)
                change_left_qs = change_left_qs.filter(leave_date__gte=from_date)
            if to_date:
                change_active_qs = change_active_qs.filter(created_at__date__lte=to_date)
                change_left_qs = change_left_qs.filter(leave_date__lte=to_date)

            change_active = change_active_qs.distinct().count()
            change_left = change_left_qs.count()

            # End Status
            end_active_qs = students_qs.filter(student_groups__isnull=False)
            end_left_qs = leaves_qs
            if to_date:
                end_active_qs = end_active_qs.filter(created_at__date__lte=to_date)
                end_left_qs = end_left_qs.filter(leave_date__lte=to_date)

            end_active = end_active_qs.distinct().count()
            end_left = end_left_qs.count()

            report.append({
                "id": index,
                "admin_name": f"{admin.first_name} {admin.last_name}".strip() or admin.username,
                "start_status": {
                    "active": start_active,
                    "left": start_left,
                    "finished": 0,
                    "frozen": 0
                },
                "changes": {
                    "active": change_active,
                    "left": change_left,
                    "finished": 0,
                    "frozen": 0
                },
                "end_status": {
                    "active": end_active,
                    "left": end_left,
                    "finished": 0,
                    "frozen": 0
                }
            })

        return Response(report)


from academics.models import Student


class StudentLeaversReasonsReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils.dateparse import parse_date
        
        # 🔥 To'g'ridan-to'g'ri ketishlar tarixi modelini import qilamiz
        from academics.models import StudentGroupLeave

        tab_type = request.query_params.get('tab', 'all')
        from_date_str = request.query_params.get('from_date')
        to_date_str = request.query_params.get('to_date')

        from_date = parse_date(from_date_str) if from_date_str else None
        to_date = parse_date(to_date_str) if to_date_str else None

        # 🌟 Filterlarni faqat joriy tashkilot va kiritilgan sanalar bo'yicha quramiz
        branch_id = get_active_branch_id(request)
        filters = Q(student__organization=request.user.organization)
        if branch_id:
            filters &= Q(branch_id=branch_id)

        if from_date:
            filters &= Q(created_at__date__gte=from_date)
        if to_date:
            filters &= Q(created_at__date__lte=to_date)

        # 🌟 Ketish sababi (LeaveReason) modelidagi 'reason' maydoni bo'yicha guruhlaymiz
        reasons_queryset = (
            StudentGroupLeave.objects.filter(filters)
            .values('leave_reason__reason')  # Sababning nomini toza matn ko'rinishida olamiz
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        chart_data = []
        for item in reasons_queryset:
            reason = item['leave_reason__reason'] or "Sababi ko'rsatilmagan"
            chart_data.append({
                "reason_name": reason,
                "count": item['count']
            })

        # Frontend qulab tushmasligi uchun sug'urta mockup:
        if not chart_data:
            chart_data = [{"reason_name": "Boshqa sabab", "count": 0}]

        total_leavers = sum(item['count'] for item in chart_data)

        return Response({
            "total_leavers": total_leavers,
            "chart_data": chart_data,
            "table_data": [
                {
                    "id": i,
                    "reason_name": item['reason_name'],
                    "student_count": item['count']
                } for i, item in enumerate(chart_data, 1)
            ]
        })


from django.utils.dateparse import parse_date


class RoomAnalyticsReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from academics.models import Room  # Modelingizga qarab tekshiring

        # TO'G'RILANDI: organization_id bo'yicha filter qo'shildi (avval umuman filter yo'q edi -
        # bu boshqa tashkilotlarning xonalari ham ko'rinishiga sabab bo'lardi)
        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)

        from_date_str = request.query_params.get('from_date')
        to_date_str = request.query_params.get('to_date')

        from_date = parse_date(from_date_str) if from_date_str else None
        to_date = parse_date(to_date_str) if to_date_str else None

        # Guruhlar ochilgan sanasi bo'yicha filter
        group_filter = Q()
        if from_date:
            group_filter &= Q(groups__created_at__gte=from_date)
        if to_date:
            group_filter &= Q(groups__created_at__lte=to_date)

        # Xonalar va ulardagi faol guruhlar sonini olish
        rooms_qs = Room.objects.filter(organization_id=org_id)
        if branch_id:
            rooms_qs = rooms_qs.filter(branch_id=branch_id)

        rooms = rooms_qs.annotate(
            active_groups=Count('groups', filter=group_filter & Q(groups__status='active'))
        )

        chart_data = []
        table_data = []
        for index, room in enumerate(rooms, 1):
            chart_data.append({
                "room_name": room.name,
                "count": room.active_groups
            })
            table_data.append({
                "id": index,
                "room_name": room.name,
                "group_count": room.active_groups
            })

        return Response({
            "chart_data": chart_data,
            "table_data": table_data
        })


class BranchMonitoringReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils.dateparse import parse_date
        from organizations.models import Branch
        from crm.models import Lead
        from academics.models import Student

        # TO'G'RILANDI: organization_id bo'yicha filter qo'shildi
        org_id = request.user.organization_id

        date_str = request.query_params.get('date')  # Kunlik filter uchun
        target_date = parse_date(date_str) if date_str else None

        branches = Branch.objects.filter(organization_id=org_id)
        table_data = []

        for index, branch in enumerate(branches, 1):
            # Base querysets for this branch using corrected related names
            leads_qs = Lead.objects.filter(organization_id=org_id, branch=branch, is_archived=False)
            students_qs = Student.objects.filter(organization_id=org_id, branch=branch)

            if target_date:
                leads_qs = leads_qs.filter(created_at__date=target_date)
                students_qs = students_qs.filter(created_at__date=target_date)

            orders = leads_qs.filter(status='open').count()
            first_lesson = leads_qs.filter(status='first_lesson').count()
            new_students = students_qs.count() # Since they are created on target_date, they are new!
            active_students = students_qs.count() # All students in database are active in this context
            group_students = students_qs.filter(student_groups__isnull=False).distinct().count()
            order_leavers = leads_qs.filter(status='lost').count()
            debtors = students_qs.filter(balance__lt=0).count()

            debt_percentage = 0
            if active_students > 0:
                debt_percentage = round((debtors / active_students) * 100, 1)

            table_data.append({
                "id": index,
                "branch_name": branch.name,
                "buyurtma": orders,
                "birinchi_dars": first_lesson,
                "yangi_oquvchi": new_students,
                "aktiv_oquvchilar": active_students,
                "guruh_oquvchilari": group_students,
                "buyurtmadan_ketganlar": order_leavers,
                "qarzdorlar": debtors,
                "qarzdorlar_foizi": f"{debt_percentage}%"
            })

        return Response({"table_data": table_data})


class UnsubmittedAttendanceReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils.dateparse import parse_date
        from academics.models import GroupLesson, Attendance

        org_id = request.user.organization_id
        branch_id = get_active_branch_id(request)

        from_date_str = request.query_params.get('from_date')
        to_date_str = request.query_params.get('to_date')

        from_date = parse_date(from_date_str) if from_date_str else None
        to_date = parse_date(to_date_str) if to_date_str else None

        # 1. Darslar (GroupLesson) bo'yicha filterlarni shakllantiramiz
        lesson_filter = Q(organization_id=org_id, is_canceled=False)
        if branch_id:
            lesson_filter &= Q(branch_id=branch_id)
        if from_date:
            lesson_filter &= Q(date__gte=from_date)
        if to_date:
            lesson_filter &= Q(date__lte=to_date)

        # 2. Barcha darslarni olamiz
        all_lessons = GroupLesson.objects.filter(lesson_filter).select_related(
            'group', 'group__teacher', 'group__course'
        ).order_by('date')

        # 3. Yo'qlama topshirilgan darslarni aniqlash
        # Agar Attendance jadvalida shu guruh va sana uchun yozuv bo'lsa, yo'qlama qilingan
        submitted_pairs = set(
            Attendance.objects.filter(
                organization_id=org_id
            ).values_list('group_id', 'date')
        )

        table_data = []
        total_lost_sum = 0
        seen_groups = set()
        index = 1

        for lesson in all_lessons:
            group = lesson.group
            if not group:
                continue

            # Yo'qlama topshirilganmi?
            if (group.id, lesson.date) in submitted_pairs:
                continue

            # Har bir guruh hisobotda faqat bir marta chiqishi uchun
            if group.id in seen_groups:
                continue
            seen_groups.add(group.id)

            group_price = getattr(group, 'price', None) or (
                group.course.price if group.course and hasattr(group.course, 'price') else 300000
            )
            total_lost_sum += float(group_price)

            teacher_name = "O'qituvchi biriktirilmagan"
            if group.teacher:
                teacher_name = f"{group.teacher.first_name} {group.teacher.last_name or ''}".strip() or group.teacher.username

            try:
                lesson_date = lesson.date.strftime("%d.%m.%Y")
            except AttributeError:
                lesson_date = str(lesson.date)

            table_data.append({
                "id": index,
                "group_name": group.name,
                "sana": lesson_date,
                "teacher_name": teacher_name,
                "amount": float(group_price)
            })
            index += 1

        return Response({
            "total_sum": total_lost_sum,
            "currency": "UZS",
            "table_data": table_data
        }, status=200)


from django.http import HttpResponse
import os

def temp_log_view(request):
    log_path = "/var/log/musojon1995.pythonanywhere.com.error.log"
    if not os.path.exists(log_path):
        return HttpResponse(f"Log path {log_path} not found. Current dirs: {os.listdir('/var') if os.path.exists('/var') else 'No var'}")
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()[-150:]
    return HttpResponse("<pre>" + "".join(lines) + "</pre>")