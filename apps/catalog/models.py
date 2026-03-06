"""
Catalog models - Products, services, categories, and variants.
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import CompanyBaseModel, MoneyField, PercentageField


class ProductCategory(CompanyBaseModel):
    """Hierarchical category for products."""
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Catégorie parente"
    )
    lft = models.PositiveIntegerField(default=0, verbose_name="Gauche (arbre)")
    rght = models.PositiveIntegerField(default=0, verbose_name="Droite (arbre)")
    level = models.PositiveIntegerField(default=0, verbose_name="Niveau")
    image = models.ImageField(
        upload_to='catalog/categories/',
        blank=True,
        null=True,
        verbose_name="Image"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'product_category'
        verbose_name = "Catégorie de produit"
        verbose_name_plural = "Catégories de produits"
        unique_together = ['company', 'code']
        ordering = ['lft', 'name']

    def __str__(self):
        return self.name

    def get_ancestors(self):
        """Return all ancestors of this category."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return list(reversed(ancestors))

    def get_descendants(self):
        """Return all descendants of this category."""
        descendants = list(self.children.all())
        for child in self.children.all():
            descendants.extend(child.get_descendants())
        return descendants

    @property
    def full_path(self):
        """Return full path like 'Parent > Child > This'."""
        ancestors = self.get_ancestors()
        path_parts = [a.name for a in ancestors] + [self.name]
        return ' > '.join(path_parts)


class UnitOfMeasure(CompanyBaseModel):
    """Unit of measure for products (kg, pcs, L, etc.)."""
    TYPE_UNIT = 'unit'
    TYPE_WEIGHT = 'weight'
    TYPE_VOLUME = 'volume'
    TYPE_LENGTH = 'length'
    TYPE_TIME = 'time'

    TYPE_CHOICES = [
        (TYPE_UNIT, 'Unité'),
        (TYPE_WEIGHT, 'Poids'),
        (TYPE_VOLUME, 'Volume'),
        (TYPE_LENGTH, 'Longueur'),
        (TYPE_TIME, 'Temps'),
    ]

    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_UNIT,
        verbose_name="Type"
    )
    ratio = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name="Ratio",
        help_text="Ratio par rapport à l'unité de base du même type"
    )
    is_reference = models.BooleanField(
        default=False,
        verbose_name="Unité de référence",
        help_text="Unité de référence pour ce type"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'unit_of_measure'
        verbose_name = "Unité de mesure"
        verbose_name_plural = "Unités de mesure"
        unique_together = ['company', 'code']
        ordering = ['type', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class UnitConversion(CompanyBaseModel):
    """Conversion between units of measure."""
    from_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.CASCADE,
        related_name='conversions_from',
        verbose_name="Unité source"
    )
    to_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.CASCADE,
        related_name='conversions_to',
        verbose_name="Unité destination"
    )
    factor = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        verbose_name="Facteur de conversion",
        help_text="Quantité source × facteur = quantité destination"
    )

    class Meta:
        db_table = 'unit_conversion'
        verbose_name = "Conversion d'unité"
        verbose_name_plural = "Conversions d'unités"
        unique_together = ['company', 'from_unit', 'to_unit']

    def __str__(self):
        return f"{self.from_unit.code} → {self.to_unit.code} (×{self.factor})"

    def convert(self, quantity):
        """Convert a quantity from source to destination unit."""
        return quantity * self.factor


class Product(CompanyBaseModel):
    """Main product model."""
    TYPE_PRODUCT = 'product'
    TYPE_SERVICE = 'service'
    TYPE_CONSUMABLE = 'consumable'

    TYPE_CHOICES = [
        (TYPE_PRODUCT, 'Produit'),
        (TYPE_SERVICE, 'Service'),
        (TYPE_CONSUMABLE, 'Consommable'),
    ]

    VALUATION_FIFO = 'fifo'
    VALUATION_LIFO = 'lifo'
    VALUATION_AVERAGE = 'average'

    VALUATION_CHOICES = [
        (VALUATION_FIFO, 'FIFO (Premier entré, premier sorti)'),
        (VALUATION_LIFO, 'LIFO (Dernier entré, premier sorti)'),
        (VALUATION_AVERAGE, 'Coût moyen pondéré'),
    ]

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_PRODUCT,
        verbose_name="Type"
    )
    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=255, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")

    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name="Catégorie"
    )
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name="Unité de mesure"
    )
    purchase_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_purchase',
        verbose_name="Unité d'achat"
    )
    sale_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_sale',
        verbose_name="Unité de vente"
    )

    barcode = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Code-barres",
        help_text="EAN/UPC"
    )
    internal_reference = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Référence interne"
    )
    image = models.ImageField(
        upload_to='catalog/products/',
        blank=True,
        null=True,
        verbose_name="Image principale"
    )

    purchase_price = MoneyField(verbose_name="Prix d'achat HT")
    sale_price = MoneyField(verbose_name="Prix de vente HT")
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Taux TVA spécifique (%)",
        help_text="Laissez vide pour utiliser le taux par défaut de l'entreprise"
    )
    tax_exempt = models.BooleanField(
        default=False,
        verbose_name="Exonéré de TVA"
    )

    is_stockable = models.BooleanField(
        default=True,
        verbose_name="Stockable",
        help_text="Décocher pour les services"
    )
    min_stock = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Stock minimum",
        help_text="Seuil d'alerte de stock bas"
    )
    max_stock = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0'),
        verbose_name="Stock maximum",
        help_text="Quantité maximale à stocker"
    )

    valuation_method = models.CharField(
        max_length=20,
        choices=VALUATION_CHOICES,
        default=VALUATION_AVERAGE,
        verbose_name="Méthode de valorisation"
    )

    weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Poids (kg)"
    )
    volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Volume (m³)"
    )

    is_purchasable = models.BooleanField(default=True, verbose_name="Achetable")
    is_saleable = models.BooleanField(default=True, verbose_name="Vendable")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'product'
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        unique_together = ['company', 'code']
        ordering = ['name']
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'barcode']),
            models.Index(fields=['company', 'category']),
            models.Index(fields=['company', 'type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if self.type == self.TYPE_SERVICE:
            self.is_stockable = False
        super().save(*args, **kwargs)

    @property
    def sale_price_ttc(self):
        """Calculate price including tax."""
        return self.sale_price * (1 + self.tax_rate / 100)

    @property
    def margin(self):
        """Calculate margin."""
        if self.purchase_price > 0:
            return self.sale_price - self.purchase_price
        return Decimal('0')

    @property
    def margin_percentage(self):
        """Calculate margin percentage."""
        if self.sale_price > 0:
            return (self.margin / self.sale_price) * 100
        return Decimal('0')


class ProductAttribute(CompanyBaseModel):
    """Attribute definition for product variants (e.g., Color, Size)."""
    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    display_type = models.CharField(
        max_length=20,
        choices=[
            ('select', 'Liste déroulante'),
            ('radio', 'Boutons radio'),
            ('color', 'Palette de couleurs'),
        ],
        default='select',
        verbose_name="Type d'affichage"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'product_attribute'
        verbose_name = "Attribut de produit"
        verbose_name_plural = "Attributs de produits"
        unique_together = ['company', 'code']
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductAttributeValue(CompanyBaseModel):
    """Possible values for a product attribute."""
    attribute = models.ForeignKey(
        ProductAttribute,
        on_delete=models.CASCADE,
        related_name='values',
        verbose_name="Attribut"
    )
    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    color_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Code couleur",
        help_text="Code hexadécimal (ex: #FF0000)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'product_attribute_value'
        verbose_name = "Valeur d'attribut"
        verbose_name_plural = "Valeurs d'attributs"
        unique_together = ['attribute', 'code']
        ordering = ['attribute', 'sequence', 'name']

    def __str__(self):
        return f"{self.attribute.name}: {self.name}"


class ProductVariant(CompanyBaseModel):
    """Product variant (e.g., T-Shirt Red XL)."""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name="Produit"
    )
    code = models.CharField(max_length=50, verbose_name="Code variante")
    name = models.CharField(max_length=255, verbose_name="Nom complet")
    attribute_values = models.ManyToManyField(
        ProductAttributeValue,
        related_name='variants',
        verbose_name="Valeurs d'attributs"
    )

    barcode = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Code-barres"
    )
    image = models.ImageField(
        upload_to='catalog/variants/',
        blank=True,
        null=True,
        verbose_name="Image"
    )

    purchase_price = MoneyField(
        null=True,
        blank=True,
        verbose_name="Prix d'achat HT",
        help_text="Laissez vide pour utiliser le prix du produit"
    )
    sale_price = MoneyField(
        null=True,
        blank=True,
        verbose_name="Prix de vente HT",
        help_text="Laissez vide pour utiliser le prix du produit"
    )
    price_extra = MoneyField(
        default=Decimal('0'),
        verbose_name="Supplément de prix",
        help_text="Montant à ajouter au prix du produit"
    )

    weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Poids (kg)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'product_variant'
        verbose_name = "Variante de produit"
        verbose_name_plural = "Variantes de produits"
        unique_together = ['company', 'code']
        ordering = ['product', 'name']

    def __str__(self):
        return self.name

    @property
    def effective_purchase_price(self):
        """Get effective purchase price."""
        if self.purchase_price is not None:
            return self.purchase_price
        return self.product.purchase_price

    @property
    def effective_sale_price(self):
        """Get effective sale price."""
        if self.sale_price is not None:
            return self.sale_price
        return self.product.sale_price + self.price_extra


class ProductSupplier(CompanyBaseModel):
    """Link products to suppliers with their codes and prices."""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='suppliers',
        verbose_name="Produit"
    )
    supplier = models.ForeignKey(
        'partners.Partner',
        on_delete=models.CASCADE,
        related_name='supplied_products',
        verbose_name="Fournisseur"
    )
    supplier_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Code fournisseur"
    )
    supplier_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Désignation fournisseur"
    )
    purchase_price = MoneyField(verbose_name="Prix d'achat")
    min_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('1'),
        verbose_name="Quantité minimum"
    )
    lead_time_days = models.PositiveIntegerField(
        default=0,
        verbose_name="Délai de livraison (jours)"
    )
    is_preferred = models.BooleanField(
        default=False,
        verbose_name="Fournisseur préféré"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'product_supplier'
        verbose_name = "Fournisseur de produit"
        verbose_name_plural = "Fournisseurs de produits"
        unique_together = ['product', 'supplier']
        ordering = ['-is_preferred', 'supplier__name']

    def __str__(self):
        return f"{self.product.name} - {self.supplier.name}"


class ProductImage(CompanyBaseModel):
    """Multiple images per product."""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name="Produit"
    )
    image = models.ImageField(
        upload_to='catalog/products/gallery/',
        verbose_name="Image"
    )
    name = models.CharField(max_length=100, blank=True, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    sequence = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_primary = models.BooleanField(
        default=False,
        verbose_name="Image principale"
    )

    class Meta:
        db_table = 'product_image'
        verbose_name = "Image de produit"
        verbose_name_plural = "Images de produits"
        ordering = ['product', '-is_primary', 'sequence']

    def __str__(self):
        return f"{self.product.name} - {self.name or f'Image {self.sequence}'}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
