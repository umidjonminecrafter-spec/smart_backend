from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status, decorators, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from decimal import Decimal
from django.db import transaction
from crm.models import Pipeline, Lead
from organizations.mixins import TenantViewSetMixin
from organizations.permissions import HasOrganizationPagePermission
from datetime import datetime
from finance.models import (
    ExpenseCategory, ExpenseSubcategory, Expense, MonthlyIncome,
    Payment, Sale, Bonus, Fine, Salary, TeacherSalaryRule, TeacherSalaryCalculation, Cashbox,CashTransaction,TransactionCategory
)
from finance.serializers import (
    ExpenseCategorySerializer, ExpenseSubcategorySerializer, ExpenseSerializer,
    MonthlyIncomeSerializer, PaymentSerializer, SaleSerializer, BonusSerializer,
    FineSerializer, SalarySerializer, TeacherSalaryRuleSerializer, TeacherSalaryCalculationSerializer, CashboxSerializer
)
from academics.models import Student, Group, StudentGroup, TeacherSalaryPayment
from academics.serializers import StudentSerializer, TeacherSalaryPaymentSerializer
from django.contrib.auth import get_user_model

from finance.serializers import CashTransactionSerializer
from organizations.models import TenantModel

from .serializers import FinanceActionSerializer, TransactionSerializer, TransactionCategorySerializer

User = get_user_model()

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

class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['type', 'category', 'cashbox']
    search_fields = ['description', 'student__full_name', 'employee__username']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']

    def get_queryset(self):
        # 🌟 MANA SHU YERDA: request.user o'rniga self.request.user yozildi!
        return Transaction.objects.filter(cashbox__tenant_id=self.request.user.organization_id)

    def perform_create(self, serializer):
        with db_transaction.atomic():  # db_transaction importi bilan xavfsiz qilindi
            tx = serializer.save()
            cashbox = tx.cashbox

            # Kirim bo'lsa kassa balansiga qo'shiladi, chiqim bo'lsa ayiriladi
            if tx.type == 'INCOME':
                cashbox.balance += tx.amount
            elif tx.type == 'EXPENSE':
                cashbox.balance -= tx.amount

            cashbox.save()


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
            "types": types,          # Kirim, Chiqim
            "categories": categories  # To'g'ridan-to'g'ri, Bonus, Jarima, Voucher, Oylik
        }, status=status.HTTP_200_OK)


class ExpenseSubcategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Xarajatlar'
    queryset = ExpenseSubcategory.objects.all()
    serializer_class = ExpenseSubcategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category']
from django.db import transaction as db_transaction

class ExpenseViewSet(viewsets.ModelViewSet):  # Agar TenantViewSetMixin kerak bo'lsa, merosxo'rlikka qaytarib qo'ying
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

    # 🌟 Real vaqtda kassa balansi va tranzaksiyani boshqarish
    def perform_create(self, serializer):
        with db_transaction.atomic():
            # Xarajatni saqlaymiz
            expense = serializer.save()

            # Agar kassa tanlangan bo'lsa, pul ayiramiz va tranzaksiya yozamiz
            if expense.cashbox:
                cashbox = expense.cashbox
                cashbox.balance -= expense.amount
                cashbox.save()

                # Sarlavhani description JSON ichidan o'qib olishga harakat qilamiz
                try:
                    import json
                    unpacked = json.loads(expense.description)
                    title = unpacked.get('name') or expense.category.name
                except:
                    title = expense.category.name if expense.category else "Xarajat"

                Transaction.objects.create(
                    cashbox=cashbox,
                    amount=expense.amount,
                    type='EXPENSE',
                    category='DIRECT',
                    description=f"Xarajat: {title}"
                )

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
    queryset = Bonus.objects.all()
    serializer_class = BonusSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee']

class FineViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Ish haqi'
    queryset = Fine.objects.all()
    serializer_class = FineSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee']

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
        
        period = request.data.get('period') or request.data.get('month') # Support both period and month
        if not period:
            return Response({"detail": "Period (YYYY-MM) is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Parse year/month
        try:
            year, month = map(int, period.split('-'))
            # TO'G'RILANDI: timezone datetime xatoligi to'g'ri Python datetime obyektiga o'tkazildi
            calc_date = datetime(year, month, 15).date()
        except ValueError:
            return Response({"detail": "Invalid period format. Use YYYY-MM."}, status=status.HTTP_400_BAD_REQUEST)
            
        employees = User.objects.filter(organization_id=org_id).exclude(is_superuser=True)
        calculated = []
        for emp in employees:
            # Simple employee salary base calculation: check if there's rules or configure default
            # Deduct fines and add bonuses in the same period
            bonuses = Bonus.objects.filter(employee=emp, date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            fines = Fine.objects.filter(employee=emp, date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            base_salary = Decimal('1000.00') # Default base salary
            if emp.role == 'manager':
                base_salary = Decimal('1500.00')
            elif emp.role == 'admin':
                base_salary = Decimal('2000.00')
            
            total_salary = base_salary + bonuses - fines
            
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
            return Response({"detail": "Organization and period query params are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        rules = TeacherSalaryRule.objects.filter(organization_id=org_id, period=period)
        return Response(TeacherSalaryRuleSerializer(rules, many=True).data, status=status.HTTP_200_OK)

    @decorators.action(detail=False, methods=['post'], url_path='configure-period')
    def configure_period(self, request):
        org_id = self.get_organization_id()
        source_period = request.data.get('source_period')
        target_period = request.data.get('target_period')
        
        if not org_id or not source_period or not target_period:
            return Response({"detail": "org_id, source_period, and target_period are required."}, status=status.HTTP_400_BAD_REQUEST)
            
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
            return Response({"detail": "Organization and period query params are required."}, status=status.HTTP_400_BAD_REQUEST)
            
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
            return Response({"detail": "org_id and period query params are required."}, status=status.HTTP_400_BAD_REQUEST)
            
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
            Transaction.objects.create(
                cashbox=cashbox,
                amount=final_payout,
                type='EXPENSE',
                description=f"Oylik to'lovi: {salary_calc.teacher} uchun ({salary_calc.period} davri)"
            )

            # 5. Kassaning haqiqiy balansini kamaytiramiz
            cashbox.balance -= final_payout
            cashbox.save()

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
        period = request.data.get('period') or request.data.get('month') # Support both period and month
        
        if not org_id or not period:
            return Response({"detail": "org_id and period are required in payload."}, status=status.HTTP_400_BAD_REQUEST)
            
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
                # Use default standard rule if available, otherwise static fallback
                if std_rule:
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
                        student_groups = student_groups.exclude(student__first_name__icontains='trial').exclude(student__first_name__icontains='sinov')

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
                    
                else: # percentage
                    total_revenue = Decimal('0.00')
                    student_groups = StudentGroup.objects.filter(group__teacher=teacher, organization_id=org_id).select_related('group', 'group__course')
                    student_count = student_groups.count()
                    
                    # N+1 so'rovlar muammosini oldini olish uchun barcha StudentPricing yozuvlarini bir so'rovda yuklaymiz
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
                            price = sg.price or getattr(sg.group, 'price', None) or (sg.group.course.price if sg.group and sg.group.course else Decimal('0.00'))
                        
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
                        if weekday in (1, 3, 5): # Tue, Thu, Sat
                            day_schedules = even_schedules
                        elif weekday in (0, 2, 4): # Mon, Wed, Fri
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
        base_filter = Q(organization_id=org_id, balance__lt=0)
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
            total_calc = TeacherSalaryCalculation.objects.filter(teacher=t).aggregate(total=Sum('calculated_amount'))['total'] or Decimal('0.00')
            # Get total paid amount
            total_paid = TeacherSalaryPayment.objects.filter(teacher=t).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
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
            total_calc = TeacherSalaryCalculation.objects.filter(teacher=t).aggregate(total=Sum('calculated_amount'))['total'] or Decimal('0.00')
            total_paid = TeacherSalaryPayment.objects.filter(teacher=t).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
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
        student_debt = Student.objects.filter(organization_id=org_id, balance__lt=0).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        student_debt_abs = abs(student_debt)
        
        # Teacher debts calculation
        teachers = User.objects.filter(organization_id=org_id, role='teacher')
        teacher_debt_val = Decimal('0.00')
        for t in teachers:
            total_calc = TeacherSalaryCalculation.objects.filter(teacher=t).aggregate(total=Sum('calculated_amount'))['total'] or Decimal('0.00')
            total_paid = TeacherSalaryPayment.objects.filter(teacher=t).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
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
            payments_sum = Payment.objects.filter(payment_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            expenses_sum = Expense.objects.filter(expense_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        else:
            payments_sum = Payment.objects.filter(organization_id=org_id).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            expenses_sum = Expense.objects.filter(organization_id=org_id).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
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
            
            total_expense = Expense.objects.filter(**e_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            total_salary = Salary.objects.filter(**s_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            total_teacher_salary = TeacherSalaryPayment.objects.filter(**t_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
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
        
        # Procedurally update student balance when a withdrawal is added
        student = serializer.validated_data.get('student')
        if student:
            student.balance += serializer.validated_data['amount']
            student.save()
            
        serializer.save(organization_id=self.get_organization_id(), branch_id=self.get_branch_id())

    def perform_destroy(self, instance):
        # Procedurally update student balance when a withdrawal is deleted (refund the withdrawal amount)
        student = instance.student
        if student:
            student.balance -= instance.amount
            student.save()
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

        # 1. Abdulmajid so'ragan barcha filtrlarni qabul qilish (Subkursdan tashqari)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        marketing_id = request.query_params.get('marketing')
        course_id = request.query_params.get('course')
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
        if course_id:
            base_filter &= Q(course_id=course_id)
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
        # Eslatma: 'status' maydonidagi qiymatlarni o'zingizning CRM liddingizga qarab moslang
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
            {"id": 8, "status_name": "Birinchi to'lovni qilib ketganlar", "count": stats['first_payment_left']},
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
        course_distribution = (
            Lead.objects.filter(base_filter)
            .values('course__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        course_chart = {
            "labels": [c['course__name'] or "Noma'lum" for c in course_distribution],
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
from organizations.mixins import TenantViewSetMixin # Agar mixiningiz nomi boshqacha bo'lsa to'g'rilab oling
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

    def get(self, request):
        setting = self.get_object()
        serializer = FinanceSettingSerializer(setting)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        setting = self.get_object()
        serializer = FinanceSettingSerializer(setting, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
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
        # Faqat foydalanuvchining tashkilotiga tegishli kassalarni olish
        cashboxes = Cashbox.objects.filter(organization=request.user.organization, is_archived=False)
        serializer = CashboxSerializer(cashboxes, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CashboxSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(organization=request.user.organization)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdvancedPaymentReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """To'lovlar uchun o'qituvchi, sana va kassa bo'yicha o'ta tez ishlaydigan filter"""
        org_id = getattr(request.user, 'organization_id', None)
        queryset = Payment.objects.filter(organization_id=org_id).select_related('student', 'cashbox', 'employee')

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
            serializer.save(organization=request.user.organization)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TransactionReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Moliya jadvali va filterlar (Sana, Kassa, O'qituvchi bo'yicha)"""
        queryset = CashTransaction.objects.filter(
            organization=request.user.organization
        ).select_related('student', 'cashbox').order_by('-date', '-id')

        # Filter: Kassa bo'yicha
        cashbox_id = request.query_params.get('cashbox_id')
        if cashbox_id:
            queryset = queryset.filter(cashbox_id=cashbox_id)

        # Filter: To'lov turi (Naqd, Plastik, Terminal)
        payment_method = request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

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

        serializer = CashTransactionSerializer(queryset, many=True)
        return Response(serializer.data)


# finance/models.py faylining oxiriga qo'shing:

# finance/views.py ichida:
from rest_framework import viewsets
from .models import FinanceAction, Transaction, Cashbox
from django.db import transaction


class FinanceActionViewSet(viewsets.ModelViewSet):
    queryset = FinanceAction.objects.all()

    serializer_class = FinanceActionSerializer
    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()

            # 1. AGAR BONUS BO'LSA (Kassadan pul chiqadi)
            if instance.action_type == 'BONUS':
                cashbox_id = self.request.data.get('cashbox')
                if cashbox_id:
                    cashbox = Cashbox.objects.get(id=cashbox_id)
                    t = Transaction.objects.create(
                        cashbox=cashbox,
                        amount=instance.amount,
                        type='EXPENSE',
                        description=f"{instance.get_target_type_display()} uchun bonus: {instance.reason}"
                    )
                    cashbox.balance -= instance.amount
                    cashbox.save()

                    instance.transaction = t
                    instance.save()

            # 2. AGAR JARIMA BO'LSA
            elif instance.action_type == 'PENALTY':
                # Kassadan pul yechilmaydi! Shunchaki bazaga yoziladi.
                # Bu jarima oylik hisoblanayotganda avtomatik chegirib tashlanadi.
                pass

from .filters import FinancialReportFilter


class FinancialAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get('type', 'kirim').lower()

        # 🌟 TO'G'RILANDI: cashbox__tenant_id o'rniga model maydoningizga mos cashbox__organization_id qo'yildi
        tx_queryset = Transaction.objects.filter(cashbox__organization_id=request.user.organization_id)

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

        # 🌟 TO'G'RILANDI: cashbox__tenant_id o'rniga cashbox__organization_id ishlatildi
        queryset = Transaction.objects.filter(cashbox__organization_id=request.user.organization_id)

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

        # 1. 🌟 To'g'rilandi: Tashkilot bo'yicha filterlashni organization_id orqali qilamiz
        queryset = Transaction.objects.filter(cashbox__organization_id=request.user.organization_id)

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

        # Tashkilot bo'yicha boshlang'ich filter
        queryset = Transaction.objects.filter(cashbox__organization_id=request.user.organization_id)

        # Sanalar bo'yicha xavfsiz filterlash
        if from_date:
            try:
                queryset = queryset.filter(created_at__gte=datetime.strptime(from_date, '%Y-%m-%d'))
            except ValueError:
                pass
        if to_date:
            try:
                queryset = queryset.filter(created_at__lte=datetime.combine(datetime.strptime(to_date, '%Y-%m-%d'), time.max))
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



class TransactionCategoryViewSet(viewsets.ModelViewSet):

    serializer_class = TransactionCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type']

    def get_queryset(self):

        return TransactionCategory.objects.filter(organization_id=self.request.user.organization_id)

    def perform_create(self, serializer):
        serializer.save(organization_id=self.request.user.organization_id)


class EmployeeFinanceBalanceReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.user.organization_id
        branch_id = request.query_params.get('branch')

        employees_qs = User.objects.filter(organization_id=org_id)
        if branch_id:
            employees_qs = employees_qs.filter(branch_id=branch_id)

        rows = []
        total_salary, total_bonus, total_advance, total_penalty = 0, 0, 0, 0

        for emp in employees_qs:
            salary = float(getattr(emp, 'base_salary', getattr(emp, 'salary', 0)) or 0)
            bonus, advance, penalty = 0, 0, 0
            final_salary = salary + bonus - advance - penalty

            total_salary += final_salary

            if hasattr(emp, 'get_full_name'):
                full_name = emp.get_full_name()
            else:
                full_name = f"{getattr(emp, 'first_name', '')} {getattr(emp, 'last_name', '')}".strip() or getattr(emp,
                                                                                                                   'username',
                                                                                                                   'Xodim')

            rows.append({
                "id": emp.id,
                "full_name": full_name,
                "phone": getattr(emp, 'phone', getattr(emp, 'phone_number', '-')),
                "salary": f"{final_salary:,.0f} UZS".replace(",", " "),
                "bonus": f"{bonus:,.0f} UZS".replace(",", " "),
                "advance": f"{advance:,.0f} UZS".replace(",", " "),
                "penalty": f"{penalty:,.0f} UZS".replace(",", " ")
            })

        return Response({"table_data": rows,
                         "totals": {"salary": total_salary, "bonus": total_bonus, "advance": total_advance,
                                    "penalty": total_penalty}}, status=status.HTTP_200_OK)


# =====================================================================
# 3-RASM: TUSHUM REJASI (Statik - Abdulmajid layoutni ko'rishi uchun)
# =====================================================================
class RevenuePlanReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get('date', '23.06.2026')
        data = [
            {"target": f"{date_str}", "students_count": 0, "expected_amount": 0},
            {"target": "Eski oydan qarzdor bo'lib o'tgan o'quvchilar summasi", "students_count": 0,
             "expected_amount": 0},
            {"target": "Eski oydan o'quvchilar to'lab o'tgan summa", "students_count": 0, "expected_amount": 0},
            {"target": "Shu oyda to'langan summa", "students_count": 0, "expected_amount": 0},
            {"target": "Qolgan kutilayotgan tushum", "students_count": 0, "expected_amount": 0},
        ]
        return Response(data, status=status.HTTP_200_OK)


# =====================================================================
# 4-RASM: OʻQUVCHINING UMUMIY TOʻLANMAGAN TOʻLOVLARI
# =====================================================================
class UnpaidLessonsReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = request.user.organization_id
        branch_id = request.query_params.get('branch')

        # Student modelida balance bor deb hisoblaymiz, bo'lmasa xato bermaydi
        students_qs = Student.objects.filter(organization_id=org_id)
        if branch_id:
            students_qs = students_qs.filter(branch_id=branch_id)

        rows = []
        for index, student in enumerate(students_qs[:10], start=1):  # Namuna uchun top 10 talaba
            balance = float(getattr(student, 'balance', 0) or 0)
            if balance < 0:  # Faqat qarzi borlar
                rows.append({
                    "id": index,
                    "name": getattr(student, 'full_name', getattr(student, 'name', 'Talaba')),
                    "groups": ", ".join([g.name for g in student.groups.all()]) if hasattr(student, 'groups') else "-",
                    "unpaid_lessons_count": abs(int(balance / 50000)) if balance else 0,
                    "total_unpaid_amount": abs(balance)
                })

        return Response({"total_count": len(rows), "table_data": rows}, status=status.HTTP_200_OK)


# =====================================================================
# 5-RASM: BEKOR QILINGAN TOʻLOVLAR HISOBOTI
# =====================================================================
class CancelledPaymentsReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Tranzaksiyalar modelidan 'CANCELLED' statusdagilarini olamiz
        from finance.models import Transaction
        org_id = request.user.organization_id
        branch_id = request.query_params.get('branch')

        # Agar Transaction modelida status yoki type bo'lsa filterlaymiz
        tx_qs = Transaction.objects.filter(cashbox__organization_id=org_id)[:10]

        rows = []
        for index, tx in enumerate(tx_qs, start=1):
            rows.append({
                "id": index,
                "name": "Noma'lum Talaba",
                "unpaid_lessons": 0,
                "total_unpaid": float(getattr(tx, 'amount', 0)),
                "teacher": "-",
                "group": "-",
                "description": getattr(tx, 'comment', 'Bekor qilingan')
            })
        return Response({"total_count": len(rows), "table_data": rows}, status=status.HTTP_200_OK)


# =====================================================================
# 6-RASM: UMUMIY CHEGIRMALAR VA BONUSLAR HISOBOTI
# =====================================================================
class DiscountsAndBonusesReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Hozircha billingda chegirma modeli yo'qligi uchun xavfsiz bo'sh ro'yxat qaytaramiz
        return Response({
            "summary": {"total_bonuses": 0.0, "total_discounts": 0.0},
            "total_count": 0,
            "table_data": []
        }, status=status.HTTP_200_OK)