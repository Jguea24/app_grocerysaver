"""Modelos del dominio de usuarios."""

from django.conf import settings
from django.db import models

from grocerysaver.models import Address, NotificationPreference, Role, RoleChangeRequest, SocialAccount, UserProfile


class UserSavingsPreference(models.Model):
    """Preferencias de ahorro del usuario para recomendaciones y alertas."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='savings_preference',
    )
    preferred_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    savings_target_percentage = models.PositiveIntegerField(default=10)
    prefer_discounted_products = models.BooleanField(default=True)
    allow_generic_brands = models.BooleanField(default=True)
    compare_all_stores = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User savings preference'
        verbose_name_plural = 'User savings preferences'

    def __str__(self):
        return f'UserSavingsPreference(user={self.user_id})'


__all__ = [
    'Address',
    'NotificationPreference',
    'Role',
    'RoleChangeRequest',
    'SocialAccount',
    'UserSavingsPreference',
    'UserProfile',
]
