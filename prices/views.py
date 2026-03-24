"""Punto de entrada modular para vistas de precios."""

from grocerysaver.dataloaders import batch_load_product_qr_codes, get_request_loader
from grocerysaver.views import OfferListView, ProductPriceComparisonView, StoreListView
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PriceHistory
from .serializers import PriceHistorySerializer, ProductSerializer


class PriceHistoryListView(APIView):
    """Expone el historico de precios de un producto."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        product_id = request.query_params.get('product_id')
        product_name = (request.query_params.get('product') or '').strip()
        store_id = request.query_params.get('store_id')

        try:
            limit = min(max(int(request.query_params.get('limit', 20) or 20), 1), 100)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'El parametro limit debe ser un entero entre 1 y 100.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not product_id and not product_name:
            return Response(
                {'detail': 'Debes enviar product_id o product en query params.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = PriceHistory.objects.select_related('product__category', 'store').order_by('-captured_at')
        if product_id:
            history = queryset.filter(product_id=product_id)
        else:
            history = queryset.filter(product__name__iexact=product_name)
            if not history.exists():
                history = queryset.filter(product__name__icontains=product_name)

        if store_id:
            history = history.filter(store_id=store_id)

        first_row = history.first()
        if first_row is None:
            return Response({'detail': 'No existe historico para el producto solicitado.'}, status=status.HTTP_404_NOT_FOUND)

        total_count = history.count()
        rows = list(history[:limit])
        latest_by_store = {}
        for row in rows:
            latest_by_store.setdefault(row.store_id, row)

        qr_codes_by_product_id = get_request_loader(
            request,
            'product_qr_codes',
            batch_load_product_qr_codes,
        ).load_many([first_row.product_id])

        return Response(
            {
                'product': ProductSerializer(
                    first_row.product,
                    context={
                        'request': request,
                        'qr_codes_by_product_id': qr_codes_by_product_id,
                    },
                ).data,
                'count': total_count,
                'history': PriceHistorySerializer(rows, many=True).data,
                'latest_by_store': PriceHistorySerializer(list(latest_by_store.values()), many=True).data,
            }
        )


class StoreViewSet(viewsets.ViewSet):
    """Lista tiendas mediante router."""

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        return StoreListView().get(request)


class OfferViewSet(viewsets.ViewSet):
    """Lista ofertas mediante router."""

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        return OfferListView().get(request)


class PriceComparisonViewSet(viewsets.ViewSet):
    """Mantiene el comparador de precios sobre un router DRF."""

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        return ProductPriceComparisonView().get(request)


class PriceHistoryViewSet(viewsets.ViewSet):
    """Expone historico de precios mediante router."""

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        return PriceHistoryListView().get(request)


__all__ = [
    'OfferListView',
    'OfferViewSet',
    'PriceComparisonViewSet',
    'PriceHistoryListView',
    'PriceHistoryViewSet',
    'ProductPriceComparisonView',
    'StoreListView',
    'StoreViewSet',
]
