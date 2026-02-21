import uuid
from datetime import timedelta

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SocialProvider(models.TextChoices):
    FACEBOOK = 'facebook', 'Facebook'
    APPLE = 'apple', 'Apple'


class RoleChangeRequestStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Store(models.Model):
    name = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Category(models.Model):
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


class ProductPrice(models.Model):
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


class EmailVerificationToken(models.Model):
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
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f'EmailVerificationToken(user={self.user_id}, used={self.is_used})'


class SocialAccount(models.Model):
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
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starts_at']

    @property
    def is_active(self):
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at

    def __str__(self):
        return self.title


class RoleChangeRequest(models.Model):
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
