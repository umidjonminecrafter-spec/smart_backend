import django_filters
from .models import Transaction, FinanceAction


class FinancialReportFilter(django_filters.FilterSet):
    # Sanalar bo'yicha filter (Sizda skrinshotda turgan kalendar uchun)
    start_date = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    end_date = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    # Kassa va to'lov turi bo'yicha filter
    kassa = django_filters.NumberFilter(field_name="cashbox_id")

    class Meta:
        model = Transaction
        fields = ['type', 'kassa', 'start_date', 'end_date']