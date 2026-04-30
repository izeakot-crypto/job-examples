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
