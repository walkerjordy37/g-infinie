"""
Payments serializers.
"""
from decimal import Decimal
from rest_framework import serializers
from .models import PaymentMethod, PaymentTerm, Payment, PaymentAllocation, Refund


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer pour les méthodes de paiement."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    bank_account_name = serializers.CharField(
        source='bank_account.name',
        read_only=True
    )

    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'code', 'name', 'type', 'type_display', 'is_active',
            'bank_account', 'bank_account_name', 'journal',
            'requires_reference', 'notes', 'company',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentTermSerializer(serializers.ModelSerializer):
    """Serializer pour les conditions de paiement."""
    class Meta:
        model = PaymentTerm
        fields = [
            'id', 'code', 'name', 'description', 'days', 'is_immediate',
            'discount_percent', 'discount_days', 'is_active', 'is_default',
            'company', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentAllocationSerializer(serializers.ModelSerializer):
    """Serializer pour les allocations de paiement."""
    sales_invoice_number = serializers.CharField(
        source='sales_invoice.number',
        read_only=True
    )
    supplier_invoice_number = serializers.CharField(
        source='supplier_invoice.number',
        read_only=True
    )
    invoice_partner = serializers.SerializerMethodField()

    class Meta:
        model = PaymentAllocation
        fields = [
            'id', 'payment', 'sales_invoice', 'sales_invoice_number',
            'supplier_invoice', 'supplier_invoice_number', 'invoice_partner',
            'amount', 'allocation_date', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_invoice_partner(self, obj):
        invoice = obj.sales_invoice or obj.supplier_invoice
        if invoice:
            return invoice.partner.name
        return None

    def validate(self, data):
        sales_invoice = data.get('sales_invoice')
        supplier_invoice = data.get('supplier_invoice')

        if not sales_invoice and not supplier_invoice:
            raise serializers.ValidationError(
                "Une facture client ou fournisseur doit être spécifiée."
            )
        if sales_invoice and supplier_invoice:
            raise serializers.ValidationError(
                "Seule une facture peut être spécifiée (client OU fournisseur)."
            )

        return data


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements."""
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    partner_name = serializers.CharField(source='partner.name', read_only=True)
    payment_method_name = serializers.CharField(
        source='payment_method.name',
        read_only=True
    )
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_type_display = serializers.CharField(
        source='get_payment_type_display',
        read_only=True
    )
    bank_account_name = serializers.CharField(
        source='bank_account.name',
        read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            'id', 'number', 'payment_type', 'payment_type_display',
            'partner', 'partner_name', 'date', 'value_date',
            'status', 'status_display', 'payment_method', 'payment_method_name',
            'currency', 'currency_code', 'exchange_rate',
            'amount', 'amount_allocated', 'amount_unallocated',
            'reference', 'memo', 'bank_account', 'bank_account_name',
            'confirmed_by', 'confirmed_at', 'journal_entry',
            'allocations', 'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'number', 'amount_allocated', 'amount_unallocated',
            'confirmed_by', 'confirmed_at', 'journal_entry',
            'created_at', 'updated_at',
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à 0.")
        return value


class PaymentWithAllocationsSerializer(PaymentSerializer):
    """Serializer pour création de paiement avec allocations."""
    allocations = PaymentAllocationSerializer(many=True, required=False)

    def create(self, validated_data):
        allocations_data = validated_data.pop('allocations', [])
        payment = Payment.objects.create(**validated_data)

        for alloc_data in allocations_data:
            alloc_data['payment'] = payment
            alloc_data['company'] = payment.company
            PaymentAllocation.objects.create(**alloc_data)

        payment.update_allocation_amounts()
        payment.save(update_fields=['amount_allocated', 'amount_unallocated'])

        return payment

    def update(self, instance, validated_data):
        allocations_data = validated_data.pop('allocations', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if allocations_data is not None:
            instance.allocations.all().delete()
            for alloc_data in allocations_data:
                alloc_data['payment'] = instance
                alloc_data['company'] = instance.company
                PaymentAllocation.objects.create(**alloc_data)

            instance.update_allocation_amounts()
            instance.save(update_fields=['amount_allocated', 'amount_unallocated'])

        return instance


class RefundSerializer(serializers.ModelSerializer):
    """Serializer pour les remboursements."""
    partner_name = serializers.CharField(source='partner.name', read_only=True)
    payment_method_name = serializers.CharField(
        source='payment_method.name',
        read_only=True
    )
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    refund_type_display = serializers.CharField(
        source='get_refund_type_display',
        read_only=True
    )
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    original_payment_number = serializers.CharField(
        source='original_payment.number',
        read_only=True
    )
    credit_note_number = serializers.CharField(
        source='credit_note.number',
        read_only=True
    )

    class Meta:
        model = Refund
        fields = [
            'id', 'number', 'refund_type', 'refund_type_display',
            'partner', 'partner_name', 'date', 'status', 'status_display',
            'reason', 'reason_display', 'reason_details',
            'payment_method', 'payment_method_name',
            'currency', 'currency_code', 'exchange_rate', 'amount',
            'original_payment', 'original_payment_number',
            'credit_note', 'credit_note_number',
            'reference', 'notes', 'bank_account',
            'paid_by', 'paid_at', 'journal_entry',
            'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'number', 'paid_by', 'paid_at', 'journal_entry',
            'created_at', 'updated_at',
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à 0.")
        return value


class AllocationRequestSerializer(serializers.Serializer):
    """Serializer pour les requêtes d'allocation."""
    invoice_id = serializers.UUIDField()
    invoice_type = serializers.ChoiceField(choices=['sales', 'supplier'])
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à 0.")
        return value


class AutoAllocateRequestSerializer(serializers.Serializer):
    """Serializer pour l'allocation automatique."""
    strategy = serializers.ChoiceField(
        choices=['fifo', 'oldest_first', 'largest_first'],
        default='fifo'
    )
    max_invoices = serializers.IntegerField(min_value=1, default=100)
