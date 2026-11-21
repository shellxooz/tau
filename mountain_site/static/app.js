'use strict';
/* GoTAU — интерфейс паспорта похода. Экраны переключаются по адресу после «#/». */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const view = $('#view');
const S = { routes: [], ai: { enabled: false, text: '' }, trip: null, tab: 'risks', filter: 'all', source: 'all', query: '', draft: null, step: 1, tracks: {}, maps: [] };
const SOURCES = { all: 'Все источники', osm: 'OpenStreetMap', tau: 'Каталог GoTAU', user: 'От пользователей' };
const SOURCE_BADGE = { osm: ['info', 'OpenStreetMap · трек'], tau: ['plain', 'Каталог GoTAU · примерно'], user: ['ok', 'От пользователя · проверен'] };

const GEAR = { warm_layer: 'Тёплый слой', shell: 'Куртка от ветра и дождя', boots: 'Треккинговая обувь', headlamp: 'Налобный фонарь', traction: 'Ледоступы', first_aid: 'Аптечка', water: 'Вода 1,5 л', power: 'Павербанк и офлайн-карта', helmet: 'Шлем' };
const EXPERIENCE = { novice: 'Новичок', some: 'Есть опыт', expert: 'Опытный' };
const AGE = { adult: '18–59 лет', teen: '14–17 лет', child: 'до 14 лет', senior: '60 лет и старше' };
const BULKY = { none: 'Без крупного груза', ski: 'Лыжи или сноуборд', bike: 'Велосипед', pack: 'Большой рюкзак' };
const SEVERITY = { critical: 'Критично', warning: 'Важно', info: 'К сведению' };
const SOURCE = { ai: 'Заметил ИИ', rules: 'Правило GoTAU', 'ai+rules': 'Правило GoTAU, объяснил ИИ' };
const ACTIVITY = { all: 'Все', hiking: 'Пешком', cycling: 'На велосипеде', skiing: 'На лыжах' };
const STATUS_TONE = { planned: 'info', active: 'ok', done: 'plain', cancelled: 'plain' };

const ICONS = {
  right: '<path d="M5 12h14M13 6l6 6-6 6"/>', left: '<path d="M19 12H5M11 6l-6 6 6 6"/>', plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="m5 12.500 4.500 4.500L19 7.500"/>', alert: '<path d="M12 4 2.500 20h19z"/><path d="M12 10v4.500M12 17.200v.300"/>',
  clock: '<circle cx="12" cy="12" r="8.500"/><path d="M12 7.500V12l3 2"/>', wind: '<path d="M3 9h10a2.500 2.500 0 1 0-2.500-2.500M3 13h15a2.500 2.500 0 1 1-2.500 2.500M3 17h7"/>',
  drop: '<path d="M12 3.500s6 6.200 6 10.500a6 6 0 0 1-12 0c0-4.300 6-10.500 6-10.500z"/>', snow: '<path d="M12 3v18M4.200 7.500l15.600 9M19.800 7.500l-15.600 9"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.500V5M12 19v2.500M2.500 12H5M19 12h2.500M5.300 5.300 7 7M17 17l1.700 1.700M18.700 5.300 17 7M7 17l-1.700 1.700"/>',
  users: '<circle cx="9" cy="8.500" r="3.200"/><path d="M3 19.500c0-3.300 2.700-5.500 6-5.500s6 2.200 6 5.500M16 5.500a3.200 3.200 0 0 1 0 6.200M17.500 14.300c2.100.700 3.500 2.500 3.500 5.200"/>',
  share: '<circle cx="6.500" cy="12" r="2.500"/><circle cx="17.500" cy="6" r="2.500"/><circle cx="17.500" cy="18" r="2.500"/><path d="m8.700 10.800 6.600-3.600M8.700 13.200l6.600 3.600"/>',
  edit: '<path d="m4 20 1-4.500L16.500 4 20 7.500 8.500 19z"/>', trash: '<path d="M4.500 7h15M9.500 7V4.500h5V7M6.500 7l1 12.500h9l1-12.500"/>',
  shield: '<path d="M12 3.500 5 6v5.500c0 4.300 2.900 7.500 7 9 4.100-1.500 7-4.700 7-9V6z"/><path d="m9 12 2.200 2.200L15 10.400"/>',
  spark: '<path d="M12 3.500 13.800 10l6.700 2-6.700 2L12 20.500 10.200 14l-6.700-2 6.700-2z"/>',
  copy: '<rect x="8.500" y="8.500" width="11" height="11" rx="2"/><path d="M15.500 8.500V6A1.500 1.500 0 0 0 14 4.500H6A1.500 1.500 0 0 0 4.500 6v8A1.500 1.500 0 0 0 6 15.500h2.500"/>',
  route: '<circle cx="6" cy="18" r="2.500"/><circle cx="18" cy="6" r="2.500"/><path d="M8.500 18H14a3.500 3.500 0 0 0 0-7h-4a3.500 3.500 0 0 1 0-7h5.500"/>',
  thermo: '<path d="M10 13.500v-8a2 2 0 0 1 4 0v8a4 4 0 1 1-4 0z"/>', doc: '<path d="M7 3.500h7l4 4v13H7z"/><path d="M14 3.500v4h4M9.500 12h5M9.500 15.500h5"/>',
  refresh: '<path d="M19.500 12a7.500 7.500 0 1 1-2.200-5.300"/><path d="M19.500 4.500V9H15"/>', car: '<path d="M4 16.500v-4l2-5h12l2 5v4z"/><circle cx="7.500" cy="16.500" r="1.800"/><circle cx="16.500" cy="16.500" r="1.800"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>', pack: '<rect x="6" y="8" width="12" height="12" rx="3"/><path d="M9 8V6a3 3 0 0 1 6 0v2M9 14h6"/>',
};
const icon = (name) => `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;

/* ---------- мелкие помощники ---------- */
const esc = (text) => String(text ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const dmy = (iso) => iso.split('-').reverse().join('.');
const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
const WEEKDAYS = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
function niceDate(iso) { const [y, m, d] = iso.split('-').map(Number); return `${d} ${MONTHS[m - 1]}, ${WEEKDAYS[new Date(y, m - 1, d).getDay()]}`; }
function localDay(shift = 0) { const now = new Date(); now.setDate(now.getDate() + shift); return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10); }
const plural = (n, one, few, many) => { const a = Math.abs(n) % 100, b = a % 10; return a > 10 && a < 20 ? many : b === 1 ? one : b >= 2 && b <= 4 ? few : many; };
const count = (n, one, few, many) => `${n} ${plural(n, one, few, many)}`;
const deg = (v) => v === null || v === undefined ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}°`;
const val = (v, unit) => v === null || v === undefined ? '—' : `${v} ${unit}`;
const minutes = (hm) => { const [h, m] = hm.split(':').map(Number); return h * 60 + m; };
const routeOf = (t) => S.routes.find(r => r.id === t.route_id);
const options = (map, selected) => Object.entries(map).map(([k, v]) => `<option value="${k}" ${k === selected ? 'selected' : ''}>${v}</option>`).join('');
const chip = (tone, text, ic) => `<span class="chip ${tone}">${ic ? icon(ic) : ''}${text}</span>`;

function toast(text) { const el = $('#toast'); el.textContent = text; el.hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => { el.hidden = true; }, 6000); }
async function api(path, payload) {
  let res;
  try { res = await fetch(path, payload === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); }
  catch (error) { throw new Error('Нет связи с сервером GoTAU. Проверьте, что он запущен'); }
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || 'Не удалось выполнить запрос');
  return body;
}
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast('Скопировано'); }
  catch (error) { toast('Не получилось скопировать. Выделите текст и скопируйте вручную.'); }
}

/* ---------- рисунки ---------- */
function ridge(id) {
  let seed = [...id].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const layer = (base, amp, n) => { let d = 'M0 160'; for (let i = 0; i <= n; i++) d += ` L${Math.round(400 * i / n)} ${Math.round(base - amp * (i % 2 ? 0.45 + rnd() * 0.55 : rnd() * 0.3))}`; return d + ' L400 160Z'; };
  return `<svg class="ridge" viewBox="0 0 400 160" preserveAspectRatio="none" aria-hidden="true"><path class="r1" d="${layer(118, 92, 8)}"/><path class="r2" d="${layer(146, 62, 6)}"/></svg>`;
}
const HERO_ART = '<svg class="hero-art" viewBox="0 0 1200 420" preserveAspectRatio="xMidYMax slice" aria-hidden="true"><circle class="h-sun" cx="930" cy="110" r="54"/><path class="h1" d="M0 420V300l170-150 120 110 170-200 150 170 130-110 180 190 120-90 160 130v70z"/><path class="h-snow" d="m460 60-58 68 60-26 34 26 22-34zM740 120l-52 44 54-14 44 30z"/><path class="h2" d="M0 420V350l210-120 150 100 200-150 240 190 190-110 210 120v40z"/><path class="h3" d="M0 420v-40l260-70 240 60 260-90 440 110v30z"/></svg>';

function timeline(w, start, finish, control) {
  const from = 240, span = 1140, x = (m) => Math.max(0, Math.min(320, (m - from) / span * 320));
  const rise = minutes(w.sunrise), set = minutes(w.sunset), s = minutes(start), f = Math.min(minutes(finish) < s ? 1380 : minutes(finish), 1380);
  const band = (cls, a, b, y, h) => b > a ? `<rect class="${cls}" x="${x(a).toFixed(1)}" y="${y}" width="${(x(b) - x(a)).toFixed(1)}" height="${h}" rx="${h / 2}"/>` : '';
  const ticks = [6, 9, 12, 15, 18, 21].map(h => `<text class="tl-tick" x="${x(h * 60).toFixed(1)}" y="50" text-anchor="middle">${h}:00</text>`).join('');
  const mark = control ? `<path class="tl-control" d="M${x(minutes(control)).toFixed(1)} 6v30"/>` : '';
  return `<figure class="tl"><svg viewBox="0 0 320 54" role="img" aria-label="Световой день и время в пути">${band('tl-night', from, from + span, 16, 10)}${band('tl-day', rise, set, 16, 10)}${band('tl-trip', s, Math.min(f, set), 12, 18)}${band('tl-dark', Math.max(s, set), f, 12, 18)}${mark}${ticks}</svg>
  <figcaption><span><i class="sw s-day"></i>Светло: ${w.sunrise}–${w.sunset}</span><span><i class="sw s-trip"></i>В пути: ${start} – около ${finish}</span>${f > set ? '<span><i class="sw s-dark"></i>Часть пути в темноте</span>' : ''}${control ? `<span><i class="sw s-control"></i>Контрольное время: ${control}</span>` : ''}</figcaption></figure>`;
}

/* ---------- карта и профиль ---------- */
function clearMaps() { S.maps.forEach(m => m.remove()); S.maps = []; }
async function trackOf(id) {
  if (!(id in S.tracks)) { try { S.tracks[id] = await api(`/api/routes/${encodeURIComponent(id)}/track`); } catch (error) { S.tracks[id] = null; } }
  return S.tracks[id];
}
function drawMap(box, { line, start, top, approximate }) {
  if (!box) return;
  if (!window.L) { box.innerHTML = '<p class="note pad">Карта не загрузилась. Проверьте подключение к интернету.</p>'; return; }
  const map = L.map(box, { scrollWheelZoom: false, attributionControl: true });
  S.maps.push(map);
  L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17, subdomains: 'abc', attribution: 'Карта © <a href="https://opentopomap.org" target="_blank" rel="noopener">OpenTopoMap</a> (CC-BY-SA), данные © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">участники OpenStreetMap</a>' }).addTo(map);
  map.attributionControl.setPrefix(false);
  const bounds = [];
  (line || []).forEach(seg => { if (seg.length > 1) { L.polyline(seg, { color: '#e0752d', weight: 4, opacity: .9 }).addTo(map); bounds.push(...seg); } });
  if (start) { L.circleMarker(start, { radius: 7, color: '#fff', weight: 2, fillColor: '#17503a', fillOpacity: 1 }).addTo(map).bindTooltip(approximate ? 'Старт (примерно)' : 'Старт'); bounds.push(start); }
  if (top && line) { L.circleMarker(top, { radius: 6, color: '#fff', weight: 2, fillColor: '#a8231b', fillOpacity: 1 }).addTo(map).bindTooltip('Верхняя точка'); bounds.push(top); }
  if (bounds.length > 1) map.fitBounds(bounds, { padding: [24, 24] }); else map.setView(start || [43.15, 77.05], approximate ? 13 : 14);
  setTimeout(() => map.invalidateSize(), 0);
}
function profileChart(profile) {
  if (!profile || profile.length < 2) return '';
  const W = 640, H = 170, P = { l: 44, r: 10, t: 12, b: 26 };
  const km = profile[profile.length - 1][0] || 1, eles = profile.map(p => p[1]), lo = Math.min(...eles), hi = Math.max(...eles), span = Math.max(50, hi - lo);
  const x = d => P.l + d / km * (W - P.l - P.r), y = e => P.t + (1 - (e - lo) / span) * (H - P.t - P.b);
  const pts = profile.map(p => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(' ');
  const ticks = [0, .5, 1].map(t => Math.round(lo + span * t));
  return `<figure class="profile"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Профиль высот: от ${lo} до ${hi} м на ${km.toFixed(1)} км">
    ${ticks.map(e => `<line class="pf-grid" x1="${P.l}" x2="${W - P.r}" y1="${y(e)}" y2="${y(e)}"/><text class="pf-tick" x="${P.l - 6}" y="${y(e) + 3}" text-anchor="end">${e}</text>`).join('')}
    <polygon class="pf-area" points="${P.l},${H - P.b} ${pts} ${x(km)},${H - P.b}"/><polyline class="pf-line" points="${pts}"/>
    <text class="pf-tick" x="${P.l}" y="${H - 8}">0 км</text><text class="pf-tick" x="${W - P.r}" y="${H - 8}" text-anchor="end">${km.toFixed(1)} км</text></svg>
    <figcaption>Профиль высот по модели рельефа, м</figcaption></figure>`;
}
function terrainBlock(t) {
  if (!t) return '';
  return `<div class="tiles terrain"><div><span>Самый крутой участок тропы</span><b>${t.max_trail_grade_pct} %</b></div><div><span>Наибольшая крутизна склона</span><b>${t.max_slope_deg}°</b></div>
    <div><span>По склонам 30–45°</span><b>${t.km_slope_30_45} км</b></div><div><span>По склонам круче 45°</span><b>${t.km_slope_45_plus} км</b></div></div>
    <p class="note">Посчитано по модели рельефа с шагом около 90 м (${esc(t.source)}): короткие обрывы и скальные ступени она сглаживает. Крутизна склона — ещё не лавинная опасность: лавинную обстановку узнавайте в ДЧС или у спасателей.</p>`;
}
async function routeMapBlock(r, holder) {
  const box = $(holder); if (!box) return;
  const track = r.has_track ? await trackOf(r.id) : null;
  if (!$(holder)) return;
  box.innerHTML = `<div class="map" id="${holder.slice(1)}-map"></div>${track ? profileChart(track.profile) + terrainBlock(track.terrain) : '<p class="note">Трека у этого маршрута нет: на карте только примерная точка старта. Не используйте её для навигации.</p>'}`;
  drawMap($(`${holder}-map`), track ? { line: track.line, start: track.stats.start, top: track.stats.top } : { start: [r.lat, r.lon], approximate: true });
}

/* ---------- погода ---------- */
function weatherCards(w) {
  const point = (title, p) => `<div class="wx"><div class="wx-head">${title}<b>${p.elevation_m} м</b></div><div class="wx-temp">${deg(p.temp_min_c)} … ${deg(p.temp_max_c)}</div>
    <ul class="wx-list"><li>${icon('thermo')}Ощущается от <b>${deg(p.feels_min_c)}</b></li><li>${icon('wind')}Порывы до <b>${val(p.gust_max_ms, 'м/с')}</b></li><li>${icon('drop')}Осадки: <b>${val(p.precip_prob_max_pct, '%')}</b>, ${val(p.precip_sum_mm, 'мм')}</li><li>${icon('snow')}Снег: <b>${val(p.snowfall_sum_cm, 'см')}</b></li></ul></div>`;
  return `<div class="wx-grid">${point('Старт', w.start)}${point('Верхняя точка', w.top)}</div><p class="note">Дневные часы ${w.window}. Источник: ${esc(w.source)}, получено ${esc(w.fetched_at)}. Это расчёт модели погоды, а не наблюдение на месте.</p>`;
}
const noWeather = (reason) => `<div class="callout warn">${icon('alert')}<div><b>Прогноз недоступен.</b> ${esc(reason)}. Цифры не подставляются: проверьте погоду сами.</div></div>`;

/* ---------- карточки ---------- */
function routeCard(r) {
  return `<a class="card route" href="#/route/${r.id}"><div class="art ${r.activity}">${ridge(r.id)}<span class="art-tag">${esc(r.activityLabel)}</span><span class="art-top">до ${r.max_elev} м</span></div>
    <div class="route-body"><p class="over">${esc(r.area)}</p><h3>${esc(r.name)}</h3><p class="muted">${esc(r.tag)}</p>
    <div class="stats"><span>${icon('route')}${r.distance} км</span><span>${icon('clock')}${r.hours} ч</span><span>${icon('up')}${r.ascent} м</span></div>
    <div class="chips">${chip('plain', esc(r.level))}${chip(...SOURCE_BADGE[r.source])}</div></div></a>`;
}
function tripVerdict(t) {
  if (!t.audited) return chip('plain', 'Ещё не проверен');
  if (t.stale) return chip('warn', 'Проверка устарела', 'refresh');
  if (t.critical) return chip('crit', count(t.critical, 'критичное замечание', 'критичных замечания', 'критичных замечаний'), 'alert');
  if (t.warning) return chip('warn', count(t.warning, 'важное замечание', 'важных замечания', 'важных замечаний'), 'alert');
  return chip('ok', 'Серьёзных замечаний нет', 'check');
}
function tripNext(t) {
  if (t.status === 'done') return 'Поход завершён';
  if (t.status === 'cancelled') return 'Поход отменён';
  if (t.overdue) return 'Контрольное время прошло: отметьте возвращение';
  if (!t.audited) return 'Дальше: проверить готовность';
  if (t.stale) return 'Дальше: проверить заново';
  if (t.undecided) return `Дальше: разобрать замечания (${t.undecided})`;
  if (!t.confirmed) return 'Дальше: подтвердить паспорт';
  if (!t.shared) return 'Дальше: отправить ссылку близким';
  return t.status === 'active' ? 'Группа на маршруте' : 'Всё готово к выходу';
}
function tripCard(t) {
  const r = routeOf(t);
  return `<a class="card trip" href="#/trip/${t.id}"><div class="trip-main"><div class="chips">${chip(t.overdue ? 'crit' : STATUS_TONE[t.status], t.overdue ? 'Не отметили возвращение' : esc(t.status_label))}${tripVerdict(t)}</div>
    <h3>${esc(t.title)}</h3><p class="muted">${esc(r ? r.name : t.route_id)} · ${niceDate(t.start_date)} · выход в ${t.start_time} · ${count(t.participants, 'человек', 'человека', 'человек')}</p></div>
    <div class="trip-next"><span>${tripNext(t)}</span>${icon('right')}</div></a>`;
}
const empty = (title, text, action = '') => `<div class="empty"><h3>${title}</h3><p>${text}</p>${action}</div>`;

/* ---------- главная ---------- */
async function viewHome() {
  const trips = await api('/api/trips');
  const next = trips.find(t => t.status === 'planned' || t.status === 'active');
  view.innerHTML = `<section class="hero">${HERO_ART}<div class="hero-in"><p class="over light">Алматы · Иле-Алатау</p><h1>Проверьте группу до&nbsp;выхода в&nbsp;горы</h1>
    <p class="lead">GoTAU сверит маршрут, прогноз на высоте и рюкзак каждого участника — и подскажет, кому чего не хватает.</p>
    <div class="row"><a class="btn light" href="#/new">Собрать поход ${icon('right')}</a><a class="btn glass" href="#/routes">Выбрать маршрут</a></div></div></section>
  ${next ? `<section class="block"><div class="block-head"><h2>Ближайший поход</h2><a class="link" href="#/trips">Все походы ${icon('right')}</a></div>${tripCard(next)}</section>` : ''}
  <section class="block"><h2>Как это работает</h2><ol class="how">
    <li><span class="num">1</span><h3>Соберите поход</h3><p>Маршрут, время выхода, кто идёт и что у каждого в рюкзаке. Это занимает пару минут.</p></li>
    <li><span class="num">2</span><h3>Получите проверку</h3><p>Реальный прогноз на высоте и правила безопасности покажут риски для конкретных людей. Решение остаётся за вами.</p></li>
    <li><span class="num">3</span><h3>Оставьте план близким</h3><p>Ссылка с маршрутом и контрольным временем. Если группа не отметит возвращение, близкие увидят, что делать.</p></li></ol></section>
  <section class="block"><div class="block-head"><h2>Погода в горах сегодня</h2><span class="muted">Кок-Жайляу</span></div><div id="home-weather" class="card pad"><p class="loading">Загружаем прогноз…</p></div></section>
  <section class="block"><div class="block-head"><h2>Куда пойти</h2><span class="row"><a class="link" href="#/propose">Предложить свой ${icon('plus')}</a><a class="link" href="#/routes">Все маршруты ${icon('right')}</a></span></div><div class="grid">${[...S.routes.filter(r => r.has_track).slice(0, 2), ...S.routes.filter(r => !r.has_track)].slice(0, 3).map(routeCard).join('')}</div></section>`;
  api('/api/weather?route_id=kok-zhailau').then(w => { const box = $('#home-weather'); if (box) box.innerHTML = w.available ? weatherCards(w) : noWeather(w.reason); })
    .catch(error => { const box = $('#home-weather'); if (box) box.innerHTML = noWeather(error.message); });
}

/* ---------- маршруты ---------- */
function routeGrid() {
  const query = S.query.trim().toLocaleLowerCase('ru');
  const items = S.routes.filter(r => (S.filter === 'all' || S.filter === r.activity) && (S.source === 'all' || S.source === r.source) && `${r.name} ${r.area}`.toLocaleLowerCase('ru').includes(query));
  return items.length ? items.map(routeCard).join('') : empty('Ничего не нашлось', 'Попробуйте другое название или снимите фильтр.');
}
function viewRoutes() {
  const pills = (map, current, act, label) => `<div class="seg-chips" role="group" aria-label="${label}">${Object.entries(map).filter(([k]) => k === 'all' || act !== 'source' || S.routes.some(r => r.source === k)).map(([k, v]) => `<button class="pill ${current === k ? 'on' : ''}" data-act="${act}" data-value="${k}" aria-pressed="${current === k}">${v}</button>`).join('')}</div>`;
  view.innerHTML = `<div class="page-head row-between"><div><h1>Маршруты</h1><p class="muted">${count(S.routes.length, 'маршрут', 'маршрута', 'маршрутов')}. У маршрутов из OpenStreetMap и от пользователей есть трек на карте и разбор рельефа.</p></div><a class="btn outline" href="#/propose">${icon('plus')}Предложить маршрут</a></div>
    <div class="tools">${pills(ACTIVITY, S.filter, 'filter', 'Вид активности')}<input id="q" class="search" type="search" placeholder="Найти по названию" aria-label="Найти маршрут" value="${esc(S.query)}"></div>
    <div class="tools">${pills(SOURCES, S.source, 'source', 'Источник')}</div>
    <div id="route-grid" class="grid">${routeGrid()}</div>
    <p class="note">Маршруты OpenStreetMap: данные © участники OpenStreetMap (лицензия ODbL). На местности GoTAU их не проверял.</p>`;
}
async function loadRouteWeather(id, day) {
  const box = $('#route-weather'); if (!box) return;
  box.innerHTML = '<p class="loading">Загружаем прогноз…</p>';
  try { const w = await api(`/api/weather?route_id=${encodeURIComponent(id)}&date=${encodeURIComponent(day)}`); box.innerHTML = w.available ? weatherCards(w) : noWeather(w.reason); }
  catch (error) { box.innerHTML = noWeather(error.message); }
}
function viewRoute(id) {
  const r = S.routes.find(x => x.id === id);
  if (!r) { view.innerHTML = empty('Маршрут не найден', 'Возможно, ссылка устарела.', '<a class="btn" href="#/routes">К маршрутам</a>'); return; }
  view.innerHTML = `<a class="back" href="#/routes">${icon('left')}Все маршруты</a>
    <section class="route-hero art ${r.activity}">${ridge(r.id)}<div class="route-hero-in"><p class="over light">${esc(r.area)} · ${esc(r.activityLabel)}</p><h1>${esc(r.name)}</h1><p>${esc(r.tag)}</p></div></section>
    <div class="tiles"><div><span>Длина</span><b>${r.distance} км</b></div><div><span>Время</span><b>${r.hours} ч</b></div><div><span>Набор высоты</span><b>${r.ascent} м</b></div><div><span>Верхняя точка</span><b>${r.max_elev} м</b></div><div><span>Сложность</span><b>${esc(r.level)}</b></div></div>
    <p class="lead-dark">${esc(r.description)}${r.source_url ? ` <a class="link" href="${esc(r.source_url)}" target="_blank" rel="noopener">Открыть в OpenStreetMap ${icon('right')}</a>` : ''}</p>
    <section class="block"><h2>Карта${r.has_track ? ' и рельеф' : ''}</h2><div id="route-map" class="card pad"><p class="loading">Загружаем карту…</p></div></section>
    <div class="callout">${icon('alert')}<div>Это не навигатор: офлайн-карты и GPS здесь нет. В горы берите офлайн-карту в телефоне${r.has_track ? ' и трек, сверенный с тем, кто ходил этот маршрут' : ''}.</div></div>
    <section class="block"><div class="block-head"><h2>Прогноз на маршруте</h2><label class="inline">День <input id="wx-date" type="date" value="${localDay()}" min="${localDay()}" max="${localDay(15)}" data-route="${r.id}"></label></div><div id="route-weather" class="card pad"></div></section>
    <div class="cta"><div><h2>Идёте сюда?</h2><p class="muted">Соберите группу, и GoTAU проверит её готовность под прогноз на этот день.</p></div><a class="btn" href="#/new/${r.id}">Собрать поход сюда ${icon('right')}</a></div>`;
  loadRouteWeather(r.id, localDay());
  routeMapBlock(r, '#route-map');
}

/* ---------- предложить маршрут ---------- */
function viewPropose() {
  view.innerHTML = `<a class="back" href="#/routes">${icon('left')}Маршруты</a>
    <div class="page-head"><h1>Предложить маршрут</h1><p class="muted">Загрузите свой трек в формате GPX: его можно выгрузить из часов, Strava, Wikiloc или приложения, в котором вы записывали поход. GoTAU посчитает длину, набор высоты и крутизну, а модератор проверит маршрут перед публикацией.</p></div>
    <form id="propose" class="card pad" novalidate>
      <label class="field">Файл трека (.gpx, до 5 МБ)<input type="file" name="file" accept=".gpx,application/gpx+xml" required></label>
      <label class="field">Название<input name="name" maxlength="80" placeholder="Например: пик Кумбель через Кок-Жайляу" required></label>
      <div class="field"><span class="label">Вид активности</span><div class="seg">${Object.entries({ hiking: 'Пешком', cycling: 'Велосипед', skiing: 'Лыжи' }).map(([k, v], i) => `<label><input type="radio" name="activity" value="${k}" ${i ? '' : 'checked'}><span>${v}</span></label>`).join('')}</div></div>
      <div class="two"><label class="field">Район<input name="area" maxlength="60" placeholder="Например: Иле-Алатау"></label><label class="field"><span>Длина по вашим данным, км <span class="muted">(не обязательно)</span></span><input name="claimed_km" type="number" min="0" step="0.1" inputmode="decimal"></label></div>
      <label class="field">Описание<textarea name="description" rows="5" maxlength="1500" placeholder="Где начало тропы и как туда добраться, есть ли вода, опасные места, когда лучше идти"></textarea></label>
      <label class="field"><span>Как вас подписать <span class="muted">(не обязательно)</span></span><input name="author" maxlength="60" autocomplete="off"></label>
      <label class="consent"><input type="checkbox" name="consent"><span>Трек записан мной или я имею право им поделиться. Разрешаю GoTAU опубликовать маршрут после проверки.</span></label>
      <p class="note">Из файла сохраняются только координаты и высоты. Время записи, имя устройства и другие данные файла не сохраняются.</p>
      <p id="form-error" class="form-error" role="alert"></p>
      <button class="btn" type="submit">${icon('up')}Отправить на проверку</button>
    </form>`;
}
async function submitProposal(form) {
  const f = new FormData(form), file = f.get('file'), button = form.querySelector('[type="submit"]'), error = $('#form-error');
  error.textContent = '';
  if (!file || !file.size) { error.textContent = 'Выберите GPX-файл'; return; }
  if (file.size > 5 * 1024 * 1024) { error.textContent = 'Файл больше 5 МБ'; return; }
  const label = button.innerHTML;
  button.disabled = true; button.textContent = 'Считаем рельеф… до минуты';
  try {
    const result = await api('/api/proposals', { gpx: await file.text(), name: f.get('name'), activity: f.get('activity'), area: f.get('area'), description: f.get('description'), author: f.get('author'), claimed_km: f.get('claimed_km') ? Number(f.get('claimed_km')) : null, consent: f.get('consent') === 'on' });
    toast('Маршрут отправлен на проверку'); location.hash = `#/proposal/${result.id}`;
  } catch (e) { error.textContent = e.message; button.disabled = false; button.innerHTML = label; }
}
const PROPOSAL_TONE = { pending: 'warn', approved: 'ok', rejected: 'crit' };
async function viewModeration() {
  const list = await api('/api/proposals');
  view.innerHTML = `<div class="page-head row-between"><div><h1>Модерация маршрутов</h1><p class="muted">Предложенные пользователями треки. В каталог попадает только то, что одобрил человек.</p></div><a class="btn outline" href="#/propose">${icon('plus')}Предложить маршрут</a></div>
    <div class="callout warn">${icon('alert')}<div>В прототипе модерация открыта всем, кто видит сайт. В рабочей версии этот раздел будет только у модераторов с входом по паролю.</div></div>
    <div class="stack block">${list.length ? list.map(p => `<a class="card trip" href="#/proposal/${p.id}"><div class="trip-main"><div class="chips">${chip(PROPOSAL_TONE[p.status], p.status_label)}${p.checks.filter(c => c.level === 'warning').length ? chip('warn', `Проверить: ${p.checks.filter(c => c.level === 'warning').length}`, 'alert') : ''}</div><h3>${esc(p.name)}</h3><p class="muted">${esc(p.activityLabel)} · ${p.stats.distance_km} км · +${p.stats.ascent_m} м · до ${p.stats.max_elev} м${p.author ? ' · ' + esc(p.author) : ''}</p></div><div class="trip-next"><span>Открыть</span>${icon('right')}</div></a>`).join('') : empty('Предложений пока нет', 'Когда кто-нибудь загрузит свой трек, он появится здесь.', '<a class="btn" href="#/propose">Предложить маршрут</a>')}</div>`;
}
async function viewProposal(id) {
  const p = await api(`/api/proposals/${id}`), s = p.stats;
  const decide = p.status === 'pending' ? `<div class="card pad"><h3>Решение модератора</h3><label class="field">Комментарий автору <span class="muted">(для отказа обязателен)</span><textarea id="mod-note" rows="3" maxlength="300"></textarea></label>
    <div class="row"><button class="btn" data-act="moderate" data-value="approve" data-id="${p.id}">${icon('check')}Одобрить и опубликовать</button><button class="btn outline" data-act="moderate" data-value="reject" data-id="${p.id}">Отклонить</button></div></div>`
    : `<div class="callout ${p.status === 'approved' ? '' : 'warn'}">${icon(p.status === 'approved' ? 'check' : 'alert')}<div><b>${p.status_label}.</b> ${esc(p.moderator_note)} ${p.route_id ? `<a class="link" href="#/route/${p.route_id}">Открыть в каталоге ${icon('right')}</a>` : ''}</div></div>`;
  view.innerHTML = `<a class="back" href="#/moderation">${icon('left')}Все предложения</a>
    <div class="page-head"><div class="chips">${chip(PROPOSAL_TONE[p.status], p.status_label)}${chip('plain', esc(p.activityLabel))}</div><h1>${esc(p.name)}</h1><p class="muted">${esc(p.area || 'Район не указан')}${p.author ? ' · прислал(а) ' + esc(p.author) : ''}</p></div>
    <div class="tiles"><div><span>Длина по треку</span><b>${s.distance_km} км</b></div><div><span>Набор</span><b>${s.ascent_m} м</b></div><div><span>Старт</span><b>${s.start_elev} м</b></div><div><span>Верхняя точка</span><b>${s.max_elev} м</b></div><div><span>Сложность (оценка)</span><b>${s.ascent_m < 500 && s.distance_km <= 10 && s.max_elev < 2500 ? 'Лёгкий' : s.ascent_m < 1100 && s.max_elev < 3200 ? 'Средний' : 'Сложный'}</b></div></div>
    ${p.checks.length ? `<section class="block"><h2>Что проверить модератору</h2><div class="stack">${p.checks.map(c => `<div class="callout ${c.level === 'warning' ? 'warn' : ''}">${icon(c.level === 'warning' ? 'alert' : 'spark')}<div>${esc(c.text)}</div></div>`).join('')}</div><p class="note">Подсказки собраны правилами GoTAU по треку и описанию. Решение принимает человек.</p></section>` : ''}
    <section class="block"><h2>Трек и рельеф</h2><div class="card pad"><div class="map" id="proposal-map"></div>${profileChart(p.profile)}${terrainBlock(p.terrain)}</div></section>
    ${p.description ? `<section class="block"><h2>Описание автора</h2><blockquote>${esc(p.description)}</blockquote></section>` : ''}
    <section class="block">${decide}</section>`;
  drawMap($('#proposal-map'), { line: p.line, start: s.start, top: s.top });
}

/* ---------- мастер похода ---------- */
const newMember = () => ({ name: '', experience: 'some', age_group: 'adult', bulky: 'none', gear: ['boots', 'water'] });
function viewWizard(trip, routeId) {
  S.step = 1;
  S.draft = trip
    ? { id: trip.id, title: trip.title, route_id: trip.route_id, start_date: trip.start_date, start_time: trip.start_time, return_time: trip.return_time || '', organizer: trip.organizer, organizer_phone: trip.organizer_phone, members: trip.members.map(m => ({ ...m, gear: [...m.gear] })) }
    : { id: null, title: '', route_id: S.routes.some(r => r.id === routeId) ? routeId : '', start_date: localDay(1), start_time: '08:00', return_time: '18:00', organizer: '', organizer_phone: '', members: [newMember(), newMember()] };
  renderWizard();
}
function memberForm(m, i) {
  return `<fieldset class="card pad member" data-m="${i}"><legend>Участник ${i + 1}</legend>
    <label class="field">Имя<input data-f="name" maxlength="60" placeholder="Имя или прозвище" value="${esc(m.name)}" autocomplete="off"></label>
    <div class="field"><span class="label">Опыт в горах</span><div class="seg">${Object.entries(EXPERIENCE).map(([k, v]) => `<label><input type="radio" name="exp${i}" data-f="experience" value="${k}" ${m.experience === k ? 'checked' : ''}><span>${v}</span></label>`).join('')}</div></div>
    <div class="two"><label class="field">Возраст<select data-f="age_group">${options(AGE, m.age_group)}</select></label><label class="field">Крупный груз<select data-f="bulky">${options(BULKY, m.bulky)}</select></label></div>
    <div class="field"><span class="label">Что уже есть в рюкзаке</span><div class="toggles">${Object.entries(GEAR).map(([k, v]) => `<label><input type="checkbox" data-gear="${k}" ${m.gear.includes(k) ? 'checked' : ''}><span>${icon('check')}${v}</span></label>`).join('')}</div></div>
    ${S.draft.members.length > 1 ? `<button type="button" class="text danger" data-act="member-remove" data-index="${i}">${icon('trash')}Убрать участника</button>` : ''}</fieldset>`;
}
function renderWizard() {
  const d = S.draft, r = S.routes.find(x => x.id === d.route_id);
  const names = ['Куда и когда', 'Кто идёт', 'Проверьте и сохраните'];
  const head = `<a class="back" href="${d.id ? '#/trip/' + d.id : '#/'}">${icon('left')}${d.id ? 'К паспорту' : 'На главную'}</a>
    <div class="page-head"><h1>${d.id ? 'Изменить поход' : 'Новый поход'}</h1></div>
    <ol class="wsteps">${names.map((n, i) => `<li class="${i + 1 < S.step ? 'done' : i + 1 === S.step ? 'now' : ''}"><span>${i + 1 < S.step ? icon('check') : i + 1}</span>${n}</li>`).join('')}</ol>`;
  let body;
  if (S.step === 1) {
    body = `<section class="block"><h2>Куда идёте?</h2><div class="pick">${S.routes.map(x => `<label class="pick-item"><input type="radio" name="route" value="${x.id}" ${x.id === d.route_id ? 'checked' : ''}><span class="pick-body"><b>${esc(x.name)}</b><small>${esc(x.activityLabel)} · ${x.distance} км · ${x.hours} ч · до ${x.max_elev} м · ${esc(x.level)}</small></span></label>`).join('')}</div></section>
    <section class="block"><h2>Когда?</h2><div class="card pad"><div class="three"><label class="field">Дата<input type="date" data-d="start_date" value="${d.start_date}" min="${localDay()}"></label><label class="field">Выход<input type="time" data-d="start_time" value="${d.start_time}"></label><label class="field">Контрольное возвращение<input type="time" data-d="return_time" value="${d.return_time}"></label></div>
    <p class="note">Контрольное время — к которому группа точно должна вернуться. Если возвращение не отмечено, близкие по ссылке увидят предупреждение и порядок действий.</p>
    <label class="field"><span>Название похода <span class="muted">(не обязательно)</span></span><input data-d="title" maxlength="80" placeholder="Например: суббота с друзьями" value="${esc(d.title)}"></label></div></section>`;
  } else if (S.step === 2) {
    body = `<section class="block"><h2>Кто отвечает за группу?</h2><div class="card pad"><div class="two"><label class="field">Имя организатора<input data-d="organizer" maxlength="60" placeholder="Кто ведёт группу" value="${esc(d.organizer)}" autocomplete="off"></label><label class="field">Телефон<input type="tel" data-d="organizer_phone" maxlength="25" placeholder="+7 000 000 00 00" value="${esc(d.organizer_phone)}" autocomplete="off"></label></div>
    <p class="note">Имя и телефон нужны для текста уведомления в ДЧС. В модель ИИ они не передаются.</p></div></section>
    <section class="block"><div class="block-head"><h2>Участники</h2><span class="muted">${count(d.members.length, 'человек', 'человека', 'человек')}</span></div><div class="members">${d.members.map(memberForm).join('')}</div>
    <button type="button" class="btn outline wide" data-act="member-add">${icon('plus')}Добавить участника</button></section>`;
  } else {
    const title = d.title.trim() || `${r.name}, ${dmy(d.start_date)}`;
    body = `<section class="block"><div class="card pad"><p class="over">${esc(r.area)} · ${esc(r.activityLabel)}</p><h2>${esc(title)}</h2>
    <dl class="facts"><div><dt>Маршрут</dt><dd>${esc(r.name)}, ${r.distance} км, до ${r.max_elev} м</dd></div><div><dt>Когда</dt><dd>${niceDate(d.start_date)}, выход в ${d.start_time}</dd></div><div><dt>Контрольное возвращение</dt><dd>${d.return_time || 'не задано'}</dd></div><div><dt>Организатор</dt><dd>${esc(d.organizer || 'не указан')}</dd></div></dl>
    <h3>Группа</h3><ul class="people">${d.members.map(m => `<li><span class="ava">${esc(m.name.trim().charAt(0).toUpperCase())}</span><div><b>${esc(m.name)}</b><small>${EXPERIENCE[m.experience]} · ${AGE[m.age_group]} · вещей отмечено: ${m.gear.length} из ${Object.keys(GEAR).length}</small></div></li>`).join('')}</ul></div>
    <div class="callout">${icon('shield')}<div><b>Что будет с данными.</b> Поход хранится только на этом компьютере. ${S.ai.enabled ? 'В модель ИИ уйдут опыт, возрастная группа и снаряжение под метками «Участник 1, 2…»: без имён и телефонов.' : 'ИИ сейчас не подключён, проверку выполнят правила GoTAU. Когда ИИ включат, в модель будут уходить только обезличенные параметры без имён и телефонов.'} Медицинские сведения не вводите.</div></div></section>`;
  }
  const nav = `<p id="form-error" class="form-error" role="alert"></p><div class="wnav">${S.step > 1 ? `<button type="button" class="btn outline" data-act="wizard-back">${icon('left')}Назад</button>` : '<span></span>'}
    ${S.step < 3 ? `<button type="button" class="btn" data-act="wizard-next">Дальше ${icon('right')}</button>` : `<button type="button" class="btn" data-act="wizard-save">${d.id ? 'Сохранить и проверить заново' : 'Сохранить и проверить готовность'} ${icon('right')}</button>`}</div>`;
  view.innerHTML = head + body + nav;
}
function wizardCheck() {
  const d = S.draft;
  if (S.step === 1) {
    if (!d.route_id) return 'Выберите маршрут';
    if (!d.start_date) return 'Укажите дату похода';
    if (d.start_date < localDay()) return 'Дата похода не может быть в прошлом';
    if (!d.start_time) return 'Укажите время выхода';
    if (d.return_time && d.return_time <= d.start_time) return 'Контрольное возвращение должно быть позже выхода';
  }
  if (S.step === 2) {
    if (!d.members[0].name.trim() && d.organizer.trim()) d.members[0].name = d.organizer.trim();
    const missing = d.members.findIndex(m => !m.name.trim());
    if (missing >= 0) return `Впишите имя участника ${missing + 1}`;
  }
  return '';
}
async function wizardSave(button) {
  const d = S.draft, r = S.routes.find(x => x.id === d.route_id);
  const payload = { title: d.title.trim() || `${r.name}, ${dmy(d.start_date)}`, route_id: d.route_id, start_date: d.start_date, start_time: d.start_time, return_time: d.return_time || null, organizer: d.organizer, organizer_phone: d.organizer_phone, members: d.members };
  const label = button.innerHTML;
  button.disabled = true; button.textContent = 'Сохраняем и проверяем…';
  try {
    const id = d.id ? (await api(`/api/trips/${d.id}/update`, payload)).id : (await api('/api/trips', payload)).id;
    try { await api(`/api/trips/${id}/audit`, {}); } catch (error) { toast('Поход сохранён, но проверка не запустилась: ' + error.message); }
    S.tab = 'risks'; location.hash = `#/trip/${id}`;
  } catch (error) { $('#form-error').textContent = error.message; button.disabled = false; button.innerHTML = label; }
}

/* ---------- мои походы ---------- */
async function viewTrips() {
  const trips = await api('/api/trips');
  const active = trips.filter(t => t.status === 'planned' || t.status === 'active'), past = trips.filter(t => t.status === 'done' || t.status === 'cancelled');
  view.innerHTML = `<div class="page-head row-between"><h1>Мои походы</h1><a class="btn" href="#/new">${icon('plus')}Новый поход</a></div>
    ${trips.length ? '' : empty('Пока ни одного похода', 'Соберите первый: маршрут, группа, рюкзаки. GoTAU проверит готовность и подготовит ссылку для близких.', '<a class="btn" href="#/new">Собрать поход</a>')}
    ${active.length ? `<section class="block"><h2>Впереди</h2><div class="stack">${active.map(tripCard).join('')}</div></section>` : ''}
    ${past.length ? `<section class="block"><h2>Прошедшие</h2><div class="stack">${past.map(tripCard).join('')}</div></section>` : ''}
    <p class="note">Походы хранятся только в базе на этом компьютере. Сохранение похода не является регистрацией в МЧС.</p>`;
}

/* ---------- паспорт похода ---------- */
function named(text) { return esc(text).replace(/Участник (\d+)/g, (m, n) => S.trip.members[n - 1] ? esc(S.trip.members[n - 1].name) : m); }
const who = (label) => label === 'Группа' ? 'Вся группа' : named(label);
const factValue = (value) => Array.isArray(value) ? value.join(', ') : value === true ? 'да' : value === false ? 'нет' : value;
function tripState() {
  const t = S.trip, a = t.audit, recs = a ? a.recommendations : [];
  return { a, recs, stale: Boolean(a && a.stale), critical: recs.filter(r => r.severity === 'critical').length, warning: recs.filter(r => r.severity === 'warning').length,
    undecided: recs.filter(r => !r.decision && r.severity !== 'info').length, closed: t.status === 'done' || t.status === 'cancelled' };
}
function nextStep() {
  const t = S.trip, s = tripState();
  if (t.status === 'cancelled') return { title: 'Поход отменён', text: 'Его можно вернуть в подготовку.', action: '<button class="btn outline" data-act="status" data-value="planned">Вернуть в подготовку</button>' };
  if (t.status === 'done') return { title: 'Группа вернулась', text: 'Поход завершён. Близкие видят это по ссылке.', action: '' };
  if (t.overdue) return { tone: 'crit', title: 'Контрольное время прошло', text: 'Близкие по ссылке уже видят предупреждение. Если группа вернулась, отметьте это.', action: `<button class="btn" data-act="status" data-value="done">${icon('check')}Мы вернулись</button>` };
  if (!s.a) return { title: 'Проверьте готовность группы', text: 'GoTAU возьмёт прогноз на день похода и сверит его с маршрутом и рюкзаками участников.', action: `<button class="btn" data-act="audit">${icon('shield')}Проверить готовность</button>` };
  if (s.stale) return { tone: 'warn', title: 'Поход изменился после проверки', text: 'Замечания ниже могут быть уже неактуальны. Запустите проверку ещё раз.', action: `<button class="btn" data-act="audit">${icon('refresh')}Проверить заново</button>` };
  if (s.undecided) return { title: `Разберите замечания: осталось ${s.undecided}`, text: 'По каждому важному замечанию решите: принимаете рекомендацию или отклоняете. Так видно, что решение принял человек.', action: '<button class="btn" data-act="tab" data-value="risks">К замечаниям</button>' };
  if (!t.confirmed) return { title: 'Подтвердите паспорт', text: 'После подтверждения сводка подготовки станет видна близким по ссылке.', action: `<button class="btn" data-act="confirm">${icon('check')}Подтвердить паспорт</button>` };
  if (!t.share) return { title: 'Оставьте план близким', text: 'Создайте ссылку: по ней видны маршрут, время, статус группы и имя организатора. Имена остальных участников и телефоны не показываются.', action: `<button class="btn" data-act="share" data-value="create">${icon('share')}Создать ссылку</button>` };
  if (t.status === 'planned') return { tone: 'ok', title: 'Всё готово к выходу', text: 'В день похода отметьте выход, чтобы близкие видели, что группа на маршруте.', action: `<button class="btn" data-act="status" data-value="active">Вышли на маршрут ${icon('right')}</button>` };
  return { tone: 'ok', title: 'Группа на маршруте', text: `Когда спуститесь, отметьте возвращение. Контрольное время: ${t.return_time || 'не задано'}.`, action: `<button class="btn" data-act="status" data-value="done">${icon('check')}Мы вернулись</button>` };
}
function stepper() {
  const t = S.trip, s = tripState();
  const done = [true, Boolean(s.a && !s.stale), Boolean(s.a && !s.stale && !s.undecided), t.confirmed, Boolean(t.share)];
  const now = done.indexOf(false);
  return `<ol class="path">${['Группа собрана', 'Проверка', 'Решения', 'Подтверждение', 'Близкие в курсе'].map((n, i) => `<li class="${done[i] ? 'done' : i === now ? 'now' : ''}"><span>${done[i] ? icon('check') : i + 1}</span>${n}</li>`).join('')}</ol>`;
}
function verdict() {
  const t = S.trip, s = tripState(), a = s.a;
  if (!a) return '';
  const tone = s.critical ? 'crit' : s.warning ? 'warn' : 'ok';
  const title = s.critical ? `Есть критичные замечания: ${s.critical}` : s.warning ? `Есть что поправить до выхода: ${s.warning}` : 'Серьёзных замечаний нет';
  const mode = a.mode === 'ai'
    ? `<p class="mode">${icon('spark')}<span><b>Сгенерировано ИИ</b> (${esc(a.model)}) и проверено правилами GoTAU, ${esc(a.generated_at)}. Это подсказка, а не решение.</span></p>`
    : `<p class="mode">${icon('shield')}<span><b>Проверено правилами GoTAU, без ИИ</b>, ${esc(a.generated_at)}.${a.ai_error ? ' Причина: ' + esc(a.ai_error) + '.' : ''}</span></p>`;
  return `<section class="verdict ${tone}"><div class="verdict-main"><p class="over">Итог проверки</p><h2>${title}</h2><p>${(s.critical || s.warning) && !s.undecided ? 'Организатор разобрал все замечания.' : s.critical || s.warning ? 'Посмотрите, кого они касаются и что с этим сделать.' : 'По данным прогноза и рюкзакам группа подготовлена.'} Идти или нет — решает организатор.</p>${mode}</div>
    <div class="tiles compact"><div><span>В пути</span><b>≈ ${a.estimate.duration_h} ч</b></div><div><span>Финиш</span><b>≈ ${a.estimate.finish_time}</b></div><div><span>Контроль</span><b>${t.return_time || 'нет'}</b></div></div></section>`;
}
function recCard(r) {
  const state = r.decision === 'accepted' ? chip('ok', 'Принято', 'check') : r.decision === 'rejected' ? chip('plain', 'Отклонено') : '';
  return `<article class="rec ${r.severity}"><div class="chips">${chip(r.severity === 'critical' ? 'crit' : r.severity === 'warning' ? 'warn' : 'info', SEVERITY[r.severity])}${state}</div>
    <h3>${esc(r.title)}</h3><p class="rec-who">${icon('users')}${r.affected.map(who).join(', ')}</p><p>${named(r.explanation)}</p>
    <div class="todo"><b>Что сделать</b>${named(r.recommendation)}</div>
    <details><summary>На чём основано: ${count(r.evidence.length, 'факт', 'факта', 'фактов')} · ${SOURCE[r.source]}</summary><ul class="evidence">${r.evidence.map(e => `<li><span>${named(e.label)}</span><b>${esc(factValue(e.value))}</b></li>`).join('')}</ul></details>
    <div class="rec-actions"><button class="btn small ${r.decision === 'accepted' ? '' : 'outline'}" data-act="decide" data-id="${r.id}" data-value="accepted" aria-pressed="${r.decision === 'accepted'}">${icon('check')}Принять</button><button class="btn small outline ${r.decision === 'rejected' ? 'on' : ''}" data-act="decide" data-id="${r.id}" data-value="rejected" aria-pressed="${r.decision === 'rejected'}">Отклонить</button></div></article>`;
}
function tabRisks() {
  const s = tripState(), a = s.a;
  if (!a) return empty('Проверка ещё не запускалась', `GoTAU возьмёт реальный прогноз на высоте маршрута, посчитает время в пути и сверит всё это с рюкзаками участников. ${S.ai.enabled ? 'Объяснения напишет ИИ, а правила GoTAU проверят его ответ.' : 'Сейчас ИИ не подключён, поэтому проверку выполнят правила GoTAU.'}`, `<button class="btn" data-act="audit">${icon('shield')}Проверить готовность</button>`);
  const v = a.validation;
  const check = a.mode === 'ai' ? `<p class="note">Проверка ответа ИИ: получено замечаний — ${v.received}; отброшено без опоры на данные — ${v.dropped_no_evidence}; отброшено из-за чисел, которых нет в данных, — ${v.dropped_numbers}; добавлено из правил — ${v.added_from_rules}${v.summary_replaced ? '; сводка заменена шаблонной' : ''}.</p>` : '';
  return `${a.recommendations.length ? a.recommendations.map(recCard).join('') : empty('Замечаний нет', 'Правила не нашли рисков для этой группы на этот день.')}${check}
    <button class="text" data-act="audit">${icon('refresh')}Запустить проверку заново</button>`;
}
function tabGroup() {
  const t = S.trip, a = t.audit;
  const cards = t.members.map((m, i) => {
    const list = a ? (a.checklists.find(c => c.participant === `Участник ${i + 1}`) || { items: [] }).items : [];
    const need = list.filter(item => !(item.code && m.gear.includes(item.code)));
    const state = !a ? '' : need.length ? chip('warn', `Не хватает: ${need.length}`) : chip('ok', 'Всё взято', 'check');
    return `<article class="card pad person"><div class="person-head"><span class="ava">${esc(m.name.charAt(0).toUpperCase())}</span><div><h3>${esc(m.name)}</h3><p class="muted">${EXPERIENCE[m.experience]} · ${AGE[m.age_group]}${m.bulky !== 'none' ? ' · ' + BULKY[m.bulky].toLowerCase() : ''}</p></div>${state}</div>
      ${need.length ? `<p class="label">Нужно взять</p><ul class="need">${need.map(item => `<li><div><b>${named(item.item)}</b><small>${named(item.reason)}</small></div>${item.code ? `<button class="btn small outline" data-act="gear" data-member="${i}" data-code="${item.code}">${icon('check')}Взяли</button>` : ''}</li>`).join('')}</ul>` : ''}
      <p class="label">В рюкзаке</p><div class="chips">${m.gear.length ? m.gear.map(g => chip('plain', GEAR[g])).join('') : '<span class="muted">Ничего не отмечено</span>'}</div></article>`;
  });
  const shared = a ? ((a.checklists.find(c => c.participant === 'Группа') || { items: [] }).items).filter(item => !(item.code && t.members.some(m => m.gear.includes(item.code)))) : [];
  const common = shared.length ? `<article class="card pad person"><div class="person-head"><span class="ava group">${icon('users')}</span><div><h3>Общее на группу</h3><p class="muted">Достаточно одного комплекта на всех</p></div>${chip('warn', `Не хватает: ${shared.length}`)}</div>
    <ul class="need">${shared.map(item => `<li><div><b>${named(item.item)}</b><small>${named(item.reason)}</small></div>${item.code ? `<button class="btn small outline" data-act="gear" data-member="0" data-code="${item.code}">${icon('check')}Есть в группе</button>` : ''}</li>`).join('')}</ul></article>` : '';
  return `${a ? '' : '<p class="note">После проверки здесь появится список: кому что взять и почему.</p>'}<div class="people-grid">${common}${cards.join('')}</div>
    <a class="text" href="#/edit/${t.id}">${icon('edit')}Изменить состав и снаряжение</a>`;
}
function tabWeather() {
  const t = S.trip, a = t.audit;
  const map = `<div class="card pad"><h3>${icon('route')}${esc(routeOf(t).name)}</h3><div id="trip-map"><p class="loading">Загружаем карту…</p></div></div>`;
  if (!a) return map + empty('Прогноз появится после проверки', 'GoTAU запросит прогноз на дату похода для старта и верхней точки маршрута.', `<button class="btn" data-act="audit">${icon('shield')}Проверить готовность</button>`);
  if (!a.weather.available) return map + noWeather(a.weather.reason) + '<p class="note">Погодные риски в этой проверке не оценивались. Прогноз доступен не более чем на 15 дней вперёд: повторите проверку ближе к дате.</p>';
  return `${map}<div class="card pad"><h3>Хватит ли светлого времени</h3>${timeline(a.weather, t.start_time, a.estimate.finish_time, t.return_time)}<p class="note">Время в пути — оценка по длине, набору высоты и составу группы, с запасом на привалы.</p></div>
    <h3 class="sub">Прогноз на ${niceDate(t.start_date)}</h3>${weatherCards(a.weather)}`;
}
function tabShare() {
  const t = S.trip, a = t.audit, link = t.share ? `${location.origin}/p/${t.share.token}` : '';
  const tr = a ? a.transport : null;
  return `<div class="card pad"><h3>${icon('share')}Ссылка для близких</h3><p>По ссылке видны маршрут, время, статус группы, имя организатора и сводка подготовки. Имена остальных участников, телефоны и списки вещей не показываются. Ссылка перестаёт работать через 48 часов после контрольного времени.</p>
      ${t.share ? `<div class="copyrow"><input readonly value="${esc(link)}" aria-label="Ссылка для близких"><button class="btn small" data-act="copy" data-text="${esc(link)}">${icon('copy')}Копировать</button></div><div class="row"><a class="text" href="${esc(link)}" target="_blank" rel="noopener">Открыть, как увидят близкие ${icon('right')}</a><button class="text danger" data-act="share" data-value="revoke">Отозвать ссылку</button></div>` : `<button class="btn outline" data-act="share" data-value="create">${icon('share')}Создать ссылку</button>`}
      <p class="note">${t.confirmed ? 'Паспорт подтверждён: сводка видна по ссылке.' : 'Сводка появится по ссылке после того, как вы подтвердите паспорт.'} Автоматических SMS и звонков нет. Сервер прототипа работает только на этом компьютере, поэтому с другого устройства ссылка не откроется.</p></div>
    ${a ? `<div class="card pad"><h3>${icon('doc')}Сводка подготовки</h3><blockquote>${named(a.summary)}</blockquote><p class="note">${a.mode === 'ai' ? 'Текст составил ИИ по обезличенным данным и прогнозу, правила GoTAU его проверили.' : 'Текст собран по правилам GoTAU, без ИИ.'} Близким он показывается без имён.</p></div>` : ''}
    <div class="card pad"><h3>${icon('doc')}Уведомление для ДЧС</h3><p>Туристы заранее сообщают в департамент по чрезвычайным ситуациям о выходе в горы. GoTAU собирает текст из паспорта, а отправляете его вы сами.</p><button class="btn outline" data-act="notice">Собрать текст уведомления</button><div id="notice"></div></div>
    ${tr ? `<div class="card pad"><h3>${icon('car')}Как добраться до старта</h3><p><b>${esc(tr.vehicle)}.</b> Нужно мест: ${tr.seats_needed} (людей — ${tr.people}, крупного груза — ${tr.bulky_items}). ${named(tr.note)}</p><label class="field split">Стоимость поездки на всех, ₸<input id="price" type="number" min="0" step="500" inputmode="numeric" placeholder="например, 30000"></label><p id="per-person" class="per"></p><p class="note">Это расчёт, а не заказ: бронирование транспорта не подключено.</p></div>` : ''}`;
}
function renderTrip() {
  const t = S.trip, r = routeOf(t), s = tripState(), step = nextStep();
  const tabs = { risks: `Замечания${s.a ? ' · ' + s.recs.length : ''}`, group: 'Рюкзаки', weather: 'Маршрут', share: 'Близкие' };
  clearMaps();
  const body = { risks: tabRisks, group: tabGroup, weather: tabWeather, share: tabShare }[S.tab]();
  view.innerHTML = `<a class="back" href="#/trips">${icon('left')}Мои походы</a>
    <div class="page-head"><div class="chips">${chip(t.overdue ? 'crit' : STATUS_TONE[t.status], t.overdue ? 'Не отметили возвращение' : esc(t.status_label))}${t.confirmed ? chip('ok', 'Паспорт подтверждён', 'check') : ''}</div>
    <h1>${esc(t.title)}</h1><p class="muted">${esc(r.name)} · ${niceDate(t.start_date)} · выход в ${t.start_time} · ${count(t.participants, 'человек', 'человека', 'человек')}${t.organizer ? ' · ведёт ' + esc(t.organizer) : ''}</p></div>
    ${stepper()}
    <section class="next ${step.tone || ''}"><div><p class="over">Что дальше</p><h2>${step.title}</h2><p>${step.text}</p></div>${step.action}</section>
    ${verdict()}
    <div class="tabs" role="tablist">${Object.entries(tabs).map(([k, v]) => `<button role="tab" aria-selected="${S.tab === k}" class="${S.tab === k ? 'on' : ''}" data-act="tab" data-value="${k}">${v}</button>`).join('')}</div>
    <div class="tab-body" role="tabpanel">${body}</div>
    <div class="trip-foot"><a class="text" href="#/edit/${t.id}">${icon('edit')}Изменить поход</a>${t.status === 'planned' ? '<button class="text" data-act="status" data-value="cancelled">Отменить поход</button>' : ''}${t.status === 'active' ? '<button class="text" data-act="status" data-value="planned">Вернуть в подготовку</button>' : ''}<button class="text danger" data-act="delete">${icon('trash')}Удалить</button></div>`;
  if (S.tab === 'weather') routeMapBlock(r, '#trip-map');
}
async function viewTrip(id) { S.trip = await api(`/api/trips/${id}`); renderTrip(); }
async function act(path, payload, done) {
  try { S.trip = await api(`/api/trips/${S.trip.id}/${path}`, payload); renderTrip(); if (done) toast(done); return true; }
  catch (error) { toast(error.message); return false; }
}

/* ---------- события ---------- */
const ACTIONS = {
  filter(el) { S.filter = el.dataset.value; viewRoutes(); },
  source(el) { S.source = el.dataset.value; viewRoutes(); },
  async moderate(el) {
    const note = $('#mod-note').value.trim();
    if (el.dataset.value === 'reject' && !note) { toast('Напишите автору, почему маршрут отклонён'); $('#mod-note').focus(); return; }
    el.disabled = true;
    try { await api(`/api/proposals/${el.dataset.id}/${el.dataset.value}`, { note }); if (el.dataset.value === 'approve') S.routes = await api('/api/routes'); toast(el.dataset.value === 'approve' ? 'Маршрут опубликован в каталоге' : 'Маршрут отклонён'); await viewProposal(el.dataset.id); }
    catch (error) { toast(error.message); el.disabled = false; }
  },
  tab(el) { S.tab = el.dataset.value; renderTrip(); $('.tabs').scrollIntoView({ behavior: 'smooth', block: 'start' }); },
  async audit(el) { el.disabled = true; el.textContent = S.ai.enabled ? 'Проверяем… до минуты' : 'Проверяем…'; if (!await act('audit', {}, 'Проверка готова')) renderTrip(); },
  decide(el) { const rec = S.trip.audit.recommendations.find(r => r.id === el.dataset.id); return act('decision', { rec_id: rec.id, decision: rec.decision === el.dataset.value ? null : el.dataset.value }); },
  confirm() { return act('confirm', {}, 'Паспорт подтверждён'); },
  status(el) { return act('status', { status: el.dataset.value }); },
  share(el) { if (el.dataset.value === 'create') S.tab = 'share'; return act('share', { action: el.dataset.value }, el.dataset.value === 'create' ? 'Ссылка создана' : 'Ссылка отозвана'); },
  gear(el) { return act('gear', { member: Number(el.dataset.member), code: el.dataset.code, has: true }, 'Отмечено. Запустите проверку заново, чтобы обновить замечания'); },
  copy(el) { return copyText(el.dataset.text); },
  async notice() { try { const n = await api(`/api/trips/${S.trip.id}/notice`); $('#notice').innerHTML = `<textarea readonly rows="14" aria-label="Текст уведомления">${esc(n.text)}</textarea><button class="btn small" data-act="copy" data-text="${esc(n.text)}">${icon('copy')}Копировать текст</button><p class="note">${esc(n.channels)}</p>`; } catch (error) { toast(error.message); } },
  async delete() { if (!confirm('Удалить поход вместе с проверкой и ссылкой? Вернуть его будет нельзя.')) return; try { await api(`/api/trips/${S.trip.id}/delete`, {}); toast('Поход удалён'); location.hash = '#/trips'; } catch (error) { toast(error.message); } },
  'member-add'() { if (S.draft.members.length >= 30) return toast('В группе не больше 30 человек'); S.draft.members.push(newMember()); renderWizard(); $$('[data-m]').pop().scrollIntoView({ behavior: 'smooth', block: 'center' }); },
  'member-remove'(el) { S.draft.members.splice(Number(el.dataset.index), 1); renderWizard(); },
  'wizard-back'() { S.step -= 1; renderWizard(); window.scrollTo(0, 0); },
  'wizard-next'() { const error = wizardCheck(); if (error) { $('#form-error').textContent = error; return; } S.step += 1; renderWizard(); window.scrollTo(0, 0); },
  'wizard-save'(el) { return wizardSave(el); },
};
document.addEventListener('click', e => {
  const el = e.target.closest('[data-act]');
  if (el && ACTIONS[el.dataset.act]) ACTIONS[el.dataset.act](el);
});
document.addEventListener('submit', e => { if (e.target.id === 'propose') { e.preventDefault(); submitProposal(e.target); } });
document.addEventListener('input', e => {
  const el = e.target, d = S.draft;
  if (el.id === 'q') { S.query = el.value; $('#route-grid').innerHTML = routeGrid(); return; }
  if (el.id === 'wx-date') { if (el.value) loadRouteWeather(el.dataset.route, el.value); return; }
  if (el.id === 'price') { const price = Number(el.value), people = S.trip.audit.transport.people; $('#per-person').textContent = price > 0 ? `Около ${Math.ceil(price / people).toLocaleString('ru')} ₸ с человека` : ''; return; }
  if (!d) return;
  if (el.name === 'route') { d.route_id = el.value; return; }
  if (el.dataset.d) { d[el.dataset.d] = el.value; return; }
  const block = el.closest('[data-m]');
  if (!block) return;
  const member = d.members[Number(block.dataset.m)];
  if (el.dataset.f) member[el.dataset.f] = el.value;
  if (el.dataset.gear) member.gear = el.checked ? [...new Set([...member.gear, el.dataset.gear])] : member.gear.filter(g => g !== el.dataset.gear);
});

/* ---------- переходы между экранами ---------- */
async function route() {
  const [name, arg] = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const section = !name ? 'home' : ['route', 'propose', 'moderation', 'proposal'].includes(name) ? 'routes' : name === 'trip' ? 'trips' : name === 'edit' ? 'trips' : name;
  $$('[data-nav]').forEach(a => { if (a.dataset.nav === section) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  document.body.classList.toggle('in-wizard', name === 'new' || name === 'edit');
  if (name !== 'new' && name !== 'edit') S.draft = null;
  clearMaps();
  try {
    if (!name) await viewHome();
    else if (name === 'routes') viewRoutes();
    else if (name === 'route') viewRoute(arg);
    else if (name === 'propose') viewPropose();
    else if (name === 'moderation') await viewModeration();
    else if (name === 'proposal') await viewProposal(arg);
    else if (name === 'new') viewWizard(null, arg);
    else if (name === 'edit') viewWizard(await api(`/api/trips/${arg}`));
    else if (name === 'trips') await viewTrips();
    else if (name === 'trip') await viewTrip(arg);
    else view.innerHTML = empty('Такой страницы нет', 'Возможно, ссылка устарела.', '<a class="btn" href="#/">На главную</a>');
  } catch (error) { view.innerHTML = empty('Не получилось открыть страницу', esc(error.message) + '.', '<a class="btn" href="#/">На главную</a>'); }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);
(async () => {
  try { S.routes = await api('/api/routes'); }
  catch (error) { view.innerHTML = empty('Сервер GoTAU не отвечает', 'Запустите его командой py app.py и обновите страницу.'); return; }
  try { S.ai = await api('/api/ai-status'); } catch (error) { /* без статуса ИИ интерфейс работает в режиме правил */ }
  route();
})();
