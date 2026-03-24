"""Serializers del dominio de productos."""

from django.utils import timezone
from rest_framework import serializers

from grocerysaver.serializers import CategorySerializer, ProductCodeSerializer, ProductScanSerializer, ProductSerializer, StoreSerializer

from .models import ProductPurchase


class ProductPurchaseSerializer(serializers.ModelSerializer):
    """Representa una compra historica ya registrada."""

    store = StoreSerializer(read_only=True)

    class Meta:
        model = ProductPurchase
        fields = ['id', 'store', 'quantity', 'unit_price', 'purchased_at', 'notes', 'source']


class ProductPurchaseWriteSerializer(serializers.Serializer):
    """Valida la creacion manual de compras historicas."""

    product_id = serializers.IntegerField()
    store_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, default=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    purchased_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)
    source = serializers.CharField(required=False, allow_blank=True, max_length=40)

    def validate_purchased_at(self, value):
        if value > timezone.now():
            raise serializers.ValidationError('La fecha de compra no puede ser futura.')
        return value


__all__ = [
    'CategorySerializer',
    'ProductCodeSerializer',
    'ProductPurchaseSerializer',
    'ProductPurchaseWriteSerializer',
    'ProductScanSerializer',
    'ProductSerializer',
    'StoreSerializer',
]
