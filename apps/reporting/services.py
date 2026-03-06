"""
Reporting services.
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count, Avg
from django.utils import timezone

from .models import ReportDefinition, ReportExecution


class ReportingService:
    """Service pour la génération de rapports."""

    def __init__(self, company):
        self.company = company

    @transaction.atomic
    def execute_report(
        self,
        report: ReportDefinition,
        parameters: dict = None,
        format: str = 'pdf',
        user=None
    ) -> ReportExecution:
        """
        Exécute un rapport.

        Args:
            report: Le rapport à exécuter
            parameters: Les paramètres du rapport
            format: Le format de sortie
            user: L'utilisateur qui exécute

        Returns:
            L'exécution créée
        """
        execution = ReportExecution.objects.create(
            company=self.company,
            report=report,
            status=ReportExecution.STATUS_RUNNING,
            parameters=parameters or {},
            format=format,
            started_at=timezone.now(),
            executed_by=user
        )

        try:
            data = self._generate_report_data(report, parameters)
            output_file = self._render_report(report, data, format)

            execution.status = ReportExecution.STATUS_COMPLETED
            execution.completed_at = timezone.now()
            execution.duration_seconds = (
                execution.completed_at - execution.started_at
            ).seconds
            if output_file:
                execution.output_file = output_file
            execution.save()

        except Exception as e:
            execution.status = ReportExecution.STATUS_FAILED
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save()

        return execution

    def _generate_report_data(self, report: ReportDefinition, parameters: dict) -> dict:
        """Génère les données du rapport."""
        if report.report_type == ReportDefinition.TYPE_FINANCIAL:
            return self._generate_financial_report(parameters)
        elif report.report_type == ReportDefinition.TYPE_SALES:
            return self._generate_sales_report(parameters)
        elif report.report_type == ReportDefinition.TYPE_PURCHASING:
            return self._generate_purchasing_report(parameters)
        elif report.report_type == ReportDefinition.TYPE_INVENTORY:
            return self._generate_inventory_report(parameters)
        return {}

    def _generate_financial_report(self, parameters: dict) -> dict:
        """Génère un rapport financier."""
        from apps.accounting.models import AccountBalance, Account

        period_id = parameters.get('period_id')

        balances = AccountBalance.objects.filter(
            company=self.company
        )
        if period_id:
            balances = balances.filter(fiscal_period_id=period_id)

        data = {
            'title': 'Rapport Financier',
            'accounts': [],
            'totals': {
                'debit': Decimal('0'),
                'credit': Decimal('0')
            }
        }

        for balance in balances.select_related('account'):
            data['accounts'].append({
                'code': balance.account.code,
                'name': balance.account.name,
                'debit': float(balance.closing_debit),
                'credit': float(balance.closing_credit),
                'balance': float(balance.balance)
            })
            data['totals']['debit'] += balance.closing_debit
            data['totals']['credit'] += balance.closing_credit

        return data

    def _generate_sales_report(self, parameters: dict) -> dict:
        """Génère un rapport de ventes."""
        from apps.sales.models import SalesInvoice

        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')

        invoices = SalesInvoice.objects.filter(
            company=self.company,
            status__in=['validated', 'sent', 'partially_paid', 'paid']
        )

        if start_date:
            invoices = invoices.filter(date__gte=start_date)
        if end_date:
            invoices = invoices.filter(date__lte=end_date)

        stats = invoices.aggregate(
            total_amount=Sum('total'),
            total_count=Count('id'),
            avg_amount=Avg('total')
        )

        return {
            'title': 'Rapport des Ventes',
            'period': {
                'start': start_date,
                'end': end_date
            },
            'summary': {
                'total_invoices': stats['total_count'] or 0,
                'total_amount': float(stats['total_amount'] or 0),
                'average_amount': float(stats['avg_amount'] or 0)
            },
            'invoices': list(invoices.values(
                'number', 'date', 'partner__name', 'total', 'status'
            )[:100])
        }

    def _generate_purchasing_report(self, parameters: dict) -> dict:
        """Génère un rapport d'achats."""
        from apps.purchasing.models import SupplierInvoice

        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')

        invoices = SupplierInvoice.objects.filter(
            company=self.company
        ).exclude(status='cancelled')

        if start_date:
            invoices = invoices.filter(date__gte=start_date)
        if end_date:
            invoices = invoices.filter(date__lte=end_date)

        stats = invoices.aggregate(
            total_amount=Sum('total'),
            total_count=Count('id')
        )

        return {
            'title': 'Rapport des Achats',
            'summary': {
                'total_invoices': stats['total_count'] or 0,
                'total_amount': float(stats['total_amount'] or 0)
            }
        }

    def _generate_inventory_report(self, parameters: dict) -> dict:
        """Génère un rapport d'inventaire."""
        from apps.inventory.models import StockLevel

        warehouse_id = parameters.get('warehouse_id')

        levels = StockLevel.objects.filter(company=self.company)
        if warehouse_id:
            levels = levels.filter(warehouse_id=warehouse_id)

        return {
            'title': 'Rapport d\'Inventaire',
            'items': list(levels.select_related('product', 'warehouse').values(
                'product__code', 'product__name',
                'warehouse__name', 'quantity_on_hand', 'quantity_reserved'
            )[:200])
        }

    def _render_report(self, report: ReportDefinition, data: dict, format: str) -> str:
        """Rend le rapport dans le format demandé."""
        return None

    def get_dashboard_data(self, dashboard) -> dict:
        """Récupère les données pour un tableau de bord."""
        result = {
            'dashboard': {
                'id': str(dashboard.id),
                'name': dashboard.name
            },
            'widgets': []
        }

        for widget in dashboard.widgets.all():
            widget_data = {
                'id': str(widget.id),
                'name': widget.name,
                'type': widget.widget_type,
                'position': {
                    'x': widget.position_x,
                    'y': widget.position_y,
                    'w': widget.width,
                    'h': widget.height
                },
                'data': self._get_widget_data(widget)
            }
            result['widgets'].append(widget_data)

        return result

    def _get_widget_data(self, widget) -> dict:
        """Récupère les données d'un widget."""
        if widget.report:
            return self._generate_report_data(
                widget.report,
                widget.parameters
            )
        return {}
