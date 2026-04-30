# Інструкції для оновлення Prepare AI Prompt node

## Проблема
Користувач замінив HTTP Request node (AI Analysis1) на AI Agent node. Тепер потрібно оновити "Prepare AI Prompt" node щоб він генерував правильний формат промпту для AI Agent замість HTTP Request.

## Що потрібно зробити

### Варіант 1: Оновити через n8n UI (РЕКОМЕНДОВАНО - 2 хвилини)

1. Відкрити workflow: https://n8nletsdo.online/workflow/qk1bISszvNIH6Ww7
2. Знайти ноду **Prepare AI Prompt** (між Parse All Data1 та AI Analysis1)
3. Відкрити ноду (подвійний клік)
4. Замінити весь код на новий (нижче)
5. Натиснути **Save**
6. Запустити тест

### Новий код для Prepare AI Prompt node:

```javascript
// Prepare prompt for AI Agent
const data = $input.item.json;

const blogArticles = data.currentData.blog.recentArticles || [];
const blogText = blogArticles.map(a => `- ${a.title} (${a.date}): ${a.preview}`).join('\n');

const reviewsText = data.currentData.reviews.samples.join('\n- ') || 'Немає відгуків';

const aiPrompt = `Ти - expert аналітик VoIP/Contact Center індустрії. Проаналізуй компанію ${data.company} на основі зібраних даних.

КОМПАНІЯ: ${data.company}
URL: ${data.url}

ДАНІ З БЛОГУ:
Знайдено статей: ${data.currentData.blog.articlesFound}
${blogText || 'Немає статей'}

ВІДГУКИ ТА КОМЕНТАРІ:
- ${reviewsText}

ЗАВДАННЯ:
Проаналізуй дані та поверни ВИКЛЮЧНО valid JSON (без жодного додаткового тексту!) з такими полями:

{
  "newFeatures": ["масив рядків - нові функції або продукти згадані в блозі"],
  "problems": ["масив рядків - проблеми або виклики згадані в матеріалах"],
  "reviewInsights": "рядок - загальні інсайти з відгуків та коментарів",
  "news": ["масив рядків - новини компанії з останньої перевірки"],
  "blogArticles": [
    {
      "title": "назва статті",
      "date": "YYYY-MM-DD",
      "summary": "короткий саммарі статті 1-2 речення"
    }
  ],
  "customerPains": ["масив рядків - болі клієнтів витягнуті з відгуків"],
  "customerWants": ["масив рядків - хотілки та побажання клієнтів"],
  "summary": "загальний саммарі аналізу компанії 2-3 речення"
}

ВАЖЛИВО:
- Якщо немає даних для певного поля - повертай пустий масив [] або пустий рядок ""
- Для blogArticles використовуй дані з розділу "ДАНІ З БЛОГУ"
- Для customerPains та customerWants аналізуй розділ "ВІДГУКИ ТА КОМЕНТАРІ"
- Повертай ТІЛЬКИ JSON, без додаткового тексту!`;

return {
  prompt: aiPrompt,
  company: data.company,
  url: data.url
};
```

## Що змінилось?

### Старий формат (для HTTP Request):
```javascript
return {
  requestBody: {
    model: 'gpt-4o-2024-08-06',
    messages: [...],
    response_format: { type: 'json_object' },
    temperature: 0.7,
    max_tokens: 2000
  },
  company: data.company,
  url: data.url
};
```

### Новий формат (для AI Agent):
```javascript
return {
  prompt: aiPrompt,  // ← просто текстовий рядок з промптом
  company: data.company,
  url: data.url
};
```

## Додаткові кроки

### Після оновлення Prepare AI Prompt потрібно перевірити AI Agent node:

1. Відкрити ноду **AI Agent** (AI Analysis1)
2. Переконатись що в полі "Prompt" вказано: `={{ $json.prompt }}`
3. Переконатись що Model = GPT-4o або аналогічний
4. В Advanced Options:
   - Response Format = JSON Object
   - Temperature = 0.7
   - Max Tokens = 2000

### Можливі проблеми:

#### Проблема 1: AI Agent повертає текст замість JSON
**Рішення:** Переконайтесь що в AI Agent node:
- Response Format = "json_object"
- Prompt містить інструкцію "Повертай ТІЛЬКИ JSON"

#### Проблема 2: Parse AI JSON Response1 не може розпарсити відповідь
**Причина:** AI Agent може повертати дані в іншому форматі ніж HTTP Request

**Рішення:** Оновити Parse AI JSON Response1 node:
```javascript
const response = $input.item.json;
let aiData;

try {
  // For AI Agent, response might be directly in json.output or json.text
  const content = response.output || response.text || response.choices?.[0]?.message?.content || '';

  aiData = JSON.parse(content);

  // Validate required fields...
} catch (error) {
  // Fallback structure...
}
```

## Варіант 2: Використати готовий JSON файл

Файл `updated_prepare_ai_prompt_node.json` містить готову конфігурацію ноди.

**НЕ ПРАЦЮЄ** через обмеження n8n MCP API - потрібно оновлювати весь workflow, а не окрему ноду.

---

## Файли в проекті:

1. `prepare_ai_prompt_for_agent.js` - код для AI Agent формату (✅ готовий)
2. `ai_analysis_body.json` - старий формат для HTTP Request (deprecated)
3. `updated_prepare_ai_prompt_node.json` - JSON конфігурація ноди
4. `MANUAL_UPDATE_INSTRUCTIONS.md` - ці інструкції

---

**РЕКОМЕНДАЦІЯ:** Оновити через UI (Варіант 1) - найшвидший та найбезпечніший спосіб.
