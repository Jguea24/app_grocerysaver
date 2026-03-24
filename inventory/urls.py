"""Rutas del dominio de inventario temporal."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CartItemDetailView, CartItemListCreateView, CartView, InventoryItemViewSet

router = DefaultRouter()
router.register('inventory/items', InventoryItemViewSet, basename='inventory-item')

urlpatterns = [
    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/items/', CartItemListCreateView.as_view(), name='cart-item-list-create'),
    path('cart/items/<int:item_id>/', CartItemDetailView.as_view(), name='cart-item-detail'),
    path('', include(router.urls)),
]
