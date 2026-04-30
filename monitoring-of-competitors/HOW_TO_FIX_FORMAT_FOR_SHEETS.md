# ВИПРАВЛЕННЯ FORMAT FOR SHEETS - ІНСТРУКЦІЯ

Проблема: API N8n вимагає повний workflow для оновлення, тому неможливо оновити одну ноду через API.
Рішення: Виправити вручну через UI N8n.

---

## КРОК 1: Відкрити workflow

1. Перейдіть на: https://n8nletsdo.online/workflow/w5Pn8RXfEteblgbC
2. Натисніть **Edit** або відкрийте workflow для редагування

---

## КРОК 2: Виправити Format for Sheets

1. Знайдіть ноду **Format for Sheets** (позиція [2944, -416])
2. Натисніть на неї двічі для відкриття
3. Перейдіть на вкладку **Parameters** або **Code**
4. Замініть весь код на наступний:

```javascript
// Format for Sheets - PASS THROUGH VERSION
const data = $input.item.json;
const ai = data.aiAnalysis || {};

const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return '-';
  if (arr.length === 0) return '-';
  return arr.join(', ');
};

const blogToString = (articles) => {
  if (!Array.isArray(articles)) return '-';
  if (articles.length === 0) return '-';
  return articles.map(a =>
    `${a.title || '?'} (${a.date || 'дата невідома'}): ${(a.summary || '').substring(0, 100)}...`
  ).join(' | ');
};

const result = {
  'Дата': new Date().toISOString().split('T')[0],
  'Компанія': data.company || 'Unknown',
  'URL': data.url || '',
  'Нові фічі': arrayToString(ai.newFeatures),
  'Проблеми': arrayToString(ai.problems),
  'Інсайти з коментарів': ai.reviewInsights || '-',
  'Новини (з останньої перевірки)': arrayToString(ai.news),
  'Статті в блозі (з останньої перевірки)': blogToString(ai.blogArticles),
  'YouTube активність': data.youtubeActivity || '-',
  'Facebook активність': data.facebookActivity || '-',
  'LinkedIn активність': data.linkedinActivity || '-',
  'Згадки на агрегаторах': data.aggregatorMentions || '-',
  'Кількість згадок в соцмережах': String(data.socialMentionsCount || 0),
  'Болі клієнтів з коментарів': arrayToString(ai.customerPains),
  'Хотілки клієнтів з коментарів': arrayToString(ai.customerWants),
  'AI Summary': ai.summary || '-',
  _originalData: { company: data.company, url: data.url, aiAnalysis: ai, parsedAt: data.parsedAt },
  _isNewData: true,
  _searchKey: { company: (data.company || '').toLowerCase().trim(), url: (data.url || '').toLowerCase().trim() }
};

console.log('Format for Sheets - Company:', result['Компанія']);
return result;
```

5. Натисніть **Done** або **Save**

---

## КРОК 3: Виправити Merge2

Поточна проблема: Format for Sheets підключений до двох місць:
- Output 0 → Get Existing Data
- Output 1 → Merge2

Це неправильно! Правильна схема:

```
Format for Sheets ──────┐
                          ├──> Merge2 ───> Check If Company Exists
Get Existing Data ────────┘
```

### Як виправити:

1. Видаліть існуючий з'єднання:
   - Натисніть на лінію між Format for Sheets та Get Existing Data
   - Натисніть Delete

2. Створіть правильне з'єднання:
   - Натисніть на точку виходу Format for Sheets
   - Перетягніте до вхідної точки Merge2 (input 1)

3. Перевірте, що Get Existing Data підключений до Merge2 (input 0)

4. Натисніть на Merge2 і перевірте налаштування:
   - **Mode**: Merge by Index
   - **Inputs**: 2

---

## КРОК 4: Перевірити Check If Company Exists

1. Відкрийте ноду **Check If Company Exists**
2. Переконайтеся, що код правильно читає з Merge2:

```javascript
// Check If Company Exists - FIX
var allInputs = $input.all();

// Перший item - дані з Format for Sheets
var formattedData = allInputs[0] ? allInputs[0].json : {};
var company = formattedData['Компанія'] || '';
var url = formattedData['URL'] || '';

console.log('Check If Company Exists - Company:', company, 'URL:', url, 'Total inputs:', allInputs.length);

// Інші items - дані з Get Existing Data
var existingRows = [];
for (var i = 1; i < allInputs.length; i++) {
  if (allInputs[i] && allInputs[i].json && Object.keys(allInputs[i].json).length > 0) {
    existingRows.push(allInputs[i]);
  }
}

console.log('Existing rows count:', existingRows.length);

var exists = false;
for (var j = 0; j < existingRows.length; j++) {
  var row = existingRows[j].json;
  if (!row || Object.keys(row).length === 0) continue;

  var rowCompany = (row['Компанія'] || '').toLowerCase().trim();
  var rowUrl = (row['URL'] || '').toLowerCase().trim();
  if (company && rowCompany === company.toLowerCase().trim()) {
    exists = true;
    break;
  }
  if (url && rowUrl === url.toLowerCase().trim()) {
    exists = true;
    break;
  }
}

console.log('Company exists:', exists);

var result = {};
for (var key in formattedData) { result[key] = formattedData[key]; }
result._action = exists ? 'update' : 'append';
result.isNewEntry = !exists;
return result;
```

---

## КРОК 5: Зберегти і протестувати

1. Натисніть **Save** workflow
2. Запустіть тест на 1 компанії:
   - Натисніть **Execute Workflow**
   - Дивіться на output кожної ноди

---

## ОЧІКУВАНІ РЕЗУЛЬТАТИ

### Format for Sheets:
Має повертати 16 колонок + `_originalData`, `_isNewData`, `_searchKey`

### Merge2:
Має об'єднувати 2 джерела:
- Input 0: Get Existing Data (всі рядки з Google Sheets)
- Input 1: Format for Sheets (нові дані компанії)

### Check If Company Exists:
Має повертати `_action: 'update'` або `_action: 'append'`

---

## ЯКЩО ЩО НЕ ПРАЦЮЄ

### Debug в Format for Sheets:
Додайте console.log на початку:
```javascript
console.log('Input data:', JSON.stringify($input.item.json));
```

### Debug в Check If Company Exists:
Перевірте скільки input приходить:
```javascript
console.log('Total inputs from Merge2:', $input.all().length);
```

### Якщо Merge2 не працює:
Спробуйте замінити його на Code node "Manual Merge":

```javascript
// Manual Merge - замість Merge2 ноди
// Input 0: Get Existing Data (можливо порожній)
// Input 1: Format for Sheets (нові дані)

const formatData = $input.item.json;
const existingData = $('Get Existing Data').all();

// Об'єднуємо для Check If Company Exists
return [
  { json: formatData },
  ...existingData
];
```

---

## ПІДСУМОК

Основна проблема була в тому, що Format for Sheets не передавав дані правильним чином через Merge2 до Check If Company Exists.
Виправлення:
1. Format for Sheets - додав pass-through поля
2. Merge2 - правильне підключення (2 inputs)
3. Check If Company Exists - правильне читання з $input.all()
