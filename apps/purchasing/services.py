"""
Purchasing services - Business logic for Purchase Requests and RFQs.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .models import (
    PurchaseRequest, PurchaseRequestLine,
    RequestForQuotation, RequestForQuotationLine, RFQComparison,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine,
    SupplierInvoice, SupplierInvoiceLine
)


class PurchasingService:
    """Service pour la gestion des achats."""

    def __init__(self, company):
        self.company = company

    def generate_request_number(self) -> str:
        """Génère un numéro unique pour une demande d'achat."""
        from apps.tenancy.models import DocumentSequence
        try:
            sequence = DocumentSequence.objects.get(
                company=self.company,
                document_type='purchase_request'
            )
            return sequence.get_next_number()
        except DocumentSequence.DoesNotExist:
            year = timezone.now().year
            count = PurchaseRequest.objects.filter(
                company=self.company,
                date__year=year
            ).count() + 1
            return f"PR-{year}-{count:05d}"

    def generate_rfq_number(self) -> str:
        """Génère un numéro unique pour une RFQ."""
        from apps.tenancy.models import DocumentSequence
        try:
            sequence = DocumentSequence.objects.get(
                company=self.company,
                document_type='rfq'
            )
            return sequence.get_next_number()
        except DocumentSequence.DoesNotExist:
            year = timezone.now().year
            count = RequestForQuotation.objects.filter(
                company=self.company,
                date__year=year
            ).count() + 1
            return f"RFQ-{year}-{count:05d}"

    @transaction.atomic
    def create_rfqs_from_request(
        self,
        purchase_request: PurchaseRequest,
        supplier_ids: list,
        buyer=None,
        deadline_days: int = 7
    ) -> list:
        """
        Crée des RFQs pour plusieurs fournisseurs à partir d'une demande d'achat.

        Args:
            purchase_request: La demande d'achat approuvée
            supplier_ids: Liste des IDs des fournisseurs
            buyer: L'acheteur responsable
            deadline_days: Nombre de jours pour le délai de réponse

        Returns:
            Liste des RFQs créées
        """
        from apps.partners.models import Partner
        from apps.tenancy.models import Currency

        if not purchase_request.is_approved:
            raise ValueError("La demande d'achat doit être approuvée.")

        suppliers = Partner.objects.filter(
            id__in=supplier_ids,
            company=self.company,
            is_supplier=True
        )

        if not suppliers.exists():
            raise ValueError("Aucun fournisseur valide trouvé.")

        default_currency = Currency.objects.filter(
            company=self.company,
            is_default=True
        ).first()

        today = timezone.now().date()
        deadline = today + timezone.timedelta(days=deadline_days)

        rfqs = []
        for supplier in suppliers:
            rfq = RequestForQuotation.objects.create(
                company=self.company,
                number=self.generate_rfq_number(),
                purchase_request=purchase_request,
                supplier=supplier,
                date=today,
                deadline=deadline,
                status=RequestForQuotation.STATUS_DRAFT,
                currency=supplier.currency or default_currency,
                buyer=buyer
            )

            for line in purchase_request.lines.all():
                RequestForQuotationLine.objects.create(
                    company=self.company,
                    rfq=rfq,
                    request_line=line,
                    product=line.product,
                    description=line.description,
                    sequence=line.sequence,
                    quantity=line.quantity,
                    unit=line.unit,
                    quoted_unit_price=line.estimated_unit_price,
                    discount_percent=Decimal('0'),
                    discount_amount=Decimal('0'),
                    tax_rate=Decimal('0'),
                    tax_amount=Decimal('0'),
                    subtotal=line.estimated_total,
                    total=line.estimated_total
                )

            self._update_rfq_totals(rfq)
            rfqs.append(rfq)

        return rfqs

    def _update_rfq_totals(self, rfq: RequestForQuotation):
        """Met à jour les totaux d'une RFQ."""
        lines = rfq.lines.all()
        rfq.subtotal = sum(line.subtotal for line in lines)
        rfq.tax_total = sum(line.tax_amount for line in lines)
        rfq.discount_total = sum(line.discount_amount for line in lines)
        rfq.total = sum(line.total for line in lines)
        rfq.save(update_fields=['subtotal', 'tax_total', 'discount_total', 'total'])

    @transaction.atomic
    def compare_rfqs(
        self,
        purchase_request: PurchaseRequest,
        rfq_ids: list,
        compared_by=None
    ) -> RFQComparison:
        """
        Crée une comparaison de RFQs pour une demande d'achat.

        Args:
            purchase_request: La demande d'achat
            rfq_ids: Liste des IDs des RFQs à comparer
            compared_by: L'utilisateur qui fait la comparaison

        Returns:
            L'objet RFQComparison créé
        """
        rfqs = RequestForQuotation.objects.filter(
            id__in=rfq_ids,
            company=self.company,
            purchase_request=purchase_request,
            status=RequestForQuotation.STATUS_RECEIVED
        )

        if rfqs.count() < 2:
            raise ValueError("Au moins 2 RFQs avec réponse sont requises pour une comparaison.")

        comparison = RFQComparison.objects.create(
            company=self.company,
            purchase_request=purchase_request,
            comparison_date=timezone.now().date(),
            compared_by=compared_by
        )
        comparison.rfqs.set(rfqs)

        return comparison

    def get_rfq_comparison_analysis(self, comparison: RFQComparison) -> dict:
        """
        Analyse une comparaison de RFQs.

        Returns:
            Dictionnaire avec l'analyse comparative
        """
        rfqs = comparison.rfqs.all().prefetch_related('lines__product')

        analysis = {
            'rfqs': [],
            'best_price': None,
            'best_lead_time': None,
            'products': {}
        }

        for rfq in rfqs:
            rfq_data = {
                'id': str(rfq.id),
                'number': rfq.number,
                'supplier': rfq.supplier.name,
                'total': float(rfq.total),
                'delivery_lead_time': rfq.delivery_lead_time,
                'validity_date': str(rfq.validity_date) if rfq.validity_date else None,
                'payment_terms': rfq.payment_terms,
                'lines': []
            }

            for line in rfq.lines.all():
                line_data = {
                    'product_id': str(line.product.id),
                    'product_name': line.product.name,
                    'quantity': float(line.quantity),
                    'unit_price': float(line.quoted_unit_price),
                    'total': float(line.total),
                    'lead_time': line.quoted_lead_time
                }
                rfq_data['lines'].append(line_data)

                product_key = str(line.product.id)
                if product_key not in analysis['products']:
                    analysis['products'][product_key] = {
                        'name': line.product.name,
                        'quotes': []
                    }
                analysis['products'][product_key]['quotes'].append({
                    'supplier': rfq.supplier.name,
                    'unit_price': float(line.quoted_unit_price),
                    'lead_time': line.quoted_lead_time
                })

            analysis['rfqs'].append(rfq_data)

        if analysis['rfqs']:
            analysis['best_price'] = min(analysis['rfqs'], key=lambda x: x['total'])
            rfqs_with_lead_time = [r for r in analysis['rfqs'] if r['delivery_lead_time']]
            if rfqs_with_lead_time:
                analysis['best_lead_time'] = min(
                    rfqs_with_lead_time,
                    key=lambda x: x['delivery_lead_time']
                )

        return analysis

    @transaction.atomic
    def select_rfq(
        self,
        rfq: RequestForQuotation,
        reason: str = ''
    ) -> RequestForQuotation:
        """
        Sélectionne une RFQ et marque les autres comme non retenues.

        Args:
            rfq: La RFQ à sélectionner
            reason: Le motif de sélection

        Returns:
            La RFQ sélectionnée
        """
        if not rfq.can_select:
            raise ValueError("Cette RFQ ne peut pas être sélectionnée.")

        rfq.status = RequestForQuotation.STATUS_SELECTED
        rfq.save(update_fields=['status'])

        if rfq.purchase_request:
            other_rfqs = RequestForQuotation.objects.filter(
                company=self.company,
                purchase_request=rfq.purchase_request,
                status=RequestForQuotation.STATUS_RECEIVED
            ).exclude(id=rfq.id)

            for other_rfq in other_rfqs:
                other_rfq.status = RequestForQuotation.STATUS_CANCELLED
                other_rfq.save(update_fields=['status'])

        return rfq

    def check_expired_rfqs(self):
        """Vérifie et marque les RFQs expirées."""
        today = timezone.now().date()
        expired_rfqs = RequestForQuotation.objects.filter(
            company=self.company,
            status=RequestForQuotation.STATUS_SENT,
            deadline__lt=today
        )

        count = 0
        for rfq in expired_rfqs:
            rfq.status = RequestForQuotation.STATUS_EXPIRED
            rfq.save(update_fields=['status'])
            count += 1

        return count

    # =========================================================================
    # PURCHASE ORDER METHODS
    # =========================================================================

    def generate_order_number(self) -> str:
        """Génère un numéro unique pour une commande fournisseur."""
        from apps.tenancy.models import DocumentSequence
        try:
            sequence = DocumentSequence.objects.get(
                company=self.company,
                document_type='purchase_order'
            )
            return sequence.get_next_number()
        except DocumentSequence.DoesNotExist:
            year = timezone.now().year
            count = PurchaseOrder.objects.filter(
                company=self.company,
                date__year=year
            ).count() + 1
            return f"PO-{year}-{count:05d}"

    @transaction.atomic
    def create_order_from_rfq(
        self,
        rfq: RequestForQuotation,
        buyer=None,
        warehouse=None
    ) -> PurchaseOrder:
        """
        Crée une commande fournisseur à partir d'une RFQ sélectionnée.

        Args:
            rfq: La RFQ sélectionnée
            buyer: L'acheteur responsable
            warehouse: L'entrepôt de réception

        Returns:
            La commande créée
        """
        if not rfq.is_selected:
            raise ValueError("La RFQ doit être sélectionnée.")

        order = PurchaseOrder.objects.create(
            company=self.company,
            number=self.generate_order_number(),
            rfq=rfq,
            purchase_request=rfq.purchase_request,
            supplier=rfq.supplier,
            date=timezone.now().date(),
            expected_delivery_date=(
                timezone.now().date() + timezone.timedelta(days=rfq.delivery_lead_time)
                if rfq.delivery_lead_time else None
            ),
            status=PurchaseOrder.STATUS_DRAFT,
            currency=rfq.currency,
            exchange_rate=rfq.exchange_rate,
            payment_terms=rfq.payment_terms,
            buyer=buyer,
            warehouse=warehouse
        )

        for rfq_line in rfq.lines.all():
            line = PurchaseOrderLine.objects.create(
                company=self.company,
                order=order,
                rfq_line=rfq_line,
                product=rfq_line.product,
                description=rfq_line.description,
                sequence=rfq_line.sequence,
                quantity=rfq_line.quantity,
                unit=rfq_line.unit,
                unit_price=rfq_line.quoted_unit_price,
                discount_percent=rfq_line.discount_percent,
                discount_amount=rfq_line.discount_amount,
                tax_rate=rfq_line.tax_rate,
                tax_amount=rfq_line.tax_amount,
                subtotal=rfq_line.subtotal,
                total=rfq_line.total
            )

        self._update_order_totals(order)

        if rfq.purchase_request:
            rfq.purchase_request.status = PurchaseRequest.STATUS_CONVERTED
            rfq.purchase_request.save(update_fields=['status'])

        return order

    def _update_order_totals(self, order: PurchaseOrder):
        """Met à jour les totaux d'une commande."""
        lines = order.lines.all()
        order.subtotal = sum(line.subtotal for line in lines)
        order.tax_total = sum(line.tax_amount for line in lines)
        order.discount_total = sum(line.discount_amount for line in lines)
        order.total = sum(line.total for line in lines)
        order.save(update_fields=['subtotal', 'tax_total', 'discount_total', 'total'])

    # =========================================================================
    # GOODS RECEIPT METHODS
    # =========================================================================

    def generate_receipt_number(self) -> str:
        """Génère un numéro unique pour une réception."""
        from apps.tenancy.models import DocumentSequence
        try:
            sequence = DocumentSequence.objects.get(
                company=self.company,
                document_type='goods_receipt'
            )
            return sequence.get_next_number()
        except DocumentSequence.DoesNotExist:
            year = timezone.now().year
            count = GoodsReceipt.objects.filter(
                company=self.company,
                date__year=year
            ).count() + 1
            return f"GR-{year}-{count:05d}"

    @transaction.atomic
    def create_goods_receipt(
        self,
        order: PurchaseOrder,
        warehouse=None,
        received_by=None
    ) -> GoodsReceipt:
        """
        Crée une réception pour une commande fournisseur.

        Args:
            order: La commande à réceptionner
            warehouse: L'entrepôt de réception
            received_by: L'utilisateur qui réceptionne

        Returns:
            La réception créée
        """
        if not order.can_receive:
            raise ValueError("Cette commande ne peut pas être réceptionnée.")

        receipt = GoodsReceipt.objects.create(
            company=self.company,
            number=self.generate_receipt_number(),
            purchase_order=order,
            supplier=order.supplier,
            date=timezone.now().date(),
            status=GoodsReceipt.STATUS_DRAFT,
            warehouse=warehouse or order.warehouse,
            received_by=received_by
        )

        for order_line in order.lines.all():
            remaining = order_line.quantity_remaining
            if remaining > 0:
                GoodsReceiptLine.objects.create(
                    company=self.company,
                    receipt=receipt,
                    order_line=order_line,
                    product=order_line.product,
                    sequence=order_line.sequence,
                    quantity_expected=remaining,
                    quantity_received=remaining,
                    quantity_rejected=Decimal('0'),
                    unit=order_line.unit
                )

        return receipt

    @transaction.atomic
    def validate_goods_receipt(self, receipt: GoodsReceipt):
        """
        Valide une réception et met à jour les stocks et la commande.

        Args:
            receipt: La réception à valider
        """
        if not receipt.is_draft:
            raise ValueError("Cette réception a déjà été validée.")

        for line in receipt.lines.all():
            order_line = line.order_line
            accepted = line.quantity_accepted

            order_line.quantity_received += accepted
            order_line.save(update_fields=['quantity_received'])

        order = receipt.purchase_order
        all_received = all(
            line.is_fully_received for line in order.lines.all()
        )

        if all_received:
            order.status = PurchaseOrder.STATUS_RECEIVED
        else:
            order.status = PurchaseOrder.STATUS_PARTIALLY_RECEIVED
        order.save(update_fields=['status'])

        receipt.status = GoodsReceipt.STATUS_VALIDATED
        receipt.validated_at = timezone.now()
        receipt.save(update_fields=['status', 'validated_at'])

    # =========================================================================
    # SUPPLIER INVOICE METHODS
    # =========================================================================

    def generate_invoice_number(self) -> str:
        """Génère un numéro unique pour une facture fournisseur."""
        from apps.tenancy.models import DocumentSequence
        try:
            sequence = DocumentSequence.objects.get(
                company=self.company,
                document_type='supplier_invoice'
            )
            return sequence.get_next_number()
        except DocumentSequence.DoesNotExist:
            year = timezone.now().year
            count = SupplierInvoice.objects.filter(
                company=self.company,
                date__year=year
            ).count() + 1
            return f"FINV-{year}-{count:05d}"

    @transaction.atomic
    def create_invoice_from_receipts(
        self,
        order: PurchaseOrder,
        supplier_invoice_number: str,
        invoice_date=None,
        due_date=None
    ) -> SupplierInvoice:
        """
        Crée une facture fournisseur à partir des réceptions validées.

        Args:
            order: La commande fournisseur
            supplier_invoice_number: Le numéro de facture du fournisseur
            invoice_date: La date de la facture
            due_date: La date d'échéance

        Returns:
            La facture créée
        """
        from apps.tenancy.models import Currency

        today = timezone.now().date()
        default_currency = Currency.objects.filter(
            company=self.company,
            is_default=True
        ).first()

        invoice = SupplierInvoice.objects.create(
            company=self.company,
            number=self.generate_invoice_number(),
            supplier_invoice_number=supplier_invoice_number,
            invoice_type=SupplierInvoice.TYPE_INVOICE,
            purchase_order=order,
            supplier=order.supplier,
            date=invoice_date or today,
            due_date=due_date or (today + timezone.timedelta(days=30)),
            received_date=today,
            status=SupplierInvoice.STATUS_DRAFT,
            currency=order.currency or default_currency,
            exchange_rate=order.exchange_rate,
            payment_terms=order.payment_terms
        )

        for order_line in order.lines.all():
            if order_line.quantity_received > order_line.quantity_invoiced:
                qty_to_invoice = order_line.quantity_received - order_line.quantity_invoiced

                line = SupplierInvoiceLine.objects.create(
                    company=self.company,
                    invoice=invoice,
                    order_line=order_line,
                    product=order_line.product,
                    description=order_line.description,
                    sequence=order_line.sequence,
                    quantity=qty_to_invoice,
                    unit_price=order_line.unit_price,
                    discount_percent=order_line.discount_percent,
                    tax_rate=order_line.tax_rate
                )
                line.calculate_totals()
                line.save()

        self._update_invoice_totals(invoice)
        return invoice

    def _update_invoice_totals(self, invoice: SupplierInvoice):
        """Met à jour les totaux d'une facture."""
        lines = invoice.lines.all()
        invoice.subtotal = sum(line.subtotal for line in lines)
        invoice.tax_total = sum(line.tax_amount for line in lines)
        invoice.discount_total = sum(line.discount_amount for line in lines)
        invoice.total = sum(line.total for line in lines)
        invoice.amount_due = invoice.total - invoice.amount_paid
        invoice.save(update_fields=[
            'subtotal', 'tax_total', 'discount_total', 'total', 'amount_due'
        ])

    @transaction.atomic
    def perform_three_way_match(
        self,
        invoice: SupplierInvoice,
        tolerance_percent: Decimal = Decimal('0.01')
    ) -> dict:
        """
        Effectue le rapprochement à trois voies (PO, réception, facture).

        Compare:
        - Quantités commandées vs reçues vs facturées
        - Prix unitaires commandés vs facturés

        Args:
            invoice: La facture à vérifier
            tolerance_percent: Tolérance de prix (défaut 1%)

        Returns:
            Dictionnaire avec le résultat du rapprochement
        """
        result = {
            'status': 'matched',
            'discrepancies': [],
            'lines': []
        }

        has_discrepancy = False

        for inv_line in invoice.lines.all():
            line_result = {
                'product': inv_line.product.name,
                'status': 'matched',
                'issues': []
            }

            order_line = inv_line.order_line
            if not order_line:
                line_result['status'] = 'no_order_line'
                line_result['issues'].append("Pas de ligne de commande associée")
                has_discrepancy = True
            else:
                if inv_line.quantity > order_line.quantity_received:
                    line_result['status'] = 'quantity_mismatch'
                    line_result['issues'].append(
                        f"Quantité facturée ({inv_line.quantity}) > "
                        f"reçue ({order_line.quantity_received})"
                    )
                    has_discrepancy = True

                price_diff = abs(inv_line.unit_price - order_line.unit_price)
                price_tolerance = order_line.unit_price * tolerance_percent
                if price_diff > price_tolerance:
                    line_result['status'] = 'price_mismatch'
                    line_result['issues'].append(
                        f"Prix facturé ({inv_line.unit_price}) ≠ "
                        f"commandé ({order_line.unit_price})"
                    )
                    has_discrepancy = True

            inv_line.three_way_match_status = line_result['status']
            inv_line.save(update_fields=['three_way_match_status'])

            result['lines'].append(line_result)
            if line_result['issues']:
                result['discrepancies'].extend(line_result['issues'])

        if has_discrepancy:
            result['status'] = 'discrepancy'
            invoice.three_way_match_status = 'discrepancy'
            invoice.three_way_match_notes = '\n'.join(result['discrepancies'])
        else:
            result['status'] = 'matched'
            invoice.three_way_match_status = 'matched'
            invoice.three_way_match_notes = 'Rapprochement OK'

        invoice.save(update_fields=['three_way_match_status', 'three_way_match_notes'])

        return result

    @transaction.atomic
    def validate_and_update_invoiced_quantities(self, invoice: SupplierInvoice):
        """
        Valide une facture et met à jour les quantités facturées sur la commande.

        Args:
            invoice: La facture à valider
        """
        if not invoice.is_validated:
            raise ValueError("La facture n'est pas validée.")

        for inv_line in invoice.lines.all():
            if inv_line.order_line:
                inv_line.order_line.quantity_invoiced += inv_line.quantity
                inv_line.order_line.save(update_fields=['quantity_invoiced'])

        if invoice.purchase_order:
            order = invoice.purchase_order
            all_invoiced = all(
                line.is_fully_invoiced for line in order.lines.all()
            )
            if all_invoiced:
                order.status = PurchaseOrder.STATUS_INVOICED
                order.save(update_fields=['status'])
