"""
Views for tenancy module.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from apps.core.viewsets import BaseViewSet, CompanyScopedViewSet
from apps.core.permissions import IsCompanyAdmin
from .models import (
    Currency, ExchangeRate, Company, Branch,
    FiscalYear, FiscalPeriod, DocumentSequence, CompanySettings
)
from .serializers import (
    CurrencySerializer, ExchangeRateSerializer, CompanySerializer,
    CompanyCreateSerializer, BranchSerializer, FiscalYearSerializer,
    FiscalPeriodSerializer, DocumentSequenceSerializer, CompanySettingsSerializer
)


class CurrencyViewSet(BaseViewSet):
    """Manage currencies."""
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']


class ExchangeRateViewSet(BaseViewSet):
    """Manage exchange rates."""
    queryset = ExchangeRate.objects.select_related('from_currency', 'to_currency')
    serializer_class = ExchangeRateSerializer
    filterset_fields = ['from_currency', 'to_currency', 'date']
    ordering_fields = ['date', 'rate']

    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Get latest exchange rate for a currency pair."""
        from_currency = request.query_params.get('from')
        to_currency = request.query_params.get('to')

        if not from_currency or not to_currency:
            return Response(
                {'error': 'Les paramètres from et to sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        rate = self.get_queryset().filter(
            from_currency__code=from_currency,
            to_currency__code=to_currency
        ).first()

        if not rate:
            return Response(
                {'error': 'Taux de change non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(ExchangeRateSerializer(rate).data)


class CompanyViewSet(BaseViewSet):
    """Manage companies."""
    queryset = Company.objects.select_related('currency').prefetch_related('branches')
    serializer_class = CompanySerializer
    filterset_fields = ['is_active', 'country']
    search_fields = ['code', 'name', 'legal_name', 'tax_id']

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        return CompanySerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super().get_queryset()
        return Company.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True
        ).distinct()

    @action(detail=True, methods=['get', 'patch'])
    def settings(self, request, pk=None):
        """Get or update company settings."""
        company = self.get_object()
        settings_obj, created = CompanySettings.objects.get_or_create(company=company)

        if request.method == 'PATCH':
            serializer = CompanySettingsSerializer(
                settings_obj,
                data=request.data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        return Response(CompanySettingsSerializer(settings_obj).data)


class BranchViewSet(CompanyScopedViewSet):
    """Manage branches."""
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filterset_fields = ['is_active', 'is_headquarters']
    search_fields = ['code', 'name', 'city']


class FiscalYearViewSet(CompanyScopedViewSet):
    """Manage fiscal years."""
    queryset = FiscalYear.objects.prefetch_related('periods')
    serializer_class = FiscalYearSerializer
    filterset_fields = ['status']
    ordering_fields = ['start_date', 'end_date']

    @action(detail=True, methods=['post'], permission_classes=[IsCompanyAdmin])
    def close(self, request, pk=None):
        """Close a fiscal year."""
        fiscal_year = self.get_object()

        if fiscal_year.status == FiscalYear.STATUS_CLOSED:
            return Response(
                {'error': 'Cet exercice est déjà clôturé'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Close all periods first
        fiscal_year.periods.update(status=FiscalPeriod.STATUS_CLOSED)
        fiscal_year.status = FiscalYear.STATUS_CLOSED
        fiscal_year.save(update_fields=['status'])

        return Response({'status': 'closed'})

    @action(detail=True, methods=['post'])
    def generate_periods(self, request, pk=None):
        """Generate monthly periods for a fiscal year."""
        fiscal_year = self.get_object()

        if fiscal_year.periods.exists():
            return Response(
                {'error': 'Des périodes existent déjà'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from datetime import date
        from dateutil.relativedelta import relativedelta

        current = fiscal_year.start_date
        periods = []
        month_num = 1

        while current <= fiscal_year.end_date:
            next_month = current + relativedelta(months=1)
            period_end = min(next_month - relativedelta(days=1), fiscal_year.end_date)

            period = FiscalPeriod(
                fiscal_year=fiscal_year,
                name=current.strftime('%B %Y'),
                number=month_num,
                start_date=current,
                end_date=period_end
            )
            periods.append(period)

            current = next_month
            month_num += 1

        FiscalPeriod.objects.bulk_create(periods)

        return Response({
            'created': len(periods),
            'periods': FiscalPeriodSerializer(periods, many=True).data
        })


class FiscalPeriodViewSet(CompanyScopedViewSet):
    """Manage fiscal periods."""
    queryset = FiscalPeriod.objects.select_related('fiscal_year')
    serializer_class = FiscalPeriodSerializer
    filterset_fields = ['fiscal_year', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(fiscal_year__company=self.request.company)

    @action(detail=True, methods=['post'], permission_classes=[IsCompanyAdmin])
    def close(self, request, pk=None):
        """Close a fiscal period."""
        period = self.get_object()

        if period.status == FiscalPeriod.STATUS_CLOSED:
            return Response(
                {'error': 'Cette période est déjà clôturée'},
                status=status.HTTP_400_BAD_REQUEST
            )

        period.status = FiscalPeriod.STATUS_CLOSED
        period.save(update_fields=['status'])

        return Response({'status': 'closed'})


class DocumentSequenceViewSet(CompanyScopedViewSet):
    """Manage document sequences."""
    queryset = DocumentSequence.objects.all()
    serializer_class = DocumentSequenceSerializer
    filterset_fields = ['document_type', 'fiscal_year']
