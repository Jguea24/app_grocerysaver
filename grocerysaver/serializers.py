from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Address,
    Category,
    NotificationPreference,
    Offer,
    Product,
    ProductCode,
    ProductCodeType,
    ProductPrice,
    Raffle,
    Role,
    RoleChangeRequest,
    RoleChangeRequestStatus,
    SocialProvider,
    Store,
    UserProfile,
)
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


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['id', 'name']


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id',
            'label',
            'contact_name',
            'phone',
            'line1',
            'line2',
            'city',
            'is_default',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ['push_enabled', 'email_enabled', 'sms_enabled', 'updated_at']
        read_only_fields = ['updated_at']


class RaffleSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Raffle
        fields = ['id', 'title', 'description', 'starts_at', 'ends_at', 'is_active']

    def get_is_active(self, obj):
        return obj.is_active


class CategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'image']

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'brand', 'description', 'image', 'category']

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class ProductPriceSerializer(serializers.ModelSerializer):
    store = StoreSerializer(read_only=True)

    class Meta:
        model = ProductPrice
        fields = ['store', 'price', 'updated_at']


class ProductCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCode
        fields = ['code', 'code_type']


class ProductScanSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=120)
    code_type = serializers.ChoiceField(choices=ProductCodeType.values, required=False)
    category_id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False, max_length=120)
    brand = serializers.CharField(required=False, allow_blank=True, max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    store_id = serializers.IntegerField(required=False)
    price = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
    )

    def validate_code(self, value):
        code = value.strip()
        if not code:
            raise serializers.ValidationError('El codigo no puede estar vacio.')
        return code

    def validate(self, attrs):
        has_store = 'store_id' in attrs
        has_price = 'price' in attrs
        if has_store != has_price:
            raise serializers.ValidationError('Debes enviar store_id y price juntos.')
        return attrs


class OfferSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    store = StoreSerializer(read_only=True)
    is_active = serializers.SerializerMethodField()
    savings = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = [
            'id',
            'product',
            'store',
            'normal_price',
            'offer_price',
            'savings',
            'discount_percent',
            'starts_at',
            'ends_at',
            'is_active',
            'updated_at',
        ]

    def get_is_active(self, obj):
        return obj.is_active

    def get_savings(self, obj):
        return str(obj.savings)

    def get_discount_percent(self, obj):
        if obj.normal_price == 0:
            return '0.00'
        discount = ((obj.normal_price - obj.offer_price) / obj.normal_price) * 100
        return f'{discount:.2f}'


class RoleChangeRequestSerializer(serializers.ModelSerializer):
    current_role = serializers.SerializerMethodField()
    requested_role = serializers.SerializerMethodField()

    class Meta:
        model = RoleChangeRequest
        fields = [
            'id',
            'current_role',
            'requested_role',
            'reason',
            'status',
            'admin_notes',
            'created_at',
            'updated_at',
            'resolved_at',
        ]

    def get_current_role(self, obj):
        if obj.current_role is None:
            return None
        return obj.current_role.name

    def get_requested_role(self, obj):
        return obj.requested_role.name


class RoleChangeRequestCreateSerializer(serializers.Serializer):
    requested_role = serializers.CharField(max_length=50)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate_requested_role(self, value):
        role = Role.objects.filter(name__iexact=value).first()
        if role is None:
            raise serializers.ValidationError('Rol solicitado invalido.')
        return role

    def validate(self, attrs):
        user = self.context['request'].user
        requested_role = attrs['requested_role']
        current_role = getattr(getattr(user, 'profile', None), 'role', None)

        if current_role and current_role.id == requested_role.id:
            raise serializers.ValidationError({'requested_role': 'Ya tienes ese rol.'})

        has_pending = RoleChangeRequest.objects.filter(
            user=user,
            status=RoleChangeRequestStatus.PENDING,
        ).exists()
        if has_pending:
            raise serializers.ValidationError('Ya tienes una solicitud pendiente.')

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        current_role = getattr(getattr(user, 'profile', None), 'role', None)

        return RoleChangeRequest.objects.create(
            user=user,
            current_role=current_role,
            requested_role=validated_data['requested_role'],
            reason=validated_data.get('reason', ''),
        )
