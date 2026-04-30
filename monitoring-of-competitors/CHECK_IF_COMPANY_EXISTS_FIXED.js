// Check If Company Exists - FIXED VERSION
// Ця нода отримує дані з Format for Sheets та Get Existing Data
// Визначає: оновити існуючий рядок або додати новий

// ============================================
// КРОК 1: Отримуємо нові дані компанії
// ============================================
// Input 0 - дані з Format for Sheets (нові дані)
const newCompanyData = $input.first().json;

const company = newCompanyData['Компанія'] || newCompanyData._originalData?.company || 'Unknown';
const url = newCompanyData['URL'] || newCompanyData._originalData?.url || '';

console.log('=== CHECK IF COMPANY EXISTS ===');
console.log('New company:', company);
console.log('New URL:', url);
console.log('All input items:', $input.all().length);

// ============================================
// КРОК 2: Отримуємо існуючі рядки з Google Sheets
// ============================================
// Get Existing Data передає всі рядки як input 1, 2, 3, ...
const existingRows = [];

// Проходимо по всіх input крім першого (перший - це нові дані)
const allInputs = $input.all();
for (let i = 1; i < allInputs.length; i++) {
  const item = allInputs[i];
  // Перевіряємо чи це не пустий об'єкт
  if (item && item.json && Object.keys(item.json).length > 1) {
    existingRows.push(item.json);
  }
}

console.log('Existing rows found:', existingRows.length);

// ============================================
// КРОК 3: Шукаємо компанію в існуючих рядах
// ============================================
let foundRow = null;
let rowIndex = -1;

// Нормалізуємо ключі пошуку для порівняння
const searchCompany = company.toString().toLowerCase().trim();
const searchUrl = url.toString().toLowerCase().trim();

for (let i = 0; i < existingRows.length; i++) {
  const row = existingRows[i];

  // Отримуємо назву компанії з різних можливих полів
  const rowCompany = (row['Компанія'] || row['Company'] || row['company'] || '').toString().toLowerCase().trim();
  const rowUrl = (row['URL'] || row['Url'] || row['url'] || '').toString().toLowerCase().trim();

  // Порівнюємо по назві АБО по URL
  if (rowCompany === searchCompany || rowUrl === searchUrl) {
    foundRow = row;
    rowIndex = i;
    console.log('Found existing company at index:', i);
    break;
  }
}

// ============================================
// КРОК 4: Формуємо результат з action типом
// ============================================
const result = {
  // Всі дані для запису в Google Sheets
  'Дата': newCompanyData['Дата'],
  'Компанія': company,
  'URL': url,
  'Нові фічі': newCompanyData['Нові фічі'],
  'Проблеми': newCompanyData['Проблеми'],
  'Інсайти з коментарів': newCompanyData['Інсайти з коментарів'],
  'Новини (з останньої перевірки)': newCompanyData['Новини (з останньої перевірки)'],
  'Статті в блозі (з останньої перевірки)': newCompanyData['Статті в блозі (з останньої перевірки)'],
  'YouTube активність': newCompanyData['YouTube активність'],
  'Facebook активність': newCompanyData['Facebook активність'],
  'LinkedIn активність': newCompanyData['LinkedIn активність'],
  'Згадки на агрегаторах': newCompanyData['Згадки на агрегаторах'],
  'Кількість згадок в соцмережах': newCompanyData['Кількість згадок в соцмережах'],
  'Болі клієнтів з коментарів': newCompanyData['Болі клієнтів з коментарів'],
  'Хотілки клієнтів з коментарів': newCompanyData['Хотілки клієнтів з коментарів'],
  'AI Summary': newCompanyData['AI Summary'],

  // === CONTROL FIELDS ===
  // Для IF ноди - який тип операції
  '_action': foundRow ? 'update' : 'append',

  // Для Update ноди - ідентифікатор рядка
  '_rowId': foundRow?.id || foundRow?.rowNumber || (rowIndex >= 0 ? rowIndex + 2 : null),

  // Для відладки
  '_isUpdate': !!foundRow,
  '_matchInfo': foundRow ? {
    matchedBy: foundRow['Компанія']?.toLowerCase() === searchCompany ? 'name' : 'url',
    existingCompany: foundRow['Компанія'],
    existingUrl: foundRow['URL']
  } : null
};

console.log('Action:', result._action);
console.log('Row ID:', result._rowId);
console.log('============================');

return result;
