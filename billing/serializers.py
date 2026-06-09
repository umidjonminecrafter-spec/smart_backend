from rest_framework import serializers
from billing.models import BillingHistory, BalanceTopUp, TariffPurchase


class BillingHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingHistory
        fields = '__all__'
        read_only_fields = ('id', 'organization', 'created_at', 'updated_at')


class BalanceTopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceTopUp
        fields = '__all__'
        read_only_fields = ('id', 'organization', 'created_at', 'updated_at')


class TariffPurchaseSerializer(serializers.ModelSerializer):
    tariff_name = serializers.CharField(source='tariff.name', read_only=True)

    class Meta:
        model = TariffPurchase
        fields = '__all__'
        read_only_fields = ('id', 'organization', 'created_at', 'updated_at')