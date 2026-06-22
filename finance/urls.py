from django.urls import path, include
from rest_framework.routers import DefaultRouter
from finance.views import (
    ExpenseCategoryViewSet, ExpenseSubcategoryViewSet, ExpenseViewSet,
    DetailedExpenseViewSet, MonthlyIncomeViewSet, PaymentViewSet, SaleViewSet,
    BonusViewSet, FineViewSet, SalaryViewSet, TeacherSalaryRuleViewSet,
    TeacherSalaryCalculationViewSet, TeacherSalaryCalculateView, TeacherSalaryPaymentsView,
    StudentDebtsView, StudentDebtsSummaryView, StudentDebtDetailView,
    TeacherDebtsView, TeacherDebtsSummaryView, AllDebtsView, CashboxViewSet, FinanceReportView,
    WithdrawalViewSet, ConversionReportsFunnelView, CRMLeadsListView,
    ConversionReportsOverviewView, ConversionReportsLostReasonsView, ConversionReportsPipelineTransitionsView,
    LeadsReportPieChartView, LeadsReportBarChartView, LeadsReportStatisticsView, CompanyProfitChartView,FinanceActionViewSet
)

from finance.views import StaffSalaryPercentViewSet, FinanceSettingAPIView,FinancialReportsView,FinancialAnalyticsView,TransactionReportAPIView,TransactionCreateAPIView,AdvancedPaymentReportAPIView,CashboxListCreateAPIView

from finance.views import CashFlowReportView, ProfitAndLossReportView,TransactionViewSet,TransactionTypesView

router = DefaultRouter()
router.register(r'salary-percents', StaffSalaryPercentViewSet, basename='salary-percent')
router.register(r'expense-categories', ExpenseCategoryViewSet, basename='expense-category')
router.register(r'actions', FinanceActionViewSet, basename='finance-actions')
router.register(r'expense-subcategories', ExpenseSubcategoryViewSet, basename='expense-subcategory')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'detailed-expenses', DetailedExpenseViewSet, basename='detailed-expense')
router.register(r'monthly-income', MonthlyIncomeViewSet, basename='monthly-income')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'bonuses', BonusViewSet, basename='bonus')
router.register(r'fines', FineViewSet, basename='fine')
router.register(r'salaries', SalaryViewSet, basename='salary')
router.register(r'teacher-salary-rules', TeacherSalaryRuleViewSet, basename='teacher-salary-rule')
router.register(r'salary-calculations', TeacherSalaryCalculationViewSet, basename='teacher-salary-calculation')
router.register(r'teacher-salary-payments', TeacherSalaryPaymentsView, basename='teacher-salary-payment')
router.register(r'cashboxes', CashboxViewSet, basename='cashbox')
router.register(r'withdrawals', WithdrawalViewSet, basename='withdrawal')
router.register(r'transactions', TransactionViewSet, basename='transactions')

urlpatterns = [
    # Custom endpoints
    path('teacher-salary/calculate/', TeacherSalaryCalculateView.as_view(), name='teacher-salary-calculate'),
    path('report/', FinanceReportView.as_view(), name='finance-report'),
    path('profit-chart/', CompanyProfitChartView.as_view(), name='company-profit-chart'),
    path('settings/', FinanceSettingAPIView.as_view(), name='finance-settings'),
    
    path('student-debts/summary/', StudentDebtsSummaryView.as_view(), name='student-debts-summary'),
    path('student-debts/', StudentDebtsView.as_view(), name='student-debts-list'),
    path('student-debts/<int:pk>/', StudentDebtDetailView.as_view(), name='student-debts-detail'),
    path('cashboxes/', CashboxListCreateAPIView.as_view(), name='cashbox-list-create'),
    path('financial-reports/', FinancialReportsView.as_view(), name='financial-reports'),
    # 2. Kuchaytirilgan moliya filtri (Sana, Kassa, O'qituvchi bo'yicha)
    path('payments/report/', AdvancedPaymentReportAPIView.as_view(), name='payments-report'),
    path('teacher-debts/summary/', TeacherDebtsSummaryView.as_view(), name='teacher-debts-summary'),
    path('teacher-debts/', TeacherDebtsView.as_view(), name='teacher-debts-list'),
    # Kirim/Chiqim tranzaksiyalarini yaratish
    path('transactions/create/', TransactionCreateAPIView.as_view(), name='transaction-create'),

    # Asosiy jadval va moliya hisoboti (Filterlar bilan)
    path('transactions/report/', TransactionReportAPIView.as_view(), name='transaction-report'),
    path('all-debts/', AllDebtsView.as_view(), name='all-debts'),
    path('analytics/', FinancialAnalyticsView.as_view(), name='financial-analytics'),
    # CRM Conversion Reports
    path('conversion-reports/funnel/', ConversionReportsFunnelView.as_view(), name='conversion-reports-funnel'),
    path('conversion-reports/overview/', ConversionReportsOverviewView.as_view(), name='conversion-reports-overview'),
    path('conversion-reports/lost-reasons/', ConversionReportsLostReasonsView.as_view(), name='conversion-reports-lost-reasons'),
    path('conversion-reports/pipeline-transitions/', ConversionReportsPipelineTransitionsView.as_view(), name='conversion-reports-pipeline-transitions'),
    path('crm-leads/', CRMLeadsListView.as_view(), name='crm-leads-list'),
    
    # CRM Leads Reports
    path('leads-report/pie-chart/', LeadsReportPieChartView.as_view(), name='leads-report-pie-chart'),
    path('leads-report/bar-chart/', LeadsReportBarChartView.as_view(), name='leads-report-bar-chart'),
    path('leads-report/statistics/', LeadsReportStatisticsView.as_view(), name='leads-report-statistics'),
    path('reports/cash-flow/', CashFlowReportView.as_view(), name='report-cash-flow'),
    path('reports/profit-loss/', ProfitAndLossReportView.as_view(), name='report-profit-loss'),
    path('transactions/types/', TransactionTypesView.as_view(), name='transaction-types'),
    path('', include(router.urls)),
]
