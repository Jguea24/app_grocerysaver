from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

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
    Store,
    UserProfile,
)

User = get_user_model()


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fk_name = 'user'
    can_delete = False
    max_num = 1
    fields = ('role', 'address', 'birth_date')

    def get_extra(self, request, obj=None, **kwargs):
        if obj is not None and hasattr(obj, 'profile'):
            return 0
        return 1


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'role',
        'address',
        'birth_date',
        'actualizar_datos',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'profile__address', 'profile__role__name')
    list_select_related = ('profile',)
    inlines = (UserProfileInline,)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('profile')

    @admin.display(description='Address')
    def address(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.address if profile else ''

    @admin.display(description='Role')
    def role(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.role.name if profile and profile.role else ''

    @admin.display(description='Birth Date')
    def birth_date(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.birth_date if profile else None

    @admin.display(description='Actualizar')
    def actualizar_datos(self, obj):
        url = reverse(
            f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change',
            args=[obj.pk],
        )
        return format_html('<a class="button" href="{}">Actualizar</a>', url)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'image_preview', 'created_at')
    search_fields = ('name',)
    fields = ('name', 'image', 'image_preview')
    readonly_fields = ('image_preview',)

    @admin.display(description='Image')
    def image_preview(self, obj):
        if not obj.image:
            return '-'
        return format_html('<img src="{}" style="height:40px; width:auto; border-radius:4px;" />', obj.image.url)


class ProductPriceInline(admin.TabularInline):
    model = ProductPrice
    extra = 0
    fields = ('store', 'price', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'short_description', 'image_preview', 'best_price', 'stores_with_prices', 'created_at')
    list_filter = ('category', 'prices__store')
    search_fields = ('name', 'brand', 'description', 'category__name')
    inlines = (ProductPriceInline,)
    fields = ('category', 'name', 'brand', 'description', 'image', 'image_preview')
    readonly_fields = ('image_preview',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('category').prefetch_related('prices__store')

    @admin.display(description='Best Price')
    def best_price(self, obj):
        prices = list(obj.prices.all())
        if not prices:
            return '-'
        return min(prices, key=lambda price_row: price_row.price).price

    @admin.display(description='Image')
    def image_preview(self, obj):
        if not obj.image:
            return '-'
        return format_html('<img src="{}" style="height:40px; width:auto; border-radius:4px;" />', obj.image.url)

    @admin.display(description='Description')
    def short_description(self, obj):
        if not obj.description:
            return '-'
        return obj.description[:60] + ('...' if len(obj.description) > 60 else '')

    @admin.display(description='Stores / Prices')
    def stores_with_prices(self, obj):
        prices = list(obj.prices.all())
        if not prices:
            return '-'
        return ', '.join(f'{price_row.store.name}: {price_row.price}' for price_row in prices)


@admin.register(ProductPrice)
class ProductPriceAdmin(admin.ModelAdmin):
    list_display = ('product', 'category', 'store', 'price', 'updated_at')
    list_filter = ('store', 'product__category')
    search_fields = ('product__name', 'product__brand', 'store__name')
    list_select_related = ('product__category', 'store')

    @admin.display(description='Category')
    def category(self, obj):
        return obj.product.category.name


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'is_used', 'expires_at', 'created_at')
    list_filter = ('is_used',)
    search_fields = ('user__email', 'user__username', 'token')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'birth_date', 'address', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__username', 'role__name', 'address')


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'contact_name', 'phone', 'city', 'is_default', 'updated_at')
    list_filter = ('is_default', 'city')
    search_fields = ('user__email', 'user__username', 'contact_name', 'phone', 'city', 'line1')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'push_enabled', 'email_enabled', 'sms_enabled', 'updated_at')
    search_fields = ('user__email', 'user__username')


@admin.register(Raffle)
class RaffleAdmin(admin.ModelAdmin):
    list_display = ('title', 'starts_at', 'ends_at', 'is_active')
    search_fields = ('title', 'description')


@admin.register(RoleChangeRequest)
class RoleChangeRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_role', 'requested_role', 'status', 'created_at', 'resolved_at')
    list_filter = ('status', 'requested_role')
    search_fields = ('user__email', 'user__username', 'reason', 'admin_notes')

    def save_model(self, request, obj, form, change):
        if obj.status == 'pending':
            obj.resolved_at = None
        elif obj.resolved_at is None:
            obj.resolved_at = timezone.now()

        super().save_model(request, obj, form, change)

        if obj.status == 'approved':
            profile = getattr(obj.user, 'profile', None)
            if profile is not None and profile.role_id != obj.requested_role_id:
                profile.role = obj.requested_role
                profile.save(update_fields=['role'])
