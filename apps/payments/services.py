"""
Payments services - Business logic for payment operations.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.tenancy.models import DocumentSequence


class PaymentService:
    """Service pour les opérations de paiement."""

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

    @classmethod
    @transaction.atomic
    def confirm_payment(cls, payment, user=None):
        """Confirme un paiement."""
        from .models import Payment

        if payment.status != Payment.STATUS_DRAFT:
            raise ValidationError("Seul un brouillon peut être confirmé.")

        if payment.payment_method.requires_reference and not payment.reference:
            raise ValidationError("Une référence est requise pour cette méthode de paiement.")

        payment.status = Payment.STATUS_CONFIRMED
        payment.confirmed_by = user
        payment.confirmed_at = timezone.now()
        payment.save(update_fields=['status', 'confirmed_by', 'confirmed_at'])

        for allocation in payment.allocations.all():
            cls._update_invoice_payment(allocation)

        return payment

    @classmethod
    @transaction.atomic
    def cancel_payment(cls, payment, user=None):
        """Annule un paiement."""
        from .models import Payment

        if payment.status == Payment.STATUS_CANCELLED:
            raise ValidationError("Ce paiement est déjà annulé.")

        if payment.status == Payment.STATUS_RECONCILED:
            raise ValidationError("Un paiement rapproché ne peut pas être annulé.")

        if payment.status == Payment.STATUS_CONFIRMED:
            for allocation in payment.allocations.all():
                cls._revert_invoice_payment(allocation)

        payment.status = Payment.STATUS_CANCELLED
        payment.save(update_fields=['status'])

        return payment

    @classmethod
    @transaction.atomic
    def allocate_payment(cls, payment, invoice, amount, notes=''):
        """Alloue un montant d'un paiement à une facture."""
        from .models import Payment, PaymentAllocation
        from apps.sales.models import SalesInvoice
        from apps.purchasing.models import SupplierInvoice

        if payment.status == Payment.STATUS_CANCELLED:
            raise ValidationError("Impossible d'allouer un paiement annulé.")

        if amount <= 0:
            raise ValidationError("Le montant doit être positif.")

        if amount > payment.amount_unallocated:
            raise ValidationError(
                f"Montant disponible insuffisant ({payment.amount_unallocated})."
            )

        if isinstance(invoice, SalesInvoice):
            if payment.payment_type != Payment.TYPE_CUSTOMER:
                raise ValidationError(
                    "Un paiement fournisseur ne peut pas être alloué à une facture client."
                )
            if amount > invoice.amount_due:
                raise ValidationError(
                    f"Le montant dépasse le solde dû de la facture ({invoice.amount_due})."
                )
            allocation = PaymentAllocation.objects.create(
                company=payment.company,
                payment=payment,
                sales_invoice=invoice,
                amount=amount,
                allocation_date=timezone.now().date(),
                notes=notes,
            )
        elif isinstance(invoice, SupplierInvoice):
            if payment.payment_type != Payment.TYPE_SUPPLIER:
                raise ValidationError(
                    "Un paiement client ne peut pas être alloué à une facture fournisseur."
                )
            if amount > invoice.amount_due:
                raise ValidationError(
                    f"Le montant dépasse le solde dû de la facture ({invoice.amount_due})."
                )
            allocation = PaymentAllocation.objects.create(
                company=payment.company,
                payment=payment,
                supplier_invoice=invoice,
                amount=amount,
                allocation_date=timezone.now().date(),
                notes=notes,
            )
        else:
            raise ValidationError("Type de facture non reconnu.")

        payment.update_allocation_amounts()
        payment.save(update_fields=['amount_allocated', 'amount_unallocated'])

        if payment.status == Payment.STATUS_CONFIRMED:
            cls._update_invoice_payment(allocation)

        return allocation

    @classmethod
    @transaction.atomic
    def deallocate(cls, allocation):
        """Supprime une allocation de paiement."""
        from .models import Payment

        payment = allocation.payment

        if payment.status == Payment.STATUS_RECONCILED:
            raise ValidationError(
                "Impossible de modifier les allocations d'un paiement rapproché."
            )

        if payment.status == Payment.STATUS_CONFIRMED:
            cls._revert_invoice_payment(allocation)

        allocation.soft_delete()

        payment.update_allocation_amounts()
        payment.save(update_fields=['amount_allocated', 'amount_unallocated'])

        return payment

    @classmethod
    @transaction.atomic
    def auto_allocate(cls, payment, strategy='fifo', max_invoices=100):
        """Alloue automatiquement un paiement sur les factures en attente."""
        from .models import Payment
        from apps.sales.models import SalesInvoice
        from apps.purchasing.models import SupplierInvoice

        if payment.status == Payment.STATUS_CANCELLED:
            raise ValidationError("Impossible d'allouer un paiement annulé.")

        if payment.amount_unallocated <= 0:
            return []

        if payment.payment_type == Payment.TYPE_CUSTOMER:
            invoices = SalesInvoice.objects.filter(
                company=payment.company,
                partner=payment.partner,
                status__in=[
                    SalesInvoice.STATUS_VALIDATED,
                    SalesInvoice.STATUS_SENT,
                    SalesInvoice.STATUS_PARTIALLY_PAID,
                ],
                amount_due__gt=0,
            )
        else:
            invoices = SupplierInvoice.objects.filter(
                company=payment.company,
                supplier=payment.partner,
                status__in=[
                    SupplierInvoice.STATUS_VALIDATED,
                    SupplierInvoice.STATUS_PARTIALLY_PAID,
                ],
                amount_due__gt=0,
            )

        if strategy == 'oldest_first':
            invoices = invoices.order_by('date', 'created_at')
        elif strategy == 'largest_first':
            invoices = invoices.order_by('-amount_due')
        else:
            invoices = invoices.order_by('due_date', 'date', 'created_at')

        invoices = invoices[:max_invoices]

        allocations = []
        remaining = payment.amount_unallocated

        for invoice in invoices:
            if remaining <= 0:
                break

            amount_to_allocate = min(remaining, invoice.amount_due)
            if amount_to_allocate > 0:
                allocation = cls.allocate_payment(
                    payment, invoice, amount_to_allocate,
                    notes=f"Allocation automatique ({strategy})"
                )
                allocations.append(allocation)
                remaining -= amount_to_allocate

        return allocations

    @classmethod
    @transaction.atomic
    def reconcile_payment(cls, payment, bank_statement_line=None):
        """Marque un paiement comme rapproché (après rapprochement bancaire)."""
        from .models import Payment

        if payment.status != Payment.STATUS_CONFIRMED:
            raise ValidationError("Seul un paiement confirmé peut être rapproché.")

        payment.status = Payment.STATUS_RECONCILED
        payment.save(update_fields=['status'])

        return payment

    @classmethod
    @transaction.atomic
    def confirm_refund(cls, refund, user=None):
        """Confirme un remboursement."""
        from .models import Refund

        if refund.status != Refund.STATUS_DRAFT:
            raise ValidationError("Seul un brouillon peut être confirmé.")

        refund.status = Refund.STATUS_CONFIRMED
        refund.save(update_fields=['status'])

        return refund

    @classmethod
    @transaction.atomic
    def pay_refund(cls, refund, user=None):
        """Marque un remboursement comme payé."""
        from .models import Refund

        if refund.status != Refund.STATUS_CONFIRMED:
            raise ValidationError("Seul un remboursement confirmé peut être payé.")

        refund.status = Refund.STATUS_PAID
        refund.paid_by = user
        refund.paid_at = timezone.now()
        refund.save(update_fields=['status', 'paid_by', 'paid_at'])

        return refund

    @classmethod
    @transaction.atomic
    def cancel_refund(cls, refund, user=None):
        """Annule un remboursement."""
        from .models import Refund

        if refund.status == Refund.STATUS_CANCELLED:
            raise ValidationError("Ce remboursement est déjà annulé.")

        if refund.status == Refund.STATUS_PAID:
            raise ValidationError("Un remboursement payé ne peut pas être annulé.")

        refund.status = Refund.STATUS_CANCELLED
        refund.save(update_fields=['status'])

        return refund

    @staticmethod
    def _update_invoice_payment(allocation):
        """Met à jour le statut de paiement d'une facture après allocation."""
        from apps.sales.models import SalesInvoice
        from apps.purchasing.models import SupplierInvoice

        invoice = allocation.sales_invoice or allocation.supplier_invoice
        if invoice:
            invoice.amount_paid += allocation.amount
            invoice.update_payment_status()
            invoice.save(update_fields=['amount_paid', 'amount_due', 'status'])

    @staticmethod
    def _revert_invoice_payment(allocation):
        """Annule l'effet d'une allocation sur une facture."""
        from apps.sales.models import SalesInvoice
        from apps.purchasing.models import SupplierInvoice

        invoice = allocation.sales_invoice or allocation.supplier_invoice
        if invoice:
            invoice.amount_paid -= allocation.amount
            if invoice.amount_paid < 0:
                invoice.amount_paid = Decimal('0')
            invoice.update_payment_status()
            invoice.save(update_fields=['amount_paid', 'amount_due', 'status'])

    @classmethod
    def get_partner_balance(cls, company, partner, payment_type=None):
        """Calcule le solde d'un partenaire (montants dus et crédits disponibles)."""
        from .models import Payment
        from apps.sales.models import SalesInvoice
        from apps.purchasing.models import SupplierInvoice

        result = {
            'invoices_due': Decimal('0'),
            'unallocated_payments': Decimal('0'),
            'net_balance': Decimal('0'),
        }

        if payment_type is None or payment_type == Payment.TYPE_CUSTOMER:
            customer_due = SalesInvoice.objects.filter(
                company=company,
                partner=partner,
                status__in=[
                    SalesInvoice.STATUS_VALIDATED,
                    SalesInvoice.STATUS_SENT,
                    SalesInvoice.STATUS_PARTIALLY_PAID,
                ],
            ).aggregate(total=models.Sum('amount_due'))['total'] or Decimal('0')

            customer_payments = Payment.objects.filter(
                company=company,
                partner=partner,
                payment_type=Payment.TYPE_CUSTOMER,
                status__in=[Payment.STATUS_CONFIRMED, Payment.STATUS_RECONCILED],
            ).aggregate(total=models.Sum('amount_unallocated'))['total'] or Decimal('0')

            result['invoices_due'] += customer_due
            result['unallocated_payments'] += customer_payments

        if payment_type is None or payment_type == Payment.TYPE_SUPPLIER:
            supplier_due = SupplierInvoice.objects.filter(
                company=company,
                supplier=partner,
                status__in=[
                    SupplierInvoice.STATUS_VALIDATED,
                    SupplierInvoice.STATUS_PARTIALLY_PAID,
                ],
            ).aggregate(total=models.Sum('amount_due'))['total'] or Decimal('0')

            supplier_payments = Payment.objects.filter(
                company=company,
                partner=partner,
                payment_type=Payment.TYPE_SUPPLIER,
                status__in=[Payment.STATUS_CONFIRMED, Payment.STATUS_RECONCILED],
            ).aggregate(total=models.Sum('amount_unallocated'))['total'] or Decimal('0')

            result['invoices_due'] += supplier_due
            result['unallocated_payments'] += supplier_payments

        result['net_balance'] = result['invoices_due'] - result['unallocated_payments']

        return result

    @classmethod
    def get_open_invoices(cls, company, partner, payment_type):
        """Récupère les factures en attente de paiement pour un partenaire."""
        from .models import Payment
        from apps.sales.models import SalesInvoice
        from apps.purchasing.models import SupplierInvoice

        if payment_type == Payment.TYPE_CUSTOMER:
            return SalesInvoice.objects.filter(
                company=company,
                partner=partner,
                status__in=[
                    SalesInvoice.STATUS_VALIDATED,
                    SalesInvoice.STATUS_SENT,
                    SalesInvoice.STATUS_PARTIALLY_PAID,
                ],
                amount_due__gt=0,
            ).order_by('due_date', 'date')
        else:
            return SupplierInvoice.objects.filter(
                company=company,
                supplier=partner,
                status__in=[
                    SupplierInvoice.STATUS_VALIDATED,
                    SupplierInvoice.STATUS_PARTIALLY_PAID,
                ],
                amount_due__gt=0,
            ).order_by('due_date', 'date')
