"""
Accounting services - Business logic for accounting operations.
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Account, Journal, JournalEntry, JournalEntryLine, AccountBalance
)


class AccountingService:
    """Service pour la gestion comptable."""

    def __init__(self, company):
        self.company = company

    def generate_entry_number(self, journal: Journal) -> str:
        """Génère un numéro d'écriture pour un journal."""
        return journal.get_next_number()

    @transaction.atomic
    def post_entry(self, entry: JournalEntry, user=None) -> JournalEntry:
        """
        Valide une écriture comptable.

        Args:
            entry: L'écriture à valider
            user: L'utilisateur qui valide

        Returns:
            L'écriture validée
        """
        if entry.is_posted:
            raise ValueError("Cette écriture est déjà validée.")

        if not entry.is_balanced:
            raise ValueError(
                f"L'écriture n'est pas équilibrée. "
                f"Débit: {entry.total_debit}, Crédit: {entry.total_credit}"
            )

        if not entry.lines.exists():
            raise ValueError("L'écriture doit contenir au moins une ligne.")

        entry.status = JournalEntry.STATUS_POSTED
        entry.posted_by = user
        entry.posted_at = timezone.now()
        entry.save(update_fields=['status', 'posted_by', 'posted_at'])

        self._update_account_balances(entry)

        return entry

    @transaction.atomic
    def reverse_entry(
        self,
        entry: JournalEntry,
        reverse_date=None,
        description: str = None
    ) -> JournalEntry:
        """
        Crée une écriture d'extourne.

        Args:
            entry: L'écriture à extourner
            reverse_date: Date de l'extourne
            description: Description de l'extourne

        Returns:
            L'écriture d'extourne
        """
        if not entry.is_posted:
            raise ValueError("Seule une écriture validée peut être extournée.")

        reverse_date = reverse_date or timezone.now().date()
        description = description or f"Extourne de {entry.number}"

        reversal = JournalEntry.objects.create(
            company=self.company,
            number=self.generate_entry_number(entry.journal),
            journal=entry.journal,
            date=reverse_date,
            fiscal_year=entry.fiscal_year,
            fiscal_period=entry.fiscal_period,
            reference=f"EXT-{entry.number}",
            description=description,
            status=JournalEntry.STATUS_DRAFT,
            reversal_of=entry,
            is_reversal=True,
            total_debit=entry.total_credit,
            total_credit=entry.total_debit
        )

        for line in entry.lines.all():
            JournalEntryLine.objects.create(
                company=self.company,
                entry=reversal,
                account=line.account,
                sequence=line.sequence,
                label=f"Extourne: {line.label}",
                debit=line.credit,
                credit=line.debit,
                partner=line.partner,
                analytic_account=line.analytic_account,
                reference=line.reference
            )

        return reversal

    def _update_account_balances(self, entry: JournalEntry):
        """Met à jour les soldes des comptes après validation."""
        for line in entry.lines.all():
            balance, created = AccountBalance.objects.get_or_create(
                company=self.company,
                account=line.account,
                fiscal_period=entry.fiscal_period,
                defaults={
                    'opening_debit': Decimal('0'),
                    'opening_credit': Decimal('0'),
                    'period_debit': Decimal('0'),
                    'period_credit': Decimal('0'),
                    'closing_debit': Decimal('0'),
                    'closing_credit': Decimal('0'),
                }
            )

            balance.period_debit += line.debit
            balance.period_credit += line.credit
            balance.closing_debit = balance.opening_debit + balance.period_debit
            balance.closing_credit = balance.opening_credit + balance.period_credit
            balance.save()

    @transaction.atomic
    def create_entry_from_invoice(
        self,
        invoice,
        journal: Journal,
        accounts: dict
    ) -> JournalEntry:
        """
        Crée une écriture comptable à partir d'une facture.

        Args:
            invoice: La facture (vente ou achat)
            journal: Le journal à utiliser
            accounts: Dict avec les comptes (client, vente, tva, etc.)

        Returns:
            L'écriture créée
        """
        from apps.tenancy.models import FiscalPeriod

        period = FiscalPeriod.objects.filter(
            company=self.company,
            start_date__lte=invoice.date,
            end_date__gte=invoice.date
        ).first()

        if not period:
            raise ValueError(f"Pas de période fiscale pour la date {invoice.date}")

        entry = JournalEntry.objects.create(
            company=self.company,
            number=self.generate_entry_number(journal),
            journal=journal,
            date=invoice.date,
            fiscal_year=period.fiscal_year,
            fiscal_period=period,
            reference=invoice.number,
            description=f"Facture {invoice.number} - {invoice.supplier.name if hasattr(invoice, 'supplier') else invoice.partner.name}",
            status=JournalEntry.STATUS_DRAFT,
            total_debit=Decimal('0'),
            total_credit=Decimal('0')
        )

        lines_data = []
        
        if 'customer' in accounts:
            lines_data.append({
                'account': accounts['customer'],
                'label': f"Client - {invoice.partner.name}",
                'debit': invoice.total,
                'credit': Decimal('0'),
                'partner': invoice.partner
            })
        elif 'supplier' in accounts:
            lines_data.append({
                'account': accounts['supplier'],
                'label': f"Fournisseur - {invoice.supplier.name}",
                'debit': Decimal('0'),
                'credit': invoice.total,
                'partner': invoice.supplier
            })

        if 'revenue' in accounts:
            lines_data.append({
                'account': accounts['revenue'],
                'label': "Ventes",
                'debit': Decimal('0'),
                'credit': invoice.subtotal
            })
        elif 'expense' in accounts:
            lines_data.append({
                'account': accounts['expense'],
                'label': "Achats",
                'debit': invoice.subtotal,
                'credit': Decimal('0')
            })

        if invoice.tax_total > 0 and 'tax' in accounts:
            if 'customer' in accounts:
                lines_data.append({
                    'account': accounts['tax'],
                    'label': "TVA collectée",
                    'debit': Decimal('0'),
                    'credit': invoice.tax_total
                })
            else:
                lines_data.append({
                    'account': accounts['tax'],
                    'label': "TVA déductible",
                    'debit': invoice.tax_total,
                    'credit': Decimal('0')
                })

        total_debit = Decimal('0')
        total_credit = Decimal('0')

        for idx, line_data in enumerate(lines_data):
            JournalEntryLine.objects.create(
                company=self.company,
                entry=entry,
                sequence=idx,
                **line_data
            )
            total_debit += line_data['debit']
            total_credit += line_data['credit']

        entry.total_debit = total_debit
        entry.total_credit = total_credit
        entry.save(update_fields=['total_debit', 'total_credit'])

        return entry

    def get_trial_balance(self, fiscal_period) -> list:
        """
        Génère la balance des comptes pour une période.

        Returns:
            Liste des soldes par compte
        """
        balances = AccountBalance.objects.filter(
            company=self.company,
            fiscal_period=fiscal_period
        ).select_related('account').order_by('account__code')

        result = []
        for balance in balances:
            result.append({
                'account_code': balance.account.code,
                'account_name': balance.account.name,
                'opening_debit': balance.opening_debit,
                'opening_credit': balance.opening_credit,
                'period_debit': balance.period_debit,
                'period_credit': balance.period_credit,
                'closing_debit': balance.closing_debit,
                'closing_credit': balance.closing_credit,
                'balance': balance.balance
            })

        return result

    def get_general_ledger(self, account: Account, fiscal_period=None) -> dict:
        """
        Génère le grand livre pour un compte.

        Returns:
            Dict avec le détail des mouvements
        """
        queryset = JournalEntryLine.objects.filter(
            company=self.company,
            account=account,
            entry__status=JournalEntry.STATUS_POSTED
        ).select_related('entry', 'partner').order_by('entry__date', 'entry__number')

        if fiscal_period:
            queryset = queryset.filter(entry__fiscal_period=fiscal_period)

        movements = []
        running_balance = Decimal('0')

        for line in queryset:
            running_balance += (line.debit - line.credit)
            movements.append({
                'date': line.entry.date,
                'entry_number': line.entry.number,
                'journal': line.entry.journal.code,
                'label': line.label,
                'reference': line.reference,
                'partner': line.partner.name if line.partner else '',
                'debit': line.debit,
                'credit': line.credit,
                'balance': running_balance
            })

        return {
            'account_code': account.code,
            'account_name': account.name,
            'movements': movements,
            'total_debit': sum(m['debit'] for m in movements),
            'total_credit': sum(m['credit'] for m in movements),
            'final_balance': running_balance
        }

    @transaction.atomic
    def reconcile_lines(self, line_ids: list, reconciliation_number: str = None):
        """
        Lettre des lignes d'écriture.

        Args:
            line_ids: IDs des lignes à lettrer
            reconciliation_number: Numéro de lettrage (généré si non fourni)
        """
        lines = JournalEntryLine.objects.filter(
            company=self.company,
            id__in=line_ids,
            reconciled=False
        )

        if lines.count() < 2:
            raise ValueError("Au moins 2 lignes sont requises pour le lettrage.")

        total_debit = lines.aggregate(Sum('debit'))['debit__sum'] or Decimal('0')
        total_credit = lines.aggregate(Sum('credit'))['credit__sum'] or Decimal('0')

        if total_debit != total_credit:
            raise ValueError(
                f"Le lettrage n'est pas équilibré. "
                f"Débit: {total_debit}, Crédit: {total_credit}"
            )

        if not reconciliation_number:
            from django.utils.crypto import get_random_string
            reconciliation_number = get_random_string(8).upper()

        lines.update(reconciled=True, reconciliation_number=reconciliation_number)

        return reconciliation_number
