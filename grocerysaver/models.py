import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class SocialProvider(models.TextChoices):
    FACEBOOK = 'facebook', 'Facebook'
    APPLE = 'apple', 'Apple'


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


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
