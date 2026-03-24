"""Vistas del dominio de alertas."""

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Alert, AlertStatus
from .serializers import AlertSerializer, AlertStatusUpdateSerializer


class AlertListView(APIView):
    """Lista alertas del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        status_param = (request.query_params.get('status') or '').strip().lower()
        queryset = Alert.objects.select_related('product', 'inventory_item').filter(user=request.user)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return Response({'alerts': AlertSerializer(queryset, many=True, context={'request': request}).data})


class AlertDetailView(APIView):
    """Permite cambiar el estado de una alerta existente."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, alert_id):
        alert = Alert.objects.select_related('product', 'inventory_item').filter(id=alert_id, user=request.user).first()
        if alert is None:
            return Response({'detail': 'Alerta no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AlertStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        alert.status = serializer.validated_data['status']
        if alert.status in {AlertStatus.RESOLVED, AlertStatus.DISMISSED}:
            alert.resolved_at = timezone.now()
        else:
            alert.resolved_at = None
        alert.save(update_fields=['status', 'resolved_at', 'updated_at'])
        return Response({'alert': AlertSerializer(alert, context={'request': request}).data})


class AlertViewSet(viewsets.ViewSet):
    """Expone alertas por router conservando la respuesta actual."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        return AlertListView().get(request)

    def partial_update(self, request, pk=None):
        return AlertDetailView().patch(request, alert_id=pk)


__all__ = ['AlertDetailView', 'AlertListView', 'AlertViewSet']
