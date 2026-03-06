"""
Sales admin configuration.
"""
from django.contrib import admin
from .models import (
    SalesQuote, SalesQuoteLine,
    SalesOrder, SalesOrderLine,
    DeliveryNote, DeliveryNoteLine,
    SalesInvoice, SalesInvoiceLine,
    SalesReturn, SalesReturnLine,
)


class SalesQuoteLineInline(admin.TabularInline):
    model = SalesQuoteLine
    extra = 1
    fields = [
        'product', 'description', 'quantity', 'unit_price',
        'discount_percent', 'tax_rate', 'subtotal', 'total'
    ]
    readonly_fields = ['subtotal', 'total']
    autocomplete_fields = ['product']


@admin.register(SalesQuote)
class SalesQuoteAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'partner', 'date', 'validity_date',
        'status', 'total', 'salesperson'
    ]
    list_filter = ['status', 'date', 'salesperson']
    search_fields = ['number', 'partner__name', 'partner__code']
    readonly_fields = [
        'number', 'subtotal', 'tax_total', 'discount_total', 'total',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    inlines = [SalesQuoteLineInline]
    autocomplete_fields = ['partner', 'currency', 'salesperson']
    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'partner', 'date', 'validity_date', 'status')
        }),
        ('Devise', {
            'fields': ('currency', 'exchange_rate')
        }),
        ('Totaux', {
            'fields': ('subtotal', 'tax_total', 'discount_total', 'total')
        }),
        ('Autres', {
            'fields': ('notes', 'terms', 'salesperson', 'company')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1
    fields = [
        'product', 'description', 'quantity', 'quantity_delivered',
        'quantity_invoiced', 'unit_price', 'discount_percent', 'tax_rate',
        'subtotal', 'total'
    ]
    readonly_fields = ['quantity_delivered', 'quantity_invoiced', 'subtotal', 'total']
    autocomplete_fields = ['product']


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'partner', 'date', 'expected_delivery_date',
        'status', 'total', 'warehouse'
    ]
    list_filter = ['status', 'date', 'warehouse', 'salesperson']
    search_fields = ['number', 'partner__name', 'partner__code', 'quote__number']
    readonly_fields = [
        'number', 'subtotal', 'tax_total', 'discount_total', 'total',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    inlines = [SalesOrderLineInline]
    autocomplete_fields = ['partner', 'currency', 'salesperson', 'warehouse', 'quote']
    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'quote', 'partner', 'date', 'expected_delivery_date', 'status')
        }),
        ('Devise', {
            'fields': ('currency', 'exchange_rate')
        }),
        ('Totaux', {
            'fields': ('subtotal', 'tax_total', 'discount_total', 'total')
        }),
        ('Logistique', {
            'fields': ('warehouse',)
        }),
        ('Autres', {
            'fields': ('notes', 'terms', 'salesperson', 'company')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class DeliveryNoteLineInline(admin.TabularInline):
    model = DeliveryNoteLine
    extra = 1
    fields = ['product', 'order_line', 'quantity_ordered', 'quantity_delivered']
    autocomplete_fields = ['product']


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'order', 'partner', 'date', 'status',
        'carrier', 'tracking_number'
    ]
    list_filter = ['status', 'date', 'carrier']
    search_fields = ['number', 'partner__name', 'order__number', 'tracking_number']
    readonly_fields = ['number', 'shipped_at', 'delivered_at', 'created_at', 'updated_at']
    date_hierarchy = 'date'
    inlines = [DeliveryNoteLineInline]
    autocomplete_fields = ['partner', 'order', 'shipped_by']
    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'order', 'partner', 'date', 'status')
        }),
        ('Expédition', {
            'fields': ('shipping_address', 'carrier', 'tracking_number')
        }),
        ('Suivi', {
            'fields': ('shipped_by', 'shipped_at', 'delivered_at')
        }),
        ('Autres', {
            'fields': ('notes', 'company')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class SalesInvoiceLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 1
    fields = [
        'product', 'description', 'quantity', 'unit_price',
        'discount_percent', 'tax_rate', 'subtotal', 'total'
    ]
    readonly_fields = ['subtotal', 'total']
    autocomplete_fields = ['product']


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'partner', 'date', 'due_date',
        'status', 'total', 'amount_paid', 'amount_due', 'is_posted'
    ]
    list_filter = ['status', 'is_posted', 'date']
    search_fields = ['number', 'partner__name', 'partner__code', 'order__number']
    readonly_fields = [
        'number', 'subtotal', 'tax_total', 'discount_total', 'total',
        'amount_paid', 'amount_due', 'is_posted', 'posted_at',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    inlines = [SalesInvoiceLineInline]
    autocomplete_fields = ['partner', 'currency', 'order', 'delivery_note']
    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'order', 'delivery_note', 'partner', 'date', 'due_date', 'status')
        }),
        ('Devise', {
            'fields': ('currency', 'exchange_rate')
        }),
        ('Totaux', {
            'fields': ('subtotal', 'tax_total', 'discount_total', 'total')
        }),
        ('Paiement', {
            'fields': ('amount_paid', 'amount_due')
        }),
        ('Comptabilité', {
            'fields': ('is_posted', 'posted_at', 'journal_entry')
        }),
        ('Autres', {
            'fields': ('notes', 'terms', 'company')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class SalesReturnLineInline(admin.TabularInline):
    model = SalesReturnLine
    extra = 1
    fields = ['product', 'invoice_line', 'quantity', 'unit_price', 'tax_rate', 'subtotal', 'total']
    readonly_fields = ['subtotal', 'total']
    autocomplete_fields = ['product']


@admin.register(SalesReturn)
class SalesReturnAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'invoice', 'partner', 'date', 'status', 'reason', 'total'
    ]
    list_filter = ['status', 'reason', 'date']
    search_fields = ['number', 'partner__name', 'invoice__number']
    readonly_fields = [
        'number', 'subtotal', 'tax_total', 'total',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'date'
    inlines = [SalesReturnLineInline]
    autocomplete_fields = ['partner', 'invoice', 'credit_note']
    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'invoice', 'partner', 'date', 'status')
        }),
        ('Motif', {
            'fields': ('reason', 'reason_details')
        }),
        ('Totaux', {
            'fields': ('subtotal', 'tax_total', 'total')
        }),
        ('Avoir', {
            'fields': ('credit_note',)
        }),
        ('Autres', {
            'fields': ('notes', 'company')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
