"""
Sales views - ViewSets for quotes, orders, deliveries, invoices, returns.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import (
    SalesQuote, SalesQuoteLine,
    SalesOrder, SalesOrderLine,
    DeliveryNote, DeliveryNoteLine,
    SalesInvoice, SalesInvoiceLine,
    SalesReturn, SalesReturnLine,
)
from .serializers import (
    SalesQuoteSerializer, SalesQuoteWithLinesSerializer, SalesQuoteLineSerializer,
    SalesOrderSerializer, SalesOrderWithLinesSerializer, SalesOrderLineSerializer,
    DeliveryNoteSerializer, DeliveryNoteLineSerializer,
    SalesInvoiceSerializer, SalesInvoiceWithLinesSerializer, SalesInvoiceLineSerializer,
    SalesReturnSerializer, SalesReturnWithLinesSerializer, SalesReturnLineSerializer,
)
from .services import SalesService
from apps.core.viewsets import CompanyScopedMixin


class SalesQuoteViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les devis."""
    queryset = SalesQuote.objects.all()
    serializer_class = SalesQuoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('partner', 'currency', 'salesperson')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SalesQuoteWithLinesSerializer
        return SalesQuoteSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        number = SalesService.get_next_number(company, 'sales_quote')
        serializer.save(
            company=company,
            number=number,
            salesperson=self.request.user
        )

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Envoyer le devis au client."""
        quote = self.get_object()
        if quote.status != SalesQuote.STATUS_DRAFT:
            return Response(
                {'error': 'Seul un brouillon peut être envoyé.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        quote.status = SalesQuote.STATUS_SENT
        quote.save(update_fields=['status'])
        return Response(SalesQuoteSerializer(quote).data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Marquer le devis comme accepté."""
        quote = self.get_object()
        if quote.status != SalesQuote.STATUS_SENT:
            return Response(
                {'error': 'Seul un devis envoyé peut être accepté.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        quote.status = SalesQuote.STATUS_ACCEPTED
        quote.save(update_fields=['status'])
        return Response(SalesQuoteSerializer(quote).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Marquer le devis comme refusé."""
        quote = self.get_object()
        if quote.status != SalesQuote.STATUS_SENT:
            return Response(
                {'error': 'Seul un devis envoyé peut être refusé.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        quote.status = SalesQuote.STATUS_REJECTED
        quote.save(update_fields=['status'])
        return Response(SalesQuoteSerializer(quote).data)

    @action(detail=True, methods=['post'])
    def convert_to_order(self, request, pk=None):
        """Convertir le devis en commande."""
        quote = self.get_object()
        warehouse_id = request.data.get('warehouse_id')
        warehouse = None
        if warehouse_id:
            from apps.inventory.models import Warehouse
            warehouse = Warehouse.objects.get(id=warehouse_id)

        try:
            order = SalesService.convert_quote_to_order(
                quote,
                user=request.user,
                warehouse=warehouse
            )
            return Response(SalesOrderSerializer(order).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def calculate_totals(self, request, pk=None):
        """Recalculer les totaux du devis."""
        quote = self.get_object()
        for line in quote.lines.all():
            SalesService.calculate_line_totals(line)
            line.save()
        SalesService.calculate_document_totals(quote)
        return Response(SalesQuoteSerializer(quote).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Générer le PDF du devis."""
        quote = self.get_object()
        pdf = SalesService.generate_pdf(quote, 'quote')
        if pdf:
            return Response({'url': pdf}, status=status.HTTP_200_OK)
        return Response(
            {'message': 'PDF generation not implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class SalesQuoteLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de devis."""
    queryset = SalesQuoteLine.objects.all()
    serializer_class = SalesQuoteLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        quote_id = self.kwargs.get('quote_pk')
        if quote_id:
            queryset = queryset.filter(quote_id=quote_id)
        return queryset.select_related('product')


class SalesOrderViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les commandes clients."""
    queryset = SalesOrder.objects.all()
    serializer_class = SalesOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('partner', 'currency', 'salesperson', 'warehouse', 'quote')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SalesOrderWithLinesSerializer
        return SalesOrderSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        number = SalesService.get_next_number(company, 'sales_order')
        serializer.save(
            company=company,
            number=number,
            salesperson=self.request.user
        )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirmer la commande."""
        order = self.get_object()
        if order.status != SalesOrder.STATUS_DRAFT:
            return Response(
                {'error': 'Seul un brouillon peut être confirmé.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = SalesOrder.STATUS_CONFIRMED
        order.save(update_fields=['status'])
        return Response(SalesOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler la commande."""
        order = self.get_object()
        if order.status in [SalesOrder.STATUS_INVOICED, SalesOrder.STATUS_CANCELLED]:
            return Response(
                {'error': 'Cette commande ne peut pas être annulée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = SalesOrder.STATUS_CANCELLED
        order.save(update_fields=['status'])
        return Response(SalesOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def create_delivery(self, request, pk=None):
        """Créer un bon de livraison."""
        order = self.get_object()
        lines_to_deliver = request.data.get('lines')

        try:
            delivery = SalesService.create_delivery_from_order(order, lines_to_deliver)
            return Response(DeliveryNoteSerializer(delivery).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def create_invoice(self, request, pk=None):
        """Créer une facture."""
        order = self.get_object()
        include_undelivered = request.data.get('include_undelivered', False)

        try:
            invoice = SalesService.create_invoice_from_order(order, include_undelivered)
            return Response(SalesInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def calculate_totals(self, request, pk=None):
        """Recalculer les totaux."""
        order = self.get_object()
        for line in order.lines.all():
            SalesService.calculate_line_totals(line)
            line.save()
        SalesService.calculate_document_totals(order)
        return Response(SalesOrderSerializer(order).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Générer le PDF de la commande."""
        order = self.get_object()
        pdf = SalesService.generate_pdf(order, 'order')
        if pdf:
            return Response({'url': pdf}, status=status.HTTP_200_OK)
        return Response(
            {'message': 'PDF generation not implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class SalesOrderLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de commande."""
    queryset = SalesOrderLine.objects.all()
    serializer_class = SalesOrderLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        order_id = self.kwargs.get('order_pk')
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset.select_related('product')


class DeliveryNoteViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les bons de livraison."""
    queryset = DeliveryNote.objects.all()
    serializer_class = DeliveryNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('partner', 'order')

    def perform_create(self, serializer):
        company = self._get_company()
        number = SalesService.get_next_number(company, 'delivery_note')
        serializer.save(company=company, number=number)

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Valider le bon de livraison."""
        delivery_note = self.get_object()
        try:
            delivery = SalesService.validate_delivery(delivery_note, user=request.user)
            return Response(DeliveryNoteSerializer(delivery).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """Marquer comme expédié."""
        delivery_note = self.get_object()
        carrier = request.data.get('carrier')
        tracking_number = request.data.get('tracking_number')

        try:
            delivery = SalesService.ship_delivery(
                delivery_note,
                carrier=carrier,
                tracking_number=tracking_number,
                user=request.user
            )
            return Response(DeliveryNoteSerializer(delivery).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def confirm_delivered(self, request, pk=None):
        """Confirmer la livraison."""
        delivery_note = self.get_object()
        try:
            delivery = SalesService.confirm_delivery(delivery_note)
            return Response(DeliveryNoteSerializer(delivery).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def create_invoice(self, request, pk=None):
        """Créer une facture depuis le bon de livraison."""
        delivery_note = self.get_object()
        try:
            invoice = SalesService.create_invoice_from_delivery(delivery_note)
            return Response(SalesInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Générer le PDF du bon de livraison."""
        delivery_note = self.get_object()
        pdf = SalesService.generate_pdf(delivery_note, 'delivery_note')
        if pdf:
            return Response({'url': pdf}, status=status.HTTP_200_OK)
        return Response(
            {'message': 'PDF generation not implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class DeliveryNoteLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de bon de livraison."""
    queryset = DeliveryNoteLine.objects.all()
    serializer_class = DeliveryNoteLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        delivery_note_id = self.kwargs.get('delivery_note_pk')
        if delivery_note_id:
            queryset = queryset.filter(delivery_note_id=delivery_note_id)
        return queryset.select_related('product', 'order_line')


class SalesInvoiceViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les factures clients."""
    queryset = SalesInvoice.objects.all()
    serializer_class = SalesInvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('partner', 'currency', 'order', 'delivery_note')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SalesInvoiceWithLinesSerializer
        return SalesInvoiceSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company, number='DRAFT')

    @action(detail=True, methods=['post'])
    def validate_invoice(self, request, pk=None):
        """Valider la facture et générer le numéro."""
        invoice = self.get_object()
        try:
            invoice = SalesService.validate_invoice(invoice, user=request.user)
            return Response(SalesInvoiceSerializer(invoice).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Marquer la facture comme envoyée."""
        invoice = self.get_object()
        if invoice.status != SalesInvoice.STATUS_VALIDATED:
            return Response(
                {'error': 'Seule une facture validée peut être envoyée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        invoice.status = SalesInvoice.STATUS_SENT
        invoice.save(update_fields=['status'])
        return Response(SalesInvoiceSerializer(invoice).data)

    @action(detail=True, methods=['post'])
    def post_to_accounting(self, request, pk=None):
        """Comptabiliser la facture."""
        invoice = self.get_object()
        try:
            invoice = SalesService.post_invoice_to_accounting(invoice, user=request.user)
            return Response(SalesInvoiceSerializer(invoice).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def register_payment(self, request, pk=None):
        """Enregistrer un paiement."""
        invoice = self.get_object()
        amount = request.data.get('amount')
        payment_date = request.data.get('payment_date')
        reference = request.data.get('reference')

        if not amount:
            return Response(
                {'error': 'Le montant est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from decimal import Decimal
            invoice = SalesService.register_payment(
                invoice,
                Decimal(str(amount)),
                payment_date=payment_date,
                reference=reference
            )
            return Response(SalesInvoiceSerializer(invoice).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler la facture."""
        invoice = self.get_object()
        if invoice.is_posted:
            return Response(
                {'error': 'Une facture comptabilisée ne peut pas être annulée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if invoice.amount_paid > 0:
            return Response(
                {'error': 'Une facture avec des paiements ne peut pas être annulée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        invoice.status = SalesInvoice.STATUS_CANCELLED
        invoice.save(update_fields=['status'])
        return Response(SalesInvoiceSerializer(invoice).data)

    @action(detail=True, methods=['post'])
    def calculate_totals(self, request, pk=None):
        """Recalculer les totaux."""
        invoice = self.get_object()
        for line in invoice.lines.all():
            SalesService.calculate_line_totals(line)
            line.save()
        SalesService.calculate_document_totals(invoice)
        invoice.amount_due = invoice.total - invoice.amount_paid
        invoice.save(update_fields=['amount_due'])
        return Response(SalesInvoiceSerializer(invoice).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Générer le PDF de la facture."""
        invoice = self.get_object()
        pdf = SalesService.generate_pdf(invoice, 'invoice')
        if pdf:
            return Response({'url': pdf}, status=status.HTTP_200_OK)
        return Response(
            {'message': 'PDF generation not implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class SalesInvoiceLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de facture."""
    queryset = SalesInvoiceLine.objects.all()
    serializer_class = SalesInvoiceLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        invoice_id = self.kwargs.get('invoice_pk')
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
        return queryset.select_related('product', 'order_line')


class SalesReturnViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les retours clients."""
    queryset = SalesReturn.objects.all()
    serializer_class = SalesReturnSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('partner', 'invoice')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SalesReturnWithLinesSerializer
        return SalesReturnSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        number = SalesService.get_next_number(company, 'sales_return')
        serializer.save(company=company, number=number)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirmer le retour."""
        sales_return = self.get_object()
        if sales_return.status != SalesReturn.STATUS_DRAFT:
            return Response(
                {'error': 'Seul un brouillon peut être confirmé.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        sales_return.status = SalesReturn.STATUS_CONFIRMED
        sales_return.save(update_fields=['status'])
        return Response(SalesReturnSerializer(sales_return).data)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Traiter le retour (créer avoir, etc.)."""
        sales_return = self.get_object()
        if sales_return.status != SalesReturn.STATUS_CONFIRMED:
            return Response(
                {'error': 'Seul un retour confirmé peut être traité.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        sales_return.status = SalesReturn.STATUS_PROCESSED
        sales_return.save(update_fields=['status'])
        return Response(SalesReturnSerializer(sales_return).data)

    @action(detail=True, methods=['post'])
    def calculate_totals(self, request, pk=None):
        """Recalculer les totaux."""
        sales_return = self.get_object()
        for line in sales_return.lines.all():
            SalesService.calculate_line_totals(line)
            line.save()
        SalesService.calculate_document_totals(sales_return)
        return Response(SalesReturnSerializer(sales_return).data)


class SalesReturnLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de retour."""
    queryset = SalesReturnLine.objects.all()
    serializer_class = SalesReturnLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        return_id = self.kwargs.get('return_pk')
        if return_id:
            queryset = queryset.filter(sales_return_id=return_id)
        return queryset.select_related('product', 'invoice_line')
