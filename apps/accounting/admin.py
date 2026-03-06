"""
Accounting admin.
"""
from django.contrib import admin
from .models import (
    AccountType, Account, Journal,
    JournalEntry, JournalEntryLine, AccountBalance
)


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_class', 'nature', 'is_debit_balance']
    list_filter = ['account_class', 'nature']
    search_fields = ['code', 'name']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'is_active', 'is_reconcilable']
    list_filter = ['account_type', 'is_active', 'is_reconcilable']
    search_fields = ['code', 'name']
    autocomplete_fields = ['account_type', 'parent', 'currency']


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'journal_type', 'is_active', 'next_sequence']
    list_filter = ['journal_type', 'is_active']
    search_fields = ['code', 'name']


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2
    fields = ['account', 'label', 'debit', 'credit', 'partner', 'reference']
    autocomplete_fields = ['account', 'partner']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'journal', 'date', 'description',
        'status', 'total_debit', 'total_credit'
    ]
    list_filter = ['status', 'journal', 'fiscal_period']
    search_fields = ['number', 'reference', 'description']
    readonly_fields = ['number', 'total_debit', 'total_credit', 'posted_by', 'posted_at']
    autocomplete_fields = ['journal', 'fiscal_year', 'fiscal_period']
    inlines = [JournalEntryLineInline]
    date_hierarchy = 'date'


@admin.register(AccountBalance)
class AccountBalanceAdmin(admin.ModelAdmin):
    list_display = [
        'account', 'fiscal_period',
        'opening_debit', 'opening_credit',
        'period_debit', 'period_credit',
        'closing_debit', 'closing_credit'
    ]
    list_filter = ['fiscal_period']
    search_fields = ['account__code', 'account__name']
    autocomplete_fields = ['account', 'fiscal_period']
