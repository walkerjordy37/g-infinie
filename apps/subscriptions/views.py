"""
Subscriptions views - Plans, Subscriptions, Payments, Webhooks.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import PlatformPlan, CompanySubscription, PaymentTransaction
from .serializers import (
    PlatformPlanSerializer,
    CompanySubscriptionSerializer,
    CompanySubscriptionCreateSerializer,
    PaymentTransactionSerializer,
    InitiatePaymentSerializer,
)
from .services import SubscriptionService


class PlatformPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Plans de la plateforme — endpoint public."""
    queryset = PlatformPlan.objects.filter(is_active=True)
    serializer_class = PlatformPlanSerializer

    def get_permissions(self):
        if self.action == 'list':
            return [AllowAny()]
        return [IsAuthenticated()]


class CompanySubscriptionViewSet(viewsets.GenericViewSet):
    """Gestion de l'abonnement de l'entreprise courante."""
    serializer_class = CompanySubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def _get_user_company(self):
        membership = self.request.user.memberships.filter(is_active=True).first()
        return membership.company if membership else None

    @action(detail=False, methods=['get'], url_path='my-subscription')
    def my_subscription(self, request):
        """Retourne l'abonnement de l'entreprise de l'utilisateur."""
        company = self._get_user_company()
        if not company:
            return Response(
                {'error': "Aucune entreprise associée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            subscription = company.subscription
        except CompanySubscription.DoesNotExist:
            return Response(
                {'error': "Aucun abonnement trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CompanySubscriptionSerializer(subscription)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """Crée un abonnement pour l'entreprise. Attend {plan_id, billing_cycle}."""
        company = self._get_user_company()
        if not company:
            return Response(
                {'error': "Aucune entreprise associée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if hasattr(company, 'subscription'):
            return Response(
                {'error': "L'entreprise a déjà un abonnement."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = CompanySubscriptionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        plan = ser.validated_data['plan']
        billing_cycle = ser.validated_data['billing_cycle']

        subscription = SubscriptionService.create_trial_subscription(
            company, plan_code=plan.code
        )
        subscription.billing_cycle = billing_cycle
        subscription.save(update_fields=['billing_cycle'])

        return Response(
            CompanySubscriptionSerializer(subscription).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'])
    def upgrade(self, request):
        """Change le plan de l'entreprise. Attend {plan_id, billing_cycle}."""
        company = self._get_user_company()
        if not company:
            return Response(
                {'error': "Aucune entreprise associée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            subscription = company.subscription
        except CompanySubscription.DoesNotExist:
            return Response(
                {'error': "Aucun abonnement trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        plan_id = request.data.get('plan_id')
        billing_cycle = request.data.get('billing_cycle', subscription.billing_cycle)

        try:
            new_plan = PlatformPlan.objects.get(id=plan_id, is_active=True)
        except PlatformPlan.DoesNotExist:
            return Response(
                {'error': "Plan introuvable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription.plan = new_plan
        subscription.billing_cycle = billing_cycle
        if billing_cycle == CompanySubscription.BILLING_YEARLY:
            subscription.amount = new_plan.yearly_price
        else:
            subscription.amount = new_plan.monthly_price
        subscription.save(update_fields=['plan', 'billing_cycle', 'amount'])

        return Response(CompanySubscriptionSerializer(subscription).data)

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """Annule l'abonnement de l'entreprise."""
        company = self._get_user_company()
        if not company:
            return Response(
                {'error': "Aucune entreprise associée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            subscription = company.subscription
        except CompanySubscription.DoesNotExist:
            return Response(
                {'error': "Aucun abonnement trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        reason = request.data.get('reason', '')
        SubscriptionService.cancel_subscription(subscription, reason)

        return Response(CompanySubscriptionSerializer(subscription).data)

    @action(detail=False, methods=['get'], url_path='check-limits')
    def check_limits(self, request):
        """Retourne les limites de l'abonnement."""
        company = self._get_user_company()
        if not company:
            return Response(
                {'error': "Aucune entreprise associée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        limits = SubscriptionService.check_subscription_limits(company)
        return Response(limits)


class PaymentViewSet(viewsets.GenericViewSet):
    """Paiements pour l'abonnement de l'entreprise courante."""
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]

    def _get_user_company(self):
        membership = self.request.user.memberships.filter(is_active=True).first()
        return membership.company if membership else None

    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """Initie un paiement. Attend {payment_method, phone_number}."""
        company = self._get_user_company()
        if not company:
            return Response(
                {'error': "Aucune entreprise associée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            subscription = company.subscription
        except CompanySubscription.DoesNotExist:
            return Response(
                {'error': "Aucun abonnement trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        ser = InitiatePaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        payment = SubscriptionService.initiate_payment(
            subscription=subscription,
            payment_method=ser.validated_data['payment_method'],
            phone_number=ser.validated_data['phone_number'],
        )

        return Response(
            PaymentTransactionSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Retourne l'historique des paiements de l'entreprise."""
        company = self._get_user_company()
        if not company:
            return Response(
                {'error': "Aucune entreprise associée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            subscription = company.subscription
        except CompanySubscription.DoesNotExist:
            return Response(
                {'error': "Aucun abonnement trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        transactions = subscription.transactions.all()
        serializer = PaymentTransactionSerializer(transactions, many=True)
        return Response(serializer.data)


class WebhookViewSet(viewsets.ViewSet):
    """Endpoints webhook pour les fournisseurs de paiement."""
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def wave(self, request):
        """Webhook Wave."""
        transaction_id = request.data.get('transaction_id')
        return self._process_webhook(transaction_id, request.data)

    @action(detail=False, methods=['post'])
    def orange_money(self, request):
        """Webhook Orange Money."""
        transaction_id = request.data.get('transaction_id')
        return self._process_webhook(transaction_id, request.data)

    @action(detail=False, methods=['post'])
    def mtn_money(self, request):
        """Webhook MTN Money."""
        transaction_id = request.data.get('transaction_id')
        return self._process_webhook(transaction_id, request.data)

    def _process_webhook(self, transaction_id, payload):
        """Traitement commun des webhooks."""
        if not transaction_id:
            return Response(
                {'error': "transaction_id manquant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = SubscriptionService.confirm_payment(transaction_id)
            return Response({
                'status': 'confirmed',
                'transaction_id': payment.transaction_id,
            })
        except PaymentTransaction.DoesNotExist:
            return Response(
                {'error': "Transaction introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
