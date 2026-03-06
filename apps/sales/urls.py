"""
Sales URLs - Router configuration for sales API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers

from .views import (
    SalesQuoteViewSet, SalesQuoteLineViewSet,
    SalesOrderViewSet, SalesOrderLineViewSet,
    DeliveryNoteViewSet, DeliveryNoteLineViewSet,
    SalesInvoiceViewSet, SalesInvoiceLineViewSet,
    SalesReturnViewSet, SalesReturnLineViewSet,
)

router = DefaultRouter()
router.register(r'quotes', SalesQuoteViewSet, basename='sales-quote')
router.register(r'orders', SalesOrderViewSet, basename='sales-order')
router.register(r'delivery-notes', DeliveryNoteViewSet, basename='delivery-note')
router.register(r'invoices', SalesInvoiceViewSet, basename='sales-invoice')
router.register(r'returns', SalesReturnViewSet, basename='sales-return')

quotes_router = nested_routers.NestedDefaultRouter(router, r'quotes', lookup='quote')
quotes_router.register(r'lines', SalesQuoteLineViewSet, basename='quote-lines')

orders_router = nested_routers.NestedDefaultRouter(router, r'orders', lookup='order')
orders_router.register(r'lines', SalesOrderLineViewSet, basename='order-lines')

delivery_notes_router = nested_routers.NestedDefaultRouter(
    router, r'delivery-notes', lookup='delivery_note'
)
delivery_notes_router.register(r'lines', DeliveryNoteLineViewSet, basename='delivery-note-lines')

invoices_router = nested_routers.NestedDefaultRouter(router, r'invoices', lookup='invoice')
invoices_router.register(r'lines', SalesInvoiceLineViewSet, basename='invoice-lines')

returns_router = nested_routers.NestedDefaultRouter(router, r'returns', lookup='return')
returns_router.register(r'lines', SalesReturnLineViewSet, basename='return-lines')

app_name = 'sales'

urlpatterns = [
    path('', include(router.urls)),
    path('', include(quotes_router.urls)),
    path('', include(orders_router.urls)),
    path('', include(delivery_notes_router.urls)),
    path('', include(invoices_router.urls)),
    path('', include(returns_router.urls)),
]
