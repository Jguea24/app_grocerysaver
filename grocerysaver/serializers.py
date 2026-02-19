from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import Role, SocialProvider, UserProfile
from .services import build_unique_username_from_email, validate_password_or_raise


User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    role = serializers.CharField(max_length=50)
    address = serializers.CharField(max_length=255)
    birth_date = serializers.DateField()

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Ya existe una cuenta con este email.')
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Ya existe una cuenta con este username.')
        return value

    def validate_birth_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('La fecha de nacimiento no puede ser futura.')
        return value

    def validate_role(self, value):
        if not Role.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError('Rol invalido. Usa un rol existente.')
        return value.lower()

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Las contrasenas no coinciden.'})

        try:
            validate_password_or_raise(attrs['password'])
        except Exception as exc:  # pragma: no cover
            raise serializers.ValidationError({'password': exc.messages if hasattr(exc, 'messages') else [str(exc)]}) from exc

        return attrs

    def create(self, validated_data):
        username = validated_data.get('username', '')
        email = validated_data['email'].lower()
        password = validated_data['password']
        first_name = validated_data.get('first_name', '')
        last_name = validated_data.get('last_name', '')
        role_name = validated_data['role']
        address = validated_data['address']
        birth_date = validated_data['birth_date']
        role = Role.objects.get(name__iexact=role_name)

        user = User.objects.create_user(
            username=username or build_unique_username_from_email(email),
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=False,
        )

        UserProfile.objects.create(
            user=user,
            role=role,
            address=address,
            birth_date=birth_date,
        )

        return user


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.UUIDField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower()
        password = attrs['password']

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise serializers.ValidationError('Credenciales invalidas.')

        if not user.is_active:
            raise serializers.ValidationError('Debes verificar tu correo antes de iniciar sesion.')

        authenticated_user = authenticate(username=user.username, password=password)
        if authenticated_user is None:
            raise serializers.ValidationError('Credenciales invalidas.')

        attrs['user'] = authenticated_user
        return attrs


class SocialLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=SocialProvider.values)
    provider_user_id = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
