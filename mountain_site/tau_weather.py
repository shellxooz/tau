"""Реальный прогноз погоды Open-Meteo для точки на заданной высоте. Только стандартная библиотека.

Модель ИИ никогда не «вспоминает» погоду сама: она получает только цифры из этого модуля.
Если прогноза нет, возвращается available=False с причиной, и ничего не выдумывается.
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime

API = 'https://api.open-meteo.com/v1/forecast'
SOURCE = 'Open-Meteo (open-meteo.com), лицензия CC BY 4.0'
MAX_DAYS_AHEAD = 15
CACHE_SECONDS = 1800
DAY_START_HOUR, DAY_END_HOUR = 7, 19
_cache = {}


def _fetch(lat, lon, elevation, day):
    params = {
        'latitude': lat, 'longitude': lon, 'elevation': elevation,
        'hourly': 'temperature_2m,apparent_temperature,precipitation_probability,precipitation,snowfall,wind_speed_10m,wind_gusts_10m',
        'daily': 'sunrise,sunset', 'wind_speed_unit': 'ms', 'timezone': 'Asia/Almaty',
        'start_date': day, 'end_date': day,
    }
    request = urllib.request.Request(API + '?' + urllib.parse.urlencode(params), headers={'User-Agent': 'tau-prototype'})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)


def summarize(raw, elevation):
    """Сводка по дневным часам (07–19): минимумы температуры, максимумы ветра и осадков."""
    hourly = raw['hourly']
    index = [i for i, t in enumerate(hourly['time']) if DAY_START_HOUR <= int(t[11:13]) <= DAY_END_HOUR]

    def values(name):
        return [hourly[name][i] for i in index if hourly[name][i] is not None]

    def pick(name, func, digits=0):
        items = values(name)
        if not items:
            return None
        result = round(func(items), digits)
        return int(result) if digits == 0 else result

    return {
        'elevation_m': int(elevation),
        'temp_min_c': pick('temperature_2m', min), 'temp_max_c': pick('temperature_2m', max),
        'feels_min_c': pick('apparent_temperature', min),
        'wind_max_ms': pick('wind_speed_10m', max), 'gust_max_ms': pick('wind_gusts_10m', max),
        'precip_prob_max_pct': pick('precipitation_probability', max),
        'precip_sum_mm': pick('precipitation', sum, 1), 'snowfall_sum_cm': pick('snowfall', sum, 1),
    }


def forecast_for_route(route, day):
    """day — строка YYYY-MM-DD. Возвращает прогноз для верхней и стартовой точек маршрута."""
    try:
        target = date.fromisoformat(day)
    except ValueError:
        return {'available': False, 'reason': 'Некорректная дата'}
    delta = (target - date.today()).days
    if delta < 0:
        return {'available': False, 'reason': 'Дата в прошлом: прогноз не запрашивается'}
    if delta > MAX_DAYS_AHEAD:
        return {'available': False, 'reason': f'Прогноз доступен не более чем на {MAX_DAYS_AHEAD} дней вперёд'}
    key = (route['id'], day)
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        top_raw = _fetch(route.get('top_lat', route['lat']), route.get('top_lon', route['lon']), route['max_elev'], day)
        start_raw = _fetch(route['lat'], route['lon'], route['start_elev'], day)
        result = {
            'available': True, 'source': SOURCE, 'date': day,
            'fetched_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'window': f'{DAY_START_HOUR:02d}:00–{DAY_END_HOUR:02d}:00',
            'top': summarize(top_raw, route['max_elev']),
            'start': summarize(start_raw, route['start_elev']),
            'sunrise': top_raw['daily']['sunrise'][0][11:16],
            'sunset': top_raw['daily']['sunset'][0][11:16],
        }
    except Exception as exc:  # сеть, формат ответа, таймаут — прогноз просто недоступен
        return {'available': False, 'reason': f'Сервис прогноза недоступен ({type(exc).__name__})'}
    _cache[key] = (time.time(), result)
    return result
