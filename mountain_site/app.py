"""TAU — прототип «Паспорта похода» с AI-аудитором готовности. Python 3.10+.

Сервер работает на стандартной библиотеке. Пакет anthropic нужен только для ИИ-режима:
без него и без ключа аудит выполняется движком правил.
"""
import argparse
import json
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import tau_ai
import tau_geo
import tau_rules
import tau_weather

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / 'data' / 'trips.sqlite3'
NOTE = 'Координаты и высоты приблизительные, для демонстрации. Трек требует полевой проверки.'
ROUTES = [
    {'id': 'kok-zhailau', 'name': 'Кок-Жайляу', 'area': 'Иле-Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 8.4, 'hours': '4–5', 'hours_max': 5, 'ascent': 750, 'level': 'Средний', 'className': 'green', 'tag': 'Начни знакомство с горами', 'lat': 43.147, 'lon': 76.972, 'start_elev': 1500, 'max_elev': 2250, 'description': 'Прогулка к горному плато. ' + NOTE},
    {'id': 'butakovka', 'name': 'Бутаковское ущелье', 'area': 'Заилийский Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 6.2, 'hours': '3–4', 'hours_max': 4, 'ascent': 420, 'level': 'Лёгкий', 'className': 'blue', 'tag': 'По тропе вдоль реки', 'lat': 43.166, 'lon': 77.075, 'start_elev': 1550, 'max_elev': 1970, 'description': 'Тропа вдоль реки к водопаду. ' + NOTE},
    {'id': 'bao', 'name': 'Большое Алматинское озеро', 'area': 'Иле-Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 15, 'hours': '6–8', 'hours_max': 8, 'ascent': 900, 'level': 'Средний', 'className': 'blue', 'tag': 'К бирюзовой воде на 2 500 м', 'lat': 43.051, 'lon': 76.985, 'start_elev': 1650, 'max_elev': 2510, 'description': 'Подъём к озеру пешком от экопоста. ' + NOTE},
    {'id': 'furmanov', 'name': 'Пик Фурманова', 'area': 'Заилийский Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 12, 'hours': '6–7', 'hours_max': 7, 'ascent': 1350, 'level': 'Сложный', 'className': 'green', 'tag': 'Первый трёхтысячник', 'lat': 43.137, 'lon': 77.06, 'start_elev': 1700, 'max_elev': 3053, 'description': 'Восхождение на вершину выше 3 000 м. ' + NOTE},
    {'id': 'bike-foothills', 'name': 'Предгорная петля', 'area': 'Окрестности Алматы', 'activity': 'cycling', 'activityLabel': 'Велосипед', 'distance': 24, 'hours': '3–4', 'hours_max': 4, 'ascent': 610, 'level': 'Средний', 'className': 'orange', 'tag': 'Больше пути на двух колёсах', 'lat': 43.2, 'lon': 76.95, 'start_elev': 900, 'max_elev': 1300, 'description': 'Концептуальный веломаршрут по предгорьям. ' + NOTE},
    {'id': 'ski-day', 'name': 'День на склоне', 'area': 'Горный кластер Алматы', 'activity': 'skiing', 'activityLabel': 'Лыжи', 'distance': 4.5, 'hours': '2–3', 'hours_max': 3, 'ascent': 0, 'level': 'По трассам', 'className': 'purple', 'tag': 'Зимний день в горах', 'lat': 43.128, 'lon': 77.081, 'start_elev': 2260, 'max_elev': 3200, 'description': 'День катания. Сведения о работе трасс и подъёмников не подключены. ' + NOTE},
    {'id': 'medeu-stairs', 'name': 'Лестница на плотину Медеу', 'area': 'Малоалматинское ущелье', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 2, 'hours': '1', 'hours_max': 1, 'ascent': 160, 'level': 'Лёгкий', 'className': 'green', 'tag': '842 ступени над катком', 'lat': 43.157, 'lon': 77.059, 'start_elev': 1690, 'max_elev': 1850, 'description': 'Короткий подъём по лестнице на селезащитную плотину. ' + NOTE},
    {'id': 'gorelnik', 'name': 'Водопад Горельник', 'area': 'Малоалматинское ущелье', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 4, 'hours': '2', 'hours_max': 2, 'ascent': 300, 'level': 'Лёгкий', 'className': 'blue', 'tag': 'Короткая тропа к водопаду', 'lat': 43.135, 'lon': 77.07, 'start_elev': 1950, 'max_elev': 2250, 'description': 'Тропа по ущелью Горельник к водопаду. ' + NOTE},
    {'id': 'medeu-shymbulak', 'name': 'От Медеу до Шымбулака', 'area': 'Малоалматинское ущелье', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 9, 'hours': '3–4', 'hours_max': 4, 'ascent': 570, 'level': 'Средний', 'className': 'green', 'tag': 'Пешком вместо канатной дороги', 'lat': 43.128, 'lon': 77.081, 'start_elev': 1690, 'max_elev': 2260, 'description': 'Подъём от катка к горнолыжной базе и обратно. ' + NOTE},
    {'id': 'alma-arasan', 'name': 'Ущелье Алма-Арасан', 'area': 'Иле-Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 8, 'hours': '3–4', 'hours_max': 4, 'ascent': 400, 'level': 'Лёгкий', 'className': 'blue', 'tag': 'Спокойная прогулка вдоль реки', 'lat': 43.08, 'lon': 76.91, 'start_elev': 1780, 'max_elev': 2180, 'description': 'Прогулка по ущелью вдоль реки Проходной. ' + NOTE},
    {'id': 'mynzhilki', 'name': 'Мынжилки и ледник Туюксу', 'area': 'Малоалматинское ущелье', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 14, 'hours': '6–7', 'hours_max': 7, 'ascent': 800, 'level': 'Средний', 'className': 'green', 'tag': 'К языку ледника', 'lat': 43.08, 'lon': 77.08, 'start_elev': 2260, 'max_elev': 3050, 'description': 'От Шымбулака вверх по ущелью к плотине Мынжилки и моренам ледника. ' + NOTE},
    {'id': 'kumbel', 'name': 'Пик Кумбель', 'area': 'Заилийский Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 12, 'hours': '7–8', 'hours_max': 8, 'ascent': 1500, 'level': 'Сложный', 'className': 'green', 'tag': 'Панорама города с 3 200 м', 'lat': 43.135, 'lon': 77.03, 'start_elev': 1700, 'max_elev': 3200, 'description': 'Долгий подъём на вершину над Кок-Жайляу. ' + NOTE},
    {'id': 'bukreev', 'name': 'Пик Букреева', 'area': 'Заилийский Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 14, 'hours': '7–8', 'hours_max': 8, 'ascent': 1400, 'level': 'Сложный', 'className': 'green', 'tag': 'Вершина над Бутаковкой', 'lat': 43.155, 'lon': 77.1, 'start_elev': 1650, 'max_elev': 3010, 'description': 'Восхождение из Бутаковского ущелья. ' + NOTE},
    {'id': 'kolsai', 'name': 'Кольсай: от первого озера ко второму', 'area': 'Кунгей Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший', 'distance': 16, 'hours': '6–7', 'hours_max': 7, 'ascent': 600, 'level': 'Средний', 'className': 'blue', 'tag': 'Лесная тропа между озёрами', 'lat': 42.96, 'lon': 78.32, 'start_elev': 1820, 'max_elev': 2250, 'description': 'Тропа через ельник от нижнего озера к среднему и обратно. До старта около 300 км от Алматы. ' + NOTE},
    {'id': 'bike-medeu', 'name': 'Велоподъём на Медеу', 'area': 'Малоалматинское ущелье', 'activity': 'cycling', 'activityLabel': 'Велосипед', 'distance': 30, 'hours': '2–3', 'hours_max': 3, 'ascent': 750, 'level': 'Средний', 'className': 'orange', 'tag': 'Классика шоссейного подъёма', 'lat': 43.157, 'lon': 77.059, 'start_elev': 950, 'max_elev': 1690, 'description': 'Подъём по шоссе от города к катку и спуск обратно. На дороге машины и автобусы. ' + NOTE},
]
for _route in ROUTES:
    _route.update(source='tau', has_track=False)
CATALOG_PATH = ROOT / 'catalog' / 'osm_routes.json'
TRACKS = {}  # id маршрута -> {'stats', 'terrain', 'profile', 'line'}
ROUTE_BY_ID = {}
STATUSES = {'planned': 'Подготовка', 'active': 'На маршруте', 'done': 'Вернулись', 'cancelled': 'Отменён'}
TIME = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
MAX_BODY = 32768
MAX_GPX_BODY = 6 * 1024 * 1024
TILE_HOSTS = 'https://a.tile.opentopomap.org https://b.tile.opentopomap.org https://c.tile.opentopomap.org https://tile.openstreetmap.org'
ACTIVITIES = {'hiking': 'Пеший', 'cycling': 'Велосипед', 'skiing': 'Лыжи'}
PROPOSAL_STATUS = {'pending': 'На модерации', 'approved': 'Одобрен', 'rejected': 'Отклонён'}


def load_catalog():
    """Каталог = ручной список TAU + маршруты OpenStreetMap (если импорт выполнен) + одобренные предложения."""
    global ROUTES
    ROUTES = [r for r in ROUTES if r['source'] == 'tau']
    ROUTE_BY_ID.clear()
    TRACKS.clear()
    if CATALOG_PATH.exists():
        data = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
        for route in data['routes']:
            route['terrain'] = data['tracks'][route['id']]['terrain']
            ROUTES.append(route)
        TRACKS.update(data['tracks'])
    if DB_PATH.exists():
        try:
            with connect() as con:
                rows = con.execute("SELECT * FROM proposals WHERE status='approved' ORDER BY id").fetchall()
        except sqlite3.OperationalError:  # старая база без таблицы предложений
            rows = []
        for row in rows:
            route = proposal_route(row)
            ROUTES.append(route)
            TRACKS[route['id']] = json.loads(row['track_json'])
    ROUTE_BY_ID.update({r['id']: r for r in ROUTES})


def proposal_route(row):
    track = json.loads(row['track_json'])
    s = track['stats']
    hours = tau_geo.naismith_hours(s['distance_km'], s['ascent_m']) * (1 if row['activity'] == 'hiking' else 0.5)
    lo, hi = max(1, round(hours)), max(1, round(hours * 1.3))
    return {'id': f'user-{row["id"]}', 'name': row['name'], 'area': row['area'] or 'Казахстан', 'activity': row['activity'], 'activityLabel': ACTIVITIES[row['activity']],
            'distance': s['distance_km'], 'hours': f'{lo}–{hi}' if hi > lo else str(lo), 'hours_max': hi, 'ascent': s['ascent_m'],
            'level': tau_geo.level_for(s['distance_km'], s['ascent_m'], s['max_elev']), 'className': 'green' if row['activity'] == 'hiking' else 'orange',
            'tag': 'Маршрут от пользователя', 'lat': s['start'][0], 'lon': s['start'][1], 'top_lat': s['top'][0], 'top_lon': s['top'][1],
            'start_elev': s['start_elev'], 'max_elev': s['max_elev'],
            'description': (row['description'] + ' ' if row['description'] else '') + 'Трек прислал пользователь, модератор TAU его одобрил. Цифры посчитаны по треку и модели рельефа.',
            'source': 'user', 'has_track': True, 'terrain': track['terrain']}


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def initialize_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS trips (id INTEGER PRIMARY KEY, title TEXT NOT NULL, route_id TEXT NOT NULL, start_date TEXT NOT NULL,
            participants INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        existing = {row['name'] for row in con.execute('PRAGMA table_info(trips)')}
        for name, ddl in (('start_time', "TEXT NOT NULL DEFAULT '08:00'"), ('return_time', 'TEXT'), ('organizer', "TEXT NOT NULL DEFAULT ''"), ('organizer_phone', "TEXT NOT NULL DEFAULT ''"),
                          ('status', "TEXT NOT NULL DEFAULT 'planned'"), ('members_json', "TEXT NOT NULL DEFAULT '[]'"), ('audit_json', 'TEXT'), ('confirmed', 'INTEGER NOT NULL DEFAULT 0'),
                          ('share_token', 'TEXT'), ('share_expires', 'TEXT')):
            if name not in existing:
                con.execute(f'ALTER TABLE trips ADD COLUMN {name} {ddl}')
        con.execute('''CREATE TABLE IF NOT EXISTS proposals (id INTEGER PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL DEFAULT '', activity TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', author TEXT NOT NULL DEFAULT '', track_json TEXT NOT NULL, checks_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', moderator_note TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP, decided_at TEXT)''')
    load_catalog()


def proposal_checks(name, description, stats, terrain, claimed_km):
    """Подсказки модератору. Решение принимает человек; правила только подсвечивают, что проверить."""
    checks = []
    def add(level, text):
        checks.append({'level': level, 'text': text})
    if re.search(r'https?://|www\.|@\w|\+?\d[\d\s()-]{8,}', description):
        add('warning', 'В описании есть ссылка, почта или телефон: возможна реклама.')
    if claimed_km and abs(claimed_km - stats['distance_km']) > max(1.0, 0.25 * stats['distance_km']):
        add('warning', f'Автор указал {claimed_km:g} км, а по треку {stats["distance_km"]:g} км.')
    if stats['distance_km'] > 40:
        add('info', 'Маршрут длиннее 40 км: скорее всего, многодневный. Проверка готовности TAU рассчитана на однодневные выходы.')
    if terrain['km_slope_45_plus'] > 0:
        add('warning', f'Есть участки на склонах круче 45° ({terrain["km_slope_45_plus"]:g} км): возможно, скалы. Нужна оценка опытного человека.')
    elif terrain['km_slope_30_45'] > 0:
        add('info', f'Около {terrain["km_slope_30_45"]:g} км пути проходит по склонам 30–45°: зимой это лавиноопасная крутизна.')
    if stats['max_elev'] >= 3500:
        add('warning', f'Верхняя точка {stats["max_elev"]} м: высотный маршрут.')
    if len(description.strip()) < 30:
        add('info', 'Описание короткое: попросите автора рассказать о тропе, воде и опасных местах.')
    return checks


def parse_proposal(data):
    name = clean_text(data.get('name'), 3, 80, 'Название маршрута')
    activity = data.get('activity', 'hiking')
    if activity not in ACTIVITIES:
        raise ValueError('Неизвестный вид активности')
    area = clean_text(data.get('area', ''), 0, 60, 'Район')
    description = clean_text(data.get('description', ''), 0, 1500, 'Описание')
    author = clean_text(data.get('author', ''), 0, 60, 'Имя автора')
    claimed = data.get('claimed_km')
    if claimed not in (None, '') and (isinstance(claimed, bool) or not isinstance(claimed, (int, float)) or not 0 < claimed < 500):
        raise ValueError('Длина маршрута указана неверно')
    if not data.get('consent'):
        raise ValueError('Подтвердите, что трек ваш и вы разрешаете его опубликовать')
    segments = tau_geo.parse_gpx(data.get('gpx'))
    if tau_geo.length_m(segments) > 120000:
        raise ValueError('Трек длиннее 120 км')
    return name, activity, area, description, author, float(claimed) if claimed not in (None, '') else None, segments


def clean_text(value, low, high, field):
    if not isinstance(value, str) or not low <= len(value.strip()) <= high:
        raise ValueError(f'{field}: от {low} до {high} символов')
    return value.strip()


def parse_members(data):
    members = data.get('members')
    if members is None:  # старый формат: только число участников
        count = data.get('participants')
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 50:
            raise ValueError('В группе должно быть от 1 до 50 человек')
        return [{'name': f'Участник {i + 1}', 'experience': 'some', 'age_group': 'adult', 'gear': [], 'bulky': 'none'} for i in range(count)]
    if not isinstance(members, list) or not 1 <= len(members) <= 30:
        raise ValueError('В группе должно быть от 1 до 30 человек')
    result = []
    for item in members:
        if not isinstance(item, dict):
            raise ValueError('Некорректные данные участника')
        gear = item.get('gear', [])
        if not isinstance(gear, list) or any(g not in tau_rules.GEAR for g in gear):
            raise ValueError('Некорректный список снаряжения')
        if item.get('experience') not in tau_rules.EXPERIENCE or item.get('age_group') not in tau_rules.AGE or item.get('bulky', 'none') not in tau_rules.BULKY:
            raise ValueError('Укажите опыт и возраст каждого участника')
        result.append({'name': clean_text(item.get('name'), 1, 60, 'Имя участника'), 'experience': item['experience'], 'age_group': item['age_group'],
                       'gear': sorted(set(gear)), 'bulky': item.get('bulky', 'none')})
    return result


def parse_trip(data):
    if not isinstance(data, dict):
        raise ValueError('Некорректный запрос')
    title = clean_text(data.get('title'), 2, 80, 'Название')
    if data.get('route_id') not in ROUTE_BY_ID:
        raise ValueError('Выберите маршрут из каталога')
    start_date = date.fromisoformat(data.get('start_date', ''))
    if start_date < date.today():
        raise ValueError('Дата похода не может быть в прошлом')
    start_time = data.get('start_time', '08:00')
    return_time = data.get('return_time') or None
    if start_date > date.today() + timedelta(days=730):
        raise ValueError('Дата похода слишком далеко: не позже чем через два года')
    if not isinstance(start_time, str) or not TIME.fullmatch(start_time) or (return_time and (not isinstance(return_time, str) or not TIME.fullmatch(return_time))):
        raise ValueError('Время указывается в формате ЧЧ:ММ')
    if return_time and return_time <= start_time:
        raise ValueError('Контрольное время возвращения должно быть позже выхода')
    organizer = clean_text(data.get('organizer', ''), 0, 60, 'Имя организатора')
    phone = clean_text(data.get('organizer_phone', ''), 0, 25, 'Телефон организатора')
    if phone and not re.fullmatch(r'\+?[\d\s()\-]{7,25}', phone):
        raise ValueError('Телефон: только цифры, пробелы, скобки и дефис')
    return title, data['route_id'], start_date.isoformat(), start_time, return_time, organizer, phone, parse_members(data)


def is_overdue(row):
    if row['status'] in ('done', 'cancelled') or not row['return_time']:
        return False
    try:
        return datetime.now() > datetime.fromisoformat(f'{row["start_date"]}T{row["return_time"].strip()}')
    except ValueError:  # испорченная запись не должна ломать список походов
        return False


def trip_summary(row):
    audit = json.loads(row['audit_json']) if row['audit_json'] else None
    recs = audit['recommendations'] if audit else []
    return {'id': row['id'], 'title': row['title'], 'route_id': row['route_id'], 'start_date': row['start_date'], 'start_time': row['start_time'], 'return_time': row['return_time'],
            'participants': row['participants'], 'status': row['status'], 'status_label': STATUSES[row['status']], 'overdue': is_overdue(row),
            'audited': bool(audit), 'attention': audit['attention'] if audit else None, 'confirmed': bool(row['confirmed']),
            'stale': bool(audit and audit.get('stale')), 'shared': bool(row['share_token']),
            'critical': sum(r['severity'] == 'critical' for r in recs), 'warning': sum(r['severity'] == 'warning' for r in recs),
            'undecided': sum(r['decision'] is None and r['severity'] != 'info' for r in recs)}


def stale_audit(row):
    """Состав или план изменились: прежний аудит помечается устаревшим, пока его не запустят заново."""
    if not row['audit_json']:
        return None
    audit = json.loads(row['audit_json'])
    audit['stale'] = True
    return json.dumps(audit, ensure_ascii=False)


def share_end(start_date, return_time):
    return (datetime.fromisoformat(f'{start_date}T{return_time or "23:59"}') + timedelta(hours=48)).isoformat(timespec='minutes')


def trip_full(row):
    data = trip_summary(row)
    data.update({'organizer': row['organizer'], 'organizer_phone': row['organizer_phone'], 'members': json.loads(row['members_json']),
                 'audit': json.loads(row['audit_json']) if row['audit_json'] else None,
                 'share': {'token': row['share_token'], 'expires': row['share_expires']} if row['share_token'] else None})
    return data


def notice_text(row):
    """Черновик уведомления для ДЧС. Сервис его НЕ отправляет: это делает сам турист."""
    route, members = ROUTE_BY_ID[row['route_id']], json.loads(row['members_json'])
    when = '.'.join(reversed(row['start_date'].split('-')))
    lines = [
        'Уведомление о выходе в горы', '',
        f'Старший группы: {row["organizer"] or "(укажите ФИО)"}',
        f'Контактный телефон: {row["organizer_phone"] or "(укажите телефон)"}',
        f'Объект: {route["name"]}, {route["area"]}',
        f'Маршрут: старт и финиш — начало тропы «{route["name"]}» (высота около {route["start_elev"]} м), верхняя точка около {route["max_elev"]} м',
        f'Протяжённость: {route["distance"]} км, набор высоты {route["ascent"]} м',
        f'Дата и время выхода: {when}, {row["start_time"]}',
        f'Планируемое возвращение: {when}, {row["return_time"] or "(укажите время)"}',
        'Ночёвки: не планируются (однодневный выход)',
        f'Количество участников: {len(members)}', 'Участники:',
    ]
    lines += [f'  {i + 1}. {m["name"]}' for i, m in enumerate(members)]
    return '\n'.join(lines)


def proposal_public(row, full):
    track = json.loads(row['track_json'])
    data = {'id': row['id'], 'name': row['name'], 'area': row['area'], 'activity': row['activity'], 'activityLabel': ACTIVITIES[row['activity']],
            'description': row['description'], 'author': row['author'], 'status': row['status'], 'status_label': PROPOSAL_STATUS[row['status']],
            'moderator_note': row['moderator_note'], 'created_at': row['created_at'], 'stats': track['stats'], 'terrain': track['terrain'],
            'checks': json.loads(row['checks_json']), 'route_id': f'user-{row["id"]}' if row['status'] == 'approved' else None}
    if full:
        data.update(line=track['line'], profile=track['profile'])
    return data


class Handler(BaseHTTPRequestHandler):
    timeout = 30  # клиент, который не дослал тело запроса, не держит поток вечно

    def log_message(self, *args):
        pass

    def host_allowed(self):
        """Защита от DNS rebinding: обслуживаем только обращения по IP-адресу или localhost, а не по чужому доменному имени."""
        host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]').lower()
        return host == 'localhost' or bool(re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', host)) or host == '::1'

    def guarded(self, handler):
        if not self.host_allowed():
            return self.send_body(403, {'error': 'Откройте приложение по адресу из окна запуска сервера'})
        try:
            return handler()
        except (OverflowError, RecursionError):
            return self.send_body(400, {'error': 'Некорректный запрос'})
        except (ConnectionError, TimeoutError):
            pass
        except Exception as exc:  # ошибка в одном запросе не должна обрывать соединение без ответа
            print(f'Ошибка при обработке {self.command} {self.path}: {type(exc).__name__}: {exc}', flush=True)
            try:
                return self.send_body(500, {'error': 'Внутренняя ошибка сервера. Попробуйте ещё раз'})
            except OSError:
                pass

    def do_GET(self):
        self.guarded(self.handle_get)

    def do_POST(self):
        self.guarded(self.handle_post)

    def send_body(self, status, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        # Серверам карт уходит только адрес сайта без пути: токен ссылки для близких наружу не попадает.
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', f"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data: {TILE_HOSTS}; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def load_trip(self, trip_id):
        with connect() as con:
            return con.execute('SELECT * FROM trips WHERE id=?', (trip_id,)).fetchone()

    def handle_get(self):
        url = urlparse(self.path)
        path = url.path
        if path == '/api/routes':
            return self.send_body(200, ROUTES)
        match = re.fullmatch(r'/api/routes/([\w-]{1,40})/track', path)
        if match:
            track = TRACKS.get(match.group(1))
            return self.send_body(200, track) if track else self.send_body(404, {'error': 'У этого маршрута нет трека'})
        if path == '/api/proposals':
            with connect() as con:
                rows = con.execute('SELECT * FROM proposals ORDER BY status=\'pending\' DESC, id DESC').fetchall()
            return self.send_body(200, [proposal_public(r, full=False) for r in rows])
        match = re.fullmatch(r'/api/proposals/(\d{1,12})', path)
        if match:
            with connect() as con:
                row = con.execute('SELECT * FROM proposals WHERE id=?', (int(match.group(1)),)).fetchone()
            return self.send_body(200, proposal_public(row, full=True)) if row else self.send_body(404, {'error': 'Предложение не найдено'})
        if path == '/api/ai-status':
            enabled, text = tau_ai.status()
            return self.send_body(200, {'enabled': enabled, 'text': text})
        if path == '/api/weather':
            query = parse_qs(url.query)
            route = ROUTE_BY_ID.get(query.get('route_id', [''])[0])
            if not route:
                return self.send_body(400, {'error': 'Неизвестный маршрут'})
            return self.send_body(200, tau_weather.forecast_for_route(route, query.get('date', [date.today().isoformat()])[0]))
        if path == '/api/trips':
            with connect() as con:
                rows = con.execute('SELECT * FROM trips ORDER BY start_date,id').fetchall()
            return self.send_body(200, [trip_summary(r) for r in rows])
        if path == '/api/metrics':
            with connect() as con:
                rows = con.execute('SELECT audit_json FROM trips WHERE audit_json IS NOT NULL').fetchall()
            stats = {'audits': len(rows), 'ai_audits': 0, 'accepted': 0, 'rejected': 0, 'undecided': 0, 'dropped_by_validation': 0}
            for row in rows:
                audit = json.loads(row['audit_json'])
                stats['ai_audits'] += audit['mode'] == 'ai'
                stats['dropped_by_validation'] += audit['validation']['dropped_no_evidence'] + audit['validation']['dropped_numbers']
                for rec in audit['recommendations']:
                    stats[{'accepted': 'accepted', 'rejected': 'rejected'}.get(rec['decision'], 'undecided')] += 1
            decided = stats['accepted'] + stats['rejected']
            stats['acceptance_rate_pct'] = round(100 * stats['accepted'] / decided) if decided else None
            return self.send_body(200, stats)
        match = re.fullmatch(r'/api/trips/(\d{1,12})(/notice)?', path)
        if match:
            row = self.load_trip(int(match.group(1)))
            if not row:
                return self.send_body(404, {'error': 'Поход не найден'})
            if match.group(2):
                return self.send_body(200, {'text': notice_text(row), 'channels': 'Отправьте сами: приложение eQonaq, электронная почта ДЧС вашего региона или телефон 112. В Алматы маршрут также можно зарегистрировать на платформе Almaty Hike (almatyhike.kz). TAU ничего не отправляет в МЧС.'})
            return self.send_body(200, trip_full(row))
        match = re.fullmatch(r'/api/share/([\w-]{10,60})', path)
        if match:
            with connect() as con:
                row = con.execute('SELECT * FROM trips WHERE share_token=?', (match.group(1),)).fetchone()
            if not row or datetime.now() > datetime.fromisoformat(row['share_expires']):
                return self.send_body(404, {'error': 'Ссылка недействительна, отозвана или её срок истёк'})
            route, audit = ROUTE_BY_ID[row['route_id']], json.loads(row['audit_json']) if row['audit_json'] else None
            show = bool(audit and row['confirmed'])  # близкие видят сводку только после подтверждения организатором
            return self.send_body(200, {
                'title': row['title'], 'route': route['name'], 'area': route['area'], 'distance': route['distance'], 'max_elev': route['max_elev'],
                'start_date': row['start_date'], 'start_time': row['start_time'], 'return_time': row['return_time'], 'participants': row['participants'],
                'organizer': row['organizer'], 'status': row['status'], 'status_label': STATUSES[row['status']], 'overdue': is_overdue(row),
                'summary': audit['summary'] if show else None, 'summary_by_ai': bool(show and audit['mode'] == 'ai'),
                'estimate': audit['estimate'] if audit else None, 'expires': row['share_expires'], 'checked_at': datetime.now().strftime('%d.%m.%Y %H:%M')})
        if re.fullmatch(r'/p/[\w-]{10,60}', path):
            return self.send_body(200, (ROOT / 'static' / 'share.html').read_bytes(), 'text/html; charset=utf-8')
        static = {'/': ('index.html', 'text/html; charset=utf-8'), '/static/style.css': ('style.css', 'text/css; charset=utf-8'), '/static/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/static/share.js': ('share.js', 'text/javascript; charset=utf-8'), '/static/icon.svg': ('icon.svg', 'image/svg+xml'),
                  '/static/vendor/leaflet.js': ('vendor/leaflet.js', 'text/javascript; charset=utf-8'), '/static/vendor/leaflet.css': ('vendor/leaflet.css', 'text/css; charset=utf-8')}
        if path in static:
            filename, mime = static[path]
            return self.send_body(200, (ROOT / 'static' / filename).read_bytes(), mime)
        self.send_body(404, {'error': 'Страница не найдена'})

    def read_json(self, limit=MAX_BODY):
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= limit:
            raise ValueError('Файл слишком большой: до 5 МБ' if size > limit and limit > MAX_BODY else 'Недопустимый размер запроса')
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict):
            raise ValueError('Некорректный запрос')
        return data

    def handle_post(self):
        path = urlparse(self.path).path
        match = re.fullmatch(r'/api/trips(?:/(\d{1,12})/(audit|decision|confirm|status|share|delete|update|gear))?', path)
        proposal = re.fullmatch(r'/api/proposals(?:/(\d{1,12})/(approve|reject))?', path)
        if not match and not proposal:
            return self.send_body(404, {'error': 'Адрес не найден'})
        # Only same-origin JSON requests can change this local prototype.
        origin = self.headers.get('Origin')
        if origin and urlparse(origin).netloc != self.headers.get('Host'):
            return self.send_body(403, {'error': 'Запрос с другого сайта запрещён'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send_body(415, {'error': 'Ожидается JSON'})
        if proposal:
            return self.handle_proposal(proposal)
        try:
            data = self.read_json()
            if not match.group(1):
                title, route_id, start_date, start_time, return_time, organizer, phone, members = parse_trip(data)
                with connect() as con:
                    result = con.execute('INSERT INTO trips(title,route_id,start_date,start_time,return_time,organizer,organizer_phone,participants,members_json) VALUES (?,?,?,?,?,?,?,?,?)',
                                         (title, route_id, start_date, start_time, return_time, organizer, phone, len(members), json.dumps(members, ensure_ascii=False)))
                return self.send_body(201, {'id': result.lastrowid, 'message': 'Паспорт похода сохранён локально. В МЧС сведения не отправлены.'})
            trip_id, action = int(match.group(1)), match.group(2)
            row = self.load_trip(trip_id)
            if not row:
                return self.send_body(404, {'error': 'Поход не найден'})
            if action == 'audit':
                route, members = ROUTE_BY_ID[row['route_id']], json.loads(row['members_json'])
                weather = tau_weather.forecast_for_route(route, row['start_date'])
                analysis = tau_rules.analyze(route, {'start_time': row['start_time'], 'return_time': row['return_time'], 'date': row['start_date']}, members, weather)
                audit = tau_ai.build_audit(analysis, weather)
                # решения организатора переносятся на те же замечания, если повторная проверка их сохранила
                previous = json.loads(row['audit_json']) if row['audit_json'] else {'recommendations': []}
                decided = {(r['code'], r['severity'], tuple(r['affected'])): r['decision'] for r in previous['recommendations'] if r['code'] != 'OTHER'}
                for rec in audit['recommendations']:
                    rec['decision'] = decided.get((rec['code'], rec['severity'], tuple(rec['affected'])))
                self.save(trip_id, audit_json=json.dumps(audit, ensure_ascii=False), confirmed=0)
            elif action == 'update':
                title, route_id, start_date, start_time, return_time, organizer, phone, members = parse_trip(data)
                fields = dict(title=title, route_id=route_id, start_date=start_date, start_time=start_time, return_time=return_time, organizer=organizer, organizer_phone=phone,
                              participants=len(members), members_json=json.dumps(members, ensure_ascii=False), audit_json=stale_audit(row), confirmed=0)
                if row['share_token']:
                    fields['share_expires'] = share_end(start_date, return_time)
                self.save(trip_id, **fields)
            elif action == 'gear':
                members, index, code = json.loads(row['members_json']), data.get('member'), data.get('code')
                if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(members) or code not in tau_rules.GEAR or not isinstance(data.get('has'), bool):
                    raise ValueError('Некорректная отметка снаряжения')
                gear = set(members[index]['gear'])
                (gear.add if data['has'] else gear.discard)(code)
                members[index]['gear'] = sorted(gear)
                self.save(trip_id, members_json=json.dumps(members, ensure_ascii=False), audit_json=stale_audit(row), confirmed=0)
            elif action == 'decision':
                audit = json.loads(row['audit_json'] or 'null')
                rec = next((r for r in (audit or {}).get('recommendations', []) if r['id'] == data.get('rec_id')), None)
                if not rec or data.get('decision') not in ('accepted', 'rejected', None):
                    raise ValueError('Рекомендация не найдена')
                rec['decision'] = data.get('decision')
                self.save(trip_id, audit_json=json.dumps(audit, ensure_ascii=False), confirmed=0)
            elif action == 'confirm':
                audit = json.loads(row['audit_json'] or 'null')
                if not audit:
                    raise ValueError('Сначала запустите аудит')
                if audit.get('stale'):
                    raise ValueError('Поход изменился после проверки. Запустите проверку заново')
                if any(r['decision'] is None and r['severity'] != 'info' for r in audit['recommendations']):
                    raise ValueError('Примите или отклоните каждую рекомендацию, отмеченную как важная или критическая')
                self.save(trip_id, confirmed=1)
            elif action == 'status':
                if data.get('status') not in STATUSES:
                    raise ValueError('Неизвестный статус')
                self.save(trip_id, status=data['status'])
            elif action == 'share':
                if data.get('action') == 'revoke':
                    self.save(trip_id, share_token=None, share_expires=None)
                else:
                    self.save(trip_id, share_token=secrets.token_urlsafe(18), share_expires=share_end(row['start_date'], row['return_time']))
            elif action == 'delete':
                with connect() as con:
                    con.execute('DELETE FROM trips WHERE id=?', (trip_id,))
                return self.send_body(200, {'message': 'Поход удалён'})
            self.send_body(200, trip_full(self.load_trip(trip_id)))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_body(400, {'error': str(exc) or 'Проверьте заполнение полей'})

    def handle_proposal(self, match):
        try:
            if not match.group(1):
                data = self.read_json(MAX_GPX_BODY)
                name, activity, area, description, author, claimed, segments = parse_proposal(data)
                try:
                    track = tau_geo.analyze(segments, elevations_of=lambda pts: tau_geo.fetch_elevations(pts, per_point_pause=0, retries=1))
                except OSError:
                    return self.send_body(503, {'error': 'Сервис высот рельефа сейчас не отвечает или перегружен. Попробуйте через минуту'})
                checks = proposal_checks(name, description, track['stats'], track['terrain'], claimed)
                with connect() as con:
                    new_id = con.execute('INSERT INTO proposals(name,area,activity,description,author,track_json,checks_json) VALUES (?,?,?,?,?,?,?)',
                                         (name, area, activity, description, author, json.dumps(track), json.dumps(checks, ensure_ascii=False))).lastrowid
                    row = con.execute('SELECT * FROM proposals WHERE id=?', (new_id,)).fetchone()
                return self.send_body(201, proposal_public(row, full=True))
            data = self.read_json()
            pid, action = int(match.group(1)), match.group(2)
            note = clean_text(data.get('note', ''), 0, 300, 'Комментарий модератора')
            if action == 'reject' and not note:
                raise ValueError('Напишите автору, почему маршрут отклонён')
            with connect() as con:
                row = con.execute('SELECT * FROM proposals WHERE id=?', (pid,)).fetchone()
                if not row:
                    return self.send_body(404, {'error': 'Предложение не найдено'})
                if row['status'] != 'pending':
                    raise ValueError('Решение по этому маршруту уже принято')
                con.execute('UPDATE proposals SET status=?, moderator_note=?, decided_at=CURRENT_TIMESTAMP WHERE id=?',
                            ('approved' if action == 'approve' else 'rejected', note, pid))
                row = con.execute('SELECT * FROM proposals WHERE id=?', (pid,)).fetchone()
            load_catalog()
            return self.send_body(200, proposal_public(row, full=True))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.send_body(400, {'error': str(exc) or 'Проверьте заполнение полей'})

    def save(self, trip_id, **fields):
        with connect() as con:
            con.execute(f'UPDATE trips SET {",".join(f"{k}=?" for k in fields)} WHERE id=?', (*fields.values(), trip_id))


load_catalog()


def lan_address():
    """Адрес компьютера в локальной сети. Пакет никуда не отправляется: UDP-сокет только выбирает маршрут."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(('192.168.0.1', 9))
            return probe.getsockname()[0]
        except OSError:
            return '127.0.0.1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--lan', action='store_true', help='открыть доступ с телефона и других устройств в той же сети (без пароля)')
    args = parser.parse_args()
    initialize_db()
    tau_geo.load_cache(ROOT / 'data' / 'elevation_cache.json')
    enabled, text = tau_ai.status()
    server = ThreadingHTTPServer(('0.0.0.0' if args.lan else '127.0.0.1', args.port), Handler)
    print(f'Откройте http://127.0.0.1:{args.port}  •  Ctrl+C для остановки', flush=True)
    if args.lan:
        print(f'С телефона в той же сети: http://{lan_address()}:{args.port}', flush=True)
        print('Внимание: пароля нет, походы увидит любой в этой сети. Для показа и демо, не для настоящих данных.', flush=True)
    print(('ИИ-режим: ' if enabled else 'Режим без ИИ (только правила): ') + text, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
