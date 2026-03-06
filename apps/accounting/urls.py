"""
Accounting URLs.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    AccountTypeViewSet, AccountViewSet, JournalViewSet,
    JournalEntryViewSet, JournalEntryLineViewSet, AccountBalanceViewSet
)

router = DefaultRouter()
router.register(r'account-types', AccountTypeViewSet, basename='account-type')
router.register(r'accounts', AccountViewSet, basename='account')
router.register(r'journals', JournalViewSet, basename='journal')
router.register(r'entries', JournalEntryViewSet, basename='journal-entry')
router.register(r'balances', AccountBalanceViewSet, basename='account-balance')

entries_router = routers.NestedDefaultRouter(router, r'entries', lookup='entry')
entries_router.register(r'lines', JournalEntryLineViewSet, basename='journal-entry-lines')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(entries_router.urls)),
]
