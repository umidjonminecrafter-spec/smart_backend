from django.contrib import admin
from billing.models import BillingHistory, BalanceTopUp, TariffPurchase, SubscriptionRequest

@admin.register(BillingHistory)
class BillingHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'amount', 'plan_name', 'months', 'created_at')
    list_filter = ('plan_name', 'created_at')
    search_fields = ('organization__name', 'plan_name')

@admin.register(BalanceTopUp)
class BalanceTopUpAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'amount', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('organization__name',)

@admin.register(TariffPurchase)
class TariffPurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'tariff', 'amount', 'start_date', 'next_charge_date', 'is_active')
    list_filter = ('is_active', 'start_date', 'next_charge_date')
    search_fields = ('organization__name', 'tariff__name')

@admin.register(SubscriptionRequest)
class SubscriptionRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'tariff', 'months', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'tariff')
    search_fields = ('organization__name', 'tariff__name')