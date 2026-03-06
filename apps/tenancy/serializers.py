"""
Serializers for tenancy module.
"""
from rest_framework import serializers
from apps.core.serializers import BaseModelSerializer
from .models import (
    Currency, ExchangeRate, Company, Branch,
    FiscalYear, FiscalPeriod, DocumentSequence, CompanySettings
)


class CurrencySerializer(BaseModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'decimal_places', 'is_active']
        read_only_fields = ['id']


class ExchangeRateSerializer(BaseModelSerializer):
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)

    class Meta:
        model = ExchangeRate
        fields = [
            'id', 'from_currency', 'from_currency_code',
            'to_currency', 'to_currency_code',
            'rate', 'date', 'source'
        ]


class BranchSerializer(BaseModelSerializer):
    class Meta:
        model = Branch
        fields = [
            'id', 'company', 'code', 'name', 'street', 'city',
            'phone', 'is_active', 'is_headquarters'
        ]
        read_only_fields = ['id', 'company']


class CompanySettingsSerializer(BaseModelSerializer):
    class Meta:
        model = CompanySettings
        fields = [
            'default_receivable_account', 'default_payable_account',
            'default_sales_account', 'default_purchase_account',
            'default_vat_collected_account', 'default_vat_deductible_account',
            'default_payment_terms_days', 'quote_validity_days',
            'default_valuation_method', 'allow_negative_stock',
            'invoice_notes', 'invoice_footer'
        ]


class CompanySerializer(BaseModelSerializer):
    settings = CompanySettingsSerializer(read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    branches = BranchSerializer(many=True, read_only=True)

    class Meta:
        model = Company
        fields = [
            'id', 'code', 'name', 'legal_name', 'tax_id', 'trade_register',
            'street', 'street2', 'city', 'state', 'postal_code', 'country',
            'phone', 'email', 'website',
            'currency', 'currency_code', 'fiscal_year_start_month',
            'logo', 'is_active', 'settings', 'branches',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanyCreateSerializer(BaseModelSerializer):
    class Meta:
        model = Company
        fields = [
            'code', 'name', 'legal_name', 'tax_id', 'trade_register',
            'street', 'street2', 'city', 'state', 'postal_code', 'country',
            'phone', 'email', 'website', 'currency', 'fiscal_year_start_month'
        ]


class FiscalPeriodSerializer(BaseModelSerializer):
    class Meta:
        model = FiscalPeriod
        fields = [
            'id', 'fiscal_year', 'name', 'number',
            'start_date', 'end_date', 'status'
        ]
        read_only_fields = ['id', 'fiscal_year']


class FiscalYearSerializer(BaseModelSerializer):
    periods = FiscalPeriodSerializer(many=True, read_only=True)

    class Meta:
        model = FiscalYear
        fields = [
            'id', 'company', 'name', 'code', 'start_date', 'end_date',
            'status', 'periods', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class DocumentSequenceSerializer(BaseModelSerializer):
    class Meta:
        model = DocumentSequence
        fields = [
            'id', 'company', 'document_type', 'prefix', 'suffix',
            'padding', 'next_number', 'fiscal_year', 'reset_on_fiscal_year'
        ]
        read_only_fields = ['id', 'company', 'next_number']
