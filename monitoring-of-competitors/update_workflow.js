const fs = require('fs');

// Шлях до збереженого воркфлоу
const workflowPath = 'C:/Users/izeak/.claude/projects/C--Users-izeak-OneDrive-Work-Oki-toki-Monitoring-of-competitors/c07261c1-a225-44cb-a2ce-90406882e3d3/tool-results/mcp-n8n-flexible-n8n_get_workflow-1766652626938.txt';
const data = JSON.parse(fs.readFileSync(workflowPath, 'utf-8'));
const workflow = JSON.parse(data[0].text);

// Код для Prepare AI Prompt
const prepareCode = `const items = $input.all();

const websiteData = items[0]?.json || {};
const youtubeData = items[1]?.json || {};
const socialData = items[2]?.json || {};
const g2Data = items[3]?.json || {};
const sitemapData = items[4]?.json || {};

const company = websiteData.company || 'Невідомо';
const url = websiteData.url || '-';
const website = websiteData.currentData?.website || {};
const blog = websiteData.currentData?.blog || {};
const reviews = websiteData.currentData?.reviews || {};

const blogArticles = (blog.recentArticles || []).map(a => '- "' + a.title + '" (' + (a.date || 'невідома') + ')').join('\\n') || 'Статті не знайдені';
const reviewsSamples = (reviews.samples || []).map((r, i) => 'Відгук ' + (i+1) + ': ' + r).join('\\n') || 'Відгуки не знайдені';

const prompt = \`КОНКУРЕНТНА РОЗВІДКА

Дата аналізу: \${new Date().toISOString().split('T')[0]}
Компанія: \${company}
Website URL: \${url}

WEBSITE ANALYSIS:
Title: \${website.title || 'відсутній'}
Description: \${website.description || 'відсутній'}
H1 Tags: \${(website.h1Tags || []).join(', ') || 'відсутні'}
Має News: \${website.hasNews || false}
Має Blog: \${website.hasBlog || false}
Має Pricing: \${website.hasPricing || false}
Має Features: \${website.hasFeatures || false}

BLOG CONTENT:
Статей знайдено: \${blog.articlesFound || 0}
\${blogArticles}

CUSTOMER REVIEWS:
Знайдено: \${reviews.found ? 'так' : 'ні'}
Кількість: \${reviews.count || 0}
\${reviewsSamples}

YOUTUBE ACTIVITY:
\${youtubeData.youtubeActivity || '-'}

SOCIAL MEDIA:
LinkedIn: \${socialData.linkedinActivity || '-'}
Facebook: \${socialData.facebookActivity || '-'}
All Social: \${socialData.allSocialLinks || '-'}

G2 AGGREGATOR:
Status: \${g2Data.aggregatorMentions || '-'}
Rating: \${g2Data.g2Rating || 'відсутній'}
Reviews: \${g2Data.g2ReviewsCount || 0}

SITEMAP PARSING:
\${sitemapData.totalPagesParsed ? 'Спарсено сторінок: ' + sitemapData.totalPagesParsed : 'Не парсився'}
\${sitemapData.statistics ? 'Blog: ' + (sitemapData.statistics.blog || 0) + ', News: ' + (sitemapData.statistics.news || 0) + ', Pricing: ' + (sitemapData.statistics.pricing || 0) + ', Features: ' + (sitemapData.statistics.features || 0) : ''}

ЗАВДАННЯ:
Проаналізуй всі дані та поверни JSON з аналізом.\`;

return [{
  json: {
    company,
    url,
    youtubeActivity: youtubeData.youtubeActivity || '-',
    linkedinActivity: socialData.linkedinActivity || '-',
    facebookActivity: socialData.facebookActivity || '-',
    aggregatorMentions: g2Data.aggregatorMentions || '-',
    socialLinksCount: socialData.socialLinksCount || 0,
    g2ReviewsCount: g2Data.g2ReviewsCount || 0,
    preparedPrompt: prompt
  }
}];`;

// System prompt
const systemPrompt = `Ти - Senior Business Intelligence Analyst з 10+ роками досвіду в VoIP/Contact Center індустрії.

КРИТИЧНІ ВИМОГИ:
1. Аналізуй дані як експерт з 10-річним стажем
2. Виявляй patterns, trends та strategic implications
3. Фокусуйся на бізнес-цінності
4. Відсутність даних - це теж insight про digital maturity
5. Повертай ВИКЛЮЧНО valid JSON БЕЗ markdown блоків

ФОРМАТ ВІДПОВІДІ:
{
  "company": "назва компанії",
  "url": "URL компанії",
  "youtubeActivity": "активність",
  "linkedinActivity": "активність",
  "facebookActivity": "активність",
  "aggregatorMentions": "згадки",
  "newFeatures": ["фіча1", "фіча2"],
  "problems": ["проблема1"],
  "reviewInsights": "4-6 речень аналізу",
  "news": ["новина1"],
  "blogArticles": [{"title": "назва", "date": "YYYY-MM-DD", "summary": "опис"}],
  "customerPains": ["біль1"],
  "customerWants": ["потреба1"],
  "summary": "4-5 речень executive summary"
}

ПРАВИЛА:
- Якщо blog відсутній - слабка content marketing strategy
- Якщо немає на G2 - втрачають social proof у B2B
- Відсутність даних - valuable insight про digital maturity
- ТІЛЬКИ JSON у відповіді`;

// Додаємо нову ноду
const prepareNode = {
  parameters: { jsCode: prepareCode },
  id: 'prepare-ai-prompt-001',
  name: 'Prepare AI Prompt',
  type: 'n8n-nodes-base.code',
  typeVersion: 2,
  position: [3320, -784]
};

workflow.nodes.push(prepareNode);

// Оновлюємо connections
workflow.connections['Merge4'] = {
  main: [[{ node: 'Prepare AI Prompt', type: 'main', index: 0 }]]
};

workflow.connections['Prepare AI Prompt'] = {
  main: [[{ node: 'AI Agent1', type: 'main', index: 0 }]]
};

// Оновлюємо AI Agent1
const aiAgent = workflow.nodes.find(n => n.name === 'AI Agent1');
if (aiAgent) {
  aiAgent.parameters.text = '{{ $json.preparedPrompt }}';
  aiAgent.parameters.options = aiAgent.parameters.options || {};
  aiAgent.parameters.options.systemMessage = systemPrompt;
}

// Зберігаємо
const outputPath = 'C:/Users/izeak/OneDrive/Work.Oki-toki/Monitoring of competitors/updated_workflow_v2.json';
fs.writeFileSync(outputPath, JSON.stringify(workflow, null, 2));

console.log('Workflow updated!');
console.log('Nodes count:', workflow.nodes.length);
console.log('New node added:', workflow.nodes.some(n => n.name === 'Prepare AI Prompt'));
console.log('AI Agent1 text:', aiAgent?.parameters?.text);
console.log('Saved to:', outputPath);

// Format for Sheets3 - FIXED
const formatForSheetsCode = `// Format for Sheets - PASS THROUGH VERSION
const data = $input.item.json;
const ai = data.aiAnalysis || {};

const arrayToString = (arr) => {
  if (!Array.isArray(arr)) return "-";
  if (arr.length === 0) return "-";
  return arr.join(", ");
};

const blogToString = (articles) => {
  if (!Array.isArray(articles)) return "-";
  if (articles.length === 0) return "-";
  return articles.map(a => a.title + " (" + (a.date || "?") + "): " + (a.summary || "").substring(0, 100) + "...").join(" | ");
};

const result = {
  "Дата": new Date().toISOString().split("T")[0],
  "Компанія": data.company || "Unknown",
  "URL": data.url || "",
  "Нові фічі": arrayToString(ai.newFeatures),
  "Проблеми": arrayToString(ai.problems),
  "Інсайти з коментарів": ai.reviewInsights || "-",
  "Новини (з останньої перевірки)": arrayToString(ai.news),
  "Статті в блозі (з останньої перевірки)": blogToString(ai.blogArticles),
  "YouTube активність": data.youtubeActivity || "-",
  "Facebook активність": data.facebookActivity || "-",
  "LinkedIn активність": data.linkedinActivity || "-",
  "Згадки на агрегаторах": data.aggregatorMentions || "-",
  "Кількість згадок в соцмережах": String(data.socialMentionsCount || 0),
  "Болі клієнтів з коментарів": arrayToString(ai.customerPains),
  "Хотілки клієнтів з коментарів": arrayToString(ai.customerWants),
  "AI Summary": ai.summary || "-",
  _originalData: { company: data.company, url: data.url, parsedAt: data.parsedAt },
  _isNewData: true
};

console.log("Format for Sheets - Company:", result["Компанія"]);
return result;`;

// Check If Company Exists1 - FIXED
const checkIfCompanyExistsCode = `// Check If Company Exists - FIXED VERSION
const allInputs = $input.all();

// Input 0 - дані з Format for Sheets (нові дані)
const newCompanyData = allInputs[0].json;

const company = newCompanyData['Компанія'] || newCompanyData._originalData?.company || 'Unknown';
const url = newCompanyData['URL'] || newCompanyData._originalData?.url || '';

console.log('=== CHECK IF COMPANY EXISTS ===');
console.log('New company:', company);
console.log('New URL:', url);
console.log('All input items:', allInputs.length);

// Get Existing Data передає всі рядки як input 1, 2, 3, ...
const existingRows = [];

// Проходимо по всіх input крім першого (перший - це нові дані)
for (let i = 1; i < allInputs.length; i++) {
  const item = allInputs[i];
  // Перевіряємо чи це не пустий об'єкт
  if (item && item.json && Object.keys(item.json).length > 1) {
    existingRows.push(item.json);
  }
}

console.log('Existing rows found:', existingRows.length);

// Шукаємо компанію в існуючих рядах
let foundRow = null;
let rowIndex = -1;

// Нормалізуємо ключі пошуку для порівняння
const searchCompany = company.toString().toLowerCase().trim();
const searchUrl = url.toString().toLowerCase().trim();

for (let i = 0; i < existingRows.length; i++) {
  const row = existingRows[i];

  // Отримуємо назву компанії з різних можливих полів
  const rowCompany = (row['Компанія'] || row['Company'] || row['company'] || '').toString().toLowerCase().trim();
  const rowUrl = (row['URL'] || row['Url'] || row['url'] || '').toString().toLowerCase().trim();

  // Порівнюємо по назві АБО по URL
  if (rowCompany === searchCompany || rowUrl === searchUrl) {
    foundRow = row;
    rowIndex = i;
    console.log('Found existing company at index:', i);
    break;
  }
}

// Формуємо результат з action типом
const result = {
  // Всі дані для запису в Google Sheets
  'Дата': newCompanyData['Дата'],
  'Компанія': company,
  'URL': url,
  'Нові фічі': newCompanyData['Нові фічі'],
  'Проблеми': newCompanyData['Проблеми'],
  'Інсайти з коментарів': newCompanyData['Інсайти з коментарів'],
  'Новини (з останньої перевірки)': newCompanyData['Новини (з останньої перевірки)'],
  'Статті в блозі (з останньої перевірки)': newCompanyData['Статті в блозі (з останньої перевірки)'],
  'YouTube активність': newCompanyData['YouTube активність'],
  'Facebook активність': newCompanyData['Facebook активність'],
  'LinkedIn активність': newCompanyData['LinkedIn активність'],
  'Згадки на агрегаторах': newCompanyData['Згадки на агрегаторах'],
  'Кількість згадок в соцмережах': newCompanyData['Кількість згадок в соцмережах'],
  'Болі клієнтів з коментарів': newCompanyData['Болі клієнтів з коментарів'],
  'Хотілки клієнтів з коментарів': newCompanyData['Хотілки клієнтів з коментарів'],
  'AI Summary': newCompanyData['AI Summary'],

  // === CONTROL FIELDS ===
  // Для IF ноди - який тип операції
  '_action': foundRow ? 'update' : 'append',

  // Для Update ноди - ідентифікатор рядка
  '_rowId': foundRow?.id || foundRow?.rowNumber || (rowIndex >= 0 ? rowIndex + 2 : null),

  // Для відладки
  '_isUpdate': !!foundRow,
  '_matchInfo': foundRow ? {
    matchedBy: foundRow['Компанія']?.toLowerCase() === searchCompany ? 'name' : 'url',
    existingCompany: foundRow['Компанія'],
    existingUrl: foundRow['URL']
  } : null
};

console.log('Action:', result._action);
console.log('Row ID:', result._rowId);
console.log('============================');

return result;`;

// Nodes to update
const nodesToUpdate = [
  {
    id: "79d14816-a09a-464e-91fb-a365e6e252b1",
    name: "Format for Sheets3",
    type: "n8n-nodes-base.code",
    typeVersion: 2,
    position: [3136, 1008],
    parameters: { jsCode: formatForSheetsCode }
  },
  {
    id: "66310e8c-9b80-4e44-b090-35885fdbde7a",
    name: "Check If Company Exists1",
    type: "n8n-nodes-base.code",
    typeVersion: 2,
    position: [3472, 1008],
    parameters: { jsCode: checkIfCompanyExistsCode }
  }
];

fs.writeFileSync('update_nodes_final.json', JSON.stringify({ nodes: nodesToUpdate }, null, 2));
console.log('Created update_nodes_final.json');
