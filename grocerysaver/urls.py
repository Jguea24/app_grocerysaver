"""Rutas publicas y autenticadas expuestas por la API GrocerySaver."""

from django.urls import include, path

from .views import (
    ActiveRaffleListView,
    AdminOnlyView,
    ApiDocsView,
    ApiRootView,
    ApiSchemaView,
    DeviceSensorReadingCreateView,
    JobDetailView,
    ProductExportJobCreateView,
    ProtectedRouteView,
    WeatherView,
)

urlpatterns = [
    path('', ApiRootView.as_view(), name='api-root'),
    path('docs/', ApiDocsView.as_view(), name='api-docs'),
    path('schema/', ApiSchemaView.as_view(), name='api-schema'),
    path('auth/', include('users.urls')),
    path('', include('users.profile_urls')),
    path('', include('inventory.urls')),
    path('', include('products.urls')),
    path('', include('prices.urls')),
    path('', include('orders.urls')),
    path('', include('alerts.urls')),
    path('raffles/active/', ActiveRaffleListView.as_view(), name='raffle-active-list'),
    path('device-sensors/', DeviceSensorReadingCreateView.as_view(), name='device-sensor-reading-create'),
    path('jobs/export-products/', ProductExportJobCreateView.as_view(), name='job-export-products'),
    path('jobs/<uuid:job_id>/', JobDetailView.as_view(), name='job-detail'),
    path('weather/', WeatherView.as_view(), name='weather'),
    path('protected/', ProtectedRouteView.as_view(), name='protected-route'),
    path('protected/admin-only/', AdminOnlyView.as_view(), name='protected-admin-only'),
]


