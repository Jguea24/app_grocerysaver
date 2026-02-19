from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailVerificationToken, Role, SocialAccount
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    SocialLoginSerializer,
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
