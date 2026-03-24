"""Punto de entrada modular para vistas de usuarios y autenticacion."""

from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from grocerysaver.views import (
    AddressDetailView,
    AddressListCreateView,
    LoginView,
    LogoutView,
    MeView,
    NotificationPreferenceView,
    ProfileAvatarView,
    RegisterView,
    RoleChangeRequestListCreateView,
    RoleListView,
    SocialLoginView,
    VerifyEmailView,
    build_user_response,
)

from .models import UserSavingsPreference
from .serializers import UserSavingsPreferenceSerializer


class AddressViewSet(viewsets.ViewSet):
    """Expone direcciones del perfil usando routers DRF."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        return AddressListCreateView().get(request)

    def create(self, request):
        return AddressListCreateView().post(request)

    def partial_update(self, request, pk=None):
        return AddressDetailView().patch(request, address_id=pk)

    def destroy(self, request, pk=None):
        return AddressDetailView().delete(request, address_id=pk)


class RoleChangeRequestViewSet(viewsets.ViewSet):
    """Expone solicitudes de cambio de rol con router."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        return RoleChangeRequestListCreateView().get(request)

    def create(self, request):
        return RoleChangeRequestListCreateView().post(request)


class SavingsPreferenceView(APIView):
    """Expone preferencias de ahorro del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        preference, _ = UserSavingsPreference.objects.get_or_create(user=request.user)
        return Response(
            {
                'savings_preferences': UserSavingsPreferenceSerializer(preference).data,
                'user': build_user_response(request.user, request=request),
            }
        )

    def patch(self, request):
        preference, _ = UserSavingsPreference.objects.get_or_create(user=request.user)
        serializer = UserSavingsPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'savings_preferences': serializer.data,
                'user': build_user_response(request.user, request=request),
            }
        )


__all__ = [
    'AddressDetailView',
    'AddressListCreateView',
    'AddressViewSet',
    'LoginView',
    'LogoutView',
    'MeView',
    'NotificationPreferenceView',
    'ProfileAvatarView',
    'RegisterView',
    'RoleChangeRequestListCreateView',
    'RoleChangeRequestViewSet',
    'RoleListView',
    'SavingsPreferenceView',
    'SocialLoginView',
    'VerifyEmailView',
]
