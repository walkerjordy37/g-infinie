"""
Pricing views.
"""
from decimal import Decimal
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import Product
from apps.partners.models import Partner

from .models import (
    PriceList,
    PriceListItem,
    CustomerPriceRule,
    VolumeDiscount,
    Promotion,
    PromotionProduct,
)
from .serializers import (
    PriceListSerializer,
    PriceListDetailSerializer,
    PriceListItemSerializer,
    CustomerPriceRuleSerializer,
    VolumeDiscountSerializer,
    PromotionSerializer,
    PromotionDetailSerializer,
    PromotionProductSerializer,
    PriceCalculationRequestSerializer,
    PriceBreakdownSerializer,
)
from .services import PricingService


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


class PriceListViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for PriceList."""
    queryset = PriceList.objects.select_related('currency')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_default', 'is_active', 'currency']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'is_default', 'created_at']
    ordering = ['-is_default', 'name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PriceListDetailSerializer
        return PriceListSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """List only active and valid price lists."""
        today = timezone.now().date()
        qs = self.get_queryset().filter(
            is_active=True
        ).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today)
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=today)
        )
        serializer = PriceListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this price list as default."""
        obj = self.get_object()
        PriceList.objects.filter(company=obj.company).update(is_default=False)
        obj.is_default = True
        obj.save(update_fields=['is_default'])
        return Response({'status': 'default'})

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate this price list with all items."""
        obj = self.get_object()
        new_code = f"{obj.code}_COPY"
        counter = 1
        while PriceList.objects.filter(company=obj.company, code=new_code).exists():
            new_code = f"{obj.code}_COPY{counter}"
            counter += 1

        new_list = PriceList.objects.create(
            company=obj.company,
            code=new_code,
            name=f"{obj.name} (Copie)",
            description=obj.description,
            currency=obj.currency,
            is_default=False,
            is_active=False,
            valid_from=obj.valid_from,
            valid_to=obj.valid_to
        )

        for item in obj.items.all():
            PriceListItem.objects.create(
                company=obj.company,
                price_list=new_list,
                product=item.product,
                min_quantity=item.min_quantity,
                unit_price=item.unit_price
            )

        serializer = PriceListDetailSerializer(new_list)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PriceListItemViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for PriceListItem."""
    queryset = PriceListItem.objects.select_related('price_list', 'product')
    serializer_class = PriceListItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['price_list', 'product']
    search_fields = ['product__code', 'product__name']
    ordering_fields = ['price_list', 'product', 'min_quantity', 'unit_price']
    ordering = ['price_list', 'product', 'min_quantity']

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create price list items."""
        items_data = request.data.get('items', [])
        price_list_id = request.data.get('price_list_id')

        if not price_list_id:
            return Response(
                {'error': 'price_list_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            price_list = PriceList.objects.get(
                id=price_list_id,
                company=self._get_company()
            )
        except PriceList.DoesNotExist:
            return Response(
                {'error': 'Liste de prix non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )

        created = 0
        updated = 0
        errors = []

        for item in items_data:
            try:
                obj, was_created = PriceListItem.objects.update_or_create(
                    company=self._get_company(),
                    price_list=price_list,
                    product_id=item['product_id'],
                    min_quantity=item.get('min_quantity', 1),
                    defaults={'unit_price': item['unit_price']}
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append({
                    'product_id': item.get('product_id'),
                    'error': str(e)
                })

        return Response({
            'created': created,
            'updated': updated,
            'errors': errors
        })


class CustomerPriceRuleViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for CustomerPriceRule."""
    queryset = CustomerPriceRule.objects.select_related('partner', 'product', 'category')
    serializer_class = CustomerPriceRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['partner', 'product', 'category', 'discount_type', 'is_active']
    search_fields = ['partner__name', 'product__name', 'category__name']
    ordering_fields = ['partner', 'priority', 'discount_value', 'created_at']
    ordering = ['partner', 'priority']

    @action(detail=False, methods=['get'])
    def by_partner(self, request):
        """Get rules for a specific partner."""
        partner_id = request.query_params.get('partner_id')
        if not partner_id:
            return Response(
                {'error': 'partner_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        today = timezone.now().date()
        qs = self.get_queryset().filter(
            partner_id=partner_id,
            is_active=True
        ).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today)
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=today)
        )
        serializer = CustomerPriceRuleSerializer(qs, many=True)
        return Response(serializer.data)


class VolumeDiscountViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for VolumeDiscount."""
    queryset = VolumeDiscount.objects.select_related('product')
    serializer_class = VolumeDiscountSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'discount_type', 'is_active']
    search_fields = ['product__code', 'product__name']
    ordering_fields = ['product', 'min_quantity', 'discount_value', 'created_at']
    ordering = ['product', 'min_quantity']

    @action(detail=False, methods=['get'])
    def by_product(self, request):
        """Get volume discounts for a specific product."""
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response(
                {'error': 'product_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        qs = self.get_queryset().filter(
            product_id=product_id,
            is_active=True
        ).order_by('min_quantity')
        serializer = VolumeDiscountSerializer(qs, many=True)
        return Response(serializer.data)


class PromotionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for Promotion."""
    queryset = Promotion.objects.prefetch_related('products', 'products__product')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'is_active']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'name', 'valid_from', 'valid_to', 'created_at']
    ordering = ['-valid_from', 'name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PromotionDetailSerializer
        return PromotionSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """List only active and valid promotions."""
        now = timezone.now()
        qs = self.get_queryset().filter(
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
        serializer = PromotionSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def validate_code(self, request):
        """Validate a promotion code."""
        code = request.data.get('code')
        purchase_amount = request.data.get('purchase_amount')

        if not code:
            return Response(
                {'error': 'code requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = PricingService(self._get_company())
        amount = Decimal(str(purchase_amount)) if purchase_amount else None
        result = service.validate_promo_code(code, amount)

        if result['valid']:
            return Response(result)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_products(self, request, pk=None):
        """Add products to promotion."""
        promotion = self.get_object()
        product_ids = request.data.get('product_ids', [])

        added = 0
        for product_id in product_ids:
            _, created = PromotionProduct.objects.get_or_create(
                company=self._get_company(),
                promotion=promotion,
                product_id=product_id
            )
            if created:
                added += 1

        return Response({'added': added})

    @action(detail=True, methods=['post'])
    def remove_products(self, request, pk=None):
        """Remove products from promotion."""
        promotion = self.get_object()
        product_ids = request.data.get('product_ids', [])

        deleted, _ = PromotionProduct.objects.filter(
            promotion=promotion,
            product_id__in=product_ids
        ).delete()

        return Response({'removed': deleted})


class PromotionProductViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for PromotionProduct."""
    queryset = PromotionProduct.objects.select_related('promotion', 'product')
    serializer_class = PromotionProductSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['promotion', 'product']
    search_fields = ['product__code', 'product__name', 'promotion__code']
    ordering = ['promotion', 'product']


class PriceCalculationViewSet(CompanyScopedMixin, viewsets.ViewSet):
    """ViewSet for price calculation."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """Calculate price for a product."""
        serializer = PriceCalculationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            product = Product.objects.get(
                id=data['product_id'],
                company=self._get_company()
            )
        except Product.DoesNotExist:
            return Response(
                {'error': 'Produit non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )

        partner = None
        if data.get('partner_id'):
            try:
                partner = Partner.objects.get(
                    id=data['partner_id'],
                    company=self._get_company()
                )
            except Partner.DoesNotExist:
                return Response(
                    {'error': 'Partenaire non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )

        price_list = None
        if data.get('price_list_id'):
            try:
                price_list = PriceList.objects.get(
                    id=data['price_list_id'],
                    company=self._get_company()
                )
            except PriceList.DoesNotExist:
                return Response(
                    {'error': 'Liste de prix non trouvée'},
                    status=status.HTTP_404_NOT_FOUND
                )

        service = PricingService(self._get_company())
        breakdown = service.calculate_price(
            product=product,
            quantity=data.get('quantity', Decimal('1')),
            partner=partner,
            price_list=price_list,
            promo_code=data.get('promo_code')
        )

        response_serializer = PriceBreakdownSerializer({
            'base_price': breakdown.base_price,
            'price_list_price': breakdown.price_list_price,
            'customer_discount': breakdown.customer_discount,
            'volume_discount': breakdown.volume_discount,
            'promotion_discount': breakdown.promotion_discount,
            'final_unit_price': breakdown.final_unit_price,
            'final_total': breakdown.final_total,
            'applied_rules': breakdown.applied_rules
        })

        return Response(response_serializer.data)

    @action(detail=False, methods=['post'])
    def calculate_bulk(self, request):
        """Calculate prices for multiple products."""
        items = request.data.get('items', [])
        partner_id = request.data.get('partner_id')
        price_list_id = request.data.get('price_list_id')
        promo_code = request.data.get('promo_code')

        partner = None
        if partner_id:
            try:
                partner = Partner.objects.get(
                    id=partner_id,
                    company=self._get_company()
                )
            except Partner.DoesNotExist:
                return Response(
                    {'error': 'Partenaire non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )

        price_list = None
        if price_list_id:
            try:
                price_list = PriceList.objects.get(
                    id=price_list_id,
                    company=self._get_company()
                )
            except PriceList.DoesNotExist:
                return Response(
                    {'error': 'Liste de prix non trouvée'},
                    status=status.HTTP_404_NOT_FOUND
                )

        service = PricingService(self._get_company())
        results = []

        for item in items:
            try:
                product = Product.objects.get(
                    id=item['product_id'],
                    company=self._get_company()
                )
                quantity = Decimal(str(item.get('quantity', 1)))

                breakdown = service.calculate_price(
                    product=product,
                    quantity=quantity,
                    partner=partner,
                    price_list=price_list,
                    promo_code=promo_code
                )

                results.append({
                    'product_id': str(product.id),
                    'product_code': product.code,
                    'product_name': product.name,
                    'quantity': str(quantity),
                    'base_price': str(breakdown.base_price),
                    'final_unit_price': str(breakdown.final_unit_price),
                    'final_total': str(breakdown.final_total),
                    'applied_rules': breakdown.applied_rules
                })
            except Product.DoesNotExist:
                results.append({
                    'product_id': item.get('product_id'),
                    'error': 'Produit non trouvé'
                })

        return Response({'results': results})
