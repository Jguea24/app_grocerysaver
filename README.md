# GrocerySaver API

Backend API para GrocerySaver construido con Django, Django REST Framework, JWT y PostgreSQL.

## Caracteristicas

- Autenticacion con JWT
- Registro, login, verificacion de correo y social login
- Catalogo de tiendas, categorias, productos, ofertas y comparacion de precios
- Escaneo de productos por codigo
- Clima con Open-Meteo
- Catalogo geografico de Ecuador
- Cache para consultas repetitivas
- Prevencion de N+1 con batching/caching por request
- Cola de trabajos para exportacion de productos a CSV

## Stack

- Python 3.12
- Django 6
- Django REST Framework
- PostgreSQL
- SimpleJWT

## Estructura

```text
api_grocerysaver/     configuracion del proyecto Django
grocerysaver/         app principal
media/                archivos subidos y exportaciones
venv/                 entorno virtual local
manage.py
```

## Requisitos

- PostgreSQL levantado en `localhost:5432`
- Base de datos `grocerysaver`
- Usuario `grocery_user`
- Entorno virtual en `.\venv`

La configuracion actual del proyecto usa estos valores en `api_grocerysaver/settings.py`:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "grocerysaver",
        "USER": "grocery_user",
        "PASSWORD": "admin1234",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

## Instalacion

Activar entorno virtual:

```powershell
.\venv\Scripts\Activate.ps1
```

Aplicar migraciones:

```powershell
.\venv\Scripts\python.exe manage.py migrate
```

Levantar servidor:

```powershell
.\venv\Scripts\python.exe manage.py runserver
```

La API queda disponible en:

```text
http://127.0.0.1:8000/api/
```

## Cache

El proyecto usa cache de Django para endpoints repetitivos.

- Por defecto: `LocMemCache`
- Opcional: Redis si defines `REDIS_URL`

Variables soportadas:

- `CACHE_DEFAULT_TTL`
- `CATALOG_CACHE_TTL`
- `WEATHER_CACHE_TTL`
- `GEO_CACHE_TTL`
- `RAFFLE_CACHE_TTL`
- `REDIS_URL`

Si `REDIS_URL` existe, Django usa `RedisCache`. Si no, usa memoria local.

## DataLoader / N+1

El proyecto incluye batching + cache por request para evitar N+1 al resolver relaciones repetidas, especialmente QR codes de productos.

Archivos relacionados:

- `grocerysaver/dataloaders.py`
- `grocerysaver/serializers.py`
- `grocerysaver/views.py`

## Job Queue

Se implemento una cola de trabajos basada en base de datos para exportar productos a CSV.

### Endpoints

Encolar exportacion:

```http
POST /api/jobs/export-products/
Authorization: Bearer <token>
Content-Type: application/json
```

Body opcional:

```json
{
  "category_id": 1,
  "search": "leche"
}
```

Consultar estado:

```http
GET /api/jobs/<job_id>/
Authorization: Bearer <token>
```

### Worker

Para procesar jobs debes correr un worker en otra terminal:

```powershell
.\venv\Scripts\python.exe manage.py run_job_worker
```

Procesar solo un job:

```powershell
.\venv\Scripts\python.exe manage.py run_job_worker --once
```

Los archivos CSV generados se guardan en:

```text
media/job_exports/
```

## Endpoints principales

### Auth

- `GET /api/auth/roles/`
- `POST /api/auth/register/`
- `POST /api/auth/verify-email/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- `POST /api/auth/social-login/`

### Catalogo

- `GET /api/stores/`
- `GET /api/categories/`
- `GET /api/products/`
- `POST /api/products/scan/`
- `GET /api/offers/`
- `GET /api/compare-prices/`

### Geo y clima

- `GET /api/weather/`
- `GET /api/geo/ecuador/`
- `GET /api/geo/ecuador/provinces/`
- `GET /api/geo/ecuador/cantons/`

### Perfil

- `GET/POST /api/profile/addresses/`
- `PATCH/DELETE /api/profile/addresses/<address_id>/`
- `GET/PATCH /api/profile/notifications/`
- `GET/POST /api/profile/role-change-requests/`

## Testing

Correr tests:

```powershell
.\venv\Scripts\python.exe manage.py test grocerysaver.tests
```

Estado actual:

- la suite completa pasa

## Flutter

Para Android Emulator usa:

```text
http://10.0.2.2:8000/api/
```

Para celular fisico usa la IP local de tu PC.

## Archivos importantes

- `api_grocerysaver/settings.py`
- `grocerysaver/models.py`
- `grocerysaver/views.py`
- `grocerysaver/serializers.py`
- `grocerysaver/services.py`
- `grocerysaver/cache_utils.py`
- `grocerysaver/dataloaders.py`
- `grocerysaver/job_queue.py`

