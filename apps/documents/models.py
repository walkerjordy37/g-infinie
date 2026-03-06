"""
Documents models - Document management, templates, attachments.
"""
import os
from django.db import models
from django.conf import settings
from apps.core.models import CompanyBaseModel


def document_upload_path(instance, filename):
    return f"documents/{instance.company.id}/{instance.category.code}/{filename}"


class DocumentCategory(CompanyBaseModel):
    """Catégorie de documents."""
    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Catégorie parente"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'documents_category'
        verbose_name = "Catégorie de documents"
        verbose_name_plural = "Catégories de documents"
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return self.name


class Document(CompanyBaseModel):
    """Document uploadé."""
    name = models.CharField(max_length=255, verbose_name="Nom")
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.PROTECT,
        related_name='documents',
        verbose_name="Catégorie"
    )
    file = models.FileField(
        upload_to=document_upload_path,
        verbose_name="Fichier"
    )
    file_size = models.PositiveIntegerField(
        default=0,
        verbose_name="Taille (octets)"
    )
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Type MIME"
    )

    description = models.TextField(blank=True, verbose_name="Description")
    tags = models.CharField(max_length=500, blank=True, verbose_name="Tags")

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents',
        verbose_name="Uploadé par"
    )

    is_public = models.BooleanField(default=False, verbose_name="Public")
    version = models.PositiveIntegerField(default=1, verbose_name="Version")

    class Meta:
        db_table = 'documents_document'
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def extension(self):
        return os.path.splitext(self.file.name)[1].lower()

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)


class DocumentVersion(CompanyBaseModel):
    """Version d'un document."""
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name="Document"
    )
    version_number = models.PositiveIntegerField(verbose_name="N° de version")
    file = models.FileField(
        upload_to='documents/versions/',
        verbose_name="Fichier"
    )
    file_size = models.PositiveIntegerField(default=0, verbose_name="Taille")
    change_notes = models.TextField(blank=True, verbose_name="Notes de modification")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_versions',
        verbose_name="Créé par"
    )

    class Meta:
        db_table = 'documents_version'
        verbose_name = "Version de document"
        verbose_name_plural = "Versions de documents"
        unique_together = ['document', 'version_number']
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.document.name} v{self.version_number}"


class DocumentTemplate(CompanyBaseModel):
    """Template de document (facture, devis, etc.)."""
    TYPE_CHOICES = [
        ('sales_quote', 'Devis'),
        ('sales_order', 'Commande client'),
        ('sales_invoice', 'Facture client'),
        ('delivery_note', 'Bon de livraison'),
        ('purchase_order', 'Commande fournisseur'),
        ('goods_receipt', 'Bon de réception'),
        ('supplier_invoice', 'Facture fournisseur'),
    ]

    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=200, verbose_name="Nom")
    document_type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        verbose_name="Type de document"
    )
    template_file = models.FileField(
        upload_to='documents/templates/',
        blank=True,
        verbose_name="Fichier template"
    )
    html_template = models.TextField(
        blank=True,
        verbose_name="Template HTML"
    )
    css_styles = models.TextField(
        blank=True,
        verbose_name="Styles CSS"
    )
    header_html = models.TextField(blank=True, verbose_name="En-tête HTML")
    footer_html = models.TextField(blank=True, verbose_name="Pied de page HTML")

    is_default = models.BooleanField(default=False, verbose_name="Par défaut")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'documents_template'
        verbose_name = "Template de document"
        verbose_name_plural = "Templates de documents"
        unique_together = ['company', 'code']
        ordering = ['document_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_document_type_display()})"


class DocumentLink(CompanyBaseModel):
    """Lien entre un document et une entité métier."""
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='links',
        verbose_name="Document"
    )
    content_type = models.CharField(
        max_length=100,
        verbose_name="Type d'entité"
    )
    object_id = models.UUIDField(verbose_name="ID de l'entité")
    link_type = models.CharField(
        max_length=50,
        default='attachment',
        verbose_name="Type de lien"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'documents_link'
        verbose_name = "Lien de document"
        verbose_name_plural = "Liens de documents"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.document.name} -> {self.content_type}:{self.object_id}"
