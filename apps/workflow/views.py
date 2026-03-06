"""
Workflow views.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.viewsets import CompanyScopedMixin
from .models import (
    WorkflowDefinition, WorkflowStep, WorkflowInstance,
    WorkflowAction, WorkflowNotification
)
from .serializers import (
    WorkflowDefinitionSerializer, WorkflowDefinitionListSerializer,
    WorkflowStepSerializer, WorkflowInstanceSerializer,
    WorkflowInstanceListSerializer, WorkflowActionSerializer,
    WorkflowNotificationSerializer
)
from .services import WorkflowService


class WorkflowDefinitionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = WorkflowDefinition.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['entity_type', 'is_active']
    search_fields = ['code', 'name']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).prefetch_related('steps')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkflowDefinitionListSerializer
        return WorkflowDefinitionSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)


class WorkflowStepViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = WorkflowStep.objects.all()
    serializer_class = WorkflowStepSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        workflow_id = self.kwargs.get('workflow_pk')
        if company and workflow_id:
            return self.queryset.filter(
                company=company, workflow_id=workflow_id
            ).order_by('sequence')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        workflow_id = self.kwargs.get('workflow_pk')
        workflow = WorkflowDefinition.objects.get(id=workflow_id, company=company)
        serializer.save(company=company, workflow=workflow)


class WorkflowInstanceViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = WorkflowInstance.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['workflow', 'status', 'content_type']
    ordering = ['-created_at']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'workflow', 'current_step', 'initiated_by'
            ).prefetch_related('actions')
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkflowInstanceListSerializer
        return WorkflowInstanceSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company, initiated_by=self.request.user)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Récupérer les approbations en attente."""
        company = self._get_company()
        service = WorkflowService(company)

        instances = service.get_pending_approvals(request.user)
        serializer = WorkflowInstanceListSerializer(instances, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuver l'étape courante."""
        instance = self.get_object()
        company = self._get_company()
        service = WorkflowService(company)

        comments = request.data.get('comments', '')

        try:
            instance = service.approve_step(instance, request.user, comments)
            return Response({
                'status': instance.status,
                'message': 'Approuvé'
            })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejeter le workflow."""
        instance = self.get_object()
        company = self._get_company()
        service = WorkflowService(company)

        comments = request.data.get('comments', '')

        try:
            instance = service.reject_step(instance, request.user, comments)
            return Response({
                'status': instance.status,
                'message': 'Rejeté'
            })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def delegate(self, request, pk=None):
        """Déléguer l'approbation."""
        instance = self.get_object()
        company = self._get_company()
        service = WorkflowService(company)

        delegate_to_id = request.data.get('delegate_to')
        comments = request.data.get('comments', '')

        if not delegate_to_id:
            return Response(
                {'error': "delegate_to requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        delegate_to = User.objects.filter(id=delegate_to_id).first()

        if not delegate_to:
            return Response(
                {'error': "Utilisateur non trouvé."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            service.delegate_step(instance, request.user, delegate_to, comments)
            return Response({'status': 'delegated'})
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler le workflow."""
        instance = self.get_object()
        company = self._get_company()
        service = WorkflowService(company)

        reason = request.data.get('reason', '')

        try:
            instance = service.cancel_workflow(instance, request.user, reason)
            return Response({'status': 'cancelled'})
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class WorkflowNotificationViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = WorkflowNotification.objects.all()
    serializer_class = WorkflowNotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['is_read']
    ordering = ['-created_at']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(
                company=company,
                recipient=self.request.user
            )
        return self.queryset.none()

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Marquer comme lu."""
        notification = self.get_object()
        from django.utils import timezone
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
        return Response({'status': 'read'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Marquer tout comme lu."""
        from django.utils import timezone
        self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'status': 'all_read'})
