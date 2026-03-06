"""
Tax serializers - Serializers for tax types, rates, groups, rules, and declarations.
"""
from rest_framework import serializers
from .models import (
    TaxType, TaxRate, TaxGroup, TaxRule,
    WithholdingTax, TaxDeclaration, TaxDeclarationLine
)


# =============================================================================
# TAX TYPE SERIALIZERS
# =============================================================================

class TaxTypeSerializer(serializers.ModelSerializer):
    """Serializer pour les types de taxe."""
    tax_type_display = serializers.CharField(source='get_tax_type_display', read_only=True)
    account_collected_name = serializers.CharField(
        source='account_collected.name', read_only=True
    )
    account_deductible_name = serializers.CharField(
        source='account_deductible.name', read_only=True
    )

    class Meta:
        model = TaxType
        fields = [
            'id', 'code', 'name', 'tax_type', 'tax_type_display',
            'description', 'is_active',
            'account_collected', 'account_collected_name',
            'account_deductible', 'account_deductible_name',
            'account_payable',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxTypeListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de types de taxe."""
    tax_type_display = serializers.CharField(source='get_tax_type_display', read_only=True)

    class Meta:
        model = TaxType
        fields = ['id', 'code', 'name', 'tax_type', 'tax_type_display', 'is_active']


# =============================================================================
# TAX RATE SERIALIZERS
# =============================================================================

class TaxRateSerializer(serializers.ModelSerializer):
    """Serializer pour les taux de taxe."""
    tax_type_name = serializers.CharField(source='tax_type.name', read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = TaxRate
        fields = [
            'id', 'tax_type', 'tax_type_name', 'name', 'rate',
            'description', 'valid_from', 'valid_to',
            'is_default', 'is_active', 'is_valid',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        valid_from = attrs.get('valid_from')
        valid_to = attrs.get('valid_to')
        if valid_to and valid_from and valid_to < valid_from:
            raise serializers.ValidationError({
                'valid_to': "La date de fin doit être postérieure à la date de début."
            })
        return attrs


class TaxRateListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de taux de taxe."""
    tax_type_name = serializers.CharField(source='tax_type.name', read_only=True)

    class Meta:
        model = TaxRate
        fields = [
            'id', 'tax_type_name', 'name', 'rate',
            'valid_from', 'valid_to', 'is_default', 'is_active'
        ]


# =============================================================================
# TAX GROUP SERIALIZERS
# =============================================================================

class TaxGroupSerializer(serializers.ModelSerializer):
    """Serializer pour les groupes de taxes."""
    tax_rates_detail = TaxRateListSerializer(source='tax_rates', many=True, read_only=True)
    total_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )

    class Meta:
        model = TaxGroup
        fields = [
            'id', 'code', 'name', 'description', 'is_active',
            'tax_rates', 'tax_rates_detail', 'total_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxGroupListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de groupes de taxes."""
    total_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )

    class Meta:
        model = TaxGroup
        fields = ['id', 'code', 'name', 'total_rate', 'is_active']


# =============================================================================
# TAX RULE SERIALIZERS
# =============================================================================

class TaxRuleSerializer(serializers.ModelSerializer):
    """Serializer pour les règles de taxe."""
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display', read_only=True
    )
    partner_type_display = serializers.CharField(
        source='get_partner_type_display', read_only=True
    )
    tax_group_name = serializers.CharField(source='tax_group.name', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    product_category_name = serializers.CharField(
        source='product_category.name', read_only=True
    )

    class Meta:
        model = TaxRule
        fields = [
            'id', 'code', 'name', 'description',
            'transaction_type', 'transaction_type_display',
            'partner_type', 'partner_type_display',
            'tax_group', 'tax_group_name',
            'country', 'country_name',
            'product_category', 'product_category_name',
            'priority', 'is_active', 'valid_from', 'valid_to',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxRuleListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de règles."""
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display', read_only=True
    )
    tax_group_name = serializers.CharField(source='tax_group.name', read_only=True)

    class Meta:
        model = TaxRule
        fields = [
            'id', 'code', 'name', 'transaction_type', 'transaction_type_display',
            'tax_group_name', 'priority', 'is_active'
        ]


# =============================================================================
# WITHHOLDING TAX SERIALIZERS
# =============================================================================

class WithholdingTaxSerializer(serializers.ModelSerializer):
    """Serializer pour les retenues à la source."""
    withholding_type_display = serializers.CharField(
        source='get_withholding_type_display', read_only=True
    )
    account_payable_name = serializers.CharField(
        source='account_payable.name', read_only=True
    )

    class Meta:
        model = WithholdingTax
        fields = [
            'id', 'code', 'name', 'withholding_type', 'withholding_type_display',
            'description', 'rate', 'threshold_amount',
            'applies_to_residents', 'applies_to_non_residents',
            'account_payable', 'account_payable_name',
            'valid_from', 'valid_to', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WithholdingTaxListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de retenues."""
    withholding_type_display = serializers.CharField(
        source='get_withholding_type_display', read_only=True
    )

    class Meta:
        model = WithholdingTax
        fields = [
            'id', 'code', 'name', 'withholding_type', 'withholding_type_display',
            'rate', 'is_active'
        ]


# =============================================================================
# TAX DECLARATION SERIALIZERS
# =============================================================================

class TaxDeclarationLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de déclaration."""
    tax_rate_name = serializers.CharField(source='tax_rate.name', read_only=True)
    tax_rate_percentage = serializers.DecimalField(
        source='tax_rate.rate', max_digits=5, decimal_places=2, read_only=True
    )
    line_type_display = serializers.CharField(source='get_line_type_display', read_only=True)

    class Meta:
        model = TaxDeclarationLine
        fields = [
            'id', 'tax_rate', 'tax_rate_name', 'tax_rate_percentage',
            'line_type', 'line_type_display', 'sequence',
            'base_amount', 'tax_amount', 'invoice_count', 'notes'
        ]
        read_only_fields = ['id']


class TaxDeclarationSerializer(serializers.ModelSerializer):
    """Serializer pour les déclarations fiscales."""
    lines = TaxDeclarationLineSerializer(many=True, required=False)
    tax_type_name = serializers.CharField(source='tax_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    period_type_display = serializers.CharField(source='get_period_type_display', read_only=True)
    calculated_by_name = serializers.SerializerMethodField()
    validated_by_name = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = TaxDeclaration
        fields = [
            'id', 'number', 'tax_type', 'tax_type_name',
            'period_type', 'period_type_display',
            'period_start', 'period_end', 'due_date',
            'status', 'status_display',
            'tax_collected', 'tax_deductible',
            'credit_carried_forward', 'tax_due', 'credit_to_carry',
            'calculated_at', 'calculated_by', 'calculated_by_name',
            'validated_at', 'validated_by', 'validated_by_name',
            'submitted_at', 'submission_reference',
            'payment_date', 'payment_reference', 'payment_amount',
            'notes', 'is_overdue', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'number', 'tax_collected', 'tax_deductible',
            'tax_due', 'credit_to_carry',
            'calculated_at', 'validated_at', 'submitted_at',
            'created_at', 'updated_at'
        ]

    def get_calculated_by_name(self, obj):
        if obj.calculated_by:
            return obj.calculated_by.get_full_name() or obj.calculated_by.email
        return None

    def get_validated_by_name(self, obj):
        if obj.validated_by:
            return obj.validated_by.get_full_name() or obj.validated_by.email
        return None

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        declaration = TaxDeclaration.objects.create(**validated_data)

        for line_data in lines_data:
            line_data['company'] = declaration.company
            TaxDeclarationLine.objects.create(declaration=declaration, **line_data)

        declaration.calculate_totals()
        declaration.save()
        return declaration

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data['company'] = instance.company
                TaxDeclarationLine.objects.create(declaration=instance, **line_data)

        instance.calculate_totals()
        instance.save()
        return instance


class TaxDeclarationListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de déclarations."""
    tax_type_name = serializers.CharField(source='tax_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    period_type_display = serializers.CharField(source='get_period_type_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = TaxDeclaration
        fields = [
            'id', 'number', 'tax_type_name',
            'period_type', 'period_type_display',
            'period_start', 'period_end', 'due_date',
            'status', 'status_display',
            'tax_due', 'is_overdue'
        ]


# =============================================================================
# CALCULATION SERIALIZERS
# =============================================================================

class TaxCalculationInputSerializer(serializers.Serializer):
    """Serializer pour les entrées de calcul de taxe."""
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    tax_rate_id = serializers.UUIDField(required=False)
    tax_group_id = serializers.UUIDField(required=False)
    transaction_type = serializers.ChoiceField(
        choices=TaxRule.TRANSACTION_CHOICES,
        required=False
    )
    partner_type = serializers.ChoiceField(
        choices=TaxRule.PARTNER_CHOICES,
        required=False
    )
    date = serializers.DateField(required=False)

    def validate(self, attrs):
        if not attrs.get('tax_rate_id') and not attrs.get('tax_group_id'):
            if not (attrs.get('transaction_type') and attrs.get('partner_type')):
                raise serializers.ValidationError(
                    "Veuillez fournir soit un taux/groupe de taxe, "
                    "soit un type de transaction et de partenaire."
                )
        return attrs


class TaxCalculationResultSerializer(serializers.Serializer):
    """Serializer pour les résultats de calcul de taxe."""
    base_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    tax_details = serializers.ListField(child=serializers.DictField())
    total_tax = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)


class WithholdingCalculationInputSerializer(serializers.Serializer):
    """Serializer pour le calcul de retenue à la source."""
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    withholding_tax_id = serializers.UUIDField()
    is_resident = serializers.BooleanField(default=True)


class WithholdingCalculationResultSerializer(serializers.Serializer):
    """Serializer pour les résultats de calcul de retenue."""
    gross_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    withholding_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    withholding_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
