"""Serializers del dominio de inventario."""

from rest_framework import serializers

from grocerysaver.models import Product, ProductCodeType
from grocerysaver.serializers import (
    CartItemSerializer,
    CartItemUpdateSerializer,
    CartItemUpsertSerializer,
    CartSerializer,
    ProductPriceSerializer,
    ProductSerializer,
)

from .models import InventoryItem


class InventoryItemSerializer(serializers.ModelSerializer):
    """Representacion de lectura para un item del inventario."""

    product = serializers.SerializerMethodField()
    best_price = serializers.SerializerMethodField()
    best_option = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = [
            'id',
            'product',
            'quantity',
            'expires_at',
            'days_until_expiry',
            'is_expired',
            'best_price',
            'best_option',
            'created_at',
            'updated_at',
        ]

    def _get_best_price_row(self, obj):
        prices = list(obj.product.prices.all())
        if not prices:
            return None
        return prices[0]

    def get_product(self, obj):
        qr_code = obj.product.codes.filter(code_type=ProductCodeType.QR).values_list('code', flat=True).first()
        return ProductSerializer(
            obj.product,
            context={
                'request': self.context.get('request'),
                'qr_codes_by_product_id': {obj.product_id: qr_code},
            },
        ).data

    def get_best_price(self, obj):
        price_row = self._get_best_price_row(obj)
        return str(price_row.price) if price_row is not None else None

    def get_best_option(self, obj):
        price_row = self._get_best_price_row(obj)
        if price_row is None:
            return None
        return ProductPriceSerializer(price_row).data

    def get_days_until_expiry(self, obj):
        return obj.days_until_expiry

    def get_is_expired(self, obj):
        return obj.is_expired


class InventoryItemWriteSerializer(serializers.Serializer):
    """Valida altas y cambios en el inventario del usuario."""

    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    expires_at = serializers.DateField(required=False, allow_null=True)

    def validate_product_id(self, value):
        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError('Producto no encontrado.')
        return value

    def validate(self, attrs):
        expires_at = attrs.get('expires_at')
        if expires_at is not None and expires_at < self.context['today']:
            raise serializers.ValidationError({'expires_at': 'La fecha de caducidad no puede estar en el pasado.'})
        return attrs
