"""Punto de entrada modular para vistas del catalogo."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from grocerysaver.dataloaders import batch_load_product_qr_codes, get_request_loader
from grocerysaver.models import Product, ProductPrice, Store
from grocerysaver.serializers import ProductPriceSerializer
from grocerysaver.views import CategoryListView, ProductListView, ProductScanView

from .models import ProductPurchase
from .serializers import (
    ProductPurchaseSerializer,
    ProductPurchaseWriteSerializer,
    ProductSerializer,
)


class CategoryViewSet(viewsets.ViewSet):
    """Lista categorias usando DRF routers."""

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        return CategoryListView().get(request)


class ProductViewSet(viewsets.ViewSet):
    """Expone catalogo, detalle y escaneo de productos mediante router."""

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        barcode = (request.query_params.get('barcode') or '').strip()
        if not barcode:
            return ProductListView().get(request)

        queryset = Product.objects.select_related('category').prefetch_related('prices__store', 'codes')
        products = list(queryset.filter(codes__code=barcode).distinct())
        qr_codes_by_product_id = get_request_loader(
            request,
            'product_qr_codes',
            batch_load_product_qr_codes,
        ).load_many([product.id for product in products])

        payload = []
        for product in products:
            prices = list(product.prices.all())
            best_option = prices[0] if prices else None
            product_data = ProductSerializer(
                product,
                context={
                    'request': request,
                    'qr_codes_by_product_id': qr_codes_by_product_id,
                },
            ).data
            product_data['prices'] = ProductPriceSerializer(prices, many=True).data
            product_data['stores_available'] = len(prices)
            product_data['best_option'] = (
                {
                    'store': best_option.store.name,
                    'price': str(best_option.price),
                }
                if best_option
                else None
            )
            product_data['best_price'] = str(best_option.price) if best_option else None
            payload.append(product_data)

        return Response({'products': payload})

    def retrieve(self, request, pk=None):
        product = (
            Product.objects.select_related('category')
            .prefetch_related('prices__store', 'codes', 'purchase_history__store')
            .filter(pk=pk)
            .first()
        )
        if product is None:
            return Response({'detail': 'Producto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        prices = list(product.prices.all())
        best_option = prices[0] if prices else None
        estimated_price = None
        if prices:
            estimated_price = sum((price.price for price in prices), Decimal('0.00')) / len(prices)

        qr_codes_by_product_id = get_request_loader(
            request,
            'product_qr_codes',
            batch_load_product_qr_codes,
        ).load_many([product.id])

        product_data = ProductSerializer(
            product,
            context={
                'request': request,
                'qr_codes_by_product_id': qr_codes_by_product_id,
            },
        ).data
        product_data['prices'] = ProductPriceSerializer(prices, many=True).data
        product_data['stores_available'] = len(prices)
        product_data['best_option'] = (
            {
                'store': best_option.store.name,
                'price': str(best_option.price),
            }
            if best_option
            else None
        )
        product_data['best_price'] = str(best_option.price) if best_option else None
        product_data['estimated_price'] = str(estimated_price.quantize(Decimal('0.01'))) if estimated_price is not None else None

        purchase_history = ProductPurchase.objects.select_related('store').filter(product=product)
        if request.user.is_authenticated:
            purchase_history = purchase_history.filter(user=request.user)
        else:
            purchase_history = purchase_history.none()

        purchases = list(purchase_history[:10])
        purchase_count = purchase_history.count()
        average_purchase_price = None
        if purchases:
            average_purchase_price = sum((purchase.unit_price for purchase in purchases), Decimal('0.00')) / len(purchases)

        alternatives = []
        if best_option is not None:
            candidates = (
                Product.objects.select_related('category')
                .prefetch_related('prices__store')
                .filter(category_id=product.category_id)
                .exclude(id=product.id)
            )
            for candidate in candidates:
                candidate_prices = list(candidate.prices.all())
                if not candidate_prices:
                    continue
                candidate_best = candidate_prices[0]
                if candidate_best.price >= best_option.price:
                    continue
                alternatives.append(
                    {
                        'id': candidate.id,
                        'name': candidate.name,
                        'brand': candidate.brand,
                        'best_price': str(candidate_best.price),
                        'store': candidate_best.store.name,
                        'savings_vs_selected': str((best_option.price - candidate_best.price).quantize(Decimal('0.01'))),
                    }
                )
            alternatives.sort(key=lambda row: Decimal(row['best_price']))

        return Response(
            {
                'product': product_data,
                'purchase_history': ProductPurchaseSerializer(purchases, many=True).data,
                'purchase_summary': {
                    'purchases_count': purchase_count,
                    'average_unit_price': str(average_purchase_price.quantize(Decimal('0.01'))) if average_purchase_price is not None else None,
                    'last_purchase_at': purchases[0].purchased_at.isoformat() if purchases else None,
                },
                'cheaper_alternatives': alternatives[:5],
            }
        )

    @action(detail=False, methods=['post'], url_path='scan', permission_classes=[permissions.AllowAny])
    def scan(self, request):
        return ProductScanView().post(request)


class ProductPurchaseViewSet(viewsets.ViewSet):
    """Permite registrar y consultar historial de compras del usuario."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        queryset = ProductPurchase.objects.select_related('product__category', 'store').filter(user=request.user)
        product_id = request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return Response({'purchases': ProductPurchaseSerializer(queryset, many=True).data})

    def create(self, request):
        serializer = ProductPurchaseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = Product.objects.filter(id=serializer.validated_data['product_id']).first()
        if product is None:
            return Response({'detail': 'Producto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        store = None
        store_id = serializer.validated_data.get('store_id')
        if store_id is not None:
            store = Store.objects.filter(id=store_id).first()
            if store is None:
                return Response({'detail': 'Tienda no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        purchase = ProductPurchase.objects.create(
            user=request.user,
            product=product,
            store=store,
            quantity=serializer.validated_data['quantity'],
            unit_price=serializer.validated_data['unit_price'],
            purchased_at=serializer.validated_data.get('purchased_at', timezone.now()),
            notes=serializer.validated_data.get('notes', ''),
            source=serializer.validated_data.get('source', 'manual') or 'manual',
        )
        return Response({'purchase': ProductPurchaseSerializer(purchase).data}, status=status.HTTP_201_CREATED)


__all__ = [
    'CategoryListView',
    'CategoryViewSet',
    'ProductListView',
    'ProductPurchaseViewSet',
    'ProductScanView',
    'ProductViewSet',
]
