"""Template tags para alimentar el dashboard visual del admin."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.template import Library
from django.utils import timezone

from grocerysaver.models import Cart, CartItem, Category, Offer, Product, ProductPrice, Store
from orders.models import OrderItem, OrderStatus


register = Library()


def build_last_days_labels(days):
    """Construye etiquetas cortas para la serie diaria."""
    today = timezone.localdate()
    dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    labels = [date.strftime('%d %b') for date in dates]
    return dates, labels


def get_top_seller_label(filters):
    """Entrega el producto mas vendido segun el filtro recibido."""
    top_item = (
        OrderItem.objects.filter(order__status=OrderStatus.PLACED, **filters)
        .values('product_name')
        .annotate(total=Sum('quantity'))
        .order_by('-total', 'product_name')
        .first()
    )
    if not top_item:
        return 'Sin ventas'
    return f"{top_item['product_name']} ({top_item['total']})"



@register.simple_tag
def grocery_dashboard_data():
    """Retorna metricas y datasets para la portada personalizada del admin."""
    user_model = get_user_model()
    now = timezone.now()
    today = timezone.localdate()

    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_stores = Store.objects.count()
    total_users = user_model.objects.count()
    active_users = user_model.objects.filter(is_active=True).count()
    active_offers = Offer.objects.filter(starts_at__lte=now, ends_at__gte=now).count()
    carts_with_items = Cart.objects.filter(items__isnull=False).distinct().count()
    cart_items_total = CartItem.objects.count()
    top_seller_day = get_top_seller_label({'created_at__date': today})
    top_seller_month = get_top_seller_label({'created_at__year': today.year, 'created_at__month': today.month})
    top_seller_year = get_top_seller_label({'created_at__year': today.year})

    offer_state_counts = Offer.objects.aggregate(
        active=Count('id', filter=Q(starts_at__lte=now, ends_at__gte=now)),
        upcoming=Count('id', filter=Q(starts_at__gt=now)),
        expired=Count('id', filter=Q(ends_at__lt=now)),
    )

    top_categories = list(
        Category.objects.annotate(total_products=Count('products'))
        .order_by('-total_products', 'name')
        .values('name', 'total_products')[:6]
    )

    top_stores = list(
        Store.objects.annotate(total_prices=Count('prices'))
        .order_by('-total_prices', 'name')
        .values('name', 'total_prices')[:6]
    )

    day_values, day_labels = build_last_days_labels(7)
    products_by_day_raw = {
        row['created_at__date']: row['total']
        for row in Product.objects.filter(created_at__date__in=day_values)
        .values('created_at__date')
        .annotate(total=Count('id'))
    }
    cart_items_by_day_raw = {
        row['updated_at__date']: row['total']
        for row in CartItem.objects.filter(updated_at__date__in=day_values)
        .values('updated_at__date')
        .annotate(total=Count('id'))
    }
    products_by_day = [products_by_day_raw.get(day, 0) for day in day_values]
    cart_activity_by_day = [cart_items_by_day_raw.get(day, 0) for day in day_values]

    metrics = [
        {
            'label': 'Productos',
            'value': total_products,
            'accent': 'blue',
            'hint': 'Catalogo total publicado',
        },
        {
            'label': 'Categorias',
            'value': total_categories,
            'accent': 'green',
            'hint': 'Secciones activas del catalogo',
        },
        {
            'label': 'Tiendas',
            'value': total_stores,
            'accent': 'violet',
            'hint': 'Supermercados con precios',
        },
        {
            'label': 'Ofertas activas',
            'value': active_offers,
            'accent': 'orange',
            'hint': 'Promociones vigentes ahora',
        },
        {
            'label': 'Usuarios activos',
            'value': active_users,
            'accent': 'cyan',
            'hint': f'{total_users} usuarios registrados',
        },
        {
            'label': 'Carritos activos',
            'value': carts_with_items,
            'accent': 'teal',
            'hint': f'{cart_items_total} items en carritos',
        },
        {
            'label': 'Mas vendido (dia)',
            'value': top_seller_day,
            'accent': 'pink',
            'hint': f"Dia: {today.strftime('%d %b %Y')}",
        },
        {
            'label': 'Mas vendido (mes)',
            'value': top_seller_month,
            'accent': 'orange',
            'hint': f"Mes: {today.strftime('%b %Y')}",
        },
        {
            'label': 'Mas vendido (ano)',
            'value': top_seller_year,
            'accent': 'violet',
            'hint': f"Ano: {today.year}",
        },
    ]

    charts = {
        'offers': {
            'labels': ['Activas', 'Proximas', 'Expiradas'],
            'values': [
                offer_state_counts['active'],
                offer_state_counts['upcoming'],
                offer_state_counts['expired'],
            ],
            'colors': ['#21c55d', '#38bdf8', '#f97316'],
            'title': 'Estado de ofertas',
            'subtitle': 'Distribucion actual',
        },
        'categories': {
            'labels': [row['name'] for row in top_categories],
            'values': [row['total_products'] for row in top_categories],
            'colors': ['#4f8df7', '#24c2b2', '#f59e0b', '#e11d48', '#8b5cf6', '#14b8a6'],
            'title': 'Categorias con mas productos',
            'subtitle': 'Top 6',
        },
        'stores': {
            'labels': [row['name'] for row in top_stores],
            'values': [row['total_prices'] for row in top_stores],
            'colors': ['#22c55e', '#06b6d4', '#f97316', '#ef4444', '#8b5cf6', '#f43f5e'],
            'title': 'Tiendas con mas precios',
            'subtitle': 'Cobertura del catalogo',
        },
        'activity': {
            'labels': day_labels,
            'series': [
                {
                    'label': 'Productos nuevos',
                    'values': products_by_day,
                    'stroke': '#38bdf8',
                    'fill': 'rgba(56, 189, 248, 0.18)',
                },
                {
                    'label': 'Actividad carrito',
                    'values': cart_activity_by_day,
                    'stroke': '#22c55e',
                    'fill': 'rgba(34, 197, 94, 0.12)',
                },
            ],
            'title': 'Actividad ultimos 7 dias',
            'subtitle': 'Movimiento reciente',
        },
    }

    return {
        'metrics': metrics,
        'charts': charts,
    }

