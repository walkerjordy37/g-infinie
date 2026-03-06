"""
Documents views.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.http import FileResponse

from apps.core.viewsets import CompanyScopedMixin
from .models import DocumentCategory, Document, DocumentVersion, DocumentTemplate, DocumentLink
from .serializers import (
    DocumentCategorySerializer, DocumentSerializer, DocumentListSerializer,
    DocumentVersionSerializer, DocumentTemplateSerializer, DocumentLinkSerializer
)
from .services import DocumentService


class DocumentCategoryViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = DocumentCategory.objects.all()
    serializer_class = DocumentCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_active', 'parent']
    search_fields = ['code', 'name']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company)
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)


class DocumentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = Document.objects.all()
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_public']
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['name', 'created_at', 'file_size']
    ordering = ['-created_at']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related(
                'category', 'uploaded_by'
            )
        return self.queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        return DocumentSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company, uploaded_by=self.request.user)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Télécharger un document."""
        document = self.get_object()
        response = FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=document.name
        )
        return response

    @action(detail=True, methods=['post'])
    def new_version(self, request, pk=None):
        """Uploader une nouvelle version."""
        document = self.get_object()
        file = request.FILES.get('file')
        notes = request.data.get('change_notes', '')

        if not file:
            return Response(
                {'error': "Fichier requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        company = self._get_company()
        service = DocumentService(company)
        version = service.create_version(document, file, notes, request.user)

        return Response({
            'status': 'version_created',
            'version_number': version.version_number
        })


class DocumentVersionViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = DocumentVersion.objects.all()
    serializer_class = DocumentVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company = self._get_company()
        document_id = self.kwargs.get('document_pk')
        if company and document_id:
            return self.queryset.filter(
                company=company, document_id=document_id
            )
        return self.queryset.none()


class DocumentTemplateViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['document_type', 'is_default', 'is_active']
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
    def set_default(self, request, pk=None):
        """Définir comme template par défaut."""
        template = self.get_object()
        company = self._get_company()

        DocumentTemplate.objects.filter(
            company=company,
            document_type=template.document_type,
            is_default=True
        ).update(is_default=False)

        template.is_default = True
        template.save(update_fields=['is_default'])

        return Response({'status': 'set_as_default'})

    @action(detail=True, methods=['post'])
    def generate_pdf(self, request, pk=None):
        """Générer un PDF à partir du template."""
        template = self.get_object()
        company = self._get_company()
        service = DocumentService(company)

        object_id = request.data.get('object_id')
        if not object_id:
            return Response(
                {'error': "object_id requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            pdf_path = service.generate_pdf(template, object_id)
            return Response({
                'status': 'generated',
                'pdf_url': pdf_path
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class DocumentLinkViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    queryset = DocumentLink.objects.all()
    serializer_class = DocumentLinkSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['content_type', 'object_id', 'link_type']

    def get_queryset(self):
        company = self._get_company()
        if company:
            return self.queryset.filter(company=company).select_related('document')
        return self.queryset.none()

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)
