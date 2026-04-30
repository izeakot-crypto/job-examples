# Оптимізовані промпти для AI Agent (30-40k токенів)

## Проблема
- Поточний AI Agent споживає 200k+ токенів
- Дуже дорого!
- Потрібно оптимізувати до 30-40k на компанію

---

## SYSTEM PROMPT (скопіювати в AI Agent → Options → System Message)

```
Ти аналітик конкурентів VoIP/контакт-центрів. Аналізуй INPUT дані і поверни JSON.

КРИТИЧНО:
- НЕ використовуй tools - всі дані вже в INPUT
- Поверни ТІЛЬКИ JSON без ```markdown```
- Максимум 3 речення на кожне поле

ФОРМАТ ВІДПОВІДІ:
{
  "company": "назва",
  "url": "url",
  "youtubeActivity": "опис або -",
  "linkedinActivity": "-",
  "facebookActivity": "-",
  "aggregatorMentions": "G2 інфо або -",
  "socialMentionsCount": число,
  "newFeatures": ["фіча1", "фіча2", "фіча3"],
  "problems": ["проблема1 або -"],
  "reviewInsights": "1 речення",
  "news": ["новина або -"],
  "blogArticles": [{"title":"","date":"","summary":""}],
  "customerPains": ["біль1", "біль2", "біль3"],
  "customerWants": ["потреба1", "потреба2", "потреба3"],
  "summary": "2-3 речення"
}
```

---

## USER PROMPT (скопіювати в AI Agent → Text)

```
=Аналізуй компанію на основі зібраних даних.

КОМПАНІЯ: {{ $input.all().find(i => i.json.company || i.json.companyName)?.json.company || $input.all().find(i => i.json.company || i.json.companyName)?.json.companyName || 'Unknown' }}
URL: {{ $input.all().find(i => i.json.url || i.json.companyUrl)?.json.url || $input.all().find(i => i.json.url || i.json.companyUrl)?.json.companyUrl || '-' }}

ЗІБРАНІ ДАНІ З САЙТУ:
{{
const pages = $input.all().filter(i => i.json.categorizedData);
const features = pages.flatMap(p => p.json.categorizedData?.features || []).slice(0,3);
const blog = pages.flatMap(p => p.json.categorizedData?.blog || []).slice(0,3);
const reviews = pages.flatMap(p => p.json.categorizedData?.reviews || []).slice(0,2);
const pricing = pages.flatMap(p => p.json.categorizedData?.pricing || []).slice(0,2);
const news = pages.flatMap(p => p.json.categorizedData?.news || []).slice(0,2);

let result = '';
if (features.length) result += 'FEATURES:\n' + features.map(f => '- ' + (f.metadata?.title || '')).join('\n') + '\n\n';
if (blog.length) result += 'BLOG:\n' + blog.map(b => '- ' + (b.metadata?.title || '') + ': ' + (b.summary || '').substring(0,150)).join('\n') + '\n\n';
if (reviews.length) result += 'REVIEWS:\n' + reviews.map(r => (r.summary || '').substring(0,200)).join('\n') + '\n\n';
if (pricing.length) result += 'PRICING:\n' + pricing.map(p => (p.metadata?.title || '') + ' - ' + (p.content?.prices?.slice(0,3).join(', ') || '')).join('\n') + '\n\n';
if (news.length) result += 'NEWS:\n' + news.map(n => (n.metadata?.title || '')).join('\n') + '\n\n';
return result || 'Дані з сайту не знайдено';
}}

YOUTUBE:
{{ $input.all().find(i => i.json.youtubeActivity)?.json.youtubeActivity || '-' }}

СОЦМЕРЕЖІ:
{{
const social = $input.all().find(i => i.json.socialLinksCount !== undefined)?.json;
social ? `LinkedIn: ${social.linkedinActivity || '-'}, Facebook: ${social.facebookActivity || '-'}, VK: ${social.vkActivity || '-'}, Telegram: ${social.telegramActivity || '-'}, Всього: ${social.socialLinksCount || 0}` : '-'
}}

G2/АГРЕГАТОРИ:
{{ $input.all().find(i => i.json.aggregatorMentions)?.json.aggregatorMentions || '-' }}

---
На основі даних вище, поверни JSON з полями:
- company, url (з даних)
- youtubeActivity (опис активності)
- linkedinActivity, facebookActivity (з соцмереж)
- aggregatorMentions (G2 рейтинг)
- socialMentionsCount (число)
- newFeatures (3-5 ключових фіч з FEATURES)
- problems (проблеми зі скарг, або ["-"])
- reviewInsights (1 речення з REVIEWS)
- news (новини або ["-"])
- blogArticles (до 3 статей з BLOG)
- customerPains (3 болі клієнтів)
- customerWants (3 потреби клієнтів)
- summary (2-3 речення про позиціонування компанії)
```

---

## АЛЬТЕРНАТИВНИЙ USER PROMPT (простіший, менше токенів)

Якщо перший prompt не працює, використай цей:

```
=Компанія: {{ $input.all()[0]?.json.company || $input.all()[0]?.json.companyName || 'Unknown' }}
URL: {{ $input.all()[0]?.json.url || $input.all()[0]?.json.companyUrl || '-' }}

Дані (summary):
{{ JSON.stringify($input.all().map(i => ({
  type: i.json.categorizedData ? 'page' : (i.json.youtubeActivity ? 'youtube' : (i.json.socialLinksCount !== undefined ? 'social' : 'g2')),
  title: i.json.categorizedData?.features?.[0]?.metadata?.title || i.json.categorizedData?.blog?.[0]?.metadata?.title || i.json.youtubeActivity || i.json.aggregatorMentions || '-'
})).slice(0,10), null, 0) }}

YouTube: {{ $input.all().find(i => i.json.youtubeActivity)?.json.youtubeActivity || '-' }}
Social: {{ $input.all().find(i => i.json.socialLinksCount)?.json.socialLinksCount || 0 }} links
G2: {{ $input.all().find(i => i.json.aggregatorMentions)?.json.aggregatorMentions || '-' }}

Поверни JSON:
{"company":"","url":"","youtubeActivity":"","linkedinActivity":"-","facebookActivity":"-","aggregatorMentions":"","socialMentionsCount":0,"newFeatures":[],"problems":["-"],"reviewInsights":"-","news":["-"],"blogArticles":[],"customerPains":[],"customerWants":[],"summary":""}
```

---

## AI Agent Settings (в n8n)

1. **Options → System Message**: вставити SYSTEM PROMPT
2. **Text**: вставити USER PROMPT
3. **Max Iterations**: встановити `3` (замість 10+)
4. **Tools**: Можна відключити tools якщо всі дані вже зібрані

---

## Оцінка токенів

| Компонент | Токени |
|-----------|--------|
| System Prompt | ~150 |
| User Prompt (з даними) | ~3,000-8,000 |
| AI Response | ~500-1,000 |
| **TOTAL** | **~5,000-10,000** |

При 19 компаніях: **~100-200k токенів** на весь run (замість 3-4M)

---

## Excel колонки ✅

AI output коректно маппиться на Excel:

| AI Field | Excel колонка |
|----------|---------------|
| company | Компанія |
| url | URL |
| newFeatures | Нові фічі |
| problems | Проблеми |
| reviewInsights | Інсайти з коментарів |
| news | Новини |
| blogArticles | Статті в блозі |
| youtubeActivity | YouTube активність |
| facebookActivity | Facebook активність |
| linkedinActivity | LinkedIn активність |
| aggregatorMentions | Згадки на агрегаторах |
| socialMentionsCount | Кількість згадок |
| customerPains | Болі клієнтів |
| customerWants | Хотілки клієнтів |
| summary | AI Summary |

---

## Як застосувати

1. Відкрий n8n: https://n8n.oki-toki.net/workflow/i8tUO6CtinXxJFu2
2. Клікни на **AI Agent** node
3. В **Options → System Message** - вставити SYSTEM PROMPT
4. В **Text** - вставити USER PROMPT
5. Save workflow
6. Тестуй на 1 компанії
