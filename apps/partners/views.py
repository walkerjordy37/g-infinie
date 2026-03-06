"""
Partners views.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import PartnerCategory, Partner, PartnerContact, PartnerAddress, PartnerBankAccount
from .serializers import (
    PartnerCategorySerializer,
    PartnerListSerializer,
    PartnerDetailSerializer,
    PartnerWriteSerializer,
    PartnerContactSerializer,
    PartnerAddressSerializer,
    PartnerBankAccountSerializer,
)


class CompanyScopedMixin:
    """Mixin to filter queryset by request's company."""

    def _get_company(self):
        """Get company from middleware or resolve from header/user."""
        # Check if middleware already set it
        company = getattr(self.request, 'company', None)
        if company:
            return company
        
        # Resolve manually (for JWT auth which runs after middleware)
        if not self.request.user.is_authenticated:
            return None
        
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
                return membership.company
            except Exception:
                pass
        
        # Fallback to default company
        membership = self.request.user.memberships.select_related('company').filter(
            is_active=True, is_default=True
        ).first()
        
        if not membership:
            membership = self.request.user.memberships.select_related('company').filter(
                is_active=True
            ).first()
        
        if membership:
            self.request.company = membership.company
            return membership.company
        
        return None

    def get_queryset(self):
        qs = super().get_queryset()
        company = self._get_company()
        if company:
            return qs.filter(company=company)
        return qs.none()

    def perform_create(self, serializer):
        company = self._get_company()
        if not company:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "Aucune entreprise associée à votre compte."})
        serializer.save(company=company)


class PartnerCategoryViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for PartnerCategory."""
    queryset = PartnerCategory.objects.all()
    serializer_class = PartnerCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['parent']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['name']


class PartnerViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for Partner."""
    queryset = Partner.objects.select_related('category', 'currency').prefetch_related(
        'contacts', 'addresses', 'bank_accounts'
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'category', 'is_active', 'city', 'country']
    search_fields = ['code', 'name', 'legal_name', 'tax_id', 'email', 'phone']
    ordering_fields = ['code', 'name', 'created_at', 'credit_limit']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return PartnerListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return PartnerWriteSerializer
        return PartnerDetailSerializer

    @action(detail=False, methods=['get'])
    def customers(self, request):
        """List only customers."""
        qs = self.filter_queryset(self.get_queryset()).filter(
            type__in=[Partner.TYPE_CUSTOMER, Partner.TYPE_BOTH]
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = PartnerListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = PartnerListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def suppliers(self, request):
        """List only suppliers."""
        qs = self.filter_queryset(self.get_queryset()).filter(
            type__in=[Partner.TYPE_SUPPLIER, Partner.TYPE_BOTH]
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = PartnerListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = PartnerListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a partner."""
        partner = self.get_object()
        partner.is_active = True
        partner.save(update_fields=['is_active'])
        return Response({'status': 'activated'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a partner."""
        partner = self.get_object()
        partner.is_active = False
        partner.save(update_fields=['is_active'])
        return Response({'status': 'deactivated'})

    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Bulk activate partners."""
        ids = request.data.get('ids', [])
        count = self.get_queryset().filter(id__in=ids).update(is_active=True)
        return Response({'activated': count})

    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate partners."""
        ids = request.data.get('ids', [])
        count = self.get_queryset().filter(id__in=ids).update(is_active=False)
        return Response({'deactivated': count})


class PartnerContactViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for PartnerContact."""
    queryset = PartnerContact.objects.select_related('partner')
    serializer_class = PartnerContactSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['partner', 'is_primary']
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['name', 'created_at']
    ordering = ['-is_primary', 'name']


class PartnerAddressViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for PartnerAddress."""
    queryset = PartnerAddress.objects.select_related('partner')
    serializer_class = PartnerAddressSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['partner', 'type', 'is_default']
    search_fields = ['name', 'city', 'street']
    ordering_fields = ['name', 'city', 'created_at']
    ordering = ['-is_default', 'name']


class PartnerBankAccountViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet for PartnerBankAccount."""
    queryset = PartnerBankAccount.objects.select_related('partner')
    serializer_class = PartnerBankAccountSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['partner', 'is_default']
    search_fields = ['bank_name', 'account_number', 'iban']
    ordering_fields = ['bank_name', 'created_at']
    ordering = ['-is_default', 'bank_name']
