"""Serializers del dominio de usuarios."""

from rest_framework import serializers

from grocerysaver.serializers import (
    AddressSerializer,
    LoginSerializer,
    LogoutSerializer,
    NotificationPreferenceSerializer,
    ProfileAvatarSerializer,
    RegisterSerializer,
    RoleChangeRequestCreateSerializer,
    RoleChangeRequestSerializer,
    SocialLoginSerializer,
    VerifyEmailSerializer,
)

from .models import UserSavingsPreference


class UserSavingsPreferenceSerializer(serializers.ModelSerializer):
    """Expone y actualiza preferencias de ahorro del usuario."""

    class Meta:
        model = UserSavingsPreference
        fields = [
            'preferred_budget',
            'savings_target_percentage',
            'prefer_discounted_products',
            'allow_generic_brands',
            'compare_all_stores',
            'updated_at',
        ]
        read_only_fields = ['updated_at']


__all__ = [
    'AddressSerializer',
    'LoginSerializer',
    'LogoutSerializer',
    'NotificationPreferenceSerializer',
    'ProfileAvatarSerializer',
    'RegisterSerializer',
    'RoleChangeRequestCreateSerializer',
    'RoleChangeRequestSerializer',
    'SocialLoginSerializer',
    'UserSavingsPreferenceSerializer',
    'VerifyEmailSerializer',
]
