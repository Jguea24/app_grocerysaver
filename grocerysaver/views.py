"""Vistas HTTP de la API GrocerySaver."""

import json
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone
from rest_framework import generics, permissions, renderers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from prices.serializers import PriceHistorySerializer
from inventory.services import seed_demo_expiring_inventory_for_user

from .cache_utils import (
    CACHE_NS_CATEGORIES,
    CACHE_NS_COMPARE_PRICES,
    CACHE_NS_OFFERS,
    CACHE_NS_PRODUCTS,
    CACHE_NS_RAFFLES,
    CACHE_NS_ROLES,
    CACHE_NS_STORES,
    CACHE_NS_WEATHER,
    CATALOG_CACHE_TTL,
    RAFFLE_CACHE_TTL,
    WEATHER_CACHE_TTL,
    get_cached_payload,
)
from .dataloaders import batch_load_product_qr_codes, get_request_loader
from .job_queue import enqueue_export_products_job
from .models import (
    Address,
    BackgroundJob,
    Cart,
    CartItem,
    Category,
    EmailVerificationToken,
    JobStatus,
    NotificationPreference,
    Offer,
    Product,
    ProductCode,
    ProductCodeType,
    ProductPrice,
    Raffle,
    Role,
    RoleChangeRequest,
    SocialAccount,
    Store,
    UserProfile,
)
from .serializers import (
    AddressSerializer,
    BackgroundJobSerializer,
    CartItemSerializer,
    CartItemUpsertSerializer,
    CartItemUpdateSerializer,
    CartSerializer,
    CategorySerializer,
    DeviceSensorReadingSerializer,
    LoginSerializer,
    LogoutSerializer,
    NotificationPreferenceSerializer,
    OfferSerializer,
    ProfileAvatarSerializer,
    ProductExportJobCreateSerializer,
    ProductCodeSerializer,
    ProductPriceSerializer,
    ProductScanSerializer,
    ProductSerializer,
    RaffleSerializer,
    RegisterSerializer,
    RoleChangeRequestCreateSerializer,
    RoleChangeRequestSerializer,
    SocialLoginSerializer,
    StoreSerializer,
    VerifyEmailSerializer,
)
from .services import (
    build_unique_username_from_email,
    get_weather_payload,
    issue_jwt_pair,
    send_email_verification,
    verify_google_id_token,
)


User = get_user_model()

API_DOC_SECTIONS = [
    {
        'id': 'identity',
        'title': 'Identidad y acceso',
        'description': 'Registro, verificacion de correo y autenticacion JWT para clientes y administradores.',
        'endpoints': [
            {'path': '/api/auth/roles/', 'method': 'GET', 'auth_required': False},
            {
                'path': '/api/auth/register/',
                'method': 'GET',
                'auth_required': False,
                'description': 'Guia de campos requeridos para crear una cuenta.',
            },
            {
                'path': '/api/auth/register/',
                'method': 'POST',
                'auth_required': False,
                'description': 'Registrar usuario nuevo.',
                'body': ['email', 'password', 'confirm_password', 'role', 'address', 'birth_date'],
            },
            {'path': '/api/auth/verify-email/', 'method': 'POST', 'auth_required': False},
            {'path': '/api/auth/login/', 'method': 'POST', 'auth_required': False},
            {'path': '/api/auth/logout/', 'method': 'POST', 'auth_required': True},
            {'path': '/api/auth/me/', 'method': 'GET', 'auth_required': True},
            {
                'path': '/api/auth/social-login/',
                'method': 'POST',
                'auth_required': False,
                'body': ['provider', 'id_token'],
                'description': 'Login social real con Google validando id_token en backend.',
            },
        ],
    },
    {
        'id': 'catalog',
        'title': 'Catalogo y discovery',
        'description': 'Consulta productos, precios, tiendas, ofertas activas y catalogos geograficos.',
        'endpoints': [
            {'path': '/api/stores/', 'method': 'GET', 'auth_required': False},
            {'path': '/api/categories/', 'method': 'GET', 'auth_required': False},
            {
                'path': '/api/products/',
                'method': 'GET',
                'auth_required': False,
                'query_params': ['category_id', 'search', 'barcode'],
            },
            {
                'path': '/api/products/<product_id>/',
                'method': 'GET',
                'auth_required': False,
                'description': 'Detalle del producto con precio estimado, historial de compras y alternativas mas economicas.',
            },
            {
                'path': '/api/products/scan/',
                'method': 'POST',
                'auth_required': False,
                'body': ['code', 'code_type?', 'category_id?', 'name?', 'brand?', 'description?', 'store_id?', 'price?'],
            },
            {
                'path': '/api/products/purchases/',
                'method': 'GET',
                'auth_required': True,
                'query_params': ['product_id'],
            },
            {
                'path': '/api/products/purchases/',
                'method': 'POST',
                'auth_required': True,
                'body': ['product_id', 'store_id?', 'quantity', 'unit_price', 'purchased_at?', 'notes?', 'source?'],
            },
            {
                'path': '/api/offers/',
                'method': 'GET',
                'auth_required': False,
                'query_params': ['active', 'store_id', 'product_id', 'category_id', 'search'],
            },
            {
                'path': '/api/compare-prices/',
                'method': 'GET',
                'auth_required': False,
                'query_params': ['product_id', 'product'],
            },
            {
                'path': '/api/prices/history/',
                'method': 'GET',
                'auth_required': False,
                'query_params': ['product_id', 'product', 'store_id', 'limit'],
            },
            {
                'path': '/api/weather/',
                'method': 'GET',
                'auth_required': False,
                'query_params': ['city', 'lat', 'lon'],
            },
        ],
    },
    {
        'id': 'customer',
        'title': 'Perfil y carrito',
        'description': 'Endpoints autenticados para la experiencia del cliente dentro de la aplicacion.',
        'endpoints': [
            {'path': '/api/profile/addresses/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/profile/addresses/', 'method': 'POST', 'auth_required': True},
            {'path': '/api/profile/notifications/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/profile/notifications/', 'method': 'PATCH', 'auth_required': True},
            {'path': '/api/profile/savings-preferences/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/profile/savings-preferences/', 'method': 'PATCH', 'auth_required': True},
            {'path': '/api/profile/role-change-requests/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/profile/role-change-requests/', 'method': 'POST', 'auth_required': True},
            {'path': '/api/raffles/active/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/cart/', 'method': 'GET', 'auth_required': True},
            {
                'path': '/api/cart/',
                'method': 'DELETE',
                'auth_required': True,
                'description': 'Vaciar carrito actual.',
            },
            {'path': '/api/cart/items/', 'method': 'GET', 'auth_required': True},
            {
                'path': '/api/cart/items/',
                'method': 'POST',
                'auth_required': True,
                'body': ['product_id', 'quantity?', 'store_id?'],
            },
            {
                'path': '/api/cart/items/<item_id>/',
                'method': 'PATCH',
                'auth_required': True,
                'body': ['quantity?', 'store_id?'],
            },
            {'path': '/api/cart/items/<item_id>/', 'method': 'DELETE', 'auth_required': True},
            {'path': '/api/checkout/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/checkout/', 'method': 'POST', 'auth_required': True, 'body': ['notes?'], 'description': 'Crea una sesion de checkout desde el carrito actual sin vaciarlo.'},
            {'path': '/api/checkout/<checkout_id>/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/checkout/<checkout_id>/', 'method': 'PATCH', 'auth_required': True, 'body': ['address_id?', 'notes?'], 'description': 'Adjunta direccion y deja el checkout listo para pago.'},
            {'path': '/api/payments/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/payments/', 'method': 'POST', 'auth_required': True, 'body': ['checkout_id', 'method', 'provider?', 'simulate_failure?'], 'description': 'Procesa un pago sobre un checkout listo y crea la orden si es exitoso.'},
            {'path': '/api/payments/<payment_id>/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/shipments/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/shipments/<shipment_id>/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/shipments/<shipment_id>/', 'method': 'PATCH', 'auth_required': True, 'body': ['status?', 'carrier?', 'tracking_number?', 'notes?', 'estimated_delivery_at?'], 'description': 'Actualiza el estado logistico del envio ya creado para la orden pagada.'},
            {'path': '/api/orders/', 'method': 'GET', 'auth_required': True},
            {'path': '/api/orders/', 'method': 'POST', 'auth_required': True, 'body': ['address_id', 'notes?'], 'description': 'Crea una orden pendiente de pago a partir del carrito actual.'},
            {'path': '/api/orders/<order_id>/', 'method': 'GET', 'auth_required': True},
        ],
    },
    {
        'id': 'ops',
        'title': 'Operaciones y seguridad',
        'description': 'Procesos internos, trabajos asincronos y rutas protegidas para control operativo.',
        'endpoints': [
            {
                'path': '/api/jobs/export-products/',
                'method': 'POST',
                'auth_required': True,
                'body': ['category_id?', 'search?'],
                'description': 'Encola un job para exportar productos a CSV.',
            },
            {
                'path': '/api/jobs/<job_id>/',
                'method': 'GET',
                'auth_required': True,
                'description': 'Consulta estado y resultado de un job.',
            },
            {'path': '/api/device-sensors/', 'method': 'POST', 'auth_required': True},
            {'path': '/api/protected/', 'method': 'GET', 'auth_required': True},
            {
                'path': '/api/protected/admin-only/',
                'method': 'GET',
                'auth_required': True,
                'role_required': 'admin',
            },
        ],
    },
]


def build_api_root_payload(request):
    """Construye el payload del indice HTML/JSON de la API."""
    docs = []
    sections = []
    public_count = 0
    protected_count = 0
    admin_count = 0

    for section in API_DOC_SECTIONS:
        endpoints = []
        for endpoint in section['endpoints']:
            doc = dict(endpoint)
            doc['path_label'] = doc['path'].removeprefix('/api/')
            doc['absolute_url'] = request.build_absolute_uri(doc['path'])
            docs.append(doc)
            endpoints.append(doc)
            if doc.get('auth_required'):
                protected_count += 1
            else:
                public_count += 1
            if doc.get('role_required') == 'admin':
                admin_count += 1

        sections.append(
            {
                'id': section['id'],
                'title': section['title'],
                'description': section['description'],
                'endpoints': endpoints,
                'count': len(endpoints),
            }
        )

    return {
        'message': 'API GrocerySaver activa',
        'docs': docs,
        'sections': sections,
        'stats': [
            {'label': 'Endpoints visibles', 'value': len(docs), 'hint': 'Cobertura base para integracion y pruebas manuales.'},
            {'label': 'Rutas publicas', 'value': public_count, 'hint': 'Disponibles sin token.'},
            {'label': 'Rutas protegidas', 'value': protected_count, 'hint': 'Requieren JWT Bearer.'},
            {'label': 'Rutas admin', 'value': admin_count, 'hint': 'Acceso exclusivo para rol admin.'},
        ],
        'quickstart': [
            {
                'title': 'Descubrir roles',
                'method': 'GET',
                'path': '/api/auth/roles/',
                'summary': 'Obtiene los roles disponibles antes del registro.',
            },
            {
                'title': 'Iniciar sesion',
                'method': 'POST',
                'path': '/api/auth/login/',
                'summary': 'Recibe access y refresh token para consumir rutas privadas.',
            },
            {
                'title': 'Validar identidad',
                'method': 'GET',
                'path': '/api/auth/me/',
                'summary': 'Comprueba que el token Bearer es valido y devuelve el perfil actual.',
            },
        ],
        'base_url': get_request_base_url(request),
        'admin_url': reverse('admin:index'),
        'docs_url': request.build_absolute_uri('/api/docs/'),
        'schema_url': request.build_absolute_uri('/api/schema/'),
        'auth_scheme': 'JWT Bearer',
        'default_format': 'JSON',
        'sample_token_header': 'Authorization: Bearer <access_token>',
    }



def normalize_openapi_path(path):
    """Convierte segmentos tipo <item_id> a la sintaxis OpenAPI {item_id}."""
    return re.sub(r'<([^>]+)>', r'{\1}', path)


def infer_openapi_scalar_schema(name):
    """Infere un schema OpenAPI basico a partir del nombre del campo."""
    if name in {'price', 'offer_price', 'normal_price', 'lat', 'lon'}:
        return {'type': 'number'}
    if name in {'quantity', 'category_id', 'product_id', 'store_id', 'province_id', 'days_remaining'} or name.endswith('_id'):
        return {'type': 'integer'}
    if name in {'active', 'push_enabled', 'sms_enabled', 'email_enabled', 'is_shaking'}:
        return {'type': 'boolean'}
    if name == 'birth_date':
        return {'type': 'string', 'format': 'date'}
    if name in {'captured_at', 'starts_at', 'ends_at'}:
        return {'type': 'string', 'format': 'date-time'}
    if name == 'job_id':
        return {'type': 'string', 'format': 'uuid'}
    if name in {'accelerometer', 'gyroscope'}:
        return {
            'type': 'object',
            'properties': {
                'x': {'type': 'number'},
                'y': {'type': 'number'},
                'z': {'type': 'number'},
            },
            'required': ['x', 'y', 'z'],
        }
    return {'type': 'string'}


def build_openapi_parameters(endpoint):
    """Genera parametros query/path a partir de la documentacion manual."""
    parameters = []
    for raw_name in endpoint.get('query_params', []):
        name = raw_name.rstrip('?')
        parameters.append(
            {
                'name': name,
                'in': 'query',
                'required': not raw_name.endswith('?'),
                'schema': infer_openapi_scalar_schema(name),
            }
        )

    for path_name in re.findall(r'<([^>]+)>', endpoint['path']):
        parameters.append(
            {
                'name': path_name,
                'in': 'path',
                'required': True,
                'schema': infer_openapi_scalar_schema(path_name),
            }
        )
    return parameters


def build_openapi_request_body(endpoint):
    """Construye un requestBody simple para endpoints documentados con body."""
    body_fields = endpoint.get('body', [])
    if not body_fields:
        return None

    properties = {}
    required = []
    for raw_field in body_fields:
        field_name = raw_field.rstrip('?')
        properties[field_name] = infer_openapi_scalar_schema(field_name)
        if not raw_field.endswith('?'):
            required.append(field_name)

    body_schema = {'type': 'object', 'properties': properties}
    if required:
        body_schema['required'] = required

    return {
        'required': True,
        'content': {
            'application/json': {
                'schema': body_schema,
            }
        },
    }


def build_openapi_schema(request):
    """Genera un documento OpenAPI 3 basico desde la matriz manual de endpoints."""
    base_server = request.build_absolute_uri('/').rstrip('/')
    tags = []
    paths = {}

    for section in API_DOC_SECTIONS:
        tags.append({'name': section['title'], 'description': section['description']})
        for endpoint in section['endpoints']:
            path_key = normalize_openapi_path(endpoint['path'])
            method = endpoint['method'].lower()
            operation = {
                'tags': [section['title']],
                'operationId': f"{section['id']}_{method}_{path_key.strip('/').replace('/', '_').replace('{', '').replace('}', '')}",
                'summary': endpoint.get('description') or f"{endpoint['method']} {endpoint['path']}",
                'responses': {
                    '200': {'description': 'Respuesta exitosa'},
                    '400': {'description': 'Solicitud invalida'},
                    '401': {'description': 'No autenticado'},
                    '403': {'description': 'Sin permisos'},
                    '404': {'description': 'Recurso no encontrado'},
                },
                'parameters': build_openapi_parameters(endpoint),
            }

            if endpoint.get('auth_required'):
                operation['security'] = [{'BearerAuth': []}]

            request_body = build_openapi_request_body(endpoint)
            if request_body is not None and method in {'post', 'put', 'patch'}:
                operation['requestBody'] = request_body

            if method == 'post':
                operation['responses']['201'] = {'description': 'Recurso creado'}
            if method == 'delete':
                operation['responses']['204'] = {'description': 'Recurso eliminado'}

            paths.setdefault(path_key, {})[method] = operation

    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'GrocerySaver API',
            'version': '1.0.0',
            'description': 'Backend para inventario del hogar, compras inteligentes y comparacion de precios.',
        },
        'servers': [
            {'url': base_server},
        ],
        'tags': tags,
        'components': {
            'securitySchemes': {
                'BearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT',
                }
            }
        },
        'paths': paths,
    }


def build_api_docs_payload(request):
    """Compone el contexto HTML para la pagina de documentacion."""
    payload = build_api_root_payload(request)
    schema = build_openapi_schema(request)
    payload.update(
        {
            'page_title': 'Documentacion OpenAPI',
            'docs_url': request.build_absolute_uri('/api/docs/'),
            'schema_url': request.build_absolute_uri('/api/schema/'),
            'schema_download_url': request.build_absolute_uri('/api/schema/?download=1'),
            'openapi_version': schema['openapi'],
            'api_version': schema['info']['version'],
            'schema_preview': json.dumps(
                {
                    'openapi': schema['openapi'],
                    'info': schema['info'],
                    'servers': schema['servers'],
                    'paths_count': len(schema['paths']),
                },
                indent=2,
                ensure_ascii=False,
            ),
        }
    )
    return payload


def cache_aware_response(payload, cache_hit):
    """Adjunta un header simple para distinguir hit y miss de cache."""
    response = Response(payload)
    response['X-Cache-Status'] = 'HIT' if cache_hit else 'MISS'
    return response


def get_request_base_url(request):
    """Obtiene la URL base absoluta del request actual."""
    return request.build_absolute_uri('/')


def build_user_response(user, request=None):
    """Construye un payload consistente de usuario autenticado."""
    from users.models import UserSavingsPreference
    from users.serializers import UserSavingsPreferenceSerializer

    profile = getattr(user, 'profile', None)
    role_name = profile.role.name if profile and profile.role else None
    avatar_url = None
    if profile and profile.avatar:
        avatar_url = profile.avatar.url
        if request is not None:
            avatar_url = request.build_absolute_uri(avatar_url)

    savings_preference = None
    if getattr(user, 'is_authenticated', False):
        savings_preference, _ = UserSavingsPreference.objects.get_or_create(user=user)

    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_staff': user.is_staff,
        'staff_status': user.is_staff,
        'role': role_name,
        'address': profile.address if profile else None,
        'birth_date': str(profile.birth_date) if profile and profile.birth_date else None,
        'avatar': avatar_url,
        'savings_preferences': UserSavingsPreferenceSerializer(savings_preference).data if savings_preference else None,
    }


def load_user_cart(user):
    """Carga el carrito del usuario con sus relaciones ya resueltas."""
    return (
        Cart.objects.select_related('user')
        .prefetch_related(
            Prefetch(
                'items',
                queryset=CartItem.objects.select_related('product__category', 'store').prefetch_related(
                    'product__codes',
                    'product__prices__store',
                ),
            )
        )
        .get(user=user)
    )


def get_or_create_user_cart(user):
    """Obtiene o crea el carrito actual del usuario autenticado."""
    Cart.objects.get_or_create(user=user)
    return load_user_cart(user)


def touch_cart(cart):
    """Actualiza la marca temporal del carrito tras una mutacion."""
    cart.save(update_fields=['updated_at'])


class IsAdminRole(permissions.BasePermission):
    """Permiso basado en el rol admin definido en el perfil del usuario."""

    message = 'No tienes permisos para acceder a esta ruta.'

    def has_permission(self, request, view):
        profile = getattr(request.user, 'profile', None)
        return bool(profile and profile.role and profile.role.name == 'admin')


class RegisterView(generics.GenericAPIView):
    """Registro de usuarios nuevos y emision de token de verificacion."""

    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def get(self, request):
        roles = list(Role.objects.order_by('name').values_list('name', flat=True))
        return Response(
            {
                'message': 'Usa POST para registrar un usuario.',
                'required_fields': ['email', 'password', 'confirm_password', 'role', 'address', 'birth_date'],
                'optional_fields': ['username', 'first_name', 'last_name'],
                'roles_endpoint': '/api/auth/roles/',
                'available_roles': roles,
                'payload_template': {
                    'username': '',
                    'email': '',
                    'password': '',
                    'confirm_password': '',
                    'first_name': '',
                    'last_name': '',
                    'role': 'cliente',
                    'address': '',
                    'birth_date': 'YYYY-MM-DD',
                },
            }
        )

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        auto_verify = getattr(settings, 'AUTO_VERIFY_EMAIL_ON_REGISTER', False)

        if auto_verify:
            user.is_active = True
            user.save(update_fields=['is_active'])
            response_data = {
                'message': 'Registro exitoso. Ya puedes iniciar sesion.',
                'email_verification_required': False,
                'user': build_user_response(user, request=request),
            }
        else:
            verification = EmailVerificationToken.create_for_user(
                user=user,
                ttl_hours=getattr(settings, 'EMAIL_VERIFICATION_TOKEN_TTL_HOURS', 24),
            )
            send_email_verification(user=user, token=verification.token)

            response_data = {
                'message': 'Registro exitoso. Revisa tu correo para verificar la cuenta.',
                'email_verification_required': True,
            }
            if settings.DEBUG:
                response_data['verification_token_debug'] = str(verification.token)

        seed_demo_expiring_inventory_for_user(user)
        return Response(response_data, status=status.HTTP_201_CREATED)


class ApiRootView(APIView):
    """Indice simple de rutas disponibles para exploracion manual."""

    permission_classes = [permissions.AllowAny]
    renderer_classes = [renderers.JSONRenderer, renderers.TemplateHTMLRenderer, renderers.BrowsableAPIRenderer]

    def get(self, request):
        payload = build_api_root_payload(request)
        if getattr(request.accepted_renderer, 'format', None) == 'html':
            return Response(payload, template_name='grocerysaver/api_root.html')
        return Response(payload)


class ApiSchemaView(APIView):
    """Expone un documento OpenAPI JSON sin dependencias externas."""

    permission_classes = [permissions.AllowAny]
    renderer_classes = [renderers.JSONRenderer, renderers.BrowsableAPIRenderer]

    def get(self, request):
        payload = build_openapi_schema(request)
        response = Response(payload)
        response['Content-Type'] = 'application/vnd.oai.openapi+json'
        if request.query_params.get('download') == '1':
            response['Content-Disposition'] = 'attachment; filename="grocerysaver-openapi.json"'
        return response


class ApiDocsView(APIView):
    """Renderiza una pagina HTML de documentacion para consumo humano."""

    permission_classes = [permissions.AllowAny]
    renderer_classes = [renderers.TemplateHTMLRenderer, renderers.BrowsableAPIRenderer]

    def get(self, request):
        payload = build_api_docs_payload(request)
        return Response(payload, template_name='grocerysaver/api_docs.html')


class RoleListView(APIView):
    """Expone los roles disponibles del sistema."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        payload, cache_hit = get_cached_payload(
            CACHE_NS_ROLES,
            lambda: {'roles': list(Role.objects.order_by('name').values('name', 'description'))},
            ttl=CATALOG_CACHE_TTL,
        )
        return cache_aware_response(payload, cache_hit)


class StoreListView(APIView):
    """Lista tiendas del catalogo publico."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        payload, cache_hit = get_cached_payload(
            CACHE_NS_STORES,
            lambda: {'stores': StoreSerializer(Store.objects.all(), many=True).data},
            ttl=CATALOG_CACHE_TTL,
        )
        return cache_aware_response(payload, cache_hit)


class CartView(APIView):
    """Lee o vacia el carrito persistido del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = get_or_create_user_cart(request.user)
        return Response({'cart': CartSerializer(cart, context={'request': request}).data})

    def delete(self, request):
        cart = get_or_create_user_cart(request.user)
        cart.items.all().delete()
        touch_cart(cart)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemListCreateView(APIView):
    """Lista items del carrito o agrega una nueva linea."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = get_or_create_user_cart(request.user)
        items = list(cart.items.all())
        return Response({'items': CartItemSerializer(items, many=True, context={'request': request}).data})

    def post(self, request):
        serializer = CartItemUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = get_or_create_user_cart(request.user)
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']
        resolved_store = serializer.validated_data['resolved_store']

        item = cart.items.filter(product=product).first()
        created = item is None

        if created:
            item = CartItem.objects.create(
                cart=cart,
                product=product,
                store=resolved_store,
                quantity=quantity,
            )
        else:
            item.quantity += quantity
            item.store = resolved_store
            item.save(update_fields=['quantity', 'store', 'updated_at'])

        touch_cart(cart)
        cart = load_user_cart(request.user)
        item = cart.items.get(id=item.id)

        return Response(
            {
                'item': CartItemSerializer(item, context={'request': request}).data,
                'cart': CartSerializer(cart, context={'request': request}).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CartItemDetailView(APIView):
    """Actualiza o elimina una linea individual del carrito."""

    permission_classes = [permissions.IsAuthenticated]

    def _get_item(self, request, item_id):
        return (
            CartItem.objects.select_related('cart', 'product__category', 'store')
            .prefetch_related('product__codes', 'product__prices__store')
            .filter(id=item_id, cart__user=request.user)
            .first()
        )

    def patch(self, request, item_id):
        item = self._get_item(request, item_id)
        if item is None:
            return Response({'detail': 'Item de carrito no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CartItemUpdateSerializer(item, data=request.data, partial=True, context={'item': item})
        serializer.is_valid(raise_exception=True)

        if 'quantity' in serializer.validated_data:
            item.quantity = serializer.validated_data['quantity']
        if 'resolved_store' in serializer.validated_data:
            item.store = serializer.validated_data['resolved_store']
        item.save(update_fields=['quantity', 'store', 'updated_at'])

        touch_cart(item.cart)
        cart = load_user_cart(request.user)
        item = cart.items.get(id=item.id)
        return Response(
            {
                'item': CartItemSerializer(item, context={'request': request}).data,
                'cart': CartSerializer(cart, context={'request': request}).data,
            }
        )

    def delete(self, request, item_id):
        item = self._get_item(request, item_id)
        if item is None:
            return Response({'detail': 'Item de carrito no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        cart = item.cart
        item.delete()
        touch_cart(cart)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AddressListCreateView(APIView):
    """Lista y crea direcciones del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        addresses = request.user.addresses.all()
        return Response({'addresses': AddressSerializer(addresses, many=True).data})

    def post(self, request):
        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_default = serializer.validated_data.get('is_default', False)
        if not request.user.addresses.exists():
            is_default = True
        if is_default:
            request.user.addresses.update(is_default=False)

        address = serializer.save(user=request.user, is_default=is_default)
        return Response({'address': AddressSerializer(address).data}, status=status.HTTP_201_CREATED)


class AddressDetailView(APIView):
    """Actualiza o elimina una direccion individual del usuario."""

    permission_classes = [permissions.IsAuthenticated]

    def _get_address(self, request, address_id):
        return Address.objects.filter(id=address_id, user=request.user).first()

    def patch(self, request, address_id):
        address = self._get_address(request, address_id)
        if address is None:
            return Response({'detail': 'Direccion no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AddressSerializer(address, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        is_default = serializer.validated_data.get('is_default', address.is_default)
        if is_default:
            request.user.addresses.exclude(id=address.id).update(is_default=False)

        updated_address = serializer.save()
        if not request.user.addresses.filter(is_default=True).exists():
            updated_address.is_default = True
            updated_address.save(update_fields=['is_default'])

        return Response({'address': AddressSerializer(updated_address).data})

    def delete(self, request, address_id):
        address = self._get_address(request, address_id)
        if address is None:
            return Response({'detail': 'Direccion no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        was_default = address.is_default
        address.delete()

        if was_default:
            replacement = request.user.addresses.order_by('-updated_at').first()
            if replacement is not None and not replacement.is_default:
                replacement.is_default = True
                replacement.save(update_fields=['is_default'])

        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationPreferenceView(APIView):
    """Lee y actualiza preferencias de notificacion del usuario."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return Response({'notification_preferences': NotificationPreferenceSerializer(preference).data})

    def patch(self, request):
        preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
        serializer = NotificationPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'notification_preferences': serializer.data})


class CategoryListView(APIView):
    """Lista categorias publicas con soporte de cache."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        payload, cache_hit = get_cached_payload(
            CACHE_NS_CATEGORIES,
            lambda: {
                'categories': CategorySerializer(
                    Category.objects.all(),
                    many=True,
                    context={'request': request},
                ).data
            },
            params={'base_url': get_request_base_url(request)},
            ttl=CATALOG_CACHE_TTL,
        )
        return cache_aware_response(payload, cache_hit)


class ActiveRaffleListView(APIView):
    """Retorna rifas vigentes para usuarios autenticados."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        def build_payload():
            now = timezone.now()
            raffles = Raffle.objects.filter(starts_at__lte=now, ends_at__gte=now)
            return {'raffles': RaffleSerializer(raffles, many=True).data}

        payload, cache_hit = get_cached_payload(
            CACHE_NS_RAFFLES,
            build_payload,
            ttl=RAFFLE_CACHE_TTL,
        )
        return cache_aware_response(payload, cache_hit)


class WeatherView(APIView):
    """Expone clima por ciudad o coordenadas."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        city = request.query_params.get('city')
        lat_raw = request.query_params.get('lat')
        lon_raw = request.query_params.get('lon')

        latitude = None
        longitude = None
        if lat_raw is not None or lon_raw is not None:
            if lat_raw is None or lon_raw is None:
                return Response(
                    {'detail': 'Debes enviar ambos query params: lat y lon.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                latitude = float(lat_raw)
                longitude = float(lon_raw)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'lat y lon deben ser numeros validos.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            payload, cache_hit = get_cached_payload(
                CACHE_NS_WEATHER,
                lambda: get_weather_payload(city=city, latitude=latitude, longitude=longitude),
                params={
                    'city': (city or '').strip().lower(),
                    'latitude': latitude,
                    'longitude': longitude,
                },
                ttl=WEATHER_CACHE_TTL,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'detail': 'No se pudo obtener el clima en este momento.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return cache_aware_response(payload, cache_hit)


class ProductListView(APIView):
    """Lista productos, precios y mejor opcion disponible."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        category_id = request.query_params.get('category_id')
        search = request.query_params.get('search')

        def build_payload():
            queryset = Product.objects.select_related('category').prefetch_related('prices__store', 'codes', 'price_history__store')

            if category_id:
                queryset_filtered = queryset.filter(category_id=category_id)
            else:
                queryset_filtered = queryset

            if search:
                queryset_filtered = queryset_filtered.filter(name__icontains=search)

            products = list(queryset_filtered)
            qr_codes_by_product_id = get_request_loader(
                request,
                'product_qr_codes',
                batch_load_product_qr_codes,
            ).load_many([product.id for product in products])

            products_payload = []
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
                products_payload.append(product_data)

            return {'products': products_payload}

        payload, cache_hit = get_cached_payload(
            CACHE_NS_PRODUCTS,
            build_payload,
            params={
                'base_url': get_request_base_url(request),
                'category_id': category_id or '',
                'search': (search or '').strip().lower(),
            },
            ttl=CATALOG_CACHE_TTL,
        )
        return cache_aware_response(payload, cache_hit)


class ProductScanView(APIView):
    """Busca un producto por codigo o lo crea si no existe."""

    permission_classes = [permissions.AllowAny]

    def _build_product_payload(self, product, request):
        prices = product.prices.select_related('store').order_by('price')
        best_option = prices.first()
        payload = ProductSerializer(product, context={'request': request}).data
        payload['prices'] = ProductPriceSerializer(prices, many=True).data
        payload['codes'] = ProductCodeSerializer(product.codes.all(), many=True).data
        payload['stores_available'] = prices.count()
        payload['best_option'] = (
            {
                'store': best_option.store.name,
                'price': str(best_option.price),
            }
            if best_option
            else None
        )
        payload['best_price'] = str(best_option.price) if best_option else None
        return payload

    def post(self, request):
        serializer = ProductScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        code = data['code']
        code_row = ProductCode.objects.select_related('product__category').filter(code=code).first()

        if code_row is None:
            category_id = data.get('category_id')
            name = data.get('name', '').strip()
            if not category_id or not name:
                return Response(
                    {'detail': 'Codigo no registrado. Envia category_id y name para crear el producto.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            category = Category.objects.filter(id=category_id).first()
            if category is None:
                return Response({'detail': 'Categoria no encontrada.'}, status=status.HTTP_400_BAD_REQUEST)

            product, product_created = Product.objects.get_or_create(
                category=category,
                name=name,
                brand=data.get('brand', ''),
                defaults={'description': data.get('description', '')},
            )
            code_row = ProductCode.objects.create(
                product=product,
                code=code,
                code_type=data.get('code_type') or ProductCodeType.BARCODE,
            )
            code_created = True
        else:
            product = code_row.product
            product_created = False
            code_created = False

        price_updated = False
        store_id = data.get('store_id')
        price = data.get('price')
        if store_id is not None and price is not None:
            store = Store.objects.filter(id=store_id).first()
            if store is None:
                return Response({'detail': 'Tienda no encontrada.'}, status=status.HTTP_400_BAD_REQUEST)
            ProductPrice.objects.update_or_create(
                product=product,
                store=store,
                defaults={'price': price},
            )
            price_updated = True

        status_code = status.HTTP_201_CREATED if code_created else status.HTTP_200_OK
        return Response(
            {
                'matched': not code_created,
                'product_created': product_created,
                'code_created': code_created,
                'price_updated': price_updated,
                'scanned_code': ProductCodeSerializer(code_row).data,
                'product': self._build_product_payload(product, request),
            },
            status=status_code,
        )


class OfferListView(APIView):
    """Lista ofertas activas o historicas con filtros basicos."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        active_param = (request.query_params.get('active') or 'true').strip().lower()
        if active_param in {'true', '1', 'yes', 'on'}:
            active_filter = True
        elif active_param in {'false', '0', 'no', 'off'}:
            active_filter = False
        else:
            return Response(
                {'detail': 'Parametro active invalido. Usa true o false.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        store_id = request.query_params.get('store_id')
        product_id = request.query_params.get('product_id')
        category_id = request.query_params.get('category_id')
        search = request.query_params.get('search')

        def build_payload():
            queryset = Offer.objects.select_related('product__category', 'store').prefetch_related('product__codes')

            if active_filter:
                now = timezone.now()
                queryset_filtered = queryset.filter(starts_at__lte=now, ends_at__gte=now)
            else:
                queryset_filtered = queryset

            if store_id:
                queryset_filtered = queryset_filtered.filter(store_id=store_id)
            if product_id:
                queryset_filtered = queryset_filtered.filter(product_id=product_id)
            if category_id:
                queryset_filtered = queryset_filtered.filter(product__category_id=category_id)
            if search:
                queryset_filtered = queryset_filtered.filter(product__name__icontains=search)

            offers = list(queryset_filtered)
            qr_codes_by_product_id = get_request_loader(
                request,
                'product_qr_codes',
                batch_load_product_qr_codes,
            ).load_many([offer.product_id for offer in offers])

            serialized = OfferSerializer(
                offers,
                many=True,
                context={
                    'request': request,
                    'qr_codes_by_product_id': qr_codes_by_product_id,
                },
            ).data
            return {
                'count': len(serialized),
                'offers': serialized,
                'results': serialized,
            }

        payload, cache_hit = get_cached_payload(
            CACHE_NS_OFFERS,
            build_payload,
            params={
                'active': active_param,
                'base_url': get_request_base_url(request),
                'category_id': category_id or '',
                'product_id': product_id or '',
                'search': (search or '').strip().lower(),
                'store_id': store_id or '',
            },
            ttl=CATALOG_CACHE_TTL,
        )
        return cache_aware_response(payload, cache_hit)


class RoleChangeRequestListCreateView(APIView):
    """Lista y crea solicitudes de cambio de rol del usuario actual."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role_requests = request.user.role_change_requests.select_related('current_role', 'requested_role')
        return Response({'requests': RoleChangeRequestSerializer(role_requests, many=True).data})

    def post(self, request):
        serializer = RoleChangeRequestCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        role_request = serializer.save()
        return Response(
            {'request': RoleChangeRequestSerializer(role_request).data},
            status=status.HTTP_201_CREATED,
        )


class ProductPriceComparisonView(APIView):
    """Compara precios de un producto entre varias tiendas."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        product_id = request.query_params.get('product_id')
        product_name = request.query_params.get('product')

        if not product_id and not product_name:
            return Response(
                {'detail': 'Debes enviar product_id o product en query params.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def build_payload():
            queryset = Product.objects.select_related('category').prefetch_related('prices__store', 'codes', 'price_history__store')
            if product_id:
                product = queryset.filter(id=product_id).first()
            else:
                product = queryset.filter(name__iexact=product_name).first()
                if product is None:
                    product = queryset.filter(name__icontains=product_name).first()

            if product is None:
                raise LookupError('Producto no encontrado.')

            prices = product.prices.select_related('store').order_by('price')
            if not prices.exists():
                return {
                    'product': ProductSerializer(product, context={'request': request}).data,
                    'prices': [],
                    'price_history': PriceHistorySerializer(product.price_history.select_related('store').all()[:12], many=True).data,
                    'stores_available': 0,
                    'best_option': None,
                    'most_expensive_option': None,
                }

            best_option = prices.first()
            most_expensive_option = prices.last()
            savings = most_expensive_option.price - best_option.price
            qr_codes_by_product_id = get_request_loader(
                request,
                'product_qr_codes',
                batch_load_product_qr_codes,
            ).load_many([product.id])

            return {
                'product': ProductSerializer(
                    product,
                    context={
                        'request': request,
                        'qr_codes_by_product_id': qr_codes_by_product_id,
                    },
                ).data,
                'prices': ProductPriceSerializer(prices, many=True).data,
                'price_history': PriceHistorySerializer(product.price_history.select_related('store').all()[:12], many=True).data,
                'stores_available': prices.count(),
                'best_option': {
                    'store': best_option.store.name,
                    'price': str(best_option.price),
                },
                'most_expensive_option': {
                    'store': most_expensive_option.store.name,
                    'price': str(most_expensive_option.price),
                },
                'savings_vs_most_expensive': str(savings),
            }

        try:
            payload, cache_hit = get_cached_payload(
                CACHE_NS_COMPARE_PRICES,
                build_payload,
                params={
                    'base_url': get_request_base_url(request),
                    'product_id': product_id or '',
                    'product_name': (product_name or '').strip().lower(),
                },
                ttl=CATALOG_CACHE_TTL,
            )
        except LookupError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return cache_aware_response(payload, cache_hit)


class ProductExportJobCreateView(APIView):
    """Encola un job asincrono para exportar productos en varios formatos."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ProductExportJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job = enqueue_export_products_job(
            created_by=request.user,
            file_format=serializer.validated_data.get('format', 'csv'),
            category_id=serializer.validated_data.get('category_id'),
            search=serializer.validated_data.get('search', ''),
        )

        response_serializer = BackgroundJobSerializer(job, context={'request': request})
        return Response(
            {
                'message': 'Job encolado correctamente.',
                'job': response_serializer.data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class DeviceSensorReadingCreateView(APIView):
    """Recibe y persiste una lectura de sensores del dispositivo autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DeviceSensorReadingSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        reading = serializer.save()
        return Response(
            {
                'detail': 'Lectura de sensores registrada.',
                'sensor_reading': DeviceSensorReadingSerializer(reading).data,
            },
            status=status.HTTP_201_CREATED,
        )


class JobDetailView(APIView):
    """Consulta estado y resultado de un trabajo en background."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        profile = getattr(request.user, 'profile', None)
        is_admin = bool(profile and profile.role and profile.role.name == 'admin')

        queryset = BackgroundJob.objects.all()
        if not is_admin:
            queryset = queryset.filter(created_by=request.user)

        job = queryset.filter(job_id=job_id).first()
        if job is None:
            return Response({'detail': 'Job no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BackgroundJobSerializer(job, context={'request': request})
        return Response(
            {
                'job': serializer.data,
                'is_finished': job.status in {JobStatus.COMPLETED, JobStatus.FAILED},
            }
        )


class VerifyEmailView(APIView):
    """Activa una cuenta a partir de un token de verificacion."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        verification = EmailVerificationToken.objects.select_related('user').filter(token=token).first()
        if verification is None:
            return Response({'detail': 'Token invalido.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.is_used:
            return Response({'detail': 'El token ya fue utilizado.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.is_expired:
            return Response({'detail': 'El token ha expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        user = verification.user
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])

        verification.is_used = True
        verification.save(update_fields=['is_used'])

        return Response(
            {
                'message': 'Correo verificado correctamente.',
                'tokens': issue_jwt_pair(user),
                'user': build_user_response(user, request=request),
            }
        )


class LoginView(APIView):
    """Autentica un usuario local por email y password."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        return Response(
            {
                'message': 'Inicio de sesion exitoso.',
                'tokens': issue_jwt_pair(user),
                'user': build_user_response(user, request=request),
            }
        )


class MeView(APIView):
    """Devuelve el perfil resumido del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({'user': build_user_response(request.user, request=request)})


class ProfileAvatarView(APIView):
    """Permite subir, reemplazar y eliminar el avatar del usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_profile(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            profile = UserProfile.objects.create(
                user=request.user,
                address='',
                birth_date=timezone.localdate(),
            )
        return profile

    def patch(self, request):
        profile = self._get_profile(request)
        serializer = ProfileAvatarSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'message': 'Foto de perfil actualizada.',
                'user': build_user_response(request.user, request=request),
            }
        )

    def delete(self, request):
        profile = self._get_profile(request)
        if profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
            profile.save(update_fields=['avatar', 'updated_at'])

        return Response(
            {
                'message': 'Foto de perfil eliminada.',
                'user': build_user_response(request.user, request=request),
            }
        )


class LogoutView(APIView):
    """Invalida un refresh token via blacklist."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data['refresh']
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({'detail': 'Refresh token invalido.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Sesion cerrada correctamente.'}, status=status.HTTP_200_OK)


class ProtectedRouteView(APIView):
    """Ruta minima de prueba para autenticacion JWT."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                'message': 'Ruta protegida accesible con token valido.',
                'user': build_user_response(request.user, request=request),
            }
        )


class AdminOnlyView(APIView):
    """Ruta protegida solo para usuarios con rol admin."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        return Response({'message': 'Acceso permitido solo para rol admin.'})


class SocialLoginView(APIView):
    """Crea o reutiliza usuarios a partir de identidad social externa."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = serializer.validated_data['provider']
        identity = verify_google_id_token(serializer.validated_data['id_token'])
        provider_user_id = identity['provider_user_id']
        email = identity['email']
        first_name = identity.get('first_name', '')
        last_name = identity.get('last_name', '')

        social_account = SocialAccount.objects.select_related('user').filter(
            provider=provider,
            provider_user_id=provider_user_id,
        ).first()

        created = False

        if social_account is not None:
            user = social_account.user
        else:
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                user = User.objects.create_user(
                    username=build_unique_username_from_email(email),
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                )
                created = True
            elif not user.is_active:
                user.is_active = True
                user.save(update_fields=['is_active'])

            SocialAccount.objects.create(
                user=user,
                provider=provider,
                provider_user_id=provider_user_id,
                email=email,
            )

        seed_demo_expiring_inventory_for_user(user)

        return Response(
            {
                'message': 'Autenticacion social exitosa.',
                'created': created,
                'tokens': issue_jwt_pair(user),
                'user': build_user_response(user, request=request),
            }
        )






