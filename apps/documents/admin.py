"""
Documents admin.
"""
from django.contrib import admin
from .models import DocumentCategory, Document, DocumentVersion, DocumentTemplate, DocumentLink


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'parent', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ['version_number', 'file_size', 'created_by', 'created_at']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'file_size', 'version', 'uploaded_by', 'created_at']
    list_filter = ['category', 'is_public']
    search_fields = ['name', 'description', 'tags']
    readonly_fields = ['file_size', 'version']
    inlines = [DocumentVersionInline]


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'document_type', 'is_default', 'is_active']
    list_filter = ['document_type', 'is_default', 'is_active']
    search_fields = ['code', 'name']


@admin.register(DocumentLink)
class DocumentLinkAdmin(admin.ModelAdmin):
    list_display = ['document', 'content_type', 'object_id', 'link_type']
    list_filter = ['content_type', 'link_type']
