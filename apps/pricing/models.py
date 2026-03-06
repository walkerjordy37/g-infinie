"""
Pricing models - Price lists, customer pricing, volume discounts, and promotions.
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import CompanyBaseModel, MoneyField, PercentageField


class PriceList(CompanyBaseModel):
    """Named tariff: standard, wholesale, VIP, etc."""
    code = models.CharField(max_length=20, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    currency = models.ForeignKey(
        'tenancy.Currency',
        on_delete=models.PROTECT,
        related_name='price_lists',
        verbose_name="Devise"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="Liste par défaut"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    valid_from = models.DateField(
        null=True,
        blank=True,
        verbose_name="Valide à partir de"
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="Valide jusqu'au"
    )

    class Meta:
        db_table = 'price_list'
        verbose_name = "Liste de prix"
        verbose_name_plural = "Listes de prix"
        unique_together = ['company', 'code']
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if self.is_default:
            PriceList.objects.filter(
                company=self.company, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class PriceListItem(CompanyBaseModel):
    """Product price in a price list."""
    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Liste de prix"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='price_list_items',
        verbose_name="Produit"
    )
    min_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('1'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Quantité minimum",
        help_text="Prix applicable à partir de cette quantité"
    )
    unit_price = MoneyField(verbose_name="Prix unitaire HT")

    class Meta:
        db_table = 'price_list_item'
        verbose_name = "Article de liste de prix"
        verbose_name_plural = "Articles de listes de prix"
        unique_together = ['price_list', 'product', 'min_quantity']
        ordering = ['price_list', 'product', 'min_quantity']

    def __str__(self):
        return f"{self.price_list.code} - {self.product.name} (qté >= {self.min_quantity})"


class CustomerPriceRule(CompanyBaseModel):
    """Specific pricing rule for a customer."""
    DISCOUNT_PERCENTAGE = 'percentage'
    DISCOUNT_FIXED = 'fixed'

    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_PERCENTAGE, 'Pourcentage'),
        (DISCOUNT_FIXED, 'Montant fixe'),
    ]

    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.CASCADE,
        related_name='price_rules',
        verbose_name="Client"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='customer_price_rules',
        verbose_name="Produit",
        help_text="Laisser vide pour appliquer à tous les produits"
    )
    category = models.ForeignKey(
        'catalog.ProductCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='customer_price_rules',
        verbose_name="Catégorie",
        help_text="Laisser vide pour appliquer à toutes les catégories"
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default=DISCOUNT_PERCENTAGE,
        verbose_name="Type de remise"
    )
    discount_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Valeur de la remise"
    )
    valid_from = models.DateField(
        null=True,
        blank=True,
        verbose_name="Valide à partir de"
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="Valide jusqu'au"
    )
    priority = models.PositiveIntegerField(
        default=10,
        verbose_name="Priorité",
        help_text="Plus le nombre est bas, plus la priorité est haute"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'customer_price_rule'
        verbose_name = "Règle de prix client"
        verbose_name_plural = "Règles de prix clients"
        ordering = ['partner', 'priority', 'product']

    def __str__(self):
        target = self.product.name if self.product else (
            self.category.name if self.category else "Tous produits"
        )
        return f"{self.partner.name} - {target} ({self.get_discount_type_display()})"


class VolumeDiscount(CompanyBaseModel):
    """Quantity-based discount for a product."""
    DISCOUNT_PERCENTAGE = 'percentage'
    DISCOUNT_FIXED = 'fixed'

    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_PERCENTAGE, 'Pourcentage'),
        (DISCOUNT_FIXED, 'Montant fixe'),
    ]

    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='volume_discounts',
        verbose_name="Produit"
    )
    min_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Quantité minimum"
    )
    max_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Quantité maximum",
        help_text="Laisser vide pour illimité"
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default=DISCOUNT_PERCENTAGE,
        verbose_name="Type de remise"
    )
    discount_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Valeur de la remise"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'volume_discount'
        verbose_name = "Remise sur volume"
        verbose_name_plural = "Remises sur volume"
        ordering = ['product', 'min_quantity']

    def __str__(self):
        max_qty = self.max_quantity or "∞"
        return f"{self.product.name}: {self.min_quantity} - {max_qty}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.max_quantity and self.max_quantity < self.min_quantity:
            raise ValidationError({
                'max_quantity': "La quantité maximum doit être supérieure à la quantité minimum."
            })


class Promotion(CompanyBaseModel):
    """Promotion / discount campaign."""
    TYPE_PERCENTAGE = 'percentage'
    TYPE_FIXED = 'fixed'
    TYPE_BUY_X_GET_Y = 'buy_x_get_y'

    TYPE_CHOICES = [
        (TYPE_PERCENTAGE, 'Pourcentage'),
        (TYPE_FIXED, 'Montant fixe'),
        (TYPE_BUY_X_GET_Y, 'Achetez X, obtenez Y'),
    ]

    code = models.CharField(
        max_length=50,
        verbose_name="Code promo",
        help_text="Code à saisir par le client"
    )
    name = models.CharField(max_length=255, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_PERCENTAGE,
        verbose_name="Type"
    )
    value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Valeur",
        help_text="Pourcentage ou montant selon le type"
    )
    buy_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Quantité à acheter (X)",
        help_text="Pour promotions 'Achetez X, obtenez Y'"
    )
    get_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Quantité offerte (Y)",
        help_text="Pour promotions 'Achetez X, obtenez Y'"
    )
    valid_from = models.DateTimeField(verbose_name="Valide à partir de")
    valid_to = models.DateTimeField(verbose_name="Valide jusqu'au")
    min_purchase_amount = MoneyField(
        default=Decimal('0'),
        verbose_name="Montant d'achat minimum",
        help_text="Montant minimum de la commande pour appliquer la promotion"
    )
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Nombre d'utilisations maximum",
        help_text="Laisser vide pour illimité"
    )
    current_uses = models.PositiveIntegerField(
        default=0,
        verbose_name="Utilisations actuelles"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'promotion'
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"
        unique_together = ['company', 'code']
        ordering = ['-valid_from', 'name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def is_exhausted(self):
        """Check if promotion has reached max uses."""
        if self.max_uses is None:
            return False
        return self.current_uses >= self.max_uses

    @property
    def remaining_uses(self):
        """Get remaining uses."""
        if self.max_uses is None:
            return None
        return max(0, self.max_uses - self.current_uses)

    def increment_usage(self):
        """Increment the usage counter."""
        self.current_uses += 1
        self.save(update_fields=['current_uses'])


class PromotionProduct(CompanyBaseModel):
    """Products included in a promotion."""
    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Promotion"
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='promotions',
        verbose_name="Produit"
    )

    class Meta:
        db_table = 'promotion_product'
        verbose_name = "Produit en promotion"
        verbose_name_plural = "Produits en promotion"
        unique_together = ['promotion', 'product']
        ordering = ['promotion', 'product']

    def __str__(self):
        return f"{self.promotion.code} - {self.product.name}"
