"""
Tax services - Business logic for tax calculations and declarations.
"""
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone

from .models import (
    TaxType, TaxRate, TaxGroup, TaxRule,
    WithholdingTax, TaxDeclaration, TaxDeclarationLine
)


class TaxService:
    """Service pour la gestion des taxes."""

    def __init__(self, company):
        self.company = company

    # =========================================================================
    # TAX CALCULATION
    # =========================================================================

    def calculate_tax(
        self,
        amount: Decimal,
        tax_rate: TaxRate = None,
        tax_group: TaxGroup = None,
        date=None
    ) -> dict:
        """
        Calcule la taxe pour un montant donné.

        Args:
            amount: Montant HT
            tax_rate: Taux de taxe spécifique (optionnel)
            tax_group: Groupe de taxes (optionnel)
            date: Date pour la validité des taux

        Returns:
            Dictionnaire avec les détails du calcul
        """
        if date is None:
            date = timezone.now().date()

        result = {
            'base_amount': amount,
            'tax_details': [],
            'total_tax': Decimal('0'),
            'total_amount': amount
        }

        if tax_rate:
            if tax_rate.is_valid_at(date):
                tax_amount = amount * (tax_rate.rate / Decimal('100'))
                result['tax_details'].append({
                    'tax_rate_id': str(tax_rate.id),
                    'tax_rate_name': tax_rate.name,
                    'rate': float(tax_rate.rate),
                    'base_amount': float(amount),
                    'tax_amount': float(tax_amount)
                })
                result['total_tax'] = tax_amount
        elif tax_group:
            applicable_rates = tax_group.get_applicable_rates(date)
            for rate in applicable_rates:
                tax_amount = amount * (rate.rate / Decimal('100'))
                result['tax_details'].append({
                    'tax_rate_id': str(rate.id),
                    'tax_rate_name': rate.name,
                    'rate': float(rate.rate),
                    'base_amount': float(amount),
                    'tax_amount': float(tax_amount)
                })
                result['total_tax'] += tax_amount

        result['total_amount'] = amount + result['total_tax']
        return result

    def get_applicable_tax_rule(
        self,
        transaction_type: str,
        partner_type: str,
        country=None,
        product_category=None,
        date=None
    ) -> TaxRule:
        """
        Trouve la règle de taxe applicable.

        Args:
            transaction_type: Type de transaction (sale, purchase, etc.)
            partner_type: Type de partenaire (domestic, eu, international)
            country: Pays (optionnel)
            product_category: Catégorie de produit (optionnel)
            date: Date d'application

        Returns:
            La règle de taxe la plus prioritaire
        """
        if date is None:
            date = timezone.now().date()

        rules = TaxRule.objects.filter(
            company=self.company,
            transaction_type=transaction_type,
            partner_type=partner_type,
            is_active=True,
            valid_from__lte=date
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=date)
        )

        if country:
            rules = rules.filter(
                models.Q(country=country) | models.Q(country__isnull=True)
            )
        if product_category:
            rules = rules.filter(
                models.Q(product_category=product_category) |
                models.Q(product_category__isnull=True)
            )

        return rules.order_by('-priority').first()

    def calculate_tax_with_rules(
        self,
        amount: Decimal,
        transaction_type: str,
        partner_type: str,
        country=None,
        product_category=None,
        date=None
    ) -> dict:
        """
        Calcule la taxe en utilisant les règles définies.

        Args:
            amount: Montant HT
            transaction_type: Type de transaction
            partner_type: Type de partenaire
            country: Pays (optionnel)
            product_category: Catégorie de produit (optionnel)
            date: Date d'application

        Returns:
            Dictionnaire avec les détails du calcul
        """
        rule = self.get_applicable_tax_rule(
            transaction_type=transaction_type,
            partner_type=partner_type,
            country=country,
            product_category=product_category,
            date=date
        )

        if not rule:
            return {
                'base_amount': amount,
                'tax_details': [],
                'total_tax': Decimal('0'),
                'total_amount': amount,
                'rule_applied': None
            }

        result = self.calculate_tax(
            amount=amount,
            tax_group=rule.tax_group,
            date=date
        )
        result['rule_applied'] = {
            'id': str(rule.id),
            'code': rule.code,
            'name': rule.name
        }
        return result

    # =========================================================================
    # WITHHOLDING TAX CALCULATION
    # =========================================================================

    def calculate_withholding(
        self,
        amount: Decimal,
        withholding_tax: WithholdingTax,
        is_resident: bool = True
    ) -> dict:
        """
        Calcule la retenue à la source.

        Args:
            amount: Montant brut
            withholding_tax: Configuration de retenue
            is_resident: Le bénéficiaire est-il résident

        Returns:
            Dictionnaire avec les détails du calcul
        """
        if is_resident and not withholding_tax.applies_to_residents:
            return {
                'gross_amount': amount,
                'withholding_rate': Decimal('0'),
                'withholding_amount': Decimal('0'),
                'net_amount': amount
            }

        if not is_resident and not withholding_tax.applies_to_non_residents:
            return {
                'gross_amount': amount,
                'withholding_rate': Decimal('0'),
                'withholding_amount': Decimal('0'),
                'net_amount': amount
            }

        withholding_amount = withholding_tax.calculate_withholding(amount)

        return {
            'gross_amount': amount,
            'withholding_rate': withholding_tax.rate,
            'withholding_amount': withholding_amount,
            'net_amount': amount - withholding_amount
        }

    # =========================================================================
    # TAX DECLARATION
    # =========================================================================

    def generate_declaration_number(self) -> str:
        """Génère un numéro unique pour une déclaration fiscale."""
        from apps.tenancy.models import DocumentSequence
        try:
            sequence = DocumentSequence.objects.get(
                company=self.company,
                document_type='tax_declaration'
            )
            return sequence.get_next_number()
        except DocumentSequence.DoesNotExist:
            year = timezone.now().year
            count = TaxDeclaration.objects.filter(
                company=self.company,
                period_start__year=year
            ).count() + 1
            return f"DECL-{year}-{count:05d}"

    @transaction.atomic
    def create_declaration(
        self,
        tax_type: TaxType,
        period_type: str,
        period_start,
        period_end,
        due_date,
        credit_carried_forward: Decimal = Decimal('0')
    ) -> TaxDeclaration:
        """
        Crée une nouvelle déclaration fiscale.

        Args:
            tax_type: Type de taxe
            period_type: Type de période (monthly, quarterly, yearly)
            period_start: Début de période
            period_end: Fin de période
            due_date: Date limite de dépôt
            credit_carried_forward: Crédit reporté de la période précédente

        Returns:
            La déclaration créée
        """
        declaration = TaxDeclaration.objects.create(
            company=self.company,
            number=self.generate_declaration_number(),
            tax_type=tax_type,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            status=TaxDeclaration.STATUS_DRAFT,
            credit_carried_forward=credit_carried_forward
        )
        return declaration

    @transaction.atomic
    def generate_declaration(
        self,
        declaration: TaxDeclaration,
        calculated_by=None
    ) -> TaxDeclaration:
        """
        Génère les lignes de déclaration à partir des factures.

        Args:
            declaration: La déclaration à remplir
            calculated_by: L'utilisateur qui calcule

        Returns:
            La déclaration mise à jour
        """
        if not declaration.is_draft:
            raise ValueError("La déclaration doit être en brouillon.")

        declaration.lines.all().delete()

        sequence = 0

        if declaration.tax_type.tax_type == TaxType.TYPE_VAT:
            sequence = self._generate_vat_lines(declaration, sequence)

        declaration.calculate_totals()
        declaration.status = TaxDeclaration.STATUS_CALCULATED
        declaration.calculated_at = timezone.now()
        declaration.calculated_by = calculated_by
        declaration.save()

        return declaration

    def _generate_vat_lines(self, declaration: TaxDeclaration, sequence: int) -> int:
        """Génère les lignes de TVA collectée et déductible."""
        from apps.sales.models import Invoice, InvoiceLine
        from apps.purchasing.models import SupplierInvoice, SupplierInvoiceLine

        tax_rates = TaxRate.objects.filter(
            company=self.company,
            tax_type=declaration.tax_type,
            is_active=True
        )

        for tax_rate in tax_rates:
            collected_lines = InvoiceLine.objects.filter(
                company=self.company,
                invoice__status__in=['validated', 'paid'],
                invoice__date__gte=declaration.period_start,
                invoice__date__lte=declaration.period_end,
                tax_rate=tax_rate.rate
            )

            base_collected = sum(line.subtotal for line in collected_lines)
            tax_collected = sum(line.tax_amount for line in collected_lines)
            invoice_ids = list(
                collected_lines.values_list('invoice_id', flat=True).distinct()
            )

            if tax_collected > 0:
                sequence += 1
                line = TaxDeclarationLine.objects.create(
                    company=self.company,
                    declaration=declaration,
                    tax_rate=tax_rate,
                    line_type=TaxDeclarationLine.LINE_TYPE_COLLECTED,
                    sequence=sequence,
                    base_amount=base_collected,
                    tax_amount=tax_collected,
                    invoice_count=len(invoice_ids)
                )
                if invoice_ids:
                    from apps.sales.models import Invoice
                    invoices = Invoice.objects.filter(id__in=invoice_ids)
                    line.source_invoices.set(invoices)

            deductible_lines = SupplierInvoiceLine.objects.filter(
                company=self.company,
                invoice__status__in=['validated', 'paid'],
                invoice__date__gte=declaration.period_start,
                invoice__date__lte=declaration.period_end,
                tax_rate=tax_rate.rate
            )

            base_deductible = sum(line.subtotal for line in deductible_lines)
            tax_deductible = sum(line.tax_amount for line in deductible_lines)
            supplier_invoice_ids = list(
                deductible_lines.values_list('invoice_id', flat=True).distinct()
            )

            if tax_deductible > 0:
                sequence += 1
                line = TaxDeclarationLine.objects.create(
                    company=self.company,
                    declaration=declaration,
                    tax_rate=tax_rate,
                    line_type=TaxDeclarationLine.LINE_TYPE_DEDUCTIBLE,
                    sequence=sequence,
                    base_amount=base_deductible,
                    tax_amount=tax_deductible,
                    invoice_count=len(supplier_invoice_ids)
                )
                if supplier_invoice_ids:
                    supplier_invoices = SupplierInvoice.objects.filter(
                        id__in=supplier_invoice_ids
                    )
                    line.source_supplier_invoices.set(supplier_invoices)

        return sequence

    @transaction.atomic
    def validate_declaration(
        self,
        declaration: TaxDeclaration,
        validated_by=None
    ) -> TaxDeclaration:
        """
        Valide une déclaration fiscale.

        Args:
            declaration: La déclaration à valider
            validated_by: L'utilisateur qui valide

        Returns:
            La déclaration validée
        """
        if not declaration.is_calculated:
            raise ValueError("La déclaration doit être calculée avant validation.")

        declaration.status = TaxDeclaration.STATUS_VALIDATED
        declaration.validated_at = timezone.now()
        declaration.validated_by = validated_by
        declaration.save(update_fields=['status', 'validated_at', 'validated_by'])

        return declaration

    @transaction.atomic
    def submit_declaration(
        self,
        declaration: TaxDeclaration,
        submission_reference: str = ''
    ) -> TaxDeclaration:
        """
        Marque une déclaration comme soumise.

        Args:
            declaration: La déclaration à soumettre
            submission_reference: Référence de soumission

        Returns:
            La déclaration soumise
        """
        if not declaration.is_validated:
            raise ValueError("La déclaration doit être validée avant soumission.")

        declaration.status = TaxDeclaration.STATUS_SUBMITTED
        declaration.submitted_at = timezone.now()
        declaration.submission_reference = submission_reference
        declaration.save(update_fields=[
            'status', 'submitted_at', 'submission_reference'
        ])

        return declaration

    @transaction.atomic
    def register_payment(
        self,
        declaration: TaxDeclaration,
        payment_date,
        payment_amount: Decimal,
        payment_reference: str = ''
    ) -> TaxDeclaration:
        """
        Enregistre le paiement d'une déclaration.

        Args:
            declaration: La déclaration payée
            payment_date: Date du paiement
            payment_amount: Montant payé
            payment_reference: Référence de paiement

        Returns:
            La déclaration mise à jour
        """
        if declaration.status not in [
            TaxDeclaration.STATUS_VALIDATED,
            TaxDeclaration.STATUS_SUBMITTED
        ]:
            raise ValueError(
                "La déclaration doit être validée ou soumise pour enregistrer un paiement."
            )

        declaration.status = TaxDeclaration.STATUS_PAID
        declaration.payment_date = payment_date
        declaration.payment_amount = payment_amount
        declaration.payment_reference = payment_reference
        declaration.save(update_fields=[
            'status', 'payment_date', 'payment_amount', 'payment_reference'
        ])

        return declaration

    # =========================================================================
    # REPORTS
    # =========================================================================

    def get_tax_summary(
        self,
        period_start,
        period_end,
        tax_type: TaxType = None
    ) -> dict:
        """
        Génère un résumé des taxes pour une période.

        Args:
            period_start: Début de période
            period_end: Fin de période
            tax_type: Type de taxe (optionnel)

        Returns:
            Dictionnaire avec le résumé
        """
        from apps.sales.models import InvoiceLine
        from apps.purchasing.models import SupplierInvoiceLine

        sales_lines = InvoiceLine.objects.filter(
            company=self.company,
            invoice__status__in=['validated', 'paid'],
            invoice__date__gte=period_start,
            invoice__date__lte=period_end
        )

        purchase_lines = SupplierInvoiceLine.objects.filter(
            company=self.company,
            invoice__status__in=['validated', 'paid'],
            invoice__date__gte=period_start,
            invoice__date__lte=period_end
        )

        collected = sum(line.tax_amount for line in sales_lines)
        deductible = sum(line.tax_amount for line in purchase_lines)
        net = collected - deductible

        return {
            'period_start': str(period_start),
            'period_end': str(period_end),
            'tax_collected': float(collected),
            'tax_deductible': float(deductible),
            'net_tax': float(net),
            'tax_to_pay': float(max(net, Decimal('0'))),
            'tax_credit': float(abs(min(net, Decimal('0'))))
        }

    def get_pending_declarations(self) -> list:
        """Retourne les déclarations en attente de soumission ou paiement."""
        return TaxDeclaration.objects.filter(
            company=self.company,
            status__in=[
                TaxDeclaration.STATUS_DRAFT,
                TaxDeclaration.STATUS_CALCULATED,
                TaxDeclaration.STATUS_VALIDATED,
                TaxDeclaration.STATUS_SUBMITTED
            ]
        ).order_by('due_date')

    def get_overdue_declarations(self) -> list:
        """Retourne les déclarations en retard."""
        today = timezone.now().date()
        return TaxDeclaration.objects.filter(
            company=self.company,
            status__in=[
                TaxDeclaration.STATUS_DRAFT,
                TaxDeclaration.STATUS_CALCULATED,
                TaxDeclaration.STATUS_VALIDATED
            ],
            due_date__lt=today
        ).order_by('due_date')
