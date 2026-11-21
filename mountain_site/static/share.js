'use strict';
/* Страница для близких: маршрут, время и статус группы. Обновляется раз в минуту. */
const esc = (text) => String(text ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
const niceDate = (iso) => { const [, m, d] = iso.split('-').map(Number); return `${d} ${MONTHS[m - 1]}`; };
const box = document.querySelector('#share');
function stateCard(t) {
  if (t.overdue) return `<div class="state overdue"><strong>Группа не отметила возвращение</strong><p>Контрольное время ${t.return_time} прошло. Это ещё не значит, что что-то случилось: в горах часто нет связи, и группы задерживаются.</p>
    <ol class="todo-steps"><li>Позвоните организатору${t.organizer ? ' (' + esc(t.organizer) + ')' : ''} и участникам.</li><li>Подождите 1–2 часа и попробуйте ещё раз.</li><li>Если связи нет, звоните 112. Назовите маршрут, дату, время выхода и число людей с этой страницы.</li></ol></div>`;
  if (t.status === 'done') return '<div class="state active"><strong>Группа вернулась</strong><p>Организатор отметил возвращение.</p></div>';
  if (t.status === 'cancelled') return '<div class="state"><strong>Поход отменён</strong><p>Группа никуда не выходила.</p></div>';
  if (t.status === 'active') return `<div class="state active"><strong>Группа на маршруте</strong><p>Контрольное время возвращения: ${t.return_time || 'не задано'}. В горах связь есть не везде, это нормально.</p></div>`;
  return '<div class="state"><strong>Поход ещё не начался</strong><p>Организатор готовит группу. Статус изменится, когда группа выйдет.</p></div>';
}
async function load() {
  try {
    const res = await fetch('/api/share/' + location.pathname.split('/').pop());
    const t = await res.json();
    if (!res.ok) throw new Error(t.error);
    const cell = (name, value) => `<div><span>${name}</span><b>${value}</b></div>`;
    box.innerHTML = `<p class="over">${esc(t.area)}</p><h1>${esc(t.title)}</h1><p class="muted">${esc(t.route)}</p>${stateCard(t)}
      <div class="card pad"><h2>План группы</h2><div class="plan">${cell('Дата', niceDate(t.start_date))}${cell('Выход', t.start_time)}${t.estimate ? cell('Расчётный финиш', 'около ' + t.estimate.finish_time) : ''}${cell('Контрольное время', t.return_time || 'не задано')}${cell('Маршрут', `${t.distance} км, до ${t.max_elev} м`)}${cell('В группе', t.participants + ' чел.')}${t.organizer ? cell('Организатор', esc(t.organizer)) : ''}</div></div>
      <div class="card pad"><h2>Как группа подготовилась</h2>${t.summary ? `<blockquote>${esc(t.summary)}</blockquote><p class="note">${t.summary_by_ai ? 'Текст составил ИИ по данным организатора и прогнозу погоды. Его проверили правила TAU и подтвердил организатор.' : 'Текст собран по правилам TAU и подтверждён организатором.'} Это не гарантия безопасности маршрута.</p>` : '<p>Организатор ещё не подтвердил проверку готовности. Сводка появится здесь позже.</p>'}</div>
      <p class="note">Страница обновляется сама раз в минуту, последняя проверка ${esc(t.checked_at)}. Ссылка действует до ${esc(t.expires.replace('T', ' '))}. TAU — учебный прототип: он не отслеживает местоположение группы и не вызывает спасателей.</p>`;
  } catch (error) {
    box.innerHTML = `<div class="empty"><h3>Ссылка не работает</h3><p>${esc(error.message || 'Не удалось загрузить данные')}. Попросите организатора прислать новую.</p></div>`;
  }
}
load();
setInterval(load, 60000);
