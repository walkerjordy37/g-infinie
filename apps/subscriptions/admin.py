"""
Subscriptions admin - PlatformPlan, CompanySubscription, PaymentTransaction.
"""
from django.contrib import admin
from .models import PlatformPlan, CompanySubscription, PaymentTransaction


@admin.register(PlatformPlan)
class PlatformPlanAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'monthly_price', 'yearly_price',
        'max_users', 'max_products', 'is_active'
    ]
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'company', 'plan', 'status', 'billing_cycle',
        'current_period_end', 'amount'
    ]
    list_filter = ['status', 'plan', 'billing_cycle']
    search_fields = ['company__name']


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'subscription', 'payment_method',
        'amount', 'status', 'paid_at'
    ]
    list_filter = ['status', 'payment_method']
    search_fields = ['transaction_id', 'phone_number']
    date_hierarchy = 'created_at'
