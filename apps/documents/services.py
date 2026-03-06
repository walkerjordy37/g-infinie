"""
Documents services.
"""
from django.db import transaction


class DocumentService:
    """Service pour la gestion documentaire."""

    def __init__(self, company):
        self.company = company

    @transaction.atomic
    def create_version(self, document, file, change_notes='', user=None):
        """
        Crée une nouvelle version d'un document.

        Args:
            document: Le document parent
            file: Le nouveau fichier
            change_notes: Notes de modification
            user: L'utilisateur qui crée la version

        Returns:
            La nouvelle version
        """
        from .models import DocumentVersion

        new_version_number = document.version + 1

        version = DocumentVersion.objects.create(
            company=self.company,
            document=document,
            version_number=new_version_number,
            file=file,
            file_size=file.size,
            change_notes=change_notes,
            created_by=user
        )

        document.file = file
        document.file_size = file.size
        document.version = new_version_number
        document.save(update_fields=['file', 'file_size', 'version'])

        return version

    def generate_pdf(self, template, object_id):
        """
        Génère un PDF à partir d'un template.

        Args:
            template: Le template de document
            object_id: L'ID de l'objet métier

        Returns:
            Le chemin du fichier PDF généré
        """
        context = self._get_context_for_template(template, object_id)
        
        from django.template import Template, Context
        html_content = Template(template.html_template).render(Context(context))

        pdf_filename = f"{template.document_type}_{object_id}.pdf"
        pdf_path = f"documents/generated/{self.company.id}/{pdf_filename}"

        return pdf_path

    def _get_context_for_template(self, template, object_id):
        """Récupère le contexte pour un template."""
        context = {
            'company': self.company,
        }

        if template.document_type == 'sales_invoice':
            from apps.sales.models import SalesInvoice
            invoice = SalesInvoice.objects.filter(id=object_id).first()
            if invoice:
                context['invoice'] = invoice
                context['lines'] = invoice.lines.all()
                context['partner'] = invoice.partner

        elif template.document_type == 'sales_quote':
            from apps.sales.models import SalesQuote
            quote = SalesQuote.objects.filter(id=object_id).first()
            if quote:
                context['quote'] = quote
                context['lines'] = quote.lines.all()
                context['partner'] = quote.partner

        elif template.document_type == 'purchase_order':
            from apps.purchasing.models import PurchaseOrder
            order = PurchaseOrder.objects.filter(id=object_id).first()
            if order:
                context['order'] = order
                context['lines'] = order.lines.all()
                context['supplier'] = order.supplier

        return context

    def link_document(self, document, content_type, object_id, link_type='attachment'):
        """
        Lie un document à une entité métier.

        Args:
            document: Le document à lier
            content_type: Le type d'entité
            object_id: L'ID de l'entité
            link_type: Le type de lien

        Returns:
            Le lien créé
        """
        from .models import DocumentLink

        return DocumentLink.objects.create(
            company=self.company,
            document=document,
            content_type=content_type,
            object_id=object_id,
            link_type=link_type
        )

    def get_documents_for_object(self, content_type, object_id):
        """
        Récupère les documents liés à un objet.

        Args:
            content_type: Le type d'entité
            object_id: L'ID de l'entité

        Returns:
            QuerySet des documents liés
        """
        from .models import Document, DocumentLink

        link_ids = DocumentLink.objects.filter(
            company=self.company,
            content_type=content_type,
            object_id=object_id
        ).values_list('document_id', flat=True)

        return Document.objects.filter(id__in=link_ids)
