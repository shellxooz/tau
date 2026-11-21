"""Импорт пеших маршрутов вокруг Алматы из OpenStreetMap в catalog/osm_routes.json.

Источник: Overpass API, отношения route=hiking. Данные © участники OpenStreetMap, лицензия ODbL:
при показе нужна атрибуция, производная база распространяется на тех же условиях.
Длина, набор и крутизна считаются по треку и модели рельефа Open-Meteo, а не берутся из тегов.

Запуск из папки mountain_site:  py tools/import_osm.py
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tau_geo  # noqa: E402

BBOX = (42.85, 76.6, 43.3, 77.4)  # юг, запад, север, восток: Иле-Алатау у Алматы
OVERPASS = 'https://overpass-api.de/api/interpreter'
OUT = ROOT / 'catalog' / 'osm_routes.json'


MIRRORS = (OVERPASS, 'https://overpass.kumi.systems/api/interpreter', 'https://overpass.private.coffee/api/interpreter')


def overpass(query):
    last = None
    for attempt, url in enumerate(MIRRORS):
        request = urllib.request.Request(url, data=urllib.parse.urlencode({'data': query}).encode(), headers={'User-Agent': 'TAU-prototype (student project)'})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)
        except OSError as exc:  # 502/504 и обрывы у публичных серверов Overpass бывают часто
            last = exc
            print(f'Overpass {url}: {exc}; пробую дальше', flush=True)
            time.sleep(5 + attempt * 5)
    raise last


def relation_full(rel_id):
    """Геометрия отношения из основного API OpenStreetMap (/relation/<id>/full) в том же виде, что даёт Overpass «out geom»."""
    import xml.etree.ElementTree as ET
    request = urllib.request.Request(f'https://api.openstreetmap.org/api/0.6/relation/{rel_id}/full', headers={'User-Agent': 'TAU-prototype (student project)'})
    with urllib.request.urlopen(request, timeout=60) as response:
        root = ET.fromstring(response.read())
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in root.iter('node')}
    ways = {w.get('id'): [nodes[nd.get('ref')] for nd in w.iter('nd') if nd.get('ref') in nodes] for w in root.iter('way')}
    rel = next(r for r in root.iter('relation') if r.get('id') == str(rel_id))
    members = [{'type': 'way', 'geometry': [{'lat': p[0], 'lon': p[1]} for p in ways[m.get('ref')]]}
               for m in rel.iter('member') if m.get('type') == 'way' and m.get('ref') in ways and m.get('role', '') in ('', 'forward', 'backward', 'main')]
    return {'id': rel_id, 'tags': {t.get('k'): t.get('v') for t in rel.iter('tag')}, 'members': members}


def name_of(tags):
    return tags.get('name:ru') or tags.get('name') or tags.get('name:en') or tags.get('name:kk')


def main():
    tau_geo.load_cache(ROOT / 'data' / 'elevation_cache.json')
    # сначала только список отношений (лёгкий запрос), затем геометрия каждого по отдельности:
    # один большой запрос с геометрией публичные серверы Overpass часто обрывают
    listing_path = ROOT / 'catalog' / 'osm_listing.json'
    try:
        if '--cached' in sys.argv and listing_path.exists():
            raise OSError('взят сохранённый список (--cached)')
        listing = overpass(f'[out:json][timeout:60];relation["route"="hiking"]({",".join(map(str, BBOX))});out tags;')
        listing_path.parent.mkdir(exist_ok=True)
        listing_path.write_text(json.dumps(listing, ensure_ascii=False), encoding='utf-8')
    except OSError:
        if not listing_path.exists():
            raise
        print('Overpass недоступен: беру список маршрутов из прошлого импорта', flush=True)
        listing = json.loads(listing_path.read_text(encoding='utf-8'))
    print(f'Найдено отношений: {len(listing["elements"])}', flush=True)
    routes, tracks, skipped = [], {}, []
    for item in listing['elements']:
        try:
            rel = relation_full(item['id'])
        except OSError as exc:
            skipped.append((item['id'], name_of(item.get('tags', {})), f'геометрия не загрузилась: {exc}'))
            continue
        time.sleep(1)  # бережём API OpenStreetMap: один запрос в секунду
        tags, name = rel.get('tags', {}), name_of(rel.get('tags', {}))
        ways = [[(g['lat'], g['lon']) for g in m['geometry']] for m in rel.get('members', []) if m.get('type') == 'way' and m.get('geometry')]
        if not name or not ways:
            skipped.append((rel['id'], name, 'нет имени или геометрии'))
            continue
        try:
            segments = tau_geo.clean([[(p[0], p[1], None) for p in s] for s in tau_geo.chain(ways)])
        except tau_geo.TrackError as exc:
            skipped.append((rel['id'], name, str(exc)))
            continue
        km = tau_geo.length_m(segments) / 1000
        if not 1 <= km <= 60:
            skipped.append((rel['id'], name, f'длина {km:.1f} км вне 1–60 км'))
            continue
        try:
            result = tau_geo.analyze(segments, step=150)
            if result['stats']['finish_elev'] < result['stats']['start_elev'] and not result['stats']['loop']:
                segments = [list(reversed(s)) for s in reversed(segments)]  # старт — с нижнего конца
                result = tau_geo.analyze(segments, step=150)
        except OSError as exc:
            skipped.append((rel['id'], name, f'высоты не загрузились: {exc}; запустите импорт ещё раз, готовые высоты возьмутся из кэша'))
            continue
        s = result['stats']
        hours = tau_geo.naismith_hours(s['distance_km'], s['ascent_m'])
        lo, hi = max(1, round(hours)), max(1, round(hours * 1.3))
        rid = f'osm-{rel["id"]}'
        route_from, route_to = tags.get('from'), tags.get('to')
        routes.append({
            'id': rid, 'name': name, 'area': 'Иле-Алатау', 'activity': 'hiking', 'activityLabel': 'Пеший',
            'distance': s['distance_km'], 'hours': f'{lo}–{hi}' if hi > lo else str(lo), 'hours_max': hi, 'ascent': s['ascent_m'],
            'level': tau_geo.level_for(s['distance_km'], s['ascent_m'], s['max_elev']), 'className': 'green',
            'tag': f'{route_from} → {route_to}' if route_from and route_to else ('Кольцевой маршрут' if s['loop'] else 'Маршрут из OpenStreetMap'),
            'lat': s['start'][0], 'lon': s['start'][1], 'top_lat': s['top'][0], 'top_lon': s['top'][1],
            'start_elev': s['start_elev'], 'max_elev': s['max_elev'],
            'description': (tags.get('description', '') + ' ' if tags.get('description') else '') + 'Маршрут из открытых данных OpenStreetMap. Длина, набор высоты и сложность посчитаны TAU по треку и модели рельефа; на местности трек не проверялся.'
                           + (f' В OpenStreetMap трек разорван на {s["segments"]} части, поэтому длина и набор могут быть занижены.' if s['segments'] > 1 else ''),
            'source': 'osm', 'source_url': f'https://www.openstreetmap.org/relation/{rel["id"]}', 'has_track': True,
        })
        tracks[rid] = result
        print(f'+ {name}: {s["distance_km"]} км, +{s["ascent_m"]} м, до {s["max_elev"]} м', flush=True)
        time.sleep(0.5)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({'generated_at': datetime.now().isoformat(timespec='minutes'), 'attribution': '© участники OpenStreetMap, ODbL',
                               'bbox': BBOX, 'routes': routes, 'tracks': tracks}, ensure_ascii=False), encoding='utf-8')
    print(f'Готово: {len(routes)} маршрутов → {OUT}')
    for item in skipped:
        print('пропущен:', *item)


if __name__ == '__main__':
    main()
