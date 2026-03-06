"""
Inventory views - ViewSets for stock management.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models, transaction
from django.db.models import Sum, F
from django_filters import rest_framework as filters
from apps.core.viewsets import CompanyScopedViewSet, BulkActionMixin, StatusTransitionMixin
from .models import (
    Warehouse, WarehouseLocation, StockLevel, StockMovement,
    StockAdjustment, StockAdjustmentLine, LotSerial
)
from .serializers import (
    WarehouseSerializer, WarehouseLocationSerializer, StockLevelSerializer,
    StockMovementSerializer, StockAdjustmentSerializer, StockAdjustmentCreateSerializer,
    StockAdjustmentLineSerializer, LotSerialSerializer,
    StockTransferSerializer, StockReservationSerializer
)
from .services import StockService


class WarehouseFilter(filters.FilterSet):
    """Filter for Warehouse."""
    is_active = filters.BooleanFilter()
    search = filters.CharFilter(method='filter_search')

    class Meta:
        model = Warehouse
        fields = ['is_active']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            models.Q(code__icontains=value) |
            models.Q(name__icontains=value) |
            models.Q(address_city__icontains=value)
        )


class WarehouseViewSet(CompanyScopedViewSet, BulkActionMixin):
    """ViewSet for Warehouse CRUD operations."""
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    filterset_class = WarehouseFilter
    search_fields = ['code', 'name', 'address_city']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def locations(self, request, pk=None):
        """Get all locations for a warehouse."""
        warehouse = self.get_object()
        locations = WarehouseLocation.objects.filter(
            warehouse=warehouse,
            is_active=True
        )
        serializer = WarehouseLocationSerializer(locations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def stock_summary(self, request, pk=None):
        """Get stock summary for a warehouse."""
        warehouse = self.get_object()
        stock_levels = StockLevel.objects.filter(warehouse=warehouse)

        summary = stock_levels.aggregate(
            total_products=Sum('id'),
            total_on_hand=Sum('quantity_on_hand'),
            total_reserved=Sum('quantity_reserved'),
            total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
        )

        return Response({
            'warehouse': WarehouseSerializer(warehouse).data,
            'total_products': stock_levels.count(),
            'total_on_hand': summary['total_on_hand'] or 0,
            'total_reserved': summary['total_reserved'] or 0,
            'total_value': summary['total_value'] or 0
        })


class WarehouseLocationViewSet(CompanyScopedViewSet):
    """ViewSet for WarehouseLocation CRUD operations."""
    queryset = WarehouseLocation.objects.all()
    serializer_class = WarehouseLocationSerializer
    filterset_fields = ['warehouse', 'parent', 'is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'warehouse']
    ordering = ['warehouse', 'code']


class StockLevelFilter(filters.FilterSet):
    """Filter for StockLevel."""
    warehouse = filters.UUIDFilter()
    product = filters.UUIDFilter()
    location = filters.UUIDFilter()
    low_stock = filters.BooleanFilter(method='filter_low_stock')
    has_stock = filters.BooleanFilter(method='filter_has_stock')

    class Meta:
        model = StockLevel
        fields = ['warehouse', 'product', 'location']

    def filter_low_stock(self, queryset, name, value):
        if value:
            return queryset.filter(
                quantity_on_hand__lte=F('product__min_stock')
            )
        return queryset

    def filter_has_stock(self, queryset, name, value):
        if value:
            return queryset.filter(quantity_on_hand__gt=0)
        return queryset.filter(quantity_on_hand__lte=0)


class StockLevelViewSet(CompanyScopedViewSet):
    """ViewSet for StockLevel queries."""
    queryset = StockLevel.objects.select_related(
        'product', 'warehouse', 'location'
    )
    serializer_class = StockLevelSerializer
    filterset_class = StockLevelFilter
    search_fields = ['product__code', 'product__name', 'warehouse__name']
    ordering_fields = ['quantity_on_hand', 'quantity_reserved', 'last_movement_date']
    ordering = ['-last_movement_date']
    http_method_names = ['get', 'head', 'options']

    @action(detail=False, methods=['get'])
    def by_product(self, request):
        """Get stock levels grouped by product."""
        product_id = request.query_params.get('product')
        if not product_id:
            return Response(
                {'error': 'Paramètre product requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stock = StockService.get_available_stock(
            product_id=product_id,
            warehouse=request.query_params.get('warehouse')
        )
        return Response(stock)

    @action(detail=False, methods=['get'])
    def low_stock_alerts(self, request):
        """Get products with stock below minimum."""
        queryset = self.get_queryset().filter(
            quantity_on_hand__lte=F('product__min_stock'),
            product__is_stockable=True
        ).select_related('product', 'warehouse')

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def reserve(self, request):
        """Reserve stock for a product."""
        serializer = StockReservationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from apps.catalog.models import Product
            product = Product.objects.get(id=serializer.validated_data['product'])
            warehouse = Warehouse.objects.get(id=serializer.validated_data['warehouse'])

            stock_level = StockService.reserve_stock(
                product=product,
                warehouse=warehouse,
                quantity=serializer.validated_data['quantity']
            )
            return Response(StockLevelSerializer(stock_level).data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def alerts_dashboard(self, request):
        """Get comprehensive alerts dashboard data."""
        from .alerts import AlertService
        company = self._get_company()
        if not company:
            return Response({'error': 'Aucune entreprise'}, status=status.HTTP_400_BAD_REQUEST)

        days = int(request.query_params.get('days', 30))
        low_stock = AlertService.get_low_stock_products(company)
        expiring = AlertService.get_expiring_lots(company, days=days)
        expired = AlertService.get_expired_lots(company)

        low_stock_msg = AlertService.build_low_stock_message(low_stock)
        expiry_msg = AlertService.build_expiry_message(expiring, expired)

        whatsapp_phone = company.whatsapp_phone
        whatsapp_urls = {}
        if whatsapp_phone:
            if low_stock_msg:
                whatsapp_urls['low_stock'] = AlertService.get_whatsapp_url(whatsapp_phone, low_stock_msg)
            if expiry_msg:
                whatsapp_urls['expiry'] = AlertService.get_whatsapp_url(whatsapp_phone, expiry_msg)

        return Response({
            'low_stock': {
                'count': low_stock.count(),
                'items': StockLevelSerializer(low_stock[:50], many=True).data,
            },
            'expiring_lots': {
                'count': expiring.count(),
                'items': LotSerialSerializer(expiring[:50], many=True).data,
            },
            'expired_lots': {
                'count': expired.count(),
                'items': LotSerialSerializer(expired[:50], many=True).data,
            },
            'whatsapp_phone': whatsapp_phone or '',
            'whatsapp_urls': whatsapp_urls,
        })

    @action(detail=False, methods=['post'])
    def send_whatsapp_alert(self, request):
        """Generate WhatsApp alert URL."""
        from .alerts import AlertService
        company = self._get_company()
        if not company:
            return Response({'error': 'Aucune entreprise'}, status=status.HTTP_400_BAD_REQUEST)

        alert_type = request.data.get('type', 'all')
        phone = request.data.get('phone') or company.whatsapp_phone
        if not phone:
            return Response({'error': 'Aucun numéro WhatsApp configuré'}, status=status.HTTP_400_BAD_REQUEST)

        messages = []
        if alert_type in ('low_stock', 'all'):
            msg = AlertService.build_low_stock_message(AlertService.get_low_stock_products(company))
            if msg:
                messages.append(msg)
        if alert_type in ('expiry', 'all'):
            msg = AlertService.build_expiry_message(
                AlertService.get_expiring_lots(company),
                AlertService.get_expired_lots(company),
            )
            if msg:
                messages.append(msg)

        if not messages:
            return Response({'message': 'Aucune alerte à envoyer'})

        full_message = "\n\n".join(messages)
        return Response({
            'whatsapp_url': AlertService.get_whatsapp_url(phone, full_message),
            'message': full_message,
            'phone': phone,
        })

    @action(detail=False, methods=['post'])
    def release(self, request):
        """Release reserved stock."""
        serializer = StockReservationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from apps.catalog.models import Product
            product = Product.objects.get(id=serializer.validated_data['product'])
            warehouse = Warehouse.objects.get(id=serializer.validated_data['warehouse'])

            stock_level = StockService.release_stock(
                product=product,
                warehouse=warehouse,
                quantity=serializer.validated_data['quantity']
            )
            return Response(StockLevelSerializer(stock_level).data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StockMovementFilter(filters.FilterSet):
    """Filter for StockMovement."""
    warehouse = filters.UUIDFilter()
    product = filters.UUIDFilter()
    type = filters.ChoiceFilter(choices=StockMovement.TYPE_CHOICES)
    source = filters.ChoiceFilter(choices=StockMovement.SOURCE_CHOICES)
    date_from = filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = filters.DateFilter(field_name='date', lookup_expr='lte')
    reference_type = filters.CharFilter()
    reference_id = filters.UUIDFilter()

    class Meta:
        model = StockMovement
        fields = ['warehouse', 'product', 'type', 'source']


class StockMovementViewSet(CompanyScopedViewSet):
    """ViewSet for StockMovement queries and creation."""
    queryset = StockMovement.objects.select_related(
        'product', 'warehouse', 'source_warehouse', 'location', 'created_by'
    )
    serializer_class = StockMovementSerializer
    filterset_class = StockMovementFilter
    search_fields = ['product__code', 'product__name', 'reference', 'notes']
    ordering_fields = ['date', 'quantity', 'created_at']
    ordering = ['-date', '-created_at']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.company,
            created_by=self.request.user
        )

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def transfer(self, request):
        """Transfer stock between warehouses."""
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from apps.catalog.models import Product
            data = serializer.validated_data

            product = Product.objects.get(id=data['product'])
            from_warehouse = Warehouse.objects.get(id=data['from_warehouse'])
            to_warehouse = Warehouse.objects.get(id=data['to_warehouse'])

            from_location = None
            to_location = None
            if data.get('from_location'):
                from_location = WarehouseLocation.objects.get(id=data['from_location'])
            if data.get('to_location'):
                to_location = WarehouseLocation.objects.get(id=data['to_location'])

            movement_out, movement_in = StockService.move_stock(
                product=product,
                from_warehouse=from_warehouse,
                to_warehouse=to_warehouse,
                quantity=data['quantity'],
                from_location=from_location,
                to_location=to_location,
                user=request.user,
                notes=data.get('notes')
            )

            return Response({
                'success': True,
                'movement_out': StockMovementSerializer(movement_out).data,
                'movement_in': StockMovementSerializer(movement_in).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def by_reference(self, request):
        """Get movements by reference document."""
        reference_type = request.query_params.get('reference_type')
        reference_id = request.query_params.get('reference_id')

        if not reference_type or not reference_id:
            return Response(
                {'error': 'Paramètres reference_type et reference_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(
            reference_type=reference_type,
            reference_id=reference_id
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class StockAdjustmentViewSet(CompanyScopedViewSet, StatusTransitionMixin):
    """ViewSet for StockAdjustment operations."""
    queryset = StockAdjustment.objects.prefetch_related('lines').select_related('warehouse')
    serializer_class = StockAdjustmentSerializer
    filterset_fields = ['warehouse', 'adjustment_type', 'status']
    search_fields = ['reference', 'notes']
    ordering_fields = ['date', 'created_at', 'reference']
    ordering = ['-date', '-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return StockAdjustmentCreateSerializer
        return StockAdjustmentSerializer

    def get_allowed_transitions(self, current_status):
        if current_status == StockAdjustment.STATUS_DRAFT:
            return [StockAdjustment.STATUS_CONFIRMED]
        return []

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def confirm(self, request, pk=None):
        """Confirm adjustment and apply stock changes."""
        adjustment = self.get_object()

        try:
            adjustment = StockService.confirm_adjustment(
                adjustment=adjustment,
                user=request.user
            )
            return Response(StockAdjustmentSerializer(adjustment).data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def add_line(self, request, pk=None):
        """Add a line to the adjustment."""
        adjustment = self.get_object()

        if adjustment.is_confirmed:
            return Response(
                {'error': "Impossible d'ajouter une ligne à un ajustement confirmé"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = StockAdjustmentLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(adjustment=adjustment, company=adjustment.company)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def prefill_from_stock(self, request, pk=None):
        """Prefill adjustment lines from current stock levels."""
        adjustment = self.get_object()

        if adjustment.is_confirmed:
            return Response(
                {'error': "Ajustement déjà confirmé"},
                status=status.HTTP_400_BAD_REQUEST
            )

        stock_levels = StockLevel.objects.filter(
            warehouse=adjustment.warehouse,
            quantity_on_hand__gt=0
        ).select_related('product')

        lines_data = []
        for level in stock_levels:
            lines_data.append({
                'product': level.product.id,
                'product_code': level.product.code,
                'product_name': level.product.name,
                'location': level.location_id,
                'system_quantity': level.quantity_on_hand,
                'counted_quantity': level.quantity_on_hand,
                'unit_cost': level.unit_cost
            })

        return Response(lines_data)


class StockAdjustmentLineViewSet(CompanyScopedViewSet):
    """ViewSet for StockAdjustmentLine operations."""
    queryset = StockAdjustmentLine.objects.select_related('product', 'location', 'adjustment')
    serializer_class = StockAdjustmentLineSerializer
    filterset_fields = ['adjustment', 'product']
    ordering = ['product__code']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.adjustment.is_confirmed:
            return Response(
                {'error': "Impossible de supprimer une ligne d'un ajustement confirmé"},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class LotSerialFilter(filters.FilterSet):
    """Filter for LotSerial."""
    product = filters.UUIDFilter()
    warehouse = filters.UUIDFilter()
    lot_number = filters.CharFilter(lookup_expr='icontains')
    serial_number = filters.CharFilter(lookup_expr='icontains')
    expired = filters.BooleanFilter(method='filter_expired')
    expiring_soon = filters.NumberFilter(method='filter_expiring_soon')

    class Meta:
        model = LotSerial
        fields = ['product', 'warehouse', 'lot_number', 'serial_number']

    def filter_expired(self, queryset, name, value):
        from django.utils import timezone
        today = timezone.now().date()
        if value:
            return queryset.filter(expiry_date__lt=today)
        return queryset.filter(expiry_date__gte=today)

    def filter_expiring_soon(self, queryset, name, value):
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        future_date = today + timedelta(days=value)
        return queryset.filter(
            expiry_date__gte=today,
            expiry_date__lte=future_date
        )


class LotSerialViewSet(CompanyScopedViewSet):
    """ViewSet for LotSerial operations."""
    queryset = LotSerial.objects.select_related('product', 'warehouse', 'location')
    serializer_class = LotSerialSerializer
    filterset_class = LotSerialFilter
    search_fields = ['lot_number', 'serial_number', 'product__code', 'product__name']
    ordering_fields = ['expiry_date', 'created_at', 'lot_number', 'serial_number']
    ordering = ['expiry_date', '-created_at']

    @action(detail=False, methods=['get'])
    def expiring(self, request):
        """Get lots expiring within specified days (default 30)."""
        from django.utils import timezone
        from datetime import timedelta

        days = int(request.query_params.get('days', 30))
        today = timezone.now().date()
        future_date = today + timedelta(days=days)

        queryset = self.get_queryset().filter(
            expiry_date__gte=today,
            expiry_date__lte=future_date,
            quantity__gt=0
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def expired(self, request):
        """Get expired lots with remaining stock."""
        from django.utils import timezone
        today = timezone.now().date()

        queryset = self.get_queryset().filter(
            expiry_date__lt=today,
            quantity__gt=0
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
