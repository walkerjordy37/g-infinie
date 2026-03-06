"""
Sales serializers.
"""
from decimal import Decimal
from rest_framework import serializers
from .models import (
    SalesQuote, SalesQuoteLine,
    SalesOrder, SalesOrderLine,
    DeliveryNote, DeliveryNoteLine,
    SalesInvoice, SalesInvoiceLine,
    SalesReturn, SalesReturnLine,
)


class SalesQuoteLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de devis."""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()

    class Meta:
        model = SalesQuoteLine
        fields = [
            'id', 'quote', 'product', 'product_code', 'product_name',
            'product_name_manual',
            'description', 'sequence', 'quantity', 'unit_price',
            'discount_percent', 'discount_amount', 'tax_rate', 'tax_amount',
            'subtotal', 'total', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'subtotal', 'total', 'tax_amount', 'created_at', 'updated_at']
        extra_kwargs = {
            'product': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_manual or ''

    def get_product_code(self, obj):
        if obj.product:
            return obj.product.code
        return ''

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être supérieure à 0.")
        return value


class SalesQuoteSerializer(serializers.ModelSerializer):
    """Serializer pour les devis."""
    lines = SalesQuoteLineSerializer(many=True, read_only=True)
    partner_name = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    salesperson_name = serializers.CharField(
        source='salesperson.get_full_name',
        read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SalesQuote
        fields = [
            'id', 'number', 'partner', 'partner_name', 'partner_name_manual',
            'date', 'validity_date',
            'status', 'status_display', 'currency', 'currency_code', 'exchange_rate',
            'subtotal', 'tax_total', 'discount_total', 'total',
            'notes', 'terms', 'salesperson', 'salesperson_name',
            'lines', 'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'number', 'subtotal', 'tax_total', 'discount_total', 'total',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'partner': {'required': False, 'allow_null': True},
        }

    def get_partner_name(self, obj):
        if obj.partner:
            return obj.partner.name
        return obj.partner_name_manual or ''


class SalesQuoteWithLinesSerializer(SalesQuoteSerializer):
    """Serializer pour création de devis avec lignes."""
    lines = SalesQuoteLineSerializer(many=True)

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        quote = SalesQuote.objects.create(**validated_data)
        for line_data in lines_data:
            line_data['quote'] = quote
            line_data['company'] = quote.company
            SalesQuoteLine.objects.create(**line_data)
        return quote

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data['quote'] = instance
                line_data['company'] = instance.company
                SalesQuoteLine.objects.create(**line_data)

        return instance


class SalesOrderLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de commande."""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrderLine
        fields = [
            'id', 'order', 'product', 'product_code', 'product_name',
            'product_name_manual',
            'description', 'sequence', 'quantity', 'quantity_delivered',
            'quantity_invoiced', 'unit_price', 'discount_percent', 'discount_amount',
            'tax_rate', 'tax_amount', 'subtotal', 'total',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'quantity_delivered', 'quantity_invoiced',
            'subtotal', 'total', 'tax_amount', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'product': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_manual or ''

    def get_product_code(self, obj):
        if obj.product:
            return obj.product.code
        return ''


class SalesOrderSerializer(serializers.ModelSerializer):
    """Serializer pour les commandes."""
    lines = SalesOrderLineSerializer(many=True, read_only=True)
    partner_name = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    salesperson_name = serializers.CharField(
        source='salesperson.get_full_name',
        read_only=True
    )
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SalesOrder
        fields = [
            'id', 'number', 'quote', 'partner', 'partner_name', 'partner_name_manual',
            'date', 'expected_delivery_date', 'status', 'status_display',
            'currency', 'currency_code', 'exchange_rate',
            'subtotal', 'tax_total', 'discount_total', 'total',
            'notes', 'terms', 'salesperson', 'salesperson_name',
            'warehouse', 'warehouse_name', 'lines', 'company',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'number', 'subtotal', 'tax_total', 'discount_total', 'total',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'partner': {'required': False, 'allow_null': True},
        }

    def get_partner_name(self, obj):
        if obj.partner:
            return obj.partner.name
        return obj.partner_name_manual or ''


class SalesOrderWithLinesSerializer(SalesOrderSerializer):
    """Serializer pour création de commande avec lignes."""
    lines = SalesOrderLineSerializer(many=True)

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        order = SalesOrder.objects.create(**validated_data)
        for line_data in lines_data:
            line_data['order'] = order
            line_data['company'] = order.company
            SalesOrderLine.objects.create(**line_data)
        return order

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data['order'] = instance
                line_data['company'] = instance.company
                SalesOrderLine.objects.create(**line_data)

        return instance


class DeliveryNoteLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de bon de livraison."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)

    class Meta:
        model = DeliveryNoteLine
        fields = [
            'id', 'delivery_note', 'order_line', 'product',
            'product_code', 'product_name', 'sequence',
            'quantity_ordered', 'quantity_delivered',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DeliveryNoteSerializer(serializers.ModelSerializer):
    """Serializer pour les bons de livraison."""
    lines = DeliveryNoteLineSerializer(many=True, read_only=True)
    partner_name = serializers.SerializerMethodField()
    order_number = serializers.CharField(source='order.number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DeliveryNote
        fields = [
            'id', 'number', 'order', 'order_number', 'partner', 'partner_name',
            'partner_name_manual',
            'date', 'status', 'status_display', 'shipping_address',
            'carrier', 'tracking_number', 'notes',
            'shipped_by', 'shipped_at', 'delivered_at',
            'lines', 'company', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'number', 'shipped_at', 'delivered_at', 'created_at', 'updated_at']
        extra_kwargs = {
            'partner': {'required': False, 'allow_null': True},
        }

    def get_partner_name(self, obj):
        if obj.partner:
            return obj.partner.name
        return obj.partner_name_manual or ''


class SalesInvoiceLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de facture."""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()

    class Meta:
        model = SalesInvoiceLine
        fields = [
            'id', 'invoice', 'order_line', 'product', 'product_code', 'product_name',
            'product_name_manual',
            'description', 'sequence', 'quantity', 'unit_price',
            'discount_percent', 'discount_amount', 'tax_rate', 'tax_amount',
            'subtotal', 'total', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'subtotal', 'total', 'tax_amount', 'created_at', 'updated_at']
        extra_kwargs = {
            'product': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_manual or ''

    def get_product_code(self, obj):
        if obj.product:
            return obj.product.code
        return ''


class SalesInvoiceSerializer(serializers.ModelSerializer):
    """Serializer pour les factures."""
    lines = SalesInvoiceLineSerializer(many=True, read_only=True)
    partner_name = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    order_number = serializers.CharField(source='order.number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SalesInvoice
        fields = [
            'id', 'number', 'order', 'order_number', 'delivery_note',
            'partner', 'partner_name', 'partner_name_manual', 'date', 'due_date',
            'status', 'status_display', 'currency', 'currency_code', 'exchange_rate',
            'subtotal', 'tax_total', 'discount_total', 'total',
            'amount_paid', 'amount_due', 'notes', 'terms',
            'is_posted', 'posted_at', 'journal_entry',
            'lines', 'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'number', 'subtotal', 'tax_total', 'discount_total', 'total',
            'amount_paid', 'amount_due', 'is_posted', 'posted_at', 'journal_entry',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'partner': {'required': False, 'allow_null': True},
        }

    def get_partner_name(self, obj):
        if obj.partner:
            return obj.partner.name
        return obj.partner_name_manual or ''


class SalesInvoiceWithLinesSerializer(SalesInvoiceSerializer):
    """Serializer pour création de facture avec lignes."""
    lines = SalesInvoiceLineSerializer(many=True)

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        invoice = SalesInvoice.objects.create(**validated_data)
        for line_data in lines_data:
            line_data['invoice'] = invoice
            line_data['company'] = invoice.company
            SalesInvoiceLine.objects.create(**line_data)
        return invoice


class SalesReturnLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de retour."""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()

    class Meta:
        model = SalesReturnLine
        fields = [
            'id', 'sales_return', 'invoice_line', 'product',
            'product_code', 'product_name', 'product_name_manual', 'sequence',
            'quantity', 'unit_price', 'tax_rate', 'tax_amount',
            'subtotal', 'total', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'subtotal', 'total', 'tax_amount', 'created_at', 'updated_at']
        extra_kwargs = {
            'product': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_manual or ''

    def get_product_code(self, obj):
        if obj.product:
            return obj.product.code
        return ''


class SalesReturnSerializer(serializers.ModelSerializer):
    """Serializer pour les retours clients."""
    lines = SalesReturnLineSerializer(many=True, read_only=True)
    partner_name = serializers.SerializerMethodField()
    invoice_number = serializers.CharField(source='invoice.number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)

    class Meta:
        model = SalesReturn
        fields = [
            'id', 'number', 'invoice', 'invoice_number', 'partner', 'partner_name',
            'partner_name_manual',
            'date', 'status', 'status_display', 'reason', 'reason_display',
            'reason_details', 'subtotal', 'tax_total', 'total',
            'credit_note', 'notes', 'lines', 'company',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'number', 'subtotal', 'tax_total', 'total', 'credit_note',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'partner': {'required': False, 'allow_null': True},
        }

    def get_partner_name(self, obj):
        if obj.partner:
            return obj.partner.name
        return obj.partner_name_manual or ''


class SalesReturnWithLinesSerializer(SalesReturnSerializer):
    """Serializer pour création de retour avec lignes."""
    lines = SalesReturnLineSerializer(many=True)

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        sales_return = SalesReturn.objects.create(**validated_data)
        for line_data in lines_data:
            line_data['sales_return'] = sales_return
            line_data['company'] = sales_return.company
            SalesReturnLine.objects.create(**line_data)
        return sales_return
