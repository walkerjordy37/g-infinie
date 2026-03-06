"""
IAM models - Users, roles, permissions, memberships.
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from apps.core.models import UUIDModel, TimeStampedModel


class UserManager(BaseUserManager):
    """Custom user manager."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('L\'email est obligatoire')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser doit avoir is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel):
    """Custom user model."""
    email = models.EmailField(unique=True, verbose_name="Email")
    first_name = models.CharField(max_length=150, blank=True, verbose_name="Prénom")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Nom")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    is_staff = models.BooleanField(default=False, verbose_name="Staff")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_email_verified = models.BooleanField(default=False, verbose_name="Email vérifié")
    date_joined = models.DateTimeField(default=timezone.now, verbose_name="Date d'inscription")
    last_login = models.DateTimeField(blank=True, null=True, verbose_name="Dernière connexion")

    # Preferences
    language = models.CharField(max_length=10, default='fr', verbose_name="Langue")
    timezone = models.CharField(max_length=50, default='Africa/Douala', verbose_name="Fuseau horaire")

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'user'
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Role(UUIDModel, TimeStampedModel):
    """Role definition for RBAC."""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom")
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    description = models.TextField(blank=True, verbose_name="Description")
    is_system = models.BooleanField(default=False, verbose_name="Rôle système")

    # Permissions flags
    can_view_financials = models.BooleanField(default=False, verbose_name="Voir finances")
    can_post_accounting = models.BooleanField(default=False, verbose_name="Valider écritures")
    can_manage_inventory = models.BooleanField(default=False, verbose_name="Gérer stock")
    can_approve_purchases = models.BooleanField(default=False, verbose_name="Approuver achats")
    can_manage_sales = models.BooleanField(default=True, verbose_name="Gérer ventes")
    can_manage_partners = models.BooleanField(default=True, verbose_name="Gérer tiers")
    can_view_reports = models.BooleanField(default=False, verbose_name="Voir rapports")
    can_manage_users = models.BooleanField(default=False, verbose_name="Gérer utilisateurs")
    can_manage_settings = models.BooleanField(default=False, verbose_name="Gérer paramètres")

    class Meta:
        db_table = 'role'
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"

    def __str__(self):
        return self.name


class CompanyMembership(UUIDModel, TimeStampedModel):
    """User membership in a company."""
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MANAGER = 'manager'
    ROLE_USER = 'user'
    ROLE_READONLY = 'readonly'

    ROLE_CHOICES = [
        (ROLE_OWNER, 'Propriétaire'),
        (ROLE_ADMIN, 'Administrateur'),
        (ROLE_MANAGER, 'Responsable'),
        (ROLE_USER, 'Utilisateur'),
        (ROLE_READONLY, 'Lecture seule'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name="Utilisateur"
    )
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name="Entreprise"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_USER,
        verbose_name="Rôle"
    )
    custom_role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='memberships',
        verbose_name="Rôle personnalisé"
    )
    branch = models.ForeignKey(
        'tenancy.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='memberships',
        verbose_name="Succursale"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_default = models.BooleanField(default=False, verbose_name="Par défaut")

    # Specific permissions (override role defaults)
    can_view_financials = models.BooleanField(default=False, verbose_name="Voir finances")
    can_post_accounting = models.BooleanField(default=False, verbose_name="Valider écritures")
    can_manage_inventory = models.BooleanField(default=False, verbose_name="Gérer stock")
    can_approve_purchases = models.BooleanField(default=False, verbose_name="Approuver achats")

    class Meta:
        db_table = 'company_membership'
        verbose_name = "Adhésion"
        verbose_name_plural = "Adhésions"
        unique_together = ['user', 'company']

    def __str__(self):
        return f"{self.user.email} - {self.company.name} ({self.role})"

    def save(self, *args, **kwargs):
        # If this is set as default, unset others
        if self.is_default:
            CompanyMembership.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class UserSession(UUIDModel, TimeStampedModel):
    """Track user sessions for security."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name="Utilisateur"
    )
    token_id = models.CharField(max_length=255, unique=True, verbose_name="ID Token")
    device_info = models.CharField(max_length=255, blank=True, verbose_name="Appareil")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adresse IP")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    expires_at = models.DateTimeField(verbose_name="Expiration")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Dernière activité")

    class Meta:
        db_table = 'user_session'
        verbose_name = "Session"
        verbose_name_plural = "Sessions"

    def __str__(self):
        return f"{self.user.email} - {self.device_info}"


class EmailVerificationCode(UUIDModel, TimeStampedModel):
    """Email verification codes for registration."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='verification_codes',
        verbose_name="Utilisateur"
    )
    code = models.CharField(max_length=6, verbose_name="Code")
    expires_at = models.DateTimeField(verbose_name="Expiration")
    is_used = models.BooleanField(default=False, verbose_name="Utilisé")

    class Meta:
        db_table = 'email_verification_code'
        verbose_name = "Code de vérification"
        verbose_name_plural = "Codes de vérification"

    @property
    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()


class PasswordResetToken(UUIDModel, TimeStampedModel):
    """Password reset tokens."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_resets',
        verbose_name="Utilisateur"
    )
    token = models.CharField(max_length=255, unique=True, verbose_name="Token")
    expires_at = models.DateTimeField(verbose_name="Expiration")
    is_used = models.BooleanField(default=False, verbose_name="Utilisé")

    class Meta:
        db_table = 'password_reset_token'
        verbose_name = "Token de réinitialisation"
        verbose_name_plural = "Tokens de réinitialisation"

    @property
    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()
