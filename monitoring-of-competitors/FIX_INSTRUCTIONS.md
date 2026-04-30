# Інструкції для виправлення Paired Items Error

## Проблема
Parse AI JSON Response1 падає з помилкою:
```
Cannot assign to read only property 'name' of object 'Error: Paired item data for item from node 'Parse All Data1' is unavailable.
```

## Причина
Parse AI JSON Response1 намагається отримати `company` та `url` через `$('Loop Companies1').item.json`, але paired items chain розірваний через складну структуру: Merge → Parse All Data1 → Merge1 → AI Agent → Parse AI JSON Response1.

## Рішення
AI Agent має повертати ВСЕ в одному JSON (включаючи company, url, youtube, social, g2 дані), щоб Parse AI JSON Response1 міг просто прочитати їх з AI output БЕЗ доступу до інших nodes.

---

## Кроки виправлення (через n8n UI)

### Крок 1: Оновити AI Agent System Prompt

1. Відкрити workflow: https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7
2. Знайти node **AI Agent**
3. В полі **System Message** (в Options секції):
   - Видалити весь текст
   - Скопіювати та вставити вміст з файлу: `AI_AGENT_SYSTEM_PROMPT_FINAL.txt`
   - Переконатися що в форматі є ВСІ поля: company, url, youtubeActivity, linkedinActivity, facebookActivity, aggregatorMentions + аналітичні поля

### Крок 2: Оновити AI Agent User Prompt

1. В тому ж node **AI Agent**
2. В полі **Text** (основне поле):
   - Видалити весь текст
   - Скопіювати та вставити вміст з файлу: `AI_AGENT_USER_PROMPT_FINAL.txt`
   - Переконатися що в кінці є КРИТИЧНО ВАЖЛИВО секція з переліком полів для JSON

### Крок 3: Оновити Parse AI JSON Response1

1. Знайти node **Parse AI JSON Response1**
2. В поле **JavaScript Code**:
   - Видалити весь код
   - Скопіювати та вставити вміст з файлу: `PARSE_AI_JSON_FINAL_FIX.js`
   - Ключові зміни:
     - Додано видалення markdown блоків: `.replace(/\`\`\`json\\n?/g, '').replace(/\`\`\`\\n?/g, '')`
     - Валідація 14 полів (включаючи company, url, youtube, social, g2)
     - Повертає ВСЕ з parsedData БЕЗ доступу до Loop або інших nodes

### Крок 4: Оновити Format for Sheets1

1. Знайти node **Format for Sheets1**
2. В поле **JavaScript Code**:
   - Видалити весь код
   - Скопіювати та вставити вміст з файлу: `FORMAT_FOR_SHEETS_FINAL_FIX.js`
   - Ключові зміни:
     - Читає ВСІ дані тільки з `$input.item.json` (від Parse AI JSON Response1)
     - Більше НІЯКОГО доступу через `$items()` або `$('NodeName')`
     - Простий та надійний код

### Крок 5: Зберегти та протестувати

1. Натиснути **Save** в workflow (Ctrl+S)
2. Запустити **Execute workflow** на одній компанії (test mode)
3. Перевірити чи:
   - AI Agent успішно виконався
   - Parse AI JSON Response1 успішно виконався (БЕЗ paired items помилки!)
   - Format for Sheets1 створив 16 колонок з даними
   - Save to Sheets1 записав дані в Google Sheets

---

## Що змінилось в архітектурі?

### Стара логіка (з paired items помилками):
```
AI Agent → Parse AI JSON Response1 (намагається отримати company/url з Loop) ❌
                                  ↓
                       Format for Sheets1 (намагається отримати youtube/social/g2 через $items())
```

### Нова логіка (БЕЗ paired items):
```
AI Agent (повертає ВСЕ в JSON: company, url, youtube, social, g2, analysis)
    ↓
Parse AI JSON Response1 (просто парсить JSON, все вже є в output)
    ↓
Format for Sheets1 (читає ВСЕ з $input.item.json)
```

---

## Переваги нового підходу

✅ **Повністю уникає paired items помилок** - Parse AI JSON Response1 не звертається до інших nodes
✅ **AI Agent як single source of truth** - всі дані в одному JSON
✅ **Простіша структура даних** - linear flow без складних paired items chains
✅ **Легше дебажити** - AI JSON містить ВСЕ, можна просто подивитись output AI Agent
✅ **Надійніше** - менше точок відмови, немає залежності від paired items mechanism

---

## Якщо все ще виникають помилки:

1. **AI повертає markdown блоки** (`\`\`\`json ... \`\`\``):
   - Parse AI JSON Response1 вже має код для їх видалення
   - Перевірте в execution output AI Agent чи він повертає чистий JSON

2. **AI не повертає якесь поле**:
   - Перевірте execution output AI Agent
   - Додайте console.error в Parse AI JSON Response1 для debug

3. **Format for Sheets1 не знаходить дані**:
   - Перевірте що Parse AI JSON Response1 успішно виконався
   - Подивіться його output - там має бути об'єкт з полями: company, url, youtubeActivity, linkedinActivity, facebookActivity, aggregatorMentions, aiAnalysis

---

**Час виконання:** 5-7 хвилин через UI

**Результат:** Workflow працює БЕЗ paired items помилок!
