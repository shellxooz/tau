"""Треки и рельеф: разбор GPX, длина, набор высоты, профиль и крутизна склонов.

Числа здесь считает код, а не ИИ. Высоты берутся из модели рельефа Open-Meteo Elevation
(Copernicus DEM, сетка около 90 м), поэтому крутизна — грубая оценка: короткие обрывы
и скальные ступени модель сглаживает.
"""
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ELEVATION_URL = 'https://api.open-meteo.com/v1/elevation'
KZ_BOX = (40.5, 46.4, 55.5, 87.4)  # широта и долгота: Казахстан с запасом
MAX_POINTS = 20000
MAX_JUMP_M = 1000  # скачок GPS больше этого — разрыв трека
STEP_M = 100  # шаг профиля
EARTH = 6371008.8


class TrackError(ValueError):
    pass


def distance_m(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH * math.asin(math.sqrt(h))


def offset(point, north_m, east_m):
    lat = point[0] + math.degrees(north_m / EARTH)
    lon = point[1] + math.degrees(east_m / (EARTH * math.cos(math.radians(point[0]))))
    return lat, lon


def parse_gpx(text):
    """GPX → список отрезков [[(lat, lon, ele|None), ...]]. Время и имена из файла не сохраняются."""
    if not isinstance(text, str) or not text.strip():
        raise TrackError('Файл пустой')
    if re.search(r'<!(DOCTYPE|ENTITY)', text, re.I):  # защита от XXE и «бомб» из сущностей
        raise TrackError('Файл содержит недопустимые XML-конструкции')
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise TrackError('Это не GPX-файл или он повреждён') from None
    local = lambda tag: tag.rsplit('}', 1)[-1]
    if local(root.tag) != 'gpx':
        raise TrackError('Это не GPX-файл')
    segments = []
    for node in root.iter():
        if local(node.tag) in ('trkseg', 'rte'):
            seg = []
            for pt in node:
                if local(pt.tag) not in ('trkpt', 'rtept'):
                    continue
                try:
                    lat, lon = float(pt.get('lat')), float(pt.get('lon'))
                except (TypeError, ValueError):
                    continue
                ele = next((child.text for child in pt if local(child.tag) == 'ele'), None)
                try:
                    ele = float(ele) if ele is not None else None
                except ValueError:
                    ele = None
                seg.append((lat, lon, ele))
            if seg:
                segments.append(seg)
    total = sum(len(s) for s in segments)
    if total < 10:
        raise TrackError('В треке меньше 10 точек')
    if total > MAX_POINTS:
        raise TrackError(f'В треке больше {MAX_POINTS} точек: упростите его в приложении, где записывали')
    return clean(segments)


def clean(segments):
    """Убирает дубли и скачки GPS, проверяет, что трек в Казахстане."""
    result = []
    for seg in segments:
        current = []
        for p in seg:
            if not (KZ_BOX[0] <= p[0] <= KZ_BOX[2] and KZ_BOX[1] <= p[1] <= KZ_BOX[3]):
                raise TrackError('Трек выходит за пределы Казахстана')
            if current:
                d = distance_m(current[-1], p)
                if d < 1:
                    continue
                if d > MAX_JUMP_M:
                    if len(current) > 1:
                        result.append(current)
                    current = []
            current.append(p)
        if len(current) > 1:
            result.append(current)
    if not result:
        raise TrackError('В треке нет непрерывных участков')
    return result


def chain(ways):
    """Склейка линий OpenStreetMap в непрерывные отрезки с учётом направления."""
    segments = []
    for way in ways:
        if len(way) < 2:
            continue
        if segments:
            tail = segments[-1]
            pairs = [(distance_m(tail[-1], way[0]), False, False), (distance_m(tail[-1], way[-1]), False, True),
                     (distance_m(tail[0], way[0]), True, False), (distance_m(tail[0], way[-1]), True, True)]
            gap, flip_tail, flip_way = min(pairs)
            if gap < 30:
                if flip_tail:
                    tail.reverse()
                tail.extend((way[::-1] if flip_way else way)[1:])
                continue
        segments.append(list(way))
    return segments


def length_m(segments):
    return sum(distance_m(a, b) for seg in segments for a, b in zip(seg, seg[1:]))


def resample(segments, step=STEP_M):
    """Точки через равный шаг вдоль трека: [(lat, lon, км от старта)]. Разрывы между отрезками не считаются."""
    out, total = [], 0.0
    for n, seg in enumerate(segments):
        out.append((seg[0][0], seg[0][1], total / 1000, n))
        mark = total + step
        for a, b in zip(seg, seg[1:]):
            d = distance_m(a, b)
            while d and mark <= total + d:
                t = (mark - total) / d
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, mark / 1000, n))
                mark += step
            total += d
        if out[-1][2] < total / 1000 - 1e-6:
            out.append((seg[-1][0], seg[-1][1], total / 1000, n))
    return out


def simplify(seg, tolerance=8.0):
    """Упрощение линии для карты (Рамер — Дуглас — Пекер), допуск в метрах."""
    if len(seg) < 3:
        return [(round(p[0], 5), round(p[1], 5)) for p in seg]
    lat0 = math.radians(seg[0][0])
    xy = [(math.radians(p[1]) * EARTH * math.cos(lat0), math.radians(p[0]) * EARTH) for p in seg]
    keep, stack = {0, len(seg) - 1}, [(0, len(seg) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = xy[i], xy[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy) or 1e-9
        best, index = 0.0, None
        for k in range(i + 1, j):
            dist = abs(dy * (xy[k][0] - x1) - dx * (xy[k][1] - y1)) / norm
            if dist > best:
                best, index = dist, k
        if index is not None and best > tolerance:
            keep.add(index)
            stack += [(i, index), (index, j)]
    return [(round(seg[k][0], 5), round(seg[k][1], 5)) for k in sorted(keep)]


CACHE = {}  # (lat, lon) с точностью 4 знака (~10 м) -> высота; бесплатный сервис ограничивает число запросов
CACHE_PATH = None


def load_cache(path):
    global CACHE_PATH
    CACHE_PATH = path
    if path and path.exists():
        CACHE.update({tuple(map(float, k.split(','))): v for k, v in json.loads(path.read_text(encoding='utf-8')).items()})


def save_cache():
    if CACHE_PATH:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps({f'{k[0]},{k[1]}': v for k, v in CACHE.items()}), encoding='utf-8')


def fetch_elevations(points, per_point_pause=0.1, retries=6):
    """Высоты из Open-Meteo Elevation для списка (lat, lon). По 100 точек за запрос, с кэшем и паузами.

    Лимиты бесплатного Open-Meteo считаются по точкам, поэтому между запросами выдерживается пауза,
    а на ответ 429 — ожидание и повтор.
    """
    keys = [(round(p[0], 4), round(p[1], 4)) for p in points]
    missing = list(dict.fromkeys(k for k in keys if k not in CACHE))
    for start in range(0, len(missing), 100):
        chunk = missing[start:start + 100]
        query = urllib.parse.urlencode({'latitude': ','.join(f'{p[0]:.4f}' for p in chunk), 'longitude': ','.join(f'{p[1]:.4f}' for p in chunk)})
        request = urllib.request.Request(f'{ELEVATION_URL}?{query}', headers={'User-Agent': 'GoTAU-prototype'})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429 or attempt == retries - 1:
                    raise
                time.sleep(65)
            except (urllib.error.URLError, ConnectionError, TimeoutError):  # обрыв соединения: подождать и повторить
                if attempt == retries - 1:
                    raise
                time.sleep(20)
        CACHE.update(zip(chunk, (float(v) for v in data['elevation'])))
        save_cache()
        time.sleep(per_point_pause * len(chunk))
    return [CACHE[k] for k in keys]


def climb(elevations, threshold=5.0):
    """Набор и сброс с порогом: мелкий шум модели рельефа не накапливается."""
    up = down = 0.0
    ref = elevations[0]
    for e in elevations[1:]:
        if e - ref >= threshold:
            up += e - ref
            ref = e
        elif ref - e >= threshold:
            down += ref - e
            ref = e
    return up, down


def analyze(segments, elevations_of=None, step=STEP_M, terrain_every=3):
    """Полный разбор трека. Возвращает профиль, сводку и оценку крутизны склонов вдоль пути."""
    elevations_of = elevations_of or fetch_elevations
    points = resample(segments, step)
    elev = elevations_of([(p[0], p[1]) for p in points])
    # набор и сброс считаются внутри каждого непрерывного куска: перепад между разорванными кусками — не подъём
    up = down = 0.0
    for n in range(len(segments)):
        part = [e for p, e in zip(points, elev) if p[3] == n]
        if len(part) > 1:
            u, d = climb(part)
            up, down = up + u, down + d
    top = max(range(len(elev)), key=elev.__getitem__)
    # крутизна трека: самый крутой подъём или спуск на окне около 300 м, не через разрыв
    window = max(1, round(300 / step))
    grade = 0.0
    for i in range(len(points) - window):
        run = (points[i + window][2] - points[i][2]) * 1000
        if run > 50 and points[i][3] == points[i + window][3]:
            grade = max(grade, abs(elev[i + window] - elev[i]) / run * 100)
    # крутизна склона вокруг тропы: разность высот с точками в 90 м к северу и к востоку
    probe_idx = list(range(0, len(points), terrain_every))
    probes = []
    for i in probe_idx:
        probes += [offset(points[i], 90, 0), offset(points[i], 0, 90)]
    around = elevations_of(probes)
    slopes = []
    for n, i in enumerate(probe_idx):
        north, east = around[2 * n:2 * n + 2]
        gradient = math.hypot((north - elev[i]) / 90, (east - elev[i]) / 90)
        slopes.append((i, math.degrees(math.atan(gradient))))
    step_km = step * terrain_every / 1000
    steep = sum(step_km for _, s in slopes if 30 <= s < 45)
    very = sum(step_km for _, s in slopes if s >= 45)
    worst = max(slopes, key=lambda x: x[1]) if slopes else (0, 0.0)
    total = points[-1][2]
    stats = {
        'segments': len(segments),
        'distance_km': round(total, 1), 'ascent_m': round(up), 'descent_m': round(down),
        'start_elev': round(elev[0]), 'finish_elev': round(elev[-1]), 'min_elev': round(min(elev)), 'max_elev': round(elev[top]),
        'start': [round(points[0][0], 5), round(points[0][1], 5)], 'top': [round(points[top][0], 5), round(points[top][1], 5)],
        'loop': distance_m(points[0], points[-1]) < 300,
    }
    terrain = {
        'max_trail_grade_pct': round(grade), 'max_slope_deg': round(worst[1]), 'max_slope_at_km': round(points[worst[0]][2], 1),
        'km_slope_30_45': round(steep, 1), 'km_slope_45_plus': round(very, 1),
        'source': 'Open-Meteo Elevation (Copernicus DEM, ~90 м)',
    }
    profile = [[round(p[2], 2), round(e)] for p, e in zip(points, elev)][::max(1, len(points) // 300)]
    return {'stats': stats, 'terrain': terrain, 'profile': profile, 'line': [simplify(seg) for seg in segments]}


def naismith_hours(distance_km, ascent_m):
    return distance_km / 4 + ascent_m / 400


def level_for(distance_km, ascent_m, max_elev):
    if ascent_m < 500 and distance_km <= 10 and max_elev < 2500:
        return 'Лёгкий'
    if ascent_m < 1100 and max_elev < 3200:
        return 'Средний'
    return 'Сложный'
