import json
import math
import unittest
from datetime import date, timedelta
from unittest import mock

import app
import tau_geo
import tau_rules
import test_app


def fake_elevations(points):
    """Ровный склон: высота растёт к северу на 1 м каждые 10 м."""
    return [1500 + (p[0] - 43.10) * 111195 / 10 for p in points]


def gpx(points, extra=''):
    body = ''.join(f'<trkpt lat="{lat}" lon="{lon}"><ele>{ele}</ele><time>2026-11-01T08:00:00Z</time></trkpt>' for lat, lon, ele in points)
    return f'<?xml version="1.0"?>{extra}<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Мой трек</name><trkseg>{body}</trkseg></trk></gpx>'


LINE = [(43.10 + i * 0.0005, 77.05, 1500 + i * 5) for i in range(60)]  # около 3,3 км на север


class GeoTests(unittest.TestCase):
    def test_parse_gpx_keeps_only_coordinates(self):
        segments = tau_geo.parse_gpx(gpx(LINE))
        self.assertEqual(len(segments), 1)
        self.assertEqual(len(segments[0][0]), 3)  # lat, lon, ele — без времени
        self.assertAlmostEqual(tau_geo.length_m(segments) / 1000, 3.28, delta=0.05)

    def test_rejects_dangerous_or_foreign_files(self):
        bomb = '<!DOCTYPE gpx [<!ENTITY a "aaaa">]>'
        for text, why in ((gpx(LINE, bomb), 'XML'), ('<html></html>', 'GPX'), (gpx(LINE[:5]), '10 точек'),
                          (gpx([(48.85 + i * 0.001, 2.35, 50) for i in range(20)]), 'Казахстан'), ('', 'пустой')):
            with self.assertRaises(tau_geo.TrackError, msg=why) as ctx:
                tau_geo.parse_gpx(text)
            self.assertIn(why, str(ctx.exception))

    def test_gps_jump_splits_track(self):
        points = LINE[:20] + [(43.30, 77.05, 2000)] + [(43.30 + i * 0.0005, 77.05, 2000) for i in range(1, 20)]
        self.assertEqual(len(tau_geo.parse_gpx(gpx(points))), 2)

    def test_analyze_profile_and_slope(self):
        result = tau_geo.analyze(tau_geo.parse_gpx(gpx(LINE)), elevations_of=fake_elevations)
        s, t = result['stats'], result['terrain']
        self.assertAlmostEqual(s['ascent_m'], 328, delta=15)  # 1 м на 10 м по горизонтали
        self.assertEqual(s['max_elev'], round(fake_elevations([s['top']])[0]))
        self.assertAlmostEqual(t['max_slope_deg'], math.degrees(math.atan(0.1)), delta=1)
        self.assertEqual(t['km_slope_30_45'], 0)
        self.assertAlmostEqual(t['max_trail_grade_pct'], 10, delta=1)

    def test_gap_between_pieces_is_not_climb(self):
        low = [(43.10 + i * 0.0005, 77.05, 0) for i in range(10)]
        high = [(43.20 + i * 0.0005, 77.05, 0) for i in range(10)]  # кусок на 11 км севернее: по модели выше на ~1100 м
        flat = lambda pts: [1500 + (p[0] > 43.15) * 1100 for p in pts]
        result = tau_geo.analyze(tau_geo.clean([low, high]), elevations_of=flat)
        self.assertEqual(result['stats']['segments'], 2)
        self.assertEqual(result['stats']['ascent_m'], 0)
        self.assertEqual(result['terrain']['max_trail_grade_pct'], 0)

    def test_chain_reverses_ways(self):
        a, b = [(43.0, 77.0), (43.001, 77.0)], [(43.002, 77.0), (43.001, 77.0)]  # вторая линия нарисована задом наперёд
        self.assertEqual(tau_geo.chain([a, b]), [[(43.0, 77.0), (43.001, 77.0), (43.002, 77.0)]])

    def test_terrain_rules(self):
        route = dict(app.ROUTE_BY_ID['bao'], terrain={'max_trail_grade_pct': 35, 'max_slope_deg': 52, 'max_slope_at_km': 3.1, 'km_slope_30_45': 1.2, 'km_slope_45_plus': 0.3, 'source': 'тест'})
        novice = {'name': 'А', 'experience': 'novice', 'age_group': 'adult', 'gear': list(tau_rules.GEAR), 'bulky': 'none'}
        winter = tau_rules.analyze(route, {'start_time': '08:00', 'return_time': '20:00', 'date': '2026-12-05'}, [novice], {'available': False, 'reason': 'тест'})
        codes = {f['code']: f for f in winter['flags']}
        self.assertIn('AVALANCHE_TERRAIN', codes)
        self.assertEqual(codes['CLIFFS']['severity'], 'warning')
        self.assertIn('STEEP_TRAIL', codes)
        self.assertEqual(winter['facts']['terrain.km_slope_30_45'], 1.2)
        summer = tau_rules.analyze(route, {'start_time': '08:00', 'return_time': '20:00', 'date': '2026-07-05'}, [novice], {'available': False, 'reason': 'тест'})
        self.assertNotIn('AVALANCHE_TERRAIN', {f['code'] for f in summer['flags']})
        plain = tau_rules.analyze(app.ROUTE_BY_ID['bao'], {'start_time': '08:00', 'return_time': '20:00', 'date': '2026-12-05'}, [novice], {'available': False, 'reason': 'тест'})
        self.assertFalse({'AVALANCHE_TERRAIN', 'CLIFFS', 'STEEP_TRAIL'} & {f['code'] for f in plain['flags']})


class ProposalTests(test_app.ServerTestCase):
    """Предложения маршрутов: загрузка GPX, проверки для модератора, публикация в каталог."""

    def setUp(self):
        patcher = mock.patch.object(tau_geo, 'fetch_elevations', side_effect=lambda pts, **kw: fake_elevations(pts))
        patcher.start()
        self.addCleanup(patcher.stop)

    def propose(self, **extra):
        payload = {'gpx': gpx(LINE), 'name': 'Тестовая тропа', 'activity': 'hiking', 'area': 'Иле-Алатау', 'description': 'Тропа вдоль ручья, вода есть внизу. Пишите +7 701 000 00 00',
                   'author': 'Автор', 'claimed_km': 8, 'consent': True, **extra}
        return self.call('/api/proposals', payload)

    def test_proposal_moderation_flow(self):
        self.assertEqual(self.propose(consent=False)[0], 400)
        self.assertEqual(self.propose(gpx='<gpx>')[0], 400)
        status, p = self.propose()
        self.assertEqual(status, 201, p)
        self.assertEqual(p['status'], 'pending')
        texts = ' '.join(c['text'] for c in p['checks'])
        self.assertIn('телефон', texts)  # подозрение на рекламу
        self.assertIn('8 км', texts)  # заявленная длина не совпадает с треком
        self.assertNotIn('2026-11-01', json.dumps(p))  # время записи не сохраняется
        rid = f'user-{p["id"]}'
        self.assertNotIn(rid, {r['id'] for r in self.call('/api/routes')[1]})  # до модерации маршрута в каталоге нет
        self.assertEqual(self.call(f'/api/proposals/{p["id"]}/reject', {'note': ''})[0], 400)  # отказ без объяснения нельзя
        status, done = self.call(f'/api/proposals/{p["id"]}/approve', {'note': 'Проверено'})
        self.assertEqual((status, done['status']), (200, 'approved'))
        self.assertEqual(self.call(f'/api/proposals/{p["id"]}/reject', {'note': 'поздно'})[0], 400)
        route = next(r for r in self.call('/api/routes')[1] if r['id'] == rid)
        self.assertEqual(route['source'], 'user')
        self.assertEqual(self.call(f'/api/routes/{rid}/track')[0], 200)
        trip = self.new_trip(route_id=rid)
        audit = self.call(f'/api/trips/{trip}/audit', {})[1]['audit']
        keys = {e['key'] for r in audit['recommendations'] for e in r['evidence']}
        self.assertTrue(audit['recommendations'])
        self.assertIsInstance(keys, set)

    def test_track_endpoint_404_for_catalog_route(self):
        self.assertEqual(self.call('/api/routes/bao/track')[0], 404)


if __name__ == '__main__':
    unittest.main()
