"""
Treasury admin configuration.
"""
from django.contrib import admin
from .models import (
    BankAccount, CashRegister,
    BankStatement, BankStatementLine, BankReconciliation,
    CashMovement, Transfer,
)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'bank_name', 'type', 'current_balance',
        'currency', 'is_active', 'is_default'
    ]
    list_filter = ['type', 'is_active', 'is_default', 'bank_name']
    search_fields = ['code', 'name', 'bank_name', 'account_number', 'iban']
    readonly_fields = [
        'current_balance', 'last_statement_balance', 'last_statement_date',
        'created_at', 'updated_at'
    ]
    autocomplete_fields = ['currency']
    fieldsets = (
        ('Identification', {
            'fields': ('code', 'name', 'type')
        }),
        ('Coordonnées bancaires', {
            'fields': (
                'bank_name', 'bank_code', 'branch_code',
                'account_number', 'rib_key', 'iban', 'bic'
            )
        }),
        ('Soldes', {
            'fields': (
                'currency', 'initial_balance', 'current_balance',
                'last_statement_balance', 'last_statement_date'
            )
        }),
        ('Paramètres', {
            'fields': (
                'accounting_code', 'is_active', 'is_default',
                'allow_overdraft', 'overdraft_limit'
            )
        }),
        ('Notes', {
            'fields': ('notes', 'company'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'branch', 'current_balance',
        'currency', 'responsible', 'is_active'
    ]
    list_filter = ['is_active', 'branch']
    search_fields = ['code', 'name']
    readonly_fields = ['current_balance', 'created_at', 'updated_at']
    autocomplete_fields = ['currency', 'branch', 'responsible']
    fieldsets = (
        ('Identification', {
            'fields': ('code', 'name', 'branch')
        }),
        ('Soldes', {
            'fields': ('currency', 'initial_balance', 'current_balance', 'max_balance')
        }),
        ('Paramètres', {
            'fields': ('accounting_code', 'responsible', 'is_active')
        }),
        ('Notes', {
            'fields': ('notes', 'company'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class BankStatementLineInline(admin.TabularInline):
    model = BankStatementLine
    extra = 0
    fields = [
        'sequence', 'date', 'reference', 'description',
        'type', 'amount', 'is_reconciled'
    ]
    readonly_fields = ['is_reconciled']
    ordering = ['sequence']


@admin.register(BankStatement)
class BankStatementAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'bank_account', 'date', 'start_date', 'end_date',
        'opening_balance', 'closing_balance', 'status', 'line_count'
    ]
    list_filter = ['status', 'bank_account', 'date']
    search_fields = ['reference', 'bank_account__name']
    readonly_fields = [
        'total_debits', 'total_credits', 'imported_at', 'imported_by',
        'line_count', 'reconciled_count', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    inlines = [BankStatementLineInline]
    autocomplete_fields = ['bank_account']
    fieldsets = (
        ('Informations', {
            'fields': ('bank_account', 'reference', 'date', 'start_date', 'end_date', 'status')
        }),
        ('Soldes', {
            'fields': ('opening_balance', 'closing_balance', 'total_debits', 'total_credits')
        }),
        ('Import', {
            'fields': ('import_format', 'import_file', 'imported_at', 'imported_by')
        }),
        ('Statistiques', {
            'fields': ('line_count', 'reconciled_count')
        }),
        ('Notes', {
            'fields': ('notes', 'company'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BankStatementLine)
class BankStatementLineAdmin(admin.ModelAdmin):
    list_display = [
        'statement', 'date', 'reference', 'description',
        'type', 'amount', 'is_reconciled'
    ]
    list_filter = ['type', 'is_reconciled', 'statement__bank_account']
    search_fields = ['reference', 'description', 'partner_name']
    readonly_fields = ['is_reconciled', 'reconciled_at', 'reconciled_by', 'created_at', 'updated_at']
    date_hierarchy = 'date'
    autocomplete_fields = ['statement', 'partner']


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = [
        'statement_line', 'payment', 'journal_entry',
        'amount', 'reconciled_at', 'reconciled_by'
    ]
    list_filter = ['reconciled_at']
    search_fields = [
        'statement_line__description', 'payment__number', 'journal_entry__number'
    ]
    readonly_fields = ['reconciled_at', 'reconciled_by', 'created_at', 'updated_at']
    autocomplete_fields = ['statement_line', 'payment', 'journal_entry']


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'cash_register', 'date', 'type', 'reason',
        'amount', 'balance_after', 'is_validated'
    ]
    list_filter = ['type', 'reason', 'is_validated', 'cash_register']
    search_fields = ['number', 'description', 'reference']
    readonly_fields = [
        'number', 'balance_before', 'balance_after',
        'validated_at', 'validated_by', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    autocomplete_fields = ['cash_register', 'partner', 'payment', 'performed_by']
    fieldsets = (
        ('Informations', {
            'fields': ('number', 'cash_register', 'date', 'type', 'reason')
        }),
        ('Montants', {
            'fields': ('amount', 'balance_before', 'balance_after')
        }),
        ('Détails', {
            'fields': ('description', 'reference', 'partner', 'payment', 'performed_by')
        }),
        ('Validation', {
            'fields': ('is_validated', 'validated_at', 'validated_by')
        }),
        ('Notes', {
            'fields': ('notes', 'company'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'date', 'source_label', 'destination_label',
        'amount', 'fees', 'status'
    ]
    list_filter = ['status', 'date']
    search_fields = ['number', 'reference', 'description']
    readonly_fields = [
        'number', 'source_label', 'destination_label',
        'executed_at', 'executed_by', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    autocomplete_fields = [
        'from_bank_account', 'from_cash_register',
        'to_bank_account', 'to_cash_register', 'currency'
    ]
    fieldsets = (
        ('Informations', {
            'fields': ('number', 'date', 'status')
        }),
        ('Source', {
            'fields': ('from_bank_account', 'from_cash_register', 'source_label')
        }),
        ('Destination', {
            'fields': ('to_bank_account', 'to_cash_register', 'destination_label')
        }),
        ('Montants', {
            'fields': ('amount', 'fees', 'currency', 'exchange_rate')
        }),
        ('Détails', {
            'fields': ('description', 'reference')
        }),
        ('Exécution', {
            'fields': ('executed_at', 'executed_by', 'journal_entry')
        }),
        ('Notes', {
            'fields': ('notes', 'company'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
