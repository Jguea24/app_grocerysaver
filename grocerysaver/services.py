"""Servicios de dominio y helpers compartidos por vistas y señales."""

import re
import uuid
from json import JSONDecodeError, loads
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ProductCode, ProductCodeType

User = get_user_model()


# Endpoints de Open-Meteo usados por el modulo de clima.
OPEN_METEO_GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'
OPEN_METEO_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo'

# Mapa de codigos weather_code de Open-Meteo a etiquetas legibles en espanol.
WEATHER_CODE_LABELS = {
    0: 'Despejado',
    1: 'Mayormente despejado',
    2: 'Parcialmente nublado',
    3: 'Nublado',
    45: 'Niebla',
    48: 'Niebla escarchada',
    51: 'Llovizna ligera',
    53: 'Llovizna moderada',
    55: 'Llovizna intensa',
    56: 'Llovizna helada ligera',
    57: 'Llovizna helada intensa',
    61: 'Lluvia ligera',
    63: 'Lluvia moderada',
    65: 'Lluvia intensa',
    66: 'Lluvia helada ligera',
    67: 'Lluvia helada intensa',
    71: 'Nieve ligera',
    73: 'Nieve moderada',
    75: 'Nieve intensa',
    77: 'Granizo',
    80: 'Chubascos ligeros',
    81: 'Chubascos moderados',
    82: 'Chubascos intensos',
    85: 'Chubascos de nieve ligeros',
    86: 'Chubascos de nieve intensos',
    95: 'Tormenta',
    96: 'Tormenta con granizo ligero',
    99: 'Tormenta con granizo intenso',
}

def build_qr_code_value():
    """Genera el valor base de un codigo QR interno."""
    return f'QR-{uuid.uuid4()}'


def build_unique_qr_code(reserved_codes=None):
    """Genera un QR unico evitando colisiones conocidas y persistidas."""
    reserved = reserved_codes or set()
    for _ in range(50):
        candidate = build_qr_code_value()
        if candidate in reserved:
            continue
        if not ProductCode.objects.filter(code=candidate).exists():
            return candidate
    raise DjangoValidationError('No se pudo generar un codigo QR unico.')


def ensure_product_qr_code(product):
    """Garantiza que un producto tenga al menos un codigo QR asociado."""
    if product is None:
        return None
    existing = product.codes.filter(code_type=ProductCodeType.QR).first()
    if existing is not None:
        return existing
    return ProductCode.objects.create(
        product=product,
        code=build_unique_qr_code(),
        code_type=ProductCodeType.QR,
    )


def verify_google_id_token(id_token):
    """Valida un id_token de Google y retorna identidad normalizada."""
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '').strip()
    if not client_id:
        raise ValueError('GOOGLE_OAUTH_CLIENT_ID no esta configurado.')

    query = urlencode({'id_token': id_token})
    token_url = f'{GOOGLE_TOKENINFO_URL}?{query}'

    try:
        with urlopen(token_url, timeout=10) as response:
            payload = loads(response.read().decode('utf-8'))
    except URLError as exc:
        raise ValueError('No se pudo validar el token de Google.') from exc
    except JSONDecodeError as exc:
        raise ValueError('Respuesta invalida de Google al validar token.') from exc

    if payload.get('aud') != client_id:
        raise ValueError('El token de Google no pertenece a esta aplicacion.')

    issuer = payload.get('iss')
    if issuer not in {'accounts.google.com', 'https://accounts.google.com'}:
        raise ValueError('Issuer invalido para token de Google.')

    if payload.get('email_verified') not in {'true', True}:
        raise ValueError('La cuenta de Google no tiene email verificado.')

    provider_user_id = payload.get('sub')
    email = (payload.get('email') or '').strip().lower()
    if not provider_user_id or not email:
        raise ValueError('El token de Google no contiene identidad suficiente.')

    return {
        'provider_user_id': provider_user_id,
        'email': email,
        'first_name': (payload.get('given_name') or '').strip(),
        'last_name': (payload.get('family_name') or '').strip(),
    }


def build_unique_username_from_email(email):
    """Crea un username estable a partir del email y asegura unicidad."""
    base = email.split('@')[0].lower()
    base = re.sub(r'[^a-z0-9_.-]', '', base)[:20] or 'user'

    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        suffix = str(counter)
        username = f'{base[: max(1, 20 - len(suffix))]}{suffix}'
        counter += 1

    return username


def validate_password_or_raise(password, user=None):
    """Valida password con los validadores de Django y reexpone errores legibles."""
    from django.contrib.auth.password_validation import validate_password

    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise DjangoValidationError(list(exc.messages)) from exc


def issue_jwt_pair(user):
    """Genera el par de tokens JWT para el usuario autenticado."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def send_email_verification(user, token):
    """Envia el token de verificacion al correo configurado del usuario."""
    message = (
        'Tu cuenta fue creada. Para verificarla usa este token en el endpoint '
        'POST /api/auth/verify-email/:\n\n'
        f'{token}\n\n'
        'Si no solicitaste este registro, ignora este correo.'
    )

    send_mail(
        subject='Verifica tu cuenta en GrocerySaver',
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def _http_get_json(base_url, params, timeout=8):
    """Ejecuta un GET JSON simple y normaliza errores de red o parseo."""
    request_url = f'{base_url}?{urlencode(params)}'
    try:
        with urlopen(request_url, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError('No se pudo consultar el servicio de clima.')
            payload = response.read().decode('utf-8')
            return loads(payload)
    except URLError as exc:
        raise ValueError('No se pudo conectar con Open-Meteo.') from exc
    except JSONDecodeError as exc:
        raise ValueError('Respuesta invalida del servicio de clima.') from exc


def _weather_text(code):
    """Convierte el weather code numerico en una etiqueta legible."""
    try:
        return WEATHER_CODE_LABELS.get(int(code), 'Condicion desconocida')
    except (TypeError, ValueError):
        return 'Condicion desconocida'


def geocode_city(city_name):
    """Resuelve una ciudad a coordenadas usando el geocoding de Open-Meteo."""
    payload = _http_get_json(
        OPEN_METEO_GEOCODING_URL,
        {
            'name': city_name,
            'count': 1,
            'language': 'es',
            'format': 'json',
        },
    )
    results = payload.get('results') or []
    if not results:
        return None

    best = results[0]
    return {
        'name': best.get('name') or city_name,
        'country': best.get('country'),
        'admin1': best.get('admin1'),
        'latitude': best.get('latitude'),
        'longitude': best.get('longitude'),
    }


def fetch_open_meteo_forecast(latitude, longitude, timezone='auto'):
    """Solicita clima actual, horario y diario en una sola llamada."""
    return _http_get_json(
        OPEN_METEO_FORECAST_URL,
        {
            'latitude': latitude,
            'longitude': longitude,
            'timezone': timezone,
            'forecast_days': 7,
            'current': 'temperature_2m,relative_humidity_2m,precipitation_probability,weather_code,wind_speed_10m,is_day',
            'hourly': 'temperature_2m,precipitation_probability,weather_code,wind_speed_10m',
            'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
        },
    )


def _build_hourly_forecast(hourly, max_items=24):
    """Normaliza la seccion hourly a una lista segura para la API."""
    times = hourly.get('time') or []
    temperatures = hourly.get('temperature_2m') or []
    precipitation_probabilities = hourly.get('precipitation_probability') or []
    weather_codes = hourly.get('weather_code') or []
    wind_speeds = hourly.get('wind_speed_10m') or []

    size = min(max_items, len(times), len(temperatures), len(precipitation_probabilities), len(weather_codes), len(wind_speeds))
    items = []
    for index in range(size):
        code = weather_codes[index]
        items.append(
            {
                'time': times[index],
                'temperature_c': temperatures[index],
                'precipitation_probability': precipitation_probabilities[index],
                'wind_kmh': wind_speeds[index],
                'weather_code': code,
                'weather_text': _weather_text(code),
            }
        )
    return items


def _build_daily_forecast(daily):
    """Construye una lista diaria compacta con min/max y descripcion."""
    dates = daily.get('time') or []
    max_temperatures = daily.get('temperature_2m_max') or []
    min_temperatures = daily.get('temperature_2m_min') or []
    weather_codes = daily.get('weather_code') or []

    size = min(len(dates), len(max_temperatures), len(min_temperatures), len(weather_codes))
    items = []
    for index in range(size):
        code = weather_codes[index]
        items.append(
            {
                'date': dates[index],
                'temp_max_c': max_temperatures[index],
                'temp_min_c': min_temperatures[index],
                'weather_code': code,
                'weather_text': _weather_text(code),
            }
        )
    return items


def get_weather_payload(city=None, latitude=None, longitude=None):
    """Construye el payload publico del endpoint de clima."""
    selected_city = (city or '').strip()
    if selected_city:
        location_data = geocode_city(selected_city)
        if location_data is None:
            raise ValueError('No se encontro la ciudad solicitada.')
        latitude = location_data['latitude']
        longitude = location_data['longitude']
        location_name = location_data['name']
        country = location_data.get('country')
        region = location_data.get('admin1')
    else:
        if latitude is None or longitude is None:
            raise ValueError('Debes enviar city o lat/lon.')
        location_name = selected_city or 'Coordenadas'
        country = None
        region = None

    forecast = fetch_open_meteo_forecast(latitude=latitude, longitude=longitude)
    current = forecast.get('current') or {}
    hourly = forecast.get('hourly') or {}
    daily = forecast.get('daily') or {}
    weather_code = current.get('weather_code')

    return {
        'provider': 'open-meteo',
        'location': {
            'name': location_name,
            'country': country,
            'region': region,
            'latitude': latitude,
            'longitude': longitude,
            'timezone': forecast.get('timezone'),
        },
        'current': {
            'temperature_c': current.get('temperature_2m'),
            'humidity': current.get('relative_humidity_2m'),
            'precipitation_probability': current.get('precipitation_probability'),
            'wind_kmh': current.get('wind_speed_10m'),
            'is_day': bool(current.get('is_day')),
            'weather_code': weather_code,
            'weather_text': _weather_text(weather_code),
        },
        'hourly': _build_hourly_forecast(hourly),
        'daily': _build_daily_forecast(daily),
    }



