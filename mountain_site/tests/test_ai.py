"""Проверка ИИ-слоя без сети: модель подменяется, проверяются валидация и объединение с правилами."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'eval'))

import app
import tau_ai
import tau_rules
from scenarios import SCENARIOS, M, W


def analysis_for(scenario_id):
    sc = next(s for s in SCENARIOS if s['id'] == scenario_id)
    return tau_rules.analyze(app.ROUTE_BY_ID[sc['route']], {'start_time': sc['start'], 'return_time': sc['ret']}, sc['members'], sc['weather']), sc['weather']


def risk(code, severity, evidence, text='Пояснение без чисел.', affected=('Участник 2',)):
    return {'code': code, 'severity': severity, 'title': 'Заголовок ИИ', 'explanation': text, 'evidence': list(evidence), 'affected': list(affected), 'recommendation': 'Сделать так.'}


def fake(risks, summary='Группа идёт к озеру и вернётся вечером.'):
    return lambda analysis: ({'risks': risks, 'checklists': [{'participant': 'Участник 2', 'items': [{'item': 'Термос', 'reason': 'холодно'}]}, {'participant': 'Чужой', 'items': []}],
                              'summary_for_contacts': summary, 'transport_note': 'Двоим хватит легкового автомобиля.'}, {'input_tokens': 100, 'output_tokens': 50, 'model': 'test-model'})


class RulesTests(unittest.TestCase):
    def test_all_scenarios_match_labels(self):
        order = tau_rules.SEVERITY
        for sc in SCENARIOS:
            analysis = tau_rules.analyze(app.ROUTE_BY_ID[sc['route']], {'start_time': sc['start'], 'return_time': sc['ret']}, sc['members'], sc['weather'])
            found = {f['code']: f['severity'] for f in analysis['flags']}
            for code, severity in sc['must'].items():
                self.assertGreaterEqual(order.get(found.get(code), -1), order[severity], f'{sc["id"]}: нет {code}')
            for code in sc['must_not']:
                self.assertNotIn(code, found, f'{sc["id"]}: лишний {code}')

    def test_payload_for_model_has_no_names(self):
        analysis = tau_rules.analyze(app.ROUTE_BY_ID['bao'], {'start_time': '08:00', 'return_time': '18:00'}, [dict(M(), name='Секретное Имя')], W())
        self.assertNotIn('Секретное', json.dumps(analysis['facts'], ensure_ascii=False) + json.dumps(analysis['flags'], ensure_ascii=False))

    def test_transport(self):
        self.assertEqual(tau_rules.transport([M()] * 3)['vehicle'], 'Легковой автомобиль или такси')
        self.assertEqual(tau_rules.transport([M(bulky='ski')] * 4)['vehicle'], 'Минивэн')
        self.assertEqual(tau_rules.transport([M()] * 12)['vehicle'], 'Микроавтобус')


class AiLayerTests(unittest.TestCase):
    def test_number_check(self):
        facts = {'weather.top.gust_max_ms': 14, 'weather.top.feels_min_c': -10, 'weather.available': True}
        self.assertEqual(tau_ai.unsupported_numbers('Порывы до 14 м/с и −10 °C, идти 5 минут.', facts), [])
        self.assertEqual(len(tau_ai.unsupported_numbers('Порывы до 25 м/с, выпадет 30 см снега.', facts)), 2)
        self.assertEqual(len(tau_ai.unsupported_numbers('Порывы до 30 метров в секунду, мороз до 25 градусов, снег 40 сантиметров.', facts)), 3)

    def test_numbers_in_recommendation_and_checklist_are_checked(self):
        analysis, weather = analysis_for('s02')
        bad = dict(risk('OTHER', 'warning', ['weather.top.gust_max_ms']), recommendation='Повернуть назад при порывах выше 33 м/с.')
        call = lambda a: ({'risks': [bad], 'checklists': [{'participant': 'Участник 2', 'items': [{'item': 'Спальник', 'reason': 'ночью будет −47 °C'}, {'item': 'Термос', 'reason': 'холодно'}]}],
                           'summary_for_contacts': 'Группа идёт к озеру.', 'transport_note': ''}, {'input_tokens': 1, 'output_tokens': 1, 'model': 'test-model'})
        audit = tau_ai.build_audit(analysis, weather, model_call=call)
        self.assertEqual(audit['validation']['dropped_numbers'], 1)
        items = ' '.join(i['item'] for c in audit['checklists'] for i in c['items'])
        self.assertIn('Термос', items)
        self.assertNotIn('Спальник', items)

    def test_ai_cannot_remove_or_downgrade_rule_flags(self):
        analysis, weather = analysis_for('s02')
        audit = tau_ai.build_audit(analysis, weather, model_call=fake([risk('COLD', 'info', ['weather.top.feels_min_c'])]))
        by_code = {r['code']: r for r in audit['recommendations']}
        self.assertEqual(audit['mode'], 'ai')
        self.assertEqual(by_code['COLD']['severity'], 'critical')
        self.assertEqual(by_code['COLD']['source'], 'ai+rules')
        self.assertEqual({f['code'] for f in analysis['flags']}, set(by_code))
        self.assertEqual(audit['validation']['added_from_rules'], len(analysis['flags']) - 1)
        self.assertEqual(audit['recommendations'][0]['severity'], 'critical')

    def test_hallucinations_are_dropped(self):
        analysis, weather = analysis_for('s02')
        risks = [risk('OTHER', 'critical', ['avalanche.risk'], 'Лавинная опасность высокая.'),
                 risk('OTHER', 'warning', ['weather.top.gust_max_ms'], 'Ожидаются порывы до 31 м/с.'),
                 risk('OTHER', 'critical', ['p2.experience', 'trip.est_finish_time'], 'Новичок устанет к концу дня, а финиш близко к закату.')]
        audit = tau_ai.build_audit(analysis, weather, model_call=fake(risks, summary='Наверху будет −40 °C.'))
        self.assertEqual(audit['validation']['dropped_no_evidence'], 1)
        self.assertEqual(audit['validation']['dropped_numbers'], 1)
        self.assertTrue(audit['validation']['summary_replaced'])
        own = [r for r in audit['recommendations'] if r['source'] == 'ai']
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]['severity'], 'warning')  # находка только ИИ не бывает критической
        self.assertNotIn('−40', audit['summary'])

    def test_checklists_keep_rule_items_and_ignore_unknown_people(self):
        analysis, weather = analysis_for('s02')
        audit = tau_ai.build_audit(analysis, weather, model_call=fake([]))
        people = [c['participant'] for c in audit['checklists']]
        self.assertNotIn('Чужой', people)
        second = next(c for c in audit['checklists'] if c['participant'] == 'Участник 2')
        items = ' '.join(i['item'] for i in second['items'])
        self.assertIn('Термос', items)
        self.assertIn('Тёплый слой', items)

    def test_model_failure_falls_back_to_rules(self):
        analysis, weather = analysis_for('s02')

        def broken(_):
            raise RuntimeError('нет сети')
        audit = tau_ai.build_audit(analysis, weather, model_call=broken)
        self.assertEqual(audit['mode'], 'rules')
        self.assertTrue(audit['ai_error'])
        self.assertEqual(len(audit['recommendations']), len(analysis['flags']))

    def test_no_key_means_rules_mode(self):
        analysis, weather = analysis_for('s01')
        with mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': '', 'ANTHROPIC_AUTH_TOKEN': '', 'OPENAI_API_KEY': '', 'TAU_AI_PROVIDER': ''}):
            audit = tau_ai.build_audit(analysis, weather)
        self.assertEqual(audit['mode'], 'rules')
        self.assertIn('ключ', audit['ai_error'])

    def test_provider_choice(self):
        env = {'ANTHROPIC_API_KEY': '', 'ANTHROPIC_AUTH_TOKEN': '', 'OPENAI_API_KEY': '', 'TAU_AI_PROVIDER': ''}
        with mock.patch.dict('os.environ', dict(env, OPENAI_API_KEY='test')):
            self.assertEqual(tau_ai.provider(), 'openai')
            self.assertEqual(tau_ai.current_model(), tau_ai.OPENAI_MODEL)
        with mock.patch.dict('os.environ', dict(env, OPENAI_API_KEY='test', ANTHROPIC_API_KEY='test')):
            self.assertEqual(tau_ai.provider(), 'claude')
        with mock.patch.dict('os.environ', dict(env, ANTHROPIC_API_KEY='test', TAU_AI_PROVIDER='openai')):
            self.assertEqual(tau_ai.provider(), 'openai')

    def test_openai_schema_is_strict_compatible(self):
        """Строгий режим OpenAI требует: все поля в required и additionalProperties=false у каждого объекта."""
        def walk(node):
            if node.get('type') == 'object':
                self.assertFalse(node['additionalProperties'])
                self.assertEqual(set(node['required']), set(node['properties']))
                for child in node['properties'].values():
                    walk(child)
            if node.get('type') == 'array':
                walk(node['items'])
        walk(tau_ai.SCHEMA)


if __name__ == '__main__':
    unittest.main()
