"""
Sales services - Business logic for sales operations.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.tenancy.models import DocumentSequence


class SalesService:
    """Service pour les opérations de vente."""

    @staticmethod
    def get_next_number(company, document_type):
        """Génère le prochain numéro de document."""
        with transaction.atomic():
            sequence, created = DocumentSequence.objects.select_for_update().get_or_create(
                company=company,
                document_type=document_type,
                defaults={
                    'prefix': document_type.upper()[:3] + '-',
                    'padding': 5,
                    'next_number': 1,
                }
            )
            return sequence.get_next_number()

    @staticmethod
    def calculate_line_totals(line):
        """Calcule les totaux d'une ligne."""
        gross = line.quantity * line.unit_price
        if hasattr(line, 'discount_percent') and line.discount_percent > 0:
            line.discount_amount = gross * (line.discount_percent / 100)
        else:
            line.discount_amount = Decimal('0')
        line.subtotal = gross - line.discount_amount
        line.tax_amount = line.subtotal * (line.tax_rate / 100)
        line.total = line.subtotal + line.tax_amount
        return line

    @staticmethod
    def calculate_document_totals(document):
        """Calcule les totaux d'un document (devis, commande, facture)."""
        subtotal = Decimal('0')
        tax_total = Decimal('0')
        discount_total = Decimal('0')

        for line in document.lines.all():
            subtotal += line.subtotal
            tax_total += line.tax_amount
            if hasattr(line, 'discount_amount'):
                discount_total += line.discount_amount

        document.subtotal = subtotal
        document.tax_total = tax_total
        document.discount_total = discount_total
        document.total = subtotal + tax_total
        document.save(update_fields=['subtotal', 'tax_total', 'discount_total', 'total'])
        return document

    @classmethod
    @transaction.atomic
    def convert_quote_to_order(cls, quote, user=None, warehouse=None):
        """Convertit un devis en commande."""
        from .models import SalesQuote, SalesOrder, SalesOrderLine

        if quote.status != SalesQuote.STATUS_ACCEPTED:
            raise ValidationError("Seul un devis accepté peut être converti en commande.")

        order = SalesOrder.objects.create(
            company=quote.company,
            number=cls.get_next_number(quote.company, 'sales_order'),
            quote=quote,
            partner=quote.partner,
            date=timezone.now().date(),
            status=SalesOrder.STATUS_DRAFT,
            currency=quote.currency,
            exchange_rate=quote.exchange_rate,
            subtotal=quote.subtotal,
            tax_total=quote.tax_total,
            discount_total=quote.discount_total,
            total=quote.total,
            notes=quote.notes,
            terms=quote.terms,
            salesperson=quote.salesperson,
            warehouse=warehouse,
        )

        for quote_line in quote.lines.all():
            SalesOrderLine.objects.create(
                company=quote.company,
                order=order,
                product=quote_line.product,
                description=quote_line.description,
                sequence=quote_line.sequence,
                quantity=quote_line.quantity,
                unit_price=quote_line.unit_price,
                discount_percent=quote_line.discount_percent,
                discount_amount=quote_line.discount_amount,
                tax_rate=quote_line.tax_rate,
                tax_amount=quote_line.tax_amount,
                subtotal=quote_line.subtotal,
                total=quote_line.total,
            )

        quote.status = SalesQuote.STATUS_CONVERTED
        quote.save(update_fields=['status'])

        return order

    @classmethod
    @transaction.atomic
    def create_delivery_from_order(cls, order, lines_to_deliver=None):
        """Crée un bon de livraison à partir d'une commande."""
        from .models import SalesOrder, DeliveryNote, DeliveryNoteLine

        if not order.can_deliver:
            raise ValidationError("Cette commande ne peut pas être livrée.")

        delivery_note = DeliveryNote.objects.create(
            company=order.company,
            number=cls.get_next_number(order.company, 'delivery_note'),
            order=order,
            partner=order.partner,
            date=timezone.now().date(),
            status=DeliveryNote.STATUS_DRAFT,
        )

        order_lines = order.lines.all()
        if lines_to_deliver:
            line_ids = [l['order_line_id'] for l in lines_to_deliver]
            order_lines = order_lines.filter(id__in=line_ids)

        for idx, order_line in enumerate(order_lines):
            qty_to_deliver = order_line.quantity_remaining
            if lines_to_deliver:
                line_info = next(
                    (l for l in lines_to_deliver if str(l['order_line_id']) == str(order_line.id)),
                    None
                )
                if line_info:
                    qty_to_deliver = min(line_info.get('quantity', qty_to_deliver), order_line.quantity_remaining)

            if qty_to_deliver > 0:
                DeliveryNoteLine.objects.create(
                    company=order.company,
                    delivery_note=delivery_note,
                    order_line=order_line,
                    product=order_line.product,
                    sequence=idx,
                    quantity_ordered=order_line.quantity,
                    quantity_delivered=qty_to_deliver,
                )

        if order.status == SalesOrder.STATUS_CONFIRMED:
            order.status = SalesOrder.STATUS_PROCESSING
            order.save(update_fields=['status'])

        return delivery_note

    @classmethod
    @transaction.atomic
    def validate_delivery(cls, delivery_note, user=None):
        """Valide un bon de livraison et met à jour les quantités livrées."""
        from .models import DeliveryNote

        if delivery_note.status != DeliveryNote.STATUS_DRAFT:
            raise ValidationError("Seul un brouillon peut être validé.")

        for line in delivery_note.lines.all():
            order_line = line.order_line
            order_line.quantity_delivered += line.quantity_delivered
            order_line.save(update_fields=['quantity_delivered'])

        delivery_note.status = DeliveryNote.STATUS_READY
        delivery_note.save(update_fields=['status'])

        order = delivery_note.order
        all_delivered = all(
            line.quantity_delivered >= line.quantity
            for line in order.lines.all()
        )
        if all_delivered:
            order.status = order.STATUS_DELIVERED
            order.save(update_fields=['status'])

        return delivery_note

    @classmethod
    @transaction.atomic
    def ship_delivery(cls, delivery_note, carrier=None, tracking_number=None, user=None):
        """Marque un bon de livraison comme expédié."""
        from .models import DeliveryNote

        if delivery_note.status != DeliveryNote.STATUS_READY:
            raise ValidationError("Seul un bon prêt peut être expédié.")

        delivery_note.status = DeliveryNote.STATUS_SHIPPED
        delivery_note.carrier = carrier or ''
        delivery_note.tracking_number = tracking_number or ''
        delivery_note.shipped_by = user
        delivery_note.shipped_at = timezone.now()
        delivery_note.save(update_fields=[
            'status', 'carrier', 'tracking_number', 'shipped_by', 'shipped_at'
        ])

        order = delivery_note.order
        if order.status == order.STATUS_PROCESSING:
            order.status = order.STATUS_SHIPPED
            order.save(update_fields=['status'])

        return delivery_note

    @classmethod
    @transaction.atomic
    def confirm_delivery(cls, delivery_note):
        """Confirme la livraison effective."""
        from .models import DeliveryNote

        if delivery_note.status != DeliveryNote.STATUS_SHIPPED:
            raise ValidationError("Seul un bon expédié peut être confirmé livré.")

        delivery_note.status = DeliveryNote.STATUS_DELIVERED
        delivery_note.delivered_at = timezone.now()
        delivery_note.save(update_fields=['status', 'delivered_at'])

        return delivery_note

    @classmethod
    @transaction.atomic
    def create_invoice_from_order(cls, order, include_undelivered=False):
        """Crée une facture à partir d'une commande."""
        from .models import SalesOrder, SalesInvoice, SalesInvoiceLine

        if not order.can_invoice:
            raise ValidationError("Cette commande ne peut pas être facturée.")

        invoice = SalesInvoice.objects.create(
            company=order.company,
            number='DRAFT',
            order=order,
            partner=order.partner,
            date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(
                days=order.partner.payment_terms_days or 30
            ),
            status=SalesInvoice.STATUS_DRAFT,
            currency=order.currency,
            exchange_rate=order.exchange_rate,
            notes=order.notes,
            terms=order.terms,
        )

        subtotal = Decimal('0')
        tax_total = Decimal('0')
        discount_total = Decimal('0')

        for idx, order_line in enumerate(order.lines.all()):
            qty_to_invoice = order_line.quantity_to_invoice
            if include_undelivered:
                qty_to_invoice = order_line.quantity - order_line.quantity_invoiced

            if qty_to_invoice > 0:
                line_subtotal = qty_to_invoice * order_line.unit_price
                line_discount = Decimal('0')
                if order_line.discount_percent > 0:
                    line_discount = line_subtotal * (order_line.discount_percent / 100)
                line_subtotal -= line_discount
                line_tax = line_subtotal * (order_line.tax_rate / 100)
                line_total = line_subtotal + line_tax

                SalesInvoiceLine.objects.create(
                    company=order.company,
                    invoice=invoice,
                    order_line=order_line,
                    product=order_line.product,
                    description=order_line.description,
                    sequence=idx,
                    quantity=qty_to_invoice,
                    unit_price=order_line.unit_price,
                    discount_percent=order_line.discount_percent,
                    discount_amount=line_discount,
                    tax_rate=order_line.tax_rate,
                    tax_amount=line_tax,
                    subtotal=line_subtotal,
                    total=line_total,
                )

                subtotal += line_subtotal
                tax_total += line_tax
                discount_total += line_discount

                order_line.quantity_invoiced += qty_to_invoice
                order_line.save(update_fields=['quantity_invoiced'])

        invoice.subtotal = subtotal
        invoice.tax_total = tax_total
        invoice.discount_total = discount_total
        invoice.total = subtotal + tax_total
        invoice.amount_due = invoice.total
        invoice.save()

        all_invoiced = all(
            line.quantity_invoiced >= line.quantity
            for line in order.lines.all()
        )
        if all_invoiced:
            order.status = SalesOrder.STATUS_INVOICED
            order.save(update_fields=['status'])

        return invoice

    @classmethod
    @transaction.atomic
    def create_invoice_from_delivery(cls, delivery_note):
        """Crée une facture à partir d'un bon de livraison."""
        from .models import DeliveryNote, SalesInvoice, SalesInvoiceLine

        if delivery_note.status != DeliveryNote.STATUS_DELIVERED:
            raise ValidationError("Seul un bon livré peut être facturé.")

        order = delivery_note.order

        invoice = SalesInvoice.objects.create(
            company=delivery_note.company,
            number='DRAFT',
            order=order,
            delivery_note=delivery_note,
            partner=delivery_note.partner,
            date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(
                days=delivery_note.partner.payment_terms_days or 30
            ),
            status=SalesInvoice.STATUS_DRAFT,
            currency=order.currency,
            exchange_rate=order.exchange_rate,
        )

        subtotal = Decimal('0')
        tax_total = Decimal('0')
        discount_total = Decimal('0')

        for idx, dn_line in enumerate(delivery_note.lines.all()):
            order_line = dn_line.order_line
            qty = dn_line.quantity_delivered

            line_subtotal = qty * order_line.unit_price
            line_discount = Decimal('0')
            if order_line.discount_percent > 0:
                line_discount = line_subtotal * (order_line.discount_percent / 100)
            line_subtotal -= line_discount
            line_tax = line_subtotal * (order_line.tax_rate / 100)
            line_total = line_subtotal + line_tax

            SalesInvoiceLine.objects.create(
                company=delivery_note.company,
                invoice=invoice,
                order_line=order_line,
                product=dn_line.product,
                description=order_line.description,
                sequence=idx,
                quantity=qty,
                unit_price=order_line.unit_price,
                discount_percent=order_line.discount_percent,
                discount_amount=line_discount,
                tax_rate=order_line.tax_rate,
                tax_amount=line_tax,
                subtotal=line_subtotal,
                total=line_total,
            )

            subtotal += line_subtotal
            tax_total += line_tax
            discount_total += line_discount

            order_line.quantity_invoiced += qty
            order_line.save(update_fields=['quantity_invoiced'])

        invoice.subtotal = subtotal
        invoice.tax_total = tax_total
        invoice.discount_total = discount_total
        invoice.total = subtotal + tax_total
        invoice.amount_due = invoice.total
        invoice.save()

        return invoice

    @classmethod
    @transaction.atomic
    def validate_invoice(cls, invoice, user=None):
        """Valide une facture (génère le numéro légal, prépare comptabilisation)."""
        from .models import SalesInvoice

        if invoice.status != SalesInvoice.STATUS_DRAFT:
            raise ValidationError("Seul un brouillon peut être validé.")

        if invoice.number == 'DRAFT' or not invoice.number:
            invoice.number = cls.get_next_number(invoice.company, 'sales_invoice')

        invoice.status = SalesInvoice.STATUS_VALIDATED
        invoice.save(update_fields=['number', 'status'])

        return invoice

    @classmethod
    @transaction.atomic
    def post_invoice_to_accounting(cls, invoice, user=None):
        """Comptabilise une facture (crée l'écriture comptable)."""
        from .models import SalesInvoice

        if invoice.status == SalesInvoice.STATUS_DRAFT:
            raise ValidationError("La facture doit être validée avant comptabilisation.")

        if invoice.is_posted:
            raise ValidationError("Cette facture est déjà comptabilisée.")

        invoice.is_posted = True
        invoice.posted_at = timezone.now()
        invoice.save(update_fields=['is_posted', 'posted_at'])

        return invoice

    @classmethod
    @transaction.atomic
    def register_payment(cls, invoice, amount, payment_date=None, reference=None):
        """Enregistre un paiement sur une facture."""
        from .models import SalesInvoice

        if invoice.status in [SalesInvoice.STATUS_DRAFT, SalesInvoice.STATUS_CANCELLED]:
            raise ValidationError("Impossible d'enregistrer un paiement sur cette facture.")

        if amount <= 0:
            raise ValidationError("Le montant doit être positif.")

        if amount > invoice.amount_due:
            raise ValidationError(f"Le montant dépasse le solde dû ({invoice.amount_due}).")

        invoice.amount_paid += amount
        invoice.update_payment_status()
        invoice.save(update_fields=['amount_paid', 'amount_due', 'status'])

        return invoice

    @classmethod
    def generate_pdf(cls, document, document_type):
        """Génère un PDF pour un document (placeholder)."""
        return None
