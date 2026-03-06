"""Sync models for offline action tracking."""
import uuid
from django.db import models
from django.conf import settings


class SyncActionLog(models.Model):
    """Log of sync actions for idempotency."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='sync_action_logs'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sync_action_logs'
    )
    action_id = models.UUIDField(verbose_name="ID action client")
    action_type = models.CharField(max_length=50, verbose_name="Type d'action")
    entity_id = models.UUIDField(null=True, blank=True, verbose_name="ID entité")
    status = models.CharField(
        max_length=20,
        choices=[
            ('applied', 'Appliqué'),
            ('duplicate', 'Doublon'),
            ('failed', 'Échoué'),
        ],
        verbose_name="Statut"
    )
    error = models.TextField(blank=True, verbose_name="Erreur")
    payload = models.JSONField(default=dict, verbose_name="Données")
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sync_action_log'
        verbose_name = "Log d'action sync"
        verbose_name_plural = "Logs d'actions sync"
        unique_together = ['company', 'action_id']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} - {self.action_id} ({self.status})"
