"""
Core models - Base classes and mixins for all apps.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract model with created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Abstract model with UUID primary key."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted records."""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    """Abstract model with soft delete capability."""
    is_deleted = models.BooleanField(default=False, verbose_name="Supprimé")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de suppression")
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_deleted",
        verbose_name="Supprimé par"
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        """Mark record as deleted."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    def restore(self):
        """Restore soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])


class CompanyScopedManager(models.Manager):
    """Manager that filters by company from request context."""
    def get_queryset(self):
        return super().get_queryset()

    def for_company(self, company):
        """Filter queryset by company."""
        return self.get_queryset().filter(company=company)


class CompanyScopedModel(models.Model):
    """Abstract model scoped to a company."""
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
        verbose_name="Entreprise"
    )

    objects = CompanyScopedManager()

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """
    Base model combining UUID, timestamps, and soft delete.
    Use this as the base for most business entities.
    """
    class Meta:
        abstract = True


class CompanyBaseModel(BaseModel, CompanyScopedModel):
    """
    Base model for company-scoped entities.
    Most business objects should inherit from this.
    """
    class Meta:
        abstract = True


class MoneyField(models.DecimalField):
    """Custom field for monetary values."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', getattr(settings, 'MAX_DIGITS', 15))
        kwargs.setdefault('decimal_places', getattr(settings, 'DECIMAL_PLACES', 2))
        kwargs.setdefault('default', Decimal('0.00'))
        super().__init__(*args, **kwargs)


class PercentageField(models.DecimalField):
    """Custom field for percentage values (0-100)."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', 5)
        kwargs.setdefault('decimal_places', 2)
        kwargs.setdefault('default', Decimal('0.00'))
        super().__init__(*args, **kwargs)


class StatusMixin(models.Model):
    """Mixin for models with status workflow."""
    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_CONFIRMED, 'Confirmé'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )

    class Meta:
        abstract = True

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    @property
    def is_cancelled(self):
        return self.status == self.STATUS_CANCELLED
