import re
from functools import lru_cache
from json import JSONDecodeError, loads
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


# Endpoints de Open-Meteo usados por el modulo de clima.
OPEN_METEO_GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'
OPEN_METEO_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'

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

BASE_DIR = Path(__file__).resolve().parent
ECUADOR_GEO_PATH = BASE_DIR / 'data' / 'ecuador_geo.json'


def build_unique_username_from_email(email):
    # Construye username desde el email y garantiza unicidad (maximo 20 chars).
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
    # Delega en validadores de Django y preserva mensajes de error legibles.
    from django.contrib.auth.password_validation import validate_password

    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise DjangoValidationError(list(exc.messages)) from exc


def issue_jwt_pair(user):
    # Genera tokens access/refresh usando SimpleJWT.
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def send_email_verification(user, token):
    # Envia token de verificacion por correo; en DEBUG puede ir a consola.
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
    # Helper HTTP comun para APIs externas con manejo de errores unificado.
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
    # Convierte weather code numerico a texto; fallback si falta o es invalido.
    try:
        return WEATHER_CODE_LABELS.get(int(code), 'Condicion desconocida')
    except (TypeError, ValueError):
        return 'Condicion desconocida'


def geocode_city(city_name):
    # Resuelve nombre de ciudad a coordenadas con Open-Meteo geocoding.
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
    # Solicita clima actual, por horas y diario en una sola llamada.
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
    # Normaliza arrays por hora al tamano comun minimo para evitar index errors.
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
    # Construye lista diaria compacta con temperatura min/max y descripcion.
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
    # Punto de entrada principal del clima:
    # - si llega city, primero geocodifica
    # - si no, exige coordenadas
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


@lru_cache(maxsize=1)
def get_ecuador_geo_data():
    # Cachea el catalogo geografico en memoria para evitar lecturas de disco.
    if not ECUADOR_GEO_PATH.exists():
        raise ValueError('No existe el catalogo geografico de Ecuador.')
    try:
        return loads(ECUADOR_GEO_PATH.read_text(encoding='utf-8'))
    except JSONDecodeError as exc:
        raise ValueError('Catalogo geografico invalido.') from exc


def get_ecuador_provinces():
    # Retorna resumen de provincias para carga rapida en clientes.
    data = get_ecuador_geo_data()
    provinces = data.get('provinces') or []
    return [
        {
            'id': province.get('id'),
            'name': province.get('name'),
            'cantons_count': len(province.get('cantons') or []),
        }
        for province in provinces
    ]


def get_ecuador_cantons(province_id=None, province_name=None):
    # Resuelve una provincia (por id o nombre exacto) y retorna sus cantones.
    data = get_ecuador_geo_data()
    provinces = data.get('provinces') or []

    selected = None
    if province_id is not None:
        for province in provinces:
            if str(province.get('id')) == str(province_id):
                selected = province
                break
    elif province_name:
        province_name_normalized = province_name.strip().lower()
        for province in provinces:
            if (province.get('name') or '').strip().lower() == province_name_normalized:
                selected = province
                break
    else:
        raise ValueError('Debes enviar province_id o province.')

    if selected is None:
        raise ValueError('Provincia no encontrada.')

    return {
        'country': data.get('country', 'Ecuador'),
        'province': {
            'id': selected.get('id'),
            'name': selected.get('name'),
        },
        'cantons': selected.get('cantons') or [],
    }
