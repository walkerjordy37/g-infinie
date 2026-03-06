import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from apps.subscriptions.models import PlatformPlan, CompanySubscription
from apps.tenancy.models import Company
from django.utils import timezone
from datetime import timedelta

plans_data = [
    {
        'code': 'micro', 'name': 'Micro', 'sort_order': 1,
        'description': '1 utilisateur, 50 produits, fonctionnalites de base',
        'monthly_price': 7500, 'yearly_price': 75000,
        'max_users': 1, 'max_products': 50,
        'has_scanner': False, 'has_csv_import': False, 'has_full_cycles': False,
        'has_dashboard': False, 'has_multi_site': False, 'has_offline_mode': False,
        'has_whatsapp_alerts': False, 'has_api_access': False,
    },
    {
        'code': 'standard', 'name': 'Standard', 'sort_order': 2,
        'description': '2 utilisateurs, 500 produits, dashboard, cycles complets',
        'monthly_price': 15000, 'yearly_price': 150000,
        'max_users': 2, 'max_products': 500,
        'has_scanner': False, 'has_csv_import': False, 'has_full_cycles': True,
        'has_dashboard': True, 'has_multi_site': False, 'has_offline_mode': False,
        'has_whatsapp_alerts': False, 'has_api_access': False,
    },
    {
        'code': 'pro', 'name': 'Pro', 'sort_order': 3,
        'description': '5 utilisateurs, 2000 produits, scanner, imports CSV',
        'monthly_price': 25000, 'yearly_price': 250000,
        'max_users': 5, 'max_products': 2000,
        'has_scanner': True, 'has_csv_import': True, 'has_full_cycles': True,
        'has_dashboard': True, 'has_multi_site': False, 'has_offline_mode': False,
        'has_whatsapp_alerts': False, 'has_api_access': False,
    },
    {
        'code': 'entreprise', 'name': 'Entreprise', 'sort_order': 4,
        'description': 'Utilisateurs et produits illimites, multi-sites, mode hors-ligne, alertes WhatsApp, API',
        'monthly_price': 75000, 'yearly_price': 750000,
        'max_users': 0, 'max_products': 0,
        'has_scanner': True, 'has_csv_import': True, 'has_full_cycles': True,
        'has_dashboard': True, 'has_multi_site': True, 'has_offline_mode': True,
        'has_whatsapp_alerts': True, 'has_api_access': True,
    },
]

for p in plans_data:
    plan, created = PlatformPlan.objects.update_or_create(code=p['code'], defaults=p)
    status = 'created' if created else 'updated'
    print(f'{plan.name}: {status}')

company = Company.objects.first()
if company:
    if not CompanySubscription.objects.filter(company=company).exists():
        standard = PlatformPlan.objects.get(code='standard')
        today = timezone.now().date()
        sub = CompanySubscription.objects.create(
            company=company,
            plan=standard,
            status='trial',
            billing_cycle='monthly',
            start_date=today,
            trial_end_date=today + timedelta(days=30),
            current_period_start=today,
            current_period_end=today + timedelta(days=30),
            amount=0,
        )
        print(f'Trial subscription created for {company.name}')
    else:
        print(f'Subscription already exists for {company.name}')

print('Done!')
