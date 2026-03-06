"""
Reporting views.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.http import FileResponse

from apps.core.viewsets import CompanyScopedMixin
from .models import (
    ReportDefinition, ReportSchedule, ReportExecution,
    Dashboard, DashboardWidget, SavedFilter
)
from .serializers import (
    ReportDefinitionSerializer, ReportScheduleSerializer,
    ReportExecutionSerializer, DashboardSerializer,
    DashboardListSerializer, DashboardWidgetSerializer, SavedFilterSerializer
)
from .services import ReportingService


class ReportDefinitionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = ReportDefinition.objects.all()
    serializer_class = ReportDefinitionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['report_type', 'is_active']
    search_fields = ['code', 'name']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company)
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Exécuter le rapport."""
        report = self.get_object()
        company = self._get_company()
        service = ReportingService(company)

        parameters = request.data.get('parameters', {})
        format = request.data.get('format', report.default_format)

        execution = service.execute_report(
            report, parameters, format, request.user
        )

        return Response({
            'execution_id': str(execution.id),
            'status': execution.status
        })


class ReportScheduleViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = ReportSchedule.objects.all()
    serializer_class = ReportScheduleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['report', 'frequency', 'is_active']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related('report')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)


class ReportExecutionViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ReportExecution.objects.all()
    serializer_class = ReportExecutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['report', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'report', 'executed_by'
            )
        return self.queryset.none()

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Télécharger le fichier du rapport."""
        execution = self.get_object()
        if not execution.output_file:
            return Response(
                {'error': "Pas de fichier disponible."},
                status=status.HTTP_404_NOT_FOUND
            )

        return FileResponse(
            execution.output_file.open('rb'),
            as_attachment=True,
            filename=f"{execution.report.code}_{execution.id}.{execution.format}"
        )


class DashboardViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Dashboard.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_default', 'is_public']
    search_fields = ['code', 'name']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).prefetch_related('widgets')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return DashboardListSerializer
        return DashboardSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company, owner=self.request.user)

    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """Récupérer les données du tableau de bord."""
        dashboard = self.get_object()
        company = self._get_company()
        service = ReportingService(company)

        result = service.get_dashboard_data(dashboard)
        return Response(result)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Récupérer les statistiques du tableau de bord principal."""
        from apps.sales.models import SalesInvoice
        from apps.purchasing.models import SupplierInvoice
        from apps.partners.models import Partner
        from apps.catalog.models import Product
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta

        company = self._get_company()
        today = timezone.now().date()
        month_start = today.replace(day=1)

        # Stats de base
        stats = {
            'total_sales': 0,
            'total_purchases': 0,
            'customers_count': 0,
            'products_count': 0,
            'sales_this_month': 0,
            'pending_invoices': 0,
            'overdue_invoices': 0,
        }

        if company:
            # Ventes
            sales = SalesInvoice.objects.filter(company=company)
            stats['total_sales'] = float(sales.aggregate(
                total=Sum('total'))['total'] or 0)
            stats['sales_this_month'] = float(sales.filter(
                date__gte=month_start).aggregate(total=Sum('total'))['total'] or 0)
            stats['pending_invoices'] = sales.filter(
                status__in=['draft', 'validated', 'sent']).count()
            stats['overdue_invoices'] = sales.filter(
                status__in=['validated', 'sent', 'partially_paid'],
                due_date__lt=today).count()

            # Achats
            purchases = SupplierInvoice.objects.filter(company=company)
            stats['total_purchases'] = float(purchases.aggregate(
                total=Sum('total'))['total'] or 0)

            # Partenaires
            stats['customers_count'] = Partner.objects.filter(
                company=company, type__in=['customer', 'both']).count()

            # Produits
            stats['products_count'] = Product.objects.filter(
                company=company, is_active=True).count()

        return Response(stats)

    @action(detail=False, methods=['get'])
    def activities(self, request):
        """Récupérer les activités récentes."""
        from apps.sales.models import SalesInvoice, SalesQuote
        from apps.purchasing.models import PurchaseOrder
        from django.utils import timezone

        company = self._get_company()
        limit = int(request.query_params.get('limit', 10))
        activities = []

        if company:
            # Dernières factures
            invoices = SalesInvoice.objects.filter(
                company=company
            ).order_by('-created_at')[:5]
            for inv in invoices:
                activities.append({
                    'type': 'invoice',
                    'title': f'Facture {inv.number}',
                    'description': f'Client: {inv.partner.name if inv.partner else "N/A"}',
                    'amount': float(inv.total),
                    'date': inv.created_at.isoformat(),
                })

            # Derniers devis
            quotes = SalesQuote.objects.filter(
                company=company
            ).order_by('-created_at')[:5]
            for quote in quotes:
                activities.append({
                    'type': 'quote',
                    'title': f'Devis {quote.number}',
                    'description': f'Client: {quote.partner.name if quote.partner else "N/A"}',
                    'amount': float(quote.total),
                    'date': quote.created_at.isoformat(),
                })

            # Dernières commandes fournisseur
            orders = PurchaseOrder.objects.filter(
                company=company
            ).order_by('-created_at')[:5]
            for order in orders:
                activities.append({
                    'type': 'purchase_order',
                    'title': f'Commande {order.number}',
                    'description': f'Fournisseur: {order.supplier.name if order.supplier else "N/A"}',
                    'amount': float(order.total),
                    'date': order.created_at.isoformat(),
                })

        # Trier par date et limiter
        activities.sort(key=lambda x: x['date'], reverse=True)
        return Response({'results': activities[:limit]})


class DashboardWidgetViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        dashboard_id = self.kwargs.get('dashboard_pk')
        if company and dashboard_id:
            return self.queryset.filter(
                company=company, dashboard_id=dashboard_id
            )
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        dashboard_id = self.kwargs.get('dashboard_pk')
        dashboard = Dashboard.objects.get(id=dashboard_id, company=company)
        serializer.save(company=company, dashboard=dashboard)


class SavedFilterViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = SavedFilter.objects.all()
    serializer_class = SavedFilterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['report']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(
                company=company, owner=self.request.user
            )
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company, owner=self.request.user)
