"""
Catalog views.
"""
from decimal import Decimal
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Q

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
from .serializers import (
    ProductCategorySerializer,
    ProductCategoryTreeSerializer,
    UnitOfMeasureSerializer,
    UnitConversionSerializer,
    ProductAttributeSerializer,
    ProductAttributeValueSerializer,
    ProductVariantSerializer,
    ProductSupplierSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductWriteSerializer,
    ProductBulkImportSerializer,
)


class CompanyScopedMixin:
    """Mixin to filter queryset by request's company."""

    def _get_company(self):
        """Get company from middleware or resolve from header/user."""
        company = getattr(self.request, 'company', None)
        if company:
            return company
        
        if not self.request.user.is_authenticated:
            return None
        
        company_id = self.request.headers.get('X-Company-ID')
        if not company_id:
            company_id = self.request.GET.get('company_id')
        
        if company_id:
            try:
                membership = self.request.user.memberships.select_related('company').get(
                    company_id=company_id, is_active=True
                )
                self.request.company = membership.company
                return membership.company
            except Exception:
                pass
        
        membership = self.request.user.memberships.select_related('company').filter(
            is_active=True, is_default=True
        ).first() or self.request.user.memberships.select_related('company').filter(
            is_active=True
        ).first()
        
        if membership:
            self.request.company = membership.company
            return membership.company
        return None

    def get_queryset(self):
        qs = super().get_queryset()
        company = self._get_company()
        if company:
            return qs.filter(company=company)
        return qs.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)


class ProductCategoryViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for ProductCategory."""
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['parent', 'is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'lft', 'created_at']
    ordering = ['lft', 'name']

    def get_serializer_class(self):
        if self.action == 'tree':
            return ProductCategoryTreeSerializer
        return ProductCategorySerializer

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get categories as a tree structure."""
        root_categories = self.get_queryset().filter(parent__isnull=True, is_active=True)
        serializer = ProductCategoryTreeSerializer(root_categories, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Bulk activate categories."""
        ids = request.data.get('ids', [])
        count = self.get_queryset().filter(id__in=ids).update(is_active=True)
        return Response({'activated': count})

    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate categories."""
        ids = request.data.get('ids', [])
        count = self.get_queryset().filter(id__in=ids).update(is_active=False)
        return Response({'deactivated': count})


class UnitOfMeasureViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for UnitOfMeasure."""
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'is_reference', 'is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'type']
    ordering = ['type', 'name']

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get units grouped by type."""
        qs = self.get_queryset().filter(is_active=True)
        result = {}
        for unit_type, type_label in UnitOfMeasure.TYPE_CHOICES:
            units = qs.filter(type=unit_type)
            result[unit_type] = {
                'label': type_label,
                'units': UnitOfMeasureSerializer(units, many=True).data
            }
        return Response(result)


class UnitConversionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for UnitConversion."""
    queryset = UnitConversion.objects.select_related('from_unit', 'to_unit')
    serializer_class = UnitConversionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['from_unit', 'to_unit']
    ordering = ['from_unit__name']

    @action(detail=False, methods=['post'])
    def convert(self, request):
        """Convert a quantity between units."""
        from_unit_id = request.data.get('from_unit')
        to_unit_id = request.data.get('to_unit')
        quantity = Decimal(str(request.data.get('quantity', 0)))

        try:
            conversion = self.get_queryset().get(
                from_unit_id=from_unit_id,
                to_unit_id=to_unit_id
            )
            result = conversion.convert(quantity)
            return Response({
                'from_quantity': quantity,
                'to_quantity': result,
                'factor': conversion.factor
            })
        except UnitConversion.DoesNotExist:
            return Response(
                {'error': 'Conversion non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )


class ProductAttributeViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for ProductAttribute."""
    queryset = ProductAttribute.objects.prefetch_related('values')
    serializer_class = ProductAttributeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'display_type']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['name']


class ProductAttributeValueViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for ProductAttributeValue."""
    queryset = ProductAttributeValue.objects.select_related('attribute')
    serializer_class = ProductAttributeValueSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['attribute', 'is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['sequence', 'name', 'created_at']
    ordering = ['attribute', 'sequence', 'name']


class ProductVariantViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for ProductVariant."""
    queryset = ProductVariant.objects.select_related('product').prefetch_related(
        'attribute_values', 'attribute_values__attribute'
    )
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'is_active']
    search_fields = ['code', 'name', 'barcode']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['product', 'name']

    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Bulk activate variants."""
        ids = request.data.get('ids', [])
        count = self.get_queryset().filter(id__in=ids).update(is_active=True)
        return Response({'activated': count})

    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate variants."""
        ids = request.data.get('ids', [])
        count = self.get_queryset().filter(id__in=ids).update(is_active=False)
        return Response({'deactivated': count})


class ProductSupplierViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for ProductSupplier."""
    queryset = ProductSupplier.objects.select_related('product', 'supplier')
    serializer_class = ProductSupplierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'supplier', 'is_preferred']
    search_fields = ['supplier_code', 'supplier_name', 'product__name', 'supplier__name']
    ordering_fields = ['purchase_price', 'lead_time_days', 'created_at']
    ordering = ['-is_preferred', 'supplier__name']

    @action(detail=True, methods=['post'])
    def set_preferred(self, request, pk=None):
        """Set this supplier as preferred for the product."""
        obj = self.get_object()
        ProductSupplier.objects.filter(product=obj.product).update(is_preferred=False)
        obj.is_preferred = True
        obj.save(update_fields=['is_preferred'])
        return Response({'status': 'preferred'})


class ProductImageViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for ProductImage."""
    queryset = ProductImage.objects.select_related('product')
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product', 'is_primary']
    ordering = ['product', '-is_primary', 'sequence']

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set this image as primary for the product."""
        obj = self.get_object()
        ProductImage.objects.filter(product=obj.product).update(is_primary=False)
        obj.is_primary = True
        obj.save(update_fields=['is_primary'])
        return Response({'status': 'primary'})

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reorder images by providing ordered list of IDs."""
        ordered_ids = request.data.get('ids', [])
        for index, image_id in enumerate(ordered_ids):
            ProductImage.objects.filter(id=image_id).update(sequence=index)
        return Response({'reordered': len(ordered_ids)})


class ProductViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for Product."""
    queryset = Product.objects.select_related(
        'category', 'unit', 'purchase_unit', 'sale_unit'
    ).prefetch_related('variants', 'suppliers', 'images')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'type', 'category', 'is_stockable', 'is_purchasable',
        'is_saleable', 'is_active', 'valuation_method'
    ]
    search_fields = ['code', 'name', 'description', 'barcode', 'internal_reference']
    ordering_fields = ['code', 'name', 'purchase_price', 'sale_price', 'created_at']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return ProductWriteSerializer
        if self.action == 'bulk_import':
            return ProductBulkImportSerializer
        return ProductDetailSerializer

    @action(detail=False, methods=['get'])
    def products(self, request):
        """List only products (not services or consumables)."""
        qs = self.filter_queryset(self.get_queryset()).filter(type=Product.TYPE_PRODUCT)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ProductListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def services(self, request):
        """List only services."""
        qs = self.filter_queryset(self.get_queryset()).filter(type=Product.TYPE_SERVICE)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ProductListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def consumables(self, request):
        """List only consumables."""
        qs = self.filter_queryset(self.get_queryset()).filter(type=Product.TYPE_CONSUMABLE)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ProductListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stockable(self, request):
        """List only stockable products."""
        qs = self.filter_queryset(self.get_queryset()).filter(is_stockable=True)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ProductListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """List products with stock below minimum (requires inventory app)."""
        qs = self.get_queryset().filter(is_stockable=True, min_stock__gt=0)
        serializer = ProductListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search_barcode(self, request):
        """Search product by barcode."""
        barcode = request.query_params.get('barcode', '')
        if not barcode:
            return Response(
                {'error': 'Paramètre barcode requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        qs = self.get_queryset().filter(
            Q(barcode=barcode) | Q(variants__barcode=barcode)
        ).distinct()
        
        if not qs.exists():
            return Response(
                {'error': 'Produit non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ProductDetailSerializer(qs.first())
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a product."""
        product = self.get_object()
        product.is_active = True
        product.save(update_fields=['is_active'])
        return Response({'status': 'activated'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a product."""
        product = self.get_object()
        product.is_active = False
        product.save(update_fields=['is_active'])
        return Response({'status': 'deactivated'})

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a product."""
        product = self.get_object()
        new_code = f"{product.code}_COPY"
        counter = 1
        while Product.objects.filter(company=product.company, code=new_code).exists():
            new_code = f"{product.code}_COPY{counter}"
            counter += 1

        new_product = Product.objects.create(
            company=product.company,
            type=product.type,
            code=new_code,
            name=f"{product.name} (Copie)",
            description=product.description,
            category=product.category,
            unit=product.unit,
            purchase_unit=product.purchase_unit,
            sale_unit=product.sale_unit,
            purchase_price=product.purchase_price,
            sale_price=product.sale_price,
            tax_rate=product.tax_rate,
            is_stockable=product.is_stockable,
            min_stock=product.min_stock,
            max_stock=product.max_stock,
            valuation_method=product.valuation_method,
            is_purchasable=product.is_purchasable,
            is_saleable=product.is_saleable,
            is_active=False,
        )

        serializer = ProductDetailSerializer(new_product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Bulk activate products."""
        ids = request.data.get('ids', [])
        count = self.get_queryset().filter(id__in=ids).update(is_active=True)
        return Response({'activated': count})

    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate products."""
        ids = request.data.get('ids', [])
        count = self.get_queryset().filter(id__in=ids).update(is_active=False)
        return Response({'deactivated': count})

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk soft delete products."""
        ids = request.data.get('ids', [])
        qs = self.get_queryset().filter(id__in=ids)
        count = 0
        for product in qs:
            product.soft_delete(user=request.user)
            count += 1
        return Response({'deleted': count})

    @action(detail=False, methods=['post'])
    def bulk_update_category(self, request):
        """Bulk update category for products."""
        ids = request.data.get('ids', [])
        category_id = request.data.get('category_id')
        if not category_id:
            return Response(
                {'error': 'category_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        count = self.get_queryset().filter(id__in=ids).update(category_id=category_id)
        return Response({'updated': count})

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def bulk_import(self, request):
        """Bulk import products from list."""
        serializer = ProductBulkImportSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        company = request.user.company
        created = 0
        updated = 0
        errors = []

        for item in serializer.validated_data:
            try:
                category = None
                if item.get('category_code'):
                    category = ProductCategory.objects.filter(
                        company=company, code=item['category_code']
                    ).first()

                unit = UnitOfMeasure.objects.filter(
                    company=company, code=item['unit_code']
                ).first()
                if not unit:
                    errors.append({
                        'code': item['code'],
                        'error': f"Unité '{item['unit_code']}' non trouvée"
                    })
                    continue

                product, was_created = Product.objects.update_or_create(
                    company=company,
                    code=item['code'],
                    defaults={
                        'name': item['name'],
                        'type': item.get('type', Product.TYPE_PRODUCT),
                        'category': category,
                        'unit': unit,
                        'barcode': item.get('barcode', ''),
                        'purchase_price': item.get('purchase_price', 0),
                        'sale_price': item.get('sale_price', 0),
                        'tax_rate': item.get('tax_rate', 0),
                    }
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append({'code': item['code'], 'error': str(e)})

        return Response({
            'created': created,
            'updated': updated,
            'errors': errors
        })
