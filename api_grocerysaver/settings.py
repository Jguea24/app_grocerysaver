"""Configuracion principal de Django para GrocerySaver."""  # Describe el proposito del archivo.

import os  # Permite leer variables de entorno del sistema.
from pathlib import Path  # Permite construir rutas de archivos de forma segura.

BASE_DIR = Path(__file__).resolve().parent.parent  # Calcula la carpeta raiz del proyecto.

SECRET_KEY = 'django-insecure-@992)6_tn_hk3k)6f0g6(cy*e*98#vqcm+t)q!_cbr9_ncbjon'  # Clave secreta usada por Django.
DEBUG = True  # Activa modo desarrollo con mensajes detallados.

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "10.0.2.2"]  # Hosts permitidos para acceder a la API.

INSTALLED_APPS = [  # Lista de aplicaciones habilitadas en Django.
    'django.contrib.admin',  # Panel administrativo de Django.
    'django.contrib.auth',  # Sistema de autenticacion y usuarios.
    'django.contrib.contenttypes',  # Soporte para tipos de contenido genericos.
    'django.contrib.sessions',  # Manejo de sesiones del framework.
    'django.contrib.messages',  # Sistema de mensajes temporales.
    'django.contrib.staticfiles',  # Servir y gestionar archivos estaticos.
    'corsheaders',  # Permite configurar CORS para clientes externos.
    'rest_framework',  # Django REST Framework para construir la API.
    'rest_framework_simplejwt',  # JWT para autenticacion basada en tokens.
    'rest_framework_simplejwt.token_blacklist',  # Blacklist de tokens refresh invalidados.
    'users',  # Dominio modular de identidad y perfil.
    'products',  # Dominio modular de catalogo.
    'inventory',  # Dominio modular de inventario y compras.
    'alerts',  # Dominio modular de alertas.
    'prices',  # Dominio modular de precios.
    'orders',  # Dominio modular de ordenes y checkout base.
    'grocerysaver',  # Aplicacion principal del proyecto.
]  # Fin de aplicaciones instaladas.

MIDDLEWARE = [  # Cadena de middlewares ejecutados en cada request.
    'django.middleware.security.SecurityMiddleware',  # Agrega cabeceras y protecciones basicas.
    'corsheaders.middleware.CorsMiddleware',  # Procesa reglas CORS antes que CommonMiddleware.
    'django.contrib.sessions.middleware.SessionMiddleware',  # Habilita sesiones por request.
    'django.middleware.common.CommonMiddleware',  # Normaliza URLs y ajustes comunes.
    'django.middleware.csrf.CsrfViewMiddleware',  # Proteccion CSRF para formularios y sesiones.
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # Asocia el usuario autenticado al request.
    'django.contrib.messages.middleware.MessageMiddleware',  # Habilita mensajes en el ciclo request/response.
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # Evita que el sitio sea embebido en iframes.
]  # Fin de middlewares.

ROOT_URLCONF = 'api_grocerysaver.urls'  # Archivo principal de rutas del proyecto.

TEMPLATES = [  # Configuracion del motor de plantillas de Django.
    {  # Inicio de la configuracion del backend de templates.
        'BACKEND': 'django.template.backends.django.DjangoTemplates',  # Backend oficial de templates.
        'DIRS': [BASE_DIR / 'templates'],  # Carpeta global de plantillas personalizadas.
        'APP_DIRS': True,  # Busca templates dentro de cada app instalada.
        'OPTIONS': {  # Opciones adicionales del motor de templates.
            'context_processors': [  # Procesadores que agregan variables globales al contexto.
                'django.template.context_processors.request',  # Expone el objeto request en templates.
                'django.contrib.auth.context_processors.auth',  # Expone datos de autenticacion.
                'django.contrib.messages.context_processors.messages',  # Expone mensajes del framework.
            ],  # Fin de context processors.
        },  # Fin de opciones del motor de templates.
    },  # Fin de la configuracion del backend de templates.
]  # Fin de configuracion de templates.

WSGI_APPLICATION = 'api_grocerysaver.wsgi.application'  # Punto de entrada WSGI para despliegues tradicionales.

# Configuracion local por defecto para PostgreSQL.
DATABASES = {  # Diccionario de conexiones a base de datos.
    'default': {  # Conexion principal usada por Django.
        'ENGINE': 'django.db.backends.postgresql',  # Motor de base de datos PostgreSQL.
        'NAME': 'grocerysaver',  # Nombre de la base de datos.
        'USER': 'grocery_user',  # Usuario de la base de datos.
        'PASSWORD': 'admin1234',  # Contrasena del usuario de la base de datos.
        'HOST': 'localhost',  # Host donde corre PostgreSQL.
        'PORT': '5432',  # Puerto por defecto de PostgreSQL.
    }  # Fin de la conexion por defecto.
}  # Fin de configuracion de base de datos.

AUTH_PASSWORD_VALIDATORS = [  # Validadores aplicados a las contrasenas de usuarios.
    {  # Validador 1.
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',  # Evita passwords parecidas a datos del usuario.
    },  # Fin del validador 1.
    {  # Validador 2.
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',  # Exige longitud minima.
    },  # Fin del validador 2.
    {  # Validador 3.
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',  # Bloquea passwords comunes.
    },  # Fin del validador 3.
    {  # Validador 4.
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',  # Bloquea passwords solo numericas.
    },  # Fin del validador 4.
]  # Fin de validadores de password.

LANGUAGE_CODE = 'en-us'  # Idioma base del proyecto.
TIME_ZONE = 'UTC'  # Zona horaria configurada para el backend.
USE_I18N = True  # Activa soporte de internacionalizacion.
USE_TZ = True  # Guarda fechas con zona horaria.

STATIC_URL = 'static/'  # URL base para archivos estaticos.
MEDIA_URL = '/media/'  # URL base para archivos subidos por usuarios.
MEDIA_ROOT = BASE_DIR / 'media'  # Carpeta fisica donde se guardan los archivos media.
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'  # Tipo por defecto para claves primarias automaticas.

# Autenticacion global via JWT para la API.
REST_FRAMEWORK = {  # Configuracion global de Django REST Framework.
    'DEFAULT_AUTHENTICATION_CLASSES': (  # Clases de autenticacion por defecto.
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # Autenticacion mediante JWT.
    ),  # Fin de clases de autenticacion.
    'DEFAULT_PERMISSION_CLASSES': (  # Permisos por defecto para todos los endpoints.
        'rest_framework.permissions.IsAuthenticated',  # Exige usuario autenticado salvo override.
    ),  # Fin de clases de permiso.
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.openapi.AutoSchema',  # Schema OpenAPI base para documentacion.
}  # Fin de configuracion de DRF.

CORS_ALLOW_ALL_ORIGINS = True  # Permite solicitudes desde cualquier origen en desarrollo.

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Imprime correos en consola en vez de enviarlos.
DEFAULT_FROM_EMAIL = 'no-reply@grocerysaver.local'  # Remitente por defecto para emails del sistema.
EMAIL_VERIFICATION_TOKEN_TTL_HOURS = 24  # Horas de validez para tokens de verificacion por email.
GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '').strip()  # Client ID OAuth usado para validar Google Sign-In.
AUTO_VERIFY_EMAIL_ON_REGISTER = os.getenv('AUTO_VERIFY_EMAIL_ON_REGISTER', 'true' if DEBUG else 'false').strip().lower() in {'1', 'true', 'yes', 'on'}  # Permite autoactivar usuarios al registrarse en desarrollo.
AUTO_SEED_EXPIRING_INVENTORY = os.getenv('AUTO_SEED_EXPIRING_INVENTORY', 'true' if DEBUG else 'false').strip().lower() in {'1', 'true', 'yes', 'on'}  # Carga inventario demo por caducar para usuarios nuevos en desarrollo.

# TTLs configurables para la capa de cache de Django.
CACHE_DEFAULT_TTL = int(os.getenv('CACHE_DEFAULT_TTL', '120'))  # TTL general por defecto en segundos.
CATALOG_CACHE_TTL = int(os.getenv('CATALOG_CACHE_TTL', str(CACHE_DEFAULT_TTL)))  # TTL del catalogo.
WEATHER_CACHE_TTL = int(os.getenv('WEATHER_CACHE_TTL', '600'))  # TTL de respuestas del clima.
RAFFLE_CACHE_TTL = int(os.getenv('RAFFLE_CACHE_TTL', '60'))  # TTL de rifas activas.

REDIS_URL = os.getenv('REDIS_URL', '').strip()  # URL de Redis tomada del entorno si existe.

if REDIS_URL:  # Usa Redis cuando hay una URL configurada.
    # En produccion o entornos compartidos se puede usar Redis.
    CACHES = {  # Configuracion de cache usando Redis.
        'default': {  # Cache principal del proyecto.
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',  # Backend Redis de Django.
            'LOCATION': REDIS_URL,  # Direccion de conexion a Redis.
            'TIMEOUT': CACHE_DEFAULT_TTL,  # TTL por defecto para entradas de cache.
            'KEY_PREFIX': 'grocerysaver',  # Prefijo para evitar colisiones de claves.
        }  # Fin de cache por defecto en Redis.
    }  # Fin de configuracion Redis.
else:  # Usa una cache en memoria local si no hay Redis.
    # Fallback simple para desarrollo cuando Redis no esta disponible.
    CACHES = {  # Configuracion de cache en memoria local.
        'default': {  # Cache principal del proyecto.
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',  # Backend de memoria en proceso.
            'LOCATION': 'grocerysaver-local-cache',  # Nombre interno de la cache local.
            'TIMEOUT': CACHE_DEFAULT_TTL,  # TTL por defecto para entradas de cache.
        }  # Fin de cache por defecto local.
    }  # Fin de configuracion LocMem.


INVENTORY_EXPIRY_ALERT_DAYS = int(os.getenv('INVENTORY_EXPIRY_ALERT_DAYS', '3'))  # Dias previos para alertas de caducidad.





