# ПОВНЕ ВИПРАВЛЕННЯ WORKFLOW - ОСТАТОЧНА ІНСТРУКЦІЯ

## Проблеми які виправляємо:

1. ❌ **Fetch Website не працює** - сайти блокують запити без User-Agent
2. ❌ **Parse All Data ставить URL в поле company** замість назви
3. ❌ **AI Agent показує `${...}` замість реальних значень** - неправильний синтаксис
4. ❌ **Всі дані NULL/порожні** - погане парсинг HTML
5. ❌ **Дублікати в Google Sheets** - немає логіки update/insert

---

## КРОК 1: Виправити HTTP запити (3 nodes)

### 1.1 Fetch Website1

1. Відкрити https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7
2. Знайти node **Fetch Website1**
3. Натиснути на node → вкладка **Parameters**
4. **Headers** секція:
   - Натиснути **Add Header**
   - Name: `User-Agent`
   - Value: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`
   - Натиснути **Add Header** ще раз
   - Name: `Accept`
   - Value: `text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8`
   - Натиснути **Add Header** третій раз
   - Name: `Accept-Language`
   - Value: `en-US,en;q=0.9`
5. **Options** → **Redirect** → **Follow Redirects**: `true`
6. **Options** → **Response** → **Never Error**: `true`
7. **Options** → **Timeout**: `30000`

### 1.2 Fetch Blog1

Повторити ті ж самі кроки для **Fetch Blog1**

### 1.3 Fetch Reviews1

Повторити ті ж самі кроки для **Fetch Reviews1**

---

## КРОК 2: Виправити Parse All Data1

### Оновити JavaScript код:

1. Знайти node **Parse All Data1**
2. Видалити весь існуючий код
3. Відкрити файл: `[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\PARSE_ALL_DATA_ULTIMATE.js`
4. Скопіювати весь код
5. Вставити в node **Parse All Data1**
6. Натиснути **Save**

**Що робить новий код:**
- Перевіряє 10+ варіантів назв колонок для company/URL
- Автоматично міняє місцями якщо company містить URL
- Витягує domain name як назву компанії (netelip.com → "Netelip")
- Парсить HTML з множинними fallback patterns
- Витягує title, description, h1 tags, paragraphs
- Знаходить blog articles та reviews
- Логує все в консоль для debugging

---

## КРОК 3: Виправити AI Agent User Prompt

### Замінити синтаксис з ${...} на {{ ... }}

1. Знайти node **AI Agent**
2. Відкрити вкладку **Chat**
3. В полі **Text** (User Prompt):
   - **ВИДАЛИТИ весь текст повністю**
4. Відкрити файл: `[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\AI_AGENT_USER_PROMPT_FIXED.txt`
5. Скопіювати весь вміст
6. Вставити в поле **Text**
7. **ОБОВ'ЯЗКОВО додати `=` на початку поля** (якщо його немає)
   - Поле має починатися з: `=КОНКУРЕНТНА РОЗВІДКА`
8. Натиснути **Save**

**Критично важливо:**
- Синтаксис `{{ ... }}` - n8n expressions (правильно)
- Синтаксис `${ ... }` - JavaScript templates (НЕправильно для n8n)

---

## КРОК 4: Виправити Parse AI JSON Response1

### Замінити на спрощену версію:

1. Знайти node **Parse AI JSON Response1**
2. Видалити весь існуючий код
3. Відкрити файл: `[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\PARSE_AI_JSON_SIMPLE.js`
4. Скопіювати весь код
5. Вставити в node **Parse AI JSON Response1**
6. Натиснути **Save**

**Що виправлено:**
- Всі змінні на верхньому рівні (scope fix)
- Немає optional chaining `?.` (compatibility)
- Простіші loops (no for...of)
- Кращий error handling з fallback data

---

## КРОК 5: Додати Update/Insert логіку для Google Sheets

### 5.1 Створити новий Code node

1. Після node **Format for Sheets1** створити новий **Code** node
2. Назвати його **Check Existing Record**
3. Вставити код з файлу: `[USER_HOME]\OneDrive\Work.Oki-toki\Monitoring of competitors\GOOGLE_SHEETS_UPDATE_LOGIC.js`

### 5.2 Додати Google Sheets Read node

1. Створити новий **Google Sheets** node
2. Назвати **Get row(s) in sheet**
3. Operation: **Get Many**
4. Document: той самий що Save to Sheets1
5. Sheet: той самий що Save to Sheets1
6. Return All: `true`
7. Підключити цей node ДО **Check Existing Record**

### 5.3 Створити розгалуження (IF node)

1. Після **Check Existing Record** створити **IF** node
2. Умова:
   - Value 1: `{{ $json.operation }}`
   - Operation: `Equal`
   - Value 2: `update`

### 5.4 Update branch

1. Якщо **true** (update):
   - Створити **Google Sheets** node
   - Operation: **Update**
   - Row ID: `={{ $json.rowId }}`
   - Data: `={{ $json.data }}`

### 5.5 Append branch

1. Якщо **false** (append):
   - Підключити до існуючого **Save to Sheets1**
   - Або створити новий з Operation: **Append**

---

## КРОК 6: Тестування

### Запустити workflow на 1 компанії:

1. Натиснути **Execute Workflow**
2. Перевірити output кожного node:

**✅ Get row(s) in sheet:**
- Має повернути рядки з Google Sheets
- Перевірити назви колонок: `company`, `url`, `Компанія`, `URL`, etc.

**✅ Parse All Data1:**
```json
{
  "company": "Netelip",  // ← НЕ URL!
  "url": "https://www.netelip.com/en/",  // ← НЕ порожній!
  "currentData": {
    "website": {
      "title": "Netelip - VoIP Solutions",  // ← НЕ null!
      "description": "...",
      "h1Tags": ["Cloud Contact Center", ...],
      "hasNews": true,
      "hasBlog": true
    }
  }
}
```

**✅ Fetch Website1:**
- `statusCode: 200`
- `body` містить HTML (довжина > 10000 symbols)
- Перевірити console logs: "Website HTML length: 45231"

**✅ AI Agent:**
- Output містить JSON
- **НЕ** містить `${...}` expressions
- Містить реальні значення:
```json
{
  "company": "Netelip",
  "url": "https://www.netelip.com/en/",
  "newFeatures": ["AI-powered routing", "WhatsApp integration"],
  "summary": "Netelip is a leading..."
}
```

**✅ Parse AI JSON Response1:**
- Немає помилок "content is not defined"
- Правильний JSON parsing
- Всі 14 полів присутні

**✅ Format for Sheets1:**
```json
{
  "Дата": "2025-01-18",
  "Компанія": "Netelip",  // ← НЕ "відсутній"!
  "URL": "https://www.netelip.com/en/",
  "Нові фічі": "AI-powered routing, WhatsApp integration",  // ← НЕ "${...}"!
  ...
}
```

**✅ Check Existing Record:**
- Повертає `operation: "update"` або `operation: "append"`
- Логує в консоль: "Found existing record at row: 5" або "Creating new record"

**✅ Save to Sheets1:**
- Запис з'являється в Google Sheets
- Всі колонки заповнені реальними даними
- Якщо компанія вже була - рядок оновлюється, не дублюється

---

## КРОК 7: Запустити на всіх компаніях

1. Після успішного тесту на 1 компанії
2. Activate workflow
3. Або запустити Execute workflow з loop на всі рядки

---

## Troubleshooting

### Якщо Fetch Website повертає пустий body:

```javascript
// В консолі node Parse All Data1:
console.log('Website HTML length:', websiteHtml.length);
```

- Якщо `0` - перевірте чи додали User-Agent header
- Якщо `< 1000` - можливо redirects не працюють

### Якщо company все ще містить URL:

```javascript
// В консолі node Parse All Data1:
console.log('Loop data keys:', Object.keys(loopData));
console.log('Extracted company:', company);
console.log('Extracted URL:', url);
```

- Подивіться які назви колонок в `Loop data keys`
- Додайте ці назви в код PARSE_ALL_DATA_ULTIMATE.js рядок 12-14

### Якщо AI Agent показує `${...}`:

1. Перевірте чи поле Text починається з `=`
2. Перевірте чи всі `${` замінені на `{{`
3. Перевірте чи всі `}` замінені на `}}`
4. Refresh сторінку n8n після Save

### Якщо Parse AI JSON падає:

```javascript
// В консолі Parse AI JSON Response1:
console.log('Raw content:', rawContent);
```

- Перевірте чи AI Agent повертає valid JSON
- Чи немає markdown блоків ```json ... ```
- Чи всі поля присутні

### Якщо дублікати все ще створюються:

1. Перевірте чи node "Get row(s) in sheet" підключений
2. Перевірте чи Return All: true
3. Перевірте console logs в Check Existing Record
4. Можливо назва компанії змінилася (Netelip → netelip)
   - Додайте `.toLowerCase()` в comparison:
   ```javascript
   if (row['Компанія'].toLowerCase() === company.toLowerCase() || ...)
   ```

---

## Очікуваний результат:

### В Google Sheets:

| Дата | Компанія | URL | Нові фічі | Проблеми | YouTube | LinkedIn | Facebook | G2 | Відгуки клієнтів | Новини | Blog статті | Customer Pains | Customer Wants | Висновки |
|------|----------|-----|-----------|----------|---------|----------|----------|----|--------------------|--------|-------------|----------------|----------------|----------|
| 2025-01-18 | Netelip | https://www.netelip.com/en/ | AI routing, WhatsApp | Legacy integration challenges | Active - 12 videos | 450+ followers | 2.3K likes | 4.2/5 (89 reviews) | Positive feedback on ease of use, some concerns about pricing | Launched new AI features Q4 2024 | 3 articles: AI in Contact Centers, Remote Work Solutions, Customer Experience Trends | High setup complexity, limited integrations | Better analytics, mobile app improvements | Strong digital presence, active content strategy, competitive G2 rating. Weakness: limited social proof compared to market leaders |

### В n8n execution logs:

```
✅ Extracted company: Netelip
✅ Extracted URL: https://www.netelip.com/en/
✅ Website HTML length: 45231
✅ Found 3 blog articles
✅ Found 5 reviews
✅ AI Agent returned valid JSON
✅ All 14 fields present
✅ Found existing record at row: 5
✅ Updating existing record for Netelip
```

---

## Час виконання всіх кроків: 15-20 хвилин

**Файли для виправлення:**
1. `PARSE_ALL_DATA_ULTIMATE.js` - найповніший парсинг даних
2. `AI_AGENT_USER_PROMPT_FIXED.txt` - правильний n8n синтаксис
3. `PARSE_AI_JSON_SIMPLE.js` - без scope помилок
4. `GOOGLE_SHEETS_UPDATE_LOGIC.js` - логіка update/insert
5. `FETCH_WEBSITE_IMPROVED.json` - конфігурація з headers
6. `FETCH_BLOG_IMPROVED.json` - конфігурація з headers
7. `FETCH_REVIEWS_IMPROVED.json` - конфігурація з headers

Після виправлення workflow буде **повністю автоматично**:
- ✅ Витягувати правильні назви компаній
- ✅ Збирати весь HTML з сайтів
- ✅ Парсити blog, reviews, metadata
- ✅ AI аналіз з реальними даними
- ✅ Записувати в Google Sheets БЕЗ дублікатів
- ✅ Всі 16 колонок заповнені правильними даними

