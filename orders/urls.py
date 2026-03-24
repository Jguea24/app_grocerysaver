"""Rutas del dominio de ordenes."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CheckoutViewSet, OrderViewSet, PaymentViewSet, ShipmentViewSet

router = DefaultRouter()
router.register('checkout', CheckoutViewSet, basename='checkout')
router.register('payments', PaymentViewSet, basename='payment')
router.register('shipments', ShipmentViewSet, basename='shipment')
router.register('orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
]
