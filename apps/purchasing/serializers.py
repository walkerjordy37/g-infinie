"""
Purchasing serializers - Purchase Requests and RFQs.
"""
from rest_framework import serializers
from .models import (
    PurchaseRequest, PurchaseRequestLine,
    RequestForQuotation, RequestForQuotationLine, RFQComparison,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine,
    SupplierInvoice, SupplierInvoiceLine
)


# =============================================================================
# PURCHASE REQUEST SERIALIZERS
# =============================================================================

class PurchaseRequestLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de demande d'achat."""
    product_name = serializers.SerializerMethodField()
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    preferred_supplier_name = serializers.CharField(
        source='preferred_supplier.name', read_only=True
    )

    class Meta:
        model = PurchaseRequestLine
        fields = [
            'id', 'product', 'product_name', 'product_name_manual',
            'description', 'sequence',
            'quantity', 'unit', 'unit_name',
            'estimated_unit_price', 'estimated_total',
            'preferred_supplier', 'preferred_supplier_name', 'notes'
        ]
        read_only_fields = ['id', 'estimated_total']
        extra_kwargs = {
            'product': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_manual or ''

    def validate(self, attrs):
        if attrs.get('quantity', 0) <= 0:
            raise serializers.ValidationError({
                'quantity': "La quantité doit être supérieure à zéro."
            })
        return attrs


class PurchaseRequestSerializer(serializers.ModelSerializer):
    """Serializer pour les demandes d'achat."""
    lines = PurchaseRequestLineSerializer(many=True, required=False)
    requester_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = PurchaseRequest
        fields = [
            'id', 'number', 'date', 'required_date',
            'status', 'status_display', 'priority', 'priority_display',
            'requester', 'requester_name', 'department',
            'approved_by', 'approved_by_name', 'approved_at', 'rejection_reason',
            'estimated_total', 'notes', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'number', 'approved_by', 'approved_at', 'estimated_total',
            'created_at', 'updated_at'
        ]

    def get_requester_name(self, obj):
        return obj.requester.get_full_name() or obj.requester.email

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return None

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        request = PurchaseRequest.objects.create(**validated_data)

        for line_data in lines_data:
            line_data['company'] = request.company
            line = PurchaseRequestLine.objects.create(request=request, **line_data)
            line.calculate_totals()
            line.save()

        self._update_request_totals(request)
        return request

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data['company'] = instance.company
                line = PurchaseRequestLine.objects.create(request=instance, **line_data)
                line.calculate_totals()
                line.save()

        self._update_request_totals(instance)
        return instance

    def _update_request_totals(self, request):
        total = sum(line.estimated_total for line in request.lines.all())
        request.estimated_total = total
        request.save(update_fields=['estimated_total'])


class PurchaseRequestListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de demandes d'achat."""
    requester_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    lines_count = serializers.IntegerField(source='lines.count', read_only=True)

    class Meta:
        model = PurchaseRequest
        fields = [
            'id', 'number', 'date', 'required_date',
            'status', 'status_display', 'priority', 'priority_display',
            'requester_name', 'department', 'estimated_total', 'lines_count'
        ]

    def get_requester_name(self, obj):
        return obj.requester.get_full_name() or obj.requester.email


# =============================================================================
# RFQ SERIALIZERS
# =============================================================================

class RequestForQuotationLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de RFQ."""
    product_name = serializers.SerializerMethodField()
    unit_name = serializers.CharField(source='unit.name', read_only=True)

    class Meta:
        model = RequestForQuotationLine
        fields = [
            'id', 'request_line', 'product', 'product_name', 'product_name_manual',
            'description', 'sequence',
            'quantity', 'unit', 'unit_name',
            'quoted_unit_price', 'discount_percent', 'discount_amount',
            'tax_rate', 'tax_amount', 'subtotal', 'total',
            'quoted_lead_time', 'notes'
        ]
        read_only_fields = ['id', 'discount_amount', 'tax_amount', 'subtotal', 'total']
        extra_kwargs = {
            'product': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_manual or ''

    def validate(self, attrs):
        if attrs.get('quantity', 0) <= 0:
            raise serializers.ValidationError({
                'quantity': "La quantité doit être supérieure à zéro."
            })
        return attrs


class RequestForQuotationSerializer(serializers.ModelSerializer):
    """Serializer pour les demandes de prix."""
    lines = RequestForQuotationLineSerializer(many=True, required=False)
    supplier_name = serializers.SerializerMethodField()
    buyer_name = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    purchase_request_number = serializers.CharField(
        source='purchase_request.number', read_only=True
    )

    class Meta:
        model = RequestForQuotation
        fields = [
            'id', 'number', 'purchase_request', 'purchase_request_number',
            'supplier', 'supplier_name', 'supplier_name_manual',
            'date', 'deadline', 'status', 'status_display',
            'currency', 'currency_code', 'exchange_rate',
            'response_date', 'validity_date', 'delivery_lead_time', 'payment_terms',
            'subtotal', 'tax_total', 'discount_total', 'total',
            'notes', 'supplier_notes',
            'buyer', 'buyer_name', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'number', 'subtotal', 'tax_total', 'discount_total', 'total',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'supplier': {'required': False, 'allow_null': True},
        }

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name_manual or ''

    def get_buyer_name(self, obj):
        if obj.buyer:
            return obj.buyer.get_full_name() or obj.buyer.email
        return None

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        rfq = RequestForQuotation.objects.create(**validated_data)

        for line_data in lines_data:
            line_data['company'] = rfq.company
            line = RequestForQuotationLine.objects.create(rfq=rfq, **line_data)
            line.calculate_totals()
            line.save()

        self._update_rfq_totals(rfq)
        return rfq

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data['company'] = instance.company
                line = RequestForQuotationLine.objects.create(rfq=instance, **line_data)
                line.calculate_totals()
                line.save()

        self._update_rfq_totals(instance)
        return instance

    def _update_rfq_totals(self, rfq):
        lines = rfq.lines.all()
        rfq.subtotal = sum(line.subtotal for line in lines)
        rfq.tax_total = sum(line.tax_amount for line in lines)
        rfq.discount_total = sum(line.discount_amount for line in lines)
        rfq.total = sum(line.total for line in lines)
        rfq.save(update_fields=['subtotal', 'tax_total', 'discount_total', 'total'])


class RequestForQuotationListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de RFQ."""
    supplier_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines_count = serializers.IntegerField(source='lines.count', read_only=True)

    class Meta:
        model = RequestForQuotation
        fields = [
            'id', 'number', 'supplier_name', 'date', 'deadline',
            'status', 'status_display', 'total', 'lines_count'
        ]

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name_manual or ''


# =============================================================================
# RFQ COMPARISON SERIALIZER
# =============================================================================

class RFQComparisonSerializer(serializers.ModelSerializer):
    """Serializer pour les comparaisons de RFQ."""
    purchase_request_number = serializers.CharField(
        source='purchase_request.number', read_only=True
    )
    selected_rfq_number = serializers.CharField(
        source='selected_rfq.number', read_only=True
    )
    compared_by_name = serializers.SerializerMethodField()
    rfqs_details = RequestForQuotationListSerializer(
        source='rfqs', many=True, read_only=True
    )

    class Meta:
        model = RFQComparison
        fields = [
            'id', 'purchase_request', 'purchase_request_number',
            'rfqs', 'rfqs_details',
            'selected_rfq', 'selected_rfq_number', 'selection_reason',
            'comparison_date', 'compared_by', 'compared_by_name', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_compared_by_name(self, obj):
        if obj.compared_by:
            return obj.compared_by.get_full_name() or obj.compared_by.email
        return None


# =============================================================================
# PURCHASE ORDER SERIALIZERS
# =============================================================================

class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de commande fournisseur."""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()
    unit_name = serializers.CharField(source='unit.name', read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = [
            'id', 'rfq_line', 'product', 'product_name', 'product_name_manual',
            'product_code', 'description', 'sequence',
            'quantity', 'quantity_received', 'quantity_invoiced', 'unit', 'unit_name',
            'unit_price', 'discount_percent', 'discount_amount',
            'tax_rate', 'tax_amount', 'subtotal', 'total', 'notes'
        ]
        read_only_fields = [
            'id', 'discount_amount', 'tax_amount', 'subtotal', 'total',
            'quantity_received', 'quantity_invoiced'
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


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """Serializer pour les commandes fournisseur."""
    lines = PurchaseOrderLineSerializer(many=True, required=False)
    supplier_name = serializers.SerializerMethodField()
    buyer_name = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    rfq_number = serializers.CharField(source='rfq.number', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'number', 'rfq', 'rfq_number', 'purchase_request',
            'supplier', 'supplier_name', 'supplier_name_manual',
            'date', 'expected_delivery_date', 'status', 'status_display',
            'currency', 'currency_code', 'exchange_rate',
            'subtotal', 'tax_total', 'discount_total', 'total',
            'payment_terms', 'incoterm', 'delivery_address',
            'notes', 'supplier_reference',
            'buyer', 'buyer_name', 'warehouse', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'number', 'subtotal', 'tax_total', 'discount_total', 'total',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'supplier': {'required': False, 'allow_null': True},
        }

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name_manual or ''

    def get_buyer_name(self, obj):
        if obj.buyer:
            return obj.buyer.get_full_name() or obj.buyer.email
        return None

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        order = PurchaseOrder.objects.create(**validated_data)

        for line_data in lines_data:
            line_data['company'] = order.company
            line = PurchaseOrderLine.objects.create(order=order, **line_data)
            line.calculate_totals()
            line.save()

        self._update_order_totals(order)
        return order

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data['company'] = instance.company
                line = PurchaseOrderLine.objects.create(order=instance, **line_data)
                line.calculate_totals()
                line.save()

        self._update_order_totals(instance)
        return instance

    def _update_order_totals(self, order):
        lines = order.lines.all()
        order.subtotal = sum(line.subtotal for line in lines)
        order.tax_total = sum(line.tax_amount for line in lines)
        order.discount_total = sum(line.discount_amount for line in lines)
        order.total = sum(line.total for line in lines)
        order.save(update_fields=['subtotal', 'tax_total', 'discount_total', 'total'])


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de commandes."""
    supplier_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines_count = serializers.IntegerField(source='lines.count', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'number', 'supplier_name', 'date', 'expected_delivery_date',
            'status', 'status_display', 'total', 'lines_count'
        ]

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name_manual or ''


# =============================================================================
# GOODS RECEIPT SERIALIZERS
# =============================================================================

class GoodsReceiptLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de réception."""
    product_name = serializers.SerializerMethodField()
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    quantity_accepted = serializers.DecimalField(
        max_digits=15, decimal_places=3, read_only=True
    )

    class Meta:
        model = GoodsReceiptLine
        fields = [
            'id', 'order_line', 'product', 'product_name', 'product_name_manual',
            'sequence',
            'quantity_expected', 'quantity_received', 'quantity_rejected',
            'quantity_accepted', 'unit', 'unit_name',
            'lot_number', 'serial_numbers', 'expiry_date',
            'location', 'rejection_reason', 'notes'
        ]
        read_only_fields = ['id', 'quantity_accepted']
        extra_kwargs = {
            'product': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_manual or ''


class GoodsReceiptSerializer(serializers.ModelSerializer):
    """Serializer pour les réceptions de marchandises."""
    lines = GoodsReceiptLineSerializer(many=True, required=False)
    supplier_name = serializers.SerializerMethodField()
    purchase_order_number = serializers.CharField(source='purchase_order.number', read_only=True)
    received_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = [
            'id', 'number', 'purchase_order', 'purchase_order_number',
            'supplier', 'supplier_name', 'supplier_name_manual',
            'date', 'status', 'status_display',
            'delivery_note_number', 'carrier', 'tracking_number',
            'warehouse', 'received_by', 'received_by_name', 'validated_at',
            'notes', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'number', 'validated_at', 'created_at', 'updated_at']
        extra_kwargs = {
            'supplier': {'required': False, 'allow_null': True},
        }

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name_manual or ''

    def get_received_by_name(self, obj):
        if obj.received_by:
            return obj.received_by.get_full_name() or obj.received_by.email
        return None

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        receipt = GoodsReceipt.objects.create(**validated_data)

        for line_data in lines_data:
            line_data['company'] = receipt.company
            GoodsReceiptLine.objects.create(receipt=receipt, **line_data)

        return receipt

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data['company'] = instance.company
                GoodsReceiptLine.objects.create(receipt=instance, **line_data)

        return instance


class GoodsReceiptListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de réceptions."""
    supplier_name = serializers.SerializerMethodField()
    purchase_order_number = serializers.CharField(source='purchase_order.number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines_count = serializers.IntegerField(source='lines.count', read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = [
            'id', 'number', 'purchase_order_number', 'supplier_name',
            'date', 'status', 'status_display', 'lines_count'
        ]

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name_manual or ''


# =============================================================================
# SUPPLIER INVOICE SERIALIZERS
# =============================================================================

class SupplierInvoiceLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de facture fournisseur."""
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = SupplierInvoiceLine
        fields = [
            'id', 'order_line', 'receipt_line', 'product', 'product_name',
            'product_name_manual', 'description', 'sequence',
            'quantity', 'unit_price', 'discount_percent', 'discount_amount',
            'tax_rate', 'tax_amount', 'subtotal', 'total',
            'three_way_match_status'
        ]
        read_only_fields = ['id', 'discount_amount', 'tax_amount', 'subtotal', 'total']
        extra_kwargs = {
            'product': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_manual or ''


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    """Serializer pour les factures fournisseur."""
    lines = SupplierInvoiceLineSerializer(many=True, required=False)
    supplier_name = serializers.SerializerMethodField()
    purchase_order_number = serializers.CharField(
        source='purchase_order.number', read_only=True
    )
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)
    validated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SupplierInvoice
        fields = [
            'id', 'number', 'supplier_invoice_number', 'invoice_type', 'type_display',
            'purchase_order', 'purchase_order_number',
            'supplier', 'supplier_name', 'supplier_name_manual',
            'date', 'due_date', 'received_date', 'status', 'status_display',
            'currency', 'currency_code', 'exchange_rate',
            'subtotal', 'tax_total', 'discount_total', 'total',
            'amount_paid', 'amount_due',
            'payment_terms', 'payment_reference', 'notes',
            'three_way_match_status', 'three_way_match_notes',
            'validated_by', 'validated_by_name', 'validated_at',
            'accounting_date', 'journal_entry', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'number', 'subtotal', 'tax_total', 'discount_total', 'total',
            'amount_due', 'validated_at', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'supplier': {'required': False, 'allow_null': True},
        }

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name_manual or ''

    def get_validated_by_name(self, obj):
        if obj.validated_by:
            return obj.validated_by.get_full_name() or obj.validated_by.email
        return None

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        invoice = SupplierInvoice.objects.create(**validated_data)

        for line_data in lines_data:
            line_data['company'] = invoice.company
            line = SupplierInvoiceLine.objects.create(invoice=invoice, **line_data)
            line.calculate_totals()
            line.save()

        self._update_invoice_totals(invoice)
        return invoice

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data['company'] = instance.company
                line = SupplierInvoiceLine.objects.create(invoice=instance, **line_data)
                line.calculate_totals()
                line.save()

        self._update_invoice_totals(instance)
        return instance

    def _update_invoice_totals(self, invoice):
        lines = invoice.lines.all()
        invoice.subtotal = sum(line.subtotal for line in lines)
        invoice.tax_total = sum(line.tax_amount for line in lines)
        invoice.discount_total = sum(line.discount_amount for line in lines)
        invoice.total = sum(line.total for line in lines)
        invoice.amount_due = invoice.total - invoice.amount_paid
        invoice.save(update_fields=[
            'subtotal', 'tax_total', 'discount_total', 'total', 'amount_due'
        ])


class SupplierInvoiceListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes de factures."""
    supplier_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            'id', 'number', 'supplier_invoice_number', 'supplier_name',
            'invoice_type', 'type_display',
            'date', 'due_date', 'status', 'status_display',
            'total', 'amount_paid', 'amount_due',
            'three_way_match_status'
        ]

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name_manual or ''
