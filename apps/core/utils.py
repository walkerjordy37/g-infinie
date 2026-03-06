"""
Utility functions for the ERP.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone


def round_money(amount, decimal_places=2):
    """Round a monetary amount."""
    if amount is None:
        return Decimal('0.00')
    quantize_str = '0.' + '0' * decimal_places
    return Decimal(str(amount)).quantize(
        Decimal(quantize_str),
        rounding=ROUND_HALF_UP
    )


def calculate_tax(amount, tax_rate):
    """Calculate tax amount from base amount and rate."""
    if amount is None or tax_rate is None:
        return Decimal('0.00')
    tax = Decimal(str(amount)) * Decimal(str(tax_rate)) / Decimal('100')
    return round_money(tax)


def calculate_discount(amount, discount_rate=None, discount_amount=None):
    """Calculate discount. Either rate (%) or fixed amount."""
    if amount is None:
        return Decimal('0.00')

    if discount_amount is not None:
        return round_money(discount_amount)

    if discount_rate is not None:
        discount = Decimal(str(amount)) * Decimal(str(discount_rate)) / Decimal('100')
        return round_money(discount)

    return Decimal('0.00')


def get_fiscal_year_start(date=None, fiscal_year_start_month=1):
    """Get the start date of fiscal year for a given date."""
    if date is None:
        date = timezone.now().date()

    year = date.year
    if date.month < fiscal_year_start_month:
        year -= 1

    return date.replace(year=year, month=fiscal_year_start_month, day=1)


def get_fiscal_year_end(date=None, fiscal_year_start_month=1):
    """Get the end date of fiscal year for a given date."""
    start = get_fiscal_year_start(date, fiscal_year_start_month)
    if fiscal_year_start_month == 1:
        return start.replace(year=start.year, month=12, day=31)
    else:
        next_year = start.replace(year=start.year + 1)
        return next_year.replace(month=fiscal_year_start_month, day=1) - timezone.timedelta(days=1)


def generate_reference(prefix, sequence, padding=5):
    """Generate a reference number with prefix and padded sequence."""
    return f"{prefix}{str(sequence).zfill(padding)}"


def format_currency(amount, currency_code='XAF', locale='fr_FR'):
    """Format amount as currency string."""
    if amount is None:
        amount = Decimal('0.00')
    return f"{amount:,.2f} {currency_code}".replace(',', ' ').replace('.', ',')


def validate_luhn(number):
    """Validate a number using the Luhn algorithm (for credit cards, etc.)."""
    digits = [int(d) for d in str(number) if d.isdigit()]
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def mask_sensitive_data(data, visible_chars=4):
    """Mask sensitive data like account numbers."""
    if not data or len(str(data)) <= visible_chars:
        return data
    data_str = str(data)
    return '*' * (len(data_str) - visible_chars) + data_str[-visible_chars:]
