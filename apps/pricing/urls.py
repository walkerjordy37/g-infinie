"""
Pricing URL configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PriceListViewSet,
    PriceListItemViewSet,
    CustomerPriceRuleViewSet,
    VolumeDiscountViewSet,
    PromotionViewSet,
    PromotionProductViewSet,
    PriceCalculationViewSet,
)

router = DefaultRouter()
router.register(r'price-lists', PriceListViewSet, basename='price-list')
router.register(r'price-list-items', PriceListItemViewSet, basename='price-list-item')
router.register(r'customer-rules', CustomerPriceRuleViewSet, basename='customer-price-rule')
router.register(r'volume-discounts', VolumeDiscountViewSet, basename='volume-discount')
router.register(r'promotions', PromotionViewSet, basename='promotion')
router.register(r'promotion-products', PromotionProductViewSet, basename='promotion-product')
router.register(r'calculate', PriceCalculationViewSet, basename='price-calculation')

app_name = 'pricing'

urlpatterns = [
    path('', include(router.urls)),
]
