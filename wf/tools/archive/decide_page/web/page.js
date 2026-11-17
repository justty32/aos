/* Wire offline choices, notes, seen state, themes, and reply copying. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('decide-data').textContent);
  const choices = Object.create(null), notes = Object.create(null), seen = Object.create(null);
  const cards = new Map();
  const output = document.querySelector('.reply-output');
  const status = document.querySelector('.reply-status');
  const reset = document.querySelector('.reply-reset');
  const theme = document.documentElement;
  try {
    const savedTheme = localStorage.getItem('aos-theme');
    if (savedTheme === 'light' || savedTheme === 'dark') theme.dataset.theme = savedTheme;
  } catch (_) { /* Storage is optional. */ }
  document.getElementById('theme').addEventListener('click', () => {
    const dark = theme.dataset.theme ? theme.dataset.theme === 'dark' :
      window.matchMedia('(prefers-color-scheme: dark)').matches;
    theme.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('aos-theme', theme.dataset.theme); } catch (_) { /* Keep the current theme. */ }
  });
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(data.storage_key) || '{}') || {}; }
  catch (_) { /* Ignore unavailable or malformed saved state. */ }
  function validObject(value) { return value && typeof value === 'object' && !Array.isArray(value); }
  for (const row of data.rows) {
    choices[row.id] = validObject(saved.choices) && row.keys.includes(saved.choices[row.id]) ?
      saved.choices[row.id] : row.fallback;
    notes[row.id] = validObject(saved.notes) && typeof saved.notes[row.id] === 'string' ? saved.notes[row.id] : '';
    seen[row.id] = !!(validObject(saved.seen) && saved.seen[row.id] === true);
    cards.set(row.id, document.getElementById('q-' + row.id));
  }
  function store() {
    try { localStorage.setItem(data.storage_key, JSON.stringify({choices, notes, seen})); }
    catch (_) { /* The page continues to work in memory. */ }
  }
  function refresh() {
    let count = 0, changed = 0;
    const items = data.rows.map(row => {
      const card = cards.get(row.id);
      if (seen[row.id]) count++;
      const different = row.keys.length > 0 && choices[row.id] !== row.recommend;
      if (different) changed++;
      card.classList.toggle('is-seen', seen[row.id]);
      const mark = card.querySelector('.read-mark');
      mark.textContent = seen[row.id] ? '✓ 已看過' : '看過，先照這個';
      mark.setAttribute('aria-pressed', String(seen[row.id]));
      card.querySelectorAll('input[type="radio"]').forEach(input => {
        input.checked = input.value === choices[row.id];
        input.closest('li').classList.toggle('is-selected', input.checked);
      });
      const note = notes[row.id].trim().replace(/\r\n|\r|\n/g, ' / ');
      return row.id + ':' + choices[row.id] + (different ? '*' : '') + (seen[row.id] ? '' : '?') +
        (note ? '（備註：' + note + '）' : '');
    });
    output.value = '[' + data.batch + '] ' + items.join('、');
    document.querySelector('.reply-compact').textContent = '已看過 ' + count + '／' + data.rows.length + ' 題';
    document.querySelector('.reply-progress progress').value = count;
    document.querySelector('.reply-changes').textContent = '* ＝跟推薦不同（' + changed +
      ' 題）；? ＝還沒看過（' + (data.rows.length - count) + ' 題，仍算待定、之後再問）';
  }
  function update(row) {
    seen[row.id] = true;
    status.textContent = '';
    refresh();
    store();
  }
  for (const row of data.rows) {
    const card = cards.get(row.id);
    card.querySelectorAll('input[type="radio"]').forEach(input => {
      input.addEventListener('click', () => { choices[row.id] = input.value; update(row); });
      input.addEventListener('change', () => { choices[row.id] = input.value; update(row); });
    });
    const note = card.querySelector('textarea');
    note.value = notes[row.id];
    note.addEventListener('input', () => { notes[row.id] = note.value; update(row); });
    card.querySelector('.read-mark').addEventListener('click', () => update(row));
    card.querySelectorAll('details').forEach(details => {
      details.addEventListener('toggle', () => { if (details.open) update(row); });
    });
  }
  const toggle = document.querySelector('.reply-toggle');
  const body = document.getElementById('reply-body');
  function collapse(value) {
    body.hidden = value;
    toggle.setAttribute('aria-expanded', String(!value));
    document.querySelector('.reply-toggle-action').textContent = value ? '展開' : '收合';
  }
  collapse(window.matchMedia('(max-width: 700px)').matches);
  toggle.addEventListener('click', () => collapse(!body.hidden));
  document.querySelector('.reply-copy').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(output.value);
      status.textContent = '已複製';
    } catch (_) {
      output.focus();
      output.select();
      output.setSelectionRange(0, output.value.length);
      status.textContent = '已選取，請按 Ctrl+C';
    }
  });
  let resetTimer = null;
  reset.addEventListener('click', () => {
    if (resetTimer === null) {
      reset.textContent = '再按一次確認重設';
      resetTimer = window.setTimeout(() => {
        resetTimer = null;
        reset.textContent = '全部重設為推薦';
      }, 4000);
      return;
    }
    window.clearTimeout(resetTimer);
    resetTimer = null;
    reset.textContent = '全部重設為推薦';
    for (const row of data.rows) {
      choices[row.id] = row.fallback;
      notes[row.id] = '';
      seen[row.id] = false;
      cards.get(row.id).querySelector('textarea').value = '';
    }
    refresh();
    store();
    status.textContent = '已重設為推薦';
  });
  refresh();
})();
