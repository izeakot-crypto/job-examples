#!/usr/bin/env python3
"""
Fix workflow - updates AI Agent and Aggregate by Category nodes
"""
import json
import re

# Read workflow
with open('workflow_current.json', 'r', encoding='utf-8-sig') as f:
    workflow = json.load(f)

print(f"Workflow: {workflow['name']}")
print(f"Nodes count: {len(workflow['nodes'])}")

# New system prompt for AI Agent
NEW_SYSTEM_PROMPT = """Ти аналітик конкурентів VoIP/контакт-центрів. Аналізуй INPUT дані і поверни JSON.

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
}"""

# New user prompt for AI Agent
NEW_USER_PROMPT = """=Аналізуй компанію на основі зібраних даних.

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
if (features.length) result += 'FEATURES:\\n' + features.map(f => '- ' + (f.metadata?.title || '')).join('\\n') + '\\n\\n';
if (blog.length) result += 'BLOG:\\n' + blog.map(b => '- ' + (b.metadata?.title || '') + ': ' + (b.summary || '').substring(0,150)).join('\\n') + '\\n\\n';
if (reviews.length) result += 'REVIEWS:\\n' + reviews.map(r => (r.summary || '').substring(0,200)).join('\\n') + '\\n\\n';
if (pricing.length) result += 'PRICING:\\n' + pricing.map(p => (p.metadata?.title || '') + ' - ' + (p.content?.prices?.slice(0,3).join(', ') || '')).join('\\n') + '\\n\\n';
if (news.length) result += 'NEWS:\\n' + news.map(n => (n.metadata?.title || '')).join('\\n') + '\\n\\n';
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
- summary (2-3 речення про позиціонування компанії)"""

# New code for Aggregate by Category
NEW_AGGREGATE_CODE = """// Aggregate by Category - FIXED VERSION
// Збирає всі розпарсені сторінки в один об'єкт для AI Agent

const allPages = $input.all();

// Отримуємо дані компанії
let companyName = 'Unknown';
let companyUrl = '';

if (allPages.length > 0 && allPages[0].json) {
  companyName = allPages[0].json.companyName || allPages[0].json.company || 'Unknown';
  companyUrl = allPages[0].json.companyUrl || allPages[0].json.url || '';
}

// Категоризуємо сторінки
const byCategory = {
  blog: [],
  news: [],
  reviews: [],
  pricing: [],
  features: []
};

for (const page of allPages) {
  const pageData = page.json;
  const category = pageData.category || 'other';
  if (byCategory[category]) {
    byCategory[category].push({
      url: pageData.url || '',
      title: pageData.title || '',
      description: pageData.description || '',
      content: (pageData.content || '').substring(0, 500)
    });
  }
}

// Статистика
const stats = {};
for (const cat in byCategory) {
  stats[cat] = byCategory[cat].length;
}

// Формуємо структуру даних для AI Agent
return {
  json: {
    company: companyName,
    url: companyUrl,
    currentData: {
      website: {
        title: byCategory.features[0]?.title || byCategory.blog[0]?.title || '-',
        description: byCategory.features[0]?.description || byCategory.blog[0]?.description || '-'
      },
      blog: {
        articlesFound: byCategory.blog.length,
        articles: byCategory.blog.slice(0, 5)
      },
      news: {
        count: byCategory.news.length,
        items: byCategory.news.slice(0, 3)
      },
      reviews: {
        count: byCategory.reviews.length,
        items: byCategory.reviews.slice(0, 3)
      },
      pricing: byCategory.pricing[0] || null,
      features: byCategory.features.slice(0, 3)
    },
    totalPagesParsed: allPages.length,
    statistics: stats,
    aggregatedAt: new Date().toISOString()
  }
};"""

# Update nodes
nodes_updated = 0

for node in workflow['nodes']:
    # Update AI Agent
    if node['name'] == 'AI Agent':
        node['parameters']['options']['systemMessage'] = NEW_SYSTEM_PROMPT
        node['parameters']['text'] = NEW_USER_PROMPT
        nodes_updated += 1
        print("[OK] Updated: AI Agent")

    # Update Aggregate by Category
    if node['name'] == 'Aggregate by Category':
        node['parameters']['jsCode'] = NEW_AGGREGATE_CODE
        nodes_updated += 1
        print("[OK] Updated: Aggregate by Category")

print(f"\nTotal nodes updated: {nodes_updated}")

# Save updated workflow
output_file = 'workflow_fixed.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)

print(f"[OK] Saved to: {output_file}")
print(f"\nTo import: Go to n8n -> Import from File -> Select {output_file}")
