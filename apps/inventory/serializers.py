"""
Inventory serializers.
"""
from rest_framework import serializers
from apps.core.serializers import CompanyScopedSerializer
from .models import (
    Warehouse, WarehouseLocation, StockLevel, StockMovement,
    StockAdjustment, StockAdjustmentLine, LotSerial
)


class WarehouseSerializer(CompanyScopedSerializer):
    """Serializer for Warehouse model."""
    full_address = serializers.ReadOnlyField()

    class Meta:
        model = Warehouse
        fields = [
            'id', 'code', 'name',
            'address_street', 'address_street2', 'address_city',
            'address_postal_code', 'address_country', 'full_address',
            'phone', 'email', 'manager', 'is_active',
            'company', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class WarehouseLocationSerializer(CompanyScopedSerializer):
    """Serializer for WarehouseLocation model."""
    full_path = serializers.ReadOnlyField()
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)

    class Meta:
        model = WarehouseLocation
        fields = [
            'id', 'warehouse', 'warehouse_name', 'code', 'name',
            'parent', 'parent_name', 'full_path', 'barcode', 'is_active',
            'company', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class StockLevelSerializer(CompanyScopedSerializer):
    """Serializer for StockLevel model."""
    quantity_available = serializers.ReadOnlyField()
    valuation = serializers.ReadOnlyField()
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)

    class Meta:
        model = StockLevel
        fields = [
            'id', 'product', 'product_code', 'product_name',
            'warehouse', 'warehouse_name', 'location', 'location_code',
            'quantity_on_hand', 'quantity_reserved', 'quantity_available',
            'unit_cost', 'valuation', 'last_movement_date',
            'company', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'company', 'created_at', 'updated_at',
            'quantity_on_hand', 'quantity_reserved', 'last_movement_date'
        ]


class StockMovementSerializer(CompanyScopedSerializer):
    """Serializer for StockMovement model."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    signed_quantity = serializers.ReadOnlyField()
    total_value = serializers.ReadOnlyField()
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    source_warehouse_name = serializers.CharField(
        source='source_warehouse.name', read_only=True
    )
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True
    )

    class Meta:
        model = StockMovement
        fields = [
            'id', 'type', 'type_display', 'source', 'source_display',
            'product', 'product_code', 'product_name',
            'warehouse', 'warehouse_name',
            'source_warehouse', 'source_warehouse_name',
            'location', 'quantity', 'signed_quantity',
            'unit_cost', 'total_value',
            'reference', 'reference_type', 'reference_id',
            'date', 'notes', 'lot_serial',
            'created_by', 'created_by_name',
            'company', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at', 'created_by']


class StockAdjustmentLineSerializer(CompanyScopedSerializer):
    """Serializer for StockAdjustmentLine model."""
    difference = serializers.ReadOnlyField()
    difference_value = serializers.ReadOnlyField()
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)

    class Meta:
        model = StockAdjustmentLine
        fields = [
            'id', 'adjustment', 'product', 'product_code', 'product_name',
            'location', 'location_code',
            'system_quantity', 'counted_quantity', 'difference',
            'unit_cost', 'difference_value', 'notes',
            'company', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at', 'adjustment']


class StockAdjustmentSerializer(CompanyScopedSerializer):
    """Serializer for StockAdjustment model."""
    lines = StockAdjustmentLineSerializer(many=True, read_only=True)
    adjustment_type_display = serializers.CharField(
        source='get_adjustment_type_display', read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_difference = serializers.ReadOnlyField()
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    confirmed_by_name = serializers.CharField(
        source='confirmed_by.get_full_name', read_only=True
    )

    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'reference', 'warehouse', 'warehouse_name',
            'adjustment_type', 'adjustment_type_display',
            'status', 'status_display', 'date', 'notes',
            'confirmed_by', 'confirmed_by_name', 'confirmed_at',
            'total_difference', 'lines',
            'company', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'company', 'created_at', 'updated_at',
            'confirmed_by', 'confirmed_at'
        ]


class StockAdjustmentCreateSerializer(CompanyScopedSerializer):
    """Serializer for creating StockAdjustment with lines."""
    lines = StockAdjustmentLineSerializer(many=True)

    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'reference', 'warehouse', 'adjustment_type',
            'status', 'date', 'notes', 'lines',
            'company', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']

    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        adjustment = StockAdjustment.objects.create(**validated_data)
        for line_data in lines_data:
            StockAdjustmentLine.objects.create(
                adjustment=adjustment,
                company=adjustment.company,
                **line_data
            )
        return adjustment


class LotSerialSerializer(CompanyScopedSerializer):
    """Serializer for LotSerial model."""
    is_expired = serializers.ReadOnlyField()
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)

    class Meta:
        model = LotSerial
        fields = [
            'id', 'product', 'product_code', 'product_name',
            'warehouse', 'warehouse_name', 'location', 'location_code',
            'lot_number', 'serial_number',
            'expiry_date', 'manufacturing_date', 'is_expired',
            'quantity', 'unit_cost', 'notes',
            'company', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class StockTransferSerializer(serializers.Serializer):
    """Serializer for stock transfer between warehouses."""
    product = serializers.UUIDField()
    from_warehouse = serializers.UUIDField()
    to_warehouse = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    from_location = serializers.UUIDField(required=False, allow_null=True)
    to_location = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data['from_warehouse'] == data['to_warehouse']:
            if not data.get('from_location') or not data.get('to_location'):
                raise serializers.ValidationError(
                    "Pour un transfert dans le même entrepôt, "
                    "les emplacements source et destination sont requis."
                )
            if data.get('from_location') == data.get('to_location'):
                raise serializers.ValidationError(
                    "Les emplacements source et destination doivent être différents."
                )
        return data


class StockReservationSerializer(serializers.Serializer):
    """Serializer for stock reservation."""
    product = serializers.UUIDField()
    warehouse = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    reference = serializers.CharField(required=False, allow_blank=True)
    reference_type = serializers.CharField(required=False, allow_blank=True)
    reference_id = serializers.UUIDField(required=False, allow_null=True)
