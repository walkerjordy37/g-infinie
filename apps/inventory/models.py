"""
Inventory models - Warehouses, stock movements, and inventory management.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from apps.core.models import CompanyBaseModel, MoneyField


class Warehouse(CompanyBaseModel):
    """Entrepôt ou dépôt de stockage."""
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    address_street = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Adresse"
    )
    address_street2 = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Complément d'adresse"
    )
    address_city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ville"
    )
    address_postal_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Code postal"
    )
    address_country = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pays"
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_warehouses',
        verbose_name="Responsable"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'warehouse'
        verbose_name = "Entrepôt"
        verbose_name_plural = "Entrepôts"
        unique_together = ['company', 'code']
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [
            self.address_street,
            self.address_street2,
            f"{self.address_postal_code} {self.address_city}".strip(),
            self.address_country
        ]
        return ', '.join(p for p in parts if p)


class WarehouseLocation(CompanyBaseModel):
    """Zone ou emplacement dans un entrepôt."""
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='locations',
        verbose_name="Entrepôt"
    )
    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Emplacement parent"
    )
    barcode = models.CharField(max_length=50, blank=True, verbose_name="Code-barres")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'warehouse_location'
        verbose_name = "Emplacement"
        verbose_name_plural = "Emplacements"
        unique_together = ['warehouse', 'code']
        ordering = ['warehouse', 'code']

    def __str__(self):
        return f"{self.warehouse.code}/{self.code}"

    @property
    def full_path(self):
        """Return full path like 'Zone A > Allée 1 > Rack 3'."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current.name)
            current = current.parent
        path_parts = list(reversed(ancestors)) + [self.name]
        return ' > '.join(path_parts)


class StockLevel(CompanyBaseModel):
    """Stock actuel par produit, entrepôt et emplacement."""
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='stock_levels',
        verbose_name="Produit"
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='stock_levels',
        verbose_name="Entrepôt"
    )
    location = models.ForeignKey(
        WarehouseLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_levels',
        verbose_name="Emplacement"
    )
    quantity_on_hand = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité en stock"
    )
    quantity_reserved = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité réservée"
    )
    last_movement_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date dernier mouvement"
    )
    unit_cost = MoneyField(
        verbose_name="Coût unitaire moyen",
        help_text="Coût moyen pondéré pour valorisation"
    )

    class Meta:
        db_table = 'stock_level'
        verbose_name = "Niveau de stock"
        verbose_name_plural = "Niveaux de stock"
        unique_together = ['product', 'warehouse', 'location']
        ordering = ['product', 'warehouse']

    def __str__(self):
        loc = f"/{self.location.code}" if self.location else ""
        return f"{self.product.code} @ {self.warehouse.code}{loc}: {self.quantity_on_hand}"

    @property
    def quantity_available(self):
        """Quantité disponible (stock - réservé)."""
        return self.quantity_on_hand - self.quantity_reserved

    @property
    def valuation(self):
        """Valorisation du stock."""
        return self.quantity_on_hand * self.unit_cost


class StockMovement(CompanyBaseModel):
    """Mouvement de stock (entrée, sortie, transfert, ajustement)."""
    TYPE_IN = 'in'
    TYPE_OUT = 'out'
    TYPE_TRANSFER = 'transfer'
    TYPE_ADJUSTMENT = 'adjustment'

    TYPE_CHOICES = [
        (TYPE_IN, 'Entrée'),
        (TYPE_OUT, 'Sortie'),
        (TYPE_TRANSFER, 'Transfert'),
        (TYPE_ADJUSTMENT, 'Ajustement'),
    ]

    SOURCE_PURCHASE = 'purchase'
    SOURCE_SALE = 'sale'
    SOURCE_RETURN_CUSTOMER = 'return_customer'
    SOURCE_RETURN_SUPPLIER = 'return_supplier'
    SOURCE_TRANSFER = 'transfer'
    SOURCE_ADJUSTMENT = 'adjustment'
    SOURCE_INITIAL = 'initial'

    SOURCE_CHOICES = [
        (SOURCE_PURCHASE, 'Achat'),
        (SOURCE_SALE, 'Vente'),
        (SOURCE_RETURN_CUSTOMER, 'Retour client'),
        (SOURCE_RETURN_SUPPLIER, 'Retour fournisseur'),
        (SOURCE_TRANSFER, 'Transfert'),
        (SOURCE_ADJUSTMENT, 'Ajustement'),
        (SOURCE_INITIAL, 'Stock initial'),
    ]

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name="Type"
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        verbose_name="Origine"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='stock_movements',
        verbose_name="Produit"
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='stock_movements',
        verbose_name="Entrepôt"
    )
    source_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='outgoing_movements',
        verbose_name="Entrepôt source",
        help_text="Pour les transferts uniquement"
    )
    location = models.ForeignKey(
        WarehouseLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name="Emplacement"
    )
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name="Quantité"
    )
    unit_cost = MoneyField(
        verbose_name="Coût unitaire",
        help_text="Pour la valorisation du stock"
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence",
        help_text="Numéro de document"
    )
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Type de référence",
        help_text="Ex: order, invoice, adjustment"
    )
    reference_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="ID de référence"
    )
    date = models.DateTimeField(verbose_name="Date du mouvement")
    notes = models.TextField(blank=True, verbose_name="Notes")
    reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Motif"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_movements_created',
        verbose_name="Créé par"
    )
    lot_serial = models.ForeignKey(
        'LotSerial',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
        verbose_name="Lot/Série"
    )

    class Meta:
        db_table = 'stock_movement'
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['product', 'warehouse', 'date']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]

    def __str__(self):
        return f"{self.get_type_display()} - {self.product.code} x{self.quantity}"

    @property
    def signed_quantity(self):
        """Quantité signée (positive pour entrée, négative pour sortie)."""
        if self.type in [self.TYPE_IN]:
            return self.quantity
        elif self.type in [self.TYPE_OUT]:
            return -self.quantity
        return self.quantity

    @property
    def total_value(self):
        """Valeur totale du mouvement."""
        return self.quantity * self.unit_cost


class StockAdjustment(CompanyBaseModel):
    """Ajustement de stock (inventaire, perte, casse, etc.)."""
    TYPE_INVENTORY_COUNT = 'inventory_count'
    TYPE_DAMAGE = 'damage'
    TYPE_LOSS = 'loss'
    TYPE_FOUND = 'found'

    TYPE_CHOICES = [
        (TYPE_INVENTORY_COUNT, 'Inventaire'),
        (TYPE_DAMAGE, 'Casse'),
        (TYPE_LOSS, 'Perte'),
        (TYPE_FOUND, 'Retrouvé'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_CONFIRMED, 'Confirmé'),
    ]

    reference = models.CharField(max_length=50, verbose_name="Référence")
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='adjustments',
        verbose_name="Entrepôt"
    )
    adjustment_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_INVENTORY_COUNT,
        verbose_name="Type d'ajustement"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Statut"
    )
    date = models.DateField(verbose_name="Date")
    notes = models.TextField(blank=True, verbose_name="Notes")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_adjustments',
        verbose_name="Confirmé par"
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de confirmation"
    )

    class Meta:
        db_table = 'stock_adjustment'
        verbose_name = "Ajustement de stock"
        verbose_name_plural = "Ajustements de stock"
        unique_together = ['company', 'reference']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.reference} - {self.warehouse.name}"

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    @property
    def total_difference(self):
        """Total des différences de quantité."""
        return sum(line.difference for line in self.lines.all())


class StockAdjustmentLine(CompanyBaseModel):
    """Ligne d'ajustement de stock."""
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Ajustement"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='adjustment_lines',
        verbose_name="Produit"
    )
    location = models.ForeignKey(
        WarehouseLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adjustment_lines',
        verbose_name="Emplacement"
    )
    system_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité système"
    )
    counted_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Quantité comptée"
    )
    unit_cost = MoneyField(
        verbose_name="Coût unitaire",
        help_text="Pour valorisation de la différence"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'stock_adjustment_line'
        verbose_name = "Ligne d'ajustement"
        verbose_name_plural = "Lignes d'ajustement"
        ordering = ['adjustment', 'product__code']

    def __str__(self):
        return f"{self.adjustment.reference} - {self.product.code}"

    @property
    def difference(self):
        """Différence entre quantité comptée et système."""
        return self.counted_quantity - self.system_quantity

    @property
    def difference_value(self):
        """Valeur de la différence."""
        return self.difference * self.unit_cost


class LotSerial(CompanyBaseModel):
    """Suivi des lots et numéros de série."""
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='lots_serials',
        verbose_name="Produit"
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='lots_serials',
        verbose_name="Entrepôt"
    )
    location = models.ForeignKey(
        WarehouseLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lots_serials',
        verbose_name="Emplacement"
    )
    lot_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Numéro de lot"
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Numéro de série"
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date d'expiration"
    )
    manufacturing_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de fabrication"
    )
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('1'),
        verbose_name="Quantité",
        help_text="1 pour les numéros de série"
    )
    unit_cost = MoneyField(verbose_name="Coût unitaire")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'lot_serial'
        verbose_name = "Lot/Série"
        verbose_name_plural = "Lots/Séries"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'lot_number']),
            models.Index(fields=['product', 'serial_number']),
        ]

    def __str__(self):
        identifier = self.serial_number or self.lot_number
        return f"{self.product.code} - {identifier}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.lot_number and not self.serial_number:
            raise ValidationError("Numéro de lot ou numéro de série requis.")
        if self.serial_number and self.quantity != Decimal('1'):
            raise ValidationError("La quantité doit être 1 pour un numéro de série.")

    @property
    def is_expired(self):
        """Check if lot is expired."""
        if self.expiry_date:
            from django.utils import timezone
            return self.expiry_date < timezone.now().date()
        return False
