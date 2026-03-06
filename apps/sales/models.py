"""
Sales models - Quotes, Orders, Delivery Notes, Invoices, Returns.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import CompanyBaseModel, MoneyField, PercentageField


class SalesQuote(CompanyBaseModel):
    """Devis client."""
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_EXPIRED = 'expired'
    STATUS_CONVERTED = 'converted'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_SENT, 'Envoyé'),
        (STATUS_ACCEPTED, 'Accepté'),
        (STATUS_REJECTED, 'Refusé'),
        (STATUS_EXPIRED, 'Expiré'),
        (STATUS_CONVERTED, 'Converti'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Généré automatiquement"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_quotes',
        verbose_name="Client"
    )
    partner_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom client (saisie libre)",
        help_text="Nom du client non enregistré"
    )
    date = models.DateField(verbose_name="Date")
    validity_date = models.DateField(verbose_name="Date de validité")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='sales_quotes',
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

    notes = models.TextField(blank=True, verbose_name="Notes")
    terms = models.TextField(blank=True, verbose_name="Conditions")

    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_quotes',
        verbose_name="Commercial"
    )

    class Meta:
        db_table = 'sales_quote'
        verbose_name = "Devis"
        verbose_name_plural = "Devis"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.partner_name_display}"

    @property
    def partner_name_display(self):
        """Returns partner name from registered partner or manual entry."""
        if self.partner:
            return self.partner.name
        return self.partner_name_manual or 'Client inconnu'

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.validity_date < timezone.now().date() and self.status == self.STATUS_SENT

    @property
    def can_convert(self):
        return self.status == self.STATUS_ACCEPTED


class SalesQuoteLine(CompanyBaseModel):
    """Ligne de devis."""
    quote = models.ForeignKey(
        SalesQuote,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Devis"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_quote_lines',
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

    class Meta:
        db_table = 'sales_quote_line'
        verbose_name = "Ligne de devis"
        verbose_name_plural = "Lignes de devis"
        ordering = ['quote', 'sequence', 'id']

    def __str__(self):
        return f"{self.quote.number} - {self.product_name_display}"

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


class SalesOrder(CompanyBaseModel):
    """Commande client."""
    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'
    STATUS_INVOICED = 'invoiced'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_CONFIRMED, 'Confirmé'),
        (STATUS_PROCESSING, 'En cours'),
        (STATUS_SHIPPED, 'Expédié'),
        (STATUS_DELIVERED, 'Livré'),
        (STATUS_INVOICED, 'Facturé'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    number = models.CharField(max_length=50, verbose_name="Numéro")
    quote = models.ForeignKey(
        SalesQuote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name="Devis d'origine"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_orders',
        verbose_name="Client"
    )
    partner_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom client (saisie libre)",
        help_text="Nom du client non enregistré"
    )
    date = models.DateField(verbose_name="Date")
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
        related_name='sales_orders',
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

    notes = models.TextField(blank=True, verbose_name="Notes")
    terms = models.TextField(blank=True, verbose_name="Conditions")

    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_orders',
        verbose_name="Commercial"
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_orders',
        verbose_name="Entrepôt"
    )

    class Meta:
        db_table = 'sales_order'
        verbose_name = "Commande client"
        verbose_name_plural = "Commandes clients"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.partner_name_display}"

    @property
    def partner_name_display(self):
        """Returns partner name from registered partner or manual entry."""
        if self.partner:
            return self.partner.name
        return self.partner_name_manual or 'Client inconnu'

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    @property
    def is_cancelled(self):
        return self.status == self.STATUS_CANCELLED

    @property
    def can_deliver(self):
        return self.status in [self.STATUS_CONFIRMED, self.STATUS_PROCESSING]

    @property
    def can_invoice(self):
        return self.status in [
            self.STATUS_CONFIRMED,
            self.STATUS_PROCESSING,
            self.STATUS_SHIPPED,
            self.STATUS_DELIVERED
        ]


class SalesOrderLine(CompanyBaseModel):
    """Ligne de commande client."""
    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Commande"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_order_lines',
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
    quantity_delivered = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité livrée"
    )
    quantity_invoiced = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité facturée"
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

    class Meta:
        db_table = 'sales_order_line'
        verbose_name = "Ligne de commande client"
        verbose_name_plural = "Lignes de commande client"
        ordering = ['order', 'sequence', 'id']

    def __str__(self):
        return f"{self.order.number} - {self.product_name_display}"

    @property
    def product_name_display(self):
        if self.product:
            return self.product.name
        return self.product_name_manual or 'Produit inconnu'

    @property
    def quantity_remaining(self):
        return self.quantity - self.quantity_delivered

    @property
    def quantity_to_invoice(self):
        return self.quantity_delivered - self.quantity_invoiced

    def calculate_totals(self):
        """Calcule les totaux de la ligne."""
        gross = self.quantity * self.unit_price
        if self.discount_percent > 0:
            self.discount_amount = gross * (self.discount_percent / 100)
        self.subtotal = gross - self.discount_amount
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax_amount


class DeliveryNote(CompanyBaseModel):
    """Bon de livraison."""
    STATUS_DRAFT = 'draft'
    STATUS_READY = 'ready'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_READY, 'Prêt'),
        (STATUS_SHIPPED, 'Expédié'),
        (STATUS_DELIVERED, 'Livré'),
    ]

    number = models.CharField(max_length=50, verbose_name="Numéro")
    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name='delivery_notes',
        verbose_name="Commande"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        related_name='delivery_notes',
        verbose_name="Client"
    )
    date = models.DateField(verbose_name="Date")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    shipping_address = models.TextField(blank=True, verbose_name="Adresse de livraison")
    carrier = models.CharField(max_length=100, blank=True, verbose_name="Transporteur")
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Numéro de suivi"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    shipped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shipped_delivery_notes',
        verbose_name="Expédié par"
    )
    shipped_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'expédition"
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de livraison"
    )

    class Meta:
        db_table = 'delivery_note'
        verbose_name = "Bon de livraison"
        verbose_name_plural = "Bons de livraison"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.partner.name}"

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_delivered(self):
        return self.status == self.STATUS_DELIVERED


class DeliveryNoteLine(CompanyBaseModel):
    """Ligne de bon de livraison."""
    delivery_note = models.ForeignKey(
        DeliveryNote,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Bon de livraison"
    )
    order_line = models.ForeignKey(
        SalesOrderLine,
        on_delete=models.PROTECT,
        related_name='delivery_lines',
        verbose_name="Ligne de commande"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        related_name='delivery_note_lines',
        verbose_name="Produit"
    )
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    quantity_ordered = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="Quantité commandée"
    )
    quantity_delivered = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Quantité livrée"
    )

    class Meta:
        db_table = 'delivery_note_line'
        verbose_name = "Ligne de bon de livraison"
        verbose_name_plural = "Lignes de bon de livraison"
        ordering = ['delivery_note', 'sequence', 'id']

    def __str__(self):
        return f"{self.delivery_note.number} - {self.product.name}"


class SalesInvoice(CompanyBaseModel):
    """Facture client."""
    STATUS_DRAFT = 'draft'
    STATUS_VALIDATED = 'validated'
    STATUS_SENT = 'sent'
    STATUS_PARTIALLY_PAID = 'partially_paid'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_VALIDATED, 'Validée'),
        (STATUS_SENT, 'Envoyée'),
        (STATUS_PARTIALLY_PAID, 'Partiellement payée'),
        (STATUS_PAID, 'Payée'),
        (STATUS_CANCELLED, 'Annulée'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Numéro légal, immuable une fois validé"
    )
    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name="Commande"
    )
    delivery_note = models.ForeignKey(
        DeliveryNote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name="Bon de livraison"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_invoices',
        verbose_name="Client"
    )
    partner_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom client (saisie libre)",
        help_text="Nom du client non enregistré"
    )
    date = models.DateField(verbose_name="Date de facture")
    due_date = models.DateField(verbose_name="Date d'échéance")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='sales_invoices',
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

    notes = models.TextField(blank=True, verbose_name="Notes")
    terms = models.TextField(blank=True, verbose_name="Conditions de paiement")

    is_posted = models.BooleanField(
        default=False,
        verbose_name="Comptabilisée",
        help_text="La facture a été enregistrée en comptabilité"
    )
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de comptabilisation"
    )
    journal_entry = models.ForeignKey(
        'accounting.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_invoices',
        verbose_name="Écriture comptable"
    )

    class Meta:
        db_table = 'sales_invoice'
        verbose_name = "Facture client"
        verbose_name_plural = "Factures clients"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.partner_name_display}"

    @property
    def partner_name_display(self):
        """Returns partner name from registered partner or manual entry."""
        if self.partner:
            return self.partner.name
        return self.partner_name_manual or 'Client inconnu'

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_validated(self):
        return self.status != self.STATUS_DRAFT and self.status != self.STATUS_CANCELLED

    @property
    def is_paid(self):
        return self.status == self.STATUS_PAID

    @property
    def is_overdue(self):
        from django.utils import timezone
        return (
            self.status in [self.STATUS_VALIDATED, self.STATUS_SENT, self.STATUS_PARTIALLY_PAID]
            and self.due_date < timezone.now().date()
        )

    def update_payment_status(self):
        """Met à jour le statut de paiement."""
        self.amount_due = self.total - self.amount_paid
        if self.amount_paid >= self.total:
            self.status = self.STATUS_PAID
        elif self.amount_paid > 0:
            self.status = self.STATUS_PARTIALLY_PAID


class SalesInvoiceLine(CompanyBaseModel):
    """Ligne de facture client."""
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Facture"
    )
    order_line = models.ForeignKey(
        SalesOrderLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines',
        verbose_name="Ligne de commande"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_invoice_lines',
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

    class Meta:
        db_table = 'sales_invoice_line'
        verbose_name = "Ligne de facture client"
        verbose_name_plural = "Lignes de facture client"
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


class SalesReturn(CompanyBaseModel):
    """Retour client (avoir)."""
    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_PROCESSED = 'processed'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_CONFIRMED, 'Confirmé'),
        (STATUS_PROCESSED, 'Traité'),
    ]

    REASON_DEFECTIVE = 'defective'
    REASON_WRONG_PRODUCT = 'wrong_product'
    REASON_DAMAGED = 'damaged'
    REASON_NOT_NEEDED = 'not_needed'
    REASON_OTHER = 'other'

    REASON_CHOICES = [
        (REASON_DEFECTIVE, 'Produit défectueux'),
        (REASON_WRONG_PRODUCT, 'Produit erroné'),
        (REASON_DAMAGED, 'Produit endommagé'),
        (REASON_NOT_NEEDED, 'Plus besoin'),
        (REASON_OTHER, 'Autre'),
    ]

    number = models.CharField(max_length=50, verbose_name="Numéro")
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.PROTECT,
        related_name='returns',
        verbose_name="Facture d'origine"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_returns',
        verbose_name="Client"
    )
    partner_name_manual = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Nom client (saisie libre)",
        help_text="Nom du client non enregistré"
    )
    date = models.DateField(verbose_name="Date")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        default=REASON_OTHER,
        verbose_name="Motif"
    )
    reason_details = models.TextField(blank=True, verbose_name="Détails du motif")

    subtotal = MoneyField(verbose_name="Sous-total HT")
    tax_total = MoneyField(verbose_name="Total TVA")
    total = MoneyField(verbose_name="Total TTC")

    credit_note = models.ForeignKey(
        SalesInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='credit_returns',
        verbose_name="Avoir généré"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'sales_return'
        verbose_name = "Retour client"
        verbose_name_plural = "Retours clients"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.partner_name_display}"

    @property
    def partner_name_display(self):
        """Returns partner name from registered partner or manual entry."""
        if self.partner:
            return self.partner.name
        return self.partner_name_manual or 'Client inconnu'

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT


class SalesReturnLine(CompanyBaseModel):
    """Ligne de retour client."""
    sales_return = models.ForeignKey(
        SalesReturn,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Retour"
    )
    invoice_line = models.ForeignKey(
        SalesInvoiceLine,
        on_delete=models.PROTECT,
        related_name='return_lines',
        verbose_name="Ligne de facture"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_return_lines',
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

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name="Quantité retournée"
    )
    unit_price = MoneyField(verbose_name="Prix unitaire HT")
    tax_rate = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Taux TVA (%)"
    )
    tax_amount = MoneyField(verbose_name="Montant TVA")
    subtotal = MoneyField(verbose_name="Sous-total HT")
    total = MoneyField(verbose_name="Total TTC")

    class Meta:
        db_table = 'sales_return_line'
        verbose_name = "Ligne de retour client"
        verbose_name_plural = "Lignes de retour client"
        ordering = ['sales_return', 'sequence', 'id']

    def __str__(self):
        return f"{self.sales_return.number} - {self.product_name_display}"

    @property
    def product_name_display(self):
        if self.product:
            return self.product.name
        return self.product_name_manual or 'Produit inconnu'

    def calculate_totals(self):
        """Calcule les totaux de la ligne."""
        self.subtotal = self.quantity * self.unit_price
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax_amount
