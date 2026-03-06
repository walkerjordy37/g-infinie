"""Stock alert service for low stock and expiring lots."""
import urllib.parse
from datetime import timedelta
from django.utils import timezone
from django.db.models import F
from .models import StockLevel, LotSerial


class AlertService:
    @staticmethod
    def get_low_stock_products(company):
        return StockLevel.objects.filter(
            company=company,
            product__is_stockable=True,
            product__min_stock__gt=0,
            quantity_on_hand__lte=F('product__min_stock'),
        ).select_related('product', 'warehouse').order_by('product__name')

    @staticmethod
    def get_expiring_lots(company, days=30):
        today = timezone.now().date()
        return LotSerial.objects.filter(
            company=company,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=days),
            quantity__gt=0,
        ).select_related('product', 'warehouse').order_by('expiry_date')

    @staticmethod
    def get_expired_lots(company):
        today = timezone.now().date()
        return LotSerial.objects.filter(
            company=company,
            expiry_date__lt=today,
            quantity__gt=0,
        ).select_related('product', 'warehouse').order_by('expiry_date')

    @staticmethod
    def build_low_stock_message(items):
        if not items:
            return None
        lines = ["\u26a0\ufe0f *ALERTE STOCK BAS*\n"]
        for item in items[:20]:
            lines.append(
                f"\u2022 {item.product.name} ({item.product.code}): "
                f"{item.quantity_on_hand} restant "
                f"(min: {item.product.min_stock}) "
                f"@ {item.warehouse.name}"
            )
        if items.count() > 20:
            lines.append(f"\n...et {items.count() - 20} autres produits")
        return "\n".join(lines)

    @staticmethod
    def build_expiry_message(expiring, expired):
        lines = []
        if expired and expired.exists():
            lines.append("\U0001f534 *LOTS EXPIR\u00c9S*\n")
            for lot in expired[:10]:
                lines.append(
                    f"\u2022 {lot.product.name} - Lot {lot.lot_number}: "
                    f"expir\u00e9 le {lot.expiry_date.strftime('%d/%m/%Y')} "
                    f"(qt\u00e9: {lot.quantity})"
                )
        if expiring and expiring.exists():
            lines.append("\n\U0001f7e1 *LOTS BIENT\u00d4T EXPIR\u00c9S*\n")
            for lot in expiring[:10]:
                days_left = (lot.expiry_date - timezone.now().date()).days
                lines.append(
                    f"\u2022 {lot.product.name} - Lot {lot.lot_number}: "
                    f"expire le {lot.expiry_date.strftime('%d/%m/%Y')} "
                    f"({days_left}j restants, qt\u00e9: {lot.quantity})"
                )
        return "\n".join(lines) if lines else None

    @staticmethod
    def get_whatsapp_url(phone, message):
        clean_phone = phone.replace(' ', '').replace('+', '').replace('-', '')
        encoded_msg = urllib.parse.quote(message)
        return f"https://wa.me/{clean_phone}?text={encoded_msg}"
