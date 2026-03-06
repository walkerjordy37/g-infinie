"""
Treasury models - Bank accounts, cash registers, statements, reconciliation.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from apps.core.models import CompanyBaseModel, MoneyField


class BankAccount(CompanyBaseModel):
    """Company bank account."""
    TYPE_CHECKING = 'checking'
    TYPE_SAVINGS = 'savings'
    TYPE_DEPOSIT = 'deposit'
    TYPE_OTHER = 'other'

    TYPE_CHOICES = [
        (TYPE_CHECKING, 'Compte courant'),
        (TYPE_SAVINGS, 'Compte épargne'),
        (TYPE_DEPOSIT, 'Compte à terme'),
        (TYPE_OTHER, 'Autre'),
    ]

    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=255, verbose_name="Nom du compte")
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_CHECKING,
        verbose_name="Type"
    )

    bank_name = models.CharField(max_length=255, verbose_name="Nom de la banque")
    bank_code = models.CharField(max_length=20, blank=True, verbose_name="Code banque")
    branch_code = models.CharField(max_length=20, blank=True, verbose_name="Code guichet")
    account_number = models.CharField(max_length=50, verbose_name="Numéro de compte")
    rib_key = models.CharField(max_length=5, blank=True, verbose_name="Clé RIB")

    iban = models.CharField(
        max_length=34,
        blank=True,
        verbose_name="IBAN",
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{4,30}$',
                message="Format IBAN invalide"
            )
        ]
    )
    bic = models.CharField(
        max_length=11,
        blank=True,
        verbose_name="BIC/SWIFT",
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$',
                message="Format BIC/SWIFT invalide"
            )
        ]
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='bank_accounts',
        verbose_name="Devise"
    )

    initial_balance = MoneyField(verbose_name="Solde initial")
    current_balance = MoneyField(verbose_name="Solde actuel")
    last_statement_balance = MoneyField(verbose_name="Dernier solde relevé")
    last_statement_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date dernier relevé"
    )

    accounting_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Compte comptable"
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_default = models.BooleanField(default=False, verbose_name="Compte par défaut")
    allow_overdraft = models.BooleanField(default=False, verbose_name="Autoriser découvert")
    overdraft_limit = MoneyField(verbose_name="Limite de découvert")

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'treasury_bank_account'
        verbose_name = "Compte bancaire"
        verbose_name_plural = "Comptes bancaires"
        unique_together = ['company', 'code']
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.accounting_code:
            self.accounting_code = f"512{self.code[:3].upper()}"
        super().save(*args, **kwargs)


class CashRegister(CompanyBaseModel):
    """Cash register (caisse)."""
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=255, verbose_name="Nom de la caisse")

    branch = models.ForeignKey(
        'tenancy.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_registers',
        verbose_name="Succursale"
    )

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='cash_registers',
        verbose_name="Devise"
    )

    initial_balance = MoneyField(verbose_name="Solde initial")
    current_balance = MoneyField(verbose_name="Solde actuel")

    accounting_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Compte comptable"
    )

    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_registers',
        verbose_name="Responsable"
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    max_balance = MoneyField(verbose_name="Solde maximum autorisé")

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'treasury_cash_register'
        verbose_name = "Caisse"
        verbose_name_plural = "Caisses"
        unique_together = ['company', 'code']
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.accounting_code:
            self.accounting_code = f"531{self.code[:3].upper()}"
        super().save(*args, **kwargs)


class BankStatement(CompanyBaseModel):
    """Imported bank statement."""
    STATUS_DRAFT = 'draft'
    STATUS_IMPORTED = 'imported'
    STATUS_RECONCILED = 'reconciled'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_IMPORTED, 'Importé'),
        (STATUS_RECONCILED, 'Rapproché'),
        (STATUS_CLOSED, 'Clôturé'),
    ]

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='statements',
        verbose_name="Compte bancaire"
    )

    reference = models.CharField(max_length=100, verbose_name="Référence")
    date = models.DateField(verbose_name="Date du relevé")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")

    opening_balance = MoneyField(verbose_name="Solde d'ouverture")
    closing_balance = MoneyField(verbose_name="Solde de clôture")
    total_debits = MoneyField(verbose_name="Total débits")
    total_credits = MoneyField(verbose_name="Total crédits")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    import_format = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Format d'import",
        help_text="OFX, CSV, MT940, etc."
    )
    import_file = models.FileField(
        upload_to='bank_statements/',
        blank=True,
        null=True,
        verbose_name="Fichier importé"
    )
    imported_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'import"
    )
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_statements',
        verbose_name="Importé par"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'treasury_bank_statement'
        verbose_name = "Relevé bancaire"
        verbose_name_plural = "Relevés bancaires"
        unique_together = ['bank_account', 'reference']
        ordering = ['-date']

    def __str__(self):
        return f"{self.bank_account.name} - {self.reference}"

    @property
    def line_count(self):
        return self.lines.count()

    @property
    def reconciled_count(self):
        return self.lines.filter(is_reconciled=True).count()


class BankStatementLine(CompanyBaseModel):
    """Line in a bank statement."""
    TYPE_DEBIT = 'debit'
    TYPE_CREDIT = 'credit'

    TYPE_CHOICES = [
        (TYPE_DEBIT, 'Débit'),
        (TYPE_CREDIT, 'Crédit'),
    ]

    statement = models.ForeignKey(
        BankStatement,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Relevé"
    )

    sequence = models.PositiveIntegerField(default=0, verbose_name="Séquence")
    date = models.DateField(verbose_name="Date")
    value_date = models.DateField(null=True, blank=True, verbose_name="Date de valeur")

    reference = models.CharField(max_length=100, blank=True, verbose_name="Référence")
    description = models.CharField(max_length=500, verbose_name="Libellé")
    partner_name = models.CharField(max_length=255, blank=True, verbose_name="Nom du tiers")

    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        verbose_name="Type"
    )
    amount = MoneyField(verbose_name="Montant")

    is_reconciled = models.BooleanField(default=False, verbose_name="Rapproché")
    reconciled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de rapprochement"
    )
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciled_statement_lines',
        verbose_name="Rapproché par"
    )

    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_statement_lines',
        verbose_name="Partenaire"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'treasury_bank_statement_line'
        verbose_name = "Ligne de relevé"
        verbose_name_plural = "Lignes de relevé"
        ordering = ['statement', 'sequence', 'date']

    def __str__(self):
        return f"{self.date} - {self.description[:50]} - {self.amount}"


class BankReconciliation(CompanyBaseModel):
    """Bank reconciliation linking statement lines to payments/journal entries."""
    statement_line = models.ForeignKey(
        BankStatementLine,
        on_delete=models.CASCADE,
        related_name='reconciliations',
        verbose_name="Ligne de relevé"
    )

    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_reconciliations',
        verbose_name="Paiement"
    )

    journal_entry = models.ForeignKey(
        'accounting.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_reconciliations',
        verbose_name="Écriture comptable"
    )

    amount = MoneyField(verbose_name="Montant rapproché")

    reconciled_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_reconciliations',
        verbose_name="Rapproché par"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'treasury_bank_reconciliation'
        verbose_name = "Rapprochement bancaire"
        verbose_name_plural = "Rapprochements bancaires"
        ordering = ['-reconciled_at']

    def __str__(self):
        return f"Rapprochement {self.statement_line} - {self.amount}"


class CashMovement(CompanyBaseModel):
    """Cash register movement."""
    TYPE_IN = 'in'
    TYPE_OUT = 'out'

    TYPE_CHOICES = [
        (TYPE_IN, 'Entrée'),
        (TYPE_OUT, 'Sortie'),
    ]

    REASON_SALE = 'sale'
    REASON_PURCHASE = 'purchase'
    REASON_EXPENSE = 'expense'
    REASON_DEPOSIT = 'deposit'
    REASON_WITHDRAWAL = 'withdrawal'
    REASON_TRANSFER = 'transfer'
    REASON_ADJUSTMENT = 'adjustment'
    REASON_OTHER = 'other'

    REASON_CHOICES = [
        (REASON_SALE, 'Vente'),
        (REASON_PURCHASE, 'Achat'),
        (REASON_EXPENSE, 'Frais'),
        (REASON_DEPOSIT, 'Dépôt en banque'),
        (REASON_WITHDRAWAL, 'Retrait'),
        (REASON_TRANSFER, 'Transfert'),
        (REASON_ADJUSTMENT, 'Ajustement'),
        (REASON_OTHER, 'Autre'),
    ]

    cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.CASCADE,
        related_name='movements',
        verbose_name="Caisse"
    )

    number = models.CharField(max_length=50, verbose_name="Numéro")
    date = models.DateField(verbose_name="Date")
    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        verbose_name="Type"
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        default=REASON_OTHER,
        verbose_name="Motif"
    )

    amount = MoneyField(verbose_name="Montant")
    balance_before = MoneyField(verbose_name="Solde avant")
    balance_after = MoneyField(verbose_name="Solde après")

    description = models.CharField(max_length=500, verbose_name="Libellé")
    reference = models.CharField(max_length=100, blank=True, verbose_name="Référence")

    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_movements',
        verbose_name="Partenaire"
    )

    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_movements',
        verbose_name="Paiement"
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_movements',
        verbose_name="Effectué par"
    )

    is_validated = models.BooleanField(default=False, verbose_name="Validé")
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
        related_name='validated_cash_movements',
        verbose_name="Validé par"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'treasury_cash_movement'
        verbose_name = "Mouvement de caisse"
        verbose_name_plural = "Mouvements de caisse"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.get_type_display()} - {self.amount}"


class Transfer(CompanyBaseModel):
    """Transfer between bank accounts and/or cash registers."""
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_PENDING, 'En attente'),
        (STATUS_COMPLETED, 'Effectué'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    number = models.CharField(max_length=50, verbose_name="Numéro")
    date = models.DateField(verbose_name="Date")

    from_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='outgoing_transfers',
        verbose_name="Compte bancaire source"
    )
    from_cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='outgoing_transfers',
        verbose_name="Caisse source"
    )

    to_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='incoming_transfers',
        verbose_name="Compte bancaire destination"
    )
    to_cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='incoming_transfers',
        verbose_name="Caisse destination"
    )

    amount = MoneyField(verbose_name="Montant")
    fees = MoneyField(verbose_name="Frais bancaires")

    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='transfers',
        verbose_name="Devise"
    )
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name="Taux de change"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    description = models.CharField(max_length=500, blank=True, verbose_name="Libellé")
    reference = models.CharField(max_length=100, blank=True, verbose_name="Référence externe")

    executed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'exécution"
    )
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='executed_transfers',
        verbose_name="Exécuté par"
    )

    journal_entry = models.ForeignKey(
        'accounting.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfers',
        verbose_name="Écriture comptable"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'treasury_transfer'
        verbose_name = "Virement"
        verbose_name_plural = "Virements"
        unique_together = ['company', 'number']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.amount}"

    @property
    def source_label(self):
        if self.from_bank_account:
            return f"Banque: {self.from_bank_account.name}"
        elif self.from_cash_register:
            return f"Caisse: {self.from_cash_register.name}"
        return "-"

    @property
    def destination_label(self):
        if self.to_bank_account:
            return f"Banque: {self.to_bank_account.name}"
        elif self.to_cash_register:
            return f"Caisse: {self.to_cash_register.name}"
        return "-"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}

        if not self.from_bank_account and not self.from_cash_register:
            errors['from_bank_account'] = "Une source est requise."

        if not self.to_bank_account and not self.to_cash_register:
            errors['to_bank_account'] = "Une destination est requise."

        if self.from_bank_account and self.from_bank_account == self.to_bank_account:
            errors['to_bank_account'] = "La source et la destination doivent être différentes."

        if self.from_cash_register and self.from_cash_register == self.to_cash_register:
            errors['to_cash_register'] = "La source et la destination doivent être différentes."

        if errors:
            raise ValidationError(errors)
