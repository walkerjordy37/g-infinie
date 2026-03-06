"""
Script de seed complet pour la base PostgreSQL.
Recrée toutes les données par défaut : devises, plans, rôles, admin, entreprise, abonnement.
"""
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.local'
django.setup()

from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

# ─── 1. Devises ──────────────────────────────────────────────────────
from apps.tenancy.models import Currency

currencies_data = [
    {'code': 'XAF', 'name': 'Franc CFA (CEMAC)', 'symbol': 'FCFA', 'decimal_places': 0},
    {'code': 'XOF', 'name': 'Franc CFA (UEMOA)', 'symbol': 'CFA', 'decimal_places': 0},
    {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'decimal_places': 2},
    {'code': 'USD', 'name': 'Dollar américain', 'symbol': '$', 'decimal_places': 2},
    {'code': 'GBP', 'name': 'Livre sterling', 'symbol': '£', 'decimal_places': 2},
]

print('=== Devises ===')
for c in currencies_data:
    obj, created = Currency.objects.update_or_create(code=c['code'], defaults=c)
    print(f"  {obj.code}: {'créée' if created else 'mise à jour'}")

xaf = Currency.objects.get(code='XAF')

# ─── 2. Plans d'abonnement ───────────────────────────────────────────
from apps.subscriptions.models import PlatformPlan

plans_data = [
    {
        'code': 'micro', 'name': 'Micro', 'sort_order': 1,
        'description': '1 utilisateur, 50 produits, fonctionnalités de base',
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
        'description': 'Utilisateurs et produits illimités, multi-sites, mode hors-ligne, alertes WhatsApp, API',
        'monthly_price': 75000, 'yearly_price': 750000,
        'max_users': 0, 'max_products': 0,
        'has_scanner': True, 'has_csv_import': True, 'has_full_cycles': True,
        'has_dashboard': True, 'has_multi_site': True, 'has_offline_mode': True,
        'has_whatsapp_alerts': True, 'has_api_access': True,
    },
]

print('\n=== Plans d\'abonnement ===')
for p in plans_data:
    obj, created = PlatformPlan.objects.update_or_create(code=p['code'], defaults=p)
    print(f"  {obj.name}: {'créé' if created else 'mis à jour'}")

# ─── 3. Rôles système ────────────────────────────────────────────────
from apps.iam.models import Role

roles_data = [
    {
        'code': 'owner', 'name': 'Propriétaire', 'is_system': True,
        'description': 'Propriétaire de l\'entreprise - tous les droits',
        'can_view_financials': True, 'can_post_accounting': True,
        'can_manage_inventory': True, 'can_approve_purchases': True,
        'can_manage_sales': True, 'can_manage_partners': True,
        'can_view_reports': True, 'can_manage_users': True,
        'can_manage_settings': True,
    },
    {
        'code': 'admin', 'name': 'Administrateur', 'is_system': True,
        'description': 'Administrateur - gestion complète sauf paramètres critiques',
        'can_view_financials': True, 'can_post_accounting': True,
        'can_manage_inventory': True, 'can_approve_purchases': True,
        'can_manage_sales': True, 'can_manage_partners': True,
        'can_view_reports': True, 'can_manage_users': True,
        'can_manage_settings': False,
    },
    {
        'code': 'manager', 'name': 'Responsable', 'is_system': True,
        'description': 'Responsable - gestion opérationnelle',
        'can_view_financials': True, 'can_post_accounting': False,
        'can_manage_inventory': True, 'can_approve_purchases': True,
        'can_manage_sales': True, 'can_manage_partners': True,
        'can_view_reports': True, 'can_manage_users': False,
        'can_manage_settings': False,
    },
    {
        'code': 'user', 'name': 'Utilisateur', 'is_system': True,
        'description': 'Utilisateur standard - ventes et stock',
        'can_view_financials': False, 'can_post_accounting': False,
        'can_manage_inventory': True, 'can_approve_purchases': False,
        'can_manage_sales': True, 'can_manage_partners': True,
        'can_view_reports': False, 'can_manage_users': False,
        'can_manage_settings': False,
    },
    {
        'code': 'readonly', 'name': 'Lecture seule', 'is_system': True,
        'description': 'Consultation uniquement',
        'can_view_financials': False, 'can_post_accounting': False,
        'can_manage_inventory': False, 'can_approve_purchases': False,
        'can_manage_sales': False, 'can_manage_partners': False,
        'can_view_reports': True, 'can_manage_users': False,
        'can_manage_settings': False,
    },
]

print('\n=== Rôles système ===')
for r in roles_data:
    obj, created = Role.objects.update_or_create(code=r['code'], defaults=r)
    print(f"  {obj.name}: {'créé' if created else 'mis à jour'}")

# ─── 4. Superuser admin + entreprise + abonnement ────────────────────
from apps.iam.models import User, CompanyMembership
from apps.tenancy.models import Company, CompanySettings, Branch
from apps.subscriptions.models import CompanySubscription

print('\n=== Compte admin ===')

with transaction.atomic():
    # Create or get admin user
    admin_email = 'admin@g-infini.com'
    admin_user, user_created = User.objects.get_or_create(
        email=admin_email,
        defaults={
            'first_name': 'Admin',
            'last_name': 'G-Infini',
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
            'is_email_verified': True,
        }
    )
    if user_created:
        admin_user.set_password('admin123')
        admin_user.save()
        print(f"  Utilisateur admin créé: {admin_email} / admin123")
    else:
        print(f"  Utilisateur admin existe déjà: {admin_email}")

    # Create default company
    company, comp_created = Company.objects.get_or_create(
        code='GINFINI',
        defaults={
            'name': 'G-Infini',
            'legal_name': 'G-Infini SARL',
            'city': 'Douala',
            'country': 'Cameroun',
            'email': admin_email,
            'currency': xaf,
            'default_tax_rate': Decimal('19.25'),
        }
    )
    if comp_created:
        print(f"  Entreprise créée: {company.name}")
    else:
        print(f"  Entreprise existe déjà: {company.name}")

    # Create company settings
    settings_obj, s_created = CompanySettings.objects.get_or_create(
        company=company,
        defaults={
            'default_receivable_account': '411000',
            'default_payable_account': '401000',
            'default_sales_account': '701000',
            'default_purchase_account': '601000',
            'default_vat_collected_account': '443100',
            'default_vat_deductible_account': '445600',
            'default_payment_terms_days': 30,
            'quote_validity_days': 30,
            'default_valuation_method': 'average',
        }
    )
    if s_created:
        print(f"  Paramètres entreprise créés")

    # Create HQ branch
    branch, b_created = Branch.objects.get_or_create(
        company=company,
        code='HQ',
        defaults={
            'name': 'Siège social',
            'city': 'Douala',
            'is_active': True,
            'is_headquarters': True,
        }
    )
    if b_created:
        print(f"  Succursale siège créée")

    # Create owner membership
    membership, m_created = CompanyMembership.objects.get_or_create(
        user=admin_user,
        company=company,
        defaults={
            'role': CompanyMembership.ROLE_OWNER,
            'is_active': True,
            'is_default': True,
            'can_view_financials': True,
            'can_post_accounting': True,
            'can_manage_inventory': True,
            'can_approve_purchases': True,
        }
    )
    if m_created:
        print(f"  Membership owner créé")

    # Create trial subscription
    if not CompanySubscription.objects.filter(company=company).exists():
        standard_plan = PlatformPlan.objects.get(code='standard')
        today = timezone.now().date()
        CompanySubscription.objects.create(
            company=company,
            plan=standard_plan,
            status='trial',
            billing_cycle='monthly',
            start_date=today,
            trial_end_date=today + timedelta(days=30),
            current_period_start=today,
            current_period_end=today + timedelta(days=30),
            amount=0,
        )
        print(f"  Abonnement trial (30 jours) créé")
    else:
        print(f"  Abonnement existe déjà")

print('\n✅ Seed terminé avec succès !')
print(f'\n📋 Récapitulatif :')
print(f'   Devises       : {Currency.objects.count()}')
print(f'   Plans         : {PlatformPlan.objects.count()}')
print(f'   Rôles         : {Role.objects.count()}')
print(f'   Entreprises   : {Company.objects.count()}')
print(f'   Utilisateurs  : {User.objects.count()}')
print(f'\n🔐 Connexion admin : {admin_email} / admin123')
