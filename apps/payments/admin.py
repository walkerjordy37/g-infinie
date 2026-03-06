"""
Payments admin configuration.
"""
from django.contrib import admin
from .models import PaymentMethod, PaymentTerm, Payment, PaymentAllocation, Refund


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'type', 'is_active', 'bank_account', 'requires_reference']
    list_filter = ['type', 'is_active', 'requires_reference']
    search_fields = ['code', 'name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['bank_account', 'journal']
    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'name', 'type', 'is_active')
        }),
        ('Comptabilité', {
            'fields': ('bank_account', 'journal')
        }),
        ('Options', {
            'fields': ('requires_reference', 'notes')
        }),
        ('Entreprise', {
            'fields': ('company',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'days', 'is_immediate', 'discount_percent', 'is_active', 'is_default']
    list_filter = ['is_active', 'is_default', 'is_immediate']
    search_fields = ['code', 'name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'name', 'description')
        }),
        ('Conditions', {
            'fields': ('days', 'is_immediate')
        }),
        ('Escompte', {
            'fields': ('discount_percent', 'discount_days')
        }),
        ('Statut', {
            'fields': ('is_active', 'is_default')
        }),
        ('Entreprise', {
            'fields': ('company',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    fields = ['sales_invoice', 'supplier_invoice', 'amount', 'allocation_date', 'notes']
    readonly_fields = ['allocation_date']
    autocomplete_fields = ['sales_invoice', 'supplier_invoice']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'payment_type', 'partner', 'date', 'status',
        'payment_method', 'amount', 'amount_allocated', 'amount_unallocated'
    ]
    list_filter = ['payment_type', 'status', 'payment_method', 'date']
    search_fields = ['number', 'partner__name', 'partner__code', 'reference']
    readonly_fields = [
        'number', 'amount_allocated', 'amount_unallocated',
        'confirmed_by', 'confirmed_at', 'journal_entry',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    inlines = [PaymentAllocationInline]
    autocomplete_fields = ['partner', 'payment_method', 'currency', 'bank_account']
    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'payment_type', 'partner', 'date', 'value_date', 'status')
        }),
        ('Paiement', {
            'fields': ('payment_method', 'currency', 'exchange_rate', 'amount', 'reference', 'memo')
        }),
        ('Allocation', {
            'fields': ('amount_allocated', 'amount_unallocated')
        }),
        ('Banque', {
            'fields': ('bank_account',)
        }),
        ('Confirmation', {
            'fields': ('confirmed_by', 'confirmed_at')
        }),
        ('Comptabilité', {
            'fields': ('journal_entry',)
        }),
        ('Entreprise', {
            'fields': ('company',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ['payment', 'sales_invoice', 'supplier_invoice', 'amount', 'allocation_date']
    list_filter = ['allocation_date']
    search_fields = [
        'payment__number', 'sales_invoice__number', 'supplier_invoice__number'
    ]
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['payment', 'sales_invoice', 'supplier_invoice']
    fieldsets = (
        ('Paiement', {
            'fields': ('payment',)
        }),
        ('Facture', {
            'fields': ('sales_invoice', 'supplier_invoice')
        }),
        ('Allocation', {
            'fields': ('amount', 'allocation_date', 'notes')
        }),
        ('Entreprise', {
            'fields': ('company',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'refund_type', 'partner', 'date', 'status',
        'reason', 'payment_method', 'amount'
    ]
    list_filter = ['refund_type', 'status', 'reason', 'payment_method', 'date']
    search_fields = ['number', 'partner__name', 'partner__code', 'reference']
    readonly_fields = [
        'number', 'paid_by', 'paid_at', 'journal_entry',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    autocomplete_fields = [
        'partner', 'payment_method', 'currency', 'bank_account',
        'original_payment', 'credit_note'
    ]
    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'refund_type', 'partner', 'date', 'status')
        }),
        ('Motif', {
            'fields': ('reason', 'reason_details')
        }),
        ('Paiement', {
            'fields': ('payment_method', 'currency', 'exchange_rate', 'amount', 'reference')
        }),
        ('Origine', {
            'fields': ('original_payment', 'credit_note')
        }),
        ('Banque', {
            'fields': ('bank_account',)
        }),
        ('Paiement effectif', {
            'fields': ('paid_by', 'paid_at')
        }),
        ('Comptabilité', {
            'fields': ('journal_entry',)
        }),
        ('Autres', {
            'fields': ('notes', 'company')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
