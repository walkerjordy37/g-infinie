"""
Base viewsets for the API.
"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from .permissions import IsCompanyMember


class CompanyScopedMixin:
    """
    Mixin to resolve company context for JWT-authenticated requests.
    Use this in ViewSets that need company filtering.
    """

    def _get_company(self):
        """Get company from middleware, header, or user's default."""
        # First check if middleware already set it
        if hasattr(self.request, 'company') and self.request.company:
            return self.request.company
        
        # JWT authentication happens in the view, so we need to resolve company here
        if not self.request.user or not self.request.user.is_authenticated:
            return None
        
        # Try X-Company-ID header
        company_id = self.request.headers.get('X-Company-ID')
        if not company_id:
            company_id = self.request.GET.get('company_id')
        
        if company_id:
            try:
                membership = self.request.user.memberships.select_related('company').get(
                    company_id=company_id,
                    is_active=True
                )
                self.request.company = membership.company
                self.request.membership = membership
                return membership.company
            except Exception:
                pass
        
        # Fall back to user's default company
        membership = self.request.user.memberships.select_related('company').filter(
            is_active=True,
            is_default=True
        ).first()
        
        if not membership:
            membership = self.request.user.memberships.select_related('company').filter(
                is_active=True
            ).first()
        
        if membership:
            self.request.company = membership.company
            self.request.membership = membership
            return membership.company
        
        return None


class BaseViewSet(viewsets.ModelViewSet):
    """Base viewset with common functionality."""

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_destroy(self, instance):
        """Soft delete by default."""
        if hasattr(instance, 'soft_delete'):
            instance.soft_delete(user=self.request.user)
        else:
            instance.delete()


class CompanyScopedViewSet(CompanyScopedMixin, BaseViewSet):
    """Viewset that filters by company."""
    permission_classes = [IsCompanyMember]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            return queryset.filter(company=company)
        return queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        if company:
            serializer.save(company=company)
        else:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'company': 'Aucune entreprise associée'})


class BulkActionMixin:
    """Mixin for bulk actions on viewsets."""

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def bulk_delete(self, request):
        """Bulk soft delete items."""
        ids = request.data.get('ids', [])
        if not ids:
            return Response(
                {'error': 'Aucun ID fourni'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(id__in=ids)
        count = 0
        for obj in queryset:
            if hasattr(obj, 'soft_delete'):
                obj.soft_delete(user=request.user)
            else:
                obj.delete()
            count += 1

        return Response({'deleted': count})

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def bulk_update_status(self, request):
        """Bulk update status."""
        ids = request.data.get('ids', [])
        new_status = request.data.get('status')

        if not ids or not new_status:
            return Response(
                {'error': 'IDs et statut requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(id__in=ids)
        count = queryset.update(status=new_status)

        return Response({'updated': count})


class StatusTransitionMixin:
    """Mixin for status transition actions."""

    def get_allowed_transitions(self, current_status):
        """Override to define allowed transitions."""
        return []

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def transition(self, request, pk=None):
        """Transition to a new status."""
        instance = self.get_object()
        new_status = request.data.get('status')

        allowed = self.get_allowed_transitions(instance.status)
        if new_status not in allowed:
            return Response(
                {'error': f'Transition vers {new_status} non autorisée'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = instance.status
        instance.status = new_status
        instance.save(update_fields=['status'])

        return Response({
            'old_status': old_status,
            'new_status': new_status,
            'success': True
        })
