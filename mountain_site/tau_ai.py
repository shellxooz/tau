"""ИИ-слой аудитора GoTAU: вызов Claude (или OpenAI для теста), проверка ответа и объединение с правилами.

Что делает команда сверх готового API:
1. В модель уходят только обезличенные факты (метки «Участник N», без имён и телефонов).
2. Ответ приходит строго по JSON-схеме (structured outputs).
3. validate() сверяет каждый риск с фактами: ссылки на несуществующие данные и числа,
   которых нет в фактах, отбрасываются.
4. merge() гарантирует, что ИИ не может убрать или смягчить флаг движка правил.
5. При любой ошибке ИИ аудит всё равно выдаётся: в режиме «только правила».
"""
import json
import os
import re
from datetime import datetime

import tau_rules

CLAUDE_MODEL = os.environ.get('TAU_AI_MODEL', 'claude-opus-5-5')
OPENAI_MODEL = os.environ.get('TAU_OPENAI_MODEL', 'gpt-5-mini')
EFFORT = os.environ.get('TAU_AI_EFFORT', 'medium')
FALLBACK_BETA = 'server-side-fallback-2026-07-01'
CODES = list(tau_rules.RULE_TITLES) + ['OTHER']

SYSTEM = """Ты — аудитор готовности горного похода в сервисе GoTAU (Казахстан). Организатор собрал «Паспорт похода», и ты помогаешь ему увидеть риски до выхода.

Как устроена работа. Ты получаешь JSON с тремя частями: facts (все известные данные о маршруте, группе и прогнозе), fact_labels (что означает каждый ключ) и rule_flags (риски, которые уже нашёл детерминированный движок правил). Участники обезличены: у них есть только метки вида «Участник 1». Твой ответ автоматически проверяет код, а затем каждую рекомендацию принимает или отклоняет человек-организатор.

Что нужно сделать:
1. Для каждого флага из rule_flags напиши риск с тем же code: объясни простым языком, что именно может пойти не так у этих конкретных людей на этом маршруте в эту погоду, и дай одно конкретное действие. Не понижай severity флага.
2. Ищи сочетания факторов, которые по отдельности выглядят терпимо, а вместе опасны (например, новичок без фонаря, финиш близко к закату и ветер). Для таких находок используй code "OTHER" и severity не выше "warning".
3. Составь личный чек-лист для каждого участника и общий для группы (participant "Группа"): только те вещи, необходимость которых следует из фактов, с причиной.
4. Напиши summary_for_contacts: до 90 слов для близких, которые остаются в городе. Спокойно и по делу: куда идёт группа, когда вернётся, какая погода, на что обратили внимание. Без имён.
5. В transport_note одной фразой объясни выбор транспорта из facts.

Жёсткие ограничения, и почему они важны:
- Используй только данные из facts. Погода, состояние троп, лавинная обстановка и закрытия маршрутов, которых нет в facts, тебе неизвестны: не описывай их. Люди будут принимать решения о выходе в горы по этому тексту, выдуманная деталь может стоить здоровья.
- В поле evidence перечисляй только ключи из facts, на которые опирается риск. Риск без существующих ключей будет отброшен.
- Не приводи чисел с единицами измерения (°C, м/с, мм, см, %, м, км), которых нет в facts: проверка отбросит такой риск целиком. Общие пороги и нормы формулируй словами.
- Не решай за людей, идти или нет. Ты описываешь риски и действия, решение принимает организатор.
- Если weather.available равно false, не рассуждай о погоде вообще, кроме того, что прогноза нет.
- Ключи terrain.* — грубая оценка крутизны по модели рельефа с шагом около 90 метров. Крутизна склона не равна лавинной опасности: не утверждай, что лавина возможна или невозможна, а советуй узнать лавинную обстановку у ДЧС или спасателей. Если terrain.* нет в facts, трека у маршрута нет: не описывай рельеф.
- Пиши по-русски, коротко, без канцелярита. Одно-два предложения в explanation, одно в recommendation."""

SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['risks', 'checklists', 'summary_for_contacts', 'transport_note'],
    'properties': {
        'risks': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['code', 'severity', 'title', 'explanation', 'evidence', 'affected', 'recommendation'],
            'properties': {
                'code': {'type': 'string', 'enum': CODES},
                'severity': {'type': 'string', 'enum': ['info', 'warning', 'critical']},
                'title': {'type': 'string'}, 'explanation': {'type': 'string'},
                'evidence': {'type': 'array', 'items': {'type': 'string'}},
                'affected': {'type': 'array', 'items': {'type': 'string'}},
                'recommendation': {'type': 'string'},
            }}},
        'checklists': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['participant', 'items'],
            'properties': {'participant': {'type': 'string'}, 'items': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['item', 'reason'],
                'properties': {'item': {'type': 'string'}, 'reason': {'type': 'string'}}}}}}},
        'summary_for_contacts': {'type': 'string'},
        'transport_note': {'type': 'string'},
    },
}


def provider():
    """Какой сервис ИИ использовать: TAU_AI_PROVIDER=claude|openai, иначе по заданному ключу (Claude в приоритете)."""
    chosen = os.environ.get('TAU_AI_PROVIDER', '').strip().lower()
    if chosen in ('claude', 'openai'):
        return chosen
    if os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN'):
        return 'claude'
    if os.environ.get('OPENAI_API_KEY'):
        return 'openai'
    return 'claude'


def current_model():
    return OPENAI_MODEL if provider() == 'openai' else CLAUDE_MODEL


MODEL = CLAUDE_MODEL  # для обратной совместимости; фактическая модель — current_model()


def status():
    """Доступен ли ИИ-режим прямо сейчас: (bool, пояснение)."""
    if os.environ.get('TAU_AI_DISABLED') == '1':
        return False, 'ИИ отключён переменной TAU_AI_DISABLED'
    if provider() == 'openai':
        try:
            import openai  # noqa: F401
        except ImportError:
            return False, 'Не установлен пакет openai (pip install openai)'
        if not os.environ.get('OPENAI_API_KEY'):
            return False, 'Не задан ключ OPENAI_API_KEY'
        return True, f'OpenAI ({OPENAI_MODEL})'
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, 'Не установлен пакет anthropic (pip install anthropic)'
    if not (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')):
        return False, 'Не задан ключ ANTHROPIC_API_KEY или OPENAI_API_KEY'
    return True, f'Claude ({CLAUDE_MODEL})'


def build_payload(analysis):
    return json.dumps({
        'facts': analysis['facts'], 'fact_labels': analysis['fact_labels'],
        'rule_flags': [{k: f[k] for k in ('code', 'severity', 'title', 'evidence', 'affected')} for f in analysis['flags']],
        'participants': analysis['participants'],
        'transport': analysis['transport'],
    }, ensure_ascii=False, sort_keys=True)


def call_model(analysis):
    """Один запрос к выбранному сервису ИИ. Возвращает (dict по SCHEMA, usage). Любая неудача — исключение."""
    return call_openai(analysis) if provider() == 'openai' else call_claude(analysis)


def call_openai(analysis):
    """Запрос к OpenAI Responses API со строгой JSON-схемой (structured outputs)."""
    import openai
    request = dict(
        model=OPENAI_MODEL, instructions=SYSTEM, input=build_payload(analysis), max_output_tokens=16000,
        text={'format': {'type': 'json_schema', 'name': 'tau_audit', 'schema': SCHEMA, 'strict': True}},
    )
    client = openai.OpenAI(timeout=120.0, max_retries=1)
    try:
        response = client.responses.create(reasoning={'effort': EFFORT}, **request)
    except openai.BadRequestError as exc:
        if 'reasoning' not in str(exc).lower():
            raise
        response = client.responses.create(**request)  # модель без рассуждений не принимает параметр reasoning
    if response.status != 'completed':
        reason = getattr(response.incomplete_details, 'reason', None) or response.status
        raise RuntimeError(f'Модель не завершила ответ ({reason})')
    for item in response.output:
        for part in getattr(item, 'content', None) or []:
            if getattr(part, 'type', '') == 'refusal':
                raise RuntimeError('Модель отказалась отвечать')
    usage = {'input_tokens': response.usage.input_tokens, 'output_tokens': response.usage.output_tokens, 'model': response.model}
    return json.loads(response.output_text), usage


def call_claude(analysis):
    """Запрос к Claude со строгой JSON-схемой."""
    import anthropic
    request = dict(
        model=CLAUDE_MODEL, max_tokens=16000, system=SYSTEM,
        messages=[{'role': 'user', 'content': build_payload(analysis)}],
        output_config={'effort': EFFORT, 'format': {'type': 'json_schema', 'schema': SCHEMA}},
    )
    client = anthropic.Anthropic(timeout=120.0, max_retries=1)
    try:
        # Серверный fallback: если основная модель отклонит запрос по политике, API повторит его на запасной.
        response = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks='default', **request)
    except (anthropic.BadRequestError, TypeError):
        response = client.messages.create(**request)
    if response.stop_reason in ('refusal', 'max_tokens'):
        raise RuntimeError(f'Модель не завершила ответ ({response.stop_reason})')
    text = next(block.text for block in response.content if block.type == 'text')
    usage = {'input_tokens': response.usage.input_tokens, 'output_tokens': response.usage.output_tokens, 'model': response.model}
    return json.loads(text), usage


def describe_error(exc):
    if provider() == 'openai':
        try:
            import openai
        except ImportError:
            return 'Пакет openai не установлен'
        sdk = openai
    else:
        try:
            import anthropic
        except ImportError:
            return 'Пакет anthropic не установлен'
        sdk = anthropic
    return describe_sdk_error(exc, sdk)


def describe_sdk_error(exc, sdk):
    """У обоих SDK одинаковые имена классов ошибок."""
    if isinstance(exc, sdk.AuthenticationError):
        return 'Ключ API не принят'
    if isinstance(exc, sdk.RateLimitError):
        return 'Превышен лимит запросов или закончились кредиты API'
    if isinstance(exc, sdk.APIConnectionError):
        return 'Нет связи с сервисом ИИ'
    if isinstance(exc, sdk.APIStatusError):
        return f'Сервис ИИ вернул ошибку {exc.status_code}'
    return f'Ответ ИИ не обработан ({type(exc).__name__})'


NUMBER = re.compile(r'(?<![\w.,])[-−–]?\s?(\d+(?:[.,]\d+)?)\s*(м/с|мм|см|км|°C|°|%|м\b|метр\w*|сантиметр\w*|миллиметр\w*|километр\w*|градус\w*|процент\w*)')


def unsupported_numbers(text, facts):
    """Числа с единицами измерения, которых нет среди фактов. Пустой список — текст чист."""
    known = set()
    for value in facts.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            known.add(abs(float(value)))
    missing = []
    for match in NUMBER.finditer(text):
        number = float(match.group(1).replace(',', '.'))
        if not any(abs(number - k) <= 0.5 for k in known):
            missing.append(match.group(0).strip())
    return missing


def validate(ai, analysis):
    """Проверка ответа ИИ по фактам. Возвращает (очищенные риски, чек-листы, сводка, отчёт)."""
    facts, people = analysis['facts'], set(analysis['participants']) | {tau_rules.GROUP}
    report = {'received': len(ai.get('risks', [])), 'dropped_no_evidence': 0, 'dropped_numbers': 0, 'summary_replaced': False, 'notes': []}
    risks = []
    for risk in ai.get('risks', []):
        evidence = [key for key in risk['evidence'] if key in facts]
        if not evidence:
            report['dropped_no_evidence'] += 1
            report['notes'].append(f'«{risk["title"]}»: нет ссылок на существующие данные')
            continue
        bad = unsupported_numbers(' '.join((risk['title'], risk['explanation'], risk['recommendation'])), facts)
        if bad:
            report['dropped_numbers'] += 1
            report['notes'].append(f'«{risk["title"]}»: числа не из данных ({", ".join(bad)})')
            continue
        affected = [p for p in risk['affected'] if p in people] or [tau_rules.GROUP]
        risks.append({**risk, 'evidence': evidence, 'affected': affected})
    summary = (ai.get('summary_for_contacts') or '').strip()
    if not summary or unsupported_numbers(summary, facts) or len(summary) > 1200:
        summary = analysis['summary']
        report['summary_replaced'] = True
    checklists = []
    for entry in ai.get('checklists', []):
        if entry['participant'] in people:
            checklists.append({'participant': entry['participant'], 'items': [i for i in entry['items'] if i['item'].strip() and not unsupported_numbers(i['item'] + ' ' + i['reason'], facts)][:12]})
    return risks, checklists, summary, report


def merge(ai_risks, ai_checklists, analysis, report):
    """Объединение: флаги правил обязательны, ИИ их поясняет и может добавить свои наблюдения."""
    order, flags = tau_rules.SEVERITY, {f['code']: f for f in analysis['flags']}
    result, covered = [], set()
    for risk in ai_risks:
        flag = flags.get(risk['code'])
        if flag and risk['code'] not in covered:
            covered.add(risk['code'])
            severity = max(risk['severity'], flag['severity'], key=order.get)
            evidence = list(dict.fromkeys(flag['evidence'] + risk['evidence']))
            affected = flag['affected'] if flag['affected'] != [tau_rules.GROUP] else risk['affected']
            result.append({**risk, 'title': flag['title'], 'severity': severity, 'evidence': evidence, 'affected': affected, 'source': 'ai+rules'})
        elif not flag:
            severity = min(risk['severity'], 'warning', key=order.get)  # находка только ИИ не может быть «критической» без правила
            result.append({**risk, 'code': 'OTHER', 'severity': severity, 'source': 'ai'})
    added = 0
    for code, flag in flags.items():
        if code not in covered:
            added += 1
            result.append(rule_risk(flag))
    report['added_from_rules'] = added
    by_person = {c['participant']: c for c in ai_checklists}
    checklists = []
    for base in analysis['checklists']:
        entry = by_person.get(base['participant'], {'participant': base['participant'], 'items': []})
        items = [{'item': i['item'], 'reason': i.get('reason', '')} for i in entry['items']]
        extra = []
        for needed in base['items']:  # код снаряжения нужен интерфейсу, чтобы отметить вещь как взятую
            key = needed['item'].lower().split(' (')[0]
            same = next((i for i in items if key in i['item'].lower()), None)
            if same:
                same['code'] = needed['code']
            else:
                extra.append(needed)
        checklists.append({'participant': base['participant'], 'items': items + extra})
    return result, checklists


def rule_risk(flag):
    return {'code': flag['code'], 'severity': flag['severity'], 'title': flag['title'], 'explanation': flag['detail'],
            'evidence': flag['evidence'], 'affected': flag['affected'], 'recommendation': flag['action'], 'source': 'rules'}


def build_audit(analysis, weather, model_call=None):
    """Полный аудит. model_call можно подменить в тестах; по умолчанию вызывается выбранный сервис ИИ."""
    enabled, why = status()
    mode, error, usage = 'rules', None, None
    report = {'received': 0, 'dropped_no_evidence': 0, 'dropped_numbers': 0, 'summary_replaced': False, 'added_from_rules': 0, 'notes': []}
    risks, checklists, summary = [rule_risk(f) for f in analysis['flags']], analysis['checklists'], analysis['summary']
    transport = dict(analysis['transport'], note='Рассчитано по числу людей и негабаритному грузу.')
    if model_call or enabled:
        try:
            ai, usage = (model_call or call_model)(analysis)
            ai_risks, ai_checklists, summary, report = validate(ai, analysis)
            risks, checklists = merge(ai_risks, ai_checklists, analysis, report)
            note = (ai.get('transport_note') or '').strip()
            if note and not unsupported_numbers(note, analysis['facts']):
                transport['note'] = note
            mode = 'ai'
        except Exception as exc:
            error = describe_error(exc)
    else:
        error = why
    order = tau_rules.SEVERITY
    risks.sort(key=lambda r: -order[r['severity']])
    for number, risk in enumerate(risks, 1):
        risk['id'] = f'r{number}'
        risk['decision'] = None
        risk['evidence'] = [{'key': k, 'label': analysis['fact_labels'][k], 'value': analysis['facts'][k]} for k in risk['evidence']]
    worst = max((order[r['severity']] for r in risks), default=0)
    attention = 'high' if worst == 2 else 'medium' if sum(r['severity'] == 'warning' for r in risks) >= 2 else 'low'
    return {'mode': mode, 'model': (usage or {}).get('model') or (current_model() if mode == 'ai' else None), 'ai_error': error, 'usage': usage,
            'generated_at': datetime.now().strftime('%d.%m.%Y %H:%M'), 'weather': weather, 'recommendations': risks, 'checklists': checklists,
            'summary': summary, 'transport': transport, 'attention': attention, 'validation': report, 'estimate': analysis['estimate']}
