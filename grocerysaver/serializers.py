"""Serializers de DRF para auth, catalogo, perfil y jobs."""

from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import serializers

from .dataloaders import batch_load_product_qr_codes, get_request_loader
from .models import (
    Address,
    BackgroundJob,
    Cart,
    CartItem,
    Category,
    DeviceSensorReading,
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


def collect_product_ids_for_batch(instance):
    """Extrae ids de producto desde una instancia o coleccion heterogenea."""
    if instance is None:
        return []

    if isinstance(instance, Product):
        return [instance.id]

    if isinstance(instance, QuerySet):
        instance = list(instance)

    product_ids = []
    seen = set()
    for item in instance:
        if isinstance(item, Product):
            product_id = item.id
        else:
            product_id = getattr(item, 'product_id', None)

        if product_id is None or product_id in seen:
            continue

        seen.add(product_id)
        product_ids.append(product_id)

    return product_ids


def get_product_price_row(product, store_id=None):
    """Resuelve el precio del producto para una tienda concreta o la mejor opcion."""
    prices = list(product.prices.all())
    if not prices:
        return None

    if store_id is None:
        return prices[0]

    for price_row in prices:
        if price_row.store_id == store_id:
            return price_row

    return None


class RegisterSerializer(serializers.Serializer):
    """Valida y crea usuarios nuevos junto con su perfil inicial."""

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
    """Recibe el token UUID usado para verificar un correo."""

    token = serializers.UUIDField()


class LoginSerializer(serializers.Serializer):
    """Autentica por email y password y expone el usuario validado."""

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
    """Valida el payload minimo para login social delegado."""

    provider = serializers.ChoiceField(choices=SocialProvider.values)
    id_token = serializers.CharField()

    def validate_provider(self, value):
        if value != SocialProvider.GOOGLE:
            raise serializers.ValidationError('Por ahora solo Google esta habilitado.')
        return value


class LogoutSerializer(serializers.Serializer):
    """Recibe el refresh token que debe invalidarse."""

    refresh = serializers.CharField()


class StoreSerializer(serializers.ModelSerializer):
    """Representacion simple de una tienda."""

    class Meta:
        model = Store
        fields = ['id', 'name']


class AddressSerializer(serializers.ModelSerializer):
    """CRUD de direcciones asociadas al usuario autenticado."""

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
    """Representacion editable de preferencias de notificacion."""

    class Meta:
        model = NotificationPreference
        fields = ['push_enabled', 'email_enabled', 'sms_enabled', 'updated_at']
        read_only_fields = ['updated_at']


class CartItemSerializer(serializers.ModelSerializer):
    """Representacion de lectura de una linea del carrito."""

    product = serializers.SerializerMethodField()
    store = StoreSerializer(read_only=True)
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    has_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id',
            'product',
            'store',
            'quantity',
            'unit_price',
            'line_total',
            'has_price',
            'created_at',
            'updated_at',
        ]

    def get_product(self, obj):
        return ProductSerializer(
            obj.product,
            context=self.context,
        ).data

    def get_unit_price(self, obj):
        price_row = get_product_price_row(obj.product, obj.store_id)
        return str(price_row.price) if price_row is not None else None

    def get_line_total(self, obj):
        price_row = get_product_price_row(obj.product, obj.store_id)
        if price_row is None:
            return None
        return str(price_row.price * obj.quantity)

    def get_has_price(self, obj):
        return get_product_price_row(obj.product, obj.store_id) is not None


class CartSerializer(serializers.ModelSerializer):
    """Representacion del carrito con items y totales agregados."""

    items = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    distinct_products = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id',
            'items',
            'total_items',
            'distinct_products',
            'subtotal',
            'created_at',
            'updated_at',
        ]

    def get_items(self, obj):
        items = list(obj.items.all())
        request = self.context.get('request')
        qr_codes_by_product_id = get_request_loader(
            request,
            'product_qr_codes',
            batch_load_product_qr_codes,
        ).load_many([item.product_id for item in items])
        return CartItemSerializer(
            items,
            many=True,
            context={
                'request': request,
                'qr_codes_by_product_id': qr_codes_by_product_id,
            },
        ).data

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_distinct_products(self, obj):
        return len(obj.items.all())

    def get_subtotal(self, obj):
        subtotal = Decimal('0.00')
        for item in obj.items.all():
            price_row = get_product_price_row(item.product, item.store_id)
            if price_row is None:
                continue
            subtotal += price_row.price * item.quantity
        return str(subtotal)


class CartItemUpsertSerializer(serializers.Serializer):
    """Valida altas de items en el carrito actual."""

    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    store_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        product = (
            Product.objects.select_related('category')
            .prefetch_related('prices__store')
            .filter(id=attrs['product_id'])
            .first()
        )
        if product is None:
            raise serializers.ValidationError({'product_id': 'Producto no encontrado.'})

        store_id = attrs.get('store_id')
        price_row = get_product_price_row(product, store_id)
        if store_id is not None and price_row is None:
            raise serializers.ValidationError({'store_id': 'La tienda no tiene precio registrado para este producto.'})

        attrs['product'] = product
        attrs['resolved_store'] = price_row.store if price_row is not None else None
        return attrs


class CartItemUpdateSerializer(serializers.Serializer):
    """Valida cambios parciales de una linea existente del carrito."""

    quantity = serializers.IntegerField(required=False, min_value=1)
    store_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Debes enviar quantity o store_id.')

        item = self.context['item']
        if 'store_id' in attrs:
            price_row = get_product_price_row(item.product, attrs['store_id'])
            if attrs['store_id'] is not None and price_row is None:
                raise serializers.ValidationError({'store_id': 'La tienda no tiene precio registrado para este producto.'})
            attrs['resolved_store'] = price_row.store if price_row is not None else None

        return attrs


class RaffleSerializer(serializers.ModelSerializer):
    """Expone rifas junto con su estado calculado."""

    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Raffle
        fields = ['id', 'title', 'description', 'starts_at', 'ends_at', 'is_active']

    def get_is_active(self, obj):
        return obj.is_active


class CategorySerializer(serializers.ModelSerializer):
    """Serializa categorias con URL absoluta de imagen cuando existe."""

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
    """Serializa productos y resuelve su QR usando batching por request."""

    category = CategorySerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_image = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    qr_code = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'brand', 'description', 'image', 'category', 'category_name', 'category_image', 'qr_code']

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    def get_category_image(self, obj):
        category = getattr(obj, 'category', None)
        if category is None or not category.image:
            return None

        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(category.image.url)
        return category.image.url

    def get_qr_code(self, obj):
        qr_codes_by_product_id = self.context.get('qr_codes_by_product_id')
        if qr_codes_by_product_id is not None:
            return qr_codes_by_product_id.get(obj.id)

        request = self.context.get('request')
        loader = get_request_loader(request, 'product_qr_codes', batch_load_product_qr_codes)
        batch_product_ids = collect_product_ids_for_batch(getattr(self.root, 'instance', None)) or [obj.id]
        return loader.load(obj.id, batch_product_ids)


class ProductPriceSerializer(serializers.ModelSerializer):
    """Serializa un precio de producto asociado a una tienda."""

    store = StoreSerializer(read_only=True)

    class Meta:
        model = ProductPrice
        fields = ['store', 'price', 'updated_at']


class ProductCodeSerializer(serializers.ModelSerializer):
    """Serializa codigos asociados a un producto."""

    class Meta:
        model = ProductCode
        fields = ['code', 'code_type']


class ProductExportJobCreateSerializer(serializers.Serializer):
    """Valida filtros opcionales y formato para exportar productos."""

    format = serializers.ChoiceField(choices=['txt', 'csv', 'pdf'], required=False, default='csv')
    category_id = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False, allow_blank=True, max_length=120)

    def validate_category_id(self, value):
        if not Category.objects.filter(id=value).exists():
            raise serializers.ValidationError('Categoria no encontrada.')
        return value


class BackgroundJobSerializer(serializers.ModelSerializer):
    """Expone el estado persistido de un trabajo en background."""

    result_url = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = BackgroundJob
        fields = [
            'job_id',
            'job_type',
            'status',
            'payload',
            'result',
            'result_url',
            'error',
            'attempts',
            'created_by',
            'created_at',
            'started_at',
            'finished_at',
        ]
        read_only_fields = fields

    def get_result_url(self, obj):
        file_path = (obj.result or {}).get('file_path')
        if not file_path:
            return None

        relative_media_path = file_path.replace('\\', '/').lstrip('/')
        url = f"{settings.MEDIA_URL.rstrip('/')}/{relative_media_path}"
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_created_by(self, obj):
        if obj.created_by is None:
            return None
        return {
            'id': obj.created_by_id,
            'email': obj.created_by.email,
        }


class ProductScanSerializer(serializers.Serializer):
    """Valida el payload usado para escanear o crear productos por codigo."""

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
    """Serializa ofertas con ahorro y descuento calculados."""

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
    """Representacion de lectura para solicitudes de cambio de rol."""

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
    """Valida y crea una nueva solicitud de cambio de rol."""

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


class SensorVectorSerializer(serializers.Serializer):
    """Valida un vector tridimensional de sensores."""

    x = serializers.FloatField()
    y = serializers.FloatField()
    z = serializers.FloatField()


class DeviceSensorReadingSerializer(serializers.ModelSerializer):
    """Serializa lecturas de sensores del dispositivo para entrada y salida."""

    accelerometer = SensorVectorSerializer(write_only=True)
    gyroscope = SensorVectorSerializer(write_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = DeviceSensorReading
        fields = [
            'id',
            'user_id',
            'accelerometer',
            'gyroscope',
            'accelerometer_x',
            'accelerometer_y',
            'accelerometer_z',
            'gyroscope_x',
            'gyroscope_y',
            'gyroscope_z',
            'is_shaking',
            'captured_at',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'user_id',
            'accelerometer_x',
            'accelerometer_y',
            'accelerometer_z',
            'gyroscope_x',
            'gyroscope_y',
            'gyroscope_z',
            'created_at',
        ]

    def create(self, validated_data):
        accelerometer = validated_data.pop('accelerometer')
        gyroscope = validated_data.pop('gyroscope')

        return DeviceSensorReading.objects.create(
            user=self.context['request'].user,
            accelerometer_x=accelerometer['x'],
            accelerometer_y=accelerometer['y'],
            accelerometer_z=accelerometer['z'],
            gyroscope_x=gyroscope['x'],
            gyroscope_y=gyroscope['y'],
            gyroscope_z=gyroscope['z'],
            **validated_data,
        )

    def to_representation(self, instance):
        payload = super().to_representation(instance)
        payload['accelerometer'] = {
            'x': payload.pop('accelerometer_x'),
            'y': payload.pop('accelerometer_y'),
            'z': payload.pop('accelerometer_z'),
        }
        payload['gyroscope'] = {
            'x': payload.pop('gyroscope_x'),
            'y': payload.pop('gyroscope_y'),
            'z': payload.pop('gyroscope_z'),
        }
        return payload


class ProfileAvatarSerializer(serializers.ModelSerializer):
    """Actualiza solo el archivo de avatar del perfil autenticado."""

    class Meta:
        model = UserProfile
        fields = ['avatar']

    def update(self, instance, validated_data):
        new_avatar = validated_data.get('avatar')
        if new_avatar is not None and instance.avatar:
            instance.avatar.delete(save=False)
        return super().update(instance, validated_data)
