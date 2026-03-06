"""
Workflow models - Approval workflows, steps, and instances.
"""
from django.db import models
from django.conf import settings
from apps.core.models import CompanyBaseModel, MoneyField


class WorkflowDefinition(CompanyBaseModel):
    """Définition d'un workflow."""
    ENTITY_CHOICES = [
        ('purchase_request', 'Demande d\'achat'),
        ('purchase_order', 'Commande fournisseur'),
        ('sales_quote', 'Devis'),
        ('sales_order', 'Commande client'),
        ('supplier_invoice', 'Facture fournisseur'),
        ('expense', 'Note de frais'),
        ('journal_entry', 'Écriture comptable'),
    ]

    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    entity_type = models.CharField(
        max_length=50,
        choices=ENTITY_CHOICES,
        verbose_name="Type d'entité"
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_sequential = models.BooleanField(
        default=True,
        verbose_name="Approbation séquentielle"
    )

    conditions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Conditions d'activation"
    )

    class Meta:
        db_table = 'workflow_definition'
        verbose_name = "Définition de workflow"
        verbose_name_plural = "Définitions de workflows"
        unique_together = ['company', 'code']
        ordering = ['entity_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_entity_type_display()})"


class WorkflowStep(CompanyBaseModel):
    """Étape d'un workflow."""
    ACTION_APPROVE = 'approve'
    ACTION_REVIEW = 'review'
    ACTION_NOTIFY = 'notify'

    ACTION_CHOICES = [
        (ACTION_APPROVE, 'Approbation'),
        (ACTION_REVIEW, 'Révision'),
        (ACTION_NOTIFY, 'Notification'),
    ]

    workflow = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name="Workflow"
    )
    sequence = models.PositiveIntegerField(verbose_name="Ordre")
    name = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        default=ACTION_APPROVE,
        verbose_name="Type d'action"
    )

    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_steps_assigned',
        verbose_name="Approbateur"
    )
    approver_role = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Rôle approbateur"
    )

    amount_threshold = MoneyField(
        null=True,
        blank=True,
        verbose_name="Seuil montant"
    )
    auto_approve_below = models.BooleanField(
        default=False,
        verbose_name="Auto-approuver sous le seuil"
    )

    timeout_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Timeout (heures)"
    )
    escalate_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_escalations',
        verbose_name="Escalader vers"
    )

    is_required = models.BooleanField(default=True, verbose_name="Obligatoire")

    class Meta:
        db_table = 'workflow_step'
        verbose_name = "Étape de workflow"
        verbose_name_plural = "Étapes de workflow"
        unique_together = ['workflow', 'sequence']
        ordering = ['workflow', 'sequence']

    def __str__(self):
        return f"{self.workflow.name} - {self.sequence}. {self.name}"


class WorkflowInstance(CompanyBaseModel):
    """Instance d'exécution d'un workflow."""
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_IN_PROGRESS, 'En cours'),
        (STATUS_APPROVED, 'Approuvé'),
        (STATUS_REJECTED, 'Rejeté'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    workflow = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.PROTECT,
        related_name='instances',
        verbose_name="Workflow"
    )
    content_type = models.CharField(
        max_length=100,
        verbose_name="Type d'entité"
    )
    object_id = models.UUIDField(verbose_name="ID de l'entité")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="Statut"
    )
    current_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_instances',
        verbose_name="Étape courante"
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Démarré le"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Terminé le"
    )

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='workflow_instances_initiated',
        verbose_name="Initié par"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Métadonnées"
    )

    class Meta:
        db_table = 'workflow_instance'
        verbose_name = "Instance de workflow"
        verbose_name_plural = "Instances de workflows"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.workflow.name} - {self.object_id}"

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING

    @property
    def is_completed(self):
        return self.status in [self.STATUS_APPROVED, self.STATUS_REJECTED]


class WorkflowAction(CompanyBaseModel):
    """Action effectuée dans un workflow."""
    ACTION_SUBMIT = 'submit'
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_REQUEST_INFO = 'request_info'
    ACTION_DELEGATE = 'delegate'
    ACTION_ESCALATE = 'escalate'

    ACTION_CHOICES = [
        (ACTION_SUBMIT, 'Soumis'),
        (ACTION_APPROVE, 'Approuvé'),
        (ACTION_REJECT, 'Rejeté'),
        (ACTION_REQUEST_INFO, 'Demande d\'info'),
        (ACTION_DELEGATE, 'Délégué'),
        (ACTION_ESCALATE, 'Escaladé'),
    ]

    instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name='actions',
        verbose_name="Instance"
    )
    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.SET_NULL,
        null=True,
        related_name='actions',
        verbose_name="Étape"
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name="Action"
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='workflow_actions',
        verbose_name="Effectué par"
    )
    performed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date"
    )

    comments = models.TextField(blank=True, verbose_name="Commentaires")
    delegated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_delegations_received',
        verbose_name="Délégué à"
    )

    class Meta:
        db_table = 'workflow_action'
        verbose_name = "Action de workflow"
        verbose_name_plural = "Actions de workflow"
        ordering = ['performed_at']

    def __str__(self):
        return f"{self.instance} - {self.get_action_display()}"


class WorkflowNotification(CompanyBaseModel):
    """Notification de workflow."""
    instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Instance"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workflow_notifications',
        verbose_name="Destinataire"
    )
    message = models.TextField(verbose_name="Message")
    is_read = models.BooleanField(default=False, verbose_name="Lu")
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Lu le"
    )

    class Meta:
        db_table = 'workflow_notification'
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification pour {self.recipient}"
