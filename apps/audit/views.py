"""
Views for audit module.
"""
from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from apps.core.permissions import CanViewFinancials
from .models import AuditLog, ActivityLog
from .serializers import AuditLogSerializer, ActivityLogSerializer


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """View audit logs (read-only)."""
    queryset = AuditLog.objects.select_related('user', 'company')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, CanViewFinancials]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['action', 'module', 'user', 'company']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self.request, 'company') and self.request.company:
            return queryset.filter(company=self.request.company)
        if not self.request.user.is_superuser:
            company_ids = self.request.user.memberships.filter(
                is_active=True
            ).values_list('company_id', flat=True)
            return queryset.filter(company_id__in=company_ids)
        return queryset


class ActivityLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """View activity logs (read-only)."""
    queryset = ActivityLog.objects.select_related('user', 'company')
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'company', 'action']
    ordering = ['-timestamp']

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self.request, 'company') and self.request.company:
            return queryset.filter(company=self.request.company)
        return queryset.filter(user=self.request.user)
