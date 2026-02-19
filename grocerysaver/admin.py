from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import EmailVerificationToken, Role, UserProfile

User = get_user_model()


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


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
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'profile__address', 'profile__role__name')
    list_select_related = ('profile',)

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


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'is_used', 'expires_at', 'created_at')
    list_filter = ('is_used',)
    search_fields = ('user__email', 'user__username', 'token')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'birth_date', 'address', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__username', 'role__name', 'address')
