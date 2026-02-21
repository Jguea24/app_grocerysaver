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
    Product,
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
    ProductPriceSerializer,
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
                        'path': '/api/compare-prices/',
                        'method': 'GET',
                        'auth_required': False,
                        'query_params': ['product_id', 'product'],
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
