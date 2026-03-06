"""
Tenancy models - Companies, branches, currencies, fiscal years.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import UUIDModel, TimeStampedModel


class Currency(UUIDModel, TimeStampedModel):
    """Currency definition."""
    code = models.CharField(max_length=3, unique=True, verbose_name="Code ISO")
    name = models.CharField(max_length=100, verbose_name="Nom")
    symbol = models.CharField(max_length=10, verbose_name="Symbole")
    decimal_places = models.PositiveSmallIntegerField(default=2, verbose_name="Décimales")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'currency'
        verbose_name = "Devise"
        verbose_name_plural = "Devises"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class ExchangeRate(UUIDModel, TimeStampedModel):
    """Exchange rate history."""
    from_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rates_from',
        verbose_name="Devise source"
    )
    to_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rates_to',
        verbose_name="Devise cible"
    )
    rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name="Taux"
    )
    date = models.DateField(verbose_name="Date")
    source = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Source"
    )

    class Meta:
        db_table = 'exchange_rate'
        verbose_name = "Taux de change"
        verbose_name_plural = "Taux de change"
        unique_together = ['from_currency', 'to_currency', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.from_currency.code}/{self.to_currency.code}: {self.rate} ({self.date})"


class Company(UUIDModel, TimeStampedModel):
    """Company/Organization entity."""
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    name = models.CharField(max_length=255, verbose_name="Raison sociale")
    legal_name = models.CharField(max_length=255, blank=True, verbose_name="Nom légal")
    tax_id = models.CharField(max_length=50, blank=True, verbose_name="N° contribuable")
    trade_register = models.CharField(max_length=50, blank=True, verbose_name="RCCM")

    # Address
    street = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
    street2 = models.CharField(max_length=255, blank=True, verbose_name="Adresse (suite)")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    state = models.CharField(max_length=100, blank=True, verbose_name="Région")
    postal_code = models.CharField(max_length=20, blank=True, verbose_name="Code postal")
    country = models.CharField(max_length=100, default='Cameroun', verbose_name="Pays")

    # Contact
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    website = models.URLField(blank=True, verbose_name="Site web")

    # Settings
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='companies',
        verbose_name="Devise principale"
    )
    fiscal_year_start_month = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Mois de début d'exercice"
    )
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    # Tax & alerts
    default_tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('18.00'),
        verbose_name="Taux de TVA par défaut (%)"
    )
    whatsapp_phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Téléphone WhatsApp pour alertes"
    )

    class Meta:
        db_table = 'company'
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"
        ordering = ['name']

    def __str__(self):
        return self.name


class Branch(UUIDModel, TimeStampedModel):
    """Branch/Location of a company."""
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='branches',
        verbose_name="Entreprise"
    )
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=255, verbose_name="Nom")

    # Address
    street = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_headquarters = models.BooleanField(default=False, verbose_name="Siège social")

    class Meta:
        db_table = 'branch'
        verbose_name = "Succursale"
        verbose_name_plural = "Succursales"
        unique_together = ['company', 'code']
        ordering = ['company', 'name']

    def __str__(self):
        return f"{self.company.code} - {self.name}"


class FiscalYear(UUIDModel, TimeStampedModel):
    """Fiscal year definition."""
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_LOCKED = 'locked'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Ouvert'),
        (STATUS_CLOSED, 'Clôturé'),
        (STATUS_LOCKED, 'Verrouillé'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='fiscal_years',
        verbose_name="Entreprise"
    )
    name = models.CharField(max_length=50, verbose_name="Nom")
    code = models.CharField(max_length=10, verbose_name="Code")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        verbose_name="Statut"
    )

    class Meta:
        db_table = 'fiscal_year'
        verbose_name = "Exercice fiscal"
        verbose_name_plural = "Exercices fiscaux"
        unique_together = ['company', 'code']
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.company.code} - {self.name}"

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN


class FiscalPeriod(UUIDModel, TimeStampedModel):
    """Fiscal period (month) within a fiscal year."""
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Ouvert'),
        (STATUS_CLOSED, 'Clôturé'),
    ]

    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.CASCADE,
        related_name='periods',
        verbose_name="Exercice"
    )
    name = models.CharField(max_length=50, verbose_name="Nom")
    number = models.PositiveSmallIntegerField(verbose_name="Numéro")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        verbose_name="Statut"
    )

    class Meta:
        db_table = 'fiscal_period'
        verbose_name = "Période comptable"
        verbose_name_plural = "Périodes comptables"
        unique_together = ['fiscal_year', 'number']
        ordering = ['fiscal_year', 'number']

    def __str__(self):
        return f"{self.fiscal_year.code} - {self.name}"


class DocumentSequence(UUIDModel, TimeStampedModel):
    """Sequence for document numbering."""
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='sequences',
        verbose_name="Entreprise"
    )
    document_type = models.CharField(max_length=50, verbose_name="Type de document")
    prefix = models.CharField(max_length=20, blank=True, verbose_name="Préfixe")
    suffix = models.CharField(max_length=20, blank=True, verbose_name="Suffixe")
    padding = models.PositiveSmallIntegerField(default=5, verbose_name="Remplissage")
    next_number = models.PositiveIntegerField(default=1, verbose_name="Prochain numéro")
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sequences',
        verbose_name="Exercice"
    )
    reset_on_fiscal_year = models.BooleanField(
        default=True,
        verbose_name="Réinitialiser par exercice"
    )

    class Meta:
        db_table = 'document_sequence'
        verbose_name = "Séquence de numérotation"
        verbose_name_plural = "Séquences de numérotation"
        unique_together = ['company', 'document_type', 'fiscal_year']

    def __str__(self):
        return f"{self.company.code} - {self.document_type}"

    def get_next_number(self):
        """Get and increment the next number (use with SELECT FOR UPDATE)."""
        number = self.next_number
        formatted = f"{self.prefix}{str(number).zfill(self.padding)}{self.suffix}"
        self.next_number = number + 1
        self.save(update_fields=['next_number'])
        return formatted


class CompanySettings(UUIDModel, TimeStampedModel):
    """Extended settings for a company."""
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='settings',
        verbose_name="Entreprise"
    )

    # Accounting settings
    default_receivable_account = models.CharField(
        max_length=20,
        default='411000',
        verbose_name="Compte client par défaut"
    )
    default_payable_account = models.CharField(
        max_length=20,
        default='401000',
        verbose_name="Compte fournisseur par défaut"
    )
    default_sales_account = models.CharField(
        max_length=20,
        default='701000',
        verbose_name="Compte de vente par défaut"
    )
    default_purchase_account = models.CharField(
        max_length=20,
        default='601000',
        verbose_name="Compte d'achat par défaut"
    )
    default_vat_collected_account = models.CharField(
        max_length=20,
        default='443100',
        verbose_name="Compte TVA collectée"
    )
    default_vat_deductible_account = models.CharField(
        max_length=20,
        default='445600',
        verbose_name="Compte TVA déductible"
    )

    # Sales settings
    default_payment_terms_days = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Délai de paiement par défaut (jours)"
    )
    quote_validity_days = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Validité des devis (jours)"
    )

    # Inventory settings
    default_valuation_method = models.CharField(
        max_length=20,
        choices=[
            ('fifo', 'FIFO'),
            ('lifo', 'LIFO'),
            ('average', 'Coût moyen pondéré'),
        ],
        default='average',
        verbose_name="Méthode de valorisation"
    )
    allow_negative_stock = models.BooleanField(
        default=False,
        verbose_name="Autoriser stock négatif"
    )

    # Invoice settings
    invoice_notes = models.TextField(blank=True, verbose_name="Notes sur factures")
    invoice_footer = models.TextField(blank=True, verbose_name="Pied de page factures")

    class Meta:
        db_table = 'company_settings'
        verbose_name = "Paramètres entreprise"
        verbose_name_plural = "Paramètres entreprises"

    def __str__(self):
        return f"Paramètres - {self.company.name}"
