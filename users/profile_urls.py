"""Rutas del dominio de perfil de usuario."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AddressViewSet, NotificationPreferenceView, RoleChangeRequestViewSet, SavingsPreferenceView

router = DefaultRouter()
router.register('profile/addresses', AddressViewSet, basename='profile-address')
router.register('profile/role-change-requests', RoleChangeRequestViewSet, basename='profile-role-change-request')

urlpatterns = [
    path('', include(router.urls)),
    path('profile/notifications/', NotificationPreferenceView.as_view(), name='profile-notification-preferences'),
    path('profile/savings-preferences/', SavingsPreferenceView.as_view(), name='profile-savings-preferences'),
]
