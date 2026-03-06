"""Lightweight serializers for sync delta responses."""
from rest_framework import serializers
from apps.catalog.models import Product, ProductCategory
from apps.inventory.models import Warehouse, StockLevel
from apps.partners.models import Partner


class SyncProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', default='')
    unit_name = serializers.CharField(source='unit.name', default='')

    class Meta:
        model = Product
        fields = [
            'id', 'code', 'name', 'description', 'type',
            'category', 'category_name', 'unit', 'unit_name',
            'barcode', 'purchase_price', 'sale_price', 'tax_rate', 'tax_exempt',
            'is_stockable', 'is_saleable', 'is_purchasable',
            'is_active', 'updated_at',
        ]


class SyncCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', default='')

    class Meta:
        model = ProductCategory
        fields = [
            'id', 'code', 'name', 'description',
            'parent', 'parent_name', 'level',
            'is_active', 'updated_at',
        ]


class SyncWarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            'id', 'code', 'name', 'address_city', 'phone',
            'is_active', 'updated_at',
        ]


class SyncStockLevelSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', default='')
    product_code = serializers.CharField(source='product.code', default='')
    warehouse_name = serializers.CharField(source='warehouse.name', default='')

    class Meta:
        model = StockLevel
        fields = [
            'id', 'product', 'product_name', 'product_code',
            'warehouse', 'warehouse_name',
            'quantity_on_hand', 'quantity_reserved',
            'unit_cost', 'last_movement_date', 'updated_at',
        ]


class SyncPartnerSerializer(serializers.ModelSerializer):
    is_customer = serializers.BooleanField(read_only=True)
    is_supplier = serializers.BooleanField(read_only=True)

    class Meta:
        model = Partner
        fields = [
            'id', 'code', 'name', 'type',
            'is_customer', 'is_supplier',
            'email', 'phone', 'mobile', 'city', 'country',
            'credit_limit', 'payment_terms_days',
            'is_active', 'updated_at',
        ]
