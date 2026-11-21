"""Тестовый набор сценариев для оценки аудитора.

Каждый сценарий: маршрут, время, группа, синтетический прогноз и разметка:
  must     — риски, которые обязаны быть найдены (код -> минимальная серьёзность);
  must_not — риски, которых быть не должно (ложная тревога).
ВАЖНО: разметку составили разработчики по правилам горной безопасности. Чтобы метрики
были независимыми, её должен перепроверить практикующий гид или инструктор.
"""
FULL = ['warm_layer', 'shell', 'boots', 'headlamp', 'traction', 'first_aid', 'water', 'power', 'helmet']


def W(feels=12, tmin=14, tmax=20, gust=5, prob=10, rain=0.0, snow=0.0, sunset='20:30'):
    point = {'elevation_m': 0, 'temp_min_c': tmin, 'temp_max_c': tmax, 'feels_min_c': feels, 'wind_max_ms': max(gust - 4, 0), 'gust_max_ms': gust,
             'precip_prob_max_pct': prob, 'precip_sum_mm': rain, 'snowfall_sum_cm': snow}
    return {'available': True, 'source': 'synthetic', 'date': '2026-01-01', 'fetched_at': '-', 'window': '07:00–19:00', 'top': dict(point), 'start': dict(point), 'sunrise': '06:00', 'sunset': sunset}


def M(experience='expert', age='adult', gear=None, without=(), bulky='none'):
    return {'name': 'x', 'experience': experience, 'age_group': age, 'gear': [g for g in (FULL if gear is None else gear) if g not in without], 'bulky': bulky}


NO_WEATHER = {'available': False, 'reason': 'синтетический сценарий без прогноза'}
SCENARIOS = [
    {'id': 's01', 'note': 'Летний Кок-Жайляу, опытная пара, всё взяли', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '16:00', 'members': [M(), M()], 'weather': W(),
     'must': {}, 'must_not': ['COLD', 'WIND', 'PRECIP', 'ICE', 'DAYLIGHT', 'NO_LEADER', 'SOLO', 'NO_FIRST_AID']},
    {'id': 's02', 'note': 'БАО в мороз, новичок без тёплого слоя', 'route': 'bao', 'start': '08:00', 'ret': '18:30', 'members': [M(), M('novice', gear=['boots', 'water'])], 'weather': W(feels=-10, tmin=-6, tmax=1, sunset='17:25'),
     'must': {'COLD': 'critical', 'ICE': 'warning', 'EFFORT': 'warning'}, 'must_not': ['WIND', 'PRECIP']},
    {'id': 's03', 'note': 'Пик Фурманова, штормовые порывы', 'route': 'furmanov', 'start': '07:00', 'ret': '17:00', 'members': [M(), M()], 'weather': W(gust=22),
     'must': {'WIND': 'critical'}, 'must_not': ['COLD', 'NO_LEADER']},
    {'id': 's04', 'note': 'Пик Фурманова, одни новички, хорошая погода', 'route': 'furmanov', 'start': '07:00', 'ret': '19:00', 'members': [M('novice'), M('novice'), M('novice')], 'weather': W(),
     'must': {'NO_LEADER': 'warning', 'ALTITUDE': 'warning', 'EFFORT': 'warning'}, 'must_not': ['WIND', 'PRECIP']},
    {'id': 's05', 'note': 'Холодный дождь, один без влагозащиты', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '16:00', 'members': [M(), M('some', without=['shell'])], 'weather': W(feels=6, tmin=3, tmax=8, prob=80, rain=6.0),
     'must': {'PRECIP': 'critical'}, 'must_not': ['WIND']},
    {'id': 's06', 'note': 'Тёплый дождь, один без влагозащиты', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '16:00', 'members': [M(), M('some', without=['shell'])], 'weather': W(feels=13, tmin=14, tmax=19, prob=75, rain=5.0),
     'must': {'PRECIP': 'warning'}, 'must_not': ['COLD', 'ICE']},
    {'id': 's07', 'note': 'БАО, поздний выход в ноябре', 'route': 'bao', 'start': '13:00', 'ret': '21:00', 'members': [M(), M()], 'weather': W(feels=6, tmin=7, tmax=10, sunset='17:30'),
     'must': {'DAYLIGHT': 'critical'}, 'must_not': ['NO_LEADER']},
    {'id': 's08', 'note': 'Одиночный выход опытного', 'route': 'butakovka', 'start': '09:00', 'ret': '15:00', 'members': [M()], 'weather': W(),
     'must': {'SOLO': 'warning'}, 'must_not': ['NO_LEADER', 'COLD']},
    {'id': 's09', 'note': 'Велосипед без шлема', 'route': 'bike-foothills', 'start': '09:00', 'ret': '15:00', 'members': [M(), M('some', without=['helmet'])], 'weather': W(),
     'must': {'NO_HELMET': 'warning'}, 'must_not': ['NO_BOOTS', 'ICE']},
    {'id': 's10', 'note': 'Катание в сильный мороз, тёплая одежда есть, шлема нет', 'route': 'ski-day', 'start': '10:00', 'ret': '16:00', 'members': [M(without=['helmet']), M()], 'weather': W(feels=-18, tmin=-12, tmax=-7, sunset='17:30'),
     'must': {'COLD': 'warning', 'NO_HELMET': 'warning'}, 'must_not': ['ICE', 'NO_BOOTS']},
    {'id': 's11', 'note': 'Прогноза нет', 'route': 'bao', 'start': '08:00', 'ret': '18:00', 'members': [M(), M()], 'weather': NO_WEATHER,
     'must': {'NO_WEATHER': 'warning'}, 'must_not': ['COLD', 'WIND', 'PRECIP', 'ICE', 'DAYLIGHT']},
    {'id': 's12', 'note': 'Ребёнок на трёхтысячнике', 'route': 'furmanov', 'start': '07:00', 'ret': '19:00', 'members': [M(), M('some', 'child')], 'weather': W(),
     'must': {'VULNERABLE': 'warning', 'ALTITUDE': 'warning'}, 'must_not': ['NO_LEADER']},
    {'id': 's13', 'note': 'Пожилой участник на лёгком маршруте', 'route': 'butakovka', 'start': '09:00', 'ret': '15:00', 'members': [M(), M('some', 'senior')], 'weather': W(),
     'must': {}, 'must_not': ['VULNERABLE', 'ALTITUDE', 'EFFORT']},
    {'id': 's14', 'note': 'В группе нет аптечки', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '16:00', 'members': [M(without=['first_aid']), M(without=['first_aid'])], 'weather': W(),
     'must': {'NO_FIRST_AID': 'warning'}, 'must_not': ['NO_NAV']},
    {'id': 's15', 'note': 'Нет павербанка и офлайн-карты на длинном маршруте', 'route': 'bao', 'start': '07:00', 'ret': '17:00', 'members': [M(without=['power']), M(without=['power'])], 'weather': W(),
     'must': {'NO_NAV': 'warning'}, 'must_not': ['NO_FIRST_AID']},
    {'id': 's16', 'note': 'Контрольное время раньше расчётного финиша', 'route': 'bao', 'start': '08:00', 'ret': '12:00', 'members': [M(), M()], 'weather': W(),
     'must': {'RETURN_TIME': 'warning'}, 'must_not': ['DAYLIGHT']},
    {'id': 's17', 'note': 'Контрольное время не задано', 'route': 'kok-zhailau', 'start': '08:00', 'ret': None, 'members': [M(), M()], 'weather': W(),
     'must': {'RETURN_TIME': 'warning'}, 'must_not': ['COLD']},
    {'id': 's18', 'note': 'Снег на Кок-Жайляу, без ледоступов', 'route': 'kok-zhailau', 'start': '09:00', 'ret': '16:00', 'members': [M(without=['traction']), M(without=['traction'])], 'weather': W(feels=-4, tmin=-3, tmax=2, snow=2.0, sunset='17:30'),
     'must': {'ICE': 'warning'}, 'must_not': ['COLD', 'PRECIP']},
    {'id': 's19', 'note': 'Мороз на низком маршруте, без ледоступов', 'route': 'butakovka', 'start': '10:00', 'ret': '15:00', 'members': [M(without=['traction']), M()], 'weather': W(feels=-6, tmin=-3, tmax=1, sunset='17:30'),
     'must': {'ICE': 'warning'}, 'must_not': ['ALTITUDE']},
    {'id': 's20', 'note': 'Ветер 14 м/с, один без ветрозащиты', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '16:00', 'members': [M(), M('some', without=['shell'])], 'weather': W(gust=14),
     'must': {'WIND': 'warning'}, 'must_not': ['PRECIP']},
    {'id': 's21', 'note': 'Ветер 14 м/с, все с ветрозащитой', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '16:00', 'members': [M(), M('some')], 'weather': W(gust=14),
     'must': {}, 'must_not': ['WIND']},
    {'id': 's22', 'note': 'Новичок в кроссовках', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '17:00', 'members': [M(), M('novice', without=['boots'])], 'weather': W(),
     'must': {'NO_BOOTS': 'warning'}, 'must_not': ['NO_LEADER']},
    {'id': 's23', 'note': 'Прохладно, один без тёплого слоя', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '16:00', 'members': [M(), M('some', without=['warm_layer'])], 'weather': W(feels=3, tmin=5, tmax=11),
     'must': {'COLD': 'warning'}, 'must_not': ['ICE']},
    {'id': 's24', 'note': 'Прохладно, все одеты', 'route': 'kok-zhailau', 'start': '08:00', 'ret': '16:00', 'members': [M(), M('some')], 'weather': W(feels=3, tmin=5, tmax=11),
     'must': {}, 'must_not': ['COLD', 'ICE']},
    {'id': 's25', 'note': 'Длинный маршрут без воды', 'route': 'bao', 'start': '07:00', 'ret': '17:00', 'members': [M(without=['water']), M()], 'weather': W(),
     'must': {'NO_WATER': 'warning'}, 'must_not': ['NO_FIRST_AID']},
    {'id': 's26', 'note': 'Финиш за полчаса до заката', 'route': 'kok-zhailau', 'start': '12:30', 'ret': '18:30', 'members': [M(), M()], 'weather': W(feels=8, tmin=9, tmax=13, sunset='17:30'),
     'must': {'DAYLIGHT': 'warning'}, 'must_not': ['COLD']},
    {'id': 's27', 'note': 'Худший случай: новички без снаряжения, шторм и мороз', 'route': 'bao', 'start': '11:00', 'ret': '19:00', 'members': [M('novice', gear=['water']), M('novice', gear=[]), M('novice', 'teen', gear=['water'])], 'weather': W(feels=-12, tmin=-7, tmax=-1, gust=21, prob=70, rain=4.0, snow=4.0, sunset='17:25'),
     'must': {'COLD': 'critical', 'WIND': 'critical', 'PRECIP': 'critical', 'DAYLIGHT': 'critical', 'NO_LEADER': 'warning', 'ICE': 'warning', 'NO_FIRST_AID': 'warning'}, 'must_not': []},
    {'id': 's28', 'note': 'Подростки с опытным взрослым на лёгком маршруте', 'route': 'butakovka', 'start': '09:00', 'ret': '15:00', 'members': [M(), M('some', 'teen'), M('some', 'teen')], 'weather': W(),
     'must': {}, 'must_not': ['VULNERABLE', 'NO_LEADER', 'SOLO']},
]
