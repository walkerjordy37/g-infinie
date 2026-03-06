"""
Accounting models - Chart of accounts, journals, entries (OHADA compliant).
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from apps.core.models import CompanyBaseModel, MoneyField


class AccountType(CompanyBaseModel):
    """Type de compte OHADA."""
    CLASS_CHOICES = [
        ('1', 'Classe 1 - Comptes de ressources durables'),
        ('2', 'Classe 2 - Comptes d\'actif immobilisé'),
        ('3', 'Classe 3 - Comptes de stocks'),
        ('4', 'Classe 4 - Comptes de tiers'),
        ('5', 'Classe 5 - Comptes de trésorerie'),
        ('6', 'Classe 6 - Comptes de charges'),
        ('7', 'Classe 7 - Comptes de produits'),
        ('8', 'Classe 8 - Comptes des autres charges'),
        ('9', 'Classe 9 - Comptes analytiques'),
    ]

    NATURE_CHOICES = [
        ('asset', 'Actif'),
        ('liability', 'Passif'),
        ('equity', 'Capitaux propres'),
        ('income', 'Produits'),
        ('expense', 'Charges'),
    ]

    code = models.CharField(max_length=10, verbose_name="Code")
    name = models.CharField(max_length=200, verbose_name="Libellé")
    account_class = models.CharField(
        max_length=1,
        choices=CLASS_CHOICES,
        verbose_name="Classe OHADA"
    )
    nature = models.CharField(
        max_length=20,
        choices=NATURE_CHOICES,
        verbose_name="Nature"
    )
    is_debit_balance = models.BooleanField(
        default=True,
        verbose_name="Solde débiteur par défaut"
    )

    class Meta:
        db_table = 'accounting_account_type'
        verbose_name = "Type de compte"
        verbose_name_plural = "Types de compte"
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Account(CompanyBaseModel):
    """Compte du plan comptable OHADA."""
    code = models.CharField(max_length=20, verbose_name="Code comptable")
    name = models.CharField(max_length=200, verbose_name="Libellé")
    account_type = models.ForeignKey(
        AccountType,
        on_delete=models.PROTECT,
        related_name='accounts',
        verbose_name="Type de compte"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Compte parent"
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_reconcilable = models.BooleanField(
        default=False,
        verbose_name="Lettrable"
    )
    is_detail = models.BooleanField(
        default=True,
        verbose_name="Compte de détail"
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounts',
        verbose_name="Devise"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'accounting_account'
        verbose_name = "Compte"
        verbose_name_plural = "Plan comptable"
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def full_code(self):
        if self.parent:
            return f"{self.parent.code}{self.code}"
        return self.code


class Journal(CompanyBaseModel):
    """Journal comptable."""
    TYPE_SALES = 'sales'
    TYPE_PURCHASES = 'purchases'
    TYPE_BANK = 'bank'
    TYPE_CASH = 'cash'
    TYPE_GENERAL = 'general'

    TYPE_CHOICES = [
        (TYPE_SALES, 'Journal des ventes'),
        (TYPE_PURCHASES, 'Journal des achats'),
        (TYPE_BANK, 'Journal de banque'),
        (TYPE_CASH, 'Journal de caisse'),
        (TYPE_GENERAL, 'Journal des opérations diverses'),
    ]

    code = models.CharField(max_length=10, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Libellé")
    journal_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_GENERAL,
        verbose_name="Type"
    )

    default_debit_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_debit_journals',
        verbose_name="Compte débit par défaut"
    )
    default_credit_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_credit_journals',
        verbose_name="Compte crédit par défaut"
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    sequence_prefix = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Préfixe de séquence"
    )
    next_sequence = models.PositiveIntegerField(
        default=1,
        verbose_name="Prochain numéro"
    )

    class Meta:
        db_table = 'accounting_journal'
        verbose_name = "Journal"
        verbose_name_plural = "Journaux"
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_next_number(self):
        number = f"{self.sequence_prefix}{self.next_sequence:06d}"
        self.next_sequence += 1
        self.save(update_fields=['next_sequence'])
        return number


class JournalEntry(CompanyBaseModel):
    """Écriture comptable."""
    STATUS_DRAFT = 'draft'
    STATUS_POSTED = 'posted'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_POSTED, 'Validée'),
        (STATUS_CANCELLED, 'Annulée'),
    ]

    number = models.CharField(max_length=50, verbose_name="Numéro")
    journal = models.ForeignKey(
        Journal,
        on_delete=models.PROTECT,
        related_name='entries',
        verbose_name="Journal"
    )
    date = models.DateField(verbose_name="Date comptable")
    fiscal_year = models.ForeignKey(
        'tenancy.FiscalYear',
        on_delete=models.PROTECT,
        related_name='journal_entries',
        verbose_name="Exercice"
    )
    fiscal_period = models.ForeignKey(
        'tenancy.FiscalPeriod',
        on_delete=models.PROTECT,
        related_name='journal_entries',
        verbose_name="Période"
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence"
    )
    description = models.TextField(verbose_name="Libellé")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    total_debit = MoneyField(verbose_name="Total débit")
    total_credit = MoneyField(verbose_name="Total crédit")

    reversal_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversals',
        verbose_name="Extourne de"
    )
    is_reversal = models.BooleanField(default=False, verbose_name="Est une extourne")

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posted_entries',
        verbose_name="Validée par"
    )
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation"
    )

    class Meta:
        db_table = 'accounting_journal_entry'
        verbose_name = "Écriture comptable"
        verbose_name_plural = "Écritures comptables"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.description[:50]}"

    def clean(self):
        if self.status == self.STATUS_POSTED:
            if self.total_debit != self.total_credit:
                raise ValidationError(
                    "L'écriture n'est pas équilibrée (débit ≠ crédit)."
                )

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_posted(self):
        return self.status == self.STATUS_POSTED

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit


class JournalEntryLine(CompanyBaseModel):
    """Ligne d'écriture comptable."""
    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Écriture"
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='entry_lines',
        verbose_name="Compte"
    )
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    label = models.CharField(max_length=200, verbose_name="Libellé")
    debit = MoneyField(verbose_name="Débit")
    credit = MoneyField(verbose_name="Crédit")

    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_entry_lines',
        verbose_name="Tiers"
    )
    analytic_account = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Compte analytique"
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence"
    )

    reconciled = models.BooleanField(default=False, verbose_name="Lettrée")
    reconciliation_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="N° lettrage"
    )

    class Meta:
        db_table = 'accounting_journal_entry_line'
        verbose_name = "Ligne d'écriture"
        verbose_name_plural = "Lignes d'écriture"
        ordering = ['entry', 'sequence', 'id']

    def __str__(self):
        return f"{self.account.code} - {self.label}"

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError(
                "Une ligne ne peut pas avoir à la fois un débit et un crédit."
            )
        if self.debit == 0 and self.credit == 0:
            raise ValidationError(
                "Une ligne doit avoir un débit ou un crédit."
            )


class AccountBalance(CompanyBaseModel):
    """Solde de compte par période."""
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='balances',
        verbose_name="Compte"
    )
    fiscal_period = models.ForeignKey(
        'tenancy.FiscalPeriod',
        on_delete=models.CASCADE,
        related_name='account_balances',
        verbose_name="Période"
    )

    opening_debit = MoneyField(verbose_name="Débit ouverture")
    opening_credit = MoneyField(verbose_name="Crédit ouverture")
    period_debit = MoneyField(verbose_name="Débit période")
    period_credit = MoneyField(verbose_name="Crédit période")
    closing_debit = MoneyField(verbose_name="Débit clôture")
    closing_credit = MoneyField(verbose_name="Crédit clôture")

    class Meta:
        db_table = 'accounting_account_balance'
        verbose_name = "Solde de compte"
        verbose_name_plural = "Soldes de comptes"
        unique_together = ['company', 'account', 'fiscal_period']
        ordering = ['account__code', 'fiscal_period']

    def __str__(self):
        return f"{self.account.code} - {self.fiscal_period}"

    @property
    def balance(self):
        return (self.closing_debit - self.closing_credit)
