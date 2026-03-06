"""
Payments models - Payment methods, terms, payments, allocations, refunds.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from apps.core.models import CompanyBaseModel, MoneyField


class PaymentMethod(CompanyBaseModel):
    """Méthode de paiement (espèces, chèque, virement, mobile money)."""
    TYPE_CASH = 'cash'
    TYPE_CHECK = 'check'
    TYPE_TRANSFER = 'transfer'
    TYPE_MOBILE_MONEY = 'mobile_money'
    TYPE_CARD = 'card'
    TYPE_OTHER = 'other'

    TYPE_CHOICES = [
        (TYPE_CASH, 'Espèces'),
        (TYPE_CHECK, 'Chèque'),
        (TYPE_TRANSFER, 'Virement bancaire'),
        (TYPE_MOBILE_MONEY, 'Mobile Money'),
        (TYPE_CARD, 'Carte bancaire'),
        (TYPE_OTHER, 'Autre'),
    ]

    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_CASH,
        verbose_name="Type"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    bank_account = models.ForeignKey(
        'treasury.BankAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_methods',
        verbose_name="Compte bancaire"
    )
    journal = models.ForeignKey(
        'accounting.Journal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_methods',
        verbose_name="Journal comptable"
    )

    requires_reference = models.BooleanField(
        default=False,
        verbose_name="Référence requise",
        help_text="Exige une référence (n° chèque, n° transaction, etc.)"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'payments_method'
        verbose_name = "Méthode de paiement"
        verbose_name_plural = "Méthodes de paiement"
        unique_together = ['company', 'code']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class PaymentTerm(CompanyBaseModel):
    """Conditions de paiement (30 jours, comptant, etc.)."""
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")

    days = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de jours",
        help_text="Délai de paiement en jours"
    )
    is_immediate = models.BooleanField(
        default=False,
        verbose_name="Paiement immédiat",
        help_text="Paiement comptant requis"
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Escompte (%)",
        help_text="Remise pour paiement anticipé"
    )
    discount_days = models.PositiveIntegerField(
        default=0,
        verbose_name="Jours pour escompte",
        help_text="Nombre de jours pour bénéficier de l'escompte"
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_default = models.BooleanField(default=False, verbose_name="Par défaut")

    class Meta:
        db_table = 'payments_term'
        verbose_name = "Condition de paiement"
        verbose_name_plural = "Conditions de paiement"
        unique_together = ['company', 'code']
        ordering = ['days', 'name']

    def __str__(self):
        if self.is_immediate:
            return f"{self.name} (Comptant)"
        return f"{self.name} ({self.days} jours)"

    def calculate_due_date(self, invoice_date):
        """Calcule la date d'échéance à partir de la date de facture."""
        from datetime import timedelta
        if self.is_immediate:
            return invoice_date
        return invoice_date + timedelta(days=self.days)

    def calculate_discount_date(self, invoice_date):
        """Calcule la date limite pour l'escompte."""
        from datetime import timedelta
        if self.discount_days > 0:
            return invoice_date + timedelta(days=self.discount_days)
        return None


class Payment(CompanyBaseModel):
    """Paiement client ou fournisseur."""
    TYPE_CUSTOMER = 'customer'
    TYPE_SUPPLIER = 'supplier'

    TYPE_CHOICES = [
        (TYPE_CUSTOMER, 'Client'),
        (TYPE_SUPPLIER, 'Fournisseur'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_RECONCILED = 'reconciled'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_CONFIRMED, 'Confirmé'),
        (STATUS_RECONCILED, 'Rapproché'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Généré automatiquement"
    )
    payment_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name="Type de paiement"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Partenaire"
    )

    date = models.DateField(verbose_name="Date de paiement")
    value_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de valeur",
        help_text="Date effective du mouvement bancaire"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Méthode de paiement"
    )
    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Devise"
    )
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name="Taux de change"
    )

    amount = MoneyField(
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant"
    )
    amount_allocated = MoneyField(verbose_name="Montant alloué")
    amount_unallocated = MoneyField(verbose_name="Montant non alloué")

    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence",
        help_text="N° chèque, n° transaction, etc."
    )
    memo = models.TextField(blank=True, verbose_name="Mémo")

    bank_account = models.ForeignKey(
        'treasury.BankAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name="Compte bancaire"
    )

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments_confirmed',
        verbose_name="Confirmé par"
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de confirmation"
    )

    journal_entry = models.ForeignKey(
        'accounting.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name="Écriture comptable"
    )

    class Meta:
        db_table = 'payments_payment'
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.partner.name} ({self.amount})"

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    @property
    def is_fully_allocated(self):
        return self.amount_unallocated <= Decimal('0')

    @property
    def is_customer_payment(self):
        return self.payment_type == self.TYPE_CUSTOMER

    @property
    def is_supplier_payment(self):
        return self.payment_type == self.TYPE_SUPPLIER

    def update_allocation_amounts(self):
        """Met à jour les montants alloués et non alloués."""
        total_allocated = sum(
            alloc.amount for alloc in self.allocations.filter(is_deleted=False)
        )
        self.amount_allocated = total_allocated
        self.amount_unallocated = self.amount - total_allocated


class PaymentAllocation(CompanyBaseModel):
    """Allocation d'un paiement sur une facture."""
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name="Paiement"
    )

    sales_invoice = models.ForeignKey(
        'sales.SalesInvoice',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payment_allocations',
        verbose_name="Facture client"
    )
    supplier_invoice = models.ForeignKey(
        'purchasing.SupplierInvoice',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payment_allocations',
        verbose_name="Facture fournisseur"
    )

    amount = MoneyField(
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant alloué"
    )
    allocation_date = models.DateField(verbose_name="Date d'allocation")

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'payments_allocation'
        verbose_name = "Allocation de paiement"
        verbose_name_plural = "Allocations de paiement"
        ordering = ['-allocation_date', '-created_at']

    def __str__(self):
        invoice = self.sales_invoice or self.supplier_invoice
        invoice_number = invoice.number if invoice else 'N/A'
        return f"{self.payment.number} → {invoice_number} ({self.amount})"

    @property
    def invoice(self):
        """Retourne la facture associée (client ou fournisseur)."""
        return self.sales_invoice or self.supplier_invoice

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.sales_invoice and not self.supplier_invoice:
            raise ValidationError("Une facture client ou fournisseur doit être spécifiée.")
        if self.sales_invoice and self.supplier_invoice:
            raise ValidationError("Seule une facture peut être spécifiée (client OU fournisseur).")


class Refund(CompanyBaseModel):
    """Remboursement client ou fournisseur."""
    TYPE_CUSTOMER = 'customer'
    TYPE_SUPPLIER = 'supplier'

    TYPE_CHOICES = [
        (TYPE_CUSTOMER, 'Client'),
        (TYPE_SUPPLIER, 'Fournisseur'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_CONFIRMED, 'Confirmé'),
        (STATUS_PAID, 'Payé'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    REASON_OVERPAYMENT = 'overpayment'
    REASON_CREDIT_NOTE = 'credit_note'
    REASON_CANCELLATION = 'cancellation'
    REASON_OTHER = 'other'

    REASON_CHOICES = [
        (REASON_OVERPAYMENT, 'Trop-perçu'),
        (REASON_CREDIT_NOTE, 'Avoir'),
        (REASON_CANCELLATION, 'Annulation'),
        (REASON_OTHER, 'Autre'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Généré automatiquement"
    )
    refund_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name="Type de remboursement"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        related_name='refunds',
        verbose_name="Partenaire"
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

    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='refunds',
        verbose_name="Méthode de paiement"
    )
    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='refunds',
        verbose_name="Devise"
    )
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name="Taux de change"
    )

    amount = MoneyField(
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant"
    )

    original_payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds',
        verbose_name="Paiement d'origine"
    )
    credit_note = models.ForeignKey(
        'sales.SalesInvoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds',
        verbose_name="Avoir associé"
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    bank_account = models.ForeignKey(
        'treasury.BankAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds',
        verbose_name="Compte bancaire"
    )

    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds_paid',
        verbose_name="Payé par"
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de paiement"
    )

    journal_entry = models.ForeignKey(
        'accounting.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds',
        verbose_name="Écriture comptable"
    )

    class Meta:
        db_table = 'payments_refund'
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.partner.name} ({self.amount})"

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    @property
    def is_customer_refund(self):
        return self.refund_type == self.TYPE_CUSTOMER

    @property
    def is_supplier_refund(self):
        return self.refund_type == self.TYPE_SUPPLIER
