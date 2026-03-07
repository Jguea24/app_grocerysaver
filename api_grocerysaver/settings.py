"""Configuracion principal de Django para GrocerySaver."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-@992)6_tn_hk3k)6f0g6(cy*e*98#vqcm+t)q!_cbr9_ncbjon'
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "10.0.2.2"]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'grocerysaver',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'api_grocerysaver.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'api_grocerysaver.wsgi.application'

# Configuracion local por defecto para PostgreSQL.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'grocerysaver',
        'USER': 'grocery_user',
        'PASSWORD': 'admin1234',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Autenticacion global via JWT para la API.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

CORS_ALLOW_ALL_ORIGINS = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'no-reply@grocerysaver.local'
EMAIL_VERIFICATION_TOKEN_TTL_HOURS = 24

# TTLs configurables para la capa de cache de Django.
CACHE_DEFAULT_TTL = int(os.getenv('CACHE_DEFAULT_TTL', '120'))
CATALOG_CACHE_TTL = int(os.getenv('CATALOG_CACHE_TTL', str(CACHE_DEFAULT_TTL)))
WEATHER_CACHE_TTL = int(os.getenv('WEATHER_CACHE_TTL', '600'))
GEO_CACHE_TTL = int(os.getenv('GEO_CACHE_TTL', '3600'))
RAFFLE_CACHE_TTL = int(os.getenv('RAFFLE_CACHE_TTL', '60'))

REDIS_URL = os.getenv('REDIS_URL', '').strip()

if REDIS_URL:
    # En produccion o entornos compartidos se puede usar Redis.
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'TIMEOUT': CACHE_DEFAULT_TTL,
            'KEY_PREFIX': 'grocerysaver',
        }
    }
else:
    # Fallback simple para desarrollo cuando Redis no esta disponible.
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'grocerysaver-local-cache',
            'TIMEOUT': CACHE_DEFAULT_TTL,
        }
    }
