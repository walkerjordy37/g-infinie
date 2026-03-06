"""
Tax models - Tax types, rates, groups, rules, withholding taxes, and declarations.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import CompanyBaseModel, MoneyField, PercentageField


# =============================================================================
# TAX TYPE
# =============================================================================

class TaxType(CompanyBaseModel):
    """Type de taxe (TVA, IS, Taxe locale, etc.)."""
    TYPE_VAT = 'vat'
    TYPE_CORPORATE = 'corporate'
    TYPE_WITHHOLDING = 'withholding'
    TYPE_LOCAL = 'local'
    TYPE_CUSTOMS = 'customs'
    TYPE_OTHER = 'other'

    TYPE_CHOICES = [
        (TYPE_VAT, 'TVA'),
        (TYPE_CORPORATE, 'Impôt sur les sociétés'),
        (TYPE_WITHHOLDING, 'Retenue à la source'),
        (TYPE_LOCAL, 'Taxe locale'),
        (TYPE_CUSTOMS, 'Droits de douane'),
        (TYPE_OTHER, 'Autre'),
    ]

    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    tax_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_VAT,
        verbose_name="Type"
    )
    description = models.TextField(blank=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    account_collected = models.ForeignKey(
        'accounting.Account',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tax_types_collected',
        verbose_name="Compte de TVA collectée"
    )
    account_deductible = models.ForeignKey(
        'accounting.Account',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tax_types_deductible',
        verbose_name="Compte de TVA déductible"
    )
    account_payable = models.ForeignKey(
        'accounting.Account',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tax_types_payable',
        verbose_name="Compte de taxe à payer"
    )

    class Meta:
        db_table = 'tax_type'
        verbose_name = "Type de taxe"
        verbose_name_plural = "Types de taxe"
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


# =============================================================================
# TAX RATE
# =============================================================================

class TaxRate(CompanyBaseModel):
    """Taux de taxe avec période de validité."""
    tax_type = models.ForeignKey(
        TaxType,
        on_delete=models.PROTECT,
        related_name='rates',
        verbose_name="Type de taxe"
    )
    name = models.CharField(max_length=100, verbose_name="Nom")
    rate = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Taux (%)"
    )
    description = models.TextField(blank=True, verbose_name="Description")

    valid_from = models.DateField(verbose_name="Valide à partir du")
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="Valide jusqu'au"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="Taux par défaut"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'tax_rate'
        verbose_name = "Taux de taxe"
        verbose_name_plural = "Taux de taxe"
        ordering = ['tax_type', '-valid_from']

    def __str__(self):
        return f"{self.name} ({self.rate}%)"

    @property
    def is_valid(self):
        """Vérifie si le taux est valide à la date courante."""
        from django.utils import timezone
        today = timezone.now().date()
        if self.valid_to:
            return self.valid_from <= today <= self.valid_to
        return self.valid_from <= today

    def is_valid_at(self, date):
        """Vérifie si le taux est valide à une date donnée."""
        if self.valid_to:
            return self.valid_from <= date <= self.valid_to
        return self.valid_from <= date


# =============================================================================
# TAX GROUP
# =============================================================================

class TaxGroup(CompanyBaseModel):
    """Groupe de taxes pour application multiple sur les produits."""
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    tax_rates = models.ManyToManyField(
        TaxRate,
        related_name='tax_groups',
        blank=True,
        verbose_name="Taux de taxe"
    )

    class Meta:
        db_table = 'tax_group'
        verbose_name = "Groupe de taxes"
        verbose_name_plural = "Groupes de taxes"
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def total_rate(self):
        """Calcule le taux total du groupe."""
        return sum(rate.rate for rate in self.tax_rates.filter(is_active=True))

    def get_applicable_rates(self, date=None):
        """Retourne les taux applicables à une date donnée."""
        from django.utils import timezone
        if date is None:
            date = timezone.now().date()
        return [
            rate for rate in self.tax_rates.filter(is_active=True)
            if rate.is_valid_at(date)
        ]


# =============================================================================
# TAX RULE
# =============================================================================

class TaxRule(CompanyBaseModel):
    """Règle d'application des taxes par type de transaction."""
    TRANSACTION_SALE = 'sale'
    TRANSACTION_PURCHASE = 'purchase'
    TRANSACTION_IMPORT = 'import'
    TRANSACTION_EXPORT = 'export'
    TRANSACTION_INTRA_EU = 'intra_eu'

    TRANSACTION_CHOICES = [
        (TRANSACTION_SALE, 'Vente'),
        (TRANSACTION_PURCHASE, 'Achat'),
        (TRANSACTION_IMPORT, 'Importation'),
        (TRANSACTION_EXPORT, 'Exportation'),
        (TRANSACTION_INTRA_EU, 'Intracommunautaire'),
    ]

    PARTNER_DOMESTIC = 'domestic'
    PARTNER_EU = 'eu'
    PARTNER_INTERNATIONAL = 'international'

    PARTNER_CHOICES = [
        (PARTNER_DOMESTIC, 'National'),
        (PARTNER_EU, 'Union Européenne'),
        (PARTNER_INTERNATIONAL, 'International'),
    ]

    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_CHOICES,
        verbose_name="Type de transaction"
    )
    partner_type = models.CharField(
        max_length=20,
        choices=PARTNER_CHOICES,
        default=PARTNER_DOMESTIC,
        verbose_name="Type de partenaire"
    )

    tax_group = models.ForeignKey(
        TaxGroup,
        on_delete=models.PROTECT,
        related_name='rules',
        verbose_name="Groupe de taxes"
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pays applicable"
    )

    product_category = models.ForeignKey(
        'catalog.ProductCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tax_rules',
        verbose_name="Catégorie de produit"
    )

    priority = models.PositiveIntegerField(
        default=0,
        verbose_name="Priorité",
        help_text="Plus la valeur est haute, plus la règle est prioritaire"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    valid_from = models.DateField(verbose_name="Valide à partir du")
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="Valide jusqu'au"
    )

    class Meta:
        db_table = 'tax_rule'
        verbose_name = "Règle de taxe"
        verbose_name_plural = "Règles de taxe"
        unique_together = ['company', 'code']
        ordering = ['-priority', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def is_valid_at(self, date):
        """Vérifie si la règle est valide à une date donnée."""
        if self.valid_to:
            return self.valid_from <= date <= self.valid_to
        return self.valid_from <= date


# =============================================================================
# WITHHOLDING TAX
# =============================================================================

class WithholdingTax(CompanyBaseModel):
    """Retenue à la source."""
    TYPE_PROFESSIONAL = 'professional'
    TYPE_RENTAL = 'rental'
    TYPE_DIVIDEND = 'dividend'
    TYPE_INTEREST = 'interest'
    TYPE_ROYALTY = 'royalty'
    TYPE_OTHER = 'other'

    TYPE_CHOICES = [
        (TYPE_PROFESSIONAL, 'Prestations professionnelles'),
        (TYPE_RENTAL, 'Revenus locatifs'),
        (TYPE_DIVIDEND, 'Dividendes'),
        (TYPE_INTEREST, 'Intérêts'),
        (TYPE_ROYALTY, 'Redevances'),
        (TYPE_OTHER, 'Autre'),
    ]

    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    withholding_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_PROFESSIONAL,
        verbose_name="Type de retenue"
    )
    description = models.TextField(blank=True, verbose_name="Description")

    rate = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Taux de retenue (%)"
    )
    threshold_amount = MoneyField(
        verbose_name="Seuil d'application",
        help_text="Montant minimum pour appliquer la retenue"
    )

    applies_to_residents = models.BooleanField(
        default=True,
        verbose_name="S'applique aux résidents"
    )
    applies_to_non_residents = models.BooleanField(
        default=True,
        verbose_name="S'applique aux non-résidents"
    )

    account_payable = models.ForeignKey(
        'accounting.Account',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='withholding_taxes',
        verbose_name="Compte de retenue à payer"
    )

    valid_from = models.DateField(verbose_name="Valide à partir du")
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="Valide jusqu'au"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'tax_withholding'
        verbose_name = "Retenue à la source"
        verbose_name_plural = "Retenues à la source"
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name} ({self.rate}%)"

    def calculate_withholding(self, amount):
        """Calcule le montant de la retenue."""
        if amount < self.threshold_amount:
            return Decimal('0')
        return amount * (self.rate / Decimal('100'))


# =============================================================================
# TAX DECLARATION
# =============================================================================

class TaxDeclaration(CompanyBaseModel):
    """Déclaration fiscale périodique."""
    STATUS_DRAFT = 'draft'
    STATUS_CALCULATED = 'calculated'
    STATUS_VALIDATED = 'validated'
    STATUS_SUBMITTED = 'submitted'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_CALCULATED, 'Calculé'),
        (STATUS_VALIDATED, 'Validé'),
        (STATUS_SUBMITTED, 'Soumis'),
        (STATUS_PAID, 'Payé'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    PERIOD_MONTHLY = 'monthly'
    PERIOD_QUARTERLY = 'quarterly'
    PERIOD_YEARLY = 'yearly'

    PERIOD_CHOICES = [
        (PERIOD_MONTHLY, 'Mensuelle'),
        (PERIOD_QUARTERLY, 'Trimestrielle'),
        (PERIOD_YEARLY, 'Annuelle'),
    ]

    number = models.CharField(
        max_length=50,
        verbose_name="Numéro",
        help_text="Généré automatiquement"
    )
    tax_type = models.ForeignKey(
        TaxType,
        on_delete=models.PROTECT,
        related_name='declarations',
        verbose_name="Type de taxe"
    )

    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        default=PERIOD_MONTHLY,
        verbose_name="Type de période"
    )
    period_start = models.DateField(verbose_name="Début de période")
    period_end = models.DateField(verbose_name="Fin de période")
    due_date = models.DateField(verbose_name="Date limite de dépôt")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    tax_collected = MoneyField(verbose_name="TVA collectée")
    tax_deductible = MoneyField(verbose_name="TVA déductible")
    credit_carried_forward = MoneyField(
        verbose_name="Crédit reporté",
        help_text="Crédit de TVA de la période précédente"
    )
    tax_due = MoneyField(verbose_name="Taxe à payer")
    credit_to_carry = MoneyField(
        verbose_name="Crédit à reporter",
        help_text="Crédit de TVA pour la période suivante"
    )

    calculated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de calcul"
    )
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tax_declarations_calculated',
        verbose_name="Calculé par"
    )

    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation"
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tax_declarations_validated',
        verbose_name="Validé par"
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de soumission"
    )
    submission_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence de soumission"
    )

    payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de paiement"
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence de paiement"
    )
    payment_amount = MoneyField(verbose_name="Montant payé")

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'tax_declaration'
        verbose_name = "Déclaration fiscale"
        verbose_name_plural = "Déclarations fiscales"
        unique_together = ['company', 'number']
        ordering = ['-period_start']

    def __str__(self):
        return f"{self.number} - {self.tax_type.name} ({self.period_start} - {self.period_end})"

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_calculated(self):
        return self.status == self.STATUS_CALCULATED

    @property
    def is_validated(self):
        return self.status in [
            self.STATUS_VALIDATED, self.STATUS_SUBMITTED, self.STATUS_PAID
        ]

    @property
    def is_overdue(self):
        from django.utils import timezone
        return (
            self.status in [self.STATUS_DRAFT, self.STATUS_CALCULATED, self.STATUS_VALIDATED]
            and self.due_date < timezone.now().date()
        )

    def calculate_totals(self):
        """Calcule les totaux à partir des lignes."""
        self.tax_collected = sum(
            line.tax_amount for line in self.lines.filter(line_type='collected')
        )
        self.tax_deductible = sum(
            line.tax_amount for line in self.lines.filter(line_type='deductible')
        )
        net = self.tax_collected - self.tax_deductible - self.credit_carried_forward
        if net > 0:
            self.tax_due = net
            self.credit_to_carry = Decimal('0')
        else:
            self.tax_due = Decimal('0')
            self.credit_to_carry = abs(net)


# =============================================================================
# TAX DECLARATION LINE
# =============================================================================

class TaxDeclarationLine(CompanyBaseModel):
    """Ligne de déclaration fiscale."""
    LINE_TYPE_COLLECTED = 'collected'
    LINE_TYPE_DEDUCTIBLE = 'deductible'

    LINE_TYPE_CHOICES = [
        (LINE_TYPE_COLLECTED, 'TVA collectée'),
        (LINE_TYPE_DEDUCTIBLE, 'TVA déductible'),
    ]

    declaration = models.ForeignKey(
        TaxDeclaration,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Déclaration"
    )
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.PROTECT,
        related_name='declaration_lines',
        verbose_name="Taux de taxe"
    )

    line_type = models.CharField(
        max_length=20,
        choices=LINE_TYPE_CHOICES,
        verbose_name="Type"
    )
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    base_amount = MoneyField(verbose_name="Base taxable")
    tax_amount = MoneyField(verbose_name="Montant de taxe")

    invoice_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de factures"
    )

    source_invoices = models.ManyToManyField(
        'sales.SalesInvoice',
        related_name='tax_declaration_lines_sales',
        blank=True,
        verbose_name="Factures clients"
    )
    source_supplier_invoices = models.ManyToManyField(
        'purchasing.SupplierInvoice',
        related_name='tax_declaration_lines_purchases',
        blank=True,
        verbose_name="Factures fournisseurs"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'tax_declaration_line'
        verbose_name = "Ligne de déclaration fiscale"
        verbose_name_plural = "Lignes de déclaration fiscale"
        ordering = ['declaration', 'sequence', 'id']

    def __str__(self):
        return f"{self.declaration.number} - {self.tax_rate.name} ({self.line_type})"
