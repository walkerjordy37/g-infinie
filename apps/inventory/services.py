"""
Inventory services - Business logic for stock operations.
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, F, Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import (
    Warehouse, StockLevel, StockMovement, StockAdjustment,
    StockAdjustmentLine
)


class StockService:
    """Service for stock management operations."""

    @staticmethod
    @transaction.atomic
    def reserve_stock(product, warehouse, quantity, location=None,
                      reference=None, reference_type=None, reference_id=None):
        """
        Reserve stock for a product in a warehouse.
        Returns True if reservation successful, False otherwise.
        """
        stock_level = StockLevel.objects.select_for_update().filter(
            product=product,
            warehouse=warehouse,
            location=location
        ).first()

        if not stock_level:
            raise ValidationError(
                f"Aucun stock trouvé pour {product.code} dans {warehouse.code}"
            )

        available = stock_level.quantity_on_hand - stock_level.quantity_reserved
        if available < quantity:
            raise ValidationError(
                f"Stock insuffisant. Disponible: {available}, Demandé: {quantity}"
            )

        stock_level.quantity_reserved = F('quantity_reserved') + quantity
        stock_level.save(update_fields=['quantity_reserved', 'updated_at'])
        stock_level.refresh_from_db()

        return stock_level

    @staticmethod
    @transaction.atomic
    def release_stock(product, warehouse, quantity, location=None):
        """
        Release previously reserved stock.
        """
        stock_level = StockLevel.objects.select_for_update().filter(
            product=product,
            warehouse=warehouse,
            location=location
        ).first()

        if not stock_level:
            raise ValidationError(
                f"Aucun stock trouvé pour {product.code} dans {warehouse.code}"
            )

        if stock_level.quantity_reserved < quantity:
            raise ValidationError(
                f"Quantité réservée insuffisante. "
                f"Réservée: {stock_level.quantity_reserved}, Demandée: {quantity}"
            )

        stock_level.quantity_reserved = F('quantity_reserved') - quantity
        stock_level.save(update_fields=['quantity_reserved', 'updated_at'])
        stock_level.refresh_from_db()

        return stock_level

    @staticmethod
    @transaction.atomic
    def move_stock(product, from_warehouse, to_warehouse, quantity,
                   from_location=None, to_location=None, user=None,
                   notes=None, unit_cost=None):
        """
        Transfer stock between warehouses or locations.
        Creates appropriate stock movements and updates levels.
        """
        now = timezone.now()
        company = product.company

        source_level = StockLevel.objects.select_for_update().filter(
            product=product,
            warehouse=from_warehouse,
            location=from_location
        ).first()

        if not source_level:
            raise ValidationError(
                f"Aucun stock trouvé pour {product.code} dans {from_warehouse.code}"
            )

        if source_level.quantity_available < quantity:
            raise ValidationError(
                f"Stock disponible insuffisant. "
                f"Disponible: {source_level.quantity_available}, Demandé: {quantity}"
            )

        if unit_cost is None:
            unit_cost = source_level.unit_cost

        source_level.quantity_on_hand = F('quantity_on_hand') - quantity
        source_level.last_movement_date = now
        source_level.save(update_fields=['quantity_on_hand', 'last_movement_date', 'updated_at'])

        dest_level, created = StockLevel.objects.select_for_update().get_or_create(
            product=product,
            warehouse=to_warehouse,
            location=to_location,
            company=company,
            defaults={
                'quantity_on_hand': Decimal('0'),
                'quantity_reserved': Decimal('0'),
                'unit_cost': unit_cost
            }
        )

        if not created:
            old_qty = dest_level.quantity_on_hand
            old_cost = dest_level.unit_cost
            new_qty = old_qty + quantity
            if new_qty > 0:
                dest_level.unit_cost = (
                    (old_qty * old_cost) + (quantity * unit_cost)
                ) / new_qty

        dest_level.quantity_on_hand = F('quantity_on_hand') + quantity
        dest_level.last_movement_date = now
        dest_level.save(update_fields=['quantity_on_hand', 'unit_cost', 'last_movement_date', 'updated_at'])

        movement_out = StockMovement.objects.create(
            company=company,
            type=StockMovement.TYPE_TRANSFER,
            source=StockMovement.SOURCE_TRANSFER,
            product=product,
            warehouse=from_warehouse,
            source_warehouse=None,
            location=from_location,
            quantity=quantity,
            unit_cost=unit_cost,
            date=now,
            notes=notes or f"Transfert vers {to_warehouse.code}",
            created_by=user
        )

        movement_in = StockMovement.objects.create(
            company=company,
            type=StockMovement.TYPE_TRANSFER,
            source=StockMovement.SOURCE_TRANSFER,
            product=product,
            warehouse=to_warehouse,
            source_warehouse=from_warehouse,
            location=to_location,
            quantity=quantity,
            unit_cost=unit_cost,
            date=now,
            notes=notes or f"Transfert depuis {from_warehouse.code}",
            created_by=user
        )

        return movement_out, movement_in

    @staticmethod
    @transaction.atomic
    def adjust_stock(product, warehouse, quantity, reason, location=None,
                     user=None, unit_cost=None, notes=None):
        """
        Adjust stock quantity (positive to add, negative to remove).
        """
        now = timezone.now()
        company = product.company

        stock_level, created = StockLevel.objects.select_for_update().get_or_create(
            product=product,
            warehouse=warehouse,
            location=location,
            company=company,
            defaults={
                'quantity_on_hand': Decimal('0'),
                'quantity_reserved': Decimal('0'),
                'unit_cost': unit_cost or product.purchase_price
            }
        )

        if quantity < 0 and stock_level.quantity_available < abs(quantity):
            raise ValidationError(
                f"Stock disponible insuffisant pour l'ajustement. "
                f"Disponible: {stock_level.quantity_available}, Ajustement: {quantity}"
            )

        if unit_cost is None:
            unit_cost = stock_level.unit_cost or product.purchase_price

        if quantity > 0 and not created:
            old_qty = stock_level.quantity_on_hand
            old_cost = stock_level.unit_cost
            new_qty = old_qty + quantity
            if new_qty > 0:
                stock_level.unit_cost = (
                    (old_qty * old_cost) + (quantity * unit_cost)
                ) / new_qty

        stock_level.quantity_on_hand = F('quantity_on_hand') + quantity
        stock_level.last_movement_date = now
        stock_level.save(update_fields=['quantity_on_hand', 'unit_cost', 'last_movement_date', 'updated_at'])

        movement_type = StockMovement.TYPE_IN if quantity > 0 else StockMovement.TYPE_OUT

        movement = StockMovement.objects.create(
            company=company,
            type=movement_type,
            source=StockMovement.SOURCE_ADJUSTMENT,
            product=product,
            warehouse=warehouse,
            location=location,
            quantity=abs(quantity),
            unit_cost=unit_cost,
            date=now,
            notes=notes or f"Ajustement: {reason}",
            created_by=user
        )

        stock_level.refresh_from_db()
        return stock_level, movement

    @staticmethod
    def get_available_stock(product, warehouse=None, location=None):
        """
        Get available stock for a product.
        If warehouse is None, returns total across all warehouses.
        """
        queryset = StockLevel.objects.filter(product=product)

        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)
        if location:
            queryset = queryset.filter(location=location)

        result = queryset.aggregate(
            total_on_hand=Sum('quantity_on_hand'),
            total_reserved=Sum('quantity_reserved')
        )

        on_hand = result['total_on_hand'] or Decimal('0')
        reserved = result['total_reserved'] or Decimal('0')

        return {
            'quantity_on_hand': on_hand,
            'quantity_reserved': reserved,
            'quantity_available': on_hand - reserved
        }

    @staticmethod
    def calculate_valuation(product, method='average', warehouse=None):
        """
        Calculate stock valuation for a product.

        Methods:
        - average: Weighted average cost
        - fifo: First In, First Out
        - lifo: Last In, First Out
        """
        queryset = StockLevel.objects.filter(product=product)
        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)

        if method == 'average':
            result = queryset.aggregate(
                total_qty=Sum('quantity_on_hand'),
                total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
            )
            total_qty = result['total_qty'] or Decimal('0')
            total_value = result['total_value'] or Decimal('0')

            return {
                'method': 'average',
                'total_quantity': total_qty,
                'total_value': total_value,
                'unit_cost': total_value / total_qty if total_qty > 0 else Decimal('0')
            }

        elif method in ['fifo', 'lifo']:
            movements = StockMovement.objects.filter(
                product=product,
                type=StockMovement.TYPE_IN
            )
            if warehouse:
                movements = movements.filter(warehouse=warehouse)

            if method == 'fifo':
                movements = movements.order_by('date', 'created_at')
            else:
                movements = movements.order_by('-date', '-created_at')

            current_stock = StockService.get_available_stock(product, warehouse)
            remaining_qty = current_stock['quantity_on_hand']
            total_value = Decimal('0')
            valued_qty = Decimal('0')

            for movement in movements:
                if remaining_qty <= 0:
                    break
                qty_to_value = min(movement.quantity, remaining_qty)
                total_value += qty_to_value * movement.unit_cost
                valued_qty += qty_to_value
                remaining_qty -= qty_to_value

            return {
                'method': method,
                'total_quantity': valued_qty,
                'total_value': total_value,
                'unit_cost': total_value / valued_qty if valued_qty > 0 else Decimal('0')
            }

        raise ValidationError(f"Méthode de valorisation inconnue: {method}")

    @staticmethod
    @transaction.atomic
    def receive_stock(product, warehouse, quantity, unit_cost,
                      source=StockMovement.SOURCE_PURCHASE,
                      location=None, user=None, reference=None,
                      reference_type=None, reference_id=None,
                      lot_serial=None, notes=None):
        """
        Receive stock into warehouse (from purchase, return, etc.).
        """
        now = timezone.now()
        company = product.company

        stock_level, created = StockLevel.objects.select_for_update().get_or_create(
            product=product,
            warehouse=warehouse,
            location=location,
            company=company,
            defaults={
                'quantity_on_hand': Decimal('0'),
                'quantity_reserved': Decimal('0'),
                'unit_cost': unit_cost
            }
        )

        if not created:
            old_qty = stock_level.quantity_on_hand
            old_cost = stock_level.unit_cost
            new_qty = old_qty + quantity
            if new_qty > 0:
                stock_level.unit_cost = (
                    (old_qty * old_cost) + (quantity * unit_cost)
                ) / new_qty

        stock_level.quantity_on_hand = F('quantity_on_hand') + quantity
        stock_level.last_movement_date = now
        stock_level.save(update_fields=['quantity_on_hand', 'unit_cost', 'last_movement_date', 'updated_at'])

        movement = StockMovement.objects.create(
            company=company,
            type=StockMovement.TYPE_IN,
            source=source,
            product=product,
            warehouse=warehouse,
            location=location,
            quantity=quantity,
            unit_cost=unit_cost,
            reference=reference or '',
            reference_type=reference_type or '',
            reference_id=reference_id,
            date=now,
            notes=notes or '',
            created_by=user,
            lot_serial=lot_serial
        )

        stock_level.refresh_from_db()
        return stock_level, movement

    @staticmethod
    @transaction.atomic
    def ship_stock(product, warehouse, quantity, unit_cost=None,
                   source=StockMovement.SOURCE_SALE,
                   location=None, user=None, reference=None,
                   reference_type=None, reference_id=None,
                   lot_serial=None, notes=None, release_reservation=True):
        """
        Ship stock from warehouse (for sale, return to supplier, etc.).
        """
        now = timezone.now()
        company = product.company

        stock_level = StockLevel.objects.select_for_update().filter(
            product=product,
            warehouse=warehouse,
            location=location
        ).first()

        if not stock_level:
            raise ValidationError(
                f"Aucun stock trouvé pour {product.code} dans {warehouse.code}"
            )

        if stock_level.quantity_available < quantity and not release_reservation:
            raise ValidationError(
                f"Stock disponible insuffisant. "
                f"Disponible: {stock_level.quantity_available}, Demandé: {quantity}"
            )

        if release_reservation:
            if stock_level.quantity_reserved >= quantity:
                stock_level.quantity_reserved = F('quantity_reserved') - quantity
            elif stock_level.quantity_on_hand < quantity:
                raise ValidationError(
                    f"Stock insuffisant. "
                    f"En stock: {stock_level.quantity_on_hand}, Demandé: {quantity}"
                )

        if unit_cost is None:
            unit_cost = stock_level.unit_cost

        stock_level.quantity_on_hand = F('quantity_on_hand') - quantity
        stock_level.last_movement_date = now
        stock_level.save(update_fields=[
            'quantity_on_hand', 'quantity_reserved',
            'last_movement_date', 'updated_at'
        ])

        movement = StockMovement.objects.create(
            company=company,
            type=StockMovement.TYPE_OUT,
            source=source,
            product=product,
            warehouse=warehouse,
            location=location,
            quantity=quantity,
            unit_cost=unit_cost,
            reference=reference or '',
            reference_type=reference_type or '',
            reference_id=reference_id,
            date=now,
            notes=notes or '',
            created_by=user,
            lot_serial=lot_serial
        )

        stock_level.refresh_from_db()
        return stock_level, movement

    @staticmethod
    @transaction.atomic
    def confirm_adjustment(adjustment, user):
        """
        Confirm a stock adjustment and apply all lines.
        """
        if adjustment.is_confirmed:
            raise ValidationError("Cet ajustement est déjà confirmé.")

        now = timezone.now()

        for line in adjustment.lines.all():
            difference = line.difference
            if difference != 0:
                StockService.adjust_stock(
                    product=line.product,
                    warehouse=adjustment.warehouse,
                    quantity=difference,
                    reason=adjustment.get_adjustment_type_display(),
                    location=line.location,
                    user=user,
                    unit_cost=line.unit_cost,
                    notes=f"Ajustement {adjustment.reference}: {line.notes}"
                )

        adjustment.status = StockAdjustment.STATUS_CONFIRMED
        adjustment.confirmed_by = user
        adjustment.confirmed_at = now
        adjustment.save(update_fields=['status', 'confirmed_by', 'confirmed_at', 'updated_at'])

        return adjustment
