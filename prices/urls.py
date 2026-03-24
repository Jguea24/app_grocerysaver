"""Rutas del dominio de precios."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OfferViewSet, PriceComparisonViewSet, PriceHistoryViewSet, StoreViewSet

router = DefaultRouter()
router.register('stores', StoreViewSet, basename='store')
router.register('offers', OfferViewSet, basename='offer')
router.register('compare-prices', PriceComparisonViewSet, basename='compare-prices')
router.register('prices/history', PriceHistoryViewSet, basename='price-history')

urlpatterns = [
    path('', include(router.urls)),
]
