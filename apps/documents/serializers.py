"""
Documents serializers.
"""
from rest_framework import serializers
from .models import DocumentCategory, Document, DocumentVersion, DocumentTemplate, DocumentLink


class DocumentCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    documents_count = serializers.IntegerField(source='documents.count', read_only=True)

    class Meta:
        model = DocumentCategory
        fields = [
            'id', 'code', 'name', 'description',
            'parent', 'parent_name', 'is_active', 'documents_count'
        ]


class DocumentVersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = [
            'id', 'version_number', 'file', 'file_size',
            'change_notes', 'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'version_number', 'file_size', 'created_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None


class DocumentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    extension = serializers.CharField(read_only=True)
    versions = DocumentVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'name', 'category', 'category_name',
            'file', 'file_size', 'mime_type', 'extension',
            'description', 'tags',
            'uploaded_by', 'uploaded_by_name',
            'is_public', 'version', 'versions',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'file_size', 'version', 'created_at', 'updated_at']

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.email
        return None


class DocumentListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    extension = serializers.CharField(read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'name', 'category_name', 'file_size',
            'extension', 'version', 'created_at'
        ]


class DocumentTemplateSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_document_type_display', read_only=True)

    class Meta:
        model = DocumentTemplate
        fields = [
            'id', 'code', 'name', 'document_type', 'type_display',
            'template_file', 'html_template', 'css_styles',
            'header_html', 'footer_html',
            'is_default', 'is_active'
        ]


class DocumentLinkSerializer(serializers.ModelSerializer):
    document_name = serializers.CharField(source='document.name', read_only=True)

    class Meta:
        model = DocumentLink
        fields = [
            'id', 'document', 'document_name',
            'content_type', 'object_id', 'link_type', 'notes'
        ]
