"""
Treasury services - Business logic for treasury operations.
"""
import csv
import io
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone


class TreasuryService:
    """Service class for treasury operations."""

    @staticmethod
    def get_next_number(company, document_type: str) -> str:
        """Generate next document number."""
        from apps.tenancy.models import DocumentSequence

        sequence, _ = DocumentSequence.objects.get_or_create(
            company=company,
            document_type=document_type,
            defaults={
                'prefix': document_type.upper()[:3] + '-',
                'padding': 5,
            }
        )
        return sequence.get_next_number()

    @staticmethod
    @transaction.atomic
    def import_statement_ofx(
        bank_account,
        file_content: bytes,
        user=None
    ) -> 'BankStatement':
        """Import bank statement from OFX file."""
        from .models import BankStatement, BankStatementLine

        try:
            from ofxparse import OfxParser
        except ImportError:
            raise ImportError("ofxparse library not installed. Run: pip install ofxparse")

        ofx = OfxParser.parse(io.BytesIO(file_content))
        account = ofx.account

        statement = BankStatement.objects.create(
            company=bank_account.company,
            bank_account=bank_account,
            reference=f"OFX-{account.statement.start_date.strftime('%Y%m%d')}",
            date=account.statement.end_date,
            start_date=account.statement.start_date,
            end_date=account.statement.end_date,
            opening_balance=Decimal(str(account.statement.balance)) - sum(
                Decimal(str(t.amount)) for t in account.statement.transactions
            ),
            closing_balance=Decimal(str(account.statement.balance)),
            status=BankStatement.STATUS_IMPORTED,
            import_format='ofx',
            imported_at=timezone.now(),
            imported_by=user,
        )

        total_debits = Decimal('0')
        total_credits = Decimal('0')

        for seq, txn in enumerate(account.statement.transactions, 1):
            amount = Decimal(str(txn.amount))
            txn_type = BankStatementLine.TYPE_CREDIT if amount > 0 else BankStatementLine.TYPE_DEBIT

            if amount > 0:
                total_credits += amount
            else:
                total_debits += abs(amount)

            BankStatementLine.objects.create(
                company=bank_account.company,
                statement=statement,
                sequence=seq,
                date=txn.date,
                value_date=txn.date,
                reference=txn.id or '',
                description=txn.memo or txn.payee or '',
                partner_name=txn.payee or '',
                type=txn_type,
                amount=abs(amount),
            )

        statement.total_debits = total_debits
        statement.total_credits = total_credits
        statement.save(update_fields=['total_debits', 'total_credits'])

        return statement

    @staticmethod
    @transaction.atomic
    def import_statement_csv(
        bank_account,
        file_content: bytes,
        user=None,
        date_format: str = '%Y-%m-%d',
        delimiter: str = ';',
        column_mapping: Optional[Dict[str, int]] = None
    ) -> 'BankStatement':
        """Import bank statement from CSV file."""
        from .models import BankStatement, BankStatementLine

        default_mapping = {
            'date': 0,
            'description': 1,
            'debit': 2,
            'credit': 3,
            'reference': 4,
        }
        mapping = column_mapping or default_mapping

        content = file_content.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            raise ValueError("Le fichier CSV est vide")

        header = rows[0]
        data_rows = rows[1:]

        if not data_rows:
            raise ValueError("Le fichier CSV ne contient pas de données")

        dates = []
        for row in data_rows:
            if len(row) > mapping['date']:
                try:
                    d = datetime.strptime(row[mapping['date']].strip(), date_format).date()
                    dates.append(d)
                except ValueError:
                    continue

        if not dates:
            raise ValueError("Impossible de parser les dates du fichier")

        start_date = min(dates)
        end_date = max(dates)

        statement = BankStatement.objects.create(
            company=bank_account.company,
            bank_account=bank_account,
            reference=f"CSV-{start_date.strftime('%Y%m%d')}",
            date=end_date,
            start_date=start_date,
            end_date=end_date,
            opening_balance=Decimal('0'),
            closing_balance=Decimal('0'),
            status=BankStatement.STATUS_IMPORTED,
            import_format='csv',
            imported_at=timezone.now(),
            imported_by=user,
        )

        total_debits = Decimal('0')
        total_credits = Decimal('0')
        running_balance = Decimal('0')

        for seq, row in enumerate(data_rows, 1):
            if len(row) < max(mapping.values()) + 1:
                continue

            try:
                date = datetime.strptime(
                    row[mapping['date']].strip(), date_format
                ).date()
            except ValueError:
                continue

            description = row[mapping['description']].strip() if 'description' in mapping else ''
            reference = row[mapping.get('reference', 4)].strip() if len(row) > mapping.get('reference', 4) else ''

            debit_str = row[mapping.get('debit', 2)].strip().replace(',', '.').replace(' ', '')
            credit_str = row[mapping.get('credit', 3)].strip().replace(',', '.').replace(' ', '')

            debit = Decimal(debit_str) if debit_str else Decimal('0')
            credit = Decimal(credit_str) if credit_str else Decimal('0')

            if debit > 0:
                amount = debit
                txn_type = BankStatementLine.TYPE_DEBIT
                total_debits += amount
                running_balance -= amount
            elif credit > 0:
                amount = credit
                txn_type = BankStatementLine.TYPE_CREDIT
                total_credits += amount
                running_balance += amount
            else:
                continue

            BankStatementLine.objects.create(
                company=bank_account.company,
                statement=statement,
                sequence=seq,
                date=date,
                reference=reference,
                description=description,
                type=txn_type,
                amount=amount,
            )

        statement.total_debits = total_debits
        statement.total_credits = total_credits
        statement.closing_balance = statement.opening_balance + total_credits - total_debits
        statement.save(update_fields=['total_debits', 'total_credits', 'closing_balance'])

        return statement

    @staticmethod
    @transaction.atomic
    def auto_reconcile(
        statement: 'BankStatement',
        tolerance_days: int = 3,
        tolerance_amount: Decimal = Decimal('0'),
        user=None
    ) -> Tuple[int, int]:
        """Auto-reconcile statement lines with payments."""
        from .models import BankStatementLine, BankReconciliation

        reconciled = 0
        total_lines = 0

        unreconciled_lines = statement.lines.filter(is_reconciled=False)
        total_lines = unreconciled_lines.count()

        for line in unreconciled_lines:
            payment = TreasuryService._find_matching_payment(
                line, tolerance_days, tolerance_amount
            )

            if payment:
                BankReconciliation.objects.create(
                    company=statement.company,
                    statement_line=line,
                    payment=payment,
                    amount=line.amount,
                    reconciled_by=user,
                )

                line.is_reconciled = True
                line.reconciled_at = timezone.now()
                line.reconciled_by = user
                line.save(update_fields=['is_reconciled', 'reconciled_at', 'reconciled_by'])

                reconciled += 1

        if reconciled > 0 and statement.lines.filter(is_reconciled=False).count() == 0:
            statement.status = BankStatement.STATUS_RECONCILED
            statement.save(update_fields=['status'])

        return reconciled, total_lines

    @staticmethod
    def _find_matching_payment(
        line: 'BankStatementLine',
        tolerance_days: int,
        tolerance_amount: Decimal
    ) -> Optional[Any]:
        """Find matching payment for a statement line."""
        try:
            from apps.payments.models import Payment
        except ImportError:
            return None

        date_from = line.date - timedelta(days=tolerance_days)
        date_to = line.date + timedelta(days=tolerance_days)

        amount_min = line.amount - tolerance_amount
        amount_max = line.amount + tolerance_amount

        payments = Payment.objects.filter(
            company=line.company,
            date__gte=date_from,
            date__lte=date_to,
            amount__gte=amount_min,
            amount__lte=amount_max,
            bank_reconciliations__isnull=True,
        )

        if line.reference:
            ref_match = payments.filter(
                Q(reference__icontains=line.reference) |
                Q(number__icontains=line.reference)
            ).first()
            if ref_match:
                return ref_match

        if line.partner_name:
            partner_match = payments.filter(
                partner__name__icontains=line.partner_name
            ).first()
            if partner_match:
                return partner_match

        exact_match = payments.filter(amount=line.amount, date=line.date).first()
        if exact_match:
            return exact_match

        return payments.first()

    @staticmethod
    @transaction.atomic
    def reconcile_line(
        statement_line: 'BankStatementLine',
        payment=None,
        journal_entry=None,
        amount: Optional[Decimal] = None,
        user=None,
        notes: str = ''
    ) -> 'BankReconciliation':
        """Manually reconcile a statement line."""
        from .models import BankReconciliation

        if not payment and not journal_entry:
            raise ValueError("Un paiement ou une écriture comptable est requis")

        reconciliation = BankReconciliation.objects.create(
            company=statement_line.company,
            statement_line=statement_line,
            payment=payment,
            journal_entry=journal_entry,
            amount=amount or statement_line.amount,
            reconciled_by=user,
            notes=notes,
        )

        total_reconciled = statement_line.reconciliations.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        if total_reconciled >= statement_line.amount:
            statement_line.is_reconciled = True
            statement_line.reconciled_at = timezone.now()
            statement_line.reconciled_by = user
            statement_line.save(update_fields=['is_reconciled', 'reconciled_at', 'reconciled_by'])

        statement = statement_line.statement
        if statement.lines.filter(is_reconciled=False).count() == 0:
            statement.status = statement.STATUS_RECONCILED
            statement.save(update_fields=['status'])

        return reconciliation

    @staticmethod
    @transaction.atomic
    def create_cash_movement(
        cash_register: 'CashRegister',
        movement_type: str,
        amount: Decimal,
        reason: str,
        description: str,
        user=None,
        partner=None,
        payment=None,
        reference: str = '',
        notes: str = ''
    ) -> 'CashMovement':
        """Create a cash movement and update balance."""
        from .models import CashMovement

        balance_before = cash_register.current_balance

        if movement_type == CashMovement.TYPE_IN:
            balance_after = balance_before + amount
        else:
            balance_after = balance_before - amount
            if balance_after < 0:
                raise ValueError("Solde insuffisant en caisse")

        number = TreasuryService.get_next_number(
            cash_register.company, 'cash_movement'
        )

        movement = CashMovement.objects.create(
            company=cash_register.company,
            cash_register=cash_register,
            number=number,
            date=timezone.now().date(),
            type=movement_type,
            reason=reason,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            description=description,
            reference=reference,
            partner=partner,
            payment=payment,
            performed_by=user,
            notes=notes,
        )

        cash_register.current_balance = balance_after
        cash_register.save(update_fields=['current_balance'])

        return movement

    @staticmethod
    @transaction.atomic
    def execute_transfer(transfer: 'Transfer', user=None) -> 'Transfer':
        """Execute a transfer between accounts/registers."""
        from .models import Transfer, CashMovement

        if transfer.status != Transfer.STATUS_DRAFT:
            raise ValueError("Seul un brouillon peut être exécuté")

        if transfer.from_bank_account:
            transfer.from_bank_account.current_balance -= transfer.amount + transfer.fees
            transfer.from_bank_account.save(update_fields=['current_balance'])

        if transfer.from_cash_register:
            if transfer.from_cash_register.current_balance < transfer.amount:
                raise ValueError("Solde insuffisant en caisse source")

            TreasuryService.create_cash_movement(
                cash_register=transfer.from_cash_register,
                movement_type=CashMovement.TYPE_OUT,
                amount=transfer.amount,
                reason=CashMovement.REASON_TRANSFER,
                description=f"Virement {transfer.number}",
                user=user,
                reference=transfer.number,
            )

        if transfer.to_bank_account:
            transfer.to_bank_account.current_balance += transfer.amount
            transfer.to_bank_account.save(update_fields=['current_balance'])

        if transfer.to_cash_register:
            TreasuryService.create_cash_movement(
                cash_register=transfer.to_cash_register,
                movement_type=CashMovement.TYPE_IN,
                amount=transfer.amount,
                reason=CashMovement.REASON_TRANSFER,
                description=f"Virement {transfer.number}",
                user=user,
                reference=transfer.number,
            )

        transfer.status = Transfer.STATUS_COMPLETED
        transfer.executed_at = timezone.now()
        transfer.executed_by = user
        transfer.save(update_fields=['status', 'executed_at', 'executed_by'])

        return transfer

    @staticmethod
    @transaction.atomic
    def cancel_transfer(transfer: 'Transfer', user=None) -> 'Transfer':
        """Cancel a pending or completed transfer."""
        from .models import Transfer, CashMovement

        if transfer.status == Transfer.STATUS_CANCELLED:
            raise ValueError("Ce virement est déjà annulé")

        if transfer.status == Transfer.STATUS_COMPLETED:
            if transfer.from_bank_account:
                transfer.from_bank_account.current_balance += transfer.amount + transfer.fees
                transfer.from_bank_account.save(update_fields=['current_balance'])

            if transfer.to_bank_account:
                transfer.to_bank_account.current_balance -= transfer.amount
                transfer.to_bank_account.save(update_fields=['current_balance'])

            if transfer.from_cash_register:
                TreasuryService.create_cash_movement(
                    cash_register=transfer.from_cash_register,
                    movement_type=CashMovement.TYPE_IN,
                    amount=transfer.amount,
                    reason=CashMovement.REASON_ADJUSTMENT,
                    description=f"Annulation virement {transfer.number}",
                    user=user,
                    reference=transfer.number,
                )

            if transfer.to_cash_register:
                TreasuryService.create_cash_movement(
                    cash_register=transfer.to_cash_register,
                    movement_type=CashMovement.TYPE_OUT,
                    amount=transfer.amount,
                    reason=CashMovement.REASON_ADJUSTMENT,
                    description=f"Annulation virement {transfer.number}",
                    user=user,
                    reference=transfer.number,
                )

        transfer.status = Transfer.STATUS_CANCELLED
        transfer.save(update_fields=['status'])

        return transfer

    @staticmethod
    def get_bank_account_balance(bank_account, as_of_date=None) -> Decimal:
        """Get bank account balance as of a specific date."""
        from .models import BankStatement

        if as_of_date:
            statement = BankStatement.objects.filter(
                bank_account=bank_account,
                end_date__lte=as_of_date,
            ).order_by('-end_date').first()

            if statement:
                return statement.closing_balance

        return bank_account.current_balance

    @staticmethod
    def get_cash_register_balance(cash_register, as_of_date=None) -> Decimal:
        """Get cash register balance as of a specific date."""
        from .models import CashMovement

        if as_of_date:
            last_movement = CashMovement.objects.filter(
                cash_register=cash_register,
                date__lte=as_of_date,
                is_validated=True,
            ).order_by('-date', '-created_at').first()

            if last_movement:
                return last_movement.balance_after

            return cash_register.initial_balance

        return cash_register.current_balance

    @staticmethod
    def get_treasury_summary(company) -> Dict[str, Any]:
        """Get treasury summary for a company."""
        from .models import BankAccount, CashRegister

        bank_accounts = BankAccount.objects.filter(
            company=company, is_active=True
        ).values('id', 'name', 'current_balance', 'currency__code')

        cash_registers = CashRegister.objects.filter(
            company=company, is_active=True
        ).values('id', 'name', 'current_balance', 'currency__code')

        total_bank = BankAccount.objects.filter(
            company=company, is_active=True
        ).aggregate(total=Sum('current_balance'))['total'] or Decimal('0')

        total_cash = CashRegister.objects.filter(
            company=company, is_active=True
        ).aggregate(total=Sum('current_balance'))['total'] or Decimal('0')

        return {
            'bank_accounts': list(bank_accounts),
            'cash_registers': list(cash_registers),
            'total_bank_balance': total_bank,
            'total_cash_balance': total_cash,
            'total_treasury': total_bank + total_cash,
        }

    @staticmethod
    @transaction.atomic
    def validate_cash_movement(movement: 'CashMovement', user=None) -> 'CashMovement':
        """Validate a cash movement."""
        if movement.is_validated:
            raise ValueError("Ce mouvement est déjà validé")

        movement.is_validated = True
        movement.validated_at = timezone.now()
        movement.validated_by = user
        movement.save(update_fields=['is_validated', 'validated_at', 'validated_by'])

        return movement

    @staticmethod
    @transaction.atomic
    def close_statement(statement: 'BankStatement', user=None) -> 'BankStatement':
        """Close a bank statement and update account balance."""
        from .models import BankStatement

        if statement.status not in [BankStatement.STATUS_IMPORTED, BankStatement.STATUS_RECONCILED]:
            raise ValueError("Seul un relevé importé ou rapproché peut être clôturé")

        unreconciled = statement.lines.filter(is_reconciled=False).count()
        if unreconciled > 0:
            raise ValueError(f"{unreconciled} lignes non rapprochées")

        statement.bank_account.last_statement_balance = statement.closing_balance
        statement.bank_account.last_statement_date = statement.end_date
        statement.bank_account.save(update_fields=['last_statement_balance', 'last_statement_date'])

        statement.status = BankStatement.STATUS_CLOSED
        statement.save(update_fields=['status'])

        return statement
