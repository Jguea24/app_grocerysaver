"""Rutas reservadas para el dominio de alertas."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlertViewSet

router = DefaultRouter()
router.register('alerts', AlertViewSet, basename='alert')

urlpatterns = [
    path('', include(router.urls)),
]
