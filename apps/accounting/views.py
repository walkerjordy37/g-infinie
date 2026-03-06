"""
Accounting views.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    AccountType, Account, Journal,
    JournalEntry, JournalEntryLine, AccountBalance
)
from .serializers import (
    AccountTypeSerializer, AccountSerializer, AccountListSerializer,
    JournalSerializer, JournalEntrySerializer, JournalEntryListSerializer,
    JournalEntryLineSerializer, AccountBalanceSerializer
)
from .services import AccountingService
from apps.core.viewsets import CompanyScopedMixin


class AccountTypeViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = AccountType.objects.all()
    serializer_class = AccountTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['account_class', 'nature']
    search_fields = ['code', 'name']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company)
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)


class AccountViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Account.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['account_type', 'is_active', 'is_reconcilable', 'parent']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name']
    ordering = ['code']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'account_type', 'parent', 'currency'
            )
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return AccountListSerializer
        return AccountSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        """Obtenir le grand livre d'un compte."""
        account = self.get_object()
        company = self._get_company()
        service = AccountingService(company)

        period_id = request.query_params.get('period')
        period = None
        if period_id:
            from apps.tenancy.models import FiscalPeriod
            period = FiscalPeriod.objects.filter(id=period_id).first()

        result = service.get_general_ledger(account, period)
        return Response(result)


class JournalViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['journal_type', 'is_active']
    search_fields = ['code', 'name']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company)
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)


class JournalEntryViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['journal', 'status', 'fiscal_year', 'fiscal_period', 'is_reversal']
    search_fields = ['number', 'reference', 'description']
    ordering_fields = ['date', 'number', 'created_at']
    ordering = ['-date', '-created_at']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'journal', 'fiscal_year', 'fiscal_period', 'posted_by'
            ).prefetch_related('lines__account')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return JournalEntryListSerializer
        return JournalEntrySerializer

    def perform_create(self, serializer):
        company = self._get_company()
        journal = serializer.validated_data.get('journal')
        service = AccountingService(company)
        number = service.generate_entry_number(journal)
        serializer.save(company=company, number=number)

    @action(detail=True, methods=['post'])
    def post(self, request, pk=None):
        """Valider une écriture comptable."""
        entry = self.get_object()
        company = self._get_company()
        service = AccountingService(company)

        try:
            service.post_entry(entry, user=request.user)
            return Response({'status': 'posted'})
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        """Créer une extourne."""
        entry = self.get_object()
        company = self._get_company()
        service = AccountingService(company)

        try:
            reverse_date = request.data.get('date')
            description = request.data.get('description')
            reversal = service.reverse_entry(entry, reverse_date, description)
            return Response({
                'status': 'reversed',
                'reversal_id': str(reversal.id),
                'reversal_number': reversal.number
            })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class JournalEntryLineViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = JournalEntryLine.objects.all()
    serializer_class = JournalEntryLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        entry_id = self.kwargs.get('entry_pk')
        if company and entry_id:
            return self.queryset.filter(
                company=company, entry_id=entry_id
            ).select_related('account', 'partner')
        return self.queryset.none()


class AccountBalanceViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AccountBalance.objects.all()
    serializer_class = AccountBalanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['account', 'fiscal_period']
    ordering = ['account__code']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'account', 'fiscal_period'
            )
        return self.queryset.none()

    @action(detail=False, methods=['get'])
    def trial_balance(self, request):
        """Générer la balance des comptes."""
        company = self._get_company()
        period_id = request.query_params.get('period')

        if not period_id:
            return Response(
                {'error': "Période requise."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.tenancy.models import FiscalPeriod
        period = FiscalPeriod.objects.filter(id=period_id).first()
        if not period:
            return Response(
                {'error': "Période non trouvée."},
                status=status.HTTP_404_NOT_FOUND
            )

        service = AccountingService(company)
        result = service.get_trial_balance(period)
        return Response(result)
