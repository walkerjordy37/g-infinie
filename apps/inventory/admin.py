"""
Inventory admin configuration.
"""
from django.contrib import admin
from .models import (
    Warehouse, WarehouseLocation, StockLevel, StockMovement,
    StockAdjustment, StockAdjustmentLine, LotSerial
)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'address_city', 'manager', 'is_active', 'company']
    list_filter = ['is_active', 'company', 'address_country']
    search_fields = ['code', 'name', 'address_city']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        (None, {
            'fields': ('company', 'code', 'name', 'is_active')
        }),
        ('Adresse', {
            'fields': (
                'address_street', 'address_street2',
                'address_postal_code', 'address_city', 'address_country'
            )
        }),
        ('Contact', {
            'fields': ('phone', 'email', 'manager')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WarehouseLocation)
class WarehouseLocationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'warehouse', 'parent', 'is_active']
    list_filter = ['warehouse', 'is_active']
    search_fields = ['code', 'name', 'warehouse__name']
    ordering = ['warehouse', 'code']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['warehouse', 'parent']


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'warehouse', 'location',
        'quantity_on_hand', 'quantity_reserved', 'quantity_available',
        'unit_cost', 'last_movement_date'
    ]
    list_filter = ['warehouse', 'company']
    search_fields = ['product__code', 'product__name', 'warehouse__name']
    ordering = ['product', 'warehouse']
    readonly_fields = [
        'quantity_available', 'valuation',
        'created_at', 'updated_at', 'last_movement_date'
    ]
    autocomplete_fields = ['product', 'warehouse', 'location']

    def quantity_available(self, obj):
        return obj.quantity_available
    quantity_available.short_description = "Disponible"


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'type', 'source', 'product', 'warehouse',
        'quantity', 'unit_cost', 'reference', 'created_by'
    ]
    list_filter = ['type', 'source', 'warehouse', 'date']
    search_fields = ['product__code', 'product__name', 'reference', 'notes']
    ordering = ['-date', '-created_at']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    autocomplete_fields = ['product', 'warehouse', 'source_warehouse', 'location']
    date_hierarchy = 'date'

    fieldsets = (
        (None, {
            'fields': ('company', 'type', 'source', 'date')
        }),
        ('Produit et Emplacement', {
            'fields': ('product', 'warehouse', 'source_warehouse', 'location')
        }),
        ('Quantité et Valeur', {
            'fields': ('quantity', 'unit_cost')
        }),
        ('Référence', {
            'fields': ('reference', 'reference_type', 'reference_id', 'lot_serial')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Métadonnées', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class StockAdjustmentLineInline(admin.TabularInline):
    model = StockAdjustmentLine
    extra = 1
    readonly_fields = ['difference', 'difference_value']
    autocomplete_fields = ['product', 'location']

    def difference(self, obj):
        return obj.difference
    difference.short_description = "Différence"

    def difference_value(self, obj):
        return obj.difference_value
    difference_value.short_description = "Valeur différence"


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'warehouse', 'adjustment_type', 'status',
        'date', 'total_difference', 'confirmed_by', 'confirmed_at'
    ]
    list_filter = ['status', 'adjustment_type', 'warehouse', 'date']
    search_fields = ['reference', 'notes', 'warehouse__name']
    ordering = ['-date', '-created_at']
    readonly_fields = [
        'total_difference', 'confirmed_by', 'confirmed_at',
        'created_at', 'updated_at'
    ]
    inlines = [StockAdjustmentLineInline]
    date_hierarchy = 'date'

    fieldsets = (
        (None, {
            'fields': ('company', 'reference', 'warehouse', 'adjustment_type', 'status')
        }),
        ('Date et Notes', {
            'fields': ('date', 'notes')
        }),
        ('Confirmation', {
            'fields': ('confirmed_by', 'confirmed_at'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def total_difference(self, obj):
        return obj.total_difference
    total_difference.short_description = "Total différence"


@admin.register(StockAdjustmentLine)
class StockAdjustmentLineAdmin(admin.ModelAdmin):
    list_display = [
        'adjustment', 'product', 'location',
        'system_quantity', 'counted_quantity', 'difference', 'unit_cost'
    ]
    list_filter = ['adjustment__warehouse', 'adjustment__status']
    search_fields = ['product__code', 'product__name', 'adjustment__reference']
    ordering = ['adjustment', 'product__code']
    readonly_fields = ['difference', 'difference_value', 'created_at', 'updated_at']
    autocomplete_fields = ['adjustment', 'product', 'location']

    def difference(self, obj):
        return obj.difference
    difference.short_description = "Différence"


@admin.register(LotSerial)
class LotSerialAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'lot_number', 'serial_number', 'warehouse',
        'quantity', 'expiry_date', 'is_expired', 'unit_cost'
    ]
    list_filter = ['warehouse', 'expiry_date']
    search_fields = ['lot_number', 'serial_number', 'product__code', 'product__name']
    ordering = ['expiry_date', '-created_at']
    readonly_fields = ['is_expired', 'created_at', 'updated_at']
    autocomplete_fields = ['product', 'warehouse', 'location']
    date_hierarchy = 'expiry_date'

    fieldsets = (
        (None, {
            'fields': ('company', 'product', 'warehouse', 'location')
        }),
        ('Identification', {
            'fields': ('lot_number', 'serial_number')
        }),
        ('Dates', {
            'fields': ('manufacturing_date', 'expiry_date', 'is_expired')
        }),
        ('Quantité et Valeur', {
            'fields': ('quantity', 'unit_cost')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_expired(self, obj):
        return obj.is_expired
    is_expired.short_description = "Expiré"
    is_expired.boolean = True
