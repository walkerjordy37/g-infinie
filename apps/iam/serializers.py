"""
Serializers for IAM module.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.core.serializers import BaseModelSerializer
from .models import User, Role, CompanyMembership


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with additional claims."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['full_name'] = user.full_name

        # Add default company
        default_membership = user.memberships.filter(is_default=True, is_active=True).first()
        if default_membership:
            token['company_id'] = str(default_membership.company.id)
            token['company_name'] = default_membership.company.name
            token['role'] = default_membership.role

        return token


class UserSerializer(BaseModelSerializer):
    full_name = serializers.CharField(read_only=True)
    companies = serializers.SerializerMethodField()
    default_company = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'avatar', 'is_active', 'language', 'timezone',
            'date_joined', 'last_login', 'companies', 'default_company'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    def get_companies(self, obj):
        memberships = obj.memberships.filter(is_active=True).select_related('company')
        return [
            {
                'id': str(m.company.id),
                'code': m.company.code,
                'name': m.company.name,
                'role': m.role,
                'is_default': m.is_default,
                'membership_id': str(m.id)
            }
            for m in memberships
        ]

    def get_default_company(self, obj):
        m = obj.memberships.filter(is_active=True, is_default=True).select_related('company').first()
        if not m:
            m = obj.memberships.filter(is_active=True).select_related('company').first()
        return str(m.company.id) if m else None


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    company_name = serializers.CharField(write_only=True)
    company_code = serializers.CharField(write_only=True)
    company_city = serializers.CharField(write_only=True, required=False, default='')
    company_phone = serializers.CharField(write_only=True, required=False, default='')

    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm', 'first_name', 'last_name', 'phone',
            'company_name', 'company_code', 'company_city', 'company_phone',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Les mots de passe ne correspondent pas'})
        return attrs

    def validate_company_code(self, value):
        from apps.tenancy.models import Company
        if Company.objects.filter(code=value.upper()).exists():
            raise serializers.ValidationError("Ce code entreprise est déjà utilisé.")
        return value.upper()

    def create(self, validated_data):
        company_name = validated_data.pop('company_name')
        company_code = validated_data.pop('company_code')
        company_city = validated_data.pop('company_city', '')
        company_phone = validated_data.pop('company_phone', '')
        validated_data.pop('password_confirm')

        from django.db import transaction
        from apps.tenancy.models import Company, Currency
        from apps.subscriptions.services import SubscriptionService

        with transaction.atomic():
            # 1. Create user
            user = User.objects.create_user(**validated_data)

            # 2. Create company with default currency (XAF)
            currency = Currency.objects.filter(code='XAF').first()
            if not currency:
                currency = Currency.objects.first()
            company = Company.objects.create(
                name=company_name,
                code=company_code,
                city=company_city,
                phone=company_phone,
                email=user.email,
                currency=currency,
            )

            # 3. Create owner membership with full permissions
            CompanyMembership.objects.create(
                user=user,
                company=company,
                role=CompanyMembership.ROLE_OWNER,
                is_active=True,
                is_default=True,
                can_view_financials=True,
                can_post_accounting=True,
                can_manage_inventory=True,
                can_approve_purchases=True,
            )

            # 4. Create 30-day trial subscription
            try:
                SubscriptionService.create_trial_subscription(company, plan_code='standard')
            except Exception:
                # If standard plan doesn't exist, try any active plan
                try:
                    from apps.subscriptions.models import PlatformPlan
                    plan = PlatformPlan.objects.filter(is_active=True).first()
                    if plan:
                        SubscriptionService.create_trial_subscription(company, plan_code=plan.code)
                except Exception:
                    pass

            # 5. Generate email verification code
            import random
            from datetime import timedelta
            from django.utils import timezone as tz
            from .models import EmailVerificationCode

            code = f"{random.randint(100000, 999999)}"
            EmailVerificationCode.objects.create(
                user=user,
                code=code,
                expires_at=tz.now() + timedelta(minutes=30),
            )

            # 6. Send verification email
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject='G-Infini - Code de vérification',
                    message=f'Votre code de vérification est : {code}\n\nCe code expire dans 30 minutes.',
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass

        return user


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """Serializer for admin to create users in their company."""
    password = serializers.CharField(write_only=True, required=False)
    role = serializers.ChoiceField(
        choices=['member', 'manager', 'admin'],
        default='member',
        write_only=True
    )

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 'phone', 'role']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un utilisateur avec cet email existe déjà.")
        return value

    def create(self, validated_data):
        role = validated_data.pop('role', 'member')
        password = validated_data.pop('password', None)
        
        # Generate password if not provided
        if not password:
            import secrets
            password = secrets.token_urlsafe(12)
        
        user = User.objects.create_user(password=password, **validated_data)
        
        # Create membership in admin's company
        company = self.context.get('company')
        if company:
            CompanyMembership.objects.create(
                user=user,
                company=company,
                role=role,
                is_active=True,
                is_default=True
            )
        
        # Store generated password to return it
        user._generated_password = password
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Les mots de passe ne correspondent pas'})
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Mot de passe actuel incorrect')
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Les mots de passe ne correspondent pas'})
        return attrs


class RoleSerializer(BaseModelSerializer):
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'code', 'description', 'is_system',
            'can_view_financials', 'can_post_accounting', 'can_manage_inventory',
            'can_approve_purchases', 'can_manage_sales', 'can_manage_partners',
            'can_view_reports', 'can_manage_users', 'can_manage_settings'
        ]
        read_only_fields = ['id', 'is_system']


class CompanyMembershipSerializer(BaseModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = CompanyMembership
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'company', 'company_name', 'role', 'custom_role',
            'branch', 'branch_name', 'is_active', 'is_default',
            'can_view_financials', 'can_post_accounting',
            'can_manage_inventory', 'can_approve_purchases',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanyMembershipCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyMembership
        fields = [
            'user', 'company', 'role', 'custom_role', 'branch',
            'can_view_financials', 'can_post_accounting',
            'can_manage_inventory', 'can_approve_purchases'
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user to update their own profile."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'avatar', 'language', 'timezone']
