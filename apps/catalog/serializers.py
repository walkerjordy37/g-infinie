"""
Catalog serializers.
"""
from rest_framework import serializers
from .models import (
    ProductCategory,
    UnitOfMeasure,
    UnitConversion,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    ProductSupplier,
    ProductImage,
)


class ProductCategorySerializer(serializers.ModelSerializer):
    """Serializer for ProductCategory."""
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    full_path = serializers.CharField(read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = [
            'id', 'code', 'name', 'description', 'parent', 'parent_name',
            'full_path', 'lft', 'rght', 'level', 'image', 'is_active',
            'children_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'lft', 'rght', 'level', 'created_at', 'updated_at']

    def get_children_count(self, obj):
        return obj.children.count()


class ProductCategoryTreeSerializer(serializers.ModelSerializer):
    """Serializer for ProductCategory with nested children."""
    children = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = ['id', 'code', 'name', 'is_active', 'children']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return ProductCategoryTreeSerializer(children, many=True).data


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    """Serializer for UnitOfMeasure."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = UnitOfMeasure
        fields = [
            'id', 'code', 'name', 'type', 'type_display', 'ratio',
            'is_reference', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UnitConversionSerializer(serializers.ModelSerializer):
    """Serializer for UnitConversion."""
    from_unit_name = serializers.CharField(source='from_unit.name', read_only=True)
    to_unit_name = serializers.CharField(source='to_unit.name', read_only=True)

    class Meta:
        model = UnitConversion
        fields = [
            'id', 'from_unit', 'from_unit_name', 'to_unit', 'to_unit_name',
            'factor', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """Serializer for ProductAttributeValue."""
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)

    class Meta:
        model = ProductAttributeValue
        fields = [
            'id', 'attribute', 'attribute_name', 'code', 'name',
            'sequence', 'color_code', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Serializer for ProductAttribute."""
    values = ProductAttributeValueSerializer(many=True, read_only=True)

    class Meta:
        model = ProductAttribute
        fields = [
            'id', 'code', 'name', 'description', 'display_type',
            'is_active', 'values', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for ProductImage."""

    class Meta:
        model = ProductImage
        fields = [
            'id', 'product', 'image', 'name', 'description',
            'sequence', 'is_primary', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductSupplierSerializer(serializers.ModelSerializer):
    """Serializer for ProductSupplier."""
    supplier_display_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = ProductSupplier
        fields = [
            'id', 'product', 'supplier', 'supplier_display_name',
            'supplier_code', 'supplier_name', 'purchase_price',
            'min_quantity', 'lead_time_days', 'is_preferred',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for ProductVariant."""
    attribute_values_display = ProductAttributeValueSerializer(
        source='attribute_values', many=True, read_only=True
    )
    effective_purchase_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    effective_sale_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'code', 'name', 'attribute_values',
            'attribute_values_display', 'barcode', 'image',
            'purchase_price', 'sale_price', 'price_extra',
            'effective_purchase_price', 'effective_sale_price',
            'weight', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer for Product list view."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    variants_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'type', 'type_display', 'code', 'name', 'category',
            'category_name', 'unit', 'unit_name', 'barcode', 'image',
            'purchase_price', 'sale_price', 'tax_rate', 'is_stockable',
            'is_purchasable', 'is_saleable', 'is_active', 'variants_count',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_variants_count(self, obj):
        return obj.variants.count()


class ProductDetailSerializer(serializers.ModelSerializer):
    """Serializer for Product detail view with nested relations."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    valuation_method_display = serializers.CharField(
        source='get_valuation_method_display', read_only=True
    )
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    purchase_unit_name = serializers.CharField(
        source='purchase_unit.name', read_only=True
    )
    sale_unit_name = serializers.CharField(source='sale_unit.name', read_only=True)
    sale_price_ttc = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    margin = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    margin_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    variants = ProductVariantSerializer(many=True, read_only=True)
    suppliers = ProductSupplierSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'type', 'type_display', 'code', 'name', 'description',
            'category', 'category_name', 'unit', 'unit_name',
            'purchase_unit', 'purchase_unit_name', 'sale_unit', 'sale_unit_name',
            'barcode', 'internal_reference', 'image',
            'purchase_price', 'sale_price', 'tax_rate', 'sale_price_ttc',
            'margin', 'margin_percentage',
            'is_stockable', 'min_stock', 'max_stock',
            'valuation_method', 'valuation_method_display',
            'weight', 'volume',
            'is_purchasable', 'is_saleable', 'is_active', 'notes',
            'variants', 'suppliers', 'images',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating Product."""

    class Meta:
        model = Product
        fields = [
            'type', 'code', 'name', 'description', 'category', 'unit',
            'purchase_unit', 'sale_unit', 'barcode', 'internal_reference',
            'image', 'purchase_price', 'sale_price', 'tax_rate',
            'is_stockable', 'min_stock', 'max_stock', 'valuation_method',
            'weight', 'volume', 'is_purchasable', 'is_saleable', 'is_active', 'notes'
        ]

    def validate_code(self, value):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'company'):
            company = request.user.company
        elif request and hasattr(request, 'company'):
            company = request.company
        else:
            return value

        qs = Product.objects.filter(company=company, code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ce code existe déjà.")
        return value

    def validate(self, data):
        if data.get('type') == Product.TYPE_SERVICE:
            data['is_stockable'] = False
        return data


class ProductBulkImportSerializer(serializers.Serializer):
    """Serializer for bulk product import."""
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=255)
    type = serializers.ChoiceField(
        choices=Product.TYPE_CHOICES, default=Product.TYPE_PRODUCT
    )
    category_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    unit_code = serializers.CharField(max_length=20)
    barcode = serializers.CharField(max_length=50, required=False, allow_blank=True)
    purchase_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )
    sale_price = serializers.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)
