"""
Purchasing models - Purchase Requests, RFQs, Purchase Orders, Goods Receipts, Supplier Invoices.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import CompanyBaseModel, MoneyField, PercentageField


# =============================================================================
# PURCHASE REQUESTS
# =============================================================================

class PurchaseRequest(CompanyBaseModel):
    """Demande d'achat interne."""
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CONVERTED = 'converted'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_SUBMITTED, 'Soumis'),
        (STATUS_APPROVED, 'Approuvé'),
        (STATUS_REJECTED, 'Rejeté'),
        (STATUS_CONVERTED, 'Converti en commande'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Basse'),
        (PRIORITY_NORMAL, 'Normale'),
        (PRIORITY_HIGH, 'Haute'),
        (PRIORITY_URGENT, 'Urgente'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Généré automatiquement"
    )
    date = models.DateField(verbose_name="Date de demande")
    required_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date requise"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
        verbose_name="Priorité"
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='purchase_requests_created',
        verbose_name="Demandeur"
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Département"
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_requests_approved',
        verbose_name="Approuvé par"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'approbation"
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Motif de rejet"
    )

    estimated_total = MoneyField(verbose_name="Total estimé")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'purchasing_request'
        verbose_name = "Demande d'achat"
        verbose_name_plural = "Demandes d'achat"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.requester.get_full_name() or self.requester.email}"

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    @property
    def can_approve(self):
        return self.status == self.STATUS_SUBMITTED

    @property
    def can_convert(self):
        return self.status == self.STATUS_APPROVED


class PurchaseRequestLine(CompanyBaseModel):
    """Ligne de demande d'achat."""
    request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Demande"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_request_lines',
        verbose_name="Produit"
    )
    product_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom produit (saisie libre)",
        help_text="Nom du produit non enregistré"
    )
    description = models.TextField(blank=True, verbose_name="Description")
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name="Quantité demandée"
    )
    unit = models.ForeignKey(
        'catalog.UnitOfMeasure',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_request_lines',
        verbose_name="Unité"
    )
    estimated_unit_price = MoneyField(
        verbose_name="Prix unitaire estimé"
    )
    estimated_total = MoneyField(verbose_name="Total estimé")

    preferred_supplier = models.ForeignKey(
        'partners.Partner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preferred_request_lines',
        verbose_name="Fournisseur préféré"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'purchasing_request_line'
        verbose_name = "Ligne de demande d'achat"
        verbose_name_plural = "Lignes de demande d'achat"
        ordering = ['request', 'sequence', 'id']

    def __str__(self):
        return f"{self.request.number} - {self.product_name_display}"

    @property
    def product_name_display(self):
        if self.product:
            return self.product.name
        return self.product_name_manual or 'Produit inconnu'

    def calculate_totals(self):
        """Calcule le total estimé de la ligne."""
        self.estimated_total = self.quantity * self.estimated_unit_price


# =============================================================================
# REQUEST FOR QUOTATIONS (RFQ)
# =============================================================================

class RequestForQuotation(CompanyBaseModel):
    """Demande de prix (appel d'offres fournisseur)."""
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_RECEIVED = 'received'
    STATUS_SELECTED = 'selected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_SENT, 'Envoyé'),
        (STATUS_RECEIVED, 'Réponse reçue'),
        (STATUS_SELECTED, 'Sélectionné'),
        (STATUS_CANCELLED, 'Annulé'),
        (STATUS_EXPIRED, 'Expiré'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Généré automatiquement"
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rfqs',
        verbose_name="Demande d'achat d'origine"
    )
    supplier = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rfqs_received',
        verbose_name="Fournisseur"
    )
    supplier_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom fournisseur (saisie libre)",
        help_text="Nom du fournisseur non enregistré"
    )

    date = models.DateField(verbose_name="Date d'envoi")
    deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date limite de réponse"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='rfqs',
        verbose_name="Devise"
    )
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name="Taux de change"
    )

    response_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de réponse"
    )
    validity_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Validité de l'offre"
    )
    delivery_lead_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Délai de livraison (jours)"
    )
    payment_terms = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Conditions de paiement"
    )

    subtotal = MoneyField(verbose_name="Sous-total HT")
    tax_total = MoneyField(verbose_name="Total TVA")
    discount_total = MoneyField(verbose_name="Total remise")
    total = MoneyField(verbose_name="Total TTC")

    notes = models.TextField(blank=True, verbose_name="Notes internes")
    supplier_notes = models.TextField(
        blank=True,
        verbose_name="Notes du fournisseur"
    )

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rfqs_managed',
        verbose_name="Acheteur"
    )

    class Meta:
        db_table = 'purchasing_rfq'
        verbose_name = "Demande de prix"
        verbose_name_plural = "Demandes de prix"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.supplier_name_display}"

    @property
    def supplier_name_display(self):
        """Returns supplier name from registered partner or manual entry."""
        if self.supplier:
            return self.supplier.name
        return self.supplier_name_manual or 'Fournisseur inconnu'

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_expired(self):
        from django.utils import timezone
        if self.deadline and self.status == self.STATUS_SENT:
            return self.deadline < timezone.now().date()
        return False

    @property
    def can_select(self):
        return self.status == self.STATUS_RECEIVED

    @property
    def is_selected(self):
        return self.status == self.STATUS_SELECTED


class RequestForQuotationLine(CompanyBaseModel):
    """Ligne de demande de prix."""
    rfq = models.ForeignKey(
        RequestForQuotation,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Demande de prix"
    )
    request_line = models.ForeignKey(
        PurchaseRequestLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rfq_lines',
        verbose_name="Ligne de demande d'origine"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rfq_lines',
        verbose_name="Produit"
    )
    product_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom produit (saisie libre)",
        help_text="Nom du produit non enregistré"
    )
    description = models.TextField(blank=True, verbose_name="Description")
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name="Quantité demandée"
    )
    unit = models.ForeignKey(
        'catalog.UnitOfMeasure',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rfq_lines',
        verbose_name="Unité"
    )

    quoted_unit_price = MoneyField(
        verbose_name="Prix unitaire proposé"
    )
    discount_percent = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Remise (%)"
    )
    discount_amount = MoneyField(verbose_name="Montant remise")

    tax_rate = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Taux TVA (%)"
    )
    tax_amount = MoneyField(verbose_name="Montant TVA")

    subtotal = MoneyField(verbose_name="Sous-total HT")
    total = MoneyField(verbose_name="Total TTC")

    quoted_lead_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Délai proposé (jours)"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'purchasing_rfq_line'
        verbose_name = "Ligne de demande de prix"
        verbose_name_plural = "Lignes de demande de prix"
        ordering = ['rfq', 'sequence', 'id']

    def __str__(self):
        return f"{self.rfq.number} - {self.product_name_display}"

    @property
    def product_name_display(self):
        if self.product:
            return self.product.name
        return self.product_name_manual or 'Produit inconnu'

    def calculate_totals(self):
        """Calcule les totaux de la ligne."""
        gross = self.quantity * self.quoted_unit_price
        if self.discount_percent > 0:
            self.discount_amount = gross * (self.discount_percent / 100)
        self.subtotal = gross - self.discount_amount
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax_amount


class RFQComparison(CompanyBaseModel):
    """Comparaison de plusieurs RFQ pour un même besoin."""
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name='comparisons',
        verbose_name="Demande d'achat"
    )
    rfqs = models.ManyToManyField(
        RequestForQuotation,
        related_name='comparisons',
        verbose_name="RFQs comparées"
    )
    selected_rfq = models.ForeignKey(
        RequestForQuotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='selected_in_comparisons',
        verbose_name="RFQ sélectionnée"
    )
    selection_reason = models.TextField(
        blank=True,
        verbose_name="Motif de sélection"
    )
    comparison_date = models.DateField(verbose_name="Date de comparaison")
    compared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rfq_comparisons',
        verbose_name="Comparé par"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'purchasing_rfq_comparison'
        verbose_name = "Comparaison de RFQ"
        verbose_name_plural = "Comparaisons de RFQ"
        ordering = ['-comparison_date', '-created_at']

    def __str__(self):
        return f"Comparaison {self.purchase_request.number}"


# =============================================================================
# PURCHASE ORDERS
# =============================================================================

class PurchaseOrder(CompanyBaseModel):
    """Commande fournisseur."""
    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_SENT = 'sent'
    STATUS_PARTIALLY_RECEIVED = 'partially_received'
    STATUS_RECEIVED = 'received'
    STATUS_INVOICED = 'invoiced'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_CONFIRMED, 'Confirmé'),
        (STATUS_SENT, 'Envoyé'),
        (STATUS_PARTIALLY_RECEIVED, 'Partiellement reçu'),
        (STATUS_RECEIVED, 'Reçu'),
        (STATUS_INVOICED, 'Facturé'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Généré automatiquement"
    )
    rfq = models.ForeignKey(
        RequestForQuotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name="RFQ d'origine"
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name="Demande d'achat d'origine"
    )
    supplier = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name="Fournisseur"
    )
    supplier_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom fournisseur (saisie libre)",
        help_text="Nom du fournisseur non enregistré"
    )

    date = models.DateField(verbose_name="Date de commande")
    expected_delivery_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de livraison prévue"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        verbose_name="Devise"
    )
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name="Taux de change"
    )

    subtotal = MoneyField(verbose_name="Sous-total HT")
    tax_total = MoneyField(verbose_name="Total TVA")
    discount_total = MoneyField(verbose_name="Total remise")
    total = MoneyField(verbose_name="Total TTC")

    payment_terms = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Conditions de paiement"
    )
    incoterm = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Incoterm"
    )
    delivery_address = models.TextField(
        blank=True,
        verbose_name="Adresse de livraison"
    )

    notes = models.TextField(blank=True, verbose_name="Notes internes")
    supplier_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence fournisseur"
    )

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name="Acheteur"
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name="Entrepôt de réception"
    )

    class Meta:
        db_table = 'purchasing_order'
        verbose_name = "Commande fournisseur"
        verbose_name_plural = "Commandes fournisseur"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.supplier_name_display}"

    @property
    def supplier_name_display(self):
        """Returns supplier name from registered partner or manual entry."""
        if self.supplier:
            return self.supplier.name
        return self.supplier_name_manual or 'Fournisseur inconnu'

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_confirmed(self):
        return self.status in [
            self.STATUS_CONFIRMED, self.STATUS_SENT,
            self.STATUS_PARTIALLY_RECEIVED, self.STATUS_RECEIVED
        ]

    @property
    def can_receive(self):
        return self.status in [
            self.STATUS_CONFIRMED, self.STATUS_SENT, self.STATUS_PARTIALLY_RECEIVED
        ]

    @property
    def is_fully_received(self):
        return self.status == self.STATUS_RECEIVED

    @property
    def is_fully_invoiced(self):
        return self.status == self.STATUS_INVOICED


class PurchaseOrderLine(CompanyBaseModel):
    """Ligne de commande fournisseur."""
    order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Commande"
    )
    rfq_line = models.ForeignKey(
        RequestForQuotationLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_lines',
        verbose_name="Ligne RFQ d'origine"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_order_lines',
        verbose_name="Produit"
    )
    product_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom produit (saisie libre)",
        help_text="Nom du produit non enregistré"
    )
    description = models.TextField(blank=True, verbose_name="Description")
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name="Quantité commandée"
    )
    quantity_received = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité reçue"
    )
    quantity_invoiced = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité facturée"
    )
    unit = models.ForeignKey(
        'catalog.UnitOfMeasure',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_order_lines',
        verbose_name="Unité"
    )

    unit_price = MoneyField(verbose_name="Prix unitaire HT")
    discount_percent = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Remise (%)"
    )
    discount_amount = MoneyField(verbose_name="Montant remise")

    tax_rate = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Taux TVA (%)"
    )
    tax_amount = MoneyField(verbose_name="Montant TVA")

    subtotal = MoneyField(verbose_name="Sous-total HT")
    total = MoneyField(verbose_name="Total TTC")

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'purchasing_order_line'
        verbose_name = "Ligne de commande fournisseur"
        verbose_name_plural = "Lignes de commande fournisseur"
        ordering = ['order', 'sequence', 'id']

    def __str__(self):
        return f"{self.order.number} - {self.product_name_display}"

    @property
    def product_name_display(self):
        if self.product:
            return self.product.name
        return self.product_name_manual or 'Produit inconnu'

    def calculate_totals(self):
        """Calcule les totaux de la ligne."""
        gross = self.quantity * self.unit_price
        if self.discount_percent > 0:
            self.discount_amount = gross * (self.discount_percent / 100)
        self.subtotal = gross - self.discount_amount
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax_amount

    @property
    def quantity_remaining(self):
        """Quantité restante à recevoir."""
        return self.quantity - self.quantity_received

    @property
    def is_fully_received(self):
        return self.quantity_received >= self.quantity

    @property
    def is_fully_invoiced(self):
        return self.quantity_invoiced >= self.quantity


# =============================================================================
# GOODS RECEIPTS
# =============================================================================

class GoodsReceipt(CompanyBaseModel):
    """Réception de marchandises."""
    STATUS_DRAFT = 'draft'
    STATUS_VALIDATED = 'validated'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_VALIDATED, 'Validé'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Généré automatiquement"
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name='goods_receipts',
        verbose_name="Commande fournisseur"
    )
    supplier = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='goods_receipts',
        verbose_name="Fournisseur"
    )
    supplier_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom fournisseur (saisie libre)",
        help_text="Nom du fournisseur non enregistré"
    )

    date = models.DateField(verbose_name="Date de réception")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    delivery_note_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="N° bon de livraison fournisseur"
    )
    carrier = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Transporteur"
    )
    tracking_number = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="N° de suivi"
    )

    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.PROTECT,
        related_name='goods_receipts',
        verbose_name="Entrepôt"
    )

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='goods_receipts',
        verbose_name="Réceptionné par"
    )
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'purchasing_goods_receipt'
        verbose_name = "Réception de marchandises"
        verbose_name_plural = "Réceptions de marchandises"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.supplier_name_display}"

    @property
    def supplier_name_display(self):
        """Returns supplier name from registered partner or manual entry."""
        if self.supplier:
            return self.supplier.name
        return self.supplier_name_manual or 'Fournisseur inconnu'

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_validated(self):
        return self.status == self.STATUS_VALIDATED


class GoodsReceiptLine(CompanyBaseModel):
    """Ligne de réception de marchandises."""
    receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Réception"
    )
    order_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        related_name='receipt_lines',
        verbose_name="Ligne de commande"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='goods_receipt_lines',
        verbose_name="Produit"
    )
    product_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom produit (saisie libre)",
        help_text="Nom du produit non enregistré"
    )
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    quantity_expected = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="Quantité attendue"
    )
    quantity_received = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Quantité reçue"
    )
    quantity_rejected = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité rejetée"
    )
    unit = models.ForeignKey(
        'catalog.UnitOfMeasure',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='goods_receipt_lines',
        verbose_name="Unité"
    )

    lot_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="N° de lot"
    )
    serial_numbers = models.TextField(
        blank=True,
        verbose_name="N° de série (un par ligne)"
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date d'expiration"
    )

    location = models.ForeignKey(
        'inventory.WarehouseLocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='goods_receipt_lines',
        verbose_name="Emplacement"
    )

    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Motif de rejet"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'purchasing_goods_receipt_line'
        verbose_name = "Ligne de réception"
        verbose_name_plural = "Lignes de réception"
        ordering = ['receipt', 'sequence', 'id']

    def __str__(self):
        return f"{self.receipt.number} - {self.product_name_display}"

    @property
    def product_name_display(self):
        if self.product:
            return self.product.name
        return self.product_name_manual or 'Produit inconnu'

    @property
    def quantity_accepted(self):
        """Quantité acceptée (reçue - rejetée)."""
        return self.quantity_received - self.quantity_rejected


# =============================================================================
# SUPPLIER INVOICES
# =============================================================================

class SupplierInvoice(CompanyBaseModel):
    """Facture fournisseur."""
    STATUS_DRAFT = 'draft'
    STATUS_VALIDATED = 'validated'
    STATUS_PARTIALLY_PAID = 'partially_paid'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_VALIDATED, 'Validé'),
        (STATUS_PARTIALLY_PAID, 'Partiellement payé'),
        (STATUS_PAID, 'Payé'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    TYPE_INVOICE = 'invoice'
    TYPE_CREDIT_NOTE = 'credit_note'
    TYPE_DEBIT_NOTE = 'debit_note'

    TYPE_CHOICES = [
        (TYPE_INVOICE, 'Facture'),
        (TYPE_CREDIT_NOTE, 'Avoir'),
        (TYPE_DEBIT_NOTE, 'Note de débit'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro interne",
        help_text="Généré automatiquement"
    )
    supplier_invoice_number = models.CharField(
        max_length=100,
        verbose_name="N° facture fournisseur"
    )
    invoice_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_INVOICE,
        verbose_name="Type"
    )

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_invoices',
        verbose_name="Commande fournisseur"
    )
    supplier = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='supplier_invoices',
        verbose_name="Fournisseur"
    )
    supplier_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom fournisseur (saisie libre)",
        help_text="Nom du fournisseur non enregistré"
    )

    date = models.DateField(verbose_name="Date de facture")
    due_date = models.DateField(verbose_name="Date d'échéance")
    received_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de réception"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='supplier_invoices',
        verbose_name="Devise"
    )
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name="Taux de change"
    )

    subtotal = MoneyField(verbose_name="Sous-total HT")
    tax_total = MoneyField(verbose_name="Total TVA")
    discount_total = MoneyField(verbose_name="Total remise")
    total = MoneyField(verbose_name="Total TTC")

    amount_paid = MoneyField(verbose_name="Montant payé")
    amount_due = MoneyField(verbose_name="Montant dû")

    payment_terms = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Conditions de paiement"
    )
    payment_reference = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Référence de paiement"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    three_way_match_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'En attente'),
            ('matched', 'Correspondant'),
            ('discrepancy', 'Écart détecté'),
            ('approved', 'Approuvé'),
        ],
        default='pending',
        verbose_name="Statut rapprochement"
    )
    three_way_match_notes = models.TextField(
        blank=True,
        verbose_name="Notes de rapprochement"
    )

    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_invoices_validated',
        verbose_name="Validé par"
    )
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation"
    )

    accounting_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de comptabilisation"
    )
    journal_entry = models.ForeignKey(
        'accounting.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_invoices',
        verbose_name="Écriture comptable"
    )

    class Meta:
        db_table = 'purchasing_supplier_invoice'
        verbose_name = "Facture fournisseur"
        verbose_name_plural = "Factures fournisseur"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.supplier_name_display}"

    @property
    def supplier_name_display(self):
        """Returns supplier name from registered partner or manual entry."""
        if self.supplier:
            return self.supplier.name
        return self.supplier_name_manual or 'Fournisseur inconnu'

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_validated(self):
        return self.status not in [self.STATUS_DRAFT, self.STATUS_CANCELLED]

    @property
    def is_paid(self):
        return self.status == self.STATUS_PAID

    @property
    def is_overdue(self):
        from django.utils import timezone
        return (
            self.status in [self.STATUS_VALIDATED, self.STATUS_PARTIALLY_PAID]
            and self.due_date < timezone.now().date()
        )

    @property
    def is_credit_note(self):
        return self.invoice_type == self.TYPE_CREDIT_NOTE

    def update_payment_status(self):
        """Met à jour le statut de paiement."""
        self.amount_due = self.total - self.amount_paid
        if self.amount_paid >= self.total:
            self.status = self.STATUS_PAID
        elif self.amount_paid > 0:
            self.status = self.STATUS_PARTIALLY_PAID


class SupplierInvoiceLine(CompanyBaseModel):
    """Ligne de facture fournisseur."""
    invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Facture"
    )
    order_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines',
        verbose_name="Ligne de commande"
    )
    receipt_line = models.ForeignKey(
        GoodsReceiptLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines',
        verbose_name="Ligne de réception"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='supplier_invoice_lines',
        verbose_name="Produit"
    )
    product_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom produit (saisie libre)",
        help_text="Nom du produit non enregistré"
    )
    description = models.TextField(blank=True, verbose_name="Description")
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name="Quantité"
    )
    unit_price = MoneyField(verbose_name="Prix unitaire HT")
    discount_percent = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Remise (%)"
    )
    discount_amount = MoneyField(verbose_name="Montant remise")

    tax_rate = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Taux TVA (%)"
    )
    tax_amount = MoneyField(verbose_name="Montant TVA")

    subtotal = MoneyField(verbose_name="Sous-total HT")
    total = MoneyField(verbose_name="Total TTC")

    three_way_match_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'En attente'),
            ('matched', 'Correspondant'),
            ('quantity_mismatch', 'Écart quantité'),
            ('price_mismatch', 'Écart prix'),
            ('approved', 'Approuvé'),
        ],
        default='pending',
        verbose_name="Statut rapprochement"
    )

    class Meta:
        db_table = 'purchasing_supplier_invoice_line'
        verbose_name = "Ligne de facture fournisseur"
        verbose_name_plural = "Lignes de facture fournisseur"
        ordering = ['invoice', 'sequence', 'id']

    def __str__(self):
        return f"{self.invoice.number} - {self.product_name_display}"

    @property
    def product_name_display(self):
        if self.product:
            return self.product.name
        return self.product_name_manual or 'Produit inconnu'

    def calculate_totals(self):
        """Calcule les totaux de la ligne."""
        gross = self.quantity * self.unit_price
        if self.discount_percent > 0:
            self.discount_amount = gross * (self.discount_percent / 100)
        self.subtotal = gross - self.discount_amount
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax_amount
