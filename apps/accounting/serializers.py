"""
Accounting serializers.
"""
from decimal import Decimal
from rest_framework import serializers
from .models import (
    AccountType, Account, Journal,
    JournalEntry, JournalEntryLine, AccountBalance
)


class AccountTypeSerializer(serializers.ModelSerializer):
    class_display = serializers.CharField(source='get_account_class_display', read_only=True)
    nature_display = serializers.CharField(source='get_nature_display', read_only=True)

    class Meta:
        model = AccountType
        fields = [
            'id', 'code', 'name', 'account_class', 'class_display',
            'nature', 'nature_display', 'is_debit_balance'
        ]


class AccountSerializer(serializers.ModelSerializer):
    account_type_name = serializers.CharField(source='account_type.name', read_only=True)
    parent_code = serializers.CharField(source='parent.code', read_only=True)

    class Meta:
        model = Account
        fields = [
            'id', 'code', 'name', 'account_type', 'account_type_name',
            'parent', 'parent_code', 'is_active', 'is_reconcilable',
            'is_detail', 'currency', 'notes'
        ]


class AccountListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'code', 'name', 'is_active']


class JournalSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_journal_type_display', read_only=True)

    class Meta:
        model = Journal
        fields = [
            'id', 'code', 'name', 'journal_type', 'type_display',
            'default_debit_account', 'default_credit_account',
            'is_active', 'sequence_prefix', 'next_sequence'
        ]
        read_only_fields = ['next_sequence']


class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    partner_name = serializers.CharField(source='partner.name', read_only=True)

    class Meta:
        model = JournalEntryLine
        fields = [
            'id', 'account', 'account_code', 'account_name', 'sequence',
            'label', 'debit', 'credit',
            'partner', 'partner_name', 'analytic_account', 'reference',
            'reconciled', 'reconciliation_number'
        ]
        read_only_fields = ['id', 'reconciled', 'reconciliation_number']

    def validate(self, attrs):
        debit = attrs.get('debit', Decimal('0'))
        credit = attrs.get('credit', Decimal('0'))
        if debit > 0 and credit > 0:
            raise serializers.ValidationError(
                "Une ligne ne peut pas avoir à la fois un débit et un crédit."
            )
        if debit == 0 and credit == 0:
            raise serializers.ValidationError(
                "Une ligne doit avoir un débit ou un crédit."
            )
        return attrs


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalEntryLineSerializer(many=True, required=True)
    journal_code = serializers.CharField(source='journal.code', read_only=True)
    journal_name = serializers.CharField(source='journal.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    posted_by_name = serializers.SerializerMethodField()
    is_balanced = serializers.BooleanField(read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            'id', 'number', 'journal', 'journal_code', 'journal_name',
            'date', 'fiscal_year', 'fiscal_period',
            'reference', 'description', 'status', 'status_display',
            'total_debit', 'total_credit', 'is_balanced',
            'reversal_of', 'is_reversal',
            'posted_by', 'posted_by_name', 'posted_at',
            'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'number', 'total_debit', 'total_credit',
            'posted_by', 'posted_at', 'created_at', 'updated_at'
        ]

    def get_posted_by_name(self, obj):
        if obj.posted_by:
            return obj.posted_by.get_full_name() or obj.posted_by.email
        return None

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])

        if not lines_data:
            raise serializers.ValidationError(
                {'lines': "Au moins une ligne est requise."}
            )

        entry = JournalEntry.objects.create(**validated_data)

        total_debit = Decimal('0')
        total_credit = Decimal('0')

        for line_data in lines_data:
            line_data['company'] = entry.company
            JournalEntryLine.objects.create(entry=entry, **line_data)
            total_debit += line_data.get('debit', Decimal('0'))
            total_credit += line_data.get('credit', Decimal('0'))

        entry.total_debit = total_debit
        entry.total_credit = total_credit
        entry.save(update_fields=['total_debit', 'total_credit'])

        return entry

    def update(self, instance, validated_data):
        if instance.is_posted:
            raise serializers.ValidationError(
                "Impossible de modifier une écriture validée."
            )

        lines_data = validated_data.pop('lines', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()

            total_debit = Decimal('0')
            total_credit = Decimal('0')

            for line_data in lines_data:
                line_data['company'] = instance.company
                JournalEntryLine.objects.create(entry=instance, **line_data)
                total_debit += line_data.get('debit', Decimal('0'))
                total_credit += line_data.get('credit', Decimal('0'))

            instance.total_debit = total_debit
            instance.total_credit = total_credit
            instance.save(update_fields=['total_debit', 'total_credit'])

        return instance


class JournalEntryListSerializer(serializers.ModelSerializer):
    journal_code = serializers.CharField(source='journal.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_balanced = serializers.BooleanField(read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            'id', 'number', 'journal_code', 'date', 'description',
            'status', 'status_display', 'total_debit', 'total_credit', 'is_balanced'
        ]


class AccountBalanceSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = AccountBalance
        fields = [
            'id', 'account', 'account_code', 'account_name', 'fiscal_period',
            'opening_debit', 'opening_credit',
            'period_debit', 'period_credit',
            'closing_debit', 'closing_credit', 'balance'
        ]
