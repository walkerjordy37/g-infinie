"""
Treasury serializers.
"""
from rest_framework import serializers
from .models import (
    BankAccount, CashRegister,
    BankStatement, BankStatementLine, BankReconciliation,
    CashMovement, Transfer,
)


class BankAccountSerializer(serializers.ModelSerializer):
    """Serializer pour les comptes bancaires."""
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            'id', 'code', 'name', 'type', 'type_display',
            'bank_name', 'bank_code', 'branch_code', 'account_number', 'rib_key',
            'iban', 'bic', 'currency', 'currency_code',
            'initial_balance', 'current_balance',
            'last_statement_balance', 'last_statement_date',
            'accounting_code', 'is_active', 'is_default',
            'allow_overdraft', 'overdraft_limit', 'notes',
            'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'current_balance', 'last_statement_balance', 'last_statement_date',
            'created_at', 'updated_at',
        ]


class CashRegisterSerializer(serializers.ModelSerializer):
    """Serializer pour les caisses."""
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    responsible_name = serializers.CharField(
        source='responsible.get_full_name', read_only=True
    )

    class Meta:
        model = CashRegister
        fields = [
            'id', 'code', 'name', 'branch', 'branch_name',
            'currency', 'currency_code',
            'initial_balance', 'current_balance',
            'accounting_code', 'responsible', 'responsible_name',
            'is_active', 'max_balance', 'notes',
            'company', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'current_balance', 'created_at', 'updated_at']


class BankStatementLineSerializer(serializers.ModelSerializer):
    """Serializer pour les lignes de relevé bancaire."""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    partner_code = serializers.CharField(source='partner.code', read_only=True)

    class Meta:
        model = BankStatementLine
        fields = [
            'id', 'statement', 'sequence', 'date', 'value_date',
            'reference', 'description', 'partner_name',
            'type', 'type_display', 'amount',
            'is_reconciled', 'reconciled_at', 'reconciled_by',
            'partner', 'partner_code', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'is_reconciled', 'reconciled_at', 'reconciled_by',
            'created_at', 'updated_at',
        ]


class BankStatementSerializer(serializers.ModelSerializer):
    """Serializer pour les relevés bancaires."""
    bank_account_name = serializers.CharField(source='bank_account.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    line_count = serializers.IntegerField(read_only=True)
    reconciled_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = BankStatement
        fields = [
            'id', 'bank_account', 'bank_account_name',
            'reference', 'date', 'start_date', 'end_date',
            'opening_balance', 'closing_balance',
            'total_debits', 'total_credits',
            'status', 'status_display',
            'import_format', 'import_file', 'imported_at', 'imported_by',
            'line_count', 'reconciled_count', 'notes',
            'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_debits', 'total_credits',
            'imported_at', 'imported_by', 'line_count', 'reconciled_count',
            'created_at', 'updated_at',
        ]


class BankStatementWithLinesSerializer(BankStatementSerializer):
    """Serializer pour relevé bancaire avec lignes."""
    lines = BankStatementLineSerializer(many=True, read_only=True)

    class Meta(BankStatementSerializer.Meta):
        fields = BankStatementSerializer.Meta.fields + ['lines']


class BankReconciliationSerializer(serializers.ModelSerializer):
    """Serializer pour les rapprochements bancaires."""
    statement_line_description = serializers.CharField(
        source='statement_line.description', read_only=True
    )
    payment_number = serializers.CharField(source='payment.number', read_only=True)
    journal_entry_number = serializers.CharField(
        source='journal_entry.number', read_only=True
    )

    class Meta:
        model = BankReconciliation
        fields = [
            'id', 'statement_line', 'statement_line_description',
            'payment', 'payment_number',
            'journal_entry', 'journal_entry_number',
            'amount', 'reconciled_at', 'reconciled_by', 'notes',
            'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reconciled_at', 'reconciled_by', 'created_at', 'updated_at',
        ]


class CashMovementSerializer(serializers.ModelSerializer):
    """Serializer pour les mouvements de caisse."""
    cash_register_name = serializers.CharField(source='cash_register.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    partner_name = serializers.CharField(source='partner.name', read_only=True)
    performed_by_name = serializers.CharField(
        source='performed_by.get_full_name', read_only=True
    )

    class Meta:
        model = CashMovement
        fields = [
            'id', 'cash_register', 'cash_register_name',
            'number', 'date', 'type', 'type_display',
            'reason', 'reason_display',
            'amount', 'balance_before', 'balance_after',
            'description', 'reference',
            'partner', 'partner_name', 'payment',
            'performed_by', 'performed_by_name',
            'is_validated', 'validated_at', 'validated_by', 'notes',
            'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'number', 'balance_before', 'balance_after',
            'is_validated', 'validated_at', 'validated_by',
            'created_at', 'updated_at',
        ]


class TransferSerializer(serializers.ModelSerializer):
    """Serializer pour les virements."""
    from_bank_account_name = serializers.CharField(
        source='from_bank_account.name', read_only=True
    )
    from_cash_register_name = serializers.CharField(
        source='from_cash_register.name', read_only=True
    )
    to_bank_account_name = serializers.CharField(
        source='to_bank_account.name', read_only=True
    )
    to_cash_register_name = serializers.CharField(
        source='to_cash_register.name', read_only=True
    )
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_label = serializers.CharField(read_only=True)
    destination_label = serializers.CharField(read_only=True)

    class Meta:
        model = Transfer
        fields = [
            'id', 'number', 'date',
            'from_bank_account', 'from_bank_account_name',
            'from_cash_register', 'from_cash_register_name',
            'to_bank_account', 'to_bank_account_name',
            'to_cash_register', 'to_cash_register_name',
            'source_label', 'destination_label',
            'amount', 'fees', 'currency', 'currency_code', 'exchange_rate',
            'status', 'status_display',
            'description', 'reference',
            'executed_at', 'executed_by', 'journal_entry', 'notes',
            'company', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'number', 'executed_at', 'executed_by', 'journal_entry',
            'created_at', 'updated_at',
        ]


class ImportStatementSerializer(serializers.Serializer):
    """Serializer pour l'import de relevés bancaires."""
    bank_account_id = serializers.UUIDField()
    file = serializers.FileField()
    format = serializers.ChoiceField(choices=[
        ('ofx', 'OFX'),
        ('csv', 'CSV'),
        ('mt940', 'MT940'),
    ])
    date_format = serializers.CharField(required=False, default='%Y-%m-%d')
    delimiter = serializers.CharField(required=False, default=';')


class ReconcileSerializer(serializers.Serializer):
    """Serializer pour le rapprochement."""
    statement_line_id = serializers.UUIDField()
    payment_id = serializers.UUIDField(required=False)
    journal_entry_id = serializers.UUIDField(required=False)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class AutoReconcileSerializer(serializers.Serializer):
    """Serializer pour le rapprochement automatique."""
    statement_id = serializers.UUIDField()
    tolerance_days = serializers.IntegerField(default=3, min_value=0, max_value=30)
    tolerance_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )
