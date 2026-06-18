from django.contrib import admin
from finance.models import (
    ExpenseCategory, ExpenseSubcategory, Expense, MonthlyIncome,
    Payment, Sale, Bonus, Fine, Salary, TeacherSalaryRule, TeacherSalaryCalculation,StaffSalaryPercent
)
from organizations.admin import TenantAdminMixin

@admin.register(StaffSalaryPercent)
class StaffSalaryPercentAdmin(TenantAdminMixin, admin.ModelAdmin):
    # Admin panel ro'yxatida ko'rinadigan ustunlar
    list_display = ('id', 'name', 'percent', 'organization', 'comment')

    # Qidiruv maydonlari
    search_fields = ('name', 'comment')

    # Filterlar (o'ng tarafda turadigan)
    list_filter = ('percent', 'organization')

    # Yangi foiz qo'shish oynasida ko'rinadigan maydonlar strukturasi
    fields = ('name', 'percent', 'comment')

    # Multi-tenant qoidasiga ko'ra organization avtomat orqada saqlanadi
    def save_model(self, request, obj, form, change):
        if not change:  # Agar yangi yaratilayotgan bo'lsa
            # Agar sizda request.user orqali tashkilotni aniqlash mantiqi bo'lsa:
            obj.organization_id = getattr(request.user, 'organization_id', None)
        super().save_model(request, obj, form, change)

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organization')
    search_fields = ('name',)

@admin.register(ExpenseSubcategory)
class ExpenseSubcategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'name', 'organization')
    list_filter = ('category',)
    search_fields = ('name',)

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'subcategory', 'amount', 'date', 'organization')
    list_filter = ('category', 'date')
    search_fields = ('description',)

@admin.register(MonthlyIncome)
class MonthlyIncomeAdmin(admin.ModelAdmin):
    list_display = ('id', 'amount', 'date', 'organization')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'amount', 'date', 'payment_method', 'organization')
    list_filter = ('date', 'payment_method')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_or_course', 'amount', 'date', 'organization')
    list_filter = ('date',)

@admin.register(Bonus)
class BonusAdmin(admin.ModelAdmin):
    list_display = ('id', 'employee', 'amount', 'date', 'organization')

@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ('id', 'employee', 'amount', 'date', 'organization')

@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'employee', 'amount', 'date', 'status', 'organization')
    list_filter = ('status', 'date')

@admin.register(TeacherSalaryRule)
class TeacherSalaryRuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'teacher', 'rule_type', 'rate', 'period', 'is_active', 'organization')
    list_filter = ('rule_type', 'is_active', 'period')

@admin.register(TeacherSalaryCalculation)
class TeacherSalaryCalculationAdmin(admin.ModelAdmin):
    list_display = ('id', 'teacher', 'calculated_amount', 'period', 'organization')
    list_filter = ('period',)
