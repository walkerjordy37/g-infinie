"""
Tax admin - Admin configuration for taxes, rates, rules, and declarations.
"""
from django.contrib import admin
from .models import (
    TaxType, TaxRate, TaxGroup, TaxRule,
    WithholdingTax, TaxDeclaration, TaxDeclarationLine
)


# =============================================================================
# TAX TYPE ADMIN
# =============================================================================

@admin.register(TaxType)
class TaxTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'tax_type', 'is_active']
    list_filter = ['tax_type', 'is_active']
    search_fields = ['code', 'name', 'description']
    autocomplete_fields = ['account_collected', 'account_deductible', 'account_payable']
    ordering = ['code']

    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'name', 'tax_type', 'description', 'is_active')
        }),
        ('Comptes comptables', {
            'fields': ('account_collected', 'account_deductible', 'account_payable'),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# TAX RATE ADMIN
# =============================================================================

@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ['name', 'tax_type', 'rate', 'valid_from', 'valid_to', 'is_default', 'is_active']
    list_filter = ['tax_type', 'is_default', 'is_active']
    search_fields = ['name', 'description']
    autocomplete_fields = ['tax_type']
    ordering = ['-valid_from']
    date_hierarchy = 'valid_from'

    fieldsets = (
        ('Informations générales', {
            'fields': ('tax_type', 'name', 'rate', 'description')
        }),
        ('Validité', {
            'fields': ('valid_from', 'valid_to', 'is_default', 'is_active')
        }),
    )


# =============================================================================
# TAX GROUP ADMIN
# =============================================================================

@admin.register(TaxGroup)
class TaxGroupAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'get_total_rate']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'description']
    filter_horizontal = ['tax_rates']
    ordering = ['code']

    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'name', 'description', 'is_active')
        }),
        ('Taux de taxe', {
            'fields': ('tax_rates',)
        }),
    )

    def get_total_rate(self, obj):
        return f"{obj.total_rate}%"
    get_total_rate.short_description = 'Taux total'


# =============================================================================
# TAX RULE ADMIN
# =============================================================================

@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'transaction_type', 'partner_type',
        'tax_group', 'priority', 'is_active'
    ]
    list_filter = ['transaction_type', 'partner_type', 'is_active']
    search_fields = ['code', 'name', 'description']
    autocomplete_fields = ['tax_group', 'product_category']
    ordering = ['-priority', 'code']

    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'name', 'description')
        }),
        ('Conditions', {
            'fields': (
                'transaction_type', 'partner_type',
                'country', 'product_category'
            )
        }),
        ('Taxe applicable', {
            'fields': ('tax_group', 'priority')
        }),
        ('Validité', {
            'fields': ('valid_from', 'valid_to', 'is_active')
        }),
    )


# =============================================================================
# WITHHOLDING TAX ADMIN
# =============================================================================

@admin.register(WithholdingTax)
class WithholdingTaxAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'withholding_type', 'rate',
        'threshold_amount', 'is_active'
    ]
    list_filter = ['withholding_type', 'is_active']
    search_fields = ['code', 'name', 'description']
    autocomplete_fields = ['account_payable']
    ordering = ['code']

    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'name', 'withholding_type', 'description')
        }),
        ('Paramètres', {
            'fields': ('rate', 'threshold_amount')
        }),
        ('Application', {
            'fields': ('applies_to_residents', 'applies_to_non_residents')
        }),
        ('Comptabilité', {
            'fields': ('account_payable',),
            'classes': ('collapse',)
        }),
        ('Validité', {
            'fields': ('valid_from', 'valid_to', 'is_active')
        }),
    )


# =============================================================================
# TAX DECLARATION ADMIN
# =============================================================================

class TaxDeclarationLineInline(admin.TabularInline):
    model = TaxDeclarationLine
    extra = 0
    fields = [
        'tax_rate', 'line_type', 'sequence',
        'base_amount', 'tax_amount', 'invoice_count'
    ]
    readonly_fields = ['invoice_count']
    autocomplete_fields = ['tax_rate']


@admin.register(TaxDeclaration)
class TaxDeclarationAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'tax_type', 'period_type',
        'period_start', 'period_end', 'due_date',
        'status', 'tax_due', 'credit_to_carry'
    ]
    list_filter = ['tax_type', 'period_type', 'status']
    search_fields = ['number', 'notes']
    readonly_fields = [
        'number', 'tax_collected', 'tax_deductible', 'tax_due', 'credit_to_carry',
        'calculated_at', 'validated_at', 'submitted_at'
    ]
    autocomplete_fields = ['tax_type', 'calculated_by', 'validated_by']
    inlines = [TaxDeclarationLineInline]
    date_hierarchy = 'period_start'
    ordering = ['-period_start']

    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'tax_type', 'period_type')
        }),
        ('Période', {
            'fields': ('period_start', 'period_end', 'due_date')
        }),
        ('Statut', {
            'fields': ('status',)
        }),
        ('Montants', {
            'fields': (
                'tax_collected', 'tax_deductible',
                'credit_carried_forward', 'tax_due', 'credit_to_carry'
            )
        }),
        ('Calcul et validation', {
            'fields': (
                'calculated_at', 'calculated_by',
                'validated_at', 'validated_by'
            ),
            'classes': ('collapse',)
        }),
        ('Soumission', {
            'fields': ('submitted_at', 'submission_reference'),
            'classes': ('collapse',)
        }),
        ('Paiement', {
            'fields': ('payment_date', 'payment_reference', 'payment_amount'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
