"""
Partners models - Customers (clients) and Suppliers (fournisseurs).
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import CompanyBaseModel, MoneyField, PercentageField


class PartnerCategory(CompanyBaseModel):
    """Category for grouping partners."""
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Catégorie parente"
    )

    class Meta:
        db_table = 'partner_category'
        verbose_name = "Catégorie de partenaire"
        verbose_name_plural = "Catégories de partenaires"
        unique_together = ['company', 'code']
        ordering = ['name']

    def __str__(self):
        return self.name


class Partner(CompanyBaseModel):
    """Main partner model for customers and suppliers."""
    TYPE_CUSTOMER = 'customer'
    TYPE_SUPPLIER = 'supplier'
    TYPE_BOTH = 'both'

    TYPE_CHOICES = [
        (TYPE_CUSTOMER, 'Client'),
        (TYPE_SUPPLIER, 'Fournisseur'),
        (TYPE_BOTH, 'Client et Fournisseur'),
    ]

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_CUSTOMER,
        verbose_name="Type"
    )
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=255, verbose_name="Nom")
    legal_name = models.CharField(max_length=255, blank=True, verbose_name="Raison sociale")

    category = models.ForeignKey(
        PartnerCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partners',
        verbose_name="Catégorie"
    )

    tax_id = models.CharField(max_length=50, blank=True, verbose_name="N° contribuable")
    trade_register = models.CharField(max_length=50, blank=True, verbose_name="RCCM")

    street = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
    street2 = models.CharField(max_length=255, blank=True, verbose_name="Adresse (suite)")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    state = models.CharField(max_length=100, blank=True, verbose_name="Région")
    postal_code = models.CharField(max_length=20, blank=True, verbose_name="Code postal")
    country = models.CharField(max_length=100, default='Cameroun', verbose_name="Pays")

    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    mobile = models.CharField(max_length=50, blank=True, verbose_name="Mobile")
    fax = models.CharField(max_length=50, blank=True, verbose_name="Fax")
    email = models.EmailField(blank=True, verbose_name="Email")
    website = models.URLField(blank=True, verbose_name="Site web")

    credit_limit = MoneyField(verbose_name="Limite de crédit")
    payment_terms_days = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Délai de paiement (jours)"
    )
    discount_rate = PercentageField(
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name="Taux de remise (%)"
    )

    customer_accounting_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Compte comptable client"
    )
    supplier_accounting_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Compte comptable fournisseur"
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='partners',
        verbose_name="Devise"
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'partner'
        verbose_name = "Partenaire"
        verbose_name_plural = "Partenaires"
        unique_together = ['company', 'code']
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def is_customer(self):
        return self.type in (self.TYPE_CUSTOMER, self.TYPE_BOTH)

    @property
    def is_supplier(self):
        return self.type in (self.TYPE_SUPPLIER, self.TYPE_BOTH)

    def save(self, *args, **kwargs):
        if not self.customer_accounting_code and self.is_customer:
            self.customer_accounting_code = f"411{self.code[:3].upper()}"
        if not self.supplier_accounting_code and self.is_supplier:
            self.supplier_accounting_code = f"401{self.code[:3].upper()}"
        super().save(*args, **kwargs)


class PartnerContact(CompanyBaseModel):
    """Multiple contacts for a partner."""
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='contacts',
        verbose_name="Partenaire"
    )
    name = models.CharField(max_length=255, verbose_name="Nom")
    title = models.CharField(max_length=100, blank=True, verbose_name="Fonction")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    mobile = models.CharField(max_length=50, blank=True, verbose_name="Mobile")
    email = models.EmailField(blank=True, verbose_name="Email")
    is_primary = models.BooleanField(default=False, verbose_name="Contact principal")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'partner_contact'
        verbose_name = "Contact"
        verbose_name_plural = "Contacts"
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return f"{self.name} ({self.partner.name})"


class PartnerAddress(CompanyBaseModel):
    """Billing and shipping addresses for a partner."""
    TYPE_BILLING = 'billing'
    TYPE_SHIPPING = 'shipping'
    TYPE_BOTH = 'both'

    TYPE_CHOICES = [
        (TYPE_BILLING, 'Facturation'),
        (TYPE_SHIPPING, 'Livraison'),
        (TYPE_BOTH, 'Facturation et Livraison'),
    ]

    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name="Partenaire"
    )
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_BOTH,
        verbose_name="Type"
    )
    name = models.CharField(max_length=255, blank=True, verbose_name="Nom de l'adresse")
    street = models.CharField(max_length=255, verbose_name="Adresse")
    street2 = models.CharField(max_length=255, blank=True, verbose_name="Adresse (suite)")
    city = models.CharField(max_length=100, verbose_name="Ville")
    state = models.CharField(max_length=100, blank=True, verbose_name="Région")
    postal_code = models.CharField(max_length=20, blank=True, verbose_name="Code postal")
    country = models.CharField(max_length=100, default='Cameroun', verbose_name="Pays")
    is_default = models.BooleanField(default=False, verbose_name="Adresse par défaut")

    class Meta:
        db_table = 'partner_address'
        verbose_name = "Adresse"
        verbose_name_plural = "Adresses"
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f"{self.name or self.type} - {self.city}"


class PartnerBankAccount(CompanyBaseModel):
    """Bank account details for a partner."""
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        verbose_name="Partenaire"
    )
    bank_name = models.CharField(max_length=255, verbose_name="Nom de la banque")
    bank_code = models.CharField(max_length=20, blank=True, verbose_name="Code banque")
    branch_code = models.CharField(max_length=20, blank=True, verbose_name="Code guichet")
    account_number = models.CharField(max_length=50, verbose_name="Numéro de compte")
    iban = models.CharField(max_length=50, blank=True, verbose_name="IBAN")
    swift_bic = models.CharField(max_length=20, blank=True, verbose_name="SWIFT/BIC")
    account_holder = models.CharField(max_length=255, blank=True, verbose_name="Titulaire du compte")
    is_default = models.BooleanField(default=False, verbose_name="Compte par défaut")

    class Meta:
        db_table = 'partner_bank_account'
        verbose_name = "Compte bancaire"
        verbose_name_plural = "Comptes bancaires"
        ordering = ['-is_default', 'bank_name']

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"
