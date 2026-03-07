"""Helpers para cachear respuestas e invalidar namespaces publicos."""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)

CACHE_NS_CATEGORIES = 'categories'
CACHE_NS_COMPARE_PRICES = 'compare_prices'
CACHE_NS_ECUADOR_CANTONS = 'ecuador_cantons'
CACHE_NS_ECUADOR_GEO = 'ecuador_geo'
CACHE_NS_ECUADOR_PROVINCES = 'ecuador_provinces'
CACHE_NS_OFFERS = 'offers'
CACHE_NS_PRODUCTS = 'products'
CACHE_NS_RAFFLES = 'raffles'
CACHE_NS_ROLES = 'roles'
CACHE_NS_STORES = 'stores'
CACHE_NS_WEATHER = 'weather'

DEFAULT_CACHE_TTL = getattr(settings, 'CACHE_DEFAULT_TTL', 120)
CATALOG_CACHE_TTL = getattr(settings, 'CATALOG_CACHE_TTL', DEFAULT_CACHE_TTL)
GEO_CACHE_TTL = getattr(settings, 'GEO_CACHE_TTL', 3600)
RAFFLE_CACHE_TTL = getattr(settings, 'RAFFLE_CACHE_TTL', 60)
WEATHER_CACHE_TTL = getattr(settings, 'WEATHER_CACHE_TTL', 600)

VERSION_KEY_TEMPLATE = 'cache_namespace_version:{namespace}'
CATALOG_NAMESPACES = (
    CACHE_NS_ROLES,
    CACHE_NS_STORES,
    CACHE_NS_CATEGORIES,
    CACHE_NS_PRODUCTS,
    CACHE_NS_OFFERS,
    CACHE_NS_COMPARE_PRICES,
)


def _get_version_key(namespace):
    """Construye la clave interna usada para versionar un namespace."""
    return VERSION_KEY_TEMPLATE.format(namespace=namespace)


def get_cache_version(namespace):
    """Obtiene o inicializa la version actual de un namespace de cache."""
    version_key = _get_version_key(namespace)
    version = cache.get(version_key)
    if version is None:
        cache.add(version_key, 1, timeout=None)
        version = cache.get(version_key) or 1
    return int(version)


def bump_cache_version(namespace):
    """Incrementa la version para invalidar todas las claves del namespace."""
    version_key = _get_version_key(namespace)
    if cache.get(version_key) is None:
        cache.set(version_key, 2, timeout=None)
        return 2

    try:
        return cache.incr(version_key)
    except ValueError:
        cache.set(version_key, 2, timeout=None)
        return 2


def build_cache_key(namespace, **params):
    """Genera una clave estable a partir del namespace y sus parametros."""
    version = get_cache_version(namespace)
    normalized = '|'.join(f'{key}={params[key]}' for key in sorted(params))
    params_digest = hashlib.md5(normalized.encode('utf-8')).hexdigest()
    return f'{namespace}:v{version}:{params_digest}'


def get_cached_payload(namespace, builder, params=None, ttl=None):
    """Recupera un payload cacheado o lo construye si aun no existe."""
    cache_key = build_cache_key(namespace, **(params or {}))
    payload = cache.get(cache_key)
    if payload is not None:
        logger.info('cache hit namespace=%s key=%s', namespace, cache_key)
        return payload, True

    payload = builder()
    cache.set(cache_key, payload, timeout=ttl or DEFAULT_CACHE_TTL)
    logger.info('cache miss namespace=%s key=%s ttl=%s', namespace, cache_key, ttl or DEFAULT_CACHE_TTL)
    return payload, False


def invalidate_catalog_caches():
    """Invalida todos los namespaces asociados al catalogo publico."""
    for namespace in CATALOG_NAMESPACES:
        bump_cache_version(namespace)


def invalidate_raffle_cache():
    """Invalida el namespace de rifas activas."""
    bump_cache_version(CACHE_NS_RAFFLES)
