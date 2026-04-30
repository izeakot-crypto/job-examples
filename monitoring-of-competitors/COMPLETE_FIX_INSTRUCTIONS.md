# Повне виправлення workflow - Крок за кроком

## Проблема 1: AI Agent не підставляє значення (показує ${...} в Excel)

### Крок 1: Виправити AI Agent User Prompt

1. Відкрити workflow: https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7
2. Знайти node **AI Agent**
3. В полі **Text** (головне поле prompt):
   - **ВАЖЛИВО:** Переконайтеся що поле починається з символу `=`
   - Якщо немає `=` на початку - додайте його
   - Замініть весь текст на вміст з файлу `AI_AGENT_USER_PROMPT_EXPRESSION.txt`
   - Переконайтеся що **${** замінилися на **{{** (n8n expression syntax)

**Правильний формат:**
```
=КОНКУРЕНТНА РОЗВІДКА

Дата аналізу: {{ new Date().toISOString().split('T')[0] }}
Компанія: {{ $input.all()[0].json.company }}
...
```

**НЕправильний формат (так було):**
```
КОНКУРЕНТНА РОЗВІДКА

Дата аналізу: ${new Date().toISOString().split('T')[0]}
Компанія: ${$input.all()[0].json.company}
...
```

### Крок 2: Виправити Parse AI JSON Response1

1. Знайти node **Parse AI JSON Response1**
2. Замінити JavaScript код на вміст з файлу: `PARSE_AI_JSON_SIMPLE.js`
3. Натиснути Save

---

## Проблема 2: Додати логіку update/insert для Google Sheets

### Варіант A: Простий (завжди append)

Якщо вас влаштовує що кожен запуск додає новий рядок (можна потім видалити дублікати вручну), то нічого не треба міняти.

### Варіант B: Складніший (update існуючих записів)

Потрібно додати логіку перевірки:

#### Крок 1: Додати node "Get All Rows from Sheets" ПЕРЕД Save to Sheets1

1. Після node **Format for Sheets1** додати новий node **Google Sheets**
2. Назвати його **Get All Rows from Sheets**
3. Налаштування:
   - Operation: **Read**
   - Document: той самий що в Save to Sheets1
   - Sheet: той самий
   - Return All: **true**

#### Крок 2: Додати Code node "Check if Exists"

1. Після **Get All Rows from Sheets** додати **Code** node
2. Назвати його **Check if Exists**
3. Вставити код з файлу: `CHECK_AND_UPSERT_LOGIC.js`

#### Крок 3: Додати IF node

1. Після **Check if Exists** додати **IF** node
2. Умова: `{{ $json._meta.action }}` equals `append`
3. True гілка → Save to Sheets1 (append)
4. False гілка → Google Sheets node з operation **Update** (update існуючий рядок)

#### Крок 4: Додати Update node

1. Створити новий **Google Sheets** node для False гілки
2. Назвати **Update Existing Row**
3. Налаштування:
   - Operation: **Update**
   - Document: той самий
   - Sheet: той самий
   - Row Number: `={{ $json._meta.rowNumber }}`
   - Columns: такі самі як в Save to Sheets1

---

## Проблема 3: Назви компаній показують "відсутній", "не вказано"

Це означає що Parse All Data1 не може знайти company та url.

### Виправлення:

1. Перевірте що в Google Sheets є колонки **company** та **url** (або **Company**, **URL**)
2. Відкрийте node **Parse All Data1**
3. Знайдіть рядки:
```javascript
const company = loopData.company || loopData.name || loopData['Компанія'] || loopData['Company'] || 'Unknown';
const url = loopData.url || loopData.URL || loopData.link || '';
```

4. Додайте до списку назву вашої колонки, наприклад:
```javascript
const company = loopData.company || loopData.name || loopData['Компанія'] || loopData['Company'] || loopData['Назва'] || 'Unknown';
const url = loopData.url || loopData.URL || loopData.link || loopData['Website'] || '';
```

---

## Після виправлення:

1. Натисніть **Save** в workflow (Ctrl+S)
2. Запустіть **Execute workflow** на ОДНІЙ компанії (test mode)
3. Перевірте output кожного node:
   - **AI Agent** → має повернути JSON з company, url, youtubeActivity, etc.
   - **Parse AI JSON Response1** → має розпарсити JSON і повернути об'єкт з усіма полями
   - **Format for Sheets1** → має створити 16 колонок з РЕАЛЬНИМИ значеннями (не ${...})

---

## Troubleshooting:

### Якщо AI Agent все ще показує ${...}:

1. Поле **Text** має починатися з `=`
2. Використовуйте `{{ }}` замість `${ }`
3. Refresh сторінку n8n після збереження

### Якщо Parse AI JSON падає з "content is not defined":

1. Переконайтеся що ви використовуєте `PARSE_AI_JSON_SIMPLE.js`
2. Змінна `rawContent` має бути оголошена на початку (рядок 5)

### Якщо компанія показує "відсутній":

1. Подивіться output node **Get row(s) in sheet**
2. Які назви колонок в JSON?
3. Додайте ці назви в Parse All Data1 код

---

**Час виконання:** 10-15 хвилин

**Результат:**
- ✅ AI Agent підставляє реальні значення
- ✅ Parse AI JSON Response1 працює без помилок
- ✅ В Google Sheets записуються правильні дані з назвами компаній
- ✅ (опціонально) Оновлюються існуючі записи замість дублювання
