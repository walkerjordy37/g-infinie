"""
Documents URLs.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    DocumentCategoryViewSet, DocumentViewSet, DocumentVersionViewSet,
    DocumentTemplateViewSet, DocumentLinkViewSet
)

router = DefaultRouter()
router.register(r'categories', DocumentCategoryViewSet, basename='document-category')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'templates', DocumentTemplateViewSet, basename='document-template')
router.register(r'links', DocumentLinkViewSet, basename='document-link')

documents_router = routers.NestedDefaultRouter(router, r'documents', lookup='document')
documents_router.register(r'versions', DocumentVersionViewSet, basename='document-versions')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(documents_router.urls)),
]
