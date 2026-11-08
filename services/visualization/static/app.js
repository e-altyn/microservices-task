const $ = id => document.getElementById(id);
let busy = false;

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, options);
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(e => e.msg).join('; ') : data.detail;
    throw new Error(detail || `Ошибка HTTP ${response.status}`);
  }
  return data;
}
const json = (method, body) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
function message(text, error = false) {
  $('message').textContent = text;
  $('message').className = error ? 'error' : '';
  $('message').hidden = !text;
}
async function action(fn) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button').forEach(button => button.disabled = true);
  try { await fn(); } catch (error) { message(error.message, true); }
  finally { busy = false; document.querySelectorAll('button').forEach(button => button.disabled = false); }
}
function table(container, headers, rows) {
  container.replaceChildren();
  const tbl = document.createElement('table');
  const head = tbl.createTHead().insertRow();
  headers.forEach(text => { const th = document.createElement('th'); th.textContent = text; head.append(th); });
  const body = tbl.createTBody();
  rows.forEach(values => { const row = body.insertRow(); values.forEach(text => row.insertCell().textContent = text ?? '—'); });
  container.append(tbl);
}
function fillSelect(id, items) {
  const select = $(id), previous = select.value;
  select.replaceChildren();
  select.add(new Option(items.length ? 'Выберите…' : 'Пока нет данных', ''));
  items.forEach(item => select.add(new Option(`${item.name}${item.algorithm ? ` · ${item.algorithm}` : ''} · ${item.id.slice(0, 8)}`, item.id)));
  if (items.some(item => item.id === previous)) select.value = previous;
}
async function refresh() {
  const [datasets, models] = await Promise.all([api('/datasets'), api('/models')]);
  fillSelect('training-data', datasets.filter(item => item.kind === 'raw'));
  fillSelect('prediction-dataset', datasets.filter(item => item.kind === 'raw'));
  fillSelect('prediction-model', models.filter(item => item.status === 'trained'));
  fillSelect('summary-model', models);
  $('datasets').replaceChildren();
  if (!datasets.length) { const row = $('datasets').insertRow(); const cell = row.insertCell(); cell.colSpan = 5; cell.textContent = 'Датасеты появятся после загрузки батча.'; }
  datasets.forEach(item => {
    const row = $('datasets').insertRow();
    [item.name, item.kind === 'raw' ? 'Сырые' : 'Подготовленные', item.row_count, item.is_synthetic ? `${item.source} (синтетика)` : item.source].forEach(text => row.insertCell().textContent = text);
    const cell = row.insertCell();
    const button = (text, handler) => { const b = document.createElement('button'); b.textContent = text; b.type = 'button'; b.className = 'secondary'; b.onclick = () => action(handler); cell.append(b); };
    button('Просмотр', async () => {
      const data = await api(`/datasets/${item.id}`), keys = Object.keys(data.records[0]);
      table($('preview'), keys, data.records.slice(0, 10).map(record => keys.map(key => record[key])));
      $('preview-panel').open = true;
      message(`Первые ${Math.min(10, data.row_count)} строк: ${data.name}`);
    });
    button('Имя', async () => {
      const name = prompt('Новое название датасета', item.name);
      if (!name?.trim()) return;
      await api(`/datasets/${item.id}`, json('PATCH', {name: name.trim()}));
      await refresh(); message('Название сохранено.');
    });
    button('Удалить', async () => {
      if (!confirm(`Удалить датасет «${item.name}»? Обученные модели сохранятся.`)) return;
      await api(`/datasets/${item.id}`, {method: 'DELETE'});
      await refresh(); message('Датасет удалён.');
    });
  });
}
$('collect-form').onsubmit = event => { event.preventDefault(); action(async () => {
  message('Получаем и сохраняем данные…');
  const data = await api('/datasets/collect', json('POST', {batch_number: Number($('batch-number').value)}));
  await refresh(); $('training-data').value = data.id;
  $('batch-number').value = data.batch_number + 1;
  message(`Сохранено ${data.row_count} строк. Батч ${data.batch_number} из ${data.total_batches}.${data.is_synthetic ? ' Данные синтетические.' : ''}`);
}); };
$('refresh').onclick = () => action(async () => { await refresh(); message('Списки обновлены.'); });
$('train-form').onsubmit = event => { event.preventDefault(); action(async () => {
  const datasetId = $('training-data').value;
  message('Обучаем модель и считаем метрики на тестовой выборке…');
  const model = await api('/models', json('POST', {name: $('model-name').value, algorithm: $('model-algorithm').value}));
  try {
    await api(`/models/${model.id}/train`, json('POST', {dataset_id: datasetId}));
  } catch (error) { await refresh(); throw error; }
  await refresh(); $('prediction-model').value = model.id; $('summary-model').value = model.id;
  await showSummary(model.id); message('Модель обучена. Можно получить прогноз или изучить оценку.');
}); };
function clearPredictions() {
  $('predictions').replaceChildren(); $('prediction-note').textContent = '';
}
function updatePredictionSource() {
  const csv = $('prediction-source').value === 'csv';
  $('prediction-dataset-field').hidden = csv;
  $('prediction-dataset').required = !csv;
  $('prediction-file-field').hidden = !csv;
  $('prediction-file').required = csv;
  clearPredictions();
}
$('prediction-source').onchange = updatePredictionSource;
updatePredictionSource();
$('predict-form').onsubmit = event => { event.preventDefault(); action(async () => {
  message('Выполняем прогноз…');
  clearPredictions();
  const modelId = $('prediction-model').value;
  let result;
  if ($('prediction-source').value === 'dataset') {
    result = await api(`/models/${modelId}/predict-dataset`, json('POST', {dataset_id: $('prediction-dataset').value}));
  } else {
    const body = new FormData(); body.append('file', $('prediction-file').files[0]);
    result = await api(`/models/${modelId}/predict-csv`, {method: 'POST', body});
  }
  const predictions = result.predictions;
  table($('predictions'), ['Строка', 'Вероятность дефолта', 'Прогноз (0/1)'], predictions.map(row => [row.row, row.probability.toFixed(4), row.prediction]));
  $('prediction-note').textContent = result.is_synthetic ? 'Модель обучена на синтетических данных.' : '';
  if (result.dataset_id) $('prediction-note').textContent += ` Данные: ${result.dataset_name} · ${result.dataset_id.slice(0, 8)}.`;
  message(`Готово: ${predictions.length} прогнозов.`);
}); };
async function showSummary(id) {
  const model = await api(`/models/${id}`), root = $('summary'); root.replaceChildren();
  const title = document.createElement('h3'); title.textContent = model.name; root.append(title);
  const description = document.createElement('p'); description.textContent = `Алгоритм: ${model.algorithm}. Состояние: ${{created:'создана',training:'обучается',trained:'обучена',failed:'ошибка'}[model.status] || model.status}. ID: ${model.id}`; root.append(description);
  if (model.error) { const p = document.createElement('p'); p.textContent = model.error; root.append(p); }
  if (!model.metrics) return;
  const m = model.metrics, cards = document.createElement('div'); cards.className = 'metrics';
  [['ROC AUC', m.roc_auc], ['Accuracy', m.accuracy], ['Precision', m.precision], ['Recall', m.recall]].forEach(([label, value]) => {
    const card = document.createElement('div'); card.className = 'metric'; card.textContent = label;
    const strong = document.createElement('strong'); strong.textContent = value.toFixed(3); card.append(strong); cards.append(card);
  }); root.append(cards);
  const size = document.createElement('p'); size.textContent = `Обучение: ${m.train_rows} строк; тест: ${m.test_rows}; исключено неподходящих статусов: ${m.excluded_rows}. Порог: ${m.threshold}.`; root.append(size);
  const matrix = document.createElement('div'); table(matrix, ['Истинный класс', 'Прогноз 0', 'Прогноз 1'], [['0 — погашен', ...m.confusion_matrix[0]], ['1 — дефолт', ...m.confusion_matrix[1]]]); root.append(matrix);
  if (model.is_synthetic) { const note = document.createElement('p'); note.className = 'notice'; note.textContent = 'Синтетическая выборка: эти метрики показывают работу приложения и не оценивают качество на Lending Club.'; root.append(note); }
}
$('summary-form').onsubmit = event => { event.preventDefault(); action(async () => { await showSummary($('summary-model').value); message('Оценка модели загружена.'); }); };
(async () => {
  try { const status = await api('/system'); $('system').textContent = Object.entries(status).map(([key, value]) => `${key}: ${value === 'ok' ? 'доступен' : 'недоступен'}`).join(' · '); await refresh(); }
  catch (error) { message(error.message, true); $('system').textContent = 'Не удалось проверить сервисы'; }
})();
