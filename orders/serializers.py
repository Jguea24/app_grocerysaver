"""Serializers del dominio de ordenes."""

from rest_framework import serializers

from .models import CheckoutItem, CheckoutSession, Order, OrderItem, Payment, PaymentMethod, Shipment, ShipmentStatus


class CheckoutCreateSerializer(serializers.Serializer):
    """Payload minimo para crear una sesion de checkout desde el carrito."""

    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)


class CheckoutUpdateSerializer(serializers.Serializer):
    """Permite adjuntar direccion y notas a un checkout abierto."""

    address_id = serializers.IntegerField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Debes enviar address_id, notes o ambos.')
        return attrs


class CheckoutItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckoutItem
        fields = ['id', 'product_id', 'store_id', 'product_name', 'product_brand', 'category_name', 'store_name', 'quantity', 'unit_price', 'line_total', 'created_at']


class CheckoutSessionSerializer(serializers.ModelSerializer):
    items = CheckoutItemSerializer(many=True, read_only=True)
    address_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = CheckoutSession
        fields = ['id', 'checkout_number', 'status', 'address_id', 'address_snapshot', 'notes', 'total_items', 'subtotal', 'delivery_fee', 'total', 'items', 'created_at', 'updated_at']

    def get_address_snapshot(self, obj):
        return {
            'label': obj.address_label,
            'contact_name': obj.contact_name,
            'phone': obj.phone,
            'line1': obj.line1,
            'line2': obj.line2,
            'city': obj.city,
        }


class OrderCreateSerializer(serializers.Serializer):
    address_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_id', 'store_id', 'product_name', 'product_brand', 'category_name', 'store_name', 'quantity', 'unit_price', 'line_total', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    address_snapshot = serializers.SerializerMethodField()
    shipment_id = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'status', 'checkout_id', 'shipment_id', 'address_id', 'address_snapshot', 'notes', 'total_items', 'subtotal', 'delivery_fee', 'total', 'items', 'created_at', 'updated_at']

    def get_address_snapshot(self, obj):
        return {
            'label': obj.address_label,
            'contact_name': obj.contact_name,
            'phone': obj.phone,
            'line1': obj.line1,
            'line2': obj.line2,
            'city': obj.city,
        }

    def get_shipment_id(self, obj):
        shipment = getattr(obj, 'shipment', None)
        return shipment.id if shipment is not None else None


class PaymentCreateSerializer(serializers.Serializer):
    """Payload para procesar un pago sobre un checkout listo."""

    checkout_id = serializers.IntegerField()
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    provider = serializers.CharField(required=False, allow_blank=True, max_length=50)
    simulate_failure = serializers.BooleanField(required=False, default=False)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'payment_number', 'checkout_id', 'order_id', 'method', 'provider', 'status', 'amount', 'currency', 'provider_reference', 'failure_reason', 'created_at', 'updated_at', 'paid_at']


class ShipmentUpdateSerializer(serializers.Serializer):
    """Permite avanzar un envio y registrar metadatos logisticos."""

    status = serializers.ChoiceField(choices=ShipmentStatus.choices, required=False)
    carrier = serializers.CharField(required=False, allow_blank=True, max_length=80)
    tracking_number = serializers.CharField(required=False, allow_blank=True, max_length=120)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)
    estimated_delivery_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Debes enviar al menos un campo para actualizar el envio.')
        return attrs


class ShipmentSerializer(serializers.ModelSerializer):
    address_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = ['id', 'shipment_number', 'order_id', 'status', 'carrier', 'tracking_number', 'address_snapshot', 'notes', 'estimated_delivery_at', 'shipped_at', 'delivered_at', 'created_at', 'updated_at']

    def get_address_snapshot(self, obj):
        return {
            'contact_name': obj.contact_name,
            'phone': obj.phone,
            'line1': obj.line1,
            'line2': obj.line2,
            'city': obj.city,
        }
