from django.contrib import admin
from .models import (
    Currency, ExchangeRate, Company, Branch,
    FiscalYear, FiscalPeriod, DocumentSequence, CompanySettings
)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['from_currency', 'to_currency', 'rate', 'date']
    list_filter = ['from_currency', 'to_currency', 'date']
    date_hierarchy = 'date'


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0


class CompanySettingsInline(admin.StackedInline):
    model = CompanySettings
    can_delete = False


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'city', 'country', 'currency', 'is_active']
    list_filter = ['is_active', 'country', 'currency']
    search_fields = ['code', 'name', 'tax_id']
    inlines = [BranchInline, CompanySettingsInline]


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'company', 'city', 'is_headquarters', 'is_active']
    list_filter = ['company', 'is_active', 'is_headquarters']
    search_fields = ['code', 'name']


class FiscalPeriodInline(admin.TabularInline):
    model = FiscalPeriod
    extra = 0


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'company', 'start_date', 'end_date', 'status']
    list_filter = ['company', 'status']
    search_fields = ['code', 'name']
    inlines = [FiscalPeriodInline]


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'fiscal_year', 'number', 'start_date', 'end_date', 'status']
    list_filter = ['fiscal_year__company', 'status']
    search_fields = ['name', 'fiscal_year__code']


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ['document_type', 'company', 'prefix', 'next_number', 'fiscal_year']
    list_filter = ['company', 'document_type']
