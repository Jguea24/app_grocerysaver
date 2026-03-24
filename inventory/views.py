"""Vistas del dominio de inventario."""

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from grocerysaver.views import CartItemDetailView, CartItemListCreateView, CartView

from .models import InventoryItem
from .serializers import InventoryItemSerializer, InventoryItemWriteSerializer


class InventoryItemListCreateView(APIView):
    """Lista y crea items del inventario del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = InventoryItem.objects.select_related('product__category').prefetch_related('product__prices__store', 'product__codes').filter(user=request.user)
        return Response({'items': InventoryItemSerializer(queryset, many=True, context={'request': request}).data})

    def post(self, request):
        serializer = InventoryItemWriteSerializer(data=request.data, context={'today': timezone.localdate()})
        serializer.is_valid(raise_exception=True)

        item, created = InventoryItem.objects.update_or_create(
            user=request.user,
            product_id=serializer.validated_data['product_id'],
            expires_at=serializer.validated_data.get('expires_at'),
            defaults={'quantity': serializer.validated_data['quantity']},
        )
        item = InventoryItem.objects.select_related('product__category').prefetch_related('product__prices__store', 'product__codes').get(id=item.id)
        return Response(
            {'item': InventoryItemSerializer(item, context={'request': request}).data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class InventoryItemDetailView(APIView):
    """Actualiza o elimina un item puntual del inventario."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, item_id):
        item = InventoryItem.objects.filter(id=item_id, user=request.user).first()
        if item is None:
            return Response({'detail': 'Item de inventario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InventoryItemWriteSerializer(
            data={
                'product_id': item.product_id,
                'quantity': request.data.get('quantity', item.quantity),
                'expires_at': request.data.get('expires_at', item.expires_at),
            },
            context={'today': timezone.localdate()},
        )
        serializer.is_valid(raise_exception=True)

        item.quantity = serializer.validated_data['quantity']
        item.expires_at = serializer.validated_data.get('expires_at')
        item.save(update_fields=['quantity', 'expires_at', 'updated_at'])
        item = InventoryItem.objects.select_related('product__category').prefetch_related('product__prices__store', 'product__codes').get(id=item.id)
        return Response({'item': InventoryItemSerializer(item, context={'request': request}).data})

    def delete(self, request, item_id):
        item = InventoryItem.objects.filter(id=item_id, user=request.user).first()
        if item is None:
            return Response({'detail': 'Item de inventario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InventoryItemViewSet(viewsets.ViewSet):
    """Expone inventario con DRF routers sin romper el contrato actual."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        return InventoryItemListCreateView().get(request)

    def create(self, request):
        return InventoryItemListCreateView().post(request)

    def partial_update(self, request, pk=None):
        return InventoryItemDetailView().patch(request, item_id=pk)

    def destroy(self, request, pk=None):
        return InventoryItemDetailView().delete(request, item_id=pk)


__all__ = [
    'CartItemDetailView',
    'CartItemListCreateView',
    'CartView',
    'InventoryItemDetailView',
    'InventoryItemListCreateView',
    'InventoryItemViewSet',
]
