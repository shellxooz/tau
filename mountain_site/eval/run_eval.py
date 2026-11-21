"""Оценка аудитора на тестовом наборе. Запуск из папки mountain_site:

    py eval/run_eval.py          — только движок правил (бесплатно, без сети)
    py eval/run_eval.py --ai     — с вызовом ИИ: Claude (ANTHROPIC_API_KEY) или OpenAI (OPENAI_API_KEY), тратит кредиты API

Результат печатается и сохраняется в eval/results.md.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app  # noqa: E402
import tau_ai  # noqa: E402
import tau_rules  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402

PRICES = {'claude': (4.0, 20.0),   # $ за 1 млн токенов, claude-opus-5-5
          'openai': (0.25, 2.0)}   # gpt-5-mini; для другой модели OpenAI сверьте цену на странице тарифов


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ai', action='store_true', help='вызывать модель (платно)')
    args = parser.parse_args()
    if args.ai and not tau_ai.status()[0]:
        sys.exit('ИИ недоступен: ' + tau_ai.status()[1])

    order = tau_rules.SEVERITY
    must_total = must_hit = not_total = false_alarm = 0
    ai = {'runs': 0, 'ok': 0, 'flags': 0, 'explained': 0, 'received': 0, 'dropped_evidence': 0, 'dropped_numbers': 0, 'summary_replaced': 0, 'own_findings': 0, 'in': 0, 'out': 0, 'seconds': 0.0}
    rows, problems = [], []
    for sc in SCENARIOS:
        route = app.ROUTE_BY_ID[sc['route']]
        analysis = tau_rules.analyze(route, {'start_time': sc['start'], 'return_time': sc['ret']}, sc['members'], sc['weather'])
        if args.ai:
            started = time.time()
            audit = tau_ai.build_audit(analysis, sc['weather'])
            ai['seconds'] += time.time() - started
            ai['runs'] += 1
            if audit['mode'] == 'ai':
                v = audit['validation']
                ai['ok'] += 1
                ai['flags'] += len(analysis['flags'])
                ai['explained'] += len(analysis['flags']) - v['added_from_rules']
                ai['received'] += v['received']
                ai['dropped_evidence'] += v['dropped_no_evidence']
                ai['dropped_numbers'] += v['dropped_numbers']
                ai['summary_replaced'] += v['summary_replaced']
                ai['own_findings'] += sum(r['source'] == 'ai' for r in audit['recommendations'])
                ai['in'] += audit['usage']['input_tokens']
                ai['out'] += audit['usage']['output_tokens']
            else:
                problems.append(f'{sc["id"]}: ИИ не ответил ({audit["ai_error"]})')
            found = {r['code']: r['severity'] for r in audit['recommendations'] if r['code'] != 'OTHER'}
        else:
            found = {f['code']: f['severity'] for f in analysis['flags']}
        missed = [c for c, sev in sc['must'].items() if order.get(found.get(c), -1) < order[sev]]
        extra = [c for c in sc['must_not'] if c in found]
        must_total += len(sc['must'])
        must_hit += len(sc['must']) - len(missed)
        not_total += len(sc['must_not'])
        false_alarm += len(extra)
        rows.append(f'| {sc["id"]} | {sc["note"]} | {", ".join(sorted(found)) or "—"} | {", ".join(missed) or "—"} | {", ".join(extra) or "—"} |')
        problems += [f'{sc["id"]}: пропущен {c}' for c in missed] + [f'{sc["id"]}: ложная тревога {c}' for c in extra]

    pct = lambda a, b: f'{100 * a / b:.0f} %' if b else 'н/д'
    lines = ['# Результаты оценки аудитора TAU', '', f'Режим: {"ИИ + правила (" + tau_ai.current_model() + ")" if args.ai else "только движок правил"}. Сценариев: {len(SCENARIOS)}.', '',
             '| Метрика | Значение |', '|---|---|',
             f'| Полнота: найдено обязательных рисков | {must_hit} из {must_total} ({pct(must_hit, must_total)}) |',
             f'| Ложные тревоги по запрещённым кодам | {false_alarm} из {not_total} ({pct(false_alarm, not_total)}) |']
    if args.ai:
        price_in, price_out = PRICES[tau_ai.provider()]
        cost = ai['in'] / 1e6 * price_in + ai['out'] / 1e6 * price_out
        lines += [f'| Успешных ответов ИИ по схеме | {ai["ok"]} из {ai["runs"]} ({pct(ai["ok"], ai["runs"])}) |',
                  f'| Флаги правил, которые ИИ сам объяснил | {ai["explained"]} из {ai["flags"]} ({pct(ai["explained"], ai["flags"])}) |',
                  f'| Риски ИИ, отброшенные проверкой (нет данных) | {ai["dropped_evidence"]} из {ai["received"]} ({pct(ai["dropped_evidence"], ai["received"])}) |',
                  f'| Риски ИИ, отброшенные проверкой (числа не из данных) | {ai["dropped_numbers"]} из {ai["received"]} ({pct(ai["dropped_numbers"], ai["received"])}) |',
                  f'| Сводки, заменённые шаблоном | {ai["summary_replaced"]} из {ai["ok"]} |',
                  f'| Собственные наблюдения ИИ (сверх правил) | {ai["own_findings"]} |',
                  f'| Среднее время ответа | {ai["seconds"] / max(ai["runs"], 1):.1f} с |',
                  f'| Токены: вход / выход | {ai["in"]} / {ai["out"]} |',
                  f'| Стоимость прогона, оценка | ${cost:.2f} (≈ ${cost / max(ai["ok"], 1):.3f} за аудит) |']
    lines += ['', 'Разметку сценариев составили разработчики. Для независимой оценки её должен перепроверить практикующий гид.', '',
              '| Сценарий | Описание | Найденные коды | Пропущено | Ложные тревоги |', '|---|---|---|---|---|'] + rows
    if problems:
        lines += ['', '## Расхождения', ''] + [f'- {p}' for p in problems]
    text = '\n'.join(lines) + '\n'
    (Path(__file__).resolve().parent / ('results-ai.md' if args.ai else 'results.md')).write_text(text, encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
