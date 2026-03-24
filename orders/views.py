"""Vistas del dominio de ordenes."""

from rest_framework import permissions, viewsets
from rest_framework.response import Response

from .models import CheckoutSession, Order, Payment, Shipment
from .serializers import CheckoutCreateSerializer, CheckoutSessionSerializer, CheckoutUpdateSerializer, OrderCreateSerializer, OrderSerializer, PaymentCreateSerializer, PaymentSerializer, ShipmentSerializer, ShipmentUpdateSerializer
from .services import UNSET, OrderCreationError, create_checkout_from_cart, create_order_from_cart, process_checkout_payment, update_checkout_session, update_shipment_status


class CheckoutViewSet(viewsets.ViewSet):
    """Lista, detalla, crea y actualiza sesiones de checkout del usuario."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        queryset = CheckoutSession.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')
        return Response({'checkouts': CheckoutSessionSerializer(queryset, many=True).data})

    def retrieve(self, request, pk=None):
        checkout = CheckoutSession.objects.filter(user=request.user).prefetch_related('items').filter(pk=pk).first()
        if checkout is None:
            return Response({'detail': 'Checkout no encontrado.'}, status=404)
        return Response({'checkout': CheckoutSessionSerializer(checkout).data})

    def create(self, request):
        serializer = CheckoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            checkout = create_checkout_from_cart(user=request.user, notes=serializer.validated_data.get('notes', ''))
        except OrderCreationError as exc:
            return Response({'detail': exc.detail}, status=exc.status_code)

        return Response({'message': 'Checkout creado desde el carrito. Falta seleccionar direccion y pago.', 'checkout': CheckoutSessionSerializer(checkout).data}, status=201)

    def partial_update(self, request, pk=None):
        checkout = CheckoutSession.objects.filter(user=request.user).prefetch_related('items').filter(pk=pk).first()
        if checkout is None:
            return Response({'detail': 'Checkout no encontrado.'}, status=404)

        serializer = CheckoutUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            checkout = update_checkout_session(
                user=request.user,
                checkout=checkout,
                address_id=serializer.validated_data.get('address_id'),
                notes=serializer.validated_data.get('notes') if 'notes' in serializer.validated_data else None,
            )
        except OrderCreationError as exc:
            return Response({'detail': exc.detail}, status=exc.status_code)

        return Response({'checkout': CheckoutSessionSerializer(checkout).data})


class PaymentViewSet(viewsets.ViewSet):
    """Lista, detalla y procesa pagos sobre sesiones de checkout."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        queryset = Payment.objects.filter(user=request.user).order_by('-created_at')
        return Response({'payments': PaymentSerializer(queryset, many=True).data})

    def retrieve(self, request, pk=None):
        payment = Payment.objects.filter(user=request.user).filter(pk=pk).first()
        if payment is None:
            return Response({'detail': 'Pago no encontrado.'}, status=404)
        return Response({'payment': PaymentSerializer(payment).data})

    def create(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = process_checkout_payment(
                user=request.user,
                checkout_id=serializer.validated_data['checkout_id'],
                method=serializer.validated_data['method'],
                provider=serializer.validated_data.get('provider', 'sandbox'),
                simulate_failure=serializer.validated_data.get('simulate_failure', False),
            )
        except OrderCreationError as exc:
            return Response({'detail': exc.detail}, status=exc.status_code)

        shipment = getattr(payment.order, 'shipment', None) if payment.order_id else None
        return Response(
            {
                'message': 'Pago procesado.' if payment.status == 'succeeded' else 'Pago rechazado.',
                'payment': PaymentSerializer(payment).data,
                'order': OrderSerializer(payment.order).data if payment.order_id else None,
                'shipment': ShipmentSerializer(shipment).data if shipment is not None else None,
            },
            status=201,
        )


class ShipmentViewSet(viewsets.ViewSet):
    """Lista, detalla y actualiza envios del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        queryset = Shipment.objects.filter(user=request.user).select_related('order').order_by('-created_at')
        return Response({'shipments': ShipmentSerializer(queryset, many=True).data})

    def retrieve(self, request, pk=None):
        shipment = Shipment.objects.filter(user=request.user).select_related('order').filter(pk=pk).first()
        if shipment is None:
            return Response({'detail': 'Envio no encontrado.'}, status=404)
        return Response({'shipment': ShipmentSerializer(shipment).data})

    def partial_update(self, request, pk=None):
        shipment = Shipment.objects.filter(user=request.user).select_related('order').filter(pk=pk).first()
        if shipment is None:
            return Response({'detail': 'Envio no encontrado.'}, status=404)

        serializer = ShipmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            shipment = update_shipment_status(
                user=request.user,
                shipment=shipment,
                status_value=serializer.validated_data['status'] if 'status' in serializer.validated_data else UNSET,
                carrier=serializer.validated_data['carrier'] if 'carrier' in serializer.validated_data else UNSET,
                tracking_number=serializer.validated_data['tracking_number'] if 'tracking_number' in serializer.validated_data else UNSET,
                notes=serializer.validated_data['notes'] if 'notes' in serializer.validated_data else UNSET,
                estimated_delivery_at=serializer.validated_data['estimated_delivery_at'] if 'estimated_delivery_at' in serializer.validated_data else UNSET,
            )
        except OrderCreationError as exc:
            return Response({'detail': exc.detail}, status=exc.status_code)

        return Response({'shipment': ShipmentSerializer(shipment).data})


class OrderViewSet(viewsets.ViewSet):
    """Lista, detalla y crea ordenes del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        queryset = Order.objects.filter(user=request.user).select_related('shipment').prefetch_related('items').order_by('-created_at')
        return Response({'orders': OrderSerializer(queryset, many=True).data})

    def retrieve(self, request, pk=None):
        order = Order.objects.filter(user=request.user).select_related('shipment').prefetch_related('items').filter(pk=pk).first()
        if order is None:
            return Response({'detail': 'Orden no encontrada.'}, status=404)
        return Response({'order': OrderSerializer(order).data})

    def create(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = create_order_from_cart(
                user=request.user,
                address_id=serializer.validated_data['address_id'],
                notes=serializer.validated_data.get('notes', ''),
            )
        except OrderCreationError as exc:
            return Response({'detail': exc.detail}, status=exc.status_code)

        return Response({'message': 'Orden creada desde el carrito. Queda pendiente de pago.', 'order': OrderSerializer(order).data}, status=201)
