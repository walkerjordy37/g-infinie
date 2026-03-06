"""
Catalog admin configuration.
"""
from django.contrib import admin
from .models import (
    ProductCategory,
    UnitOfMeasure,
    UnitConversion,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    ProductSupplier,
    ProductImage,
)


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 1
    fields = ['code', 'name', 'sequence', 'color_code', 'is_active']


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ['code', 'name', 'barcode', 'purchase_price', 'sale_price', 'price_extra', 'is_active']
    readonly_fields = ['code', 'name']
    show_change_link = True


class ProductSupplierInline(admin.TabularInline):
    model = ProductSupplier
    extra = 1
    fields = ['supplier', 'supplier_code', 'purchase_price', 'min_quantity', 'lead_time_days', 'is_preferred']
    autocomplete_fields = ['supplier']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'name', 'sequence', 'is_primary']


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'parent', 'level', 'is_active', 'company', 'created_at']
    list_filter = ['company', 'is_active', 'level']
    search_fields = ['code', 'name']
    ordering = ['lft', 'name']
    readonly_fields = ['lft', 'rght', 'level', 'created_at', 'updated_at']

    fieldsets = (
        ('Informations générales', {
            'fields': ('company', 'code', 'name', 'description', 'parent', 'image', 'is_active')
        }),
        ('Arborescence', {
            'fields': ('lft', 'rght', 'level'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'type', 'ratio', 'is_reference', 'is_active', 'company']
    list_filter = ['company', 'type', 'is_reference', 'is_active']
    search_fields = ['code', 'name']
    ordering = ['type', 'name']


@admin.register(UnitConversion)
class UnitConversionAdmin(admin.ModelAdmin):
    list_display = ['from_unit', 'to_unit', 'factor', 'company', 'created_at']
    list_filter = ['company', 'from_unit__type']
    search_fields = ['from_unit__name', 'to_unit__name']
    autocomplete_fields = ['from_unit', 'to_unit']


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'display_type', 'is_active', 'company', 'created_at']
    list_filter = ['company', 'display_type', 'is_active']
    search_fields = ['code', 'name']
    ordering = ['name']
    inlines = [ProductAttributeValueInline]


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ['attribute', 'code', 'name', 'sequence', 'color_code', 'is_active']
    list_filter = ['attribute__company', 'attribute', 'is_active']
    search_fields = ['code', 'name', 'attribute__name']
    ordering = ['attribute', 'sequence', 'name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'type', 'category', 'unit', 'purchase_price',
        'sale_price', 'tax_rate', 'is_stockable', 'is_active', 'company'
    ]
    list_filter = [
        'company', 'type', 'category', 'is_stockable', 'is_purchasable',
        'is_saleable', 'is_active', 'valuation_method'
    ]
    search_fields = ['code', 'name', 'barcode', 'internal_reference', 'description']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['category', 'unit', 'purchase_unit', 'sale_unit']
    inlines = [ProductVariantInline, ProductSupplierInline, ProductImageInline]

    fieldsets = (
        ('Informations générales', {
            'fields': (
                'company', 'type', 'code', 'name', 'description',
                'category', 'image', 'is_active'
            )
        }),
        ('Unités', {
            'fields': ('unit', 'purchase_unit', 'sale_unit')
        }),
        ('Identification', {
            'fields': ('barcode', 'internal_reference')
        }),
        ('Prix', {
            'fields': ('purchase_price', 'sale_price', 'tax_rate')
        }),
        ('Stock', {
            'fields': ('is_stockable', 'min_stock', 'max_stock', 'valuation_method')
        }),
        ('Dimensions', {
            'fields': ('weight', 'volume'),
            'classes': ('collapse',)
        }),
        ('Options', {
            'fields': ('is_purchasable', 'is_saleable')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_products', 'deactivate_products', 'mark_stockable', 'mark_non_stockable']

    @admin.action(description="Activer les produits sélectionnés")
    def activate_products(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} produit(s) activé(s).")

    @admin.action(description="Désactiver les produits sélectionnés")
    def deactivate_products(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} produit(s) désactivé(s).")

    @admin.action(description="Marquer comme stockable")
    def mark_stockable(self, request, queryset):
        count = queryset.exclude(type=Product.TYPE_SERVICE).update(is_stockable=True)
        self.message_user(request, f"{count} produit(s) marqué(s) comme stockable(s).")

    @admin.action(description="Marquer comme non stockable")
    def mark_non_stockable(self, request, queryset):
        count = queryset.update(is_stockable=False)
        self.message_user(request, f"{count} produit(s) marqué(s) comme non stockable(s).")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'product', 'barcode', 'purchase_price',
        'sale_price', 'price_extra', 'is_active'
    ]
    list_filter = ['product__company', 'is_active', 'product__category']
    search_fields = ['code', 'name', 'barcode', 'product__name']
    ordering = ['product', 'name']
    autocomplete_fields = ['product']
    filter_horizontal = ['attribute_values']


@admin.register(ProductSupplier)
class ProductSupplierAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'supplier', 'supplier_code', 'purchase_price',
        'min_quantity', 'lead_time_days', 'is_preferred'
    ]
    list_filter = ['product__company', 'is_preferred', 'supplier']
    search_fields = ['product__name', 'supplier__name', 'supplier_code']
    ordering = ['product', '-is_preferred', 'supplier']
    autocomplete_fields = ['product', 'supplier']


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'name', 'sequence', 'is_primary', 'created_at']
    list_filter = ['product__company', 'is_primary']
    search_fields = ['product__name', 'name']
    ordering = ['product', '-is_primary', 'sequence']
    autocomplete_fields = ['product']
