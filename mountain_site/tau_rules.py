"""Движок правил безопасности TAU. Детерминированный код команды, работает без ИИ и без сети.

Вход: маршрут, поход, участники, прогноз. Выход: факты (единственный источник цифр для ИИ),
флаги рисков, чек-листы, расчёт времени и транспорта. ИИ не может отменить флаг этого модуля.
"""
import math

GEAR = {
    'warm_layer': 'Тёплый слой (пуховка или флис)',
    'shell': 'Ветро- и влагозащитная куртка',
    'boots': 'Треккинговая обувь',
    'headlamp': 'Налобный фонарь',
    'traction': 'Ледоступы или кошки',
    'first_aid': 'Аптечка',
    'water': 'Вода от 1,5 л',
    'power': 'Павербанк и офлайн-карта',
    'helmet': 'Шлем',
}
GROUP_GEAR = ('first_aid', 'power')
EXPERIENCE = {'novice': 'новичок', 'some': 'есть опыт', 'expert': 'опытный'}
AGE = {'child': 'до 14 лет', 'teen': '14–17 лет', 'adult': '18–59 лет', 'senior': '60 лет и старше'}
BULKY = {'none': 'нет', 'ski': 'лыжи или сноуборд', 'bike': 'велосипед', 'pack': 'большой рюкзак'}
SEVERITY = {'info': 0, 'warning': 1, 'critical': 2}
GROUP = 'Группа'

RULE_TITLES = {
    'NO_WEATHER': 'Нет прогноза погоды',
    'COLD': 'Холод на маршруте',
    'WIND': 'Сильный ветер',
    'PRECIP': 'Осадки',
    'ICE': 'Снег и лёд на тропе',
    'ALTITUDE': 'Высота',
    'EFFORT': 'Большая нагрузка',
    'DAYLIGHT': 'Нехватка светового дня',
    'RETURN_TIME': 'Контрольное время возвращения',
    'SOLO': 'Одиночный выход',
    'NO_LEADER': 'В группе нет опытного участника',
    'VULNERABLE': 'Дети или пожилые на сложном участке',
    'NO_FIRST_AID': 'В группе нет аптечки',
    'NO_NAV': 'Нет навигации и запаса заряда',
    'NO_WATER': 'Мало воды',
    'NO_HELMET': 'Нет шлема',
    'NO_BOOTS': 'Неподходящая обувь',
    'AVALANCHE_TERRAIN': 'Лавиноопасная крутизна склонов',
    'CLIFFS': 'Очень крутые участки',
    'STEEP_TRAIL': 'Крутой подъём на тропе',
}
WINTER_MONTHS = {11, 12, 1, 2, 3, 4}


def hm_to_min(text):
    hours, minutes = text.split(':')
    return int(hours) * 60 + int(minutes)


def min_to_hm(minutes):
    minutes = int(round(minutes))
    return f'{(minutes // 60) % 24:02d}:{minutes % 60:02d}'


def label(index):
    return f'Участник {index + 1}'


def estimate_duration_h(route, members):
    """Оценка времени в пути: правило Нейсмита с поправкой на состав группы и привалы."""
    if route['activity'] == 'hiking':
        base = route['distance'] / 4 + route['ascent'] / 400
    elif route['activity'] == 'cycling':
        base = route['distance'] / 12 + route['ascent'] / 500
    else:
        base = route['hours_max']
    experience = {m['experience'] for m in members}
    factor = 1.3 if 'novice' in experience else 1.15 if 'some' in experience else 1.0
    if any(m['age_group'] in ('child', 'senior') for m in members):
        factor += 0.1
    return round(base * factor * 1.1 * 2) / 2


def transport(members):
    people = len(members)
    bulky = sum(1 for m in members if m.get('bulky', 'none') != 'none')
    seats = people + math.ceil(bulky / 2)
    if seats <= 3:
        vehicle = 'Легковой автомобиль или такси'
    elif seats <= 6:
        vehicle = 'Минивэн'
    elif seats <= 18:
        vehicle = 'Микроавтобус'
    else:
        vehicle = 'Автобус или два микроавтобуса'
    return {'vehicle': vehicle, 'people': people, 'bulky_items': bulky, 'seats_needed': seats}


def analyze(route, trip, members, weather):
    facts, labels_of = {}, {}

    def fact(key, value, title):
        facts[key] = value
        labels_of[key] = title

    fact('route.activity', route['activityLabel'], 'Вид активности')
    fact('route.level', route['level'], 'Сложность маршрута')
    fact('route.distance_km', route['distance'], 'Длина маршрута, км')
    fact('route.ascent_m', route['ascent'], 'Набор высоты, м')
    fact('route.start_elevation_m', route['start_elev'], 'Высота старта, м')
    fact('route.max_elevation_m', route['max_elev'], 'Максимальная высота, м')
    duration = estimate_duration_h(route, members)
    start_min = hm_to_min(trip['start_time'])
    finish_min = start_min + duration * 60
    fact('trip.group_size', len(members), 'Человек в группе')
    fact('trip.start_time', trip['start_time'], 'Время выхода')
    fact('trip.est_duration_h', duration, 'Расчётное время в пути, ч')
    fact('trip.est_finish_time', min_to_hm(finish_min), 'Расчётное время финиша')
    fact('trip.control_return_time', trip.get('return_time') or 'не задано', 'Контрольное время возвращения')

    available = bool(weather and weather.get('available'))
    fact('weather.available', available, 'Прогноз получен')
    top = weather['top'] if available else {}
    if available:
        for point, title in (('top', 'на верхней точке'), ('start', 'на старте')):
            data = weather[point]
            for name, text in (('temp_min_c', 'Мин. температура'), ('temp_max_c', 'Макс. температура'), ('feels_min_c', 'Мин. ощущаемая температура'),
                               ('wind_max_ms', 'Макс. ветер, м/с'), ('gust_max_ms', 'Макс. порывы, м/с'), ('precip_prob_max_pct', 'Макс. вероятность осадков, %'),
                               ('precip_sum_mm', 'Сумма осадков, мм'), ('snowfall_sum_cm', 'Снег, см')):
                if data.get(name) is not None:
                    fact(f'weather.{point}.{name}', data[name], f'{text} {title}')
        fact('weather.sunrise', weather['sunrise'], 'Восход')
        fact('weather.sunset', weather['sunset'], 'Закат')

    terrain = route.get('terrain')
    if terrain:
        fact('terrain.max_trail_grade_pct', terrain['max_trail_grade_pct'], 'Самый крутой участок тропы (на 300 м), %')
        fact('terrain.max_slope_deg', terrain['max_slope_deg'], 'Наибольшая крутизна склона у тропы, °')
        fact('terrain.km_slope_30_45', terrain['km_slope_30_45'], 'Путь по склонам крутизной 30–45°, км')
        fact('terrain.km_slope_45_plus', terrain['km_slope_45_plus'], 'Путь по склонам круче 45°, км')
        fact('terrain.source', terrain['source'], 'Источник рельефа')
    if trip.get('date'):
        fact('trip.month', int(trip['date'][5:7]), 'Месяц похода')

    names = [label(i) for i in range(len(members))]
    for i, member in enumerate(members):
        fact(f'p{i + 1}.experience', EXPERIENCE[member['experience']], f'{names[i]}: опыт')
        fact(f'p{i + 1}.age_group', AGE[member['age_group']], f'{names[i]}: возраст')
        fact(f'p{i + 1}.gear', [GEAR[g] for g in member['gear']] or ['ничего не отмечено'], f'{names[i]}: снаряжение')
        fact(f'p{i + 1}.bulky', BULKY[member.get('bulky', 'none')], f'{names[i]}: негабаритный груз')

    flags = []

    def flag(code, severity, detail, evidence, affected, action):
        flags.append({'code': code, 'severity': severity, 'title': RULE_TITLES[code], 'detail': detail,
                      'evidence': [k for k in evidence if k in facts], 'affected': affected or [GROUP], 'action': action})

    def without(code):
        return [names[i] for i, m in enumerate(members) if code not in m['gear']]

    def gear_keys(people):
        return [f'p{names.index(p) + 1}.gear' for p in people if p in names]

    needed = {}  # код снаряжения -> причина, почему оно нужно в этом походе
    hiking = route['activity'] == 'hiking'
    feels, gust = top.get('feels_min_c'), top.get('gust_max_ms')
    prob, rain, snow, temp_min = top.get('precip_prob_max_pct'), top.get('precip_sum_mm'), top.get('snowfall_sum_cm'), top.get('temp_min_c')

    if not available:
        reason = (weather or {}).get('reason', 'нет данных')
        flag('NO_WEATHER', 'warning', f'Прогноз не получен: {reason}. Погодные риски не оценивались.', ['weather.available'], None,
             'Проверьте прогноз для высоты маршрута самостоятельно перед выходом и повторите аудит ближе к дате.')
        if route['max_elev'] >= 2000:
            needed['warm_layer'] = 'прогноза нет, а на высоте погода меняется быстро'
            needed['shell'] = 'прогноза нет, а на высоте погода меняется быстро'

    if feels is not None and feels <= 5:
        needed['warm_layer'] = f'ощущаемая температура на верхней точке до {feels} °C'
        cold = without('warm_layer')
        if cold:
            flag('COLD', 'critical' if feels <= -5 else 'warning',
                 f'Ощущаемая температура на высоте {route["max_elev"]} м опускается до {feels} °C, а тёплого слоя нет.',
                 ['weather.top.feels_min_c', 'route.max_elevation_m'] + gear_keys(cold), cold, 'Взять пуховку или плотный флис, шапку и перчатки.')
        elif feels <= -15:
            flag('COLD', 'warning', f'Сильный мороз: ощущаемая температура до {feels} °C. Даже с тёплой одеждой остановки должны быть короткими.',
                 ['weather.top.feels_min_c'], None, 'Сократить привалы, взять термос и запасные перчатки.')

    if gust is not None and gust >= 8:
        needed['shell'] = f'порывы ветра на верхней точке до {gust} м/с'
    if gust is not None and gust >= 20:
        flag('WIND', 'critical', f'Порывы ветра на верхней точке до {gust} м/с: на открытых участках и гребнях трудно удерживать равновесие.',
             ['weather.top.gust_max_ms'], None, 'Перенести выход или выбрать маршрут ниже границы леса.')
    elif gust is not None and gust >= 12:
        windy = without('shell')
        if windy:
            flag('WIND', 'warning', f'Порывы ветра до {gust} м/с, а ветрозащитной куртки нет: тело быстро теряет тепло.',
                 ['weather.top.gust_max_ms'] + gear_keys(windy), windy, 'Взять ветрозащитную куртку с капюшоном.')

    wet = (prob is not None and prob >= 60) or (rain is not None and rain >= 3)
    if (prob is not None and prob >= 30) or wet:
        needed['shell'] = needed.get('shell') or f'вероятность осадков до {prob} %'
    if wet:
        soaked = without('shell')
        if soaked:
            cold_wet = temp_min is not None and temp_min <= 5
            flag('PRECIP', 'critical' if cold_wet else 'warning',
                 f'Вероятность осадков до {prob} %, сумма {rain} мм. Без влагозащиты одежда промокнет' + (f', а при {temp_min} °C это прямой риск переохлаждения.' if cold_wet else '.'),
                 ['weather.top.precip_prob_max_pct', 'weather.top.precip_sum_mm', 'weather.top.temp_min_c'] + gear_keys(soaked), soaked,
                 'Взять мембранную куртку или дождевик и сухой комплект одежды.')

    icy = hiking and ((snow is not None and snow > 0) or (temp_min is not None and temp_min <= 0))
    if icy:
        needed['traction'] = f'на высоте {route["max_elev"]} м температура до {temp_min} °C, возможны снег и лёд'
        slipping = without('traction')
        if slipping:
            flag('ICE', 'warning', f'На верхней точке температура до {temp_min} °C' + (f', ожидается {snow} см снега' if snow else '') + ': тропа может быть скользкой, а ледоступов нет.',
                 ['weather.top.temp_min_c', 'weather.top.snowfall_sum_cm', 'route.max_elevation_m'] + gear_keys(slipping), slipping, 'Взять ледоступы и треккинговые палки.')

    if route['max_elev'] >= 2500:
        needed.setdefault('warm_layer', f'высота до {route["max_elev"]} м: наверху заметно холоднее, чем в городе')
        needed.setdefault('shell', f'высота до {route["max_elev"]} м: ветер и погода меняются быстро')
        sensitive = [names[i] for i, m in enumerate(members) if m['experience'] == 'novice' or m['age_group'] in ('child', 'senior')]
        if sensitive:
            high = route['max_elev'] >= 3000
            flag('ALTITUDE', 'warning' if high else 'info',
                 f'Маршрут поднимается до {route["max_elev"]} м. У людей без акклиматизации возможны головная боль, тошнота и слабость.',
                 ['route.max_elevation_m'] + [f'p{names.index(p) + 1}.experience' for p in sensitive], sensitive,
                 'Идти медленнее обычного, пить воду, при ухудшении самочувствия спускаться всей группой.')

    if duration >= 6 or route['ascent'] >= 1000:
        beginners = [names[i] for i, m in enumerate(members) if m['experience'] == 'novice']
        if beginners:
            flag('EFFORT', 'warning', f'Расчётное время в пути {duration:g} ч при наборе {route["ascent"]} м: для новичка это тяжёлая нагрузка.',
                 ['trip.est_duration_h', 'route.ascent_m'] + [f'p{names.index(p) + 1}.experience' for p in beginners], beginners,
                 'Назначить точку разворота и время, после которого группа идёт назад независимо от того, дошли или нет.')

    if duration >= 5:
        needed['headlamp'] = f'расчётное время в пути {duration:g} ч, запас на случай задержки'
    if available:
        sunset_min = hm_to_min(weather['sunset'])
        if finish_min > sunset_min - 60:
            needed['headlamp'] = f'расчётный финиш {min_to_hm(finish_min)}, закат в {weather["sunset"]}'
            dark = finish_min > sunset_min
            no_light = without('headlamp')
            flag('DAYLIGHT', 'critical' if dark else 'warning',
                 f'Расчётный финиш в {min_to_hm(finish_min)}, закат в {weather["sunset"]}: ' + ('часть пути придётся идти в темноте.' if dark else 'запас светлого времени меньше часа.')
                 + (f' Без фонаря: {", ".join(no_light)}.' if no_light else ''),
                 ['trip.est_finish_time', 'weather.sunset', 'trip.start_time'] + gear_keys(no_light), None,
                 'Выйти раньше или сократить маршрут; каждому взять налобный фонарь.')

    control = trip.get('return_time')
    if not control:
        flag('RETURN_TIME', 'warning', 'Контрольное время возвращения не задано: близкие не узнают, когда начинать беспокоиться.', ['trip.control_return_time'], None,
             'Задать контрольное время с запасом и сообщить его близким.')
    elif hm_to_min(control) < finish_min:
        flag('RETURN_TIME', 'warning', f'Контрольное время {control} раньше расчётного финиша {min_to_hm(finish_min)}: вероятна ложная тревога у близких.',
             ['trip.control_return_time', 'trip.est_finish_time'], None, 'Сдвинуть контрольное время на час-полтора позже расчётного финиша.')

    if len(members) == 1:
        flag('SOLO', 'warning', 'В походе один человек: при травме некому помочь и вызвать спасателей.', ['trip.group_size'], None,
             'Найти напарника или точно сообщить близким маршрут и контрольное время.')
    elif all(m['experience'] == 'novice' for m in members):
        flag('NO_LEADER', 'warning', 'Все участники новички: некому принять решение о развороте и оказать помощь.', [f'p{i + 1}.experience' for i in range(len(members))], None,
             'Позвать опытного участника или гида либо выбрать более простой маршрут.')

    hard = route['ascent'] >= 700 or route['max_elev'] >= 2500 or duration >= 6
    fragile = [names[i] for i, m in enumerate(members) if m['age_group'] in ('child', 'senior')]
    if fragile and hard:
        flag('VULNERABLE', 'warning', f'В группе есть дети или пожилые, а маршрут требует {duration:g} ч и набора {route["ascent"]} м.',
             ['trip.est_duration_h', 'route.ascent_m'] + [f'p{names.index(p) + 1}.age_group' for p in fragile], fragile,
             'Заложить больше привалов и заранее выбрать точку, с которой можно вернуться.')

    if terrain:
        steep_km = terrain['km_slope_30_45'] + terrain['km_slope_45_plus']
        snowy = (snow is not None and snow > 0) or (trip.get('date') and int(trip['date'][5:7]) in WINTER_MONTHS)
        if steep_km >= 0.3 and snowy:
            flag('AVALANCHE_TERRAIN', 'warning',
                 f'Около {steep_km:g} км пути проходит по склонам крутизной 30 градусов и больше, а в это время года на них может лежать снег. '
                 'TAU считает только крутизну по модели рельефа и не знает лавинной обстановки.',
                 ['terrain.km_slope_30_45', 'terrain.km_slope_45_plus', 'trip.month', 'weather.top.snowfall_sum_cm'], None,
                 'Перед выходом узнать лавинную обстановку в ДЧС или у спасателей; без лавинного снаряжения и навыков не выходить на снежные склоны.')
        sensitive = [names[i] for i, m in enumerate(members) if m['experience'] == 'novice' or m['age_group'] in ('child', 'senior')]
        if terrain['km_slope_45_plus'] > 0:
            flag('CLIFFS', 'warning' if sensitive else 'info',
                 f'На треке есть участки у склонов круче 45 градусов ({terrain["km_slope_45_plus"]:g} км): возможны скалы, осыпи или обрывы.',
                 ['terrain.km_slope_45_plus', 'terrain.max_slope_deg'] + [f'p{names.index(p) + 1}.experience' for p in sensitive], sensitive or None,
                 'Заранее узнать у тех, кто ходил, где эти места; на них идти медленно и страховать новичков и детей.')
        if terrain['max_trail_grade_pct'] >= 30 and sensitive:
            flag('STEEP_TRAIL', 'info',
                 f'Самый крутой участок тропы — около {terrain["max_trail_grade_pct"]} % уклона: на спуске там легко поскользнуться.',
                 ['terrain.max_trail_grade_pct'] + [f'p{names.index(p) + 1}.experience' for p in sensitive], sensitive,
                 'Взять треккинговые палки и спускаться на этом участке медленно.')

    needed['first_aid'] = 'на группу нужна хотя бы одна аптечка'
    needed['power'] = 'связь и карта не должны зависеть от одного разряженного телефона'
    needed['water'] = f'расчётное время в пути {duration:g} ч'
    all_gear_keys = [f'p{i + 1}.gear' for i in range(len(members))]
    if not any('first_aid' in m['gear'] for m in members):
        flag('NO_FIRST_AID', 'warning', 'Ни у кого в группе не отмечена аптечка.', all_gear_keys, None, 'Взять одну общую аптечку: бинт, пластырь, обезболивающее, спасательное одеяло.')
    if not any('power' in m['gear'] for m in members):
        flag('NO_NAV', 'warning' if duration >= 4 else 'info', 'Ни у кого нет павербанка и офлайн-карты: при разряженном телефоне группа останется без навигации и связи.', all_gear_keys, None,
             'Скачать офлайн-карту района и взять павербанк.')
    thirsty = without('water')
    if thirsty and duration >= 3:
        flag('NO_WATER', 'warning' if duration >= 5 else 'info', f'Расчётное время в пути {duration:g} ч, а запас воды отмечен не у всех.', ['trip.est_duration_h'] + gear_keys(thirsty), thirsty, 'Взять не менее 1,5 л воды на человека.')
    if route['activity'] in ('cycling', 'skiing'):
        needed['helmet'] = f'вид активности: {route["activityLabel"].lower()}'
        bare = without('helmet')
        if bare:
            flag('NO_HELMET', 'warning', 'Для этой активности нужен шлем, а он отмечен не у всех.', ['route.activity'] + gear_keys(bare), bare, 'Взять или арендовать шлем.')
    if hiking:
        needed['boots'] = f'пеший маршрут с набором {route["ascent"]} м'
        barefoot = without('boots')
        if barefoot and route['ascent'] >= 500:
            flag('NO_BOOTS', 'warning', f'Набор высоты {route["ascent"]} м по тропе, а треккинговой обуви нет: выше риск подвернуть ногу и поскользнуться.',
                 ['route.ascent_m'] + gear_keys(barefoot), barefoot, 'Надеть обувь с протектором и фиксацией голеностопа.')

    checklists = []
    for i, member in enumerate(members):
        items = [{'item': GEAR[code], 'reason': reason, 'code': code} for code, reason in needed.items() if code not in GROUP_GEAR and code not in member['gear']]
        checklists.append({'participant': names[i], 'items': items})
    group_items = [{'item': GEAR[code], 'reason': needed[code], 'code': code} for code in GROUP_GEAR if not any(code in m['gear'] for m in members)]
    if group_items:
        checklists.append({'participant': GROUP, 'items': group_items})

    worst = max((SEVERITY[f['severity']] for f in flags), default=0)
    warnings = sum(1 for f in flags if f['severity'] == 'warning')
    attention = 'high' if worst == 2 else 'medium' if warnings >= 2 else 'low'

    parts = [f'Группа из {len(members)} чел. идёт по маршруту «{route["name"]}». Выход в {trip["start_time"]}, расчётный финиш около {min_to_hm(finish_min)}'
             + (f', контрольное время возвращения {control}.' if control else '. Контрольное время не задано.')]
    if available:
        parts.append(f'Прогноз на высоте {route["max_elev"]} м: от {top.get("temp_min_c")} до {top.get("temp_max_c")} °C, порывы ветра до {gust} м/с, вероятность осадков до {prob} %.')
    else:
        parts.append('Прогноз погоды получить не удалось.')
    serious = [f['title'].lower() for f in flags if f['severity'] != 'info'][:4]
    parts.append('На что обратили внимание: ' + ', '.join(serious) + '.' if serious else 'Существенных замечаний по подготовке нет.')

    return {'facts': facts, 'fact_labels': labels_of, 'flags': flags, 'needed': needed, 'checklists': checklists, 'participants': names,
            'attention': attention, 'summary': ' '.join(parts), 'transport': transport(members),
            'estimate': {'duration_h': duration, 'finish_time': min_to_hm(finish_min)}}
