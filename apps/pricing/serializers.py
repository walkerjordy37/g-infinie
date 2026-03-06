"""
Pricing serializers.
"""
from rest_framework import serializers
from .models import (
    PriceList,
    PriceListItem,
    CustomerPriceRule,
    VolumeDiscount,
    Promotion,
    PromotionProduct,
)


class PriceListSerializer(serializers.ModelSerializer):
    """Serializer for PriceList."""
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = PriceList
        fields = [
            'id', 'code', 'name', 'description', 'currency', 'currency_code',
            'currency_symbol', 'is_default', 'is_active', 'valid_from', 'valid_to',
            'items_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_items_count(self, obj):
        return obj.items.count()


class PriceListItemSerializer(serializers.ModelSerializer):
    """Serializer for PriceListItem."""
    price_list_name = serializers.CharField(source='price_list.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PriceListItem
        fields = [
            'id', 'price_list', 'price_list_name', 'product', 'product_code',
            'product_name', 'min_quantity', 'unit_price', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PriceListDetailSerializer(serializers.ModelSerializer):
    """Serializer for PriceList with nested items."""
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    items = PriceListItemSerializer(many=True, read_only=True)

    class Meta:
        model = PriceList
        fields = [
            'id', 'code', 'name', 'description', 'currency', 'currency_code',
            'currency_symbol', 'is_default', 'is_active', 'valid_from', 'valid_to',
            'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CustomerPriceRuleSerializer(serializers.ModelSerializer):
    """Serializer for CustomerPriceRule."""
    partner_name = serializers.CharField(source='partner.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    discount_type_display = serializers.CharField(
        source='get_discount_type_display', read_only=True
    )

    class Meta:
        model = CustomerPriceRule
        fields = [
            'id', 'partner', 'partner_name', 'product', 'product_name',
            'category', 'category_name', 'discount_type', 'discount_type_display',
            'discount_value', 'valid_from', 'valid_to', 'priority', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        if data.get('product') and data.get('category'):
            raise serializers.ValidationError(
                "Vous ne pouvez pas spécifier à la fois un produit et une catégorie."
            )
        return data


class VolumeDiscountSerializer(serializers.ModelSerializer):
    """Serializer for VolumeDiscount."""
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    discount_type_display = serializers.CharField(
        source='get_discount_type_display', read_only=True
    )

    class Meta:
        model = VolumeDiscount
        fields = [
            'id', 'product', 'product_code', 'product_name', 'min_quantity',
            'max_quantity', 'discount_type', 'discount_type_display',
            'discount_value', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        min_qty = data.get('min_quantity')
        max_qty = data.get('max_quantity')
        if max_qty is not None and min_qty is not None and max_qty < min_qty:
            raise serializers.ValidationError({
                'max_quantity': "La quantité maximum doit être supérieure à la quantité minimum."
            })
        return data


class PromotionProductSerializer(serializers.ModelSerializer):
    """Serializer for PromotionProduct."""
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PromotionProduct
        fields = [
            'id', 'promotion', 'product', 'product_code', 'product_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PromotionSerializer(serializers.ModelSerializer):
    """Serializer for Promotion."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    is_exhausted = serializers.BooleanField(read_only=True)
    remaining_uses = serializers.IntegerField(read_only=True)
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = [
            'id', 'code', 'name', 'description', 'type', 'type_display',
            'value', 'buy_quantity', 'get_quantity', 'valid_from', 'valid_to',
            'min_purchase_amount', 'max_uses', 'current_uses', 'is_exhausted',
            'remaining_uses', 'is_active', 'products_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_uses', 'created_at', 'updated_at']

    def get_products_count(self, obj):
        return obj.products.count()

    def validate(self, data):
        promo_type = data.get('type', getattr(self.instance, 'type', None))
        if promo_type == Promotion.TYPE_BUY_X_GET_Y:
            if not data.get('buy_quantity') and not getattr(self.instance, 'buy_quantity', None):
                raise serializers.ValidationError({
                    'buy_quantity': "Requis pour les promotions 'Achetez X, obtenez Y'."
                })
            if not data.get('get_quantity') and not getattr(self.instance, 'get_quantity', None):
                raise serializers.ValidationError({
                    'get_quantity': "Requis pour les promotions 'Achetez X, obtenez Y'."
                })

        valid_from = data.get('valid_from')
        valid_to = data.get('valid_to')
        if valid_from and valid_to and valid_to < valid_from:
            raise serializers.ValidationError({
                'valid_to': "La date de fin doit être postérieure à la date de début."
            })
        return data


class PromotionDetailSerializer(serializers.ModelSerializer):
    """Serializer for Promotion with nested products."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    is_exhausted = serializers.BooleanField(read_only=True)
    remaining_uses = serializers.IntegerField(read_only=True)
    products = PromotionProductSerializer(many=True, read_only=True)

    class Meta:
        model = Promotion
        fields = [
            'id', 'code', 'name', 'description', 'type', 'type_display',
            'value', 'buy_quantity', 'get_quantity', 'valid_from', 'valid_to',
            'min_purchase_amount', 'max_uses', 'current_uses', 'is_exhausted',
            'remaining_uses', 'is_active', 'products', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_uses', 'created_at', 'updated_at']


class PriceCalculationRequestSerializer(serializers.Serializer):
    """Serializer for price calculation request."""
    product_id = serializers.UUIDField(required=True)
    partner_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.DecimalField(
        max_digits=15, decimal_places=3, default=1
    )
    price_list_id = serializers.UUIDField(required=False, allow_null=True)
    promo_code = serializers.CharField(required=False, allow_blank=True)


class PriceBreakdownSerializer(serializers.Serializer):
    """Serializer for price calculation response."""
    base_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    price_list_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, allow_null=True
    )
    customer_discount = serializers.DecimalField(
        max_digits=15, decimal_places=2, allow_null=True
    )
    volume_discount = serializers.DecimalField(
        max_digits=15, decimal_places=2, allow_null=True
    )
    promotion_discount = serializers.DecimalField(
        max_digits=15, decimal_places=2, allow_null=True
    )
    final_unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    final_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    applied_rules = serializers.ListField(child=serializers.DictField())
