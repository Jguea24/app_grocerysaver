from django.urls import path

from .views import (
    AdminOnlyView,
    ApiRootView,
    CategoryListView,
    LoginView,
    LogoutView,
    MeView,
    ProductListView,
    ProductPriceComparisonView,
    ProtectedRouteView,
    RegisterView,
    RoleListView,
    SocialLoginView,
    StoreListView,
    VerifyEmailView,
)

urlpatterns = [
    path('', ApiRootView.as_view(), name='api-root'),
    path('auth/roles/', RoleListView.as_view(), name='auth-roles'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/verify-email/', VerifyEmailView.as_view(), name='auth-verify-email'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/social-login/', SocialLoginView.as_view(), name='auth-social-login'),
    path('stores/', StoreListView.as_view(), name='store-list'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('compare-prices/', ProductPriceComparisonView.as_view(), name='compare-prices'),
    path('protected/', ProtectedRouteView.as_view(), name='protected-route'),
    path('protected/admin-only/', AdminOnlyView.as_view(), name='protected-admin-only'),
]
