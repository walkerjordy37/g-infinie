"""
Purchasing views - Purchase Requests and RFQs.
"""
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import CompanyScopedMixin

from .models import (
    PurchaseRequest, PurchaseRequestLine,
    RequestForQuotation, RequestForQuotationLine, RFQComparison,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine,
    SupplierInvoice, SupplierInvoiceLine
)
from .serializers import (
    PurchaseRequestSerializer, PurchaseRequestListSerializer, PurchaseRequestLineSerializer,
    RequestForQuotationSerializer, RequestForQuotationListSerializer,
    RequestForQuotationLineSerializer, RFQComparisonSerializer,
    PurchaseOrderSerializer, PurchaseOrderListSerializer, PurchaseOrderLineSerializer,
    GoodsReceiptSerializer, GoodsReceiptListSerializer, GoodsReceiptLineSerializer,
    SupplierInvoiceSerializer, SupplierInvoiceListSerializer, SupplierInvoiceLineSerializer
)
from .services import PurchasingService


class PurchaseRequestViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les demandes d'achat."""
    queryset = PurchaseRequest.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'requester', 'department']
    search_fields = ['number', 'notes', 'department']
    ordering_fields = ['date', 'required_date', 'created_at', 'estimated_total']
    ordering = ['-date']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'requester', 'approved_by'
            ).prefetch_related('lines__product')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseRequestListSerializer
        return PurchaseRequestSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        service = PurchasingService(company)
        number = service.generate_request_number()
        serializer.save(
            company=company,
            requester=self.request.user,
            number=number
        )

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Soumettre une demande pour approbation."""
        purchase_request = self.get_object()
        if not purchase_request.is_draft:
            return Response(
                {'error': "Seule une demande en brouillon peut être soumise."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not purchase_request.lines.exists():
            return Response(
                {'error': "La demande doit contenir au moins une ligne."},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_request.status = PurchaseRequest.STATUS_SUBMITTED
        purchase_request.save(update_fields=['status'])
        return Response({'status': 'submitted'})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuver une demande d'achat."""
        purchase_request = self.get_object()
        if not purchase_request.can_approve:
            return Response(
                {'error': "Cette demande ne peut pas être approuvée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_request.status = PurchaseRequest.STATUS_APPROVED
        purchase_request.approved_by = request.user
        purchase_request.approved_at = timezone.now()
        purchase_request.save(update_fields=['status', 'approved_by', 'approved_at'])
        return Response({'status': 'approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejeter une demande d'achat."""
        purchase_request = self.get_object()
        if not purchase_request.can_approve:
            return Response(
                {'error': "Cette demande ne peut pas être rejetée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', '')
        purchase_request.status = PurchaseRequest.STATUS_REJECTED
        purchase_request.rejection_reason = reason
        purchase_request.save(update_fields=['status', 'rejection_reason'])
        return Response({'status': 'rejected'})

    @action(detail=True, methods=['post'])
    def create_rfqs(self, request, pk=None):
        """Créer des RFQs à partir d'une demande approuvée."""
        purchase_request = self.get_object()
        if not purchase_request.can_convert:
            return Response(
                {'error': "Cette demande n'est pas approuvée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        supplier_ids = request.data.get('supplier_ids', [])
        if not supplier_ids:
            return Response(
                {'error': "Veuillez sélectionner au moins un fournisseur."},
                status=status.HTTP_400_BAD_REQUEST
            )

        company = self._get_company()
        service = PurchasingService(company)
        rfqs = service.create_rfqs_from_request(
            purchase_request,
            supplier_ids,
            buyer=request.user
        )

        return Response({
            'status': 'rfqs_created',
            'rfq_ids': [str(rfq.id) for rfq in rfqs]
        })


class PurchaseRequestLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de demande d'achat."""
    queryset = PurchaseRequestLine.objects.all()
    serializer_class = PurchaseRequestLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        request_id = self.kwargs.get('request_pk')
        if company and request_id:
            return self.queryset.filter(
                company=company,
                request_id=request_id
            ).select_related('product', 'unit', 'preferred_supplier')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        request_id = self.kwargs.get('request_pk')
        purchase_request = PurchaseRequest.objects.get(id=request_id, company=company)
        line = serializer.save(company=company, request=purchase_request)
        line.calculate_totals()
        line.save()

        total = sum(l.estimated_total for l in purchase_request.lines.all())
        purchase_request.estimated_total = total
        purchase_request.save(update_fields=['estimated_total'])


class RequestForQuotationViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les demandes de prix (RFQ)."""
    queryset = RequestForQuotation.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'supplier', 'buyer']
    search_fields = ['number', 'supplier__name', 'notes']
    ordering_fields = ['date', 'deadline', 'created_at', 'total']
    ordering = ['-date']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'supplier', 'currency', 'buyer', 'purchase_request'
            ).prefetch_related('lines__product')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return RequestForQuotationListSerializer
        return RequestForQuotationSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        service = PurchasingService(company)
        number = service.generate_rfq_number()
        serializer.save(
            company=company,
            buyer=self.request.user,
            number=number
        )

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Marquer la RFQ comme envoyée."""
        rfq = self.get_object()
        if not rfq.is_draft:
            return Response(
                {'error': "Seule une RFQ en brouillon peut être envoyée."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not rfq.lines.exists():
            return Response(
                {'error': "La RFQ doit contenir au moins une ligne."},
                status=status.HTTP_400_BAD_REQUEST
            )

        rfq.status = RequestForQuotation.STATUS_SENT
        rfq.save(update_fields=['status'])
        return Response({'status': 'sent'})

    @action(detail=True, methods=['post'])
    def receive_response(self, request, pk=None):
        """Enregistrer la réponse du fournisseur."""
        rfq = self.get_object()
        if rfq.status != RequestForQuotation.STATUS_SENT:
            return Response(
                {'error': "Cette RFQ n'a pas été envoyée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        rfq.status = RequestForQuotation.STATUS_RECEIVED
        rfq.response_date = timezone.now().date()

        if 'validity_date' in request.data:
            rfq.validity_date = request.data['validity_date']
        if 'delivery_lead_time' in request.data:
            rfq.delivery_lead_time = request.data['delivery_lead_time']
        if 'payment_terms' in request.data:
            rfq.payment_terms = request.data['payment_terms']
        if 'supplier_notes' in request.data:
            rfq.supplier_notes = request.data['supplier_notes']

        rfq.save()
        return Response({'status': 'response_received'})

    @action(detail=True, methods=['post'])
    def select(self, request, pk=None):
        """Sélectionner cette RFQ pour créer une commande."""
        rfq = self.get_object()
        if not rfq.can_select:
            return Response(
                {'error': "Cette RFQ ne peut pas être sélectionnée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        rfq.status = RequestForQuotation.STATUS_SELECTED
        rfq.save(update_fields=['status'])
        return Response({'status': 'selected'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler une RFQ."""
        rfq = self.get_object()
        if rfq.is_selected:
            return Response(
                {'error': "Une RFQ sélectionnée ne peut pas être annulée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        rfq.status = RequestForQuotation.STATUS_CANCELLED
        rfq.save(update_fields=['status'])
        return Response({'status': 'cancelled'})


class RequestForQuotationLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de RFQ."""
    queryset = RequestForQuotationLine.objects.all()
    serializer_class = RequestForQuotationLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        rfq_id = self.kwargs.get('rfq_pk')
        if company and rfq_id:
            return self.queryset.filter(
                company=company,
                rfq_id=rfq_id
            ).select_related('product', 'unit')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        rfq_id = self.kwargs.get('rfq_pk')
        rfq = RequestForQuotation.objects.get(id=rfq_id, company=company)
        line = serializer.save(company=company, rfq=rfq)
        line.calculate_totals()
        line.save()

        lines = rfq.lines.all()
        rfq.subtotal = sum(l.subtotal for l in lines)
        rfq.tax_total = sum(l.tax_amount for l in lines)
        rfq.discount_total = sum(l.discount_amount for l in lines)
        rfq.total = sum(l.total for l in lines)
        rfq.save(update_fields=['subtotal', 'tax_total', 'discount_total', 'total'])


class RFQComparisonViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les comparaisons de RFQ."""
    queryset = RFQComparison.objects.all()
    serializer_class = RFQComparisonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['purchase_request']
    ordering = ['-comparison_date']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'purchase_request', 'selected_rfq', 'compared_by'
            ).prefetch_related('rfqs')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company, compared_by=self.request.user)

    @action(detail=True, methods=['post'])
    def select_rfq(self, request, pk=None):
        """Sélectionner une RFQ dans la comparaison."""
        comparison = self.get_object()
        rfq_id = request.data.get('rfq_id')
        reason = request.data.get('reason', '')

        if not rfq_id:
            return Response(
                {'error': "Veuillez spécifier une RFQ."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not comparison.rfqs.filter(id=rfq_id).exists():
            return Response(
                {'error': "Cette RFQ ne fait pas partie de la comparaison."},
                status=status.HTTP_400_BAD_REQUEST
            )

        rfq = RequestForQuotation.objects.get(id=rfq_id)
        rfq.status = RequestForQuotation.STATUS_SELECTED
        rfq.save(update_fields=['status'])

        comparison.selected_rfq = rfq
        comparison.selection_reason = reason
        comparison.save(update_fields=['selected_rfq', 'selection_reason'])

        return Response({'status': 'rfq_selected'})


# =============================================================================
# PURCHASE ORDER VIEWS
# =============================================================================

class PurchaseOrderViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les commandes fournisseur."""
    queryset = PurchaseOrder.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'supplier', 'buyer', 'warehouse']
    search_fields = ['number', 'supplier__name', 'supplier_reference', 'notes']
    ordering_fields = ['date', 'expected_delivery_date', 'created_at', 'total']
    ordering = ['-date']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'supplier', 'currency', 'buyer', 'warehouse', 'rfq'
            ).prefetch_related('lines__product')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseOrderListSerializer
        return PurchaseOrderSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        service = PurchasingService(company)
        number = service.generate_order_number()
        serializer.save(
            company=company,
            buyer=self.request.user,
            number=number
        )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirmer une commande."""
        order = self.get_object()
        if not order.is_draft:
            return Response(
                {'error': "Seule une commande en brouillon peut être confirmée."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not order.lines.exists():
            return Response(
                {'error': "La commande doit contenir au moins une ligne."},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = PurchaseOrder.STATUS_CONFIRMED
        order.save(update_fields=['status'])
        return Response({'status': 'confirmed'})

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Marquer la commande comme envoyée."""
        order = self.get_object()
        if order.status != PurchaseOrder.STATUS_CONFIRMED:
            return Response(
                {'error': "La commande doit être confirmée avant envoi."},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = PurchaseOrder.STATUS_SENT
        order.save(update_fields=['status'])
        return Response({'status': 'sent'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler une commande."""
        order = self.get_object()
        if order.is_fully_received:
            return Response(
                {'error': "Une commande reçue ne peut pas être annulée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = PurchaseOrder.STATUS_CANCELLED
        order.save(update_fields=['status'])
        return Response({'status': 'cancelled'})

    @action(detail=True, methods=['post'])
    def create_receipt(self, request, pk=None):
        """Créer une réception pour cette commande."""
        order = self.get_object()
        if not order.can_receive:
            return Response(
                {'error': "Cette commande ne peut pas être réceptionnée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        company = self._get_company()
        service = PurchasingService(company)
        receipt = service.create_goods_receipt(
            order,
            warehouse=order.warehouse,
            received_by=request.user
        )

        return Response({
            'status': 'receipt_created',
            'receipt_id': str(receipt.id),
            'receipt_number': receipt.number
        })


class PurchaseOrderLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de commande fournisseur."""
    queryset = PurchaseOrderLine.objects.all()
    serializer_class = PurchaseOrderLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        order_id = self.kwargs.get('order_pk')
        if company and order_id:
            return self.queryset.filter(
                company=company,
                order_id=order_id
            ).select_related('product', 'unit')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        order_id = self.kwargs.get('order_pk')
        order = PurchaseOrder.objects.get(id=order_id, company=company)
        line = serializer.save(company=company, order=order)
        line.calculate_totals()
        line.save()

        lines = order.lines.all()
        order.subtotal = sum(l.subtotal for l in lines)
        order.tax_total = sum(l.tax_amount for l in lines)
        order.discount_total = sum(l.discount_amount for l in lines)
        order.total = sum(l.total for l in lines)
        order.save(update_fields=['subtotal', 'tax_total', 'discount_total', 'total'])


# =============================================================================
# GOODS RECEIPT VIEWS
# =============================================================================

class GoodsReceiptViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les réceptions de marchandises."""
    queryset = GoodsReceipt.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'supplier', 'purchase_order', 'warehouse']
    search_fields = ['number', 'delivery_note_number', 'tracking_number']
    ordering_fields = ['date', 'created_at']
    ordering = ['-date']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'supplier', 'purchase_order', 'warehouse', 'received_by'
            ).prefetch_related('lines__product')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return GoodsReceiptListSerializer
        return GoodsReceiptSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        service = PurchasingService(company)
        number = service.generate_receipt_number()
        serializer.save(
            company=company,
            received_by=self.request.user,
            number=number
        )

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Valider une réception et mettre à jour le stock."""
        receipt = self.get_object()
        if not receipt.is_draft:
            return Response(
                {'error': "Cette réception a déjà été validée."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not receipt.lines.exists():
            return Response(
                {'error': "La réception doit contenir au moins une ligne."},
                status=status.HTTP_400_BAD_REQUEST
            )

        company = self._get_company()
        service = PurchasingService(company)
        service.validate_goods_receipt(receipt)

        return Response({'status': 'validated'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler une réception (si brouillon)."""
        receipt = self.get_object()
        if receipt.is_validated:
            return Response(
                {'error': "Une réception validée ne peut pas être annulée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        receipt.status = GoodsReceipt.STATUS_CANCELLED
        receipt.save(update_fields=['status'])
        return Response({'status': 'cancelled'})


class GoodsReceiptLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de réception."""
    queryset = GoodsReceiptLine.objects.all()
    serializer_class = GoodsReceiptLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        receipt_id = self.kwargs.get('receipt_pk')
        if company and receipt_id:
            return self.queryset.filter(
                company=company,
                receipt_id=receipt_id
            ).select_related('product', 'unit', 'order_line')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        receipt_id = self.kwargs.get('receipt_pk')
        receipt = GoodsReceipt.objects.get(id=receipt_id, company=company)
        serializer.save(company=company, receipt=receipt)


# =============================================================================
# SUPPLIER INVOICE VIEWS
# =============================================================================

class SupplierInvoiceViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les factures fournisseur."""
    queryset = SupplierInvoice.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'invoice_type', 'supplier', 'three_way_match_status']
    search_fields = ['number', 'supplier_invoice_number', 'supplier__name']
    ordering_fields = ['date', 'due_date', 'created_at', 'total']
    ordering = ['-date']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'supplier', 'currency', 'purchase_order', 'validated_by'
            ).prefetch_related('lines__product')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return SupplierInvoiceListSerializer
        return SupplierInvoiceSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        service = PurchasingService(company)
        number = service.generate_invoice_number()
        serializer.save(company=company, number=number)

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Valider une facture fournisseur."""
        invoice = self.get_object()
        if not invoice.is_draft:
            return Response(
                {'error': "Cette facture a déjà été validée."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not invoice.lines.exists():
            return Response(
                {'error': "La facture doit contenir au moins une ligne."},
                status=status.HTTP_400_BAD_REQUEST
            )

        invoice.status = SupplierInvoice.STATUS_VALIDATED
        invoice.validated_by = request.user
        invoice.validated_at = timezone.now()
        invoice.amount_due = invoice.total
        invoice.save(update_fields=[
            'status', 'validated_by', 'validated_at', 'amount_due'
        ])
        return Response({'status': 'validated'})

    @action(detail=True, methods=['post'])
    def three_way_match(self, request, pk=None):
        """Effectuer le rapprochement à trois voies."""
        invoice = self.get_object()
        company = self._get_company()
        service = PurchasingService(company)

        result = service.perform_three_way_match(invoice)
        return Response(result)

    @action(detail=True, methods=['post'])
    def approve_discrepancy(self, request, pk=None):
        """Approuver une facture malgré les écarts."""
        invoice = self.get_object()
        if invoice.three_way_match_status != 'discrepancy':
            return Response(
                {'error': "Cette facture n'a pas d'écart à approuver."},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', '')
        invoice.three_way_match_status = 'approved'
        invoice.three_way_match_notes = f"Écart approuvé: {reason}"
        invoice.save(update_fields=['three_way_match_status', 'three_way_match_notes'])
        return Response({'status': 'approved'})

    @action(detail=True, methods=['post'])
    def register_payment(self, request, pk=None):
        """Enregistrer un paiement sur la facture."""
        invoice = self.get_object()
        if not invoice.is_validated:
            return Response(
                {'error': "La facture doit être validée avant paiement."},
                status=status.HTTP_400_BAD_REQUEST
            )

        amount = request.data.get('amount')
        if not amount:
            return Response(
                {'error': "Montant requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from decimal import Decimal
        amount = Decimal(str(amount))
        invoice.amount_paid += amount
        invoice.update_payment_status()
        invoice.save(update_fields=['amount_paid', 'amount_due', 'status'])

        return Response({
            'status': invoice.status,
            'amount_paid': str(invoice.amount_paid),
            'amount_due': str(invoice.amount_due)
        })


class SupplierInvoiceLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de facture fournisseur."""
    queryset = SupplierInvoiceLine.objects.all()
    serializer_class = SupplierInvoiceLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        invoice_id = self.kwargs.get('invoice_pk')
        if company and invoice_id:
            return self.queryset.filter(
                company=company,
                invoice_id=invoice_id
            ).select_related('product', 'order_line', 'receipt_line')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        invoice_id = self.kwargs.get('invoice_pk')
        invoice = SupplierInvoice.objects.get(id=invoice_id, company=company)
        line = serializer.save(company=company, invoice=invoice)
        line.calculate_totals()
        line.save()

        lines = invoice.lines.all()
        invoice.subtotal = sum(l.subtotal for l in lines)
        invoice.tax_total = sum(l.tax_amount for l in lines)
        invoice.discount_total = sum(l.discount_amount for l in lines)
        invoice.total = sum(l.total for l in lines)
        invoice.amount_due = invoice.total - invoice.amount_paid
        invoice.save(update_fields=[
            'subtotal', 'tax_total', 'discount_total', 'total', 'amount_due'
        ])
