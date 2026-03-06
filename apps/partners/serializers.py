"""
Partners serializers.
"""
from rest_framework import serializers
from .models import PartnerCategory, Partner, PartnerContact, PartnerAddress, PartnerBankAccount


class PartnerCategorySerializer(serializers.ModelSerializer):
    """Serializer for PartnerCategory."""
    parent_name = serializers.CharField(source='parent.name', read_only=True)

    class Meta:
        model = PartnerCategory
        fields = [
            'id', 'code', 'name', 'description', 'parent', 'parent_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PartnerContactSerializer(serializers.ModelSerializer):
    """Serializer for PartnerContact."""

    class Meta:
        model = PartnerContact
        fields = [
            'id', 'partner', 'name', 'title', 'phone', 'mobile', 'email',
            'is_primary', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PartnerAddressSerializer(serializers.ModelSerializer):
    """Serializer for PartnerAddress."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = PartnerAddress
        fields = [
            'id', 'partner', 'type', 'type_display', 'name', 'street', 'street2',
            'city', 'state', 'postal_code', 'country', 'is_default',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PartnerBankAccountSerializer(serializers.ModelSerializer):
    """Serializer for PartnerBankAccount."""

    class Meta:
        model = PartnerBankAccount
        fields = [
            'id', 'partner', 'bank_name', 'bank_code', 'branch_code',
            'account_number', 'iban', 'swift_bic', 'account_holder',
            'is_default', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PartnerListSerializer(serializers.ModelSerializer):
    """Serializer for Partner list view."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)

    class Meta:
        model = Partner
        fields = [
            'id', 'type', 'type_display', 'code', 'name', 'legal_name',
            'category', 'category_name', 'city', 'phone', 'email',
            'credit_limit', 'is_active', 'currency_code', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PartnerDetailSerializer(serializers.ModelSerializer):
    """Serializer for Partner detail view with nested relations."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    contacts = PartnerContactSerializer(many=True, read_only=True)
    addresses = PartnerAddressSerializer(many=True, read_only=True)
    bank_accounts = PartnerBankAccountSerializer(many=True, read_only=True)

    class Meta:
        model = Partner
        fields = [
            'id', 'type', 'type_display', 'code', 'name', 'legal_name',
            'category', 'category_name', 'tax_id', 'trade_register',
            'street', 'street2', 'city', 'state', 'postal_code', 'country',
            'phone', 'mobile', 'fax', 'email', 'website',
            'credit_limit', 'payment_terms_days', 'discount_rate',
            'customer_accounting_code', 'supplier_accounting_code',
            'currency', 'currency_code', 'is_active', 'notes',
            'contacts', 'addresses', 'bank_accounts',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PartnerWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating Partner."""
    code = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Partner
        fields = [
            'type', 'code', 'name', 'legal_name', 'category',
            'tax_id', 'trade_register',
            'street', 'street2', 'city', 'state', 'postal_code', 'country',
            'phone', 'mobile', 'fax', 'email', 'website',
            'credit_limit', 'payment_terms_days', 'discount_rate',
            'customer_accounting_code', 'supplier_accounting_code',
            'currency', 'is_active', 'notes'
        ]

    def validate_code(self, value):
        if not value:
            return value
        request = self.context.get('request')
        company = getattr(request, 'company', None) if request else None
        if not company:
            return value
        qs = Partner.objects.filter(company=company, code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ce code existe déjà.")
        return value

    def create(self, validated_data):
        # Auto-generate code if not provided
        if not validated_data.get('code'):
            company = validated_data.get('company')
            partner_type = validated_data.get('type', 'customer')
            prefix = 'CLI' if partner_type == 'customer' else 'FOU' if partner_type == 'supplier' else 'PAR'
            
            # Find next number
            last_partner = Partner.objects.filter(
                company=company,
                code__startswith=prefix
            ).order_by('-code').first()
            
            if last_partner and last_partner.code[3:].isdigit():
                next_num = int(last_partner.code[3:]) + 1
            else:
                next_num = 1
            
            validated_data['code'] = f"{prefix}{next_num:05d}"
        
        return super().create(validated_data)
