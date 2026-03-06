"""
Custom pagination classes for the API.
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list endpoints."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class LargeResultsSetPagination(PageNumberPagination):
    """Pagination for large datasets."""
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class CursorResultsSetPagination(CursorPagination):
    """Cursor-based pagination for mobile apps."""
    page_size = 20
    page_size_query_param = 'page_size'
    ordering = '-created_at'
    cursor_query_param = 'cursor'
