"""
Partners admin configuration.
"""
from django.contrib import admin
from .models import PartnerCategory, Partner, PartnerContact, PartnerAddress, PartnerBankAccount


class PartnerContactInline(admin.TabularInline):
    model = PartnerContact
    extra = 1
    fields = ['name', 'title', 'phone', 'mobile', 'email', 'is_primary']


class PartnerAddressInline(admin.TabularInline):
    model = PartnerAddress
    extra = 1
    fields = ['type', 'name', 'street', 'city', 'country', 'is_default']


class PartnerBankAccountInline(admin.TabularInline):
    model = PartnerBankAccount
    extra = 1
    fields = ['bank_name', 'account_number', 'iban', 'swift_bic', 'is_default']


@admin.register(PartnerCategory)
class PartnerCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'parent', 'company', 'created_at']
    list_filter = ['company']
    search_fields = ['code', 'name']
    ordering = ['name']


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'type', 'category', 'city', 'phone', 'email',
        'credit_limit', 'is_active', 'company'
    ]
    list_filter = ['type', 'category', 'is_active', 'company', 'country']
    search_fields = ['code', 'name', 'legal_name', 'tax_id', 'email', 'phone']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PartnerContactInline, PartnerAddressInline, PartnerBankAccountInline]

    fieldsets = (
        ('Informations générales', {
            'fields': ('company', 'type', 'code', 'name', 'legal_name', 'category', 'is_active')
        }),
        ('Informations légales', {
            'fields': ('tax_id', 'trade_register')
        }),
        ('Adresse principale', {
            'fields': ('street', 'street2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Contacts', {
            'fields': ('phone', 'mobile', 'fax', 'email', 'website')
        }),
        ('Conditions commerciales', {
            'fields': ('credit_limit', 'payment_terms_days', 'discount_rate', 'currency')
        }),
        ('Comptabilité', {
            'fields': ('customer_accounting_code', 'supplier_accounting_code')
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

    actions = ['activate_partners', 'deactivate_partners']

    @admin.action(description="Activer les partenaires sélectionnés")
    def activate_partners(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} partenaire(s) activé(s).")

    @admin.action(description="Désactiver les partenaires sélectionnés")
    def deactivate_partners(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} partenaire(s) désactivé(s).")


@admin.register(PartnerContact)
class PartnerContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'partner', 'title', 'phone', 'email', 'is_primary']
    list_filter = ['is_primary', 'partner__company']
    search_fields = ['name', 'email', 'partner__name']
    ordering = ['partner', '-is_primary', 'name']


@admin.register(PartnerAddress)
class PartnerAddressAdmin(admin.ModelAdmin):
    list_display = ['partner', 'type', 'name', 'city', 'country', 'is_default']
    list_filter = ['type', 'is_default', 'country', 'partner__company']
    search_fields = ['name', 'city', 'partner__name']
    ordering = ['partner', '-is_default', 'name']


@admin.register(PartnerBankAccount)
class PartnerBankAccountAdmin(admin.ModelAdmin):
    list_display = ['partner', 'bank_name', 'account_number', 'iban', 'is_default']
    list_filter = ['is_default', 'bank_name', 'partner__company']
    search_fields = ['bank_name', 'account_number', 'iban', 'partner__name']
    ordering = ['partner', '-is_default', 'bank_name']
