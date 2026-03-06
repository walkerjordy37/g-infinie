"""
Inventory URL configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WarehouseViewSet, WarehouseLocationViewSet,
    StockLevelViewSet, StockMovementViewSet,
    StockAdjustmentViewSet, StockAdjustmentLineViewSet,
    LotSerialViewSet
)

app_name = 'inventory'

router = DefaultRouter()
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'locations', WarehouseLocationViewSet, basename='location')
router.register(r'stock-levels', StockLevelViewSet, basename='stock-level')
router.register(r'movements', StockMovementViewSet, basename='movement')
router.register(r'adjustments', StockAdjustmentViewSet, basename='adjustment')
router.register(r'adjustment-lines', StockAdjustmentLineViewSet, basename='adjustment-line')
router.register(r'lots-serials', LotSerialViewSet, basename='lot-serial')

urlpatterns = [
    path('', include(router.urls)),
]
