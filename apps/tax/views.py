"""
Tax views - ViewSets for tax types, rates, groups, rules, and declarations.
"""
from django.db import models
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import CompanyScopedMixin
from .models import (
    TaxType, TaxRate, TaxGroup, TaxRule,
    WithholdingTax, TaxDeclaration, TaxDeclarationLine
)
from .serializers import (
    TaxTypeSerializer, TaxTypeListSerializer,
    TaxRateSerializer, TaxRateListSerializer,
    TaxGroupSerializer, TaxGroupListSerializer,
    TaxRuleSerializer, TaxRuleListSerializer,
    WithholdingTaxSerializer, WithholdingTaxListSerializer,
    TaxDeclarationSerializer, TaxDeclarationListSerializer,
    TaxDeclarationLineSerializer,
    TaxCalculationInputSerializer, TaxCalculationResultSerializer,
    WithholdingCalculationInputSerializer, WithholdingCalculationResultSerializer
)
from .services import TaxService


# =============================================================================
# TAX TYPE VIEWS
# =============================================================================

class TaxTypeViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les types de taxe."""
    queryset = TaxType.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tax_type', 'is_active']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['code']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'account_collected', 'account_deductible', 'account_payable'
            )
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return TaxTypeListSerializer
        return TaxTypeSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)


# =============================================================================
# TAX RATE VIEWS
# =============================================================================

class TaxRateViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les taux de taxe."""
    queryset = TaxRate.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tax_type', 'is_default', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'rate', 'valid_from', 'created_at']
    ordering = ['-valid_from']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related('tax_type')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return TaxRateListSerializer
        return TaxRateSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Retourne les taux actifs et valides à la date courante."""
        company = self._get_company()
        if not company:
            return Response([])

        today = timezone.now().date()
        rates = TaxRate.objects.filter(
            company=company,
            is_active=True,
            valid_from__lte=today
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=today)
        ).select_related('tax_type')

        serializer = TaxRateListSerializer(rates, many=True)
        return Response(serializer.data)


# =============================================================================
# TAX GROUP VIEWS
# =============================================================================

class TaxGroupViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les groupes de taxes."""
    queryset = TaxGroup.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['code']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).prefetch_related(
                'tax_rates__tax_type'
            )
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return TaxGroupListSerializer
        return TaxGroupSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)


# =============================================================================
# TAX RULE VIEWS
# =============================================================================

class TaxRuleViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les règles de taxe."""
    queryset = TaxRule.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['transaction_type', 'partner_type', 'is_active', 'country']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'priority', 'created_at']
    ordering = ['-priority', 'code']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'tax_group', 'country', 'product_category'
            )
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return TaxRuleListSerializer
        return TaxRuleSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)

    @action(detail=False, methods=['get'])
    def find_applicable(self, request):
        """Trouve la règle applicable pour une transaction."""
        company = self._get_company()
        if not company:
            return Response({'error': 'Company required'}, status=400)

        transaction_type = request.query_params.get('transaction_type')
        partner_type = request.query_params.get('partner_type')

        if not transaction_type or not partner_type:
            return Response(
                {'error': 'transaction_type et partner_type sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = TaxService(company)
        rule = service.get_applicable_tax_rule(
            transaction_type=transaction_type,
            partner_type=partner_type
        )

        if rule:
            serializer = TaxRuleSerializer(rule)
            return Response(serializer.data)
        return Response(
            {'message': 'Aucune règle applicable trouvée'},
            status=status.HTTP_404_NOT_FOUND
        )


# =============================================================================
# WITHHOLDING TAX VIEWS
# =============================================================================

class WithholdingTaxViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les retenues à la source."""
    queryset = WithholdingTax.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['withholding_type', 'is_active']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'rate', 'created_at']
    ordering = ['code']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'account_payable'
            )
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return WithholdingTaxListSerializer
        return WithholdingTaxSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """Calcule la retenue pour un montant donné."""
        withholding_tax = self.get_object()
        company = self._get_company()

        serializer = WithholdingCalculationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = TaxService(company)
        result = service.calculate_withholding(
            amount=serializer.validated_data['amount'],
            withholding_tax=withholding_tax,
            is_resident=serializer.validated_data.get('is_resident', True)
        )

        return Response(result)


# =============================================================================
# TAX DECLARATION VIEWS
# =============================================================================

class TaxDeclarationViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les déclarations fiscales."""
    queryset = TaxDeclaration.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tax_type', 'period_type', 'status']
    search_fields = ['number', 'notes']
    ordering_fields = ['period_start', 'due_date', 'created_at']
    ordering = ['-period_start']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'tax_type', 'calculated_by', 'validated_by'
            ).prefetch_related('lines__tax_rate')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return TaxDeclarationListSerializer
        return TaxDeclarationSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        service = TaxService(company)
        number = service.generate_declaration_number()
        serializer.save(company=company, number=number)

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Génère les lignes de déclaration à partir des factures."""
        declaration = self.get_object()
        company = self._get_company()

        if not declaration.is_draft:
            return Response(
                {'error': "La déclaration doit être en brouillon."},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = TaxService(company)
        try:
            declaration = service.generate_declaration(
                declaration=declaration,
                calculated_by=request.user
            )
            serializer = TaxDeclarationSerializer(declaration)
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Valide une déclaration calculée."""
        declaration = self.get_object()
        company = self._get_company()

        if not declaration.is_calculated:
            return Response(
                {'error': "La déclaration doit être calculée avant validation."},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = TaxService(company)
        try:
            declaration = service.validate_declaration(
                declaration=declaration,
                validated_by=request.user
            )
            return Response({'status': 'validated'})
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Marque la déclaration comme soumise."""
        declaration = self.get_object()
        company = self._get_company()

        if not declaration.is_validated:
            return Response(
                {'error': "La déclaration doit être validée avant soumission."},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = TaxService(company)
        try:
            reference = request.data.get('submission_reference', '')
            declaration = service.submit_declaration(
                declaration=declaration,
                submission_reference=reference
            )
            return Response({'status': 'submitted'})
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def register_payment(self, request, pk=None):
        """Enregistre le paiement de la déclaration."""
        declaration = self.get_object()
        company = self._get_company()

        payment_date = request.data.get('payment_date')
        payment_amount = request.data.get('payment_amount')
        payment_reference = request.data.get('payment_reference', '')

        if not payment_date or not payment_amount:
            return Response(
                {'error': "Date et montant de paiement requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = TaxService(company)
        try:
            from decimal import Decimal
            declaration = service.register_payment(
                declaration=declaration,
                payment_date=payment_date,
                payment_amount=Decimal(str(payment_amount)),
                payment_reference=payment_reference
            )
            return Response({'status': 'paid'})
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Retourne les déclarations en attente."""
        company = self._get_company()
        if not company:
            return Response([])

        service = TaxService(company)
        declarations = service.get_pending_declarations()
        serializer = TaxDeclarationListSerializer(declarations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Retourne les déclarations en retard."""
        company = self._get_company()
        if not company:
            return Response([])

        service = TaxService(company)
        declarations = service.get_overdue_declarations()
        serializer = TaxDeclarationListSerializer(declarations, many=True)
        return Response(serializer.data)


class TaxDeclarationLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les lignes de déclaration fiscale."""
    queryset = TaxDeclarationLine.objects.all()
    serializer_class = TaxDeclarationLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        declaration_id = self.kwargs.get('declaration_pk')
        if company and declaration_id:
            return self.queryset.filter(
                company=company,
                declaration_id=declaration_id
            ).select_related('tax_rate')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        declaration_id = self.kwargs.get('declaration_pk')
        declaration = TaxDeclaration.objects.get(id=declaration_id, company=company)
        serializer.save(company=company, declaration=declaration)


# =============================================================================
# TAX CALCULATION VIEWS
# =============================================================================

class TaxCalculationViewSet(CompanyScopedMixin, viewsets.ViewSet):
    """ViewSet pour les calculs de taxe."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def calculate_tax(self, request):
        """Calcule la taxe pour un montant donné."""
        company = self._get_company()
        if not company:
            return Response(
                {'error': 'Company required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TaxCalculationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = TaxService(company)
        data = serializer.validated_data

        if data.get('tax_rate_id'):
            try:
                tax_rate = TaxRate.objects.get(
                    id=data['tax_rate_id'],
                    company=company
                )
                result = service.calculate_tax(
                    amount=data['amount'],
                    tax_rate=tax_rate,
                    date=data.get('date')
                )
            except TaxRate.DoesNotExist:
                return Response(
                    {'error': 'Taux de taxe introuvable'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif data.get('tax_group_id'):
            try:
                tax_group = TaxGroup.objects.get(
                    id=data['tax_group_id'],
                    company=company
                )
                result = service.calculate_tax(
                    amount=data['amount'],
                    tax_group=tax_group,
                    date=data.get('date')
                )
            except TaxGroup.DoesNotExist:
                return Response(
                    {'error': 'Groupe de taxe introuvable'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            result = service.calculate_tax_with_rules(
                amount=data['amount'],
                transaction_type=data['transaction_type'],
                partner_type=data['partner_type'],
                date=data.get('date')
            )

        return Response(result)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Retourne un résumé des taxes pour une période."""
        company = self._get_company()
        if not company:
            return Response(
                {'error': 'Company required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')

        if not period_start or not period_end:
            return Response(
                {'error': 'period_start et period_end sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = TaxService(company)
        summary = service.get_tax_summary(
            period_start=period_start,
            period_end=period_end
        )

        return Response(summary)
