"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # API v1
    path('api/v1/iam/', include('apps.iam.urls')),
    path('api/v1/tenancy/', include('apps.tenancy.urls')),
    path('api/v1/audit/', include('apps.audit.urls')),
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/pricing/', include('apps.pricing.urls')),
    path('api/v1/partners/', include('apps.partners.urls')),
    path('api/v1/sales/', include('apps.sales.urls')),
    path('api/v1/purchasing/', include('apps.purchasing.urls')),
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/accounting/', include('apps.accounting.urls')),
    path('api/v1/tax/', include('apps.tax.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/treasury/', include('apps.treasury.urls')),
    path('api/v1/documents/', include('apps.documents.urls')),
    path('api/v1/subscriptions/', include('apps.subscriptions.urls')),
    path('api/v1/reporting/', include('apps.reporting.urls')),
    path('api/v1/workflow/', include('apps.workflow.urls')),
    path('api/v1/sync/', include('apps.sync.urls')),
]
