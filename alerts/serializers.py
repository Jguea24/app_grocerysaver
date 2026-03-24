"""Serializers del dominio de alertas."""

from rest_framework import serializers

from grocerysaver.models import ProductCodeType
from grocerysaver.serializers import ProductSerializer

from .models import Alert, AlertStatus


class AlertSerializer(serializers.ModelSerializer):
    """Representacion de lectura para alertas del usuario."""

    product = serializers.SerializerMethodField()
    inventory_item_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id',
            'type',
            'status',
            'days_remaining',
            'message',
            'product',
            'inventory_item_id',
            'created_at',
            'updated_at',
            'resolved_at',
        ]

    def get_product(self, obj):
        qr_code = obj.product.codes.filter(code_type=ProductCodeType.QR).values_list('code', flat=True).first()
        return ProductSerializer(
            obj.product,
            context={
                'request': self.context.get('request'),
                'qr_codes_by_product_id': {obj.product_id: qr_code},
            },
        ).data


class AlertStatusUpdateSerializer(serializers.Serializer):
    """Permite cambiar el estado de una alerta."""

    status = serializers.ChoiceField(choices=[AlertStatus.ACTIVE, AlertStatus.RESOLVED, AlertStatus.DISMISSED])
