"""
Reporting models - Report definitions, schedules, dashboards.
"""
from django.db import models
from django.conf import settings
from apps.core.models import CompanyBaseModel


class ReportDefinition(CompanyBaseModel):
    """Définition de rapport."""
    TYPE_FINANCIAL = 'financial'
    TYPE_SALES = 'sales'
    TYPE_PURCHASING = 'purchasing'
    TYPE_INVENTORY = 'inventory'
    TYPE_CUSTOM = 'custom'

    TYPE_CHOICES = [
        (TYPE_FINANCIAL, 'Financier'),
        (TYPE_SALES, 'Ventes'),
        (TYPE_PURCHASING, 'Achats'),
        (TYPE_INVENTORY, 'Inventaire'),
        (TYPE_CUSTOM, 'Personnalisé'),
    ]

    FORMAT_PDF = 'pdf'
    FORMAT_EXCEL = 'excel'
    FORMAT_CSV = 'csv'

    FORMAT_CHOICES = [
        (FORMAT_PDF, 'PDF'),
        (FORMAT_EXCEL, 'Excel'),
        (FORMAT_CSV, 'CSV'),
    ]

    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    report_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_CUSTOM,
        verbose_name="Type"
    )

    query = models.TextField(blank=True, verbose_name="Requête SQL")
    template = models.TextField(blank=True, verbose_name="Template")
    parameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Paramètres"
    )

    default_format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default=FORMAT_PDF,
        verbose_name="Format par défaut"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_system = models.BooleanField(default=False, verbose_name="Système")

    class Meta:
        db_table = 'reporting_definition'
        verbose_name = "Définition de rapport"
        verbose_name_plural = "Définitions de rapports"
        unique_together = ['company', 'code']
        ordering = ['report_type', 'name']

    def __str__(self):
        return self.name


class ReportSchedule(CompanyBaseModel):
    """Planification de rapport."""
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_MONTHLY = 'monthly'

    FREQUENCY_CHOICES = [
        (FREQUENCY_DAILY, 'Quotidien'),
        (FREQUENCY_WEEKLY, 'Hebdomadaire'),
        (FREQUENCY_MONTHLY, 'Mensuel'),
    ]

    report = models.ForeignKey(
        ReportDefinition,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name="Rapport"
    )
    name = models.CharField(max_length=200, verbose_name="Nom")
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default=FREQUENCY_MONTHLY,
        verbose_name="Fréquence"
    )
    day_of_week = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Jour de la semaine (0=Lundi)"
    )
    day_of_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Jour du mois"
    )
    time = models.TimeField(verbose_name="Heure")

    parameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Paramètres"
    )
    format = models.CharField(
        max_length=10,
        choices=ReportDefinition.FORMAT_CHOICES,
        default=ReportDefinition.FORMAT_PDF,
        verbose_name="Format"
    )

    recipients = models.TextField(
        blank=True,
        verbose_name="Destinataires (emails)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    last_run = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dernière exécution"
    )
    next_run = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Prochaine exécution"
    )

    class Meta:
        db_table = 'reporting_schedule'
        verbose_name = "Planification de rapport"
        verbose_name_plural = "Planifications de rapports"
        ordering = ['next_run']

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"


class ReportExecution(CompanyBaseModel):
    """Historique d'exécution de rapport."""
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_RUNNING, 'En cours'),
        (STATUS_COMPLETED, 'Terminé'),
        (STATUS_FAILED, 'Échec'),
    ]

    report = models.ForeignKey(
        ReportDefinition,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name="Rapport"
    )
    schedule = models.ForeignKey(
        ReportSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='executions',
        verbose_name="Planification"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="Statut"
    )
    parameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Paramètres"
    )
    format = models.CharField(
        max_length=10,
        choices=ReportDefinition.FORMAT_CHOICES,
        default=ReportDefinition.FORMAT_PDF,
        verbose_name="Format"
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Début"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fin"
    )
    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Durée (sec)"
    )

    output_file = models.FileField(
        upload_to='reports/output/',
        blank=True,
        verbose_name="Fichier"
    )
    error_message = models.TextField(blank=True, verbose_name="Erreur")

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='report_executions',
        verbose_name="Exécuté par"
    )

    class Meta:
        db_table = 'reporting_execution'
        verbose_name = "Exécution de rapport"
        verbose_name_plural = "Exécutions de rapports"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.report.name} - {self.created_at}"


class Dashboard(CompanyBaseModel):
    """Tableau de bord."""
    code = models.CharField(max_length=50, verbose_name="Code")
    name = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    is_default = models.BooleanField(default=False, verbose_name="Par défaut")
    is_public = models.BooleanField(default=False, verbose_name="Public")
    layout = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuration"
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dashboards',
        verbose_name="Propriétaire"
    )

    class Meta:
        db_table = 'reporting_dashboard'
        verbose_name = "Tableau de bord"
        verbose_name_plural = "Tableaux de bord"
        unique_together = ['company', 'code']
        ordering = ['name']

    def __str__(self):
        return self.name


class DashboardWidget(CompanyBaseModel):
    """Widget de tableau de bord."""
    TYPE_CHOICES = [
        ('kpi', 'KPI'),
        ('chart_line', 'Graphique lignes'),
        ('chart_bar', 'Graphique barres'),
        ('chart_pie', 'Graphique circulaire'),
        ('table', 'Tableau'),
        ('list', 'Liste'),
    ]

    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='widgets',
        verbose_name="Tableau de bord"
    )
    name = models.CharField(max_length=200, verbose_name="Nom")
    widget_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='kpi',
        verbose_name="Type"
    )

    report = models.ForeignKey(
        ReportDefinition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='widgets',
        verbose_name="Rapport source"
    )
    query = models.TextField(blank=True, verbose_name="Requête")
    parameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Paramètres"
    )

    position_x = models.PositiveSmallIntegerField(default=0, verbose_name="Position X")
    position_y = models.PositiveSmallIntegerField(default=0, verbose_name="Position Y")
    width = models.PositiveSmallIntegerField(default=4, verbose_name="Largeur")
    height = models.PositiveSmallIntegerField(default=3, verbose_name="Hauteur")

    refresh_interval = models.PositiveIntegerField(
        default=0,
        verbose_name="Rafraîchissement (sec)"
    )

    class Meta:
        db_table = 'reporting_widget'
        verbose_name = "Widget"
        verbose_name_plural = "Widgets"
        ordering = ['position_y', 'position_x']

    def __str__(self):
        return f"{self.dashboard.name} - {self.name}"


class SavedFilter(CompanyBaseModel):
    """Filtre sauvegardé."""
    name = models.CharField(max_length=200, verbose_name="Nom")
    report = models.ForeignKey(
        ReportDefinition,
        on_delete=models.CASCADE,
        related_name='saved_filters',
        verbose_name="Rapport"
    )
    filters = models.JSONField(
        default=dict,
        verbose_name="Filtres"
    )
    is_default = models.BooleanField(default=False, verbose_name="Par défaut")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_filters',
        verbose_name="Propriétaire"
    )

    class Meta:
        db_table = 'reporting_saved_filter'
        verbose_name = "Filtre sauvegardé"
        verbose_name_plural = "Filtres sauvegardés"
        ordering = ['name']

    def __str__(self):
        return self.name
