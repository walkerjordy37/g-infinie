"""
Workflow services.
"""
from django.db import transaction
from django.utils import timezone

from .models import (
    WorkflowDefinition, WorkflowStep, WorkflowInstance,
    WorkflowAction, WorkflowNotification
)


class WorkflowService:
    """Service pour la gestion des workflows."""

    def __init__(self, company):
        self.company = company

    def get_workflow_for_entity(self, entity_type: str, amount=None) -> WorkflowDefinition:
        """
        Trouve le workflow applicable pour une entité.

        Args:
            entity_type: Le type d'entité
            amount: Le montant (pour les conditions)

        Returns:
            Le workflow applicable ou None
        """
        workflows = WorkflowDefinition.objects.filter(
            company=self.company,
            entity_type=entity_type,
            is_active=True
        ).prefetch_related('steps')

        for workflow in workflows:
            if self._check_conditions(workflow, amount):
                return workflow

        return None

    def _check_conditions(self, workflow: WorkflowDefinition, amount=None) -> bool:
        """Vérifie les conditions d'activation du workflow."""
        conditions = workflow.conditions or {}

        if 'min_amount' in conditions and amount:
            if amount < conditions['min_amount']:
                return False

        if 'max_amount' in conditions and amount:
            if amount > conditions['max_amount']:
                return False

        return True

    @transaction.atomic
    def start_workflow(
        self,
        workflow: WorkflowDefinition,
        content_type: str,
        object_id: str,
        initiated_by=None,
        metadata: dict = None
    ) -> WorkflowInstance:
        """
        Démarre une instance de workflow.

        Args:
            workflow: Le workflow à démarrer
            content_type: Le type d'entité
            object_id: L'ID de l'entité
            initiated_by: L'utilisateur qui initie
            metadata: Métadonnées supplémentaires

        Returns:
            L'instance créée
        """
        first_step = workflow.steps.order_by('sequence').first()

        instance = WorkflowInstance.objects.create(
            company=self.company,
            workflow=workflow,
            content_type=content_type,
            object_id=object_id,
            status=WorkflowInstance.STATUS_IN_PROGRESS,
            current_step=first_step,
            started_at=timezone.now(),
            initiated_by=initiated_by,
            metadata=metadata or {}
        )

        WorkflowAction.objects.create(
            company=self.company,
            instance=instance,
            step=None,
            action=WorkflowAction.ACTION_SUBMIT,
            performed_by=initiated_by,
            comments="Workflow démarré"
        )

        if first_step:
            self._notify_approvers(instance, first_step)

        return instance

    @transaction.atomic
    def approve_step(
        self,
        instance: WorkflowInstance,
        user,
        comments: str = ''
    ) -> WorkflowInstance:
        """
        Approuve l'étape courante.

        Args:
            instance: L'instance de workflow
            user: L'utilisateur qui approuve
            comments: Commentaires

        Returns:
            L'instance mise à jour
        """
        if instance.is_completed:
            raise ValueError("Ce workflow est déjà terminé.")

        current_step = instance.current_step
        if not current_step:
            raise ValueError("Pas d'étape courante.")

        WorkflowAction.objects.create(
            company=self.company,
            instance=instance,
            step=current_step,
            action=WorkflowAction.ACTION_APPROVE,
            performed_by=user,
            comments=comments
        )

        next_step = instance.workflow.steps.filter(
            sequence__gt=current_step.sequence
        ).order_by('sequence').first()

        if next_step:
            instance.current_step = next_step
            instance.save(update_fields=['current_step'])
            self._notify_approvers(instance, next_step)
        else:
            instance.status = WorkflowInstance.STATUS_APPROVED
            instance.current_step = None
            instance.completed_at = timezone.now()
            instance.save(update_fields=['status', 'current_step', 'completed_at'])
            self._on_workflow_completed(instance, approved=True)

        return instance

    @transaction.atomic
    def reject_step(
        self,
        instance: WorkflowInstance,
        user,
        comments: str = ''
    ) -> WorkflowInstance:
        """
        Rejette le workflow.

        Args:
            instance: L'instance de workflow
            user: L'utilisateur qui rejette
            comments: Commentaires

        Returns:
            L'instance mise à jour
        """
        if instance.is_completed:
            raise ValueError("Ce workflow est déjà terminé.")

        current_step = instance.current_step

        WorkflowAction.objects.create(
            company=self.company,
            instance=instance,
            step=current_step,
            action=WorkflowAction.ACTION_REJECT,
            performed_by=user,
            comments=comments
        )

        instance.status = WorkflowInstance.STATUS_REJECTED
        instance.completed_at = timezone.now()
        instance.save(update_fields=['status', 'completed_at'])

        self._on_workflow_completed(instance, approved=False)

        return instance

    @transaction.atomic
    def delegate_step(
        self,
        instance: WorkflowInstance,
        user,
        delegate_to,
        comments: str = ''
    ) -> WorkflowInstance:
        """
        Délègue l'étape à un autre utilisateur.

        Args:
            instance: L'instance de workflow
            user: L'utilisateur qui délègue
            delegate_to: L'utilisateur délégué
            comments: Commentaires

        Returns:
            L'instance mise à jour
        """
        if instance.is_completed:
            raise ValueError("Ce workflow est déjà terminé.")

        WorkflowAction.objects.create(
            company=self.company,
            instance=instance,
            step=instance.current_step,
            action=WorkflowAction.ACTION_DELEGATE,
            performed_by=user,
            delegated_to=delegate_to,
            comments=comments
        )

        self._send_notification(
            instance,
            delegate_to,
            f"Une approbation vous a été déléguée par {user.get_full_name() or user.email}"
        )

        return instance

    def _notify_approvers(self, instance: WorkflowInstance, step: WorkflowStep):
        """Notifie les approbateurs de l'étape."""
        if step.approver:
            self._send_notification(
                instance,
                step.approver,
                f"Approbation requise: {step.name}"
            )

    def _send_notification(self, instance: WorkflowInstance, recipient, message: str):
        """Envoie une notification."""
        WorkflowNotification.objects.create(
            company=self.company,
            instance=instance,
            recipient=recipient,
            message=message
        )

    def _on_workflow_completed(self, instance: WorkflowInstance, approved: bool):
        """Callback quand un workflow est terminé."""
        if instance.initiated_by:
            status = "approuvé" if approved else "rejeté"
            self._send_notification(
                instance,
                instance.initiated_by,
                f"Votre demande a été {status}."
            )

    def get_pending_approvals(self, user) -> list:
        """
        Récupère les approbations en attente pour un utilisateur.

        Args:
            user: L'utilisateur

        Returns:
            Liste des instances en attente
        """
        return WorkflowInstance.objects.filter(
            company=self.company,
            status=WorkflowInstance.STATUS_IN_PROGRESS,
            current_step__approver=user
        ).select_related('workflow', 'current_step')

    def cancel_workflow(
        self,
        instance: WorkflowInstance,
        user,
        reason: str = ''
    ) -> WorkflowInstance:
        """
        Annule un workflow.

        Args:
            instance: L'instance à annuler
            user: L'utilisateur qui annule
            reason: Motif d'annulation

        Returns:
            L'instance annulée
        """
        if instance.is_completed:
            raise ValueError("Ce workflow est déjà terminé.")

        instance.status = WorkflowInstance.STATUS_CANCELLED
        instance.completed_at = timezone.now()
        instance.save(update_fields=['status', 'completed_at'])

        WorkflowAction.objects.create(
            company=self.company,
            instance=instance,
            step=instance.current_step,
            action=WorkflowAction.ACTION_REJECT,
            performed_by=user,
            comments=f"Annulé: {reason}"
        )

        return instance
