import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import app
import tau_ai

FAKE_WEATHER = {'available': False, 'reason': 'тестовый режим без сети'}
MEMBERS = [
    {'name': 'Айдар Тестов', 'experience': 'expert', 'age_group': 'adult', 'gear': list(app.tau_rules.GEAR), 'bulky': 'none'},
    {'name': 'Дана Примерова', 'experience': 'novice', 'age_group': 'adult', 'gear': ['water'], 'bulky': 'pack'},
]


class ServerTestCase(unittest.TestCase):
    """Тестовый сервер на временной базе, без сети. Тестов здесь нет, только общая подготовка."""
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        app.DB_PATH = Path(cls.directory.name) / 'trips.sqlite3'
        app.initialize_db()
        cls.patches = [mock.patch.object(app.tau_weather, 'forecast_for_route', return_value=FAKE_WEATHER), mock.patch.object(tau_ai, 'status', return_value=(False, 'тест'))]
        for patch in cls.patches:
            patch.start()
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        for patch in cls.patches:
            patch.stop()
        cls.directory.cleanup()

    def request(self, path, payload=None, headers=None):
        request = urllib.request.Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers or ({'Content-Type': 'application/json'} if payload is not None else {}))
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def call(self, path, payload=None):
        status, body = self.request(path, payload)
        return status, json.loads(body)

    def new_trip(self, **extra):
        payload = {'title': 'Тестовая группа', 'route_id': 'bao', 'start_date': (date.today() + timedelta(days=3)).isoformat(), 'start_time': '08:00', 'return_time': '18:00',
                   'organizer': 'Айдар Тестов', 'organizer_phone': '+7 000 000 00 00', 'members': MEMBERS, **extra}
        status, body = self.call('/api/trips', payload)
        self.assertEqual(status, 201, body)
        return body['id']


class ApplicationTests(ServerTestCase):
    def test_pages_and_route_catalog(self):
        for path in ['/', '/static/style.css', '/static/app.js', '/static/share.js', '/static/icon.svg']:
            self.assertEqual(self.request(path)[0], 200)
        routes = self.call('/api/routes')[1]
        self.assertEqual(sum(r['source'] == 'tau' for r in routes), 15)
        self.assertEqual(len({r['id'] for r in routes}), len(routes))
        for r in routes:
            if r['source'] == 'osm':  # маршруты OpenStreetMap: трек есть, цифры правдоподобны
                self.assertTrue(r['has_track'] and r['source_url'].startswith('https://www.openstreetmap.org/relation/'))
                self.assertLess(r['terrain']['max_trail_grade_pct'], 120, r['name'])
        self.assertTrue(all(r['max_elev'] >= r['start_elev'] for r in routes))
        self.assertEqual(self.request('/app.py')[0], 404)

    def test_create_trip_and_persistence(self):
        payload = {'title': 'Старый формат', 'route_id': 'kok-zhailau', 'start_date': (date.today() + timedelta(days=3)).isoformat(), 'participants': 3}
        status, body = self.call('/api/trips', payload)
        self.assertEqual(status, 201)
        with sqlite3.connect(app.DB_PATH) as con:
            self.assertEqual(con.execute('SELECT title,participants FROM trips WHERE id=?', (body['id'],)).fetchone(), ('Старый формат', 3))
        self.assertTrue(any(t['id'] == body['id'] for t in self.call('/api/trips')[1]))

    def test_invalid_trip_rejected(self):
        base = {'title': 'Тест', 'route_id': 'kok-zhailau', 'start_date': date.today().isoformat(), 'participants': 2}
        for change in ({'participants': 0}, {'route_id': 'unknown'}, {'start_time': '25:00'}, {'start_time': '10:00', 'return_time': '09:00'},
                       {'members': [{'name': 'А', 'experience': 'guru', 'age_group': 'adult', 'gear': []}]}, {'members': [{'name': 'А', 'experience': 'some', 'age_group': 'adult', 'gear': ['jetpack']}]}):
            self.assertEqual(self.request('/api/trips', {**base, **change})[0], 400, change)

    def test_cross_origin_rejected(self):
        self.assertEqual(self.request('/api/trips', {}, {'Content-Type': 'application/json', 'Origin': 'https://example.com'})[0], 403)

    def test_foreign_host_rejected(self):
        """DNS rebinding: запрос приходит на наш адрес, но с чужим именем в заголовке Host."""
        self.assertEqual(self.request('/api/trips', headers={'Host': 'evil.example:8000'})[0], 403)
        self.assertEqual(self.request('/api/trips', headers={'Host': 'localhost:8000'})[0], 200)

    def test_malformed_requests_get_an_answer(self):
        base = {'title': 'Тест', 'route_id': 'kok-zhailau', 'start_date': (date.today() + timedelta(days=3)).isoformat(), 'participants': 2}
        self.assertEqual(self.request('/api/trips', {**base, 'return_time': '18:00\n'})[0], 400)
        self.assertEqual(self.request('/api/trips', {**base, 'start_time': 800})[0], 400)
        self.assertEqual(self.request('/api/trips', {**base, 'start_date': '9999-12-31'})[0], 400)
        self.assertEqual(self.request('/api/trips/99999999999999999999')[0], 404)
        self.assertEqual(self.request('/api/trips/999999999999')[0], 404)
        deep = urllib.request.Request(self.url + '/api/trips', data=b'[' * 20000, headers={'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(deep)
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(self.request('/api/trips')[0], 200)  # список походов после всего этого открывается

    def test_audit_decisions_and_confirmation(self):
        trip_id = self.new_trip()
        self.assertEqual(self.call(f'/api/trips/{trip_id}/confirm', {})[0], 400)  # без аудита подтверждать нечего
        status, trip = self.call(f'/api/trips/{trip_id}/audit', {})
        self.assertEqual(status, 200)
        audit = trip['audit']
        self.assertEqual(audit['mode'], 'rules')
        codes = {r['code'] for r in audit['recommendations']}
        self.assertTrue({'NO_WEATHER', 'EFFORT', 'NO_BOOTS'} <= codes, codes)
        self.assertEqual(audit['transport']['vehicle'], 'Легковой автомобиль или такси')
        self.assertEqual(self.call(f'/api/trips/{trip_id}/confirm', {})[0], 400)  # есть нерешённые рекомендации
        for rec in audit['recommendations']:
            self.assertEqual(self.call(f'/api/trips/{trip_id}/decision', {'rec_id': rec['id'], 'decision': 'accepted'})[0], 200)
        status, trip = self.call(f'/api/trips/{trip_id}/confirm', {})
        self.assertTrue(trip['confirmed'])
        metrics = self.call('/api/metrics')[1]
        self.assertGreaterEqual(metrics['accepted'], len(audit['recommendations']))

    def test_gear_mark_makes_audit_stale_and_reaudit_keeps_decisions(self):
        trip_id = self.new_trip()
        audit = self.call(f'/api/trips/{trip_id}/audit', {})[1]['audit']
        self.assertTrue(all(item['code'] in app.tau_rules.GEAR for entry in audit['checklists'] for item in entry['items']))
        for rec in audit['recommendations']:
            self.call(f'/api/trips/{trip_id}/decision', {'rec_id': rec['id'], 'decision': 'accepted'})
        self.assertTrue(self.call(f'/api/trips/{trip_id}/confirm', {})[1]['confirmed'])
        for bad in ({'member': 9, 'code': 'boots', 'has': True}, {'member': 1, 'code': 'jetpack', 'has': True}, {'member': 1, 'code': 'boots', 'has': 'yes'}):
            self.assertEqual(self.call(f'/api/trips/{trip_id}/gear', bad)[0], 400, bad)
        status, trip = self.call(f'/api/trips/{trip_id}/gear', {'member': 1, 'code': 'boots', 'has': True})
        self.assertEqual(status, 200)
        self.assertIn('boots', trip['members'][1]['gear'])
        self.assertTrue(trip['audit']['stale'])
        self.assertFalse(trip['confirmed'])
        self.assertEqual(self.call(f'/api/trips/{trip_id}/confirm', {})[0], 400)  # устаревшую проверку подтвердить нельзя
        fresh = self.call(f'/api/trips/{trip_id}/audit', {})[1]['audit']
        self.assertNotIn('stale', fresh)
        self.assertNotIn('NO_BOOTS', {r['code'] for r in fresh['recommendations']})
        self.assertTrue(all(r['decision'] == 'accepted' for r in fresh['recommendations'] if r['code'] == 'EFFORT'))

    def test_update_trip(self):
        trip_id = self.new_trip()
        self.call(f'/api/trips/{trip_id}/audit', {})
        day = (date.today() + timedelta(days=5)).isoformat()
        payload = {'title': 'Новое название', 'route_id': 'butakovka', 'start_date': day, 'start_time': '09:00', 'return_time': '15:00', 'organizer': 'Айдар Тестов', 'organizer_phone': '', 'members': MEMBERS[:1]}
        status, trip = self.call(f'/api/trips/{trip_id}/update', payload)
        self.assertEqual(status, 200)
        self.assertEqual((trip['title'], trip['route_id'], trip['start_date'], trip['participants']), ('Новое название', 'butakovka', day, 1))
        self.assertTrue(trip['audit']['stale'])
        self.assertEqual(self.call(f'/api/trips/{trip_id}/update', {**payload, 'route_id': 'nowhere'})[0], 400)
        summary = next(t for t in self.call('/api/trips')[1] if t['id'] == trip_id)
        self.assertTrue(summary['stale'])

    def test_share_link_hides_private_data_and_can_be_revoked(self):
        trip_id = self.new_trip()
        self.call(f'/api/trips/{trip_id}/audit', {})
        token = self.call(f'/api/trips/{trip_id}/share', {'action': 'create'})[1]['share']['token']
        self.assertEqual(self.request(f'/p/{token}')[0], 200)
        status, raw = self.request(f'/api/share/{token}')
        self.assertEqual(status, 200)
        text = raw.decode()
        self.assertNotIn('Дана Примерова', text)
        self.assertNotIn('+7 000', text)
        self.assertIsNone(json.loads(raw)['summary'])  # сводка скрыта, пока организатор не подтвердил аудит
        self.call(f'/api/trips/{trip_id}/share', {'action': 'revoke'})
        self.assertEqual(self.request(f'/api/share/{token}')[0], 404)
        self.assertEqual(self.request('/api/share/' + 'x' * 24)[0], 404)

    def test_status_notice_and_delete(self):
        trip_id = self.new_trip()
        self.assertEqual(self.call(f'/api/trips/{trip_id}/status', {'status': 'active'})[1]['status'], 'active')
        self.assertEqual(self.call(f'/api/trips/{trip_id}/status', {'status': 'flying'})[0], 400)
        notice = self.call(f'/api/trips/{trip_id}/notice')[1]
        self.assertIn('Дана Примерова', notice['text'])
        self.assertIn('TAU ничего не отправляет', notice['channels'])
        self.assertEqual(self.call(f'/api/trips/{trip_id}/delete', {})[0], 200)
        self.assertEqual(self.call(f'/api/trips/{trip_id}')[0], 404)


if __name__ == '__main__':
    unittest.main()
