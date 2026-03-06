"""
Audit models - Tracking changes and user actions.
"""
import uuid
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class AuditLog(models.Model):
    """Audit log for tracking all important actions."""
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_VIEW = 'view'
    ACTION_EXPORT = 'export'
    ACTION_PRINT = 'print'
    ACTION_POST = 'post'
    ACTION_CANCEL = 'cancel'
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'

    ACTION_CHOICES = [
        (ACTION_CREATE, 'Création'),
        (ACTION_UPDATE, 'Modification'),
        (ACTION_DELETE, 'Suppression'),
        (ACTION_VIEW, 'Consultation'),
        (ACTION_EXPORT, 'Export'),
        (ACTION_PRINT, 'Impression'),
        (ACTION_POST, 'Validation'),
        (ACTION_CANCEL, 'Annulation'),
        (ACTION_APPROVE, 'Approbation'),
        (ACTION_REJECT, 'Rejet'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # User info
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    user_email = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Company context
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )

    # Action info
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    module = models.CharField(max_length=50, db_index=True)
    description = models.TextField(blank=True)

    # Target object (generic foreign key)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=255, blank=True, db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    object_repr = models.CharField(max_length=255, blank=True)

    # Change data
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    changes = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'audit_log'
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'action']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['company', 'timestamp']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.user_email} - {self.action} - {self.object_repr}"

    @classmethod
    def log(cls, user, action, obj=None, old_values=None, new_values=None,
            description='', request=None, company=None, module=None):
        """Create an audit log entry."""
        log_entry = cls(
            user=user if user and user.is_authenticated else None,
            user_email=user.email if user and user.is_authenticated else '',
            action=action,
            description=description,
            old_values=old_values,
            new_values=new_values,
            company=company,
            module=module or ''
        )

        if request:
            log_entry.ip_address = cls._get_client_ip(request)
            log_entry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            if not company and hasattr(request, 'company'):
                log_entry.company = request.company

        if obj:
            log_entry.content_type = ContentType.objects.get_for_model(obj)
            log_entry.object_id = str(obj.pk)
            log_entry.object_repr = str(obj)[:255]
            if not module:
                log_entry.module = obj._meta.app_label

        if old_values and new_values:
            log_entry.changes = cls._compute_changes(old_values, new_values)

        log_entry.save()
        return log_entry

    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @staticmethod
    def _compute_changes(old_values, new_values):
        """Compute the differences between old and new values."""
        changes = {}
        all_keys = set(old_values.keys()) | set(new_values.keys())
        for key in all_keys:
            old_val = old_values.get(key)
            new_val = new_values.get(key)
            if old_val != new_val:
                changes[key] = {'old': old_val, 'new': new_val}
        return changes


class ActivityLog(models.Model):
    """Simpler activity log for user actions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='activities'
    )
    action = models.CharField(max_length=100)
    details = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'activity_log'
        verbose_name = "Journal d'activité"
        verbose_name_plural = "Journaux d'activité"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.timestamp}"
