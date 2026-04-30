# Кроки для реструктуризації Workflow

## Проблема
Format for Sheets1 не може отримати дані з паралельних гілок через paired items error.

## Рішення
Додати Merge2 node який об'єднає всі 4 потоки даних перед Format for Sheets1.

## Кроки виконання (через n8n UI)

### Крок 1: Додати Merge2 node
1. Відкрити workflow: https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7
2. Додати новий node типу **Merge** (назвати "Merge2")
3. Встановити **Number of Inputs** = 4
4. Розмістити node приблизно на позиції [2368, -400] (між AI агентом та Format for Sheets1)

### Крок 2: Перепідключити вхідні з'єднання до Merge2
Видалити старі з'єднання та створити нові:

**Вхід 1 (Input 1) в Merge2:**
- З'єднати: Parse AI JSON Response1 → Merge2 (Input 1)

**Вхід 2 (Input 2) в Merge2:**
- З'єднати: Parse YouTube Data1 → Merge2 (Input 2)

**Вхід 3 (Input 3) в Merge2:**
- З'єднати: Format Social Activity1 → Merge2 (Input 3)

**Вхід 4 (Input 4) в Merge2:**
- З'єднати: Merge Aggregator Data → Merge2 (Input 4)

### Крок 3: Перепідключити вихідне з'єднання від Merge2
- Видалити з'єднання: Parse AI JSON Response1 → Format for Sheets1
- Створити нове: Merge2 → Format for Sheets1

### Крок 4: Оновити код Format for Sheets1 node

Відкрити node **Format for Sheets1** та замінити весь код на:

```javascript
// Format for Sheets - reads from Merge2 output
// Merge2 combines: [0]=Parse AI JSON Response1, [1]=Parse YouTube Data1, [2]=Format Social Activity1, [3]=Merge Aggregator Data

const allData = $input.all();

// Get AI analysis from index 0
const aiAnalysis = allData[0]?.json?.aiAnalysis || {};

// Get YouTube from index 1
const youtubeActivity = allData[1]?.json?.youtubeActivity || '-';

// Get Social from index 2
const linkedinActivity = allData[2]?.json?.linkedinActivity || '-';
const facebookActivity = allData[2]?.json?.facebookActivity || '-';

// Get G2 from index 3
const aggregatorMentions = allData[3]?.json?.aggregatorMentions || '-';

// Get company and URL from Loop (still accessible from execution context)
const loopData = $('Loop Companies1').item.json;
const company = loopData.company || loopData.name || loopData['Компанія'] || loopData['Company'] || 'Unknown';
const url = loopData.url || loopData.URL || loopData.link || '';

// Helper: convert array to comma-separated string
const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return '-';
  if (arr.length === 0) return '-';
  return arr.join(', ');
};

// Helper: convert blog articles to readable string
const blogToString = (articles) => {
  if (!Array.isArray(articles)) return '-';
  if (articles.length === 0) return '-';
  return articles.map(a =>
    `${a.title || 'Без назви'} (${a.date || 'дата невідома'}): ${(a.summary || '').substring(0, 100)}...`
  ).join(' | ');
};

// Create 16-column row
return {
  'Дата': new Date().toISOString().split('T')[0],
  'Компанія': company,
  'URL': url,
  'Нові фічі': arrayToString(aiAnalysis.newFeatures),
  'Проблеми': arrayToString(aiAnalysis.problems),
  'Інсайти з коментарів': aiAnalysis.reviewInsights || '-',
  'Новини (з останньої перевірки)': arrayToString(aiAnalysis.news),
  'Статті в блозі (з останньої перевірки)': blogToString(aiAnalysis.blogArticles),
  'YouTube активність': youtubeActivity,
  'Facebook активність': facebookActivity,
  'LinkedIn активність': linkedinActivity,
  'Згадки на агрегаторах': aggregatorMentions,
  'Кількість згадок в соцмережах': '0',
  'Болі клієнтів з коментарів': arrayToString(aiAnalysis.customerPains),
  'Хотілки клієнтів з коментарів': arrayToString(aiAnalysis.customerWants),
  'AI Summary': aiAnalysis.summary || '-'
};
```

### Крок 5: Зберегти та протестувати
1. Натиснути **Save** в workflow
2. Запустити тест на одній компанії
3. Перевірити що всі 16 колонок заповнюються правильно

## Що змінилось?

### Стара структура (з paired items помилками):
```
Parse AI JSON Response1 ──→ Format for Sheets1
Parse YouTube Data1 ────────(намагається отримати через $('NodeName'))
Format Social Activity1 ───(намагається отримати через $('NodeName'))
Merge Aggregator Data ─────(намагається отримати через $('NodeName'))
```

### Нова структура (без paired items):
```
Parse AI JSON Response1 ──┐
Parse YouTube Data1 ──────┤
Format Social Activity1 ──┼──→ Merge2 ──→ Format for Sheets1
Merge Aggregator Data ────┘
```

### Зміни в коді Format for Sheets1:

**Старий спосіб (НЕ ПРАЦЮЄ):**
```javascript
const aiAnalysis = $('Parse AI JSON Response1').item.json.aiAnalysis || {};
const youtubeActivity = $('Parse YouTube Data1').item.json.youtubeActivity || '-';
// ... etc - викликає paired items error
```

**Новий спосіб (ПРАЦЮЄ):**
```javascript
const allData = $input.all();
const aiAnalysis = allData[0]?.json?.aiAnalysis || {};
const youtubeActivity = allData[1]?.json?.youtubeActivity || '-';
// ... etc - читає з Merge2 за індексами
```

## Чому це працює?

1. **Merge2 створює один потік даних** з усіх 4 джерел
2. **$input.all()** повертає масив з усіма вхідними items від Merge2
3. **Індекси чіткі та передбачувані**:
   - [0] = Parse AI JSON Response1
   - [1] = Parse YouTube Data1
   - [2] = Format Social Activity1
   - [3] = Merge Aggregator Data
4. **Не потрібно paired items chain** - всі дані вже в одному merged stream

## Переваги нової архітектури

✅ Уникає paired items помилок
✅ Чітка структура даних через індекси
✅ Легше дебажити - всі дані в одному місці
✅ Масштабується - легко додати ще джерела даних
✅ Код простіший та надійніший

---

**Час виконання:** 5-7 хвилин через UI

**Альтернатива:** Програмно оновити через API, але n8n MCP API не дозволяє часткове оновлення - треба відправляти весь workflow JSON.
