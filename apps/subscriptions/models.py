"""
Subscriptions models - SaaS platform subscription management.
Manages which companies pay for the ERP service.
"""
from datetime import date
from django.db import models
from apps.core.models import UUIDModel, TimeStampedModel


class PlatformPlan(UUIDModel, TimeStampedModel):
    """Plan tarifaire de la plateforme SaaS (global, non lié à une company)."""

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code"
    )
    name = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")

    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Prix mensuel"
    )
    yearly_price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Prix annuel"
    )

    max_users = models.PositiveIntegerField(
        default=1,
        verbose_name="Nombre max d'utilisateurs",
        help_text="0 = illimité"
    )
    max_products = models.PositiveIntegerField(
        default=50,
        verbose_name="Nombre max de produits",
        help_text="0 = illimité"
    )

    has_scanner = models.BooleanField(default=False, verbose_name="Scanner")
    has_csv_import = models.BooleanField(default=False, verbose_name="Import CSV")
    has_full_cycles = models.BooleanField(default=False, verbose_name="Cycles complets")
    has_dashboard = models.BooleanField(default=False, verbose_name="Tableau de bord")
    has_multi_site = models.BooleanField(default=False, verbose_name="Multi-site")
    has_offline_mode = models.BooleanField(default=False, verbose_name="Mode hors-ligne")
    has_whatsapp_alerts = models.BooleanField(default=False, verbose_name="Alertes WhatsApp")
    has_api_access = models.BooleanField(default=False, verbose_name="Accès API")

    trial_days = models.PositiveIntegerField(default=30, verbose_name="Jours d'essai")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        db_table = 'platform_plan'
        verbose_name = "Plan plateforme"
        verbose_name_plural = "Plans plateforme"
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.name} ({self.monthly_price} XOF/mois)"


class CompanySubscription(UUIDModel, TimeStampedModel):
    """Abonnement d'une company à la plateforme SaaS."""

    STATUS_TRIAL = 'trial'
    STATUS_ACTIVE = 'active'
    STATUS_PAST_DUE = 'past_due'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_TRIAL, 'Essai'),
        (STATUS_ACTIVE, 'Actif'),
        (STATUS_PAST_DUE, 'Impayé'),
        (STATUS_SUSPENDED, 'Suspendu'),
        (STATUS_CANCELLED, 'Annulé'),
        (STATUS_EXPIRED, 'Expiré'),
    ]

    BILLING_MONTHLY = 'monthly'
    BILLING_YEARLY = 'yearly'

    BILLING_CHOICES = [
        (BILLING_MONTHLY, 'Mensuel'),
        (BILLING_YEARLY, 'Annuel'),
    ]

    company = models.OneToOneField(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name="Entreprise"
    )
    plan = models.ForeignKey(
        PlatformPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name="Plan"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_TRIAL,
        verbose_name="Statut"
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CHOICES,
        default=BILLING_MONTHLY,
        verbose_name="Cycle de facturation"
    )

    start_date = models.DateField(verbose_name="Date de début")
    trial_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fin de l'essai"
    )
    current_period_start = models.DateField(verbose_name="Début période courante")
    current_period_end = models.DateField(verbose_name="Fin période courante")

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Montant facturé"
    )

    auto_renew = models.BooleanField(default=True, verbose_name="Renouvellement auto")
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date d'annulation"
    )
    cancellation_reason = models.TextField(
        blank=True,
        verbose_name="Motif d'annulation"
    )

    class Meta:
        db_table = 'company_subscription'
        verbose_name = "Abonnement entreprise"
        verbose_name_plural = "Abonnements entreprises"

    def __str__(self):
        return f"{self.company} - {self.plan.name} ({self.get_status_display()})"

    @property
    def is_active(self):
        return self.status in [self.STATUS_TRIAL, self.STATUS_ACTIVE]

    @property
    def is_trial(self):
        return self.status == self.STATUS_TRIAL

    @property
    def is_expired(self):
        return self.status in [self.STATUS_EXPIRED, self.STATUS_SUSPENDED, self.STATUS_CANCELLED]

    @property
    def days_remaining(self):
        return (self.current_period_end - date.today()).days

    def can_add_user(self, current_count):
        return self.plan.max_users == 0 or current_count < self.plan.max_users

    def can_add_product(self, current_count):
        return self.plan.max_products == 0 or current_count < self.plan.max_products


class PaymentTransaction(UUIDModel, TimeStampedModel):
    """Transaction de paiement pour un abonnement."""

    PAYMENT_WAVE = 'wave'
    PAYMENT_ORANGE_MONEY = 'orange_money'
    PAYMENT_MTN_MONEY = 'mtn_money'
    PAYMENT_CARD = 'card'
    PAYMENT_MANUAL = 'manual'

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_WAVE, 'Wave'),
        (PAYMENT_ORANGE_MONEY, 'Orange Money'),
        (PAYMENT_MTN_MONEY, 'MTN Money'),
        (PAYMENT_CARD, 'Carte bancaire'),
        (PAYMENT_MANUAL, 'Manuel'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_COMPLETED, 'Complété'),
        (STATUS_FAILED, 'Échoué'),
        (STATUS_REFUNDED, 'Remboursé'),
    ]

    subscription = models.ForeignKey(
        CompanySubscription,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name="Abonnement"
    )
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="ID transaction"
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name="Moyen de paiement"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name="Montant"
    )
    currency_code = models.CharField(
        max_length=3,
        default='XOF',
        verbose_name="Devise"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="Statut"
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Numéro de téléphone"
    )
    provider_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence fournisseur"
    )
    provider_response = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Réponse fournisseur"
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="Message d'erreur"
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de paiement"
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Métadonnées"
    )

    class Meta:
        db_table = 'payment_transaction'
        verbose_name = "Transaction de paiement"
        verbose_name_plural = "Transactions de paiement"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_id} - {self.amount} {self.currency_code} ({self.get_status_display()})"
