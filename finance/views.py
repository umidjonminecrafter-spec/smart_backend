from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status, decorators, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from decimal import Decimal

from organizations.mixins import TenantViewSetMixin
from organizations.permissions import HasOrganizationPagePermission
from datetime import datetime
from finance.models import (
    ExpenseCategory, ExpenseSubcategory, Expense, MonthlyIncome,
    Payment, Sale, Bonus, Fine, Salary, TeacherSalaryRule, TeacherSalaryCalculation, Cashbox,CashTransaction
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

User = get_user_model()

class ExpenseCategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Xarajatlar'
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer

class ExpenseSubcategoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Xarajatlar'
    queryset = ExpenseSubcategory.objects.all()
    serializer_class = ExpenseSubcategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category']

class ExpenseViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Xarajatlar'
    queryset = Expense.objects.all().select_related('category', 'subcategory')
    serializer_class = ExpenseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['category', 'subcategory']
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
            
        # Search query (for name/recipient/izoh inside packed JSON description or plain text)
        search_query = self.request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(description__icontains=search_query)
            
        # Payment type / Cashbox filtering
        payment_type = self.request.query_params.get('payment_type')
        if payment_type:
            queryset = queryset.filter(description__icontains=f'"payment_type": {payment_type}') | queryset.filter(description__icontains=f'"payment_type": "{payment_type}"')
            
        return queryset

    @decorators.action(detail=False, methods=['get'], url_path='monthly-summary')
    def monthly_summary(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        expenses = Expense.objects.filter(organization_id=org_id)
        # In SQLite, we can extract month using strftime or process in python
        # Processing in Python is extremely safe and database-agnostic
        summary = {}
        for exp in expenses:
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
    Sotuv voronkasi (Funnel chart) uchun ma'lumotlar:
    Har bir pipeline (bosqich) bo'yicha lidlar sonini qaytaradi.
    """
    def get(self, request):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        source_id = request.query_params.get('source')
        
        from crm.models import Pipeline, Lead
        pipelines = Pipeline.objects.filter(organization_id=org_id).order_by('order')
        
        if not pipelines.exists():
            return Response([], status=status.HTTP_200_OK)
            
        data = []
        for pl in pipelines:
            leads_qs = Lead.objects.filter(organization_id=org_id, pipeline=pl, is_archived=False)
            
            if start_date:
                leads_qs = leads_qs.filter(created_at__date__gte=start_date)
            if end_date:
                leads_qs = leads_qs.filter(created_at__date__lte=end_date)
            if source_id:
                leads_qs = leads_qs.filter(source_id=source_id)
                
            lead_count = leads_qs.count()
            
            data.append({
                "pipeline_id": pl.id,
                "pipeline_name": pl.name,
                "total_leads": lead_count
            })
            
        return Response(data, status=status.HTTP_200_OK)


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