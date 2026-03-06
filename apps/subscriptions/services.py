"""
Subscriptions services - SubscriptionService for SaaS platform.
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import PlatformPlan, CompanySubscription, PaymentTransaction


class SubscriptionService:
    """Service pour la gestion des abonnements SaaS."""

    @staticmethod
    @transaction.atomic
    def create_trial_subscription(company, plan_code='standard'):
        """
        Crée un abonnement d'essai pour une nouvelle entreprise.

        Args:
            company: L'entreprise
            plan_code: Le code du plan (par défaut 'standard')

        Returns:
            CompanySubscription créé en mode trial
        """
        plan = PlatformPlan.objects.get(code=plan_code, is_active=True)
        today = timezone.now().date()
        trial_end = today + timedelta(days=plan.trial_days)

        subscription = CompanySubscription.objects.create(
            company=company,
            plan=plan,
            status=CompanySubscription.STATUS_TRIAL,
            billing_cycle=CompanySubscription.BILLING_MONTHLY,
            start_date=today,
            trial_end_date=trial_end,
            current_period_start=today,
            current_period_end=trial_end,
            amount=Decimal('0'),
        )
        return subscription

    @staticmethod
    @transaction.atomic
    def activate_subscription(subscription, billing_cycle):
        """
        Active un abonnement (après essai ou paiement).

        Args:
            subscription: L'abonnement à activer
            billing_cycle: 'monthly' ou 'yearly'

        Returns:
            L'abonnement activé
        """
        subscription.status = CompanySubscription.STATUS_ACTIVE
        subscription.billing_cycle = billing_cycle

        if billing_cycle == CompanySubscription.BILLING_YEARLY:
            subscription.amount = subscription.plan.yearly_price
        else:
            subscription.amount = subscription.plan.monthly_price

        today = timezone.now().date()
        subscription.current_period_start = today
        if billing_cycle == CompanySubscription.BILLING_YEARLY:
            subscription.current_period_end = today + timedelta(days=365)
        else:
            subscription.current_period_end = today + timedelta(days=30)

        subscription.save()
        return subscription

    @staticmethod
    @transaction.atomic
    def suspend_subscription(subscription, reason=''):
        """
        Suspend un abonnement.

        Args:
            subscription: L'abonnement à suspendre
            reason: Motif de suspension

        Returns:
            L'abonnement suspendu
        """
        subscription.status = CompanySubscription.STATUS_SUSPENDED
        subscription.cancellation_reason = reason
        subscription.save(update_fields=['status', 'cancellation_reason'])
        return subscription

    @staticmethod
    @transaction.atomic
    def cancel_subscription(subscription, reason=''):
        """
        Annule un abonnement.

        Args:
            subscription: L'abonnement à annuler
            reason: Motif d'annulation

        Returns:
            L'abonnement annulé
        """
        subscription.status = CompanySubscription.STATUS_CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.cancellation_reason = reason
        subscription.auto_renew = False
        subscription.save(update_fields=[
            'status', 'cancelled_at', 'cancellation_reason', 'auto_renew'
        ])
        return subscription

    @staticmethod
    @transaction.atomic
    def renew_subscription(subscription):
        """
        Renouvelle un abonnement pour une nouvelle période.

        Args:
            subscription: L'abonnement à renouveler

        Returns:
            L'abonnement renouvelé
        """
        if subscription.billing_cycle == CompanySubscription.BILLING_YEARLY:
            delta = timedelta(days=365)
        else:
            delta = timedelta(days=30)

        subscription.current_period_start = subscription.current_period_end
        subscription.current_period_end = subscription.current_period_end + delta
        subscription.status = CompanySubscription.STATUS_ACTIVE
        subscription.save(update_fields=[
            'current_period_start', 'current_period_end', 'status'
        ])
        return subscription

    @staticmethod
    def check_subscription_limits(company):
        """
        Vérifie les limites de l'abonnement d'une entreprise.

        Args:
            company: L'entreprise

        Returns:
            dict avec can_add_user, can_add_product, users_count, products_count,
            users_limit, products_limit
        """
        try:
            subscription = company.subscription
        except CompanySubscription.DoesNotExist:
            return {
                'can_add_user': False,
                'can_add_product': False,
                'users_count': 0,
                'products_count': 0,
                'users_limit': 0,
                'products_limit': 0,
            }

        users_count = company.memberships.filter(is_active=True).count()
        products_count = company.products.count() if hasattr(company, 'products') else 0

        users_limit = subscription.plan.max_users
        products_limit = subscription.plan.max_products

        can_add_user = users_limit == 0 or users_count < users_limit
        can_add_product = products_limit == 0 or products_count < products_limit

        return {
            'can_add_user': can_add_user,
            'can_add_product': can_add_product,
            'users_count': users_count,
            'products_count': products_count,
            'users_limit': users_limit,
            'products_limit': products_limit,
        }

    @staticmethod
    @transaction.atomic
    def initiate_payment(subscription, payment_method, phone_number=''):
        """
        Initie un paiement pour un abonnement.

        Args:
            subscription: L'abonnement concerné
            payment_method: Le moyen de paiement
            phone_number: Le numéro de téléphone (mobile money)

        Returns:
            PaymentTransaction créée avec statut pending
        """
        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

        payment = PaymentTransaction.objects.create(
            subscription=subscription,
            transaction_id=transaction_id,
            payment_method=payment_method,
            amount=subscription.amount,
            currency_code='XOF',
            status=PaymentTransaction.STATUS_PENDING,
            phone_number=phone_number,
        )
        return payment

    @staticmethod
    @transaction.atomic
    def confirm_payment(transaction_id):
        """
        Confirme un paiement et active/renouvelle l'abonnement.

        Args:
            transaction_id: L'identifiant de la transaction

        Returns:
            La transaction confirmée
        """
        payment = PaymentTransaction.objects.select_related(
            'subscription'
        ).get(transaction_id=transaction_id)

        payment.status = PaymentTransaction.STATUS_COMPLETED
        payment.paid_at = timezone.now()
        payment.save(update_fields=['status', 'paid_at'])

        subscription = payment.subscription

        if subscription.status in [
            CompanySubscription.STATUS_TRIAL,
            CompanySubscription.STATUS_EXPIRED,
            CompanySubscription.STATUS_SUSPENDED,
        ]:
            SubscriptionService.activate_subscription(
                subscription, subscription.billing_cycle
            )
        elif subscription.status == CompanySubscription.STATUS_ACTIVE:
            SubscriptionService.renew_subscription(subscription)

        return payment

    @staticmethod
    def check_expired_subscriptions():
        """
        Vérifie et marque comme expirés les abonnements dont la période est dépassée.

        Returns:
            Nombre d'abonnements expirés
        """
        today = timezone.now().date()

        expired_qs = CompanySubscription.objects.filter(
            status__in=[
                CompanySubscription.STATUS_TRIAL,
                CompanySubscription.STATUS_ACTIVE,
            ],
            current_period_end__lt=today,
        )

        count = expired_qs.update(status=CompanySubscription.STATUS_EXPIRED)
        return count
