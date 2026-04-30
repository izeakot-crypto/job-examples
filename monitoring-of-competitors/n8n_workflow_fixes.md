# 🔧 Виправлення для Workflow "Monitoring of Competitors v2"

## 📋 Виявлені проблеми:

1. ❌ **Append New Row1** - падає з помилкою "Could not get parameter"
2. ⚠️ **AI Agent1** - працює 100 секунд (занадто повільно)
3. 📉 **Дані порожні** - більшість полів містять "-"

---

## 🛠️ Виправлення #1: Append New Row1 (КРИТИЧНО!)

**Проблема:** Mapping використовує `={{ $json['поле'] }}` без fallback. Якщо поле відсутнє → помилка.

**Рішення:** Додати `|| '-'` для всіх полів

### Кроки виправлення:
1. Відкрийте workflow в n8n
2. Знайдіть ноду **"Append New Row1"**
3. Відкрийте вкладку **"Columns to Send"** → **"Define Below"**
4. Замініть кожен mapping expression з fallback:

```javascript
// СТАРИЙ КОД (БЕЗ FALLBACK):
={{ $json['Дата'] }}
={{ $json['Компанія'] }}
={{ $json['URL'] }}

// НОВИЙ КОД (З FALLBACK):
={{ $json['Дата'] || new Date().toISOString().split('T')[0] }}
={{ $json['Компанія'] || 'Unknown' }}
={{ $json['URL'] || '-' }}
={{ $json['Нові фічі'] || '-' }}
={{ $json['Проблеми'] || '-' }}
={{ $json['Інсайти з коментарів'] || '-' }}
={{ $json['Новини (з останньої перевірки)'] || '-' }}
={{ $json['Статті в блозі (з останньої перевірки)'] || '-' }}
={{ $json['YouTube активність'] || '-' }}
={{ $json['Facebook активність'] || '-' }}
={{ $json['LinkedIn активність'] || '-' }}
={{ $json['Згадки на агрегаторах'] || '-' }}
={{ $json['Кількість згадок в соцмережах'] || '0' }}
={{ $json['Болі клієнтів з коментарів'] || '-' }}
={{ $json['Хотілки клієнтів з коментарів'] || '-' }}
={{ $json['AI Summary'] || '-' }}
={{ $json.isNewEntry || 'true' }}
```

---

## 🛠️ Виправлення #2: Update Existing Row1

**Те саме виправлення** - додати fallback для всіх полів:

```javascript
={{ $json['Дата'] || new Date().toISOString().split('T')[0] }}
={{ $json['Компанія'] || 'Unknown' }}
={{ $json['URL'] || '-' }}
// ... і так далі для всіх полів
```

---

## 🛠️ Виправлення #3: AI Agent1 - Оптимізація промпту

**Проблема:** Промпт занадто великий (100 секунд виконання)

**Рішення:** Спростити промпт, зменшити кількість template expressions

### Старий промпт (занадто великий):
```
КОНКУРЕНТНА РОЗВІДКА - АНАЛІЗ КОМПАНІЇ...
[Великий блок з багатьма template expressions]
```

### Новий промпт (оптимізований):

Замініть поле **"Text"** в ноді **AI Agent1** на:

```
Ти - Senior Business Analyst. Проаналізуй компанію і поверни ТІЛЬКИ valid JSON (без markdown блоків).

ДАНІ КОМПАНІЇ:
{{ JSON.stringify($input.all(), null, 2) }}

ЗАВДАННЯ:
Проаналізуй всі надані дані та створи детальний аналіз. Якщо даних мало - зроби обґрунтовані висновки.

ПОВЕРНИ JSON У ТАКОМУ ФОРМАТІ (БЕЗ ```json):
{
  "company": "назва компанії",
  "url": "URL компанії",
  "youtubeActivity": "опис YouTube активності або '-'",
  "linkedinActivity": "LinkedIn профіль або '-'",
  "facebookActivity": "Facebook сторінка або '-'",
  "aggregatorMentions": "згадки на G2/Capterra або '-'",
  "socialMentionsCount": 0,
  "newFeatures": ["список нових фіч і можливостей продукту"],
  "problems": ["виявлені проблеми та скарги клієнтів"],
  "reviewInsights": "короткий аналіз відгуків клієнтів",
  "news": ["новини компанії"],
  "blogArticles": [{"title": "назва", "date": "YYYY-MM-DD", "summary": "опис"}],
  "customerPains": ["болі клієнтів з відгуків"],
  "customerWants": ["побажання клієнтів"],
  "summary": "Детальний аналіз: позиціонування, сильні/слабкі сторони, онлайн-присутність, маркетингова активність (3-5 речень)"
}

ВАЖЛИВО:
- Повертай ТІЛЬКИ valid JSON
- Заповнюй ВСІ масиви даними (мінімум 1-2 елементи)
- Якщо даних немає - вкажи це явно у відповідному полі
- НЕ використовуй markdown блоки (```)
```

---

## 🛠️ Виправлення #4: Format for Sheets3 - Покращення

Додайте logging для діагностики. Замініть код ноди **Format for Sheets3**:

```javascript
const data = $input.item.json;
const ai = data.aiAnalysis || {};

// ДОДАНО: Логування для діагностики
console.log('=== FORMAT FOR SHEETS DEBUG ===');
console.log('Company:', data.company);
console.log('AI Analysis exists:', !!ai);
console.log('AI Summary exists:', !!ai.summary);
console.log('Features count:', (ai.newFeatures || []).length);
console.log('Problems count:', (ai.problems || []).length);

const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return "-";
  if (arr.length === 0) return "-";
  return arr.join(", ");
};

const blogToString = (articles) => {
  if (!Array.isArray(articles)) return "-";
  if (articles.length === 0) return "-";
  return articles.map(a => {
    const title = a.title || a.name || 'Article';
    const date = a.date || a.publishedAt || '?';
    const summary = (a.summary || a.description || a.preview || '').substring(0, 80);
    return title + " (" + date + "): " + summary + "...";
  }).join(" | ");
};

// Витягування даних з aiAnalysis
const newFeatures = ai.newFeatures || ai.features || [];
const problems = ai.problems || ai.issues || [];
const pains = ai.customerPains || ai.pains || [];
const wants = ai.customerWants || ai.wants || [];
const news = ai.news || ai.newsItems || [];
const blogArticles = ai.blogArticles || ai.blogs || [];
const reviewInsights = ai.reviewInsights || ai.reviews || ai.customerInsights || '-';

// Fallback до прямих полів
const featuresText = newFeatures.length > 0 ? arrayToString(newFeatures) :
  (data.features || data.newFeatures || '-');
const problemsText = problems.length > 0 ? arrayToString(problems) :
  (data.problems || data.issues || '-');
const painsText = pains.length > 0 ? arrayToString(pains) :
  (data.customerPains || data.pains || '-');
const wantsText = wants.length > 0 ? arrayToString(wants) :
  (data.customerWants || data.wants || '-');
const newsText = news.length > 0 ? arrayToString(news) :
  (data.news || data.newsItems || '-');
const blogText = blogArticles.length > 0 ? blogToString(blogArticles) :
  (data.blogArticles || data.blogs || '-');
const insightsText = reviewInsights !== '-' ? reviewInsights :
  (data.reviewInsights || data.reviews || data.customerInsights || '-');

// YouTube/Facebook/LinkedIn
const youtubeActivity = data.youtubeActivity || data.youtube || 'Немає даних';
const facebookActivity = data.facebookActivity || data.facebook || '-';
const linkedinActivity = data.linkedinActivity || data.linkedin || '-';

// G2 / Агрегатори
const aggregatorMentions = data.aggregatorMentions || data.g2Data || '-';

const result = {
  "Дата": new Date().toISOString().split("T")[0],
  "Компанія": data.company || "Unknown",
  "URL": data.url || "",
  "Нові фічі": featuresText,
  "Проблеми": problemsText,
  "Інсайти з коментарів": insightsText,
  "Новини (з останньої перевірки)": newsText,
  "Статті в блозі (з останньої перевірки)": blogText,
  "YouTube активність": youtubeActivity,
  "Facebook активність": facebookActivity,
  "LinkedIn активність": linkedinActivity,
  "Згадки на агрегаторах": aggregatorMentions,
  "Кількість згадок в соцмережах": String(data.socialMentionsCount || data.socialLinksCount || 0),
  "Болі клієнтів з коментарів": painsText,
  "Хотілки клієнтів з коментарів": wantsText,
  "AI Summary": ai.summary || data.summary || '-',
  _originalData: { company: data.company, url: data.url, parsedAt: data.parsedAt },
  _isNewData: true
};

// ДОДАНО: Логування результату
console.log("Result fields filled:");
console.log("- Features:", result["Нові фічі"] !== '-');
console.log("- Problems:", result["Проблеми"] !== '-');
console.log("- AI Summary:", result["AI Summary"] !== '-');
console.log('================================');

return result;
```

---

## 📝 Порядок виправлень:

1. **Спочатку:** Виправте **Append New Row1** і **Update Existing Row1** (додайте fallback)
2. **Потім:** Оптимізуйте промпт в **AI Agent1**
3. **Опціонально:** Додайте logging в **Format for Sheets3** для діагностики

---

## ✅ Перевірка після виправлень:

1. Збережіть workflow
2. Запустіть вручну на **1 компанії**
3. Перевірте в Execution log:
   - Чи всі ноди виконалися успішно
   - Чи є дані в **Format for Sheets3** output
   - Чи записалися дані в Google Sheets
4. Якщо все ОК → запускайте на всіх компаніях

---

## 🎯 Очікувані результати:

- ✅ Execution не падатиме на Append New Row
- ✅ AI Agent працюватиме швидше (40-60 сек замість 100)
- ✅ Більше даних у таблиці (features, problems, summary)
- ✅ Менше порожніх полів "-"

---

## 🆘 Якщо після виправлень все ще проблеми:

1. Перевірте Console log в execution (там є console.log з Format for Sheets3)
2. Подивіться на output ноди **Parse AI JSON Response3** - чи правильно парсується JSON
3. Перевірте чи AI повертає valid JSON без markdown блоків

