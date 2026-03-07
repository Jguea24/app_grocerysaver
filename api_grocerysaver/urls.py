"""Rutas raiz del proyecto y exposicion del prefijo /api/."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('grocerysaver.urls')),
]

if settings.DEBUG:
    # Sirve archivos media directamente en desarrollo local.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
