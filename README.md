# GrocerySaver API

Backend API de GrocerySaver construido con Django, Django REST Framework, JWT y PostgreSQL.

## Caracteristicas

- Arquitectura modular por apps: `users`, `products`, `prices`, `inventory`, `alerts`, `orders`.
- Autenticacion con JWT (registro, login, logout, perfil, login social Google).
- Catalogo de productos, categorias, tiendas, ofertas y comparador de precios.
- Carrito persistido por usuario.
- Flujo de compra completo: `Carrito -> Checkout -> Payment -> Order -> Shipment`.
- Inventario del hogar con fecha de caducidad.
- Alertas automaticas por caducidad.
- Historial de precios y comparacion de precios.
- Exportacion de productos por jobs en segundo plano.
- Documentacion viva en `/api/docs/` y esquema OpenAPI en `/api/schema/`.

## Stack

- Python 3.12
- Django 6
- Django REST Framework
- PostgreSQL
- SimpleJWT

## Estructura

```text
api_grocerysaver/     configuracion del proyecto
alerts/               dominio de alertas
grocerysaver/         app base y endpoints generales
inventory/            inventario y carrito
orders/               checkout, pagos, ordenes, envios
prices/               tiendas, ofertas, comparador, historial
products/             productos, categorias, compras
users/                autenticacion y perfil
manage.py
```

## Requisitos

- PostgreSQL en `localhost:5432`
- Base de datos `grocerysaver`
- Usuario `grocery_user`
- Entorno virtual en `./venv`

Configuracion actual de base de datos en `api_grocerysaver/settings.py`:

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

API base:

```text
http://127.0.0.1:8000/api/
```

## Variables de entorno relevantes

- `GOOGLE_OAUTH_CLIENT_ID`
- `AUTO_VERIFY_EMAIL_ON_REGISTER`
- `AUTO_SEED_EXPIRING_INVENTORY`
- `INVENTORY_EXPIRY_ALERT_DAYS`
- `REDIS_URL`
- `CACHE_DEFAULT_TTL`
- `CATALOG_CACHE_TTL`
- `WEATHER_CACHE_TTL`
- `RAFFLE_CACHE_TTL`

## Endpoints principales

### API y docs

- `GET /api/`
- `GET /api/docs/`
- `GET /api/schema/`

### Auth

- `GET /api/auth/roles/`
- `POST /api/auth/register/`
- `POST /api/auth/verify-email/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- `PATCH /api/auth/me/avatar/`
- `DELETE /api/auth/me/avatar/`
- `POST /api/auth/social-login/`

### Perfil

- `GET/POST /api/profile/addresses/`
- `PATCH/DELETE /api/profile/addresses/<address_id>/`
- `GET/PATCH /api/profile/notifications/`
- `GET/PATCH /api/profile/savings-preferences/`
- `GET/POST /api/profile/role-change-requests/`

### Catalogo

- `GET /api/stores/`
- `GET /api/categories/`
- `GET /api/products/`
- `GET /api/products/<product_id>/`
- `POST /api/products/scan/`
- `GET/POST /api/products/purchases/`
- `GET /api/offers/`
- `GET /api/compare-prices/`
- `GET /api/prices/history/`

### Carrito

- `GET /api/cart/`
- `DELETE /api/cart/`
- `GET /api/cart/items/`
- `POST /api/cart/items/`
- `PATCH /api/cart/items/<item_id>/`
- `DELETE /api/cart/items/<item_id>/`

### Checkout, pago, orden y envio

- `GET /api/checkout/`
- `POST /api/checkout/`
- `GET /api/checkout/<checkout_id>/`
- `PATCH /api/checkout/<checkout_id>/`
- `GET /api/payments/`
- `POST /api/payments/`
- `GET /api/payments/<payment_id>/`
- `GET /api/orders/`
- `POST /api/orders/`
- `GET /api/orders/<order_id>/`
- `GET /api/shipments/`
- `GET /api/shipments/<shipment_id>/`
- `PATCH /api/shipments/<shipment_id>/`

### Inventario y alertas

- `GET /api/inventory/items/`
- `POST /api/inventory/items/`
- `PATCH /api/inventory/items/<id>/`
- `DELETE /api/inventory/items/<id>/`
- `GET /api/alerts/`
- `PATCH /api/alerts/<id>/`

### Otros

- `GET /api/raffles/active/`
- `POST /api/device-sensors/`
- `POST /api/jobs/export-products/`
- `GET /api/jobs/<job_id>/`
- `GET /api/weather/`
- `GET /api/protected/`
- `GET /api/protected/admin-only/`

## Flujo recomendado de compra

1. Agregar items al carrito (`/api/cart/items/`).
2. Crear checkout (`POST /api/checkout/`).
3. Asociar direccion (`PATCH /api/checkout/<id>/`).
4. Procesar pago (`POST /api/payments/`).
5. Consultar orden (`/api/orders/`).
6. Consultar seguimiento (`/api/shipments/`).

Nota: si intentas pagar sin direccion en checkout, el backend responde `400`.

## Jobs y comandos utiles

Worker de exportaciones:

```powershell
.\venv\Scripts\python.exe manage.py run_job_worker
```

Procesar un solo job:

```powershell
.\venv\Scripts\python.exe manage.py run_job_worker --once
```

Sincronizar alertas de inventario:

```powershell
.\venv\Scripts\python.exe manage.py sync_inventory_alerts
```

## Testing

Suite completa de ordenes (checkout, payment, shipment):

```powershell
.\venv\Scripts\python.exe manage.py test orders.tests --keepdb
```

Chequeo de proyecto:

```powershell
.\venv\Scripts\python.exe manage.py check
```

## Guia rapida Flutter

Base URL:

- Web: `http://127.0.0.1:8000/api`
- Android emulator: `http://10.0.2.2:8000/api`

Para la lista de compras (carrito), usa `GET /api/cart/items/` y lee `response['items']`.

Para inventario, usa `GET /api/inventory/items/` y lee `response['items']`.

Para alertas de caducidad, usa `GET /api/alerts/?status=active` y lee `response['alerts']`.
