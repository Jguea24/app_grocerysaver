"""Rutas del dominio de autenticacion."""

from django.urls import path

from .views import LoginView, LogoutView, MeView, ProfileAvatarView, RegisterView, RoleListView, SocialLoginView, VerifyEmailView

urlpatterns = [
    path('roles/', RoleListView.as_view(), name='auth-roles'),
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('verify-email/', VerifyEmailView.as_view(), name='auth-verify-email'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('me/avatar/', ProfileAvatarView.as_view(), name='auth-me-avatar'),
    path('social-login/', SocialLoginView.as_view(), name='auth-social-login'),
]