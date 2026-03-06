"""Sync views for offline delta and action replay."""
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product, ProductCategory
from apps.core.viewsets import CompanyScopedMixin
from apps.inventory.models import Warehouse, StockLevel, StockMovement
from apps.partners.models import Partner

from .models import SyncActionLog
from .serializers import (
    SyncProductSerializer,
    SyncCategorySerializer,
    SyncWarehouseSerializer,
    SyncStockLevelSerializer,
    SyncPartnerSerializer,
)


class SyncDeltaAPIView(CompanyScopedMixin, APIView):
    """
    GET /api/v1/sync/delta/?since=ISO_TIMESTAMP

    Returns all records updated after `since` for the company.
    If `since` is omitted, returns all data (initial sync).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = self._get_company()
        if not company:
            return Response(
                {'error': 'Aucune entreprise associée'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        since_param = request.query_params.get('since')
        since = parse_datetime(since_param) if since_param else None
        server_time = timezone.now()

        # ---------- live (non-deleted) records ----------
        def qs(model, select=()):
            base = model.objects.filter(company=company)
            if select:
                base = base.select_related(*select)
            if since:
                base = base.filter(updated_at__gt=since)
            return base

        products = qs(Product, ('category', 'unit'))
        categories = qs(ProductCategory, ('parent',))
        warehouses = qs(Warehouse)
        stock_levels = qs(StockLevel, ('product', 'warehouse'))
        partners = qs(Partner)

        # ---------- deleted IDs since last sync ----------
        def deleted_ids(model):
            if not since:
                return []
            return list(
                model.all_objects
                .filter(company=company, is_deleted=True, deleted_at__gt=since)
                .values_list('id', flat=True)
            )

        return Response({
            'server_time': server_time.isoformat(),
            'since': since_param or None,
            'data': {
                'products': SyncProductSerializer(products, many=True).data,
                'categories': SyncCategorySerializer(categories, many=True).data,
                'warehouses': SyncWarehouseSerializer(warehouses, many=True).data,
                'stock_levels': SyncStockLevelSerializer(stock_levels, many=True).data,
                'partners': SyncPartnerSerializer(partners, many=True).data,
            },
            'deleted': {
                'products': deleted_ids(Product),
                'categories': deleted_ids(ProductCategory),
                'warehouses': deleted_ids(Warehouse),
                'stock_levels': deleted_ids(StockLevel),
                'partners': deleted_ids(Partner),
            },
        })


class SyncActionsAPIView(CompanyScopedMixin, APIView):
    """
    POST /api/v1/sync/actions/

    Replay offline actions. Body:
    {
        "actions": [
            {
                "action_id": "<uuid>",
                "type": "create_stock_movement",
                "entity_id": "<uuid>",
                "created_at": "ISO",
                "payload": { ... }
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = self._get_company()
        if not company:
            return Response(
                {'error': 'Aucune entreprise associée'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actions = request.data.get('actions', [])
        if not isinstance(actions, list):
            return Response(
                {'error': 'Le champ actions doit être une liste'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        for action_data in actions:
            result = self._process_action(action_data, company, request.user)
            results.append(result)

        return Response({'results': results})

    # ------------------------------------------------------------------
    def _process_action(self, action_data, company, user):
        action_id = action_data.get('action_id')
        action_type = action_data.get('type', '')
        entity_id = action_data.get('entity_id')
        payload = action_data.get('payload', {})

        # Idempotency check
        existing = SyncActionLog.objects.filter(
            company=company, action_id=action_id,
        ).first()
        if existing:
            return {
                'action_id': str(action_id),
                'status': 'duplicate',
                'entity_id': str(existing.entity_id) if existing.entity_id else None,
            }

        handler = {
            'create_stock_movement': self._handle_create_stock_movement,
        }.get(action_type)

        if handler is None:
            log = SyncActionLog.objects.create(
                company=company,
                user=user,
                action_id=action_id,
                action_type=action_type,
                entity_id=entity_id,
                status='failed',
                error=f"Type d'action inconnu : {action_type}",
                payload=payload,
            )
            return {
                'action_id': str(action_id),
                'status': 'failed',
                'error': log.error,
            }

        return handler(
            action_id=action_id,
            action_type=action_type,
            entity_id=entity_id,
            payload=payload,
            company=company,
            user=user,
        )

    # ------------------------------------------------------------------
    def _handle_create_stock_movement(
        self, *, action_id, action_type, entity_id, payload, company, user
    ):
        try:
            with transaction.atomic():
                # --- validate payload fields ---
                product_id = payload.get('product')
                warehouse_id = payload.get('warehouse')
                movement_type = payload.get('type')
                source = payload.get('source', StockMovement.SOURCE_ADJUSTMENT)
                quantity_raw = payload.get('quantity')
                unit_cost_raw = payload.get('unit_cost', '0')
                reference = payload.get('reference', '')
                notes = payload.get('notes', '')

                if not all([product_id, warehouse_id, movement_type, quantity_raw]):
                    raise ValueError(
                        "Champs requis manquants : product, warehouse, type, quantity"
                    )

                try:
                    quantity = Decimal(str(quantity_raw))
                    unit_cost = Decimal(str(unit_cost_raw))
                except (InvalidOperation, TypeError):
                    raise ValueError("quantity ou unit_cost invalide")

                if quantity <= 0:
                    raise ValueError("La quantité doit être positive")

                # --- validate ownership ---
                product = Product.objects.get(id=product_id, company=company)
                warehouse = Warehouse.objects.get(id=warehouse_id, company=company)

                now = timezone.now()

                # --- create the stock movement with client-provided PK ---
                movement = StockMovement.objects.create(
                    id=entity_id,
                    company=company,
                    type=movement_type,
                    source=source,
                    product=product,
                    warehouse=warehouse,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    reference=reference,
                    date=now,
                    notes=notes,
                    created_by=user,
                )

                # --- update StockLevel ---
                stock_level, created = StockLevel.objects.select_for_update().get_or_create(
                    product=product,
                    warehouse=warehouse,
                    location=None,
                    company=company,
                    defaults={
                        'quantity_on_hand': Decimal('0'),
                        'quantity_reserved': Decimal('0'),
                        'unit_cost': unit_cost,
                    },
                )

                if movement_type == StockMovement.TYPE_IN:
                    # Weighted average cost for incoming stock
                    if not created:
                        old_qty = stock_level.quantity_on_hand
                        old_cost = stock_level.unit_cost
                        new_qty = old_qty + quantity
                        if new_qty > 0:
                            stock_level.unit_cost = (
                                (old_qty * old_cost) + (quantity * unit_cost)
                            ) / new_qty
                    stock_level.quantity_on_hand = F('quantity_on_hand') + quantity
                elif movement_type == StockMovement.TYPE_OUT:
                    stock_level.quantity_on_hand = F('quantity_on_hand') - quantity
                elif movement_type == StockMovement.TYPE_ADJUSTMENT:
                    stock_level.quantity_on_hand = F('quantity_on_hand') + quantity
                else:
                    raise ValueError(f"Type de mouvement non géré : {movement_type}")

                stock_level.last_movement_date = now
                stock_level.save(
                    update_fields=['quantity_on_hand', 'unit_cost', 'last_movement_date', 'updated_at']
                )

                # --- log success ---
                SyncActionLog.objects.create(
                    company=company,
                    user=user,
                    action_id=action_id,
                    action_type=action_type,
                    entity_id=entity_id,
                    status='applied',
                    payload=payload,
                    applied_at=now,
                )

                return {
                    'action_id': str(action_id),
                    'status': 'applied',
                    'entity_id': str(entity_id),
                }

        except Exception as exc:
            # Log the failure outside the rolled-back transaction
            SyncActionLog.objects.create(
                company=company,
                user=user,
                action_id=action_id,
                action_type=action_type,
                entity_id=entity_id,
                status='failed',
                error=str(exc),
                payload=payload,
            )
            return {
                'action_id': str(action_id),
                'status': 'failed',
                'error': str(exc),
            }
