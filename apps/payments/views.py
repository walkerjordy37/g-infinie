"""
Payments views - ViewSets for payment methods, terms, payments, allocations, refunds.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from apps.core.viewsets import CompanyScopedMixin
from .models import PaymentMethod, PaymentTerm, Payment, PaymentAllocation, Refund
from .serializers import (
    PaymentMethodSerializer,
    PaymentTermSerializer,
    PaymentSerializer, PaymentWithAllocationsSerializer,
    PaymentAllocationSerializer,
    RefundSerializer,
    AllocationRequestSerializer,
    AutoAllocateRequestSerializer,
)
from .services import PaymentService


class PaymentMethodViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les méthodes de paiement."""
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('bank_account', 'journal')

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Liste les méthodes de paiement actives."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PaymentTermViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les conditions de paiement."""
    queryset = PaymentTerm.objects.all()
    serializer_class = PaymentTermSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Liste les conditions de paiement actives."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def default(self, request):
        """Retourne la condition de paiement par défaut."""
        term = self.get_queryset().filter(is_default=True, is_active=True).first()
        if term:
            return Response(self.get_serializer(term).data)
        return Response({'detail': 'Aucune condition par défaut.'}, status=status.HTTP_404_NOT_FOUND)


class PaymentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les paiements."""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)

        payment_type = self.request.query_params.get('type')
        if payment_type:
            queryset = queryset.filter(payment_type=payment_type)

        partner_id = self.request.query_params.get('partner')
        if partner_id:
            queryset = queryset.filter(partner_id=partner_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.select_related(
            'partner', 'payment_method', 'currency', 'bank_account', 'confirmed_by'
        ).prefetch_related('allocations')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PaymentWithAllocationsSerializer
        return PaymentSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        number = PaymentService.get_next_number(company, 'payment')
        payment = serializer.save(
            company=company,
            number=number,
            amount_allocated=0,
        )
        payment.amount_unallocated = payment.amount
        payment.save(update_fields=['amount_unallocated'])

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirmer le paiement."""
        payment = self.get_object()
        try:
            payment = PaymentService.confirm_payment(payment, user=request.user)
            return Response(PaymentSerializer(payment).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler le paiement."""
        payment = self.get_object()
        try:
            payment = PaymentService.cancel_payment(payment, user=request.user)
            return Response(PaymentSerializer(payment).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def allocate(self, request, pk=None):
        """Allouer le paiement à une facture."""
        payment = self.get_object()
        serializer = AllocationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invoice_id = serializer.validated_data['invoice_id']
        invoice_type = serializer.validated_data['invoice_type']
        amount = serializer.validated_data['amount']

        try:
            if invoice_type == 'sales':
                from apps.sales.models import SalesInvoice
                invoice = SalesInvoice.objects.get(id=invoice_id)
            else:
                from apps.purchasing.models import SupplierInvoice
                invoice = SupplierInvoice.objects.get(id=invoice_id)

            allocation = PaymentService.allocate_payment(payment, invoice, amount)
            return Response(
                PaymentAllocationSerializer(allocation).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def auto_allocate(self, request, pk=None):
        """Allocation automatique sur les factures ouvertes."""
        payment = self.get_object()
        serializer = AutoAllocateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        strategy = serializer.validated_data.get('strategy', 'fifo')
        max_invoices = serializer.validated_data.get('max_invoices', 100)

        try:
            allocations = PaymentService.auto_allocate(
                payment, strategy=strategy, max_invoices=max_invoices
            )
            return Response({
                'allocations_created': len(allocations),
                'amount_allocated': payment.amount_allocated,
                'amount_unallocated': payment.amount_unallocated,
                'allocations': PaymentAllocationSerializer(allocations, many=True).data,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        """Marquer le paiement comme rapproché."""
        payment = self.get_object()
        try:
            payment = PaymentService.reconcile_payment(payment)
            return Response(PaymentSerializer(payment).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def open_invoices(self, request, pk=None):
        """Liste les factures ouvertes pour le partenaire du paiement."""
        payment = self.get_object()
        invoices = PaymentService.get_open_invoices(
            payment.company, payment.partner, payment.payment_type
        )

        invoice_data = []
        for invoice in invoices:
            invoice_data.append({
                'id': invoice.id,
                'number': invoice.number,
                'date': invoice.date,
                'due_date': invoice.due_date,
                'total': invoice.total,
                'amount_paid': invoice.amount_paid,
                'amount_due': invoice.amount_due,
            })

        return Response(invoice_data)


class PaymentAllocationViewSet(viewsets.ModelViewSet):
    """ViewSet pour les allocations de paiement."""
    queryset = PaymentAllocation.objects.all()
    serializer_class = PaymentAllocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        payment_id = self.kwargs.get('payment_pk')
        if payment_id:
            queryset = queryset.filter(payment_id=payment_id)
        return queryset.select_related('payment', 'sales_invoice', 'supplier_invoice')

    @action(detail=True, methods=['post'])
    def remove(self, request, pk=None, payment_pk=None):
        """Supprimer une allocation."""
        allocation = self.get_object()
        try:
            PaymentService.deallocate(allocation)
            return Response({'status': 'Allocation supprimée.'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RefundViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les remboursements."""
    queryset = Refund.objects.all()
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)

        refund_type = self.request.query_params.get('type')
        if refund_type:
            queryset = queryset.filter(refund_type=refund_type)

        partner_id = self.request.query_params.get('partner')
        if partner_id:
            queryset = queryset.filter(partner_id=partner_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.select_related(
            'partner', 'payment_method', 'currency',
            'bank_account', 'original_payment', 'credit_note'
        )

    def perform_create(self, serializer):
        company = self._get_company()
        number = PaymentService.get_next_number(company, 'refund')
        serializer.save(company=company, number=number)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirmer le remboursement."""
        refund = self.get_object()
        try:
            refund = PaymentService.confirm_refund(refund, user=request.user)
            return Response(RefundSerializer(refund).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """Marquer le remboursement comme payé."""
        refund = self.get_object()
        try:
            refund = PaymentService.pay_refund(refund, user=request.user)
            return Response(RefundSerializer(refund).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler le remboursement."""
        refund = self.get_object()
        try:
            refund = PaymentService.cancel_refund(refund, user=request.user)
            return Response(RefundSerializer(refund).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
