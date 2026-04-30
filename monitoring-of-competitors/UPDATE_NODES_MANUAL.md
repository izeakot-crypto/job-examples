# Manual Node Update Instructions

## Problem
After the "Format for Sheets" node, data is lost when passing through Merge5 to "Check If Company Exists".

## Solution
Update "Format for Sheets3" node code to include `_originalData` and `_isNewData` fields.

## Workflow URL
https://n8nletsdo.online/workflow/w5Pn8RXfEteblgbC

---

## Node 1: Format for Sheets3 (ID: 79d14816-a09a-464e-91fb-a365e6e252b1)

### Steps:
1. Open workflow in N8n editor
2. Find node "Format for Sheets3"
3. Click "Edit Code"
4. Replace ALL code with:

```javascript
// Format for Sheets - PASS THROUGH VERSION
const data = $input.item.json;
const ai = data.aiAnalysis || {};

const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return "-";
  if (arr.length === 0) return "-";
  return arr.join(", ");
};

const blogToString = (articles) => {
  if (!Array.isArray(articles)) return "-";
  if (articles.length === 0) return "-";
  return articles.map(a => a.title + " (" + (a.date || "?") + "): " + (a.summary || "").substring(0, 100) + "...").join(" | ");
};

const result = {
  "Дата": new Date().toISOString().split("T")[0],
  "Компанія": data.company || "Unknown",
  "URL": data.url || "",
  "Нові фічі": arrayToString(ai.newFeatures),
  "Проблеми": arrayToString(ai.problems),
  "Інсайти з коментарів": ai.reviewInsights || "-",
  "Новини (з останньої перевірки)": arrayToString(ai.news),
  "Статті в блозі (з останньої перевірки)": blogToString(ai.blogArticles),
  "YouTube активність": data.youtubeActivity || "-",
  "Facebook активність": data.facebookActivity || "-",
  "LinkedIn активність": data.linkedinActivity || "-",
  "Згадки на агрегаторах": data.aggregatorMentions || "-",
  "Кількість згадок в соцмережах": String(data.socialMentionsCount || 0),
  "Болі клієнтів з коментарів": arrayToString(ai.customerPains),
  "Хотілки клієнтів з коментарів": arrayToString(ai.customerWants),
  "AI Summary": ai.summary || "-",
  _originalData: { company: data.company, url: data.url, parsedAt: data.parsedAt },
  _isNewData: true
};

console.log("Format for Sheets - Company:", result["Компанія"]);
return result;
```

### Key Changes Added:
- `_originalData: { company: data.company, url: data.url, parsedAt: data.parsedAt }`
- `_isNewData: true`

---

## Node 2: Check If Company Exists1 (ID: 66310e8c-9b80-4e44-b090-35885fdbde7a)

### Current Code Check:
The existing code may already be updated. Verify it contains:
- `_action` field
- `_rowId` field
- `_isUpdate` field
- `_matchInfo` field

If NOT, replace with:

```javascript
// Check If Company Exists - FIXED VERSION
const allInputs = $input.all();

// Input 0 - дані з Format for Sheets (нові дані)
const newCompanyData = allInputs[0].json;

const company = newCompanyData['Компанія'] || newCompanyData._originalData?.company || 'Unknown';
const url = newCompanyData['URL'] || newCompanyData._originalData?.url || '';

console.log('=== CHECK IF COMPANY EXISTS ===');
console.log('New company:', company);
console.log('New URL:', url);
console.log('All input items:', allInputs.length);

// Get Existing Data передає всі рядки як input 1, 2, 3, ...
const existingRows = [];

// Проходимо по всіх input крім першого (перший - це нові дані)
for (let i = 1; i < allInputs.length; i++) {
  const item = allInputs[i];
  // Перевіряємо чи це не пустий об'єкт
  if (item && item.json && Object.keys(item.json).length > 1) {
    existingRows.push(item.json);
  }
}

console.log('Existing rows found:', existingRows.length);

// Шукаємо компанію в існуючих рядах
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

// Формуємо результат з action типом
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
```

---

## Verify Connections

After updating code, verify Merge5 connections:
- **Input 1** → Get Existing Data1
- **Input 2** → Format for Sheets3

Flow should be:
```
Format for Sheets3 → (Input 2) Merge5 (Input 1) ← Get Existing Data1
                                    ↓
                        Check If Company Exists1
                                    ↓
                             IF Company Exists1
                              ↓             ↓
                        Update Existing   Append New
```

---

## Save and Test

1. Save workflow (Ctrl+S)
2. Execute test run
3. Check console logs for:
   - "Format for Sheets - Company: XXX"
   - "CHECK IF COMPANY EXISTS"
   - "Action: update" or "Action: append"
