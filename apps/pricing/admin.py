"""
Pricing admin configuration.
"""
from django.contrib import admin
from .models import (
    PriceList,
    PriceListItem,
    CustomerPriceRule,
    VolumeDiscount,
    Promotion,
    PromotionProduct,
)


class PriceListItemInline(admin.TabularInline):
    model = PriceListItem
    extra = 1
    fields = ['product', 'min_quantity', 'unit_price']
    autocomplete_fields = ['product']


class PromotionProductInline(admin.TabularInline):
    model = PromotionProduct
    extra = 1
    fields = ['product']
    autocomplete_fields = ['product']


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'currency', 'is_default', 'is_active',
        'valid_from', 'valid_to', 'company', 'created_at'
    ]
    list_filter = ['company', 'is_default', 'is_active', 'currency']
    search_fields = ['code', 'name']
    ordering = ['-is_default', 'name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['currency']
    inlines = [PriceListItemInline]

    fieldsets = (
        ('Informations générales', {
            'fields': ('company', 'code', 'name', 'description', 'currency')
        }),
        ('Statut', {
            'fields': ('is_default', 'is_active')
        }),
        ('Validité', {
            'fields': ('valid_from', 'valid_to')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_lists', 'deactivate_lists']

    @admin.action(description="Activer les listes de prix sélectionnées")
    def activate_lists(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} liste(s) de prix activée(s).")

    @admin.action(description="Désactiver les listes de prix sélectionnées")
    def deactivate_lists(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} liste(s) de prix désactivée(s).")


@admin.register(PriceListItem)
class PriceListItemAdmin(admin.ModelAdmin):
    list_display = [
        'price_list', 'product', 'min_quantity', 'unit_price', 'created_at'
    ]
    list_filter = ['price_list__company', 'price_list']
    search_fields = ['product__code', 'product__name', 'price_list__name']
    ordering = ['price_list', 'product', 'min_quantity']
    autocomplete_fields = ['price_list', 'product']


@admin.register(CustomerPriceRule)
class CustomerPriceRuleAdmin(admin.ModelAdmin):
    list_display = [
        'partner', 'product', 'category', 'discount_type', 'discount_value',
        'priority', 'is_active', 'valid_from', 'valid_to', 'company'
    ]
    list_filter = ['company', 'discount_type', 'is_active', 'partner']
    search_fields = ['partner__name', 'product__name', 'category__name']
    ordering = ['partner', 'priority']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['partner', 'product', 'category']

    fieldsets = (
        ('Cible', {
            'fields': ('company', 'partner', 'product', 'category')
        }),
        ('Remise', {
            'fields': ('discount_type', 'discount_value', 'priority')
        }),
        ('Validité', {
            'fields': ('valid_from', 'valid_to', 'is_active')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_rules', 'deactivate_rules']

    @admin.action(description="Activer les règles sélectionnées")
    def activate_rules(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} règle(s) activée(s).")

    @admin.action(description="Désactiver les règles sélectionnées")
    def deactivate_rules(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} règle(s) désactivée(s).")


@admin.register(VolumeDiscount)
class VolumeDiscountAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'min_quantity', 'max_quantity', 'discount_type',
        'discount_value', 'is_active', 'company'
    ]
    list_filter = ['company', 'discount_type', 'is_active']
    search_fields = ['product__code', 'product__name']
    ordering = ['product', 'min_quantity']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['product']

    fieldsets = (
        ('Produit', {
            'fields': ('company', 'product')
        }),
        ('Quantités', {
            'fields': ('min_quantity', 'max_quantity')
        }),
        ('Remise', {
            'fields': ('discount_type', 'discount_value')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_discounts', 'deactivate_discounts']

    @admin.action(description="Activer les remises sélectionnées")
    def activate_discounts(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} remise(s) activée(s).")

    @admin.action(description="Désactiver les remises sélectionnées")
    def deactivate_discounts(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} remise(s) désactivée(s).")


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'type', 'value', 'valid_from', 'valid_to',
        'max_uses', 'current_uses', 'is_active', 'company'
    ]
    list_filter = ['company', 'type', 'is_active']
    search_fields = ['code', 'name', 'description']
    ordering = ['-valid_from', 'name']
    readonly_fields = ['current_uses', 'created_at', 'updated_at']
    inlines = [PromotionProductInline]

    fieldsets = (
        ('Informations générales', {
            'fields': ('company', 'code', 'name', 'description')
        }),
        ('Type et valeur', {
            'fields': ('type', 'value', 'buy_quantity', 'get_quantity')
        }),
        ('Validité', {
            'fields': ('valid_from', 'valid_to', 'is_active')
        }),
        ('Conditions', {
            'fields': ('min_purchase_amount',)
        }),
        ('Utilisation', {
            'fields': ('max_uses', 'current_uses')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_promotions', 'deactivate_promotions', 'reset_usage']

    @admin.action(description="Activer les promotions sélectionnées")
    def activate_promotions(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} promotion(s) activée(s).")

    @admin.action(description="Désactiver les promotions sélectionnées")
    def deactivate_promotions(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} promotion(s) désactivée(s).")

    @admin.action(description="Réinitialiser le compteur d'utilisation")
    def reset_usage(self, request, queryset):
        count = queryset.update(current_uses=0)
        self.message_user(request, f"Compteur réinitialisé pour {count} promotion(s).")


@admin.register(PromotionProduct)
class PromotionProductAdmin(admin.ModelAdmin):
    list_display = ['promotion', 'product', 'created_at']
    list_filter = ['promotion__company', 'promotion']
    search_fields = ['promotion__code', 'product__name']
    ordering = ['promotion', 'product']
    autocomplete_fields = ['promotion', 'product']
