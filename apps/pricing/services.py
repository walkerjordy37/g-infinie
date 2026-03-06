"""
Pricing services - Price calculation logic.
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from django.utils import timezone
from django.db.models import Q

from .models import (
    PriceList,
    PriceListItem,
    CustomerPriceRule,
    VolumeDiscount,
    Promotion,
    PromotionProduct,
)


@dataclass
class AppliedRule:
    """Represents an applied pricing rule."""
    type: str
    name: str
    discount_type: str
    discount_value: Decimal
    discount_amount: Decimal


@dataclass
class PriceBreakdown:
    """Result of price calculation."""
    base_price: Decimal
    price_list_price: Optional[Decimal] = None
    customer_discount: Optional[Decimal] = None
    volume_discount: Optional[Decimal] = None
    promotion_discount: Optional[Decimal] = None
    final_unit_price: Decimal = Decimal('0')
    final_total: Decimal = Decimal('0')
    applied_rules: list = field(default_factory=list)


class PricingService:
    """Service for calculating product prices with all applicable discounts."""

    def __init__(self, company):
        self.company = company

    def calculate_price(
        self,
        product,
        quantity: Decimal = Decimal('1'),
        partner=None,
        price_list=None,
        promo_code: str = None
    ) -> PriceBreakdown:
        """
        Calculate the best price for a product considering all pricing rules.

        Args:
            product: Product instance
            quantity: Quantity being purchased
            partner: Partner (customer) instance, optional
            price_list: PriceList instance, optional
            promo_code: Promotion code string, optional

        Returns:
            PriceBreakdown with all applied discounts
        """
        now = timezone.now()
        today = now.date()
        applied_rules = []

        base_price = product.sale_price
        working_price = base_price

        price_list_price = self._get_price_list_price(
            product, quantity, price_list, today
        )
        if price_list_price is not None:
            applied_rules.append({
                'type': 'price_list',
                'name': price_list.name if price_list else 'Liste de prix par défaut',
                'discount_type': 'fixed_price',
                'discount_value': str(price_list_price),
                'discount_amount': str(base_price - price_list_price)
            })
            working_price = price_list_price

        customer_discount_amount = None
        if partner:
            customer_discount_amount = self._get_customer_discount(
                product, partner, working_price, today
            )
            if customer_discount_amount:
                rule_info = customer_discount_amount.pop('rule_info', None)
                discount = customer_discount_amount['discount']
                applied_rules.append({
                    'type': 'customer_rule',
                    'name': f"Remise client: {partner.name}",
                    'discount_type': rule_info['type'] if rule_info else 'unknown',
                    'discount_value': str(rule_info['value']) if rule_info else '0',
                    'discount_amount': str(discount)
                })
                working_price = working_price - discount
                customer_discount_amount = discount

        volume_discount_amount = self._get_volume_discount(
            product, quantity, working_price
        )
        if volume_discount_amount:
            rule_info = volume_discount_amount.pop('rule_info', None)
            discount = volume_discount_amount['discount']
            applied_rules.append({
                'type': 'volume_discount',
                'name': f"Remise volume (qté >= {rule_info['min_qty']})" if rule_info else 'Remise volume',
                'discount_type': rule_info['type'] if rule_info else 'unknown',
                'discount_value': str(rule_info['value']) if rule_info else '0',
                'discount_amount': str(discount)
            })
            working_price = working_price - discount
            volume_discount_amount = discount

        promotion_discount_amount = None
        if promo_code:
            promotion_discount_amount = self._get_promotion_discount(
                product, promo_code, working_price, now
            )
            if promotion_discount_amount:
                rule_info = promotion_discount_amount.pop('rule_info', None)
                discount = promotion_discount_amount['discount']
                applied_rules.append({
                    'type': 'promotion',
                    'name': f"Promotion: {rule_info['name']}" if rule_info else 'Promotion',
                    'discount_type': rule_info['type'] if rule_info else 'unknown',
                    'discount_value': str(rule_info['value']) if rule_info else '0',
                    'discount_amount': str(discount)
                })
                working_price = working_price - discount
                promotion_discount_amount = discount

        final_unit_price = max(Decimal('0'), working_price)
        final_total = final_unit_price * quantity

        return PriceBreakdown(
            base_price=base_price,
            price_list_price=price_list_price,
            customer_discount=customer_discount_amount,
            volume_discount=volume_discount_amount,
            promotion_discount=promotion_discount_amount,
            final_unit_price=final_unit_price,
            final_total=final_total,
            applied_rules=applied_rules
        )

    def _get_price_list_price(
        self,
        product,
        quantity: Decimal,
        price_list,
        today
    ) -> Optional[Decimal]:
        """Get price from price list for the given quantity."""
        if price_list is None:
            price_list = PriceList.objects.filter(
                company=self.company,
                is_default=True,
                is_active=True
            ).filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=today)
            ).filter(
                Q(valid_to__isnull=True) | Q(valid_to__gte=today)
            ).first()

        if not price_list:
            return None

        item = PriceListItem.objects.filter(
            price_list=price_list,
            product=product,
            min_quantity__lte=quantity
        ).order_by('-min_quantity').first()

        return item.unit_price if item else None

    def _get_customer_discount(
        self,
        product,
        partner,
        current_price: Decimal,
        today
    ) -> Optional[dict]:
        """Get customer-specific discount."""
        rules = CustomerPriceRule.objects.filter(
            company=self.company,
            partner=partner,
            is_active=True
        ).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today)
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=today)
        ).filter(
            Q(product=product) |
            Q(product__isnull=True, category=product.category) |
            Q(product__isnull=True, category__isnull=True)
        ).order_by('priority').first()

        if not rules:
            return None

        discount = self._calculate_discount(
            current_price,
            rules.discount_type,
            rules.discount_value
        )

        return {
            'discount': discount,
            'rule_info': {
                'type': rules.discount_type,
                'value': rules.discount_value
            }
        }

    def _get_volume_discount(
        self,
        product,
        quantity: Decimal,
        current_price: Decimal
    ) -> Optional[dict]:
        """Get volume-based discount."""
        volume_discount = VolumeDiscount.objects.filter(
            company=self.company,
            product=product,
            is_active=True,
            min_quantity__lte=quantity
        ).filter(
            Q(max_quantity__isnull=True) | Q(max_quantity__gte=quantity)
        ).order_by('-min_quantity').first()

        if not volume_discount:
            return None

        discount = self._calculate_discount(
            current_price,
            volume_discount.discount_type,
            volume_discount.discount_value
        )

        return {
            'discount': discount,
            'rule_info': {
                'type': volume_discount.discount_type,
                'value': volume_discount.discount_value,
                'min_qty': volume_discount.min_quantity
            }
        }

    def _get_promotion_discount(
        self,
        product,
        promo_code: str,
        current_price: Decimal,
        now
    ) -> Optional[dict]:
        """Get promotion discount by code."""
        promotion = Promotion.objects.filter(
            company=self.company,
            code__iexact=promo_code,
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        ).first()

        if not promotion or promotion.is_exhausted:
            return None

        is_applicable = not promotion.products.exists() or \
            PromotionProduct.objects.filter(
                promotion=promotion,
                product=product
            ).exists()

        if not is_applicable:
            return None

        if promotion.type == Promotion.TYPE_BUY_X_GET_Y:
            return None

        discount = self._calculate_discount(
            current_price,
            promotion.type,
            promotion.value
        )

        return {
            'discount': discount,
            'rule_info': {
                'type': promotion.type,
                'value': promotion.value,
                'name': promotion.name
            }
        }

    def _calculate_discount(
        self,
        price: Decimal,
        discount_type: str,
        discount_value: Decimal
    ) -> Decimal:
        """Calculate discount amount based on type."""
        if discount_type in ('percentage', Promotion.TYPE_PERCENTAGE):
            return (price * discount_value / Decimal('100')).quantize(Decimal('0.01'))
        elif discount_type in ('fixed', Promotion.TYPE_FIXED):
            return min(discount_value, price)
        return Decimal('0')

    def get_product_prices_for_customer(self, partner, products):
        """
        Get prices for multiple products for a specific customer.

        Args:
            partner: Partner (customer) instance
            products: List of Product instances

        Returns:
            Dict mapping product_id to PriceBreakdown
        """
        return {
            product.id: self.calculate_price(product, partner=partner)
            for product in products
        }

    def validate_promo_code(self, promo_code: str, purchase_amount: Decimal = None):
        """
        Validate a promotion code.

        Args:
            promo_code: Promotion code string
            purchase_amount: Optional total purchase amount to check minimum

        Returns:
            Dict with 'valid' boolean and 'message' or 'promotion' data
        """
        now = timezone.now()

        promotion = Promotion.objects.filter(
            company=self.company,
            code__iexact=promo_code
        ).first()

        if not promotion:
            return {'valid': False, 'message': 'Code promo invalide.'}

        if not promotion.is_active:
            return {'valid': False, 'message': 'Cette promotion n\'est plus active.'}

        if promotion.valid_from > now:
            return {'valid': False, 'message': 'Cette promotion n\'a pas encore commencé.'}

        if promotion.valid_to < now:
            return {'valid': False, 'message': 'Cette promotion a expiré.'}

        if promotion.is_exhausted:
            return {'valid': False, 'message': 'Cette promotion a atteint sa limite d\'utilisation.'}

        if purchase_amount and promotion.min_purchase_amount > purchase_amount:
            return {
                'valid': False,
                'message': f'Montant minimum d\'achat requis: {promotion.min_purchase_amount}'
            }

        return {
            'valid': True,
            'promotion': {
                'id': str(promotion.id),
                'code': promotion.code,
                'name': promotion.name,
                'type': promotion.type,
                'value': str(promotion.value),
                'min_purchase_amount': str(promotion.min_purchase_amount)
            }
        }
