"""Modelos de dominio para usuarios, catalogo, clima y jobs del sistema."""

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class SocialProvider(models.TextChoices):
    """Proveedores soportados para login social."""

    FACEBOOK = 'facebook', 'Facebook'
    APPLE = 'apple', 'Apple'


class RoleChangeRequestStatus(models.TextChoices):
    """Estados posibles de una solicitud de cambio de rol."""

    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class ProductCodeType(models.TextChoices):
    """Tipos de codigos asociados a un producto."""

    BARCODE = 'barcode', 'Barcode'
    QR = 'qr', 'QR'


class JobStatus(models.TextChoices):
    """Estados de ciclo de vida de un trabajo en background."""

    QUEUED = 'queued', 'Queued'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class JobType(models.TextChoices):
    """Tipos de trabajos asincronos soportados por la cola."""

    EXPORT_PRODUCTS_CSV = 'export_products_csv', 'Export products CSV'


class Role(models.Model):
    """Catalogo de roles de usuario dentro de la aplicacion."""

    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Store(models.Model):
    """Tienda o supermercado que publica precios y ofertas."""

    name = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Category(models.Model):
    """Categoria principal del catalogo de productos."""

    name = models.CharField(max_length=80, unique=True)
    image = models.FileField(
        upload_to='categories/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Producto base sobre el que se comparan precios y ofertas."""

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    name = models.CharField(max_length=120)
    brand = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True, default='')
    image = models.FileField(
        upload_to='products/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['category', 'name', 'brand'], name='uniq_product_by_category_name_brand'),
        ]
        ordering = ['name']

    def __str__(self):
        brand_label = f' ({self.brand})' if self.brand else ''
        return f'{self.name}{brand_label}'


class ProductCode(models.Model):
    """Codigo fisico asociado a un producto, ya sea barcode o QR."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='codes')
    code = models.CharField(max_length=120, unique=True)
    code_type = models.CharField(max_length=20, choices=ProductCodeType.choices, default=ProductCodeType.BARCODE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code_type}:{self.code}'


class ProductPrice(models.Model):
    """Precio de un producto en una tienda especifica."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prices')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='prices')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['product', 'store'], name='uniq_price_per_product_store'),
        ]
        ordering = ['price']

    def __str__(self):
        return f'{self.product} - {self.store}: {self.price}'


class Offer(models.Model):
    """Oferta temporal publicada por una tienda para un producto."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='offers')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='offers')
    normal_price = models.DecimalField(max_digits=10, decimal_places=2)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['offer_price', '-starts_at']
        constraints = [
            models.CheckConstraint(condition=Q(offer_price__lte=F('normal_price')), name='offer_price_lte_normal_price'),
            models.CheckConstraint(condition=Q(ends_at__gte=F('starts_at')), name='offer_ends_after_start'),
        ]

    @property
    def is_active(self):
        """Indica si la oferta esta activa al momento actual."""
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at

    @property
    def savings(self):
        """Calcula el ahorro nominal frente al precio normal."""
        return self.normal_price - self.offer_price

    def __str__(self):
        return f'{self.product} - {self.store}: {self.offer_price}'


class EmailVerificationToken(models.Model):
    """Token de un solo uso para activar cuentas por correo."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_verification_token',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create_for_user(cls, user, ttl_hours):
        """Genera o reemplaza el token vigente de un usuario."""
        expires_at = timezone.now() + timedelta(hours=ttl_hours)
        verification, _ = cls.objects.update_or_create(
            user=user,
            defaults={
                'token': uuid.uuid4(),
                'is_used': False,
                'expires_at': expires_at,
            },
        )
        return verification

    @property
    def is_expired(self):
        """Evalua si el token ya sobrepaso su fecha de expiracion."""
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f'EmailVerificationToken(user={self.user_id}, used={self.is_used})'


class SocialAccount(models.Model):
    """Relacion entre un usuario local y una cuenta externa."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='social_accounts',
    )
    provider = models.CharField(max_length=20, choices=SocialProvider.choices)
    provider_user_id = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'provider_user_id'],
                name='uniq_provider_user_id',
            ),
            models.UniqueConstraint(
                fields=['user', 'provider'],
                name='uniq_user_provider',
            ),
        ]

    def __str__(self):
        return f'{self.provider}:{self.provider_user_id}'


class UserProfile(models.Model):
    """Metadatos de perfil extendido para el usuario autenticado."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='profiles',
        null=True,
        blank=True,
    )
    address = models.CharField(max_length=255)
    birth_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'UserProfile(user={self.user_id})'


class Address(models.Model):
    """Direcciones guardadas por un usuario para futuras compras."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
    )
    label = models.CharField(max_length=50, blank=True)
    contact_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(is_default=True),
                name='uniq_default_address_per_user',
            ),
        ]

    def __str__(self):
        return f'Address(user={self.user_id}, city={self.city})'


class NotificationPreference(models.Model):
    """Preferencias de notificacion del usuario."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
    )
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'NotificationPreference(user={self.user_id})'


class Raffle(models.Model):
    """Rifa activa o historica ofrecida por la plataforma."""

    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starts_at']

    @property
    def is_active(self):
        """Indica si la rifa esta activa al momento actual."""
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at

    def __str__(self):
        return self.title


class RoleChangeRequest(models.Model):
    """Solicitud de cambio de rol enviada por un usuario."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='role_change_requests',
    )
    current_role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='current_role_change_requests',
        null=True,
        blank=True,
    )
    requested_role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='requested_role_change_requests',
    )
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=RoleChangeRequestStatus.choices,
        default=RoleChangeRequestStatus.PENDING,
    )
    admin_notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(status=RoleChangeRequestStatus.PENDING),
                name='uniq_pending_role_change_per_user',
            ),
        ]

    def __str__(self):
        return f'RoleChangeRequest(user={self.user_id}, status={self.status})'


class BackgroundJob(models.Model):
    """Trabajo asincrono persistido y procesado por un worker."""

    job_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    job_type = models.CharField(max_length=50, choices=JobType.choices)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.QUEUED)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='background_jobs',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['job_type', 'created_at']),
        ]

    def __str__(self):
        return f'BackgroundJob(job_id={self.job_id}, status={self.status})'
