"""
Subscriptions serializers - PlatformPlan, CompanySubscription, PaymentTransaction.
"""
from rest_framework import serializers
from .models import PlatformPlan, CompanySubscription, PaymentTransaction


class PlatformPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformPlan
        fields = [
            'id', 'code', 'name', 'description',
            'monthly_price', 'yearly_price',
            'max_users', 'max_products',
            'has_scanner', 'has_csv_import', 'has_full_cycles',
            'has_dashboard', 'has_multi_site', 'has_offline_mode',
            'has_whatsapp_alerts', 'has_api_access',
            'trial_days', 'is_active', 'sort_order',
            'created_at', 'updated_at',
        ]


class CompanySubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_trial = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = CompanySubscription
        fields = [
            'id', 'company', 'plan', 'plan_name',
            'status', 'status_display', 'billing_cycle',
            'start_date', 'trial_end_date',
            'current_period_start', 'current_period_end',
            'amount', 'auto_renew',
            'cancelled_at', 'cancellation_reason',
            'days_remaining', 'is_active', 'is_trial', 'is_expired',
            'created_at', 'updated_at',
        ]


class CompanySubscriptionCreateSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=PlatformPlan.objects.filter(is_active=True))
    billing_cycle = serializers.ChoiceField(choices=CompanySubscription.BILLING_CHOICES)


class PaymentTransactionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='subscription.company.name', read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'subscription', 'transaction_id',
            'payment_method', 'amount', 'currency_code',
            'status', 'phone_number',
            'provider_reference', 'provider_response',
            'error_message', 'paid_at', 'metadata',
            'company_name',
            'created_at', 'updated_at',
        ]


class InitiatePaymentSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=PaymentTransaction.PAYMENT_METHOD_CHOICES)
    phone_number = serializers.CharField(max_length=20)
