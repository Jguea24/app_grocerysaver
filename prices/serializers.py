"""Serializers del dominio de precios."""

from rest_framework import serializers

from grocerysaver.serializers import OfferSerializer, ProductPriceSerializer, ProductSerializer, StoreSerializer

from .models import PriceHistory


class PriceHistorySerializer(serializers.ModelSerializer):
    """Representa una observacion historica de precio."""

    store = StoreSerializer(read_only=True)

    class Meta:
        model = PriceHistory
        fields = ['id', 'store', 'price', 'captured_at', 'source']


__all__ = ['OfferSerializer', 'PriceHistorySerializer', 'ProductPriceSerializer', 'ProductSerializer', 'StoreSerializer']