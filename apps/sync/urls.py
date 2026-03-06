from django.urls import path
from .views import SyncDeltaAPIView, SyncActionsAPIView

app_name = 'sync'

urlpatterns = [
    path('delta/', SyncDeltaAPIView.as_view(), name='sync-delta'),
    path('actions/', SyncActionsAPIView.as_view(), name='sync-actions'),
]
