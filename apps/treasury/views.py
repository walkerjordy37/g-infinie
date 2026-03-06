"""
Treasury views - ViewSets for bank accounts, cash registers, statements.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction

from apps.core.viewsets import CompanyScopedMixin
from .models import (
    BankAccount, CashRegister,
    BankStatement, BankStatementLine, BankReconciliation,
    CashMovement, Transfer,
)
from .serializers import (
    BankAccountSerializer, CashRegisterSerializer,
    BankStatementSerializer, BankStatementWithLinesSerializer,
    BankStatementLineSerializer, BankReconciliationSerializer,
    CashMovementSerializer, TransferSerializer,
    ImportStatementSerializer, ReconcileSerializer, AutoReconcileSerializer,
)
from .services import TreasuryService


class BankAccountViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les comptes bancaires."""
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('currency')

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company, current_balance=serializer.validated_data.get('initial_balance', 0))

    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get current balance."""
        account = self.get_object()
        as_of_date = request.query_params.get('as_of_date')
        balance = TreasuryService.get_bank_account_balance(account, as_of_date)
        return Response({
            'account': account.name,
            'balance': balance,
            'currency': account.currency.code,
        })

    @action(detail=True, methods=['get'])
    def statements(self, request, pk=None):
        """List statements for this account."""
        account = self.get_object()
        statements = account.statements.all()[:20]
        return Response(BankStatementSerializer(statements, many=True).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary of all bank accounts."""
        company = self._get_company()
        if not company:
            return Response({'error': 'Company required'}, status=400)
        summary = TreasuryService.get_treasury_summary(company)
        return Response(summary)


class CashRegisterViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les caisses."""
    queryset = CashRegister.objects.all()
    serializer_class = CashRegisterSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('currency', 'branch', 'responsible')

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company, current_balance=serializer.validated_data.get('initial_balance', 0))

    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get current balance."""
        register = self.get_object()
        as_of_date = request.query_params.get('as_of_date')
        balance = TreasuryService.get_cash_register_balance(register, as_of_date)
        return Response({
            'register': register.name,
            'balance': balance,
            'currency': register.currency.code,
        })

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """List movements for this register."""
        register = self.get_object()
        movements = register.movements.all()[:50]
        return Response(CashMovementSerializer(movements, many=True).data)


class BankStatementViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les relevés bancaires."""
    queryset = BankStatement.objects.all()
    serializer_class = BankStatementSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('bank_account', 'imported_by')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BankStatementWithLinesSerializer
        return BankStatementSerializer

    def perform_create(self, serializer):
        company = self._get_company()
        serializer.save(company=company)

    @action(detail=False, methods=['post'])
    def import_statement(self, request):
        """Import bank statement from file."""
        serializer = ImportStatementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bank_account_id = serializer.validated_data['bank_account_id']
        file = serializer.validated_data['file']
        format_type = serializer.validated_data['format']

        try:
            bank_account = BankAccount.objects.get(
                id=bank_account_id,
                company=self._get_company()
            )
        except BankAccount.DoesNotExist:
            return Response(
                {'error': 'Compte bancaire non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            file_content = file.read()

            if format_type == 'ofx':
                statement = TreasuryService.import_statement_ofx(
                    bank_account, file_content, user=request.user
                )
            elif format_type == 'csv':
                statement = TreasuryService.import_statement_csv(
                    bank_account, file_content, user=request.user,
                    date_format=serializer.validated_data.get('date_format', '%Y-%m-%d'),
                    delimiter=serializer.validated_data.get('delimiter', ';'),
                )
            else:
                return Response(
                    {'error': f'Format non supporté: {format_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            statement.import_file = file
            statement.save(update_fields=['import_file'])

            return Response(
                BankStatementWithLinesSerializer(statement).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def auto_reconcile(self, request, pk=None):
        """Auto-reconcile statement lines."""
        statement = self.get_object()

        serializer = AutoReconcileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tolerance_days = serializer.validated_data.get('tolerance_days', 3)
        tolerance_amount = serializer.validated_data.get('tolerance_amount', 0)

        try:
            reconciled, total = TreasuryService.auto_reconcile(
                statement,
                tolerance_days=tolerance_days,
                tolerance_amount=tolerance_amount,
                user=request.user
            )
            return Response({
                'reconciled': reconciled,
                'total': total,
                'message': f'{reconciled}/{total} lignes rapprochées automatiquement'
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close the statement."""
        statement = self.get_object()
        try:
            statement = TreasuryService.close_statement(statement, user=request.user)
            return Response(BankStatementSerializer(statement).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BankStatementLineViewSet(viewsets.ModelViewSet):
    """ViewSet pour les lignes de relevé."""
    queryset = BankStatementLine.objects.all()
    serializer_class = BankStatementLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        statement_id = self.kwargs.get('statement_pk')
        if statement_id:
            queryset = queryset.filter(statement_id=statement_id)
        return queryset.select_related('partner')

    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None, **kwargs):
        """Manually reconcile a line."""
        line = self.get_object()

        serializer = ReconcileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = None
        journal_entry = None

        if serializer.validated_data.get('payment_id'):
            try:
                from apps.payments.models import Payment
                payment = Payment.objects.get(id=serializer.validated_data['payment_id'])
            except:
                return Response(
                    {'error': 'Paiement non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )

        if serializer.validated_data.get('journal_entry_id'):
            try:
                from apps.accounting.models import JournalEntry
                journal_entry = JournalEntry.objects.get(
                    id=serializer.validated_data['journal_entry_id']
                )
            except:
                return Response(
                    {'error': 'Écriture comptable non trouvée'},
                    status=status.HTTP_404_NOT_FOUND
                )

        try:
            reconciliation = TreasuryService.reconcile_line(
                line,
                payment=payment,
                journal_entry=journal_entry,
                amount=serializer.validated_data.get('amount'),
                user=request.user,
                notes=serializer.validated_data.get('notes', '')
            )
            return Response(BankReconciliationSerializer(reconciliation).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def unreconcile(self, request, pk=None, **kwargs):
        """Remove reconciliation from a line."""
        line = self.get_object()

        with transaction.atomic():
            line.reconciliations.all().delete()
            line.is_reconciled = False
            line.reconciled_at = None
            line.reconciled_by = None
            line.save(update_fields=['is_reconciled', 'reconciled_at', 'reconciled_by'])

        return Response(BankStatementLineSerializer(line).data)


class BankReconciliationViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les rapprochements."""
    queryset = BankReconciliation.objects.all()
    serializer_class = BankReconciliationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('statement_line', 'payment', 'journal_entry')


class CashMovementViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les mouvements de caisse."""
    queryset = CashMovement.objects.all()
    serializer_class = CashMovementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related('cash_register', 'partner', 'performed_by')

    def perform_create(self, serializer):
        company = self._get_company()
        cash_register = serializer.validated_data['cash_register']
        movement_type = serializer.validated_data['type']
        amount = serializer.validated_data['amount']
        reason = serializer.validated_data.get('reason', CashMovement.REASON_OTHER)
        description = serializer.validated_data.get('description', '')

        movement = TreasuryService.create_cash_movement(
            cash_register=cash_register,
            movement_type=movement_type,
            amount=amount,
            reason=reason,
            description=description,
            user=self.request.user,
            partner=serializer.validated_data.get('partner'),
            reference=serializer.validated_data.get('reference', ''),
            notes=serializer.validated_data.get('notes', ''),
        )

        serializer.instance = movement

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Validate a cash movement."""
        movement = self.get_object()
        try:
            movement = TreasuryService.validate_cash_movement(movement, user=request.user)
            return Response(CashMovementSerializer(movement).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TransferViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """ViewSet pour les virements."""
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._get_company()
        if company:
            queryset = queryset.filter(company=company)
        return queryset.select_related(
            'from_bank_account', 'from_cash_register',
            'to_bank_account', 'to_cash_register',
            'currency', 'executed_by'
        )

    def perform_create(self, serializer):
        company = self._get_company()
        number = TreasuryService.get_next_number(company, 'transfer')
        serializer.save(company=company, number=number)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute the transfer."""
        transfer = self.get_object()
        try:
            transfer = TreasuryService.execute_transfer(transfer, user=request.user)
            return Response(TransferSerializer(transfer).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel the transfer."""
        transfer = self.get_object()
        try:
            transfer = TreasuryService.cancel_transfer(transfer, user=request.user)
            return Response(TransferSerializer(transfer).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
