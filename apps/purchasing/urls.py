"""
Purchasing URLs - API routes for Purchase Requests and RFQs.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    PurchaseRequestViewSet, PurchaseRequestLineViewSet,
    RequestForQuotationViewSet, RequestForQuotationLineViewSet,
    RFQComparisonViewSet,
    PurchaseOrderViewSet, PurchaseOrderLineViewSet,
    GoodsReceiptViewSet, GoodsReceiptLineViewSet,
    SupplierInvoiceViewSet, SupplierInvoiceLineViewSet
)

router = DefaultRouter()
router.register(r'purchase-requests', PurchaseRequestViewSet, basename='purchase-request')
router.register(r'rfqs', RequestForQuotationViewSet, basename='rfq')
router.register(r'rfq-comparisons', RFQComparisonViewSet, basename='rfq-comparison')
router.register(r'orders', PurchaseOrderViewSet, basename='purchase-order')
router.register(r'receipts', GoodsReceiptViewSet, basename='goods-receipt')
router.register(r'invoices', SupplierInvoiceViewSet, basename='supplier-invoice')

requests_router = routers.NestedDefaultRouter(router, r'purchase-requests', lookup='request')
requests_router.register(r'lines', PurchaseRequestLineViewSet, basename='purchase-request-lines')

rfqs_router = routers.NestedDefaultRouter(router, r'rfqs', lookup='rfq')
rfqs_router.register(r'lines', RequestForQuotationLineViewSet, basename='rfq-lines')

orders_router = routers.NestedDefaultRouter(router, r'orders', lookup='order')
orders_router.register(r'lines', PurchaseOrderLineViewSet, basename='purchase-order-lines')

receipts_router = routers.NestedDefaultRouter(router, r'receipts', lookup='receipt')
receipts_router.register(r'lines', GoodsReceiptLineViewSet, basename='goods-receipt-lines')

invoices_router = routers.NestedDefaultRouter(router, r'invoices', lookup='invoice')
invoices_router.register(r'lines', SupplierInvoiceLineViewSet, basename='supplier-invoice-lines')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(requests_router.urls)),
    path('', include(rfqs_router.urls)),
    path('', include(orders_router.urls)),
    path('', include(receipts_router.urls)),
    path('', include(invoices_router.urls)),
]
