from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Address,
    Category,
    EmailVerificationToken,
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
)
from .serializers import (
    AddressSerializer,
    CategorySerializer,
    LoginSerializer,
    LogoutSerializer,
    NotificationPreferenceSerializer,
    OfferSerializer,
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
    get_ecuador_cantons,
    get_ecuador_geo_data,
    get_ecuador_provinces,
    get_weather_payload,
    issue_jwt_pair,
    send_email_verification,
)


User = get_user_model()


def build_user_response(user):
    profile = getattr(user, 'profile', None)
    role_name = profile.role.name if profile and profile.role else None
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
    }


class IsAdminRole(permissions.BasePermission):
    message = 'No tienes permisos para acceder a esta ruta.'

    def has_permission(self, request, view):
        profile = getattr(request.user, 'profile', None)
        return bool(profile and profile.role and profile.role.name == 'admin')


class RegisterView(generics.GenericAPIView):
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
        verification = EmailVerificationToken.create_for_user(
            user=user,
            ttl_hours=getattr(settings, 'EMAIL_VERIFICATION_TOKEN_TTL_HOURS', 24),
        )
        send_email_verification(user=user, token=verification.token)

        response_data = {
            'message': 'Registro exitoso. Revisa tu correo para verificar la cuenta.',
        }
        if settings.DEBUG:
            response_data['verification_token_debug'] = str(verification.token)

        return Response(response_data, status=status.HTTP_201_CREATED)


class ApiRootView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(
            {
                'message': 'API GrocerySaver activa',
                'docs': [
                    {
                        'path': '/api/auth/roles/',
                        'method': 'GET',
                        'auth_required': False,
                    },
                    {
                        'path': '/api/auth/register/',
                        'method': 'GET',
                        'auth_required': False,
                        'description': 'Guia del endpoint de registro.',
                    },
                    {
                        'path': '/api/auth/register/',
                        'method': 'POST',
                        'auth_required': False,
                        'description': 'Registrar usuario nuevo.',
                    },
                    {
                        'path': '/api/auth/verify-email/',
                        'method': 'POST',
                        'auth_required': False,
                    },
                    {
                        'path': '/api/auth/login/',
                        'method': 'POST',
                        'auth_required': False,
                    },
                    {
                        'path': '/api/auth/logout/',
                        'method': 'POST',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/auth/me/',
                        'method': 'GET',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/auth/social-login/',
                        'method': 'POST',
                        'auth_required': False,
                    },
                    {
                        'path': '/api/stores/',
                        'method': 'GET',
                        'auth_required': False,
                    },
                    {
                        'path': '/api/categories/',
                        'method': 'GET',
                        'auth_required': False,
                    },
                    {
                        'path': '/api/products/',
                        'method': 'GET',
                        'auth_required': False,
                        'query_params': ['category_id', 'search'],
                    },
                    {
                        'path': '/api/products/scan/',
                        'method': 'POST',
                        'auth_required': False,
                        'body': ['code', 'code_type?', 'category_id?', 'name?', 'brand?', 'description?', 'store_id?', 'price?'],
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
                        'path': '/api/weather/',
                        'method': 'GET',
                        'auth_required': False,
                        'query_params': ['city', 'lat', 'lon'],
                    },
                    {
                        'path': '/api/geo/ecuador/',
                        'method': 'GET',
                        'auth_required': False,
                    },
                    {
                        'path': '/api/geo/ecuador/provinces/',
                        'method': 'GET',
                        'auth_required': False,
                    },
                    {
                        'path': '/api/geo/ecuador/cantons/',
                        'method': 'GET',
                        'auth_required': False,
                        'query_params': ['province_id', 'province'],
                    },
                    {
                        'path': '/api/profile/addresses/',
                        'method': 'GET',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/profile/addresses/',
                        'method': 'POST',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/profile/notifications/',
                        'method': 'GET',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/profile/notifications/',
                        'method': 'PATCH',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/raffles/active/',
                        'method': 'GET',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/profile/role-change-requests/',
                        'method': 'GET',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/profile/role-change-requests/',
                        'method': 'POST',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/protected/',
                        'method': 'GET',
                        'auth_required': True,
                    },
                    {
                        'path': '/api/protected/admin-only/',
                        'method': 'GET',
                        'auth_required': True,
                        'role_required': 'admin',
                    },
                ],
            }
        )


class RoleListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        roles = Role.objects.order_by('name').values('name', 'description')
        return Response({'roles': list(roles)})


class StoreListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        stores = Store.objects.all()
        return Response({'stores': StoreSerializer(stores, many=True).data})


class AddressListCreateView(APIView):
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
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        categories = Category.objects.all()
        return Response({'categories': CategorySerializer(categories, many=True, context={'request': request}).data})


class ActiveRaffleListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        raffles = Raffle.objects.filter(starts_at__lte=now, ends_at__gte=now)
        return Response({'raffles': RaffleSerializer(raffles, many=True).data})


class WeatherView(APIView):
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
            payload = get_weather_payload(city=city, latitude=latitude, longitude=longitude)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'detail': 'No se pudo obtener el clima en este momento.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(payload)


class EcuadorGeoView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = get_ecuador_geo_data()
        return Response(
            {
                'country': data.get('country', 'Ecuador'),
                'provinces': data.get('provinces') or [],
            }
        )


class EcuadorProvinceListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        provinces = get_ecuador_provinces()
        return Response({'country': 'Ecuador', 'provinces': provinces})


class EcuadorCantonListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        province_id = request.query_params.get('province_id')
        province_name = request.query_params.get('province')
        try:
            payload = get_ecuador_cantons(province_id=province_id, province_name=province_name)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class ProductListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = Product.objects.select_related('category').prefetch_related('prices__store')
        category_id = request.query_params.get('category_id')
        search = request.query_params.get('search')

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if search:
            queryset = queryset.filter(name__icontains=search)

        products_payload = []
        for product in queryset:
            prices = list(product.prices.all())
            best_option = prices[0] if prices else None
            product_data = ProductSerializer(product, context={'request': request}).data
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

        return Response({'products': products_payload})


class ProductScanView(APIView):
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
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = Offer.objects.select_related('product__category', 'store')

        active_param = (request.query_params.get('active') or 'true').strip().lower()
        if active_param in {'true', '1', 'yes', 'on'}:
            now = timezone.now()
            queryset = queryset.filter(starts_at__lte=now, ends_at__gte=now)
        elif active_param in {'false', '0', 'no', 'off'}:
            pass
        else:
            return Response(
                {'detail': 'Parametro active invalido. Usa true o false.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        store_id = request.query_params.get('store_id')
        product_id = request.query_params.get('product_id')
        category_id = request.query_params.get('category_id')
        search = request.query_params.get('search')

        if store_id:
            queryset = queryset.filter(store_id=store_id)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if category_id:
            queryset = queryset.filter(product__category_id=category_id)
        if search:
            queryset = queryset.filter(product__name__icontains=search)

        serialized = OfferSerializer(queryset, many=True, context={'request': request}).data
        return Response(
            {
                'count': len(serialized),
                'offers': serialized,
                'results': serialized,
            }
        )


class RoleChangeRequestListCreateView(APIView):
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
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        product_id = request.query_params.get('product_id')
        product_name = request.query_params.get('product')

        if not product_id and not product_name:
            return Response(
                {'detail': 'Debes enviar product_id o product en query params.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = Product.objects.select_related('category').prefetch_related('prices__store')
        if product_id:
            product = queryset.filter(id=product_id).first()
        else:
            product = queryset.filter(name__iexact=product_name).first()
            if product is None:
                product = queryset.filter(name__icontains=product_name).first()

        if product is None:
            return Response({'detail': 'Producto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        prices = product.prices.select_related('store').order_by('price')
        if not prices.exists():
            return Response(
                {
                    'product': ProductSerializer(product, context={'request': request}).data,
                    'prices': [],
                    'stores_available': 0,
                    'best_option': None,
                    'most_expensive_option': None,
                }
            )

        best_option = prices.first()
        most_expensive_option = prices.last()
        savings = most_expensive_option.price - best_option.price

        return Response(
            {
                'product': ProductSerializer(product, context={'request': request}).data,
                'prices': ProductPriceSerializer(prices, many=True).data,
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
        )


class VerifyEmailView(APIView):
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
                'user': build_user_response(user),
            }
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        return Response(
            {
                'message': 'Inicio de sesion exitoso.',
                'tokens': issue_jwt_pair(user),
                'user': build_user_response(user),
            }
        )


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({'user': build_user_response(request.user)})


class LogoutView(APIView):
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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                'message': 'Ruta protegida accesible con token valido.',
                'user': build_user_response(request.user),
            }
        )


class AdminOnlyView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        return Response({'message': 'Acceso permitido solo para rol admin.'})


class SocialLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = serializer.validated_data['provider']
        provider_user_id = serializer.validated_data['provider_user_id']
        email = serializer.validated_data['email'].lower()
        first_name = serializer.validated_data.get('first_name', '')
        last_name = serializer.validated_data.get('last_name', '')

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

        return Response(
            {
                'message': 'Autenticacion social exitosa.',
                'created': created,
                'tokens': issue_jwt_pair(user),
                'user': build_user_response(user),
            }
        )
