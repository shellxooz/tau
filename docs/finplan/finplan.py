"""Финансовый план GoTAU на 24 месяца (декабрь 2026 — ноябрь 2028).

Все допущения собраны в ASSUMPTIONS вверху файла: поменяйте число и запустите
    py docs/finplan/finplan.py
Скрипт пересчитает помесячную таблицу (finplan.csv) и итоги (печатает в консоль).
Цифры — гипотезы команды, а не факты: пользователей и выручки у GoTAU пока нет.
"""
import csv
import math
from pathlib import Path

USD = 445  # ₸ за доллар: официальный курс Нацбанка около 444 ₸ на 14.11.2026

ASSUMPTIONS = {
    # --- выручка ---
    'pro_price': 4990,            # ₸ в месяц: тариф Pro для гида или клуба (гипотеза, проверить в интервью)
    'pro_start_month': 7,         # платный тариф после бесплатного пилота с гидами
    'pro_new_per_month_y1': 5,    # новых платящих в месяц в первый год после запуска
    'pro_new_per_month_y2': 8,    # во второй год
    'pro_churn': 0.05,            # доля платящих, уходящих каждый месяц
    'partner_start_month': 13,    # комиссия с трансфера и проката — со второго года
    'partner_revenue_per_100_trips': 15000,  # ₸ комиссии на каждые 100 проверенных походов
    # --- использование ---
    'audits_m1': 50,              # проверок готовности в месяц на старте пилота
    'audits_growth': 0.18,        # рост числа проверок в месяц
    'audits_cap': 4000,           # потолок для расчёта на горизонте 24 месяцев
    'ai_cost_usd_per_audit': 0.08,  # Claude Opus 5.5: ~6k токенов на входе, ~2.5k на выходе по $4/$20 за 1M
    # --- команда ---
    'mobile_dev_salary': 400000,  # ₸ в месяц: подрядчик-мобильный разработчик (ориентир hh.kz, опыт 3–6 лет)
    'mobile_dev_months': (3, 9),  # месяцы работы подрядчика включительно
    'founder_stipend': 150000,    # ₸ в месяц каждому из трёх основателей, частичная занятость
    'founder_stipend_from': 13,   # первый год основатели работают без оплаты
    'founders': 3,
    # --- сервисы, ₸ в месяц ---
    'hosting': 25 * USD,          # сервер, домен, резервные копии, HTTPS
    'weather_api': 29 * USD,      # Open-Meteo Standard для коммерческого использования
    'maps_api': 25 * USD,         # коммерческий тариф карт (MapTiler Flex, цена по стороннему источнику)
    'paid_services_from': 3,      # до запуска пилота хватает бесплатных тарифов
    'marketing': 200000,          # ₸ в месяц с запуска пилота: контент, встречи с клубами, реклама
    'marketing_from': 4,
    # --- разовые расходы, ₸ ---
    'one_off': {
        1: [('Регистрация ИП/ТОО, бухгалтер на старте', 150000), ('Консультация юриста: персональные данные, оферта', 250000)],
        2: [('Проверка правил безопасности сертифицированным гидом (20 ч)', 300000)],
        8: [('Аккаунты Apple Developer и Google Play', (99 + 25) * USD)],
        20: [('Продление Apple Developer', 99 * USD)],
    },
    'accountant': 40000,          # ₸ в месяц, бухгалтерское сопровождение
    'tax_rate': 0.04,             # упрощённая декларация (ставка по новому НК — сверить с КГД)
    'reserve_share': 0.15,        # резерв к сумме привлечения
}
MONTHS = 24
START = (2026, 12)


def month_name(i):
    y, m = START[0], START[1] + i - 1
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f'{m:02d}.{y}'


def build(a=ASSUMPTIONS):
    rows, pro, cash = [], 0.0, 0.0
    for i in range(1, MONTHS + 1):
        audits = min(a['audits_cap'], round(a['audits_m1'] * (1 + a['audits_growth']) ** (i - 1)))
        if i >= a['pro_start_month']:
            pro = pro * (1 - a['pro_churn']) + (a['pro_new_per_month_y1'] if i <= 12 else a['pro_new_per_month_y2'])
        pro_rev = round(pro) * a['pro_price']
        partner = audits / 100 * a['partner_revenue_per_100_trips'] if i >= a['partner_start_month'] else 0
        revenue = pro_rev + partner
        lo, hi = a['mobile_dev_months']
        team = (a['mobile_dev_salary'] if lo <= i <= hi else 0) + (a['founder_stipend'] * a['founders'] if i >= a['founder_stipend_from'] else 0)
        services = (a['hosting'] + a['weather_api'] + a['maps_api'] if i >= a['paid_services_from'] else 0) + audits * a['ai_cost_usd_per_audit'] * USD
        marketing = a['marketing'] if i >= a['marketing_from'] else 0
        one_off = sum(v for _, v in a['one_off'].get(i, []))
        tax = revenue * a['tax_rate']
        costs = team + services + marketing + one_off + a['accountant'] + tax
        cash += revenue - costs
        rows.append({'month': i, 'period': month_name(i), 'audits': audits, 'pro_accounts': round(pro), 'revenue': round(revenue),
                     'team': round(team), 'services_ai': round(services), 'marketing': round(marketing), 'one_off': round(one_off),
                     'accountant': a['accountant'], 'tax': round(tax), 'costs': round(costs), 'net': round(revenue - costs), 'cumulative': round(cash)})
    need = -min(r['cumulative'] for r in rows)
    funding = math.ceil(need * (1 + a['reserve_share']) / USD / 1000) * 1000
    return rows, need, funding


def main():
    rows, need, funding = build()
    out = Path(__file__).with_name('finplan.csv')
    with out.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=';')
        writer.writeheader()
        writer.writerows(rows)
    for year in (1, 2):
        part = rows[(year - 1) * 12: year * 12]
        print(f'Год {year}: выручка {sum(r["revenue"] for r in part):,} ₸, расходы {sum(r["costs"] for r in part):,} ₸, итог {sum(r["net"] for r in part):,} ₸'.replace(',', ' '))
        for key in ('team', 'services_ai', 'marketing', 'one_off', 'accountant', 'tax'):
            print(f'   {key}: {sum(r[key] for r in part):,}'.replace(',', ' '))
    last = rows[-1]
    print(f'Месяц 24: платящих {last["pro_accounts"]}, проверок {last["audits"]}, выручка {last["revenue"]:,} ₸, расходы {last["costs"]:,} ₸'.replace(',', ' '))
    first_positive = next((r['period'] for r in rows if r['net'] > 0), 'не достигается за 24 месяца')
    print(f'Первый месяц с плюсом: {first_positive}')
    print(f'Наибольший накопленный минус: {need:,} ₸ = ${need / USD:,.0f}'.replace(',', ' '))
    print(f'Сумма привлечения с резервом {ASSUMPTIONS["reserve_share"]:.0%}: ${funding:,}'.replace(',', ' '))
    for q in range(8):
        part = rows[q * 3:(q + 1) * 3]
        print(f'Q{q + 1} {part[0]["period"]}–{part[-1]["period"]}: выручка {sum(r["revenue"] for r in part):>10,} расходы {sum(r["costs"] for r in part):>10,} накоплено {part[-1]["cumulative"]:>11,}'.replace(',', ' '))


if __name__ == '__main__':
    main()
