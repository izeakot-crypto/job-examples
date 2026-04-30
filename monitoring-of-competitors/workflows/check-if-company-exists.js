// Check If Company Exists
const allInputs = $input.all();

// Розділяємо inputs: існуючі рядки (мають row_number) vs нові дані аналізу
let newData = null;
const existingRows = [];

for (const item of allInputs) {
  const data = item.json;
  if (data.row_number) {
    // Це рядок з Google Sheets (від Get Existing Data)
    existingRows.push(data);
  } else if (data['Компанія'] || data['AI Summary'] || data._isNewData) {
    // Це нові дані аналізу
    newData = data;
  }
}

// Fallback: якщо не знайшли по ознаках - останній елемент
if (!newData && allInputs.length > 0) {
  newData = allInputs[allInputs.length - 1].json;
}

const company = newData['Компанія'] || newData.company || 'Unknown';
const url = newData['URL'] || newData.url || '';

// Шукаємо компанію в існуючих рядках (partial match)
let foundRow = null;
const searchCompany = String(company).toLowerCase().trim();
const searchUrl = String(url).toLowerCase().trim().replace(/\/+$/, '');

for (const row of existingRows) {
  const rowCompany = String(row['Компанія'] || row.company || row['Company'] || '').toLowerCase().trim();
  const rowUrl = String(row['URL'] || row.url || '').toLowerCase().trim().replace(/\/+$/, '');

  // Збіг по імені: точний або один містить інший
  const nameMatch = rowCompany && searchCompany &&
    (rowCompany === searchCompany ||
     searchCompany.includes(rowCompany) ||
     rowCompany.includes(searchCompany));

  // Збіг по URL
  const urlMatch = rowUrl && searchUrl &&
    searchUrl !== '-' && rowUrl !== '-' &&
    (rowUrl === searchUrl ||
     searchUrl.includes(rowUrl) ||
     rowUrl.includes(searchUrl));

  if (nameMatch || urlMatch) {
    foundRow = row;
    break;
  }
}

// Результат: всі дані + _action для IF ноди
// _action: "update" → IF true → Update Row
// _action: "append" → IF false → Append New Row
return {
  'Дата': newData['Дата'] || new Date().toISOString().split('T')[0],
  'Компанія': company,
  'URL': url,
  'Нові фічі': newData['Нові фічі'] || '-',
  'Проблеми': newData['Проблеми'] || '-',
  'Інсайти з коментарів': newData['Інсайти з коментарів'] || '-',
  'Новини (з останньої перевірки)': newData['Новини (з останньої перевірки)'] || '-',
  'Статті в блозі (з останньої перевірки)': newData['Статті в блозі (з останньої перевірки)'] || '-',
  'YouTube активність': newData['YouTube активність'] || '-',
  'Facebook активність': newData['Facebook активність'] || '-',
  'LinkedIn активність': newData['LinkedIn активність'] || '-',
  'Згадки на агрегаторах': newData['Згадки на агрегаторах'] || '-',
  'Кількість згадок в соцмережах': newData['Кількість згадок в соцмережах'] || '0',
  'Болі клієнтів з коментарів': newData['Болі клієнтів з коментарів'] || '-',
  'Хотілки клієнтів з коментарів': newData['Хотілки клієнтів з коментарів'] || '-',
  'AI Summary': newData['AI Summary'] || '-',
  'isNewEntry': newData['isNewEntry'] || 'false',
  '_action': foundRow ? 'update' : 'append',
  '_rowNumber': foundRow ? foundRow.row_number : null
};
