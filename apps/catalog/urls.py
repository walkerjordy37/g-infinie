"""
Catalog URL configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductCategoryViewSet,
    UnitOfMeasureViewSet,
    UnitConversionViewSet,
    ProductAttributeViewSet,
    ProductAttributeValueViewSet,
    ProductVariantViewSet,
    ProductSupplierViewSet,
    ProductImageViewSet,
    ProductViewSet,
)

router = DefaultRouter()
router.register(r'categories', ProductCategoryViewSet, basename='product-category')
router.register(r'units', UnitOfMeasureViewSet, basename='unit-of-measure')
router.register(r'conversions', UnitConversionViewSet, basename='unit-conversion')
router.register(r'attributes', ProductAttributeViewSet, basename='product-attribute')
router.register(r'attribute-values', ProductAttributeValueViewSet, basename='product-attribute-value')
router.register(r'variants', ProductVariantViewSet, basename='product-variant')
router.register(r'suppliers', ProductSupplierViewSet, basename='product-supplier')
router.register(r'images', ProductImageViewSet, basename='product-image')
router.register(r'products', ProductViewSet, basename='product')

app_name = 'catalog'

urlpatterns = [
    path('', include(router.urls)),
]
