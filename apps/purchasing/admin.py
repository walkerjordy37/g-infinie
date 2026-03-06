"""
Purchasing admin - Admin configuration for Purchase Requests and RFQs.
"""
from django.contrib import admin
from .models import (
    PurchaseRequest, PurchaseRequestLine,
    RequestForQuotation, RequestForQuotationLine, RFQComparison,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine,
    SupplierInvoice, SupplierInvoiceLine
)


class PurchaseRequestLineInline(admin.TabularInline):
    model = PurchaseRequestLine
    extra = 1
    fields = [
        'product', 'description', 'quantity', 'unit',
        'estimated_unit_price', 'estimated_total', 'preferred_supplier'
    ]
    readonly_fields = ['estimated_total']
    autocomplete_fields = ['product', 'unit', 'preferred_supplier']


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'date', 'requester', 'department',
        'status', 'priority', 'estimated_total'
    ]
    list_filter = ['status', 'priority', 'date', 'department']
    search_fields = ['number', 'requester__email', 'notes']
    readonly_fields = ['number', 'approved_by', 'approved_at', 'estimated_total']
    autocomplete_fields = ['requester']
    inlines = [PurchaseRequestLineInline]
    date_hierarchy = 'date'

    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'date', 'required_date', 'status', 'priority')
        }),
        ('Demandeur', {
            'fields': ('requester', 'department')
        }),
        ('Approbation', {
            'fields': ('approved_by', 'approved_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Totaux', {
            'fields': ('estimated_total',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


class RequestForQuotationLineInline(admin.TabularInline):
    model = RequestForQuotationLine
    extra = 1
    fields = [
        'product', 'description', 'quantity', 'unit',
        'quoted_unit_price', 'discount_percent', 'tax_rate',
        'subtotal', 'total', 'quoted_lead_time'
    ]
    readonly_fields = ['subtotal', 'total']
    autocomplete_fields = ['product', 'unit']


@admin.register(RequestForQuotation)
class RequestForQuotationAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'supplier', 'date', 'deadline',
        'status', 'total', 'buyer'
    ]
    list_filter = ['status', 'date', 'supplier']
    search_fields = ['number', 'supplier__name', 'notes']
    readonly_fields = ['number', 'subtotal', 'tax_total', 'discount_total', 'total']
    autocomplete_fields = ['supplier', 'currency', 'buyer', 'purchase_request']
    inlines = [RequestForQuotationLineInline]
    date_hierarchy = 'date'

    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'purchase_request', 'supplier', 'buyer')
        }),
        ('Dates', {
            'fields': ('date', 'deadline', 'response_date', 'validity_date')
        }),
        ('Statut et conditions', {
            'fields': ('status', 'delivery_lead_time', 'payment_terms')
        }),
        ('Devise', {
            'fields': ('currency', 'exchange_rate')
        }),
        ('Totaux', {
            'fields': ('subtotal', 'discount_total', 'tax_total', 'total')
        }),
        ('Notes', {
            'fields': ('notes', 'supplier_notes'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RFQComparison)
class RFQComparisonAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_request', 'comparison_date', 'selected_rfq', 'compared_by'
    ]
    list_filter = ['comparison_date']
    search_fields = ['purchase_request__number', 'selection_reason']
    autocomplete_fields = ['purchase_request', 'selected_rfq', 'compared_by']
    filter_horizontal = ['rfqs']


# =============================================================================
# PURCHASE ORDER ADMIN
# =============================================================================

class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1
    fields = [
        'product', 'description', 'quantity', 'quantity_received', 'quantity_invoiced',
        'unit', 'unit_price', 'discount_percent', 'tax_rate', 'subtotal', 'total'
    ]
    readonly_fields = ['quantity_received', 'quantity_invoiced', 'subtotal', 'total']
    autocomplete_fields = ['product', 'unit']


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'supplier', 'date', 'expected_delivery_date',
        'status', 'total', 'buyer'
    ]
    list_filter = ['status', 'date', 'supplier']
    search_fields = ['number', 'supplier__name', 'supplier_reference', 'notes']
    readonly_fields = ['number', 'subtotal', 'tax_total', 'discount_total', 'total']
    autocomplete_fields = ['supplier', 'currency', 'buyer', 'warehouse', 'rfq', 'purchase_request']
    inlines = [PurchaseOrderLineInline]
    date_hierarchy = 'date'

    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'rfq', 'purchase_request', 'supplier', 'buyer')
        }),
        ('Dates', {
            'fields': ('date', 'expected_delivery_date')
        }),
        ('Statut et conditions', {
            'fields': ('status', 'payment_terms', 'incoterm', 'supplier_reference')
        }),
        ('Livraison', {
            'fields': ('warehouse', 'delivery_address')
        }),
        ('Devise', {
            'fields': ('currency', 'exchange_rate')
        }),
        ('Totaux', {
            'fields': ('subtotal', 'discount_total', 'tax_total', 'total')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# GOODS RECEIPT ADMIN
# =============================================================================

class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 1
    fields = [
        'product', 'quantity_expected', 'quantity_received', 'quantity_rejected',
        'unit', 'lot_number', 'expiry_date', 'location', 'rejection_reason'
    ]
    autocomplete_fields = ['product', 'unit']


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'purchase_order', 'supplier', 'date', 'status', 'received_by'
    ]
    list_filter = ['status', 'date', 'warehouse']
    search_fields = ['number', 'delivery_note_number', 'tracking_number']
    readonly_fields = ['number', 'validated_at']
    autocomplete_fields = ['purchase_order', 'supplier', 'warehouse', 'received_by']
    inlines = [GoodsReceiptLineInline]
    date_hierarchy = 'date'

    fieldsets = (
        ('Informations générales', {
            'fields': ('number', 'purchase_order', 'supplier', 'date', 'status')
        }),
        ('Livraison', {
            'fields': ('delivery_note_number', 'carrier', 'tracking_number', 'warehouse')
        }),
        ('Validation', {
            'fields': ('received_by', 'validated_at')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# SUPPLIER INVOICE ADMIN
# =============================================================================

class SupplierInvoiceLineInline(admin.TabularInline):
    model = SupplierInvoiceLine
    extra = 1
    fields = [
        'product', 'description', 'quantity', 'unit_price',
        'discount_percent', 'tax_rate', 'subtotal', 'total', 'three_way_match_status'
    ]
    readonly_fields = ['subtotal', 'total']
    autocomplete_fields = ['product']


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'supplier_invoice_number', 'supplier', 'invoice_type',
        'date', 'due_date', 'status', 'total', 'amount_due', 'three_way_match_status'
    ]
    list_filter = ['status', 'invoice_type', 'three_way_match_status', 'date']
    search_fields = ['number', 'supplier_invoice_number', 'supplier__name']
    readonly_fields = [
        'number', 'subtotal', 'tax_total', 'discount_total', 'total',
        'amount_due', 'validated_at'
    ]
    autocomplete_fields = ['purchase_order', 'supplier', 'currency', 'validated_by']
    inlines = [SupplierInvoiceLineInline]
    date_hierarchy = 'date'

    fieldsets = (
        ('Informations générales', {
            'fields': (
                'number', 'supplier_invoice_number', 'invoice_type',
                'purchase_order', 'supplier'
            )
        }),
        ('Dates', {
            'fields': ('date', 'due_date', 'received_date')
        }),
        ('Statut', {
            'fields': ('status', 'payment_terms', 'payment_reference')
        }),
        ('Devise', {
            'fields': ('currency', 'exchange_rate')
        }),
        ('Totaux', {
            'fields': ('subtotal', 'discount_total', 'tax_total', 'total')
        }),
        ('Paiement', {
            'fields': ('amount_paid', 'amount_due')
        }),
        ('Rapprochement', {
            'fields': ('three_way_match_status', 'three_way_match_notes'),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('validated_by', 'validated_at', 'accounting_date', 'journal_entry'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
